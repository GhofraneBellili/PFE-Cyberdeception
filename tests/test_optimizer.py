"""
Réf. architecture : CLAUDE.md §16 (Problème global d'optimisation (P)) —
contrat technique du PFE Cyberdéception.

Tests unitaires de src/optimizer.py (§25.4 : pytest obligatoire).

`TestExhaustiveValidationSmallInstance` répond directement à CLAUDE.md
§23 (« validation exhaustive du solveur sur petite instance ») : sur une
petite instance, toutes les configurations faisables sont énumérées « à
la main », leur objectif est calculé indépendamment, et la meilleure
solution exacte est comparée à celle produite par `solve()`.
"""

import pytest

from src.optimizer import (
    Candidate,
    Configuration,
    OptimizerError,
    build_candidates_from_admissibility,
    dominates,
    enumerate_configurations,
    evaluate_configuration,
    filter_by_budget,
    pareto_front,
    select_by_sum_aggregation,
    solve,
)
from src.risk_engine import propagate_risk
from src.schemas import AttackGraph, AttackGraphEdge, NodeAttributes, TechniqueOccurrence

THETA = 0.99


def make_attributes(*, tactics=None, accessible=True, critical=False, **overrides):
    base = dict(
        tactics=tactics or ["execution"],
        outcomes=[],
        q_local_success=0.5,
        impact_confidentiality=0.5,
        impact_integrity=0.5,
        impact_availability=0.5,
        critical_asset=critical,
        accessible_asset=accessible,
    )
    base.update(overrides)
    return NodeAttributes(**base)


def make_occurrence(technique_id, asset_id, **kwargs):
    return TechniqueOccurrence(technique_id=technique_id, asset_id=asset_id, attributes=make_attributes(**kwargs))


def small_instance():
    """Entrée T1566@H1 -> T1003@H1 (2 candidats admissibles) -> T1041@H1
    (Terminal, critical_asset=True). Graphe linéaire, non divergent."""
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
            "T1003@H1": {
                "C_i_h": [
                    {"mechanism_id": "D1", "location_id": "L1"},
                    {"mechanism_id": "D2", "location_id": "L2"},
                ]
            },
            "T1041@H1": {"C_i_h": []},
        }
    }
    de_by_candidate = {("T1003@H1", "D1", "L1"): 0.5, ("T1003@H1", "D2", "L2"): 0.2}
    cost_by_mechanism = {"D1": 100.0, "D2": 10.0}
    q_by_occurrence = {"T1566@H1": 0.6, "T1003@H1": 0.8, "T1041@H1": 0.7}
    impact_by_occurrence = {"T1566@H1": 0.5, "T1003@H1": 0.5, "T1041@H1": 0.67}
    return graph, admissibility_report, de_by_candidate, cost_by_mechanism, q_by_occurrence, impact_by_occurrence


# ---------------------------------------------------------------------------
# A. Construction des candidats — réf. §16.1/§16.3
# ---------------------------------------------------------------------------


class TestBuildCandidates:
    def test_builds_candidates_from_c_i_h(self):
        graph, report, de, cost, _, _ = small_instance()
        candidates_by_occurrence = build_candidates_from_admissibility(
            report, de_by_candidate=de, cost_by_mechanism=cost
        )
        assert candidates_by_occurrence["T1566@H1"] == []
        assert candidates_by_occurrence["T1041@H1"] == []
        mid_candidates = candidates_by_occurrence["T1003@H1"]
        assert len(mid_candidates) == 2
        assert {c.mechanism_id for c in mid_candidates} == {"D1", "D2"}

    def test_missing_de_raises(self):
        graph, report, de, cost, _, _ = small_instance()
        del de[("T1003@H1", "D1", "L1")]
        with pytest.raises(OptimizerError):
            build_candidates_from_admissibility(report, de_by_candidate=de, cost_by_mechanism=cost)

    def test_missing_cost_raises(self):
        graph, report, de, cost, _, _ = small_instance()
        del cost["D1"]
        with pytest.raises(OptimizerError):
            build_candidates_from_admissibility(report, de_by_candidate=de, cost_by_mechanism=cost)


# ---------------------------------------------------------------------------
# B. Énumération — réf. §16.1 (unicité) / §23 (petite instance)
# ---------------------------------------------------------------------------


