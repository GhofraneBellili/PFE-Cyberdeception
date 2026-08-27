"""
Réf. architecture : CLAUDE.md §7/§9/§10 — réf. tâche « separate knowledge
and organization capabilities ».

Chargement et validation du catalogue OPÉRATIONNEL d'une organisation
(`OrganizationDeceptionCatalog`/`OrganizationDeceptionCapability`,
`src/schemas.py`) — distinct du catalogue de connaissances général
(`src/knowledge_deception.py`).

Rôle strict de ce module :
- charger un fichier JSON représentant le profil opérationnel d'UNE
  organisation (jamais une vérité extraite de D3FEND/Engage/littérature) ;
- vérifier qu'aucun `mechanism_id` référencé n'est absent du catalogue de
  connaissances (invariant explicite, réf. tâche §4) ;
- réduire ce catalogue aux formes attendues par SP1 (`D_org`, table
  indexée par `mechanism_id`).

Ce module ne fait ni SP1, ni RAG, ni appel LLM, ni calcul de risque, ni
optimisation.

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from src.knowledge_deception import DeceptionKnowledgeBase
from src.schemas import OrganizationDeceptionCapability, OrganizationDeceptionCatalog


class OrganizationCatalogError(Exception):
    """Erreur de chargement ou de validation du catalogue organisationnel."""


def load_organization_catalog(path: str | Path) -> OrganizationDeceptionCatalog:
    """Réf. tâche §3 : charge le catalogue opérationnel d'une organisation
    (une ENTRÉE fournie par l'organisation, pas une vérité documentaire).
    Aucune valeur manquante n'est complétée silencieusement (§25.3) : un
    JSON syntaxiquement invalide lève `json.JSONDecodeError`, un contenu
    structurellement invalide lève une erreur de validation Pydantic."""
    file_path = Path(path)
    raw = json.loads(file_path.read_bytes().decode("utf-8"))
    return OrganizationDeceptionCatalog.model_validate(raw)


def validate_against_knowledge_catalog(
    org_catalog: OrganizationDeceptionCatalog, knowledge_kb: DeceptionKnowledgeBase
) -> None:
    """Réf. tâche §4 : « Le catalogue opérationnel ne doit jamais contenir
    un mechanism_id qui n'existe pas dans le catalogue général » — invariant
    explicite, jamais silencieusement ignoré. Lève `OrganizationCatalogError`
    listant tous les identifiants orphelins (dédupliqués, triés) s'il y en a
    au moins un."""
    orphan_ids = sorted(
        {
            capability.mechanism_id
            for capability in org_catalog.capabilities
            if capability.mechanism_id not in knowledge_kb.mechanisms_by_id
        }
    )
    if orphan_ids:
        raise OrganizationCatalogError(
            "Le catalogue organisationnel référence des mechanism_id absents du catalogue "
            f"de connaissances : {', '.join(orphan_ids)}."
        )


def capabilities_by_id(
    org_catalog: OrganizationDeceptionCatalog,
) -> Mapping[str, OrganizationDeceptionCapability]:
    """Réduit le catalogue organisationnel à une table indexée par
    `mechanism_id` (lecture seule) — forme attendue par
    `src/admissibility.py`. L'unicité des `mechanism_id` est déjà garantie
    à la construction de `OrganizationDeceptionCatalog` (validateur Pydantic)."""
    return MappingProxyType({capability.mechanism_id: capability for capability in org_catalog.capabilities})


def enabled_mechanism_ids(org_catalog: OrganizationDeceptionCatalog) -> frozenset[str]:
    """Réf. tâche §5 : `D_org` = ensemble des mechanism_id activés
    (`enabled=True`) par l'organisation."""
    return frozenset(capability.mechanism_id for capability in org_catalog.capabilities if capability.enabled)
