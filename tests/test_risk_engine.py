"""
Réf. architecture : CLAUDE.md §14 (SP3) — contrat technique du PFE
Cyberdéception.

Tests unitaires de src/risk_engine.py (§25.4 : pytest obligatoire).

`TestReferenceExample` est l'ANCRE DE VALIDATION du projet (prompt
d'implémentation, section « Ancre de validation — exemple de référence
§11 ») : aucun module de risque, de propagation ou d'optimisation n'est
considéré comme correct tant que ce test ne passe pas. Il reprend le
scénario de référence de CLAUDE.md §20 (T1566/T1190 -> T1003 -> T1078 ->
T1059 -> T1041), simplifié à une seule déception (sur T1003 uniquement),
conformément aux valeurs numériques cibles imposées :
DE=0.429, Gamma_1003=0.571, R_avec_deception=0.0208, R_sans_deception=0.0365,
réduction ≈ 42.9%.
"""

import pytest

from src.risk_engine import (
    RiskEngineError,
    compute_aggregated_impact,
    compute_gamma,
    compute_propagated_success_probability,
    compute_reachability,
    compute_risk,
    compute_transmitted_edge_probability,
    propagate_risk,
)
from src.schemas import AttackGraph, AttackGraphEdge, NodeAttributes, TechniqueOccurrence

TOLERANCE = 1e-3


def make_attributes(*, tactics=None, accessible=True, **overrides):
    base = dict(
        tactics=tactics or ["execution"],
        outcomes=[],
        q_local_success=0.5,
        impact_confidentiality=0.5,
        impact_integrity=0.5,
        impact_availability=0.5,
        critical_asset=False,
        accessible_asset=accessible,
    )
    base.update(overrides)
    return NodeAttributes(**base)


def make_occurrence(technique_id, asset_id, **kwargs):
    return TechniqueOccurrence(technique_id=technique_id, asset_id=asset_id, attributes=make_attributes(**kwargs))


# ---------------------------------------------------------------------------
# A. Formules élémentaires
# ---------------------------------------------------------------------------


class TestElementaryFormulas:
    def test_gamma_no_deception(self):
        assert compute_gamma(0.0) == 1.0

    def test_gamma_with_deception(self):
        assert compute_gamma(0.429) == pytest.approx(0.571, abs=TOLERANCE)

    def test_gamma_out_of_bounds_rejected(self):
        with pytest.raises(RiskEngineError):
            compute_gamma(1.5)

    def test_transmitted_edge_probability_non_divergent(self):
        p_e = compute_transmitted_edge_probability(0.566, 0.571)
        assert p_e == pytest.approx(0.566 * 0.571)

    def test_transmitted_edge_probability_divergent_with_pi(self):
        p_e = compute_transmitted_edge_probability(0.6, 1.0, pi=1 / 3)
        assert p_e == pytest.approx(0.2)

    def test_reachability_single_parent(self):
        assert compute_reachability([0.4]) == pytest.approx(0.4)

    def test_reachability_no_parents_is_one(self):
        assert compute_reachability([]) == 1.0

    def test_reachability_noisy_or_two_parents(self):
        # A = 1 - (1-0.55)(1-0.35) = 0.7075
        assert compute_reachability([0.55, 0.35]) == pytest.approx(0.7075)

    def test_propagated_success_probability(self):
        assert compute_propagated_success_probability(0.7075, 0.80) == pytest.approx(0.566)

    def test_aggregated_impact_default_weights(self):
        i = compute_aggregated_impact(1.0, 0.2, 0.1)
        assert i == pytest.approx(0.67)

    def test_aggregated_impact_invalid_weights_rejected(self):
        with pytest.raises(RiskEngineError):
            compute_aggregated_impact(1.0, 0.2, 0.1, w_c=0.5, w_i=0.5, w_a=0.5)

    def test_risk(self):
        assert compute_risk(0.03110646, 0.67) == pytest.approx(0.03110646 * 0.67)


# ---------------------------------------------------------------------------
# B. Propagation sur petits graphes
# ---------------------------------------------------------------------------


