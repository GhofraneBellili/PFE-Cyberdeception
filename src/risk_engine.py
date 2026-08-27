"""
Réf. architecture : "14. SP3 — Propagation déterministe du risque"
(CLAUDE.md §14, §26 — module `risk_engine.py`).

Chaîne officielle : y -> DE -> Gamma -> P^e -> A -> P -> I -> R (§14.7).

Ce module ne calcule JAMAIS Realisme, P_interaction, P_engagement,
Effet_prog ni DE lui-même (SP2, hors périmètre) : il reçoit `DE` déjà
calculé (frozen, réf. §13) par occurrence — la valeur effective de DE
résultant du couple (mécanisme, emplacement) éventuellement sélectionné
par `y` à cette occurrence (0.0 si aucune déception n'y est déployée,
réf. §14.3 : « au plus un couple par occurrence »).

**Invariant central du projet (réf. tâche « LLM hors du chemin
d'exécution ») : ce module n'importe jamais `src/annotator_llm.py` ni
`src/rag_indexer.py`/`src/rag_retriever.py`.** Il ne lit que des valeurs
déjà figées (q, I, DE) — aucun appel LLM, aucun RAG, à aucun moment de la
propagation.

Notation verrouillée (chapitre 4, section 0 du prompt d'implémentation) :
`Gamma`, `A`, `P`, `I`, `R`, `q`, `DE` — inchangée de CLAUDE.md pour ces
symboles (seuls les concepts SP2 sont renommés en français : Realisme,
P_interaction, P_engagement, Effet_prog).

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

import networkx as nx

from src.graph_builder import get_child_ids, get_parent_ids, identify_entry_nodes, to_networkx
from src.schemas import AttackGraph


class RiskEngineError(Exception):
    """Erreur de propagation du risque SP3."""


# ---------------------------------------------------------------------------
# Formules élémentaires — réf. §14.3 à §14.7
# ---------------------------------------------------------------------------


def compute_gamma(de: float) -> float:
    """Réf. §14.3 « Facteur résiduel de continuation » :
    Gamma_{i,h}(y) = 1 - DE_{i,h} (au plus un couple par occurrence,
    §14.3)."""
    if not 0.0 <= de <= 1.0:
        raise RiskEngineError(f"DE doit être dans [0,1] (valeur reçue : {de}).")
    return 1.0 - de


def compute_transmitted_edge_probability(p_parent: float, gamma_parent: float, pi: float = 1.0) -> float:
    """Réf. §14.4 « Probabilité transmise sur une arête » P^e. `pi=1.0`
    pour un parent non divergent (§14.4, règle gelée : π intervient
    uniquement en divergence) ; sinon la probabilité de branche fournie
    par l'appelant."""
    return p_parent * gamma_parent * pi


def compute_reachability(edge_probabilities: list[float]) -> float:
    """Réf. §14.5 « Convergence » — agrégateur noisy-OR :
    A_{i,h}(y) = 1 - prod(1 - P^e) sur tous les parents. Un nœud
    d'entrée (aucun parent) a A=1 (§5)."""
    if not edge_probabilities:
        return 1.0
    product = 1.0
    for p in edge_probabilities:
        if not 0.0 <= p <= 1.0:
            raise RiskEngineError(f"Probabilité transmise hors bornes [0,1] : {p}.")
        product *= 1.0 - p
    return 1.0 - product


def compute_propagated_success_probability(a: float, q: float) -> float:
    """Réf. §14.6 : P_{i,h}(y) = A_{i,h}(y) * q_{i,h}."""
    if not 0.0 <= q <= 1.0:
        raise RiskEngineError(f"q doit être dans [0,1] (valeur reçue : {q}).")
    return a * q


def compute_aggregated_impact(
    i_c: float, i_i: float, i_a: float, *, w_c: float = 0.6, w_i: float = 0.3, w_a: float = 0.1
) -> float:
    """Réf. §12.2 : I_{i,h} = w_C*I^C + w_I*I^I + w_A*I^A (poids par
    défaut §20.6, jamais imposés silencieusement si l'appelant en fournit
    d'autres explicitement)."""
    if abs((w_c + w_i + w_a) - 1.0) > 1e-9:
        raise RiskEngineError("w_c + w_i + w_a doit valoir 1.")
    return w_c * i_c + w_i * i_i + w_a * i_a


