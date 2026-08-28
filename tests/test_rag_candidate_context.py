"""
Réf. architecture : CLAUDE.md §11.2 — réf. tâche « renforcer le RAG
utilisé par SP2 », §5 « Représentation du contexte candidat pour le
RAG ».

Tests unitaires de `src/rag_candidate_context.py` (§25.4 : pytest
obligatoire).
"""

import json

import pytest

from src.attack_runtime_knowledge import load_attack_runtime_knowledge
from src.rag_candidate_context import RagCandidateContextError, build_rag_candidate_context
from src.schemas import (
    Asset,
    AttackGraph,
    AttackGraphEdge,
    DeceptionMechanism,
    Location,
    NodeAttributes,
    SIInventory,
    SystemInstance,
    TechniqueOccurrence,
)

THETA = dict(theta_c=0.8, theta_i=0.8, theta_a=0.8)


def make_attributes(**overrides):
    base = dict(
        tactics=["initial-access"],
        outcomes=[],
        q_local_success=0.6,
        impact_confidentiality=0.2,
        impact_integrity=0.1,
        impact_availability=0.1,
        critical_asset=False,
        accessible_asset=True,
    )
    base.update(overrides)
    return NodeAttributes(**base)


def make_mechanism(mechanism_id="D1", **overrides):
    base = dict(
        id=mechanism_id,
        name=f"Fixture {mechanism_id}",
        description="Fixture mechanism description.",
        target_artifacts=["credential"],
        interaction_mechanism="attacker uses a fake credential",
        version="1.0",
    )
    base.update(overrides)
    return DeceptionMechanism(**base)


def make_instance():
    occ1 = TechniqueOccurrence(
        technique_id="T1566",
        asset_id="WS01",
        attributes=make_attributes(tactics=["initial-access"], accessible_asset=True),
    )
    occ2 = TechniqueOccurrence(
        technique_id="T1003",
        asset_id="DC",
        attributes=make_attributes(tactics=["credential-access"], accessible_asset=False),
    )
    graph = AttackGraph(
        nodes=[occ1, occ2],
        edges=[AttackGraphEdge(source_id=occ1.occurrence_id, target_id=occ2.occurrence_id)],
    )
    assets = [
        Asset(
            asset_id="WS01",
            asset_type="workstation",
            critical=False,
            accessible=True,
            properties={"services": ["email"], "artifacts": []},
        ),
        Asset(
            asset_id="DC",
            asset_type="domain_controller",
            critical=False,
            accessible=False,
            properties={"services": ["ldap", "kerberos"], "artifacts": ["ntds.dit"]},
        ),
    ]
    locations = [Location(location_id="auth-store", location_type="credential_store", asset_id="DC")]
    inventory = SIInventory(assets=assets, locations=locations)
    return SystemInstance(graph=graph, si_inventory=inventory), occ1, occ2


# ---------------------------------------------------------------------------
# A. Champs de base copiés depuis le candidat
# ---------------------------------------------------------------------------


class TestBasicFields:
    def test_copies_occurrence_mechanism_location_identifiers(self):
        instance, occ1, occ2 = make_instance()
        mechanism = make_mechanism("D1")
        location = instance.si_inventory.locations[0]
        context = build_rag_candidate_context(
            occurrence=occ2, mechanism=mechanism, location=location, instance=instance, **THETA
        )
        assert context.occurrence_id == occ2.occurrence_id
        assert context.technique_id == "T1003"
        assert context.asset_id == "DC"
        assert context.asset_type == "domain_controller"
        assert context.mechanism_id == "D1"
        assert context.mechanism_name == "Fixture D1"
        assert context.location_id == "auth-store"
        assert context.location_type == "credential_store"
        assert context.target_artifacts == ["credential"]

    def test_technique_name_none_without_attack_kb(self):
        instance, occ1, occ2 = make_instance()
        mechanism = make_mechanism("D1")
        location = instance.si_inventory.locations[0]
        context = build_rag_candidate_context(
            occurrence=occ2, mechanism=mechanism, location=location, instance=instance, **THETA
        )
        assert context.technique_name is None

    def test_technique_name_populated_from_attack_staging_without_raw_file(self, tmp_path):
        """Réf. tâche « dernière passe de finition technique », §6-§9 :
        technique_name doit se renseigner depuis le STAGING RAG ATT&CK
        déjà versionné, SANS jamais dépendre du bundle STIX brut
        enterprise-attack.json (absent ici, jamais référencé)."""
        staging = {
            "schema": "attack_rag_seed",
            "techniques": [
                {
                    "technique_id": "T1003",
                    "name": "OS Credential Dumping",
                    "tactics": ["credential-access"],
                    "platforms": ["Windows"],
                    "version": "2.0",
                    "revoked": False,
                    "deprecated": False,
                }
            ],
        }
        staging_path = tmp_path / "attack_rag_seed_test.json"
        staging_path.write_text(json.dumps(staging), encoding="utf-8")
        attack_kb = load_attack_runtime_knowledge(staging_path)

        instance, occ1, occ2 = make_instance()
        mechanism = make_mechanism("D1")
        location = instance.si_inventory.locations[0]
        context = build_rag_candidate_context(
            occurrence=occ2, mechanism=mechanism, location=location, instance=instance, attack_kb=attack_kb, **THETA
        )
        assert context.technique_name == "OS Credential Dumping"

    def test_technique_unknown_to_staging_never_invents_a_name(self, tmp_path):
        """Réf. tâche §10 : une technique du graphe absente du staging
        runtime ne doit jamais produire un nom inventé -- technique_id
        reste, technique_name reste None."""
        staging = {
            "schema": "attack_rag_seed",
            "techniques": [
                {
                    "technique_id": "T9999",
                    "name": "Unrelated Technique",
                    "tactics": [],
                    "platforms": [],
                    "version": None,
                    "revoked": False,
                    "deprecated": False,
                }
            ],
        }
        staging_path = tmp_path / "attack_rag_seed_test.json"
        staging_path.write_text(json.dumps(staging), encoding="utf-8")
        attack_kb = load_attack_runtime_knowledge(staging_path)

        instance, occ1, occ2 = make_instance()
        mechanism = make_mechanism("D1")
        location = instance.si_inventory.locations[0]
        context = build_rag_candidate_context(
            occurrence=occ2, mechanism=mechanism, location=location, instance=instance, attack_kb=attack_kb, **THETA
        )
        assert context.technique_id == "T1003"
        assert context.technique_name is None

    def test_missing_asset_raises_explicit_error(self):
        instance, occ1, occ2 = make_instance()
        rogue_occurrence = TechniqueOccurrence(
            technique_id="T1078", asset_id="UNKNOWN-ASSET", attributes=make_attributes()
        )
        mechanism = make_mechanism("D1")
        location = instance.si_inventory.locations[0]
        with pytest.raises(RagCandidateContextError):
            build_rag_candidate_context(
                occurrence=rogue_occurrence, mechanism=mechanism, location=location, instance=instance, **THETA
            )


