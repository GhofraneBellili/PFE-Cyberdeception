"""
Réf. architecture : CLAUDE.md — contrat technique du PFE Cyberdéception.

Tests unitaires de src/graph_builder.py (§25.4 : pytest obligatoire).

Les identifiants ATT&CK utilisés ici (T1003, T1078, ...) sont des données
de test uniquement : la classe TestGenerality vérifie explicitement
qu'aucune logique de production ne leur est liée.
"""

import json

import networkx as nx
import pytest
from pydantic import ValidationError

from src.graph_builder import (
    ENTRY_TACTIC_LABEL,
    build_attack_graph,
    get_child_ids,
    get_parent_ids,
    identify_entry_nodes,
    identify_terminal_nodes,
    is_entry_node,
    is_terminal_node,
    load_attack_graph_json,
    to_networkx,
)
from src.schemas import AttackGraph, AttackGraphEdge, NodeAttributes, TechniqueOccurrence

# ---------------------------------------------------------------------------
# Constructeurs auxiliaires
# ---------------------------------------------------------------------------


def make_node_attributes(**overrides):
    """Jeu d'attributs valide par défaut (§3.3), personnalisable."""
    base = dict(
        tactics=["execution"],
        outcomes=[],
        q_local_success=0.5,
        impact_confidentiality=0.5,
        impact_integrity=0.5,
        impact_availability=0.5,
        critical_asset=False,
        accessible_asset=True,
    )
    base.update(overrides)
    return base


def make_occurrence(technique_id, asset_id, **attr_overrides):
    return TechniqueOccurrence(
        technique_id=technique_id,
        asset_id=asset_id,
        attributes=NodeAttributes(**make_node_attributes(**attr_overrides)),
    )


def valid_graph_payload():
    """Payload JSON minimal conforme au schéma AttackGraph."""
    return {
        "nodes": [
            {
                "technique_id": "T1078",
                "asset_id": "DC",
                "attributes": {
                    "tactics": ["execution"],
                    "outcomes": [],
                    "q_local_success": 0.5,
                    "impact_confidentiality": 0.5,
                    "impact_integrity": 0.5,
                    "impact_availability": 0.5,
                    "critical_asset": False,
                    "accessible_asset": True,
                },
            },
            {
                "technique_id": "T1059",
                "asset_id": "DC",
                "attributes": {
                    "tactics": ["execution"],
                    "outcomes": [],
                    "q_local_success": 0.6,
                    "impact_confidentiality": 0.2,
                    "impact_integrity": 0.2,
                    "impact_availability": 0.2,
                    "critical_asset": False,
                    "accessible_asset": True,
                },
            },
        ],
        "edges": [{"source_id": "T1078@DC", "target_id": "T1059@DC"}],
    }


# ---------------------------------------------------------------------------
# A. Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_build_attack_graph_valid(self):
        parent = make_occurrence("T1078", "DC")
        child = make_occurrence("T1059", "DC")
        graph = build_attack_graph(
            nodes=[parent, child],
            edges=[AttackGraphEdge(source_id=parent.occurrence_id, target_id=child.occurrence_id)],
        )
        assert isinstance(graph, AttackGraph)
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1

    def test_build_attack_graph_invalid_rejected_via_schemas(self):
        """La validation (ici : arête vers un nœud inexistant) reste
        déléguée à AttackGraph, pas dupliquée dans graph_builder.py."""
        parent = make_occurrence("T1078", "DC")
        with pytest.raises(ValidationError):
            build_attack_graph(
                nodes=[parent],
                edges=[AttackGraphEdge(source_id=parent.occurrence_id, target_id="T9999@GHOST")],
            )


# ---------------------------------------------------------------------------
# B. Chargement JSON
# ---------------------------------------------------------------------------