class TestEnumerateConfigurations:
    def test_none_plus_each_candidate(self):
        graph, report, de, cost, _, _ = small_instance()
        candidates_by_occurrence = build_candidates_from_admissibility(
            report, de_by_candidate=de, cost_by_mechanism=cost
        )
        configurations = enumerate_configurations(candidates_by_occurrence)
        # une seule occurrence avec des candidats (2) => 1 (aucune) + 2 = 3 configurations
        assert len(configurations) == 3

    def test_at_most_one_candidate_per_occurrence(self):
        graph, report, de, cost, _, _ = small_instance()
        candidates_by_occurrence = build_candidates_from_admissibility(
            report, de_by_candidate=de, cost_by_mechanism=cost
        )
        configurations = enumerate_configurations(candidates_by_occurrence)
        for configuration in configurations:
            for occurrence_id in configuration.selections:
                assert occurrence_id in candidates_by_occurrence

    def test_no_candidates_anywhere_yields_single_empty_configuration(self):
        configurations = enumerate_configurations({"T1@H": [], "T2@H": []})
        assert configurations == [Configuration(selections={})]

    def test_max_configurations_guard_raises(self):
        candidates_by_occurrence = {
            "A": [Candidate("A", "d1", "l1", 0.1, 1.0), Candidate("A", "d2", "l2", 0.1, 1.0)],
            "B": [Candidate("B", "d1", "l1", 0.1, 1.0), Candidate("B", "d2", "l2", 0.1, 1.0)],
        }
        with pytest.raises(OptimizerError):
            enumerate_configurations(candidates_by_occurrence, max_configurations=4)


# ---------------------------------------------------------------------------
# C. Budget — réf. §16.2
# ---------------------------------------------------------------------------


class TestFilterByBudget:
    def test_filters_configurations_over_budget(self):
        configurations = [
            Configuration(selections={}),
            Configuration(selections={"T1003@H1": Candidate("T1003@H1", "D1", "L1", 0.5, 100.0)}),
            Configuration(selections={"T1003@H1": Candidate("T1003@H1", "D2", "L2", 0.2, 10.0)}),
        ]
        feasible = filter_by_budget(configurations, 50.0)
        assert len(feasible) == 2
        assert all(c.total_cost <= 50.0 for c in feasible)

    def test_negative_budget_rejected(self):
        with pytest.raises(OptimizerError):
            filter_by_budget([Configuration(selections={})], -1.0)


# ---------------------------------------------------------------------------
# D. Dominance et front de Pareto — réf. §16
# ---------------------------------------------------------------------------


class TestDominance:
    def test_strict_dominance(self):
        assert dominates({"a": 0.1, "b": 0.2}, {"a": 0.2, "b": 0.3})

    def test_equal_vectors_do_not_dominate(self):
        assert not dominates({"a": 0.1}, {"a": 0.1})

    def test_incomparable_vectors_do_not_dominate(self):
        assert not dominates({"a": 0.1, "b": 0.9}, {"a": 0.2, "b": 0.1})

    def test_mismatched_keys_raise(self):
        with pytest.raises(OptimizerError):
            dominates({"a": 0.1}, {"b": 0.1})


class TestParetoFront:
    def test_front_excludes_dominated_configurations(self):
        cfg_none = Configuration(selections={})
        cfg_d2 = Configuration(selections={"T1003@H1": Candidate("T1003@H1", "D2", "L2", 0.2, 10.0)})
        evaluated = [
            evaluate_configuration_stub(cfg_none, {"T1041@H1": 0.22512}),
            evaluate_configuration_stub(cfg_d2, {"T1041@H1": 0.180096}),
        ]
        front = pareto_front(evaluated)
        assert len(front) == 1
        assert front[0].configuration is cfg_d2

    def test_incomparable_configurations_both_kept(self):
        cfg_a = Configuration(selections={})
        cfg_b = Configuration(selections={"X@H": Candidate("X@H", "D", "L", 0.1, 1.0)})
        evaluated = [
            evaluate_configuration_stub(cfg_a, {"t1": 0.1, "t2": 0.9}),
            evaluate_configuration_stub(cfg_b, {"t1": 0.9, "t2": 0.1}),
        ]
        front = pareto_front(evaluated)
        assert len(front) == 2


def evaluate_configuration_stub(configuration, terminal_risks):
    """Petit constructeur direct d'EvaluatedConfiguration pour isoler les
    tests de dominance/Pareto de la propagation SP3 réelle."""
    from src.optimizer import EvaluatedConfiguration

    return EvaluatedConfiguration(configuration=configuration, terminal_risks=terminal_risks)


class TestSelectBySumAggregation:
    def test_selects_minimum_sum_on_front(self):
        cfg_a = Configuration(selections={})
        cfg_b = Configuration(selections={"X@H": Candidate("X@H", "D", "L", 0.1, 1.0)})
        evaluated = [
            evaluate_configuration_stub(cfg_a, {"t1": 0.5}),
            evaluate_configuration_stub(cfg_b, {"t1": 0.2}),
        ]
        selected = select_by_sum_aggregation(evaluated)
        assert selected.configuration is cfg_b

    def test_empty_front_raises(self):
        with pytest.raises(OptimizerError):
            select_by_sum_aggregation([])


