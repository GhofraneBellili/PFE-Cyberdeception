"""
Réf. architecture : "8. Base de connaissances ATT&CK" — contrat technique
du PFE Cyberdéception (CLAUDE.md).

Couche de connaissance offensive MITRE ATT&CK : chargement et validation
documentaire d'un bundle STIX enterprise-attack.json, extraction des
techniques (objets "attack-pattern"), indexation déterministe par
identifiant ATT&CK Txxxx / Txxxx.xxx, et accès en lecture pour les futurs
modules.

Ce module est une base de connaissances structurée déterministe : il ne
fait ni sélection de déception, ni SP1, ni RAG, ni appel LLM, ni calcul de
risque, ni optimisation. Il ne contient aucun identifiant de technique
ATT&CK ni aucun actif codé en dur : ces valeurs n'apparaissent que dans les
tests.

Convention : identifiants de code en anglais, commentaires et docstrings en
français (§25.1).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from src.schemas import ATTACK_TECHNIQUE_ID_PATTERN, AttackGraph

# ---------------------------------------------------------------------------
# Erreurs
# ---------------------------------------------------------------------------


class AttackKnowledgeError(Exception):
    """Erreur de base de la base de connaissances ATT&CK (bundle STIX
    structurellement invalide, ex. racine non-objet ou 'objects' absent)."""


class UnknownAttackTechniqueError(AttackKnowledgeError):
    """Levée quand un identifiant ATT&CK demandé n'existe pas dans la KB
    chargée (accès direct ou validation d'un graphe, réf. tâche §8/§9)."""


class DuplicateAttackTechniqueError(AttackKnowledgeError):
    """Levée quand deux objets attack-pattern actifs (retenus après filtrage
    revoked/deprecated) produisent le même identifiant ATT&CK (réf. tâche
    §6) : techniques_by_id doit rester non ambigu."""


# ---------------------------------------------------------------------------
# Modèle interne d'une technique
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AttackTechniqueRecord:
    """Réf. architecture : "8. Base de connaissances ATT&CK" — représentation
    interne immuable d'une technique ATT&CK extraite d'un bundle STIX.

    Les champs booléens (is_subtechnique, revoked, deprecated) valent False
    lorsque la propriété MITRE correspondante est absente du JSON source :
    c'est une représentation structurelle d'une absence, pas une donnée
    scientifique inventée (revoked/deprecated l'indiquent explicitement,
    réf. tâche §2/§7). description et version valent None lorsqu'absentes,
    pour la même raison — jamais de texte généré.
    """

    technique_id: str
    stix_id: str
    name: str
    description: str | None
    tactics: tuple[str, ...]
    platforms: tuple[str, ...]
    is_subtechnique: bool
    revoked: bool
    deprecated: bool
    version: str | None
    external_url: str | None


# ---------------------------------------------------------------------------
# Base de connaissances
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AttackKnowledgeBase:
    """Réf. architecture : "8. Base de connaissances ATT&CK" — index
    déterministe des techniques ATT&CK chargées depuis un bundle STIX.

    techniques_by_id est une Mapping en lecture seule (MappingProxyType) :
    aucune mutation externe n'est possible après chargement. L'ordre
    d'itération correspond à l'ordre d'apparition des objets dans le bundle
    source (stable et déterministe, pas une base vectorielle).
    """

    source_path: Path
    techniques_by_id: Mapping[str, AttackTechniqueRecord]
    bundle_type: str | None = None
    spec_version: str | None = None


# ---------------------------------------------------------------------------
# Extraction depuis un objet STIX attack-pattern
# ---------------------------------------------------------------------------

# Réf. tâche §1 : l'identifiant ATT&CK humain est lu depuis
# external_references, jamais déduit du nom ou du stix id.
_MITRE_SOURCE_NAME = "mitre-attack"
_TECHNIQUE_ID_RE = re.compile(ATTACK_TECHNIQUE_ID_PATTERN)


def _get_typed_optional(raw_object: dict, key: str, expected_type: type, default):
    """Lit un champ ATT&CK optionnel en distinguant explicitement deux cas
    (durcissement — ne jamais confondre un champ manquant avec un champ
    malformé) :

    - la clé est ABSENTE du JSON source -> `default` est retourné (défaut
      structurel autorisé, réf. tâche §2/§7, §25.3) ;
    - la clé est PRÉSENTE mais sa valeur n'est pas de type `expected_type`
      -> AttackKnowledgeError explicite (champ concerné, type attendu,
      objet STIX concerné si son id est disponible), au lieu d'être
      silencieusement traitée comme absente.
    """
    if key not in raw_object:
        return default
    value = raw_object[key]
    if not isinstance(value, expected_type):
        object_id = raw_object.get("id")
        id_part = f" (objet '{object_id}')" if isinstance(object_id, str) else ""
        raise AttackKnowledgeError(
            f"Champ '{key}' invalide{id_part} : type attendu "
            f"{expected_type.__name__}, reçu {type(value).__name__}."
        )
    return value


def _find_attack_reference(raw_object: dict) -> dict | None:
    """Cherche, dans external_references, la référence MITRE ATT&CK portant
    un external_id Txxxx / Txxxx.xxx exploitable. Retourne None si aucune
    référence exploitable n'est trouvée (réf. tâche §1/§5). external_references
    absent -> aucune référence (comportement inchangé) ; présent mais pas une
    liste -> AttackKnowledgeError (durcissement)."""
    references = _get_typed_optional(raw_object, "external_references", list, [])
    for reference in references:
        if not isinstance(reference, dict):
            continue
        if reference.get("source_name") != _MITRE_SOURCE_NAME:
            continue
        external_id = reference.get("external_id")
        if isinstance(external_id, str) and _TECHNIQUE_ID_RE.match(external_id):
            return reference
    return None


def _extract_tactics(raw_object: dict) -> tuple[str, ...]:
    """Réf. tâche §10 : les tactiques proviennent des kill_chain_phases
    ATT&CK (phase_name), conservées telles quelles — libellés canoniques
    ATT&CK (ex. "initial-access") — sans fuzzy matching ni reformulation.
    kill_chain_phases absent -> tuple vide ; présent mais pas une liste ->
    AttackKnowledgeError (durcissement)."""
    phases = _get_typed_optional(raw_object, "kill_chain_phases", list, [])
    tactics: list[str] = []
    for phase in phases:
        if not isinstance(phase, dict):
            continue
        if phase.get("kill_chain_name") != _MITRE_SOURCE_NAME:
            continue
        phase_name = phase.get("phase_name")
        if isinstance(phase_name, str):
            tactics.append(phase_name)
    return tuple(tactics)


def _extract_platforms(raw_object: dict) -> tuple[str, ...]:
    """platforms vient de x_mitre_platforms lorsqu'il existe et est une
    liste, sinon tuple vide si absent (réf. tâche §2) — jamais une
    plateforme inventée ; présent mais pas une liste -> AttackKnowledgeError
    (durcissement)."""
    platforms = _get_typed_optional(raw_object, "x_mitre_platforms", list, [])
    return tuple(platform for platform in platforms if isinstance(platform, str))


def _extract_bool(raw_object: dict, key: str) -> bool:
    """Champ booléen MITRE optionnel : False si absent (réf. tâche §2/§7) ;
    présent mais de type différent de bool -> AttackKnowledgeError
    (durcissement)."""
    return _get_typed_optional(raw_object, key, bool, False)


def _extract_str_or_none(raw_object: dict, key: str) -> str | None:
    """Champ texte MITRE optionnel : None si absent (réf. tâche §2/§13) ;
    présent mais de type différent de str -> AttackKnowledgeError
    (durcissement) — jamais de texte inventé."""
    return _get_typed_optional(raw_object, key, str, None)


def _parse_attack_pattern(raw_object: dict) -> AttackTechniqueRecord | None:
    """Construit un AttackTechniqueRecord à partir d'un objet STIX
    "attack-pattern", ou retourne None si l'objet n'est pas exploitable
    (pas d'external_id ATT&CK, ou champs structurels STIX manquants) — il
    est alors ignoré par l'appelant (réf. tâche §5). Un champ ATT&CK
    optionnel présent mais mal typé lève AttackKnowledgeError (durcissement)
    plutôt que d'être traité silencieusement comme absent."""
    reference = _find_attack_reference(raw_object)
    if reference is None:
        return None

    stix_id = raw_object.get("id")
    name = raw_object.get("name")
    if not isinstance(stix_id, str) or not isinstance(name, str):
        return None

    return AttackTechniqueRecord(
        technique_id=reference["external_id"],
        stix_id=stix_id,
        name=name,
        description=_extract_str_or_none(raw_object, "description"),
        tactics=_extract_tactics(raw_object),
        platforms=_extract_platforms(raw_object),
        is_subtechnique=_extract_bool(raw_object, "x_mitre_is_subtechnique"),
        revoked=_extract_bool(raw_object, "revoked"),
        deprecated=_extract_bool(raw_object, "x_mitre_deprecated"),
        version=_extract_str_or_none(raw_object, "x_mitre_version"),
        external_url=_extract_str_or_none(reference, "url"),
    )


# ---------------------------------------------------------------------------
# Chargement du bundle
# ---------------------------------------------------------------------------


def load_attack_knowledge(
    path: str | Path,
    *,
    include_revoked: bool = False,
    include_deprecated: bool = False,
) -> AttackKnowledgeBase:
    """Réf. architecture : "8. Base de connaissances ATT&CK" — charge un
    bundle STIX enterprise-attack.json et construit une AttackKnowledgeBase.

    Comportement (réf. tâche §4 à §7) :
    - un JSON syntaxiquement invalide lève json.JSONDecodeError ;
    - une racine non-objet, un "type" absent/différent de "bundle", ou un
      bundle sans liste "objects", lève AttackKnowledgeError ;
    - un champ ATT&CK optionnel présent mais mal typé (ex. "revoked": "false")
      lève AttackKnowledgeError au lieu d'être traité silencieusement comme
      absent (durcissement — absence ≠ malformation) ;
    - seuls les objets de type "attack-pattern" sont considérés ;
    - un attack-pattern sans external_id ATT&CK exploitable est ignoré
      (jamais de technique_id inventé, jamais stix_id en substitut) ;
    - par défaut, les techniques revoked et deprecated sont exclues de
      l'index (include_revoked / include_deprecated pour les inclure) ;
    - le doublon d'identifiant ATT&CK est détecté parmi les techniques
      effectivement retenues après filtrage revoked/deprecated (c'est cet
      ensemble, et lui seul, dont techniques_by_id doit être non ambigu,
      réf. tâche §6) ; un doublon lève DuplicateAttackTechniqueError.

    Aucune donnée du fichier source n'est modifiée.
    """
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as file:
        raw_bundle = json.load(file)

    if not isinstance(raw_bundle, dict):
        raise AttackKnowledgeError(
            "La racine du fichier ATT&CK doit être un objet JSON (bundle STIX)."
        )

    # Durcissement : le module charge un bundle STIX, pas un objet JSON
    # arbitraire portant simplement une clé "objects". "type" absent,
    # non-string ou différent de "bundle" sont rejetés de façon identique.
    bundle_type = raw_bundle.get("type")
    if bundle_type != "bundle":
        raise AttackKnowledgeError(
            "Le bundle STIX doit avoir 'type' == 'bundle' "
            f"(valeur reçue : {bundle_type!r})."
        )

    raw_objects = raw_bundle.get("objects")
    if not isinstance(raw_objects, list):
        raise AttackKnowledgeError("Le bundle STIX doit contenir une liste 'objects'.")

    techniques_by_id: dict[str, AttackTechniqueRecord] = {}
    for raw_object in raw_objects:
        if not isinstance(raw_object, dict):
            continue
        if raw_object.get("type") != "attack-pattern":
            continue

        record = _parse_attack_pattern(raw_object)
        if record is None:
            continue
        if not include_revoked and record.revoked:
            continue
        if not include_deprecated and record.deprecated:
            continue

        if record.technique_id in techniques_by_id:
            raise DuplicateAttackTechniqueError(
                f"Identifiant ATT&CK dupliqué : '{record.technique_id}'."
            )
        techniques_by_id[record.technique_id] = record

    return AttackKnowledgeBase(
        source_path=file_path,
        techniques_by_id=MappingProxyType(techniques_by_id),
        bundle_type=bundle_type,
        spec_version=_extract_str_or_none(raw_bundle, "spec_version"),
    )


# ---------------------------------------------------------------------------
# Fonctions d'accès
# ---------------------------------------------------------------------------


def get_technique(kb: AttackKnowledgeBase, technique_id: str) -> AttackTechniqueRecord:
    """Réf. architecture : "8. Base de connaissances ATT&CK" — accès direct
    par identifiant. Aucune correspondance approximative, aucune correction
    automatique : un identifiant absent lève UnknownAttackTechniqueError."""
    try:
        return kb.techniques_by_id[technique_id]
    except KeyError as exc:
        raise UnknownAttackTechniqueError(
            f"Technique ATT&CK inconnue : '{technique_id}'."
        ) from exc


def has_technique(kb: AttackKnowledgeBase, technique_id: str) -> bool:
    """Réf. architecture : "8. Base de connaissances ATT&CK" — teste
    l'appartenance d'un identifiant à la KB."""
    return technique_id in kb.techniques_by_id


def list_technique_ids(kb: AttackKnowledgeBase) -> list[str]:
    """Réf. architecture : "8. Base de connaissances ATT&CK" — liste des
    identifiants indexés, dans l'ordre stable d'insertion (ordre du bundle
    source)."""
    return list(kb.techniques_by_id.keys())


def get_tactics(kb: AttackKnowledgeBase, technique_id: str) -> tuple[str, ...]:
    """Réf. architecture : "8. Base de connaissances ATT&CK" — Tactics(T_i)
    telles qu'extraites du bundle (réf. tâche §10)."""
    return get_technique(kb, technique_id).tactics


def get_platforms(kb: AttackKnowledgeBase, technique_id: str) -> tuple[str, ...]:
    """Réf. architecture : "8. Base de connaissances ATT&CK" — plateformes
    associées à la technique."""
    return get_technique(kb, technique_id).platforms


# ---------------------------------------------------------------------------
# Validation des occurrences du graphe contre la KB
# ---------------------------------------------------------------------------


def validate_graph_techniques(graph: AttackGraph, kb: AttackKnowledgeBase) -> None:
    """Réf. architecture : "3.1 Graphe d'attaque" / "8. Base de connaissances
    ATT&CK" — vérifie que le technique_id de chaque occurrence T_{i,h} du
    graphe existe dans la KB ATT&CK chargée (réf. tâche §9).

    Ne vérifie que l'existence de T_i : ne modifie ni NodeAttributes, ni les
    tactiques, ni q, ni les impacts, ni Critical/Accessible ; ne crée aucune
    arête ; n'effectue aucun appel réseau. Si au moins un technique_id est
    absent de la KB, lève UNE UnknownAttackTechniqueError listant tous les
    identifiants inconnus, triés de manière déterministe.
    """
    unknown_ids = sorted(
        {
            node.technique_id
            for node in graph.nodes
            if not has_technique(kb, node.technique_id)
        }
    )
    if unknown_ids:
        raise UnknownAttackTechniqueError(
            "Unknown ATT&CK techniques: " + ", ".join(unknown_ids)
        )