class TestJsonLoading:
    def test_load_valid_json(self, tmp_path):
        path = tmp_path / "graph.json"
        path.write_text(json.dumps(valid_graph_payload()), encoding="utf-8")
        graph = load_attack_graph_json(path)
        assert isinstance(graph, AttackGraph)
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1

    def test_load_syntactically_invalid_json_rejected(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{ceci n'est pas du JSON valide", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_attack_graph_json(path)

    def test_load_schema_invalid_json_rejected(self, tmp_path):
        payload = valid_graph_payload()
        payload["nodes"][0]["technique_id"] = "not-a-technique-id"
        path = tmp_path / "invalid_schema.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValidationError):
            load_attack_graph_json(path)

    def test_load_missing_field_not_silently_filled(self, tmp_path):
        """Aucune valeur manquante (ici Critical(h)) n'est complétée
        automatiquement : le chargement doit échouer, pas inventer une
        valeur par défaut (§25.3)."""
        payload = valid_graph_payload()
        del payload["nodes"][0]["attributes"]["critical_asset"]
        path = tmp_path / "missing_field.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValidationError):
            load_attack_graph_json(path)


# ---------------------------------------------------------------------------
# C. NetworkX
# ---------------------------------------------------------------------------


class TestToNetworkx:
    def test_node_count_preserved(self):
        parent = make_occurrence("T1078", "DC")
        child = make_occurrence("T1059", "DC")
        graph = build_attack_graph(nodes=[parent, child], edges=[])
        nx_graph = to_networkx(graph)
        assert nx_graph.number_of_nodes() == 2

    def test_edge_count_preserved(self):
        parent = make_occurrence("T1078", "DC")
        child = make_occurrence("T1059", "DC")
        graph = build_attack_graph(
            nodes=[parent, child],
            edges=[AttackGraphEdge(source_id=parent.occurrence_id, target_id=child.occurrence_id)],
        )
        nx_graph = to_networkx(graph)
        assert nx_graph.number_of_edges() == 1

    def test_occurrence_preserved_as_node_attribute(self):
        parent = make_occurrence("T1078", "DC")
        graph = build_attack_graph(nodes=[parent], edges=[])
        nx_graph = to_networkx(graph)
        assert nx_graph.nodes[parent.occurrence_id]["occurrence"] is parent

    def test_branch_probability_preserved_when_set(self):
        parent = make_occurrence("T1078", "DC")
        child_a = make_occurrence("T1059", "DC")
        child_b = make_occurrence("T1021", "DC")
        graph = build_attack_graph(
            nodes=[parent, child_a, child_b],
            edges=[
                AttackGraphEdge(
                    source_id=parent.occurrence_id,
                    target_id=child_a.occurrence_id,
                    branch_probability=0.5,
                ),
                AttackGraphEdge(
                    source_id=parent.occurrence_id,
                    target_id=child_b.occurrence_id,
                    branch_probability=0.5,
                ),
            ],
        )
        nx_graph = to_networkx(graph)
        assert (
            nx_graph.edges[parent.occurrence_id, child_a.occurrence_id]["branch_probability"]
            == 0.5
        )

    def test_branch_probability_none_preserved_as_none(self):
        parent = make_occurrence("T1078", "DC")
        child = make_occurrence("T1059", "DC")
        graph = build_attack_graph(
            nodes=[parent, child],
            edges=[AttackGraphEdge(source_id=parent.occurrence_id, target_id=child.occurrence_id)],
        )
        nx_graph = to_networkx(graph)
        assert (
            nx_graph.edges[parent.occurrence_id, child.occurrence_id]["branch_probability"]
            is None
        )


# ---------------------------------------------------------------------------
# D. Navigation
# ---------------------------------------------------------------------------


class TestNavigation:
    def test_get_parent_ids_correct(self):
        parent = make_occurrence("T1078", "DC")
        child = make_occurrence("T1059", "DC")
        graph = build_attack_graph(
            nodes=[parent, child],
            edges=[AttackGraphEdge(source_id=parent.occurrence_id, target_id=child.occurrence_id)],
        )
        assert get_parent_ids(graph, child.occurrence_id) == [parent.occurrence_id]
        assert get_parent_ids(graph, parent.occurrence_id) == []

    def test_get_child_ids_correct(self):
        parent = make_occurrence("T1078", "DC")
        child = make_occurrence("T1059", "DC")
        graph = build_attack_graph(
            nodes=[parent, child],
            edges=[AttackGraphEdge(source_id=parent.occurrence_id, target_id=child.occurrence_id)],
        )
        assert get_child_ids(graph, parent.occurrence_id) == [child.occurrence_id]
        assert get_child_ids(graph, child.occurrence_id) == []

    def test_get_parent_ids_unknown_occurrence_rejected(self):
        parent = make_occurrence("T1078", "DC")
        graph = build_attack_graph(nodes=[parent], edges=[])
        with pytest.raises(ValueError):
            get_parent_ids(graph, "T9999@GHOST")

    def test_get_child_ids_unknown_occurrence_rejected(self):
        parent = make_occurrence("T1078", "DC")
        graph = build_attack_graph(nodes=[parent], edges=[])
        with pytest.raises(ValueError):
            get_child_ids(graph, "T9999@GHOST")


# ---------------------------------------------------------------------------
# E. Nœuds Entry
# ---------------------------------------------------------------------------


class TestEntryNodes:
    def test_initial_access_and_accessible_is_entry(self):
        node = make_occurrence(
            "T1566", "MAIL-GW", tactics=[ENTRY_TACTIC_LABEL], accessible_asset=True
        )
        assert is_entry_node(node) is True

    def test_initial_access_and_not_accessible_is_not_entry(self):
        node = make_occurrence(
            "T1566", "MAIL-GW", tactics=[ENTRY_TACTIC_LABEL], accessible_asset=False
        )
        assert is_entry_node(node) is False

    def test_not_initial_access_and_accessible_is_not_entry(self):
        node = make_occurrence("T1078", "DC", tactics=["persistence"], accessible_asset=True)
        assert is_entry_node(node) is False

    def test_no_parent_but_not_initial_access_is_not_entry(self):
        """Un nœud sans parent n'est pas Entry si sa tactique n'est pas
        InitialAccess : le degré entrant n'est jamais un critère."""
        node = make_occurrence("T1059", "DC", tactics=["execution"], accessible_asset=True)
        graph = build_attack_graph(nodes=[node], edges=[])
        assert get_parent_ids(graph, node.occurrence_id) == []
        assert is_entry_node(node) is False

    def test_identify_entry_nodes_order_matches_graph_nodes(self):
        entry = make_occurrence(
            "T1566", "MAIL-GW", tactics=[ENTRY_TACTIC_LABEL], accessible_asset=True
        )
        non_entry = make_occurrence("T1078", "DC", tactics=["persistence"], accessible_asset=True)
        graph = build_attack_graph(nodes=[non_entry, entry], edges=[])
        assert identify_entry_nodes(graph) == [entry.occurrence_id]


# ---------------------------------------------------------------------------
# F. Nœuds Terminal
# ---------------------------------------------------------------------------


class TestTerminalNodes:
    THETA = 0.7

    def test_critical_is_terminal(self):
        node = make_occurrence(
            "T1041",
            "DB",
            critical_asset=True,
            impact_confidentiality=0.1,
            impact_integrity=0.1,
            impact_availability=0.1,
        )
        assert is_terminal_node(node, self.THETA, self.THETA, self.THETA) is True

    def test_confidentiality_above_threshold_is_terminal(self):
        node = make_occurrence(
            "T1041",
            "DB",
            critical_asset=False,
            impact_confidentiality=0.8,
            impact_integrity=0.1,
            impact_availability=0.1,
        )
        assert is_terminal_node(node, self.THETA, self.THETA, self.THETA) is True

    def test_integrity_above_threshold_is_terminal(self):
        node = make_occurrence(
            "T1041",
            "DB",
            critical_asset=False,
            impact_confidentiality=0.1,
            impact_integrity=0.8,
            impact_availability=0.1,
        )
        assert is_terminal_node(node, self.THETA, self.THETA, self.THETA) is True

    def test_availability_above_threshold_is_terminal(self):
        node = make_occurrence(
            "T1041",
            "DB",
            critical_asset=False,
            impact_confidentiality=0.1,
            impact_integrity=0.1,
            impact_availability=0.8,
        )
        assert is_terminal_node(node, self.THETA, self.THETA, self.THETA) is True

    def test_all_below_threshold_and_not_critical_is_not_terminal(self):
        node = make_occurrence(
            "T1041",
            "DB",
            critical_asset=False,
            impact_confidentiality=0.1,
            impact_integrity=0.1,
            impact_availability=0.1,
        )
        assert is_terminal_node(node, self.THETA, self.THETA, self.THETA) is False

    def test_exact_threshold_equality_is_terminal(self):
        node = make_occurrence(
            "T1041",
            "DB",
            critical_asset=False,
            impact_confidentiality=self.THETA,
            impact_integrity=0.1,
            impact_availability=0.1,
        )
        assert is_terminal_node(node, self.THETA, self.THETA, self.THETA) is True

    def test_threshold_below_zero_rejected(self):
        node = make_occurrence("T1041", "DB")
        with pytest.raises(ValueError):
            is_terminal_node(node, -0.1, self.THETA, self.THETA)

    def test_threshold_above_one_rejected(self):
        node = make_occurrence("T1041", "DB")
        with pytest.raises(ValueError):
            is_terminal_node(node, self.THETA, 1.5, self.THETA)

    def test_leaf_not_critical_and_below_threshold_is_not_terminal(self):
        """out-degree == 0 n'est jamais, à lui seul, un critère Terminal."""
        node = make_occurrence(
            "T1041",
            "DB",
            critical_asset=False,
            impact_confidentiality=0.1,
            impact_integrity=0.1,
            impact_availability=0.1,
        )
        graph = build_attack_graph(nodes=[node], edges=[])
        assert get_child_ids(graph, node.occurrence_id) == []
        assert is_terminal_node(node, self.THETA, self.THETA, self.THETA) is False

    def test_identify_terminal_nodes_order_matches_graph_nodes(self):
        terminal = make_occurrence("T1041", "DB", critical_asset=True)
        non_terminal = make_occurrence("T1078", "DC", critical_asset=False)
        graph = build_attack_graph(nodes=[non_terminal, terminal], edges=[])
        assert identify_terminal_nodes(graph, self.THETA, self.THETA, self.THETA) == [
            terminal.occurrence_id
        ]


# ---------------------------------------------------------------------------
# G. Généralité — aucune logique liée au cas d'usage de référence (§20)
# ---------------------------------------------------------------------------


class TestGenerality:
    def test_generic_ids_unrelated_to_reference_case(self):
        """Le cas de référence de CLAUDE.md (§20) utilise T1566, T1190,
        T1003, T1078, T1059, T1041. Ce test utilise un ensemble totalement
        différent pour démontrer qu'aucune logique de production n'y est
        liée."""
        entry = make_occurrence(
            "T9001", "PRINTER-7", tactics=[ENTRY_TACTIC_LABEL], accessible_asset=True
        )
        terminal = make_occurrence("T9002", "IOT-CAM-3", critical_asset=True)
        graph = build_attack_graph(
            nodes=[entry, terminal],
            edges=[AttackGraphEdge(source_id=entry.occurrence_id, target_id=terminal.occurrence_id)],
        )
        assert identify_entry_nodes(graph) == [entry.occurrence_id]
        assert identify_terminal_nodes(graph, 0.7, 0.7, 0.7) == [terminal.occurrence_id]
        assert get_child_ids(graph, entry.occurrence_id) == [terminal.occurrence_id]
        assert get_parent_ids(graph, terminal.occurrence_id) == [entry.occurrence_id]


# ---------------------------------------------------------------------------
# H. Cycles — aucune hypothèse DAG non autorisée
# ---------------------------------------------------------------------------


class TestCycles:
    def test_cyclic_graph_not_rejected(self):
        """graph_builder ne prend aucune décision sur les cycles (§9 de la
        tâche de durcissement — OPEN_DECISION différée) : un cycle
        structurellement valide (arêtes non dupliquées, pas de divergence)
        doit être accepté sans erreur. Ce test ne valide aucune propagation
        de risque."""
        a = make_occurrence("T2001", "NODE-A")
        b = make_occurrence("T2002", "NODE-B")
        c = make_occurrence("T2003", "NODE-C")
        graph = build_attack_graph(
            nodes=[a, b, c],
            edges=[
                AttackGraphEdge(source_id=a.occurrence_id, target_id=b.occurrence_id),
                AttackGraphEdge(source_id=b.occurrence_id, target_id=c.occurrence_id),
                AttackGraphEdge(source_id=c.occurrence_id, target_id=a.occurrence_id),
            ],
        )
        assert len(graph.edges) == 3
        nx_graph = to_networkx(graph)
        assert nx.is_directed_acyclic_graph(nx_graph) is False
