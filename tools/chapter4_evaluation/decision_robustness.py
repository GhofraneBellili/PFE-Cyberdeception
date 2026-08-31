"""
Réf. tâche « campagne d'évaluation réelle RAG/LLM/système » §5 : robustesse
de la décision face au bruit d'annotation. Perturbe une table DE gelée
RÉELLE par un bruit borné (±epsilon), rejoue SP3+optimiseur (`solve`) pour
chaque tirage, et mesure la stabilité du plan sélectionné et du front de
Pareto.

**Invariant central de ce module (réf. tâche §5) : AUCUN appel LLM.** Ce
fichier n'importe volontairement RIEN de `src/annotator_llm.py` ni de
`src/llm_provider.py` — seule la table DE déjà gelée (fournie en entrée)
est utilisée ; elle n'est jamais recalculée ici. `tests/test_chapter4_evaluation_decision_robustness.py`
vérifie explicitement l'absence de cet import (réf. tâche §8).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from src.optimizer import OptimizerError, solve
from src.schemas import AttackGraph

DEFAULT_EPSILONS: tuple[float, ...] = (0.02, 0.05, 0.10)
DEFAULT_N_DRAWS = 30


class DecisionRobustnessError(Exception):
    """Erreur d'analyse de robustesse de la décision (§5)."""


def _clip_unit(value: float) -> float:
    return min(1.0, max(0.0, value))


def perturb_de(de_by_candidate: dict[tuple[str, str, str], float], *, epsilon: float, rng: random.Random) -> dict[tuple[str, str, str], float]:
    """Réf. §5 : bruit uniforme borné [-epsilon, +epsilon] appliqué à
    chaque DE gelé, tronqué à [0,1] (§25.2 : toute quantité probabiliste
    reste bornée)."""
    return {key: _clip_unit(value + rng.uniform(-epsilon, epsilon)) for key, value in de_by_candidate.items()}


def _plan_signature(deployment_plan: list[dict]) -> tuple:
    return tuple(sorted((row["occurrence_id"], row["mechanism_id"], row["location_id"]) for row in deployment_plan))


def _pareto_signature(pareto_front) -> frozenset:
    return frozenset(
        (tuple(sorted(ec.configuration.selections.keys())), round(ec.total_cost, 6))
        for ec in pareto_front
    )


def _solve_once(graph, admissibility_report, de_by_candidate, cost_by_mechanism, budget_total, q_by_occurrence, impact_by_occurrence, theta_c, theta_i, theta_a):
    return solve(
        graph,
        admissibility_report,
        de_by_candidate=de_by_candidate,
        cost_by_mechanism=cost_by_mechanism,
        budget_total=budget_total,
        q_by_occurrence=q_by_occurrence,
        impact_by_occurrence=impact_by_occurrence,
        theta_c=theta_c,
        theta_i=theta_i,
        theta_a=theta_a,
    )


@dataclass(frozen=True)
class RobustnessLevelResult:
    epsilon: float
    n_draws: int
    identical_plan_count: int
    identical_pareto_count: int
    failed_draw_count: int

    @property
    def identical_plan_rate(self) -> float:
        return self.identical_plan_count / self.n_draws if self.n_draws else 0.0

    @property
    def identical_pareto_rate(self) -> float:
        return self.identical_pareto_count / self.n_draws if self.n_draws else 0.0


def run_decision_robustness(
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
    epsilons: tuple[float, ...] = DEFAULT_EPSILONS,
    n_draws: int = DEFAULT_N_DRAWS,
    seed: int = 20260831,
) -> dict:
    """Réf. §5 : baseline (DE gelé non perturbé) puis, pour chaque
    `epsilon`, `n_draws` tirages perturbés -- rejoue `solve()` à chaque
    tirage (donc SP3 + optimiseur, jamais l'annotation) et mesure la part
    de tirages où le plan sélectionné / le front de Pareto restent
    identiques à la baseline."""
    baseline = _solve_once(
        graph, admissibility_report, de_by_candidate, cost_by_mechanism, budget_total,
        q_by_occurrence, impact_by_occurrence, theta_c, theta_i, theta_a,
    )
    baseline_plan_sig = _plan_signature(baseline["selected"].configuration.to_deployment_plan())
    baseline_pareto_sig = _pareto_signature(baseline["pareto_front"])

    rng = random.Random(seed)
    levels = []
    for epsilon in epsilons:
        identical_plan = 0
        identical_pareto = 0
        failed = 0
        for _ in range(n_draws):
            perturbed_de = perturb_de(de_by_candidate, epsilon=epsilon, rng=rng)
            try:
                result = _solve_once(
                    graph, admissibility_report, perturbed_de, cost_by_mechanism, budget_total,
                    q_by_occurrence, impact_by_occurrence, theta_c, theta_i, theta_a,
                )
            except OptimizerError:
                failed += 1
                continue
            if _plan_signature(result["selected"].configuration.to_deployment_plan()) == baseline_plan_sig:
                identical_plan += 1
            if _pareto_signature(result["pareto_front"]) == baseline_pareto_sig:
                identical_pareto += 1
        levels.append(
            RobustnessLevelResult(
                epsilon=epsilon, n_draws=n_draws,
                identical_plan_count=identical_plan, identical_pareto_count=identical_pareto, failed_draw_count=failed,
            )
        )

    return {
        "epsilons_tested": list(epsilons),
        "n_draws_per_level": n_draws,
        "seed": seed,
        "baseline_plan": baseline["selected"].configuration.to_deployment_plan(),
        "baseline_pareto_front_size": len(baseline["pareto_front"]),
        "levels": [
            {
                "epsilon": level.epsilon,
                "n_draws": level.n_draws,
                "identical_plan_count": level.identical_plan_count,
                "identical_plan_rate": level.identical_plan_rate,
                "identical_pareto_count": level.identical_pareto_count,
                "identical_pareto_rate": level.identical_pareto_rate,
                "failed_draw_count": level.failed_draw_count,
            }
            for level in levels
        ],
    }
