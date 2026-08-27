"""
Réf. architecture : "16. Problème global d'optimisation (P)"
(CLAUDE.md §16, §26 — module `optimizer.py`).

(P) : min_y (R_{i1,h1}(y), ..., R_{im,hm}(y))  — minimisation multiobjectif
des risques terminaux (§16), sous :

- **unicité locale** (§16.1) : au plus un couple (d,l) sélectionné par
  occurrence — garantie ici PAR CONSTRUCTION (une `Configuration` associe
  à chaque occurrence 0 ou 1 candidat de son `C_i_h`, jamais plus) ;
- **budget** (§16.2) : somme des `Cost(d;H)` des candidats sélectionnés
  <= `B_total` ;
- **domaine** (§16.3) : `y` binaire, n'existe que pour `(d,l) in C_{i,h}`
  (ce module n'itère jamais que sur les candidats déjà admissibles selon
  `src/admissibility.py`).

Ce module explore **exhaustivement** l'espace des configurations
admissibles, conformément à CLAUDE.md §23 (« validation exhaustive du
solveur sur petite instance ») et à l'interdiction du §24 de toute
« réduction arbitraire de l'espace de décision » ou « Top-K arbitraire »
avant validation du modèle. Il est donc, par conception, réservé aux
instances de taille prototype (garde-fou explicite `max_configurations`,
pas une heuristique de réduction — voir `enumerate_configurations`).

`DE_{i,h,d,l}` (SP2, non encore implémenté) et `Cost(d;H)` (cost_engine)
sont reçus déjà calculés/gelés (§13) — ce module ne les recalcule jamais.

**Invariant central du projet (LLM hors du chemin d'exécution)** : ce
module n'importe jamais `src/annotator_llm.py` ni `src/rag_indexer.py`/
`src/rag_retriever.py` — il ne lit que des valeurs déjà figées.

Le front de Pareto (§16, minimisation multiobjectif) est la sortie de
référence de (P). La sélection d'une unique configuration `y*` par somme
des risques terminaux (`select_by_sum_aggregation`) est une politique
**explicite et illustrative** au sens de §16 (« une règle d'agrégation
peut également être utilisée si elle est explicitement définie et
justifiée ») — ce n'est pas une règle imposée par le chapitre 3.

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from src.graph_builder import identify_terminal_nodes
from src.risk_engine import propagate_risk
from src.schemas import AttackGraph


class OptimizerError(Exception):
    """Erreur de construction ou de résolution du problème global (P)."""


# ---------------------------------------------------------------------------
# Candidats et configurations — réf. §16.1/§16.3
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Candidate:
    """Un couple admissible (d,l) pour une occurrence, avec DE et Cost déjà
    calculés (SP2 gelé, cost_engine) — réf. §16.3 : n'existe que pour
    (d,l) in C_{i,h}."""

    occurrence_id: str
    mechanism_id: str
    location_id: str
    de: float
    cost: float


@dataclass(frozen=True)
class Configuration:
    """Une décision complète y : au plus un candidat par occurrence (§16.1).
    Une occurrence absente de `selections` n'a aucune déception déployée
    (DE=0 pour risk_engine)."""

    selections: dict[str, Candidate]

    @property
    def total_cost(self) -> float:
        return sum(candidate.cost for candidate in self.selections.values())

    @property
    def de_by_occurrence(self) -> dict[str, float]:
        return {occurrence_id: candidate.de for occurrence_id, candidate in self.selections.items()}

    def to_deployment_plan(self) -> list[dict]:
        """Réf. §16 : matérialisation de Y* pour une configuration donnée."""
        return [
            {
                "occurrence_id": candidate.occurrence_id,
                "mechanism_id": candidate.mechanism_id,
                "location_id": candidate.location_id,
                "DE": candidate.de,
                "Cost": candidate.cost,
            }
            for candidate in sorted(self.selections.values(), key=lambda c: c.occurrence_id)
        ]


def build_candidates_from_admissibility(
    admissibility_report: dict,
    *,
    de_by_candidate: dict[tuple[str, str, str], float],
    cost_by_mechanism: dict[str, float],
) -> dict[str, list[Candidate]]:
    """Réf. §16.1/§16.3 : construit, pour chaque occurrence, la liste des
    candidats de `C_{i,h}` (sortie de SP1) enrichis de DE et Cost déjà
    calculés.

    `de_by_candidate` : dict[(occurrence_id, mechanism_id, location_id),
    float] — DE_{i,h,d,l} figé (SP2). `cost_by_mechanism` : dict
    [mechanism_id, float] — Cost(d;H) (cost_engine), indépendant de
    l'emplacement par construction (§15).
    """
    candidates_by_occurrence: dict[str, list[Candidate]] = {}
    for occurrence_id, occurrence_report in admissibility_report["occurrences"].items():
        candidates: list[Candidate] = []
        for entry in occurrence_report["C_i_h"]:
            mechanism_id = entry["mechanism_id"]
            location_id = entry["location_id"]
            key = (occurrence_id, mechanism_id, location_id)
            if key not in de_by_candidate:
                raise OptimizerError(
                    f"DE manquant pour le candidat admissible {key} "
                    "(SP2 non fourni — aucune valeur devinée, §25.3)."
                )
            if mechanism_id not in cost_by_mechanism:
                raise OptimizerError(f"Cost manquant pour le mécanisme '{mechanism_id}'.")
            candidates.append(
                Candidate(
                    occurrence_id=occurrence_id,
                    mechanism_id=mechanism_id,
                    location_id=location_id,
                    de=de_by_candidate[key],
                    cost=cost_by_mechanism[mechanism_id],
                )
            )
        candidates_by_occurrence[occurrence_id] = candidates
    return candidates_by_occurrence


def enumerate_configurations(
    candidates_by_occurrence: dict[str, list[Candidate]],
    *,
    max_configurations: int = 100_000,
) -> list[Configuration]:
    """Réf. §16.1 (unicité) + §23 (validation exhaustive sur petite
    instance). Pour chaque occurrence dotée de candidats, énumère « aucune
    déception » + chaque candidat, puis fait le produit cartésien sur
    toutes les occurrences.

    Garde-fou explicite (`max_configurations`) contre l'explosion
    combinatoire — ce n'est PAS une réduction arbitraire de l'espace de
    décision (§24 l'interdit) : au-delà du seuil, ce module refuse
    d'énumérer plutôt que d'omettre silencieusement des configurations.
    """
    occurrence_ids = [occ_id for occ_id, candidates in candidates_by_occurrence.items() if candidates]
    if not occurrence_ids:
        return [Configuration(selections={})]

    choice_lists: list[list[Candidate | None]] = [
        [None, *candidates_by_occurrence[occ_id]] for occ_id in occurrence_ids
    ]
    total = 1
    for choices in choice_lists:
        total *= len(choices)
    if total > max_configurations:
        raise OptimizerError(
            f"Espace de configurations trop grand ({total} > {max_configurations}). "
            "Ce module explore exhaustivement sans réduction arbitraire (§24) : "
            "il est réservé aux petites instances de validation (§23)."
        )

    configurations = []
    for combo in product(*choice_lists):
        selections = {candidate.occurrence_id: candidate for candidate in combo if candidate is not None}
        configurations.append(Configuration(selections=selections))
    return configurations


def filter_by_budget(configurations: list[Configuration], budget_total: float) -> list[Configuration]:
    """Réf. §16.2 : contrainte budgétaire — somme des Cost(d;H) des
    candidats sélectionnés <= B_total."""
    if budget_total < 0:
        raise OptimizerError(f"Le budget total doit être positif ou nul (valeur reçue : {budget_total}).")
    return [configuration for configuration in configurations if configuration.total_cost <= budget_total]


# ---------------------------------------------------------------------------
# Évaluation SP3 et dominance — réf. §16
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvaluatedConfiguration:
    """Une configuration évaluée : ses risques terminaux (SP3) et son coût."""

    configuration: Configuration
    terminal_risks: dict[str, float]

    @property
    def total_cost(self) -> float:
        return self.configuration.total_cost


def evaluate_configuration(
    graph: AttackGraph,
    configuration: Configuration,
    *,
    q_by_occurrence: dict[str, float],
    impact_by_occurrence: dict[str, float],
    terminal_ids: list[str],
) -> EvaluatedConfiguration:
    """Réf. §16 : évalue une configuration via SP3 (`propagate_risk`) et
    restreint le résultat au vecteur des risques terminaux
    `(R_{i1,h1}, ..., R_{im,hm})`."""
    propagation = propagate_risk(
        graph,
        q_by_occurrence=q_by_occurrence,
        de_by_occurrence=configuration.de_by_occurrence,
        impact_by_occurrence=impact_by_occurrence,
    )
    terminal_risks = {occurrence_id: propagation[occurrence_id]["R"] for occurrence_id in terminal_ids}
    return EvaluatedConfiguration(configuration=configuration, terminal_risks=terminal_risks)


def dominates(risks_a: dict[str, float], risks_b: dict[str, float]) -> bool:
    """Réf. §16 : A domine B (minimisation) ssi A <= B sur tous les objectifs
    et A < B sur au moins un objectif."""
    if risks_a.keys() != risks_b.keys():
        raise OptimizerError("Les vecteurs de risques terminaux comparés doivent porter sur les mêmes occurrences.")
    all_le = all(risks_a[key] <= risks_b[key] for key in risks_a)
    any_lt = any(risks_a[key] < risks_b[key] for key in risks_a)
    return all_le and any_lt


def pareto_front(evaluated_configurations: list[EvaluatedConfiguration]) -> list[EvaluatedConfiguration]:
    """Réf. §16 : ensemble des configurations non dominées (minimisation
    multiobjectif des risques terminaux)."""
    front = []
    for candidate in evaluated_configurations:
        dominated = any(
            dominates(other.terminal_risks, candidate.terminal_risks)
            for other in evaluated_configurations
            if other is not candidate
        )
        if not dominated:
            front.append(candidate)
    return front


def select_by_sum_aggregation(evaluated_configurations: list[EvaluatedConfiguration]) -> EvaluatedConfiguration:
    """Politique de décision EXPLICITE ET ILLUSTRATIVE (§16 : « une règle
    d'agrégation peut également être utilisée si elle est explicitement
    définie et justifiée »). Choisit, parmi le front de Pareto, la
    configuration minimisant la somme des risques terminaux. Ce n'est PAS
    une règle imposée par le chapitre 3 : seuls l'énumération et le front
    de Pareto sont la sortie de référence de (P)."""
    front = pareto_front(evaluated_configurations)
    if not front:
        raise OptimizerError("Aucune configuration faisable : impossible de sélectionner y*.")
    return min(front, key=lambda evaluated: sum(evaluated.terminal_risks.values()))


# ---------------------------------------------------------------------------
# Orchestration complète de (P) — réf. §16, pseudo-algorithme implicite
# ---------------------------------------------------------------------------


def solve(
    graph: AttackGraph,
    admissibility_report: dict,
    *,
    de_by_candidate: dict[tuple[str, str, str], float],
    cost_by_mechanism: dict[str, float],
    budget_total: float,
    q_by_occurrence: dict[str, float],
    impact_by_occurrence: dict[str, float],
    theta_c: float,
    theta_i: float,
    theta_a: float,
    max_configurations: int = 100_000,
) -> dict:
    """Réf. §16 : résolution complète de (P) sur une petite instance —
    C_{i,h} -> configurations (unicité par construction) -> budget -> SP3
    -> risques terminaux -> front de Pareto -> y* (agrégation
    illustrative).
    """
    terminal_ids = identify_terminal_nodes(graph, theta_c, theta_i, theta_a)
    if not terminal_ids:
        raise OptimizerError("Aucune occurrence Terminal identifiée : (P) n'a pas d'objectif à minimiser.")

    candidates_by_occurrence = build_candidates_from_admissibility(
        admissibility_report, de_by_candidate=de_by_candidate, cost_by_mechanism=cost_by_mechanism
    )
    all_configurations = enumerate_configurations(candidates_by_occurrence, max_configurations=max_configurations)
    feasible_configurations = filter_by_budget(all_configurations, budget_total)
    if not feasible_configurations:
        raise OptimizerError(f"Aucune configuration ne respecte le budget B_total={budget_total}.")

    evaluated = [
        evaluate_configuration(
            graph,
            configuration,
            q_by_occurrence=q_by_occurrence,
            impact_by_occurrence=impact_by_occurrence,
            terminal_ids=terminal_ids,
        )
        for configuration in feasible_configurations
    ]
    front = pareto_front(evaluated)
    selected = select_by_sum_aggregation(evaluated)

    return {
        "terminal_ids": terminal_ids,
        "configurations_enumerated": len(all_configurations),
        "configurations_feasible": len(feasible_configurations),
        "pareto_front": front,
        "selected": selected,
    }
