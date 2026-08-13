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
