"""
Réf. architecture : "11.3 Sous-métriques annotées par le LLM" (CLAUDE.md
§11.3) — réf. tâche « renforcer l'architecture et l'implémentation du
module RAG utilisé par SP2 », §6/§7 « Construction de requêtes
spécifiques par famille de sous-métriques ».

Construit, de façon entièrement DÉTERMINISTE (jamais par un LLM, §6), les
trois requêtes documentaires attendues par le retrieval contextuel de
SP2, une par famille de sous-métriques (§11.3) :

- **Q_realism** : plausibilité technique du placement (`R_tech`), cohérence
  avec l'actif/l'emplacement (`R_context`), perception plausible par
  l'attaquant (`R_perception`), comportement attendu du mécanisme
  (`R_behavior`).
- **Q_interaction** : objet avec lequel l'attaquant peut interagir
  (`A_object`), action requise (`A_action`), exposition dans le chemin/
  comportement de `T_i` (`A_source`).
- **Q_effect** : effet défensif attendu sur la progression — arrêt,
  redirection, confinement, retardement (`S_stop`, `S_redirect`,
  `S_contain`, `S_delay`).

Ce module ne récupère aucun document et ne calcule aucune sous-métrique :
il ne fait que construire le texte des trois requêtes à partir des champs
déjà présents dans un `RagCandidateContext` (`src/schemas.py`). Aucun
`technique_id`/`mechanism_id`/`asset_id`/`location_id` n'est codé en dur
ici (réf. tâche §7) — le comportement est entièrement déterminé par le
contexte passé en paramètre.

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

from src.schemas import RagCandidateContext


def _join(*parts: str | None) -> str:
    """Assemble des fragments de requête non vides, séparés par un espace
    — jamais de fragment vide ni de valeur inventée en son absence."""
    return " ".join(part for part in parts if part)


def _list_or_none(values: list[str]) -> str | None:
    return ", ".join(values) if values else None


def build_realism_query(context: RagCandidateContext) -> str:
    """Réf. §6 : Q_realism — plausibilité technique, cohérence
    actif/emplacement, perception attendue de l'attaquant, comportement
    attendu du mécanisme."""
    return _join(
        "Technical plausibility and realism of deploying deception mechanism",
        context.mechanism_name,
        f"({context.mechanism_description})" if context.mechanism_description else None,
        "on asset type",
        context.asset_type,
        "at location type",
        context.location_type,
        "in the context of attack technique",
        context.technique_id,
        f"({context.technique_name})" if context.technique_name else None,
        "expected attacker perception and behavior of the deception mechanism, interaction mechanism:",
        context.interaction_mechanism,
        "relevant services:",
        _list_or_none(context.si_context.relevant_services),
        "relevant artifacts:",
        _list_or_none(context.si_context.relevant_artifacts),
    )


def build_interaction_query(context: RagCandidateContext) -> str:
    """Réf. §6 : Q_interaction — objet interactible par l'attaquant, action
    requise, exposition dans le comportement/chemin de `T_i`."""
    return _join(
        "Object an attacker could interact with, required attacker action, and exposure of",
        context.mechanism_name,
        "target artifacts:",
        _list_or_none(context.target_artifacts),
        "in the behavior and path of attack technique",
        context.technique_id,
        f"({context.technique_name})" if context.technique_name else None,
        "tactics:",
        _list_or_none(context.tactics),
        "deception mechanism interaction mechanism:",
        context.interaction_mechanism,
        "on location type",
        context.location_type,
        "of asset type",
        context.asset_type,
    )


def build_effect_query(context: RagCandidateContext) -> str:
    """Réf. §6 : Q_effect — effet défensif attendu sur la progression
    (stop/redirect/contain/delay), contexte de graphe en aval quand
    pertinent."""
    return _join(
        "Expected defensive effect (stop, redirect, contain, or delay attacker progression) of deception mechanism",
        context.mechanism_name,
        "against attack technique",
        context.technique_id,
        f"({context.technique_name})" if context.technique_name else None,
        "interaction mechanism:",
        context.interaction_mechanism,
        "downstream attack techniques potentially prevented:",
        _list_or_none(context.graph_context.direct_child_technique_ids),
        "terminal objective downstream:" if context.graph_context.is_terminal else None,
        "yes" if context.graph_context.is_terminal else None,
    )


def build_rag_queries(context: RagCandidateContext) -> dict[str, str]:
    """Réf. §6/§7 : point d'entrée unique — construit les trois requêtes
    déterministes `{"realism": ..., "interaction": ..., "effect": ...}`
    pour un candidat donné."""
    return {
        "realism": build_realism_query(context),
        "interaction": build_interaction_query(context),
        "effect": build_effect_query(context),
    }