def compute_risk(p: float, i: float) -> float:
    """Réf. §14.7 : R_{i,h}(y) = P_{i,h}(y) * I_{i,h}."""
    return p * i


# ---------------------------------------------------------------------------
# Propagation complète sur le graphe — réf. §14.4/§14.5, pseudo-algorithme SP3
# ---------------------------------------------------------------------------


def _branch_probability(graph: AttackGraph, source_id: str, target_id: str, child_ids: list[str]) -> float:
    """Réf. §14.4 : π uniquement en divergence (out-degree > 1). Si le
    parent n'a qu'un seul enfant, π ne s'applique pas (retourne 1.0). En
    divergence, utilise `branch_probability` si fourni sur les arêtes
    (déjà validé par AttackGraph : soit toutes les arêtes du parent le
    portent et somment à 1, soit aucune), sinon 1/|Children| (§14.4,
    défaut explicitement autorisé)."""
    if len(child_ids) <= 1:
        return 1.0
    edge = next(e for e in graph.edges if e.source_id == source_id and e.target_id == target_id)
    if edge.branch_probability is not None:
        return edge.branch_probability
    return 1.0 / len(child_ids)


def propagate_risk(
    graph: AttackGraph,
    *,
    q_by_occurrence: dict[str, float],
    de_by_occurrence: dict[str, float],
    impact_by_occurrence: dict[str, float],
) -> dict[str, dict]:
    """Réf. §14 (pseudo-algorithme SP3) : propage Gamma -> P^e -> A -> P ->
    R sur l'ensemble du graphe, dans l'ordre topologique.

    `q_by_occurrence`/`impact_by_occurrence` doivent couvrir toutes les
    occurrences du graphe (§25.3 : aucune valeur manquante n'est devinée —
    une occurrence absente lève une erreur explicite). `de_by_occurrence`
    peut être partiel : toute occurrence absente est traitée comme
    DE=0 (aucune déception déployée à cette occurrence).
    """
    nx_graph = to_networkx(graph)
    try:
        topo_order = list(nx.topological_sort(nx_graph))
    except nx.NetworkXUnfeasible as exc:
        raise RiskEngineError(f"Le graphe n'est pas acyclique : {exc}") from exc

    entry_ids = set(identify_entry_nodes(graph))
    results: dict[str, dict] = {}

    for occurrence_id in topo_order:
        if occurrence_id not in q_by_occurrence:
            raise RiskEngineError(f"q manquant pour l'occurrence '{occurrence_id}' — aucune valeur devinée (§25.3).")
        if occurrence_id not in impact_by_occurrence:
            raise RiskEngineError(
                f"I (impact agrégé) manquant pour l'occurrence '{occurrence_id}' — aucune valeur devinée (§25.3)."
            )
        q = q_by_occurrence[occurrence_id]
        impact = impact_by_occurrence[occurrence_id]
        de = de_by_occurrence.get(occurrence_id, 0.0)
        gamma = compute_gamma(de)

        if occurrence_id in entry_ids:
            a = 1.0
        else:
            parent_ids = get_parent_ids(graph, occurrence_id)
            edge_probabilities = []
            for parent_id in parent_ids:
                parent_result = results[parent_id]
                parent_children = get_child_ids(graph, parent_id)
                pi = _branch_probability(graph, parent_id, occurrence_id, parent_children)
                edge_probabilities.append(
                    compute_transmitted_edge_probability(parent_result["P"], parent_result["Gamma"], pi)
                )
            a = compute_reachability(edge_probabilities)

        p = compute_propagated_success_probability(a, q)
        r = compute_risk(p, impact)

        results[occurrence_id] = {"Gamma": gamma, "A": a, "P": p, "I": impact, "R": r, "DE": de, "q": q}

    return results