class TestPropagationLinear:
    def test_entry_node_p_equals_q(self):
        entry = make_occurrence("T1566", "H", tactics=["initial-access"])
        graph = AttackGraph(nodes=[entry], edges=[])
        results = propagate_risk(
            graph,
            q_by_occurrence={"T1566@H": 0.55},
            de_by_occurrence={},
            impact_by_occurrence={"T1566@H": 0.5},
        )
        assert results["T1566@H"]["A"] == 1.0
        assert results["T1566@H"]["P"] == pytest.approx(0.55)

    def test_linear_chain_with_deception(self):
        entry = make_occurrence("T1566", "H", tactics=["initial-access"])
        child = make_occurrence("T1003", "H")
        graph = AttackGraph(
            nodes=[entry, child],
            edges=[AttackGraphEdge(source_id="T1566@H", target_id="T1003@H")],
        )
        results = propagate_risk(
            graph,
            q_by_occurrence={"T1566@H": 0.55, "T1003@H": 0.80},
            de_by_occurrence={"T1566@H": 0.42},
            impact_by_occurrence={"T1566@H": 0.5, "T1003@H": 0.5},
        )
        # Gamma_1566 = 1-0.42 = 0.58 ; P^e = 0.55*0.58 ; A_1003 = P^e (parent unique)
        expected_pe = 0.55 * 0.58
        assert results["T1003@H"]["A"] == pytest.approx(expected_pe)
        assert results["T1003@H"]["P"] == pytest.approx(expected_pe * 0.80)

    def test_missing_q_raises(self):
        entry = make_occurrence("T1566", "H", tactics=["initial-access"])
        graph = AttackGraph(nodes=[entry], edges=[])
        with pytest.raises(RiskEngineError):
            propagate_risk(graph, q_by_occurrence={}, de_by_occurrence={}, impact_by_occurrence={"T1566@H": 0.5})

    def test_missing_impact_raises(self):
        entry = make_occurrence("T1566", "H", tactics=["initial-access"])
        graph = AttackGraph(nodes=[entry], edges=[])
        with pytest.raises(RiskEngineError):
            propagate_risk(graph, q_by_occurrence={"T1566@H": 0.5}, de_by_occurrence={}, impact_by_occurrence={})

    def test_missing_de_defaults_to_zero(self):
        entry = make_occurrence("T1566", "H", tactics=["initial-access"])
        child = make_occurrence("T1003", "H")
        graph = AttackGraph(nodes=[entry, child], edges=[AttackGraphEdge(source_id="T1566@H", target_id="T1003@H")])
        results = propagate_risk(
            graph,
            q_by_occurrence={"T1566@H": 0.55, "T1003@H": 0.80},
            de_by_occurrence={},  # aucune déception déclarée
            impact_by_occurrence={"T1566@H": 0.5, "T1003@H": 0.5},
        )
        assert results["T1003@H"]["Gamma"] == 1.0


class TestPropagationConvergenceAndDivergence:
    def test_convergence_two_entries(self):
        e1 = make_occurrence("T1566", "H1", tactics=["initial-access"])
        e2 = make_occurrence("T1190", "H2", tactics=["initial-access"])
        child = make_occurrence("T1003", "H3")
        graph = AttackGraph(
            nodes=[e1, e2, child],
            edges=[
                AttackGraphEdge(source_id="T1566@H1", target_id="T1003@H3"),
                AttackGraphEdge(source_id="T1190@H2", target_id="T1003@H3"),
            ],
        )
        results = propagate_risk(
            graph,
            q_by_occurrence={"T1566@H1": 0.55, "T1190@H2": 0.35, "T1003@H3": 0.80},
            de_by_occurrence={},
            impact_by_occurrence={"T1566@H1": 0.5, "T1190@H2": 0.5, "T1003@H3": 0.5},
        )
        assert results["T1003@H3"]["A"] == pytest.approx(0.7075)
        assert results["T1003@H3"]["P"] == pytest.approx(0.566)

    def test_divergence_equal_split_default(self):
        parent = make_occurrence("T1078", "H")
        c1 = make_occurrence("T1059", "H")
        c2 = make_occurrence("T1057", "H")
        c3 = make_occurrence("T1082", "H")
        graph = AttackGraph(
            nodes=[parent, c1, c2, c3],
            edges=[
                AttackGraphEdge(source_id="T1078@H", target_id="T1059@H"),
                AttackGraphEdge(source_id="T1078@H", target_id="T1057@H"),
                AttackGraphEdge(source_id="T1078@H", target_id="T1082@H"),
            ],
        )
        results = propagate_risk(
            graph,
            q_by_occurrence={"T1078@H": 0.75, "T1059@H": 0.55, "T1057@H": 0.5, "T1082@H": 0.5},
            de_by_occurrence={},
            impact_by_occurrence={"T1078@H": 0.5, "T1059@H": 0.5, "T1057@H": 0.5, "T1082@H": 0.5},
        )
        # T1078 est ici un noeud d'entree "de fait" dans ce sous-graphe isole
        # (aucun parent) : A_1078=1, P_1078=0.75. Divergence 1/3 vers T1059.
        expected_p_1059 = 0.75 * 1.0 * (1 / 3) * 0.55
        assert results["T1059@H"]["P"] == pytest.approx(expected_p_1059)

    def test_divergence_explicit_branch_probability(self):
        parent = make_occurrence("T1078", "H")
        c1 = make_occurrence("T1059", "H")
        c2 = make_occurrence("T1057", "H")
        graph = AttackGraph(
            nodes=[parent, c1, c2],
            edges=[
                AttackGraphEdge(source_id="T1078@H", target_id="T1059@H", branch_probability=0.9),
                AttackGraphEdge(source_id="T1078@H", target_id="T1057@H", branch_probability=0.1),
            ],
        )
        results = propagate_risk(
            graph,
            q_by_occurrence={"T1078@H": 0.75, "T1059@H": 0.55, "T1057@H": 0.5},
            de_by_occurrence={},
            impact_by_occurrence={"T1078@H": 0.5, "T1059@H": 0.5, "T1057@H": 0.5},
        )
        expected_p_1059 = 0.75 * 1.0 * 0.9 * 0.55
        assert results["T1059@H"]["P"] == pytest.approx(expected_p_1059)