# ---------------------------------------------------------------------------
# B. Contexte SI compact (services/artefacts pertinents)
# ---------------------------------------------------------------------------


class TestSIContext:
    def test_relevant_services_and_artifacts_from_asset_properties(self):
        instance, occ1, occ2 = make_instance()
        mechanism = make_mechanism("D1")
        location = instance.si_inventory.locations[0]
        context = build_rag_candidate_context(
            occurrence=occ2, mechanism=mechanism, location=location, instance=instance, **THETA
        )
        assert context.si_context.relevant_services == ["ldap", "kerberos"]
        assert context.si_context.relevant_artifacts == ["ntds.dit"]

    def test_missing_properties_produce_empty_lists_not_invented_values(self):
        instance, occ1, occ2 = make_instance()
        mechanism = make_mechanism("D1")
        location = instance.si_inventory.locations[0]
        context = build_rag_candidate_context(
            occurrence=occ1, mechanism=mechanism, location=location, instance=instance, **THETA
        )
        assert context.si_context.relevant_artifacts == []


# ---------------------------------------------------------------------------
# C. Contexte de graphe compact — parents/enfants directs, Entry/Terminal
# ---------------------------------------------------------------------------


class TestGraphContext:
    def test_entry_occurrence_has_no_parents_and_is_entry(self):
        instance, occ1, occ2 = make_instance()
        mechanism = make_mechanism("D1")
        location = instance.si_inventory.locations[0]
        context = build_rag_candidate_context(
            occurrence=occ1, mechanism=mechanism, location=location, instance=instance, **THETA
        )
        assert context.graph_context.direct_parent_technique_ids == []
        assert context.graph_context.direct_child_technique_ids == ["T1003"]
        assert context.graph_context.is_entry is True
        assert context.graph_context.is_terminal is False

    def test_child_occurrence_has_direct_parent_and_neighboring_tactics(self):
        instance, occ1, occ2 = make_instance()
        mechanism = make_mechanism("D1")
        location = instance.si_inventory.locations[0]
        context = build_rag_candidate_context(
            occurrence=occ2, mechanism=mechanism, location=location, instance=instance, **THETA
        )
        assert context.graph_context.direct_parent_technique_ids == ["T1566"]
        assert context.graph_context.is_entry is False
        assert "initial-access" in context.graph_context.neighboring_tactics

    def test_high_impact_occurrence_is_terminal(self):
        instance, occ1, occ2 = make_instance()
        mechanism = make_mechanism("D1")
        location = instance.si_inventory.locations[0]
        context = build_rag_candidate_context(
            occurrence=occ2,
            mechanism=mechanism,
            location=location,
            instance=instance,
            theta_c=0.05,
            theta_i=0.8,
            theta_a=0.8,
        )
        assert context.graph_context.is_terminal is True


# ---------------------------------------------------------------------------
# D. Interdiction structurelle du budget (§5)
# ---------------------------------------------------------------------------


class TestNoBudgetField:
    def test_context_model_has_no_budget_related_field(self):
        instance, occ1, occ2 = make_instance()
        mechanism = make_mechanism("D1")
        location = instance.si_inventory.locations[0]
        context = build_rag_candidate_context(
            occurrence=occ2, mechanism=mechanism, location=location, instance=instance, **THETA
        )
        dumped = context.model_dump(mode="json")
        forbidden = {"budget", "b_total", "budget_total", "total_budget", "cost", "risk"}
        assert forbidden.isdisjoint({key.lower() for key in dumped})