# ---------------------------------------------------------------------------
# E. Résolution complète de (P) sur une petite instance — réf. §16
# ---------------------------------------------------------------------------


class TestSolveEndToEnd:
    def test_solve_selects_affordable_lower_risk_configuration(self):
        graph, report, de, cost, q, impact = small_instance()
        result = solve(
            graph,
            report,
            de_by_candidate=de,
            cost_by_mechanism=cost,
            budget_total=50.0,
            q_by_occurrence=q,
            impact_by_occurrence=impact,
            theta_c=THETA,
            theta_i=THETA,
            theta_a=THETA,
        )
        assert result["terminal_ids"] == ["T1041@H1"]
        assert result["configurations_enumerated"] == 3
        assert result["configurations_feasible"] == 2  # D1 (cout=100) exclu par le budget
        selected_plan = result["selected"].configuration.to_deployment_plan()
        assert len(selected_plan) == 1
        assert selected_plan[0]["mechanism_id"] == "D2"
        assert result["selected"].terminal_risks["T1041@H1"] == pytest.approx(0.180096, abs=1e-4)

    def test_no_terminal_nodes_raises(self):
        entry = make_occurrence("T1566", "H1", tactics=["initial-access"])
        graph = AttackGraph(nodes=[entry], edges=[])
        with pytest.raises(OptimizerError):
            solve(
                graph,
                {"occurrences": {"T1566@H1": {"C_i_h": []}}},
                de_by_candidate={},
                cost_by_mechanism={},
                budget_total=10.0,
                q_by_occurrence={"T1566@H1": 0.5},
                impact_by_occurrence={"T1566@H1": 0.5},
                theta_c=THETA,
                theta_i=THETA,
                theta_a=THETA,
            )

    def test_budget_too_low_raises(self):
        graph, report, de, cost, q, impact = small_instance()
        with pytest.raises(OptimizerError):
            solve(
                graph,
                report,
                de_by_candidate=de,
                cost_by_mechanism=cost,
                budget_total=-1.0,
                q_by_occurrence=q,
                impact_by_occurrence=impact,
                theta_c=THETA,
                theta_i=THETA,
                theta_a=THETA,
            )


# ---------------------------------------------------------------------------
# F. Validation exhaustive sur petite instance — réf. CLAUDE.md §23
# ---------------------------------------------------------------------------


class TestExhaustiveValidationSmallInstance:
    def test_manual_enumeration_matches_solver(self):
        """Réf. §23 : sur une petite instance, énumérer TOUTES les
        configurations faisables « à la main » (sans passer par
        enumerate_configurations), calculer leur objectif indépendamment
        via propagate_risk, et comparer la meilleure solution exacte à
        celle produite par solve()."""
        graph, report, de, cost, q, impact = small_instance()
        budget_total = 50.0

        manual_configs = {
            "none": {},
            "D1": {"T1003@H1": 0.5},
            "D2": {"T1003@H1": 0.2},
        }
        manual_costs = {"none": 0.0, "D1": 100.0, "D2": 10.0}

        feasible = {name: de_map for name, de_map in manual_configs.items() if manual_costs[name] <= budget_total}
        assert set(feasible) == {"none", "D2"}

        objectives = {}
        for name, de_map in feasible.items():
            propagation = propagate_risk(graph, q_by_occurrence=q, de_by_occurrence=de_map, impact_by_occurrence=impact)
            objectives[name] = propagation["T1041@H1"]["R"]

        best_name = min(objectives, key=objectives.get)
        assert best_name == "D2"

        result = solve(
            graph,
            report,
            de_by_candidate=de,
            cost_by_mechanism=cost,
            budget_total=budget_total,
            q_by_occurrence=q,
            impact_by_occurrence=impact,
            theta_c=THETA,
            theta_i=THETA,
            theta_a=THETA,
        )
        assert result["selected"].terminal_risks["T1041@H1"] == pytest.approx(objectives[best_name])


# ---------------------------------------------------------------------------
# G. Invariant LLM hors du chemin d'exécution
# ---------------------------------------------------------------------------


class TestLlmOutOfExecutionPath:
    def test_optimizer_does_not_import_llm_or_rag(self):
        import ast
        from pathlib import Path

        import src.optimizer as module

        source = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

        forbidden = {"src.annotator_llm", "src.rag_indexer", "src.rag_retriever"}
        assert not (imported_modules & forbidden)