# ---------------------------------------------------------------------------
# C. ANCRE DE VALIDATION — exemple de référence (prompt §0bis)
# ---------------------------------------------------------------------------


class TestReferenceExample:
    def _build_graph(self):
        nodes = [
            make_occurrence("T1566", "H1", tactics=["initial-access"]),
            make_occurrence("T1190", "H2", tactics=["initial-access"]),
            make_occurrence("T1003", "H3"),
            make_occurrence("T1078", "H3"),
            make_occurrence("T1059", "H4"),
            make_occurrence("T1057", "H5"),  # frere non suivi (divergence a 3 enfants)
            make_occurrence("T1082", "H6"),  # frere non suivi
            make_occurrence("T1041", "H7"),
        ]
        edges = [
            AttackGraphEdge(source_id="T1566@H1", target_id="T1003@H3"),
            AttackGraphEdge(source_id="T1190@H2", target_id="T1003@H3"),
            AttackGraphEdge(source_id="T1003@H3", target_id="T1078@H3"),
            AttackGraphEdge(source_id="T1078@H3", target_id="T1059@H4"),
            AttackGraphEdge(source_id="T1078@H3", target_id="T1057@H5"),
            AttackGraphEdge(source_id="T1078@H3", target_id="T1082@H6"),
            AttackGraphEdge(source_id="T1059@H4", target_id="T1041@H7"),
        ]
        return AttackGraph(nodes=nodes, edges=edges)

    def _common_inputs(self):
        q = {
            "T1566@H1": 0.55,
            "T1190@H2": 0.35,
            "T1003@H3": 0.80,
            "T1078@H3": 0.75,
            "T1059@H4": 0.55,
            "T1057@H5": 0.5,
            "T1082@H6": 0.5,
            "T1041@H7": 0.70,
        }
        impact = {occ: 0.5 for occ in q}
        impact["T1041@H7"] = compute_aggregated_impact(1.0, 0.2, 0.1)  # I = 0.67
        return q, impact

    def test_reference_example(self):
        """ANCRE DE VALIDATION DU PROJET — voir docstring du module."""
        graph = self._build_graph()
        q, impact = self._common_inputs()

        # --- Avec deception : DE=0.429 sur T1003 uniquement -------------
        results_with = propagate_risk(
            graph, q_by_occurrence=q, de_by_occurrence={"T1003@H3": 0.429}, impact_by_occurrence=impact
        )
        de_1003 = results_with["T1003@H3"]["DE"]
        gamma_1003 = results_with["T1003@H3"]["Gamma"]
        r_avec = results_with["T1041@H7"]["R"]

        assert de_1003 == pytest.approx(0.429, abs=TOLERANCE)
        assert gamma_1003 == pytest.approx(0.571, abs=TOLERANCE)
        assert r_avec == pytest.approx(0.0208, abs=TOLERANCE)

        # --- Sans deception ----------------------------------------------
        results_without = propagate_risk(graph, q_by_occurrence=q, de_by_occurrence={}, impact_by_occurrence=impact)
        r_sans = results_without["T1041@H7"]["R"]
        assert r_sans == pytest.approx(0.0365, abs=TOLERANCE)

        # --- Reduction relative (tolerance elargie : valeur derivee "≈") -
        reduction = (r_sans - r_avec) / r_sans
        assert reduction == pytest.approx(0.429, abs=5e-3)

    def test_reference_example_bounds(self):
        """Réf. §22 : 0 <= A,P,Gamma,R <= 1 pour toutes les occurrences."""
        graph = self._build_graph()
        q, impact = self._common_inputs()
        results = propagate_risk(
            graph, q_by_occurrence=q, de_by_occurrence={"T1003@H3": 0.429}, impact_by_occurrence=impact
        )
        for occurrence_id, values in results.items():
            for key in ("A", "P", "Gamma"):
                assert 0.0 <= values[key] <= 1.0, f"{key} hors bornes pour {occurrence_id}"
            assert values["R"] >= 0.0


# ---------------------------------------------------------------------------
# D. Invariant — le LLM hors du chemin d'exécution
# ---------------------------------------------------------------------------


class TestLlmOutOfExecutionPath:
    def test_risk_engine_does_not_import_llm_or_rag(self):
        """Réf. prompt d'implémentation, section « Invariant — le LLM hors
        du chemin d'exécution » : src/risk_engine.py ne doit jamais
        importer src/annotator_llm.py ni src/rag_indexer.py/
        src/rag_retriever.py."""
        import ast
        from pathlib import Path

        source = Path("src/risk_engine.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

        forbidden = {"src.annotator_llm", "src.rag_indexer", "src.rag_retriever"}
        assert not (imported_modules & forbidden), f"import interdit trouvé : {imported_modules & forbidden}"
