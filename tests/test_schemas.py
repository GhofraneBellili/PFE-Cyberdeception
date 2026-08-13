"""
Réf. architecture : CLAUDE.md — contrat technique du PFE Cyberdéception.

Tests unitaires de src/schemas.py (§25.4 : pytest obligatoire, aucun module
critique sans tests verts).
"""

import pytest
from pydantic import ValidationError

from src.schemas import (
    Annotation,
    AnnotationContext,
    Asset,
    AttackGraph,
    AttackGraphEdge,
    AttackOccurrenceRef,
    DeceptionMechanism,
    DeceptionRef,
    GraphContext,
    Location,
    NodeAttributes,
    SIInventory,
    SystemInstance,
    TechniqueOccurrence,
)

# ---------------------------------------------------------------------------
# Constructeurs auxiliaires
# ---------------------------------------------------------------------------


def make_node_attributes(**overrides):
    """Réf. architecture : "3.3 Attributs minimums d'un nœud" — jeu
    d'attributs valide par défaut, personnalisable via overrides."""
    base = dict(
        tactics=["initial-access"],
        outcomes=["credentials_dumped"],
        q_local_success=0.6,
        impact_confidentiality=0.8,
        impact_integrity=0.2,
        impact_availability=0.1,
        critical_asset=False,
        accessible_asset=True,
    )
    base.update(overrides)
    return base


def make_occurrence(technique_id="T1003", asset_id="DC", **attr_overrides):
    return TechniqueOccurrence(
        technique_id=technique_id,
        asset_id=asset_id,
        attributes=NodeAttributes(**make_node_attributes(**attr_overrides)),
    )


def make_deception_mechanism(**overrides):
    base = dict(
        id="DT11",
        name="Honeytoken credentials",
        description="Jeu d'identifiants leurres déposés sur un partage.",
        target_artifacts=["credential_store"],
        requirements=["agent de journalisation"],
        possible_placements=["poste"],
        interaction_mechanism="Déclenche une alerte lors de l'utilisation.",
        realism_factors=["format identique aux vrais identifiants"],
        progression_effects=["stop", "delay"],
        resource_requirements={"cpu": "faible", "ram": "faible"},
        maintenance_requirements=["rotation périodique"],
        evidence=[{"source": "MITRE Engage", "passage": "extrait de démonstration"}],
        version="1.0.0",
    )
    base.update(overrides)
    return base


def make_annotation(**overrides):
    base = dict(
        metric="R_context",
        score=0.80,
        justification="Le leurre est cohérent avec le contexte observé.",
        evidence=["source_A#chunk_17"],
        confidence=0.87,
    )
    base.update(overrides)
    return base


