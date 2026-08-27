"""
Réf. architecture : "7. Catalogue global de cyberdéception" / "9. Base de
connaissances cyberdéception" — contrat technique du PFE Cyberdéception
(CLAUDE.md).

Moteur générique du CATALOGUE NORMALISÉ PFE de cyberdéception : chargement,
validation stricte, indexation déterministe par deception_id, et accès en
lecture pour les futurs modules SP1/SP2.

Ce module charge le catalogue déjà normalisé au format interne PFE (§3 de
cette étape) — il ne parse PAS l'ontologie brute D3FEND, MITRE Engage, des
PDF ou du HTML. Cette extraction/normalisation appartient à une phase future
distincte (voir data/deception/README.md). D3FEND et Engage ne sont
mentionnés ici qu'à titre de sources futures prévues par l'architecture,
jamais codés en dur.

Ce module ne fait ni SP1, ni mapping ATT&CK ↔ déception, ni RAG, ni appel
LLM, ni calcul de risque, ni optimisation : le catalogue D qu'il représente
est fermé, et aucun mécanisme absent du fichier source n'est jamais inventé.

Réutilise strictement les modèles Pydantic existants de src/schemas.py
(DeceptionMechanism, DeceptionEvidence, DeceptionAdmissibilityProfile,
DeceptionResourceRequirements) sans les redéfinir ni les modifier.

Convention : identifiants de code en anglais, commentaires et docstrings en
français (§25.1).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from src.schemas import DeceptionAdmissibilityProfile, DeceptionEvidence, DeceptionMechanism

# ---------------------------------------------------------------------------
# Erreurs
# ---------------------------------------------------------------------------


class DeceptionKnowledgeError(Exception):
    """Erreur de base de la base de connaissances cyberdéception (catalogue
    JSON structurellement invalide, ex. racine non-objet, catalog_version
    absente/vide, mechanisms absent, ou mécanisme validé sans preuve)."""


class UnknownDeceptionMechanismError(DeceptionKnowledgeError):
    """Levée quand un deception_id demandé n'existe pas dans le catalogue
    fermé D chargé (accès direct ou validation d'une liste d'identifiants)."""


class DuplicateDeceptionMechanismError(DeceptionKnowledgeError):
    """Levée quand deux mécanismes du catalogue possèdent le même id :
    mechanisms_by_id doit rester non ambigu (réf. tâche §7)."""


# ---------------------------------------------------------------------------
# Base de connaissances
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeceptionKnowledgeBase:
    """Réf. architecture : "7. Catalogue global de cyberdéception" — index
    déterministe du catalogue fermé D chargé depuis un fichier JSON
    normalisé.

    mechanisms_by_id est une Mapping en lecture seule (MappingProxyType) :
    aucune mutation externe n'est possible après chargement. L'ordre
    d'itération correspond à l'ordre d'apparition dans le fichier source
    (stable et déterministe, aucun tri arbitraire).

    source_sha256 est le SHA-256 des octets exacts du fichier chargé : il
    permet d'identifier précisément la version du catalogue réellement
    utilisée (provenance, reproductibilité), indépendamment de
    catalog_version qui est une métadonnée déclarée par le fichier
    lui-même.
    """

    source_path: Path
    catalog_version: str
    mechanisms_by_id: Mapping[str, DeceptionMechanism]
    source_sha256: str


# ---------------------------------------------------------------------------
# Chargement du catalogue
# ---------------------------------------------------------------------------


def load_deception_catalog(path: str | Path) -> DeceptionKnowledgeBase:
    """Réf. architecture : "9. Base de connaissances cyberdéception" —
    charge le catalogue normalisé PFE et construit une
    DeceptionKnowledgeBase.

    Format canonique attendu (§3 de cette étape — format interne PFE, pas
    le format natif de D3FEND/Engage) :

        {"catalog_version": "...", "mechanisms": [{...DeceptionMechanism...}]}

    Comportement :
    - le SHA-256 est calculé sur les octets bruts du fichier avant tout
      décodage/parsing ;
    - un JSON syntaxiquement invalide lève json.JSONDecodeError ;
    - une racine non-objet, catalog_version absente/non-str/vide (après
      strip), ou mechanisms absent/non-liste, lève DeceptionKnowledgeError —
      catalog_version n'est jamais complétée par une valeur par défaut
      (réf. §25.3) ;
    - chaque élément de mechanisms est validé via
      DeceptionMechanism.model_validate (aucune revalidation manuelle) ;
      une erreur de validation Pydantic remonte telle quelle ;
    - un mécanisme validé sans aucune DeceptionEvidence lève
      DeceptionKnowledgeError (règle plus stricte que le schéma Pydantic
      seul, propre à la KB validée) ;
    - un id de mécanisme dupliqué lève DuplicateDeceptionMechanismError ;
    - aucune normalisation silencieuse n'est appliquée (pas de trim, pas de
      changement de casse, pas de fusion de synonymes, pas de
      déduplication de listes) : un catalogue normalisé invalide est
      rejeté, jamais corrigé automatiquement.
    """
    file_path = Path(path)
    raw_bytes = file_path.read_bytes()
    source_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    raw_catalog = json.loads(raw_bytes.decode("utf-8"))

    if not isinstance(raw_catalog, dict):
        raise DeceptionKnowledgeError(
            "La racine du catalogue de déception doit être un objet JSON."
        )

    catalog_version = raw_catalog.get("catalog_version")
    if not isinstance(catalog_version, str) or not catalog_version.strip():
        raise DeceptionKnowledgeError(
            "'catalog_version' est obligatoire et doit être une chaîne non vide."
        )

    raw_mechanisms = raw_catalog.get("mechanisms")
    if not isinstance(raw_mechanisms, list):
        raise DeceptionKnowledgeError("'mechanisms' est obligatoire et doit être une liste.")

    mechanisms_by_id: dict[str, DeceptionMechanism] = {}
    for raw_mechanism in raw_mechanisms:
        mechanism = DeceptionMechanism.model_validate(raw_mechanism)

        if not mechanism.evidence:
            raise DeceptionKnowledgeError(
                f"Le mécanisme '{mechanism.id}' ne possède aucune preuve "
                "documentaire (evidence) : une fiche validée doit en "
                "contenir au moins une."
            )

        if mechanism.id in mechanisms_by_id:
            raise DuplicateDeceptionMechanismError(
                f"Identifiant de déception dupliqué : '{mechanism.id}'."
            )
        mechanisms_by_id[mechanism.id] = mechanism

    return DeceptionKnowledgeBase(
        source_path=file_path,
        catalog_version=catalog_version,
        mechanisms_by_id=MappingProxyType(mechanisms_by_id),
        source_sha256=source_sha256,
    )


# ---------------------------------------------------------------------------
# Fonctions d'accès
# ---------------------------------------------------------------------------


def get_deception(kb: DeceptionKnowledgeBase, deception_id: str) -> DeceptionMechanism:
    """Réf. architecture : "7. Catalogue global de cyberdéception" — accès
    direct par identifiant. Aucune correspondance approximative, aucune
    correction automatique : un identifiant absent lève
    UnknownDeceptionMechanismError."""
    try:
        return kb.mechanisms_by_id[deception_id]
    except KeyError as exc:
        raise UnknownDeceptionMechanismError(
            f"Mécanisme de déception inconnu : '{deception_id}'."
        ) from exc


def has_deception(kb: DeceptionKnowledgeBase, deception_id: str) -> bool:
    """Réf. architecture : "7. Catalogue global de cyberdéception" — teste
    l'appartenance d'un identifiant au catalogue fermé chargé."""
    return deception_id in kb.mechanisms_by_id


def list_deception_ids(kb: DeceptionKnowledgeBase) -> list[str]:
    """Réf. architecture : "7. Catalogue global de cyberdéception" — liste
    des identifiants indexés, dans l'ordre stable d'insertion (ordre du
    fichier source)."""
    return list(kb.mechanisms_by_id.keys())


def get_evidence(kb: DeceptionKnowledgeBase, deception_id: str) -> tuple[DeceptionEvidence, ...]:
    """Réf. architecture : "9. Base de connaissances cyberdéception" —
    preuves documentaires du mécanisme, telles que chargées (aucune
    modification, aucun résumé, aucune vérification en ligne)."""
    return tuple(get_deception(kb, deception_id).evidence)


def get_admissibility_profile(
    kb: DeceptionKnowledgeBase, deception_id: str
) -> DeceptionAdmissibilityProfile:
    """Réf. architecture : "10.4 Étape 3 — Emplacements admissibles" —
    profil d'admissibilité du mécanisme tel que chargé et conservé, sans
    aucune interprétation SP1 (les listes, y compris vides, ne sont ni
    complétées ni interprétées ici)."""
    return get_deception(kb, deception_id).admissibility_profile


# ---------------------------------------------------------------------------
# Fermeture du catalogue
# ---------------------------------------------------------------------------


def validate_deception_ids(deception_ids: Iterable[str], kb: DeceptionKnowledgeBase) -> None:
    """Réf. architecture : "7. Catalogue global de cyberdéception" —
    vérifie que chaque identifiant appartient au catalogue fermé D chargé.
    Ne fait aucun mapping ATT&CK : sert
    uniquement à faire respecter la fermeture de D.

    Si au moins un identifiant est inconnu, lève UNE
    UnknownDeceptionMechanismError listant tous les identifiants inconnus
    (dédupliqués, triés de manière déterministe).
    """
    unknown_ids = sorted(
        {deception_id for deception_id in deception_ids if not has_deception(kb, deception_id)}
    )
    if unknown_ids:
        raise UnknownDeceptionMechanismError(
            "Unknown deception mechanisms: " + ", ".join(unknown_ids)
        )


# ---------------------------------------------------------------------------
# Mapping M_{i,d} — réf. "10.2 Étape 1 — Mapping attaque ↔ déception"
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AttackDeceptionMapping:
    """Réf. architecture : "10.2 Étape 1" — M_{i,d} déjà matérialisé et
    versionné (`tools/deception_kb/mapping_builder.py`,
    `data/deception/attack_deception_mapping.json`), chargé tel quel.

    `relations` conserve chaque relation source (attack_id, mechanism_id,
    evidence, origin) sans réinterprétation : la réduction vers la forme
    `{technique_id: [mechanism_id, ...]}` attendue par
    `src.admissibility.build_admissibility_report` est une opération
    séparée (`to_sp1_mapping`), pour ne jamais perdre la provenance en
    mémoire.
    """

    source_path: Path
    mapping_version: str
    relations: tuple[Mapping[str, Any], ...]
    source_sha256: str


def load_attack_deception_mapping(path: str | Path) -> AttackDeceptionMapping:
    """Réf. architecture : "10.2 Étape 1" — charge M_{i,d} déjà
    matérialisé (§9.1). Validation structurelle minimale : chaque
    relation doit porter un `attack_id` et un `mechanism_id` non vides.
    La provenance (`evidence`, `origin`) est conservée telle quelle, sans
    normalisation ni interprétation supplémentaire.

    Aucune valeur manquante n'est complétée automatiquement (§25.3) : un
    JSON syntaxiquement invalide lève `json.JSONDecodeError`, un contenu
    structurellement invalide lève `DeceptionKnowledgeError`.
    """
    file_path = Path(path)
    raw_bytes = file_path.read_bytes()
    source_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    raw_mapping = json.loads(raw_bytes.decode("utf-8"))

    if not isinstance(raw_mapping, dict):
        raise DeceptionKnowledgeError("La racine du mapping M_{i,d} doit être un objet JSON.")

    mapping_version = raw_mapping.get("mapping_version")
    if not isinstance(mapping_version, str) or not mapping_version.strip():
        raise DeceptionKnowledgeError(
            "'mapping_version' est obligatoire et doit être une chaîne non vide."
        )

    raw_relations = raw_mapping.get("relations")
    if not isinstance(raw_relations, list):
        raise DeceptionKnowledgeError("'relations' est obligatoire et doit être une liste.")

    relations: list[Mapping[str, Any]] = []
    for relation in raw_relations:
        if not isinstance(relation, dict):
            raise DeceptionKnowledgeError("Chaque relation de M_{i,d} doit être un objet JSON.")
        attack_id = relation.get("attack_id")
        mechanism_id = relation.get("mechanism_id")
        if not isinstance(attack_id, str) or not attack_id.strip():
            raise DeceptionKnowledgeError("Chaque relation de M_{i,d} doit porter un 'attack_id' non vide.")
        if not isinstance(mechanism_id, str) or not mechanism_id.strip():
            raise DeceptionKnowledgeError("Chaque relation de M_{i,d} doit porter un 'mechanism_id' non vide.")
        relations.append(MappingProxyType(dict(relation)))

    return AttackDeceptionMapping(
        source_path=file_path,
        mapping_version=mapping_version,
        relations=tuple(relations),
        source_sha256=source_sha256,
    )


def to_sp1_mapping(
    mapping: AttackDeceptionMapping, kb: DeceptionKnowledgeBase | None = None
) -> dict[str, list[str]]:
    """Réf. architecture : "10.2 Étape 1" — réduit M_{i,d} à la forme
    `{technique_id: [mechanism_id, ...]}` attendue par
    `src.admissibility.build_admissibility_report`.

    Si `kb` est fourni, vérifie d'abord que chaque `mechanism_id`
    référence bien un mécanisme du catalogue fermé chargé (cohérence
    mapping -> catalogue, réf. tâche §4/§5) — lève
    `UnknownDeceptionMechanismError` sinon, avant toute réduction.
    """
    if kb is not None:
        validate_deception_ids((relation["mechanism_id"] for relation in mapping.relations), kb)

    grouped: dict[str, set[str]] = {}
    for relation in mapping.relations:
        grouped.setdefault(relation["attack_id"], set()).add(relation["mechanism_id"])
    return {attack_id: sorted(mechanism_ids) for attack_id, mechanism_ids in grouped.items()}
