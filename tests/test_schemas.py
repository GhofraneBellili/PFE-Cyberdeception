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
    DeceptionAdmissibilityProfile,
    DeceptionMechanism,
    DeceptionRef,
    GraphContext,
    Location,
    NodeAttributes,
    SIInventory,
    SITopologyEdge,
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
            asset_id="DC",
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

    def test_deception_resource_requirements_disk_network_valid(self):
        """§15.2 : le coût des ressources porte sur CPU, RAM, disk et network."""
        mechanism = DeceptionMechanism(
            **make_deception_mechanism(
                resource_requirements={
                    "cpu": "faible",
                    "ram": "faible",
                    "disk": "négligeable",
                    "network": "faible",
                }
            )
        )
        assert mechanism.resource_requirements.disk == "négligeable"
        assert mechanism.resource_requirements.network == "faible"

    def test_deception_mechanism_default_admissibility_profile_valid(self):
        mechanism = DeceptionMechanism(**make_deception_mechanism())
        assert mechanism.admissibility_profile.allowed_location_types == []
        assert mechanism.admissibility_profile.exposure_mode is None

    def test_deception_admissibility_profile_explicit_valid(self):
        profile = DeceptionAdmissibilityProfile(
            allowed_location_types=["poste", "serveur"],
            required_asset_types=["windows"],
            required_services=["smb"],
            required_artifacts=["credential_store"],
            exposure_mode="passive",
        )
        mechanism = DeceptionMechanism(**make_deception_mechanism(admissibility_profile=profile))
        assert mechanism.admissibility_profile.exposure_mode == "passive"
        assert mechanism.admissibility_profile.allowed_location_types == ["poste", "serveur"]

    def test_annotation_valid(self):
        annotation = Annotation(**make_annotation())
        assert annotation.metric == "R_context"

    def test_attack_occurrence_ref_asset_id_and_occurrence_id_valid(self):
        ref = AttackOccurrenceRef(
            technique_id="T1003",
            asset_id="DC",
            attributes=NodeAttributes(**make_node_attributes()),
        )
        assert ref.asset_id == "DC"
        assert ref.occurrence_id == "T1003@DC"

    def test_annotation_context_valid(self):
        context = AnnotationContext(
            **make_annotation_context(
                graph_context=GraphContext(parents=["T1078@DC"], children=[], terminal_paths=[]),
                system_context={"os": "windows"},
                retrieved_evidence=[],
            )
        )
        assert context.placement == "credential_store::DC"
        assert context.attack_occurrence.occurrence_id == "T1003@DC"

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

    def test_system_instance_with_topology_edge_valid(self):
        """Réf. architecture : "10.4 Étape 3 — Emplacements admissibles"
        (Relevant dépend de la relation topologique entre h et l)."""
        node = make_occurrence("T1003", "DC")
        graph = AttackGraph(nodes=[node], edges=[])
        inventory = SIInventory(
            assets=[
                Asset(asset_id="DC", critical=False, accessible=True),
                Asset(asset_id="WS-01", critical=False, accessible=True),
            ],
            locations=[],
            topology_edges=[
                SITopologyEdge(
                    source_asset_id="DC",
                    target_asset_id="WS-01",
                    relation_type="network_adjacency",
                    bidirectional=True,
                )
            ],
        )
        instance = SystemInstance(graph=graph, si_inventory=inventory)
        assert instance.si_inventory.topology_edges[0].relation_type == "network_adjacency"


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

    def test_unknown_extra_field_rejected(self):
        """StrictModel (extra="forbid") : un champ non déclaré doit être
        rejeté plutôt que silencieusement ignoré."""
        attrs = make_node_attributes()
        attrs["unexpected_field"] = "should not be accepted"
        with pytest.raises(ValidationError):
            NodeAttributes(**attrs)

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

    def test_duplicate_attack_edge_rejected(self):
        """Réf. architecture : "3.1 Graphe d'attaque" — E est un ensemble ;
        un même couple (source_id, target_id) dupliqué fausserait le calcul
        de l'out-degree utilisé pour détecter la divergence (§14.4)."""
        parent = make_occurrence("T1078", "DC")
        child = make_occurrence("T1059", "APP")
        with pytest.raises(ValidationError):
            AttackGraph(
                nodes=[parent, child],
                edges=[
                    AttackGraphEdge(source_id="T1078@DC", target_id="T1059@APP"),
                    AttackGraphEdge(source_id="T1078@DC", target_id="T1059@APP"),
                ],
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

    def test_system_instance_accessible_mismatch_rejected(self):
        # make_occurrence() par défaut : critical_asset=False, accessible_asset=True
        node = make_occurrence("T1003", "DC")
        graph = AttackGraph(nodes=[node], edges=[])
        inventory = SIInventory(
            assets=[Asset(asset_id="DC", critical=False, accessible=False)],
            locations=[],
        )
        with pytest.raises(ValidationError):
            SystemInstance(graph=graph, si_inventory=inventory)

    def test_system_instance_duplicate_asset_id_rejected(self):
        node = make_occurrence("T1003", "DC")
        graph = AttackGraph(nodes=[node], edges=[])
        inventory = SIInventory(
            assets=[
                Asset(asset_id="DC", critical=False, accessible=True),
                Asset(asset_id="DC", critical=True, accessible=False),
            ],
            locations=[],
        )
        with pytest.raises(ValidationError):
            SystemInstance(graph=graph, si_inventory=inventory)

    def test_system_instance_duplicate_location_id_rejected(self):
        node = make_occurrence("T1003", "DC")
        graph = AttackGraph(nodes=[node], edges=[])
        inventory = SIInventory(
            assets=[Asset(asset_id="DC", critical=False, accessible=True)],
            locations=[
                Location(location_id="loc1", asset_id="DC"),
                Location(location_id="loc1", asset_id="DC"),
            ],
        )
        with pytest.raises(ValidationError):
            SystemInstance(graph=graph, si_inventory=inventory)

    def test_system_instance_location_unknown_asset_rejected(self):
        node = make_occurrence("T1003", "DC")
        graph = AttackGraph(nodes=[node], edges=[])
        inventory = SIInventory(
            assets=[Asset(asset_id="DC", critical=False, accessible=True)],
            locations=[Location(location_id="loc1", asset_id="GHOST")],
        )
        with pytest.raises(ValidationError):
            SystemInstance(graph=graph, si_inventory=inventory)

    def test_system_instance_topology_edge_unknown_asset_rejected(self):
        node = make_occurrence("T1003", "DC")
        graph = AttackGraph(nodes=[node], edges=[])
        inventory = SIInventory(
            assets=[Asset(asset_id="DC", critical=False, accessible=True)],
            locations=[],
            topology_edges=[
                SITopologyEdge(
                    source_asset_id="DC",
                    target_asset_id="GHOST",
                    relation_type="network_adjacency",
                    bidirectional=True,
                )
            ],
        )
        with pytest.raises(ValidationError):
            SystemInstance(graph=graph, si_inventory=inventory)