def make_annotation_context(**overrides):
    base = dict(
        attack_occurrence=AttackOccurrenceRef(
            technique_id="T1003",
            asset="DC",
            attributes=NodeAttributes(**make_node_attributes()),
        ),
        deception=DeceptionRef(id="DT11", name="Honeytoken credentials"),
        placement="credential_store::DC",
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Cas valides
# ---------------------------------------------------------------------------


class TestValidCases:
    def test_technique_occurrence_valid(self):
        occurrence = make_occurrence()
        assert occurrence.occurrence_id == "T1003@DC"
        assert occurrence.attributes.q_local_success == 0.6

    def test_technique_id_with_subtechnique_valid(self):
        occurrence = make_occurrence(technique_id="T1078.001", asset_id="WS-01")
        assert occurrence.occurrence_id == "T1078.001@WS-01"

    def test_deception_mechanism_valid(self):
        mechanism = DeceptionMechanism(**make_deception_mechanism())
        assert mechanism.progression_effects == ["stop", "delay"]
        assert mechanism.resource_requirements.cpu == "faible"

    def test_deception_mechanism_free_form_id_accepted(self):
        """L'id n'est pas contraint au format 'DTxx' (peut venir de D3FEND
        ou de toute autre convention de la KB)."""
        mechanism = DeceptionMechanism(**make_deception_mechanism(id="d3f:DecoyObject"))
        assert mechanism.id == "d3f:DecoyObject"

    def test_annotation_valid(self):
        annotation = Annotation(**make_annotation())
        assert annotation.metric == "R_context"

    def test_annotation_context_valid(self):
        context = AnnotationContext(
            **make_annotation_context(
                graph_context=GraphContext(parents=["T1078@DC"], children=[], terminal_paths=[]),
                system_context={"os": "windows"},
                retrieved_evidence=[],
            )
        )
        assert context.placement == "credential_store::DC"

    def test_attack_graph_non_divergent_valid(self):
        parent = make_occurrence("T1078", "DC")
        child = make_occurrence("T1059", "DC")
        graph = AttackGraph(
            nodes=[parent, child],
            edges=[AttackGraphEdge(source_id="T1078@DC", target_id="T1059@DC")],
        )
        assert len(graph.edges) == 1

    def test_attack_graph_divergent_explicit_pi_valid(self):
        parent = make_occurrence("T1078", "DC")
        child_a = make_occurrence("T1059", "DC")
        child_b = make_occurrence("T1021", "DC")
        graph = AttackGraph(
            nodes=[parent, child_a, child_b],
            edges=[
                AttackGraphEdge(
                    source_id="T1078@DC", target_id="T1059@DC", branch_probability=0.5
                ),
                AttackGraphEdge(
                    source_id="T1078@DC", target_id="T1021@DC", branch_probability=0.5
                ),
            ],
        )
        assert len(graph.edges) == 2

    def test_attack_graph_divergent_implicit_pi_valid(self):
        parent = make_occurrence("T1078", "DC")
        child_a = make_occurrence("T1059", "DC")
        child_b = make_occurrence("T1021", "DC")
        graph = AttackGraph(
            nodes=[parent, child_a, child_b],
            edges=[
                AttackGraphEdge(source_id="T1078@DC", target_id="T1059@DC"),
                AttackGraphEdge(source_id="T1078@DC", target_id="T1021@DC"),
            ],
        )
        assert all(edge.branch_probability is None for edge in graph.edges)

    def test_system_instance_consistent(self):
        node = make_occurrence("T1003", "DC", critical_asset=True, accessible_asset=False)
        graph = AttackGraph(nodes=[node], edges=[])
        inventory = SIInventory(
            assets=[Asset(asset_id="DC", asset_type="serveur", critical=True, accessible=False)],
            locations=[
                Location(
                    location_id="credential_store::DC",
                    location_type="magasin de credentials",
                    asset_id="DC",
                )
            ],
        )
        instance = SystemInstance(graph=graph, si_inventory=inventory)
        assert instance.si_inventory.assets[0].asset_id == "DC"


# ---------------------------------------------------------------------------
# Cas rejetés
# ---------------------------------------------------------------------------


class TestRejectedCases:
    def test_score_out_of_bounds_rejected(self):
        with pytest.raises(ValidationError):
            Annotation(**make_annotation(score=1.5))

    def test_confidence_out_of_bounds_rejected(self):
        with pytest.raises(ValidationError):
            Annotation(**make_annotation(confidence=-0.1))

    def test_missing_required_field_in_node_attributes_rejected(self):
        attrs = make_node_attributes()
        del attrs["q_local_success"]
        with pytest.raises(ValidationError):
            NodeAttributes(**attrs)

    def test_missing_attributes_on_occurrence_rejected(self):
        with pytest.raises(ValidationError):
            TechniqueOccurrence(technique_id="T1003", asset_id="DC")

    def test_outcome_cannot_be_used_as_bare_graph_node(self):
        """Garantie structurelle (§3.2) : AttackGraph.nodes exige des
        TechniqueOccurrence ; une chaîne d'outcome brute ne peut pas être
        ajoutée comme sommet indépendant du graphe."""
        with pytest.raises(ValidationError):
            AttackGraph(nodes=["credentials_dumped"], edges=[])

    def test_outcome_like_string_rejected_as_technique_id(self):
        """Garde secondaire : un technique_id qui ressemble à un outcome
        échoue au pattern ATT&CK."""
        with pytest.raises(ValidationError):
            TechniqueOccurrence(
                technique_id="credentials_dumped",
                asset_id="DC",
                attributes=NodeAttributes(**make_node_attributes()),
            )

    def test_edge_referencing_unknown_node_rejected(self):
        node = make_occurrence("T1003", "DC")
        with pytest.raises(ValidationError):
            AttackGraph(
                nodes=[node],
                edges=[AttackGraphEdge(source_id="T1003@DC", target_id="T9999@GHOST")],
            )

    def test_branch_probability_on_non_divergent_parent_rejected(self):
        parent = make_occurrence("T1078", "DC")
        child = make_occurrence("T1059", "DC")
        with pytest.raises(ValidationError):
            AttackGraph(
                nodes=[parent, child],
                edges=[
                    AttackGraphEdge(
                        source_id="T1078@DC", target_id="T1059@DC", branch_probability=1.0
                    )
                ],
            )

    def test_divergent_branches_not_summing_to_one_rejected(self):
        parent = make_occurrence("T1078", "DC")
        child_a = make_occurrence("T1059", "DC")
        child_b = make_occurrence("T1021", "DC")
        with pytest.raises(ValidationError):
            AttackGraph(
                nodes=[parent, child_a, child_b],
                edges=[
                    AttackGraphEdge(
                        source_id="T1078@DC", target_id="T1059@DC", branch_probability=0.5
                    ),
                    AttackGraphEdge(
                        source_id="T1078@DC", target_id="T1021@DC", branch_probability=0.6
                    ),
                ],
            )

    def test_divergent_branches_mixed_explicit_and_implicit_pi_rejected(self):
        parent = make_occurrence("T1078", "DC")
        child_a = make_occurrence("T1059", "DC")
        child_b = make_occurrence("T1021", "DC")
        with pytest.raises(ValidationError):
            AttackGraph(
                nodes=[parent, child_a, child_b],
                edges=[
                    AttackGraphEdge(
                        source_id="T1078@DC", target_id="T1059@DC", branch_probability=0.5
                    ),
                    AttackGraphEdge(source_id="T1078@DC", target_id="T1021@DC"),
                ],
            )

    def test_budget_in_system_context_rejected(self):
        with pytest.raises(ValidationError):
            AnnotationContext(**make_annotation_context(system_context={"budget": 10000}))

    def test_budget_nested_in_system_context_rejected(self):
        """L'interdiction du budget (§11.2) doit être récursive : ici cachée
        dans deux niveaux de sous-dictionnaires."""
        with pytest.raises(ValidationError):
            AnnotationContext(
                **make_annotation_context(
                    system_context={"infrastructure": {"finance": {"b_total": 5000}}}
                )
            )

    def test_system_instance_missing_asset_rejected(self):
        node = make_occurrence("T1003", "DC")
        graph = AttackGraph(nodes=[node], edges=[])
        inventory = SIInventory(assets=[], locations=[])
        with pytest.raises(ValidationError):
            SystemInstance(graph=graph, si_inventory=inventory)

    def test_system_instance_critical_mismatch_rejected(self):
        node = make_occurrence("T1003", "DC", critical_asset=True)
        graph = AttackGraph(nodes=[node], edges=[])
        inventory = SIInventory(
            assets=[Asset(asset_id="DC", critical=False, accessible=True)],
            locations=[],
        )
        with pytest.raises(ValidationError):
            SystemInstance(graph=graph, si_inventory=inventory)
