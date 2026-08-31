"""
Réf. tâche « campagne d'évaluation réelle RAG/LLM/système » §5/§8 :
- invariant central §5 : AUCUN appel LLM pendant l'analyse de robustesse
  (vérifié statiquement : le module n'importe rien de `src.annotator_llm`/
  `src.llm_provider`) ;
- correction de `perturb_de` (bornes [0,1], epsilon respecté) ;
- correction de `run_decision_robustness` sur un cas jouet connu (2
  candidats admissibles, réutilise le patron de `tests/test_optimizer.py`).
"""

import ast
import random
from pathlib import Path

import pytest

from src.schemas import AttackGraph, AttackGraphEdge, NodeAttributes, TechniqueOccurrence
from tools.chapter4_evaluation.decision_robustness import perturb_de, run_decision_robustness

MODULE_PATH = Path("tools/chapter4_evaluation/decision_robustness.py")


class TestNoLlmImport:
    def test_module_source_never_imports_llm_modules(self):
        """Réf. §5 : garantie STATIQUE, pas seulement comportementale --
        aucun `import`/`from ... import` du module ne référence
        `src.annotator_llm` ni `src.llm_provider`."""
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
        forbidden = {m for m in imported_modules if "annotator_llm" in m or "llm_provider" in m}
        assert forbidden == set()


class TestPerturbDe:
    def test_zero_epsilon_leaves_values_unchanged(self):
        de = {("A", "D1", "L1"): 0.4, ("A", "D2", "L2"): 0.9}
        perturbed = perturb_de(de, epsilon=0.0, rng=random.Random(1))
        assert perturbed == de

    def test_perturbed_values_stay_in_unit_interval(self):
        de = {("A", "D1", "L1"): 0.05, ("A", "D2", "L2"): 0.95}
        rng = random.Random(42)
        for _ in range(200):
            perturbed = perturb_de(de, epsilon=0.5, rng=rng)
            assert all(0.0 <= v <= 1.0 for v in perturbed.values())

    def test_preserves_all_keys(self):
        de = {("A", "D1", "L1"): 0.4, ("B", "D2", "L2"): 0.6}
        perturbed = perturb_de(de, epsilon=0.1, rng=random.Random(0))
        assert set(perturbed.keys()) == set(de.keys())


def make_attributes(*, tactics=None, accessible=True, critical=False, **overrides):
    base = dict(
        tactics=tactics or ["execution"], outcomes=[], q_local_success=0.5,
        impact_confidentiality=0.5, impact_integrity=0.5, impact_availability=0.5,
        critical_asset=critical, accessible_asset=accessible,
    )
    base.update(overrides)
    return NodeAttributes(**base)


def make_occurrence(technique_id, asset_id, **kwargs):
    return TechniqueOccurrence(technique_id=technique_id, asset_id=asset_id, attributes=make_attributes(**kwargs))


def toy_instance():
    """Même patron que `tests/test_optimizer.py::small_instance` : entrée
    -> occurrence intermédiaire (2 candidats admissibles D1/D2) -> Terminal
    critique."""
    entry = make_occurrence("T1566", "H1", tactics=["initial-access"])
    mid = make_occurrence("T1003", "H1")
    terminal = make_occurrence("T1041", "H1", critical=True)
    graph = AttackGraph(
        nodes=[entry, mid, terminal],
        edges=[
            AttackGraphEdge(source_id="T1566@H1", target_id="T1003@H1"),
            AttackGraphEdge(source_id="T1003@H1", target_id="T1041@H1"),
        ],
    )
    admissibility_report = {
        "occurrences": {
            "T1566@H1": {"C_i_h": []},
            "T1003@H1": {"C_i_h": [{"mechanism_id": "D1", "location_id": "L1"}, {"mechanism_id": "D2", "location_id": "L2"}]},
            "T1041@H1": {"C_i_h": []},
        }
    }
    de_by_candidate = {("T1003@H1", "D1", "L1"): 0.5, ("T1003@H1", "D2", "L2"): 0.2}
    cost_by_mechanism = {"D1": 100.0, "D2": 10.0}
    q_by_occurrence = {"T1566@H1": 0.6, "T1003@H1": 0.8, "T1041@H1": 0.7}
    impact_by_occurrence = {"T1566@H1": 0.5, "T1003@H1": 0.5, "T1041@H1": 0.67}
    return graph, admissibility_report, de_by_candidate, cost_by_mechanism, q_by_occurrence, impact_by_occurrence


class TestRunDecisionRobustness:
    def test_zero_epsilon_is_perfectly_stable(self):
        graph, report, de, cost, q, impact = toy_instance()
        result = run_decision_robustness(
            graph, report, de_by_candidate=de, cost_by_mechanism=cost, budget_total=1000.0,
            q_by_occurrence=q, impact_by_occurrence=impact, theta_c=0.99, theta_i=0.99, theta_a=0.99,
            epsilons=(0.0,), n_draws=10, seed=7,
        )
        level = result["levels"][0]
        assert level["identical_plan_rate"] == pytest.approx(1.0)
        assert level["identical_pareto_rate"] == pytest.approx(1.0)
        assert level["failed_draw_count"] == 0

    def test_output_structure_matches_epsilons_tested(self):
        graph, report, de, cost, q, impact = toy_instance()
        result = run_decision_robustness(
            graph, report, de_by_candidate=de, cost_by_mechanism=cost, budget_total=1000.0,
            q_by_occurrence=q, impact_by_occurrence=impact, theta_c=0.99, theta_i=0.99, theta_a=0.99,
            epsilons=(0.02, 0.05, 0.10), n_draws=20, seed=123,
        )
        assert [level["epsilon"] for level in result["levels"]] == [0.02, 0.05, 0.10]
        for level in result["levels"]:
            assert 0.0 <= level["identical_plan_rate"] <= 1.0
            assert 0.0 <= level["identical_pareto_rate"] <= 1.0
            assert level["n_draws"] == 20
        assert result["baseline_plan"]  # au moins une decision non triviale sur ce cas jouet

    def test_reproducible_with_same_seed(self):
        graph, report, de, cost, q, impact = toy_instance()

        def run():
            return run_decision_robustness(
                graph, report, de_by_candidate=de, cost_by_mechanism=cost, budget_total=1000.0,
                q_by_occurrence=q, impact_by_occurrence=impact, theta_c=0.99, theta_i=0.99, theta_a=0.99,
                epsilons=(0.1,), n_draws=15, seed=99,
            )

        first, second = run(), run()
        assert first["levels"][0]["identical_plan_count"] == second["levels"][0]["identical_plan_count"]
