"""
Réf. architecture : "11.2 Entrées du LLM" (CLAUDE.md §11.2) — réf. tâche
« renforcer l'architecture et l'implémentation du module RAG utilisé par
SP2 », §5 « Représentation du contexte candidat pour le RAG ».

Construit un `RagCandidateContext` (`src/schemas.py`) à partir d'un
candidat admissible `(T_{i,h}, d, l)` déjà produit par SP1
(`src/admissibility.py`), de l'instance système courante et,
optionnellement, de la base de connaissances ATT&CK RUNTIME (pour le nom
lisible de la technique — jamais inventé si absent).

**Réf. tâche « dernière passe de finition technique du chapitre 4 »,
§6-§9** : `attack_kb` est un `AttackRuntimeKnowledge`
(`src/attack_runtime_knowledge.py`), chargé depuis le STAGING RAG ATT&CK
déjà versionné — JAMAIS depuis le bundle STIX brut
`enterprise-attack.json` (non versionné, réservé à la reconstruction
OFFLINE de la base de connaissances). Ce module ne dépend donc plus
d'aucun fichier brut au runtime.

Ce module ne fait aucun RAG, aucun appel LLM, aucun calcul de risque ou de
coût : il assemble uniquement les champs déjà disponibles AVANT toute
récupération documentaire ou décision d'optimisation (§5, §11.2).

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

from src.attack_runtime_knowledge import AttackRuntimeKnowledge, has_technique
from src.graph_builder import get_child_ids, get_parent_ids, is_entry_node, is_terminal_node
from src.schemas import (
    Asset,
    DeceptionMechanism,
    Location,
    RagCandidateContext,
    RagGraphContext,
    SIPlacementContext,
    SystemInstance,
    TechniqueOccurrence,
)


class RagCandidateContextError(Exception):
    """Erreur de construction du contexte candidat RAG."""


def _asset_by_id(instance: SystemInstance) -> dict[str, Asset]:
    return {asset.asset_id: asset for asset in instance.si_inventory.assets}


def _as_str_list(value: object) -> list[str]:
    """Réf. §25.3 : une propriété SI absente ou mal typée ne produit
    jamais une liste inventée — seulement une liste vide."""
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def build_rag_candidate_context(
    *,
    occurrence: TechniqueOccurrence,
    mechanism: DeceptionMechanism,
    location: Location,
    instance: SystemInstance,
    theta_c: float,
    theta_i: float,
    theta_a: float,
    attack_kb: AttackRuntimeKnowledge | None = None,
) -> RagCandidateContext:
    """Réf. tâche §5 : assemble le contexte compact d'un candidat
    admissible, prêt pour `src/rag_query_builder.py::build_rag_queries`.

    `theta_c`/`theta_i`/`theta_a` : mêmes seuils que
    `src/admissibility.py::build_admissibility_report` (Terminal, §6) —
    fournis explicitement, jamais une valeur par défaut inventée.
    `attack_kb` est optionnel (`AttackRuntimeKnowledge`, chargé depuis le
    staging RAG ATT&CK déjà versionné — réf. tâche « dernière passe de
    finition technique » §6-§9) : si fourni, `technique_name` est
    renseigné depuis ce staging ; sinon, ou si la technique n'y figure
    pas, il reste `None` (jamais un nom de technique inventé, §25.3/§10).
    """
    assets_by_id = _asset_by_id(instance)
    asset = assets_by_id.get(occurrence.asset_id)
    if asset is None:
        raise RagCandidateContextError(
            f"L'actif '{occurrence.asset_id}' de l'occurrence "
            f"'{occurrence.occurrence_id}' est absent de l'inventaire SI."
        )

    technique_name = None
    if attack_kb is not None and has_technique(attack_kb, occurrence.technique_id):
        technique_name = attack_kb.techniques_by_id[occurrence.technique_id].name

    nodes_by_id = {node.occurrence_id: node for node in instance.graph.nodes}
    parent_ids = get_parent_ids(instance.graph, occurrence.occurrence_id)
    child_ids = get_child_ids(instance.graph, occurrence.occurrence_id)
    neighbor_ids = parent_ids + child_ids

    direct_parent_technique_ids = sorted({nodes_by_id[pid].technique_id for pid in parent_ids if pid in nodes_by_id})
    direct_child_technique_ids = sorted({nodes_by_id[cid].technique_id for cid in child_ids if cid in nodes_by_id})
    neighboring_tactics = sorted(
        {tactic for nid in neighbor_ids if nid in nodes_by_id for tactic in nodes_by_id[nid].attributes.tactics}
    )

    return RagCandidateContext(
        occurrence_id=occurrence.occurrence_id,
        technique_id=occurrence.technique_id,
        technique_name=technique_name,
        tactics=list(occurrence.attributes.tactics),
        asset_id=occurrence.asset_id,
        asset_type=asset.asset_type,
        mechanism_id=mechanism.id,
        mechanism_name=mechanism.name,
        mechanism_description=mechanism.description,
        target_artifacts=list(mechanism.target_artifacts),
        interaction_mechanism=mechanism.interaction_mechanism,
        location_id=location.location_id,
        location_type=location.location_type,
        si_context=SIPlacementContext(
            relevant_services=_as_str_list(asset.properties.get("services")),
            relevant_artifacts=_as_str_list(asset.properties.get("artifacts")),
        ),
        graph_context=RagGraphContext(
            direct_parent_technique_ids=direct_parent_technique_ids,
            direct_child_technique_ids=direct_child_technique_ids,
            is_entry=is_entry_node(occurrence),
            is_terminal=is_terminal_node(occurrence, theta_c, theta_i, theta_a),
            neighboring_tactics=neighboring_tactics,
        ),
    )
