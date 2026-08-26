"""
Réf. architecture : CLAUDE.md §10 (SP1) — contrat technique du PFE
Cyberdéception.

Tests unitaires de src/admissibility.py (§25.4 : pytest obligatoire).

Les identifiants ATT&CK et actifs utilisés ici (T1078, T1041, DC, WS01,
...) reprennent volontairement le scénario de référence de CLAUDE.md §20 :
contrairement aux couches offline de préparation de données (D3FEND/
Engage/littérature), SP1 implémente directement la formalisation du
chapitre 3 et doit être validé sur ce scénario, pas sur un cas
générique arbitraire.
"""

import pytest

from src.admissibility import (
    build_admissibility_report,
    evaluate_allowed,
    evaluate_relevant,
    evaluate_requirements_satisfied,
)
from src.schemas import (
    Asset,
    AttackGraph,
    DeceptionAdmissibilityProfile,
    DeceptionMechanism,
    Location,
    NodeAttributes,
    SIInventory,
    SITopologyEdge,
    SystemInstance,
    TechniqueOccurrence,
)

THETA = dict(theta_c=0.8, theta_i=0.8, theta_a=0.8)


def make_attributes(**overrides):
    """Réf. SystemInstance : critical_asset/accessible_asset doivent être
    cohérents avec les actifs des fixtures par défaut (§default_assets :
    ni DC ni WS01 ne sont critiques, pour que la terminalité d'une
    occurrence dépende ici uniquement du seuil d'impact — pas de
    Critical(h), qui rendrait toute occurrence sur DC terminale)."""
    base = dict(
        tactics=["credential-access"],
        outcomes=[],
        q_local_success=0.75,
        impact_confidentiality=0.2,
        impact_integrity=0.1,
        impact_availability=0.1,
        critical_asset=False,
        accessible_asset=True,
    )
    base.update(overrides)
    return NodeAttributes(**base)


def make_mechanism(mechanism_id, *, profile=None, **overrides):
    base = dict(
        id=mechanism_id,
        name=f"Fixture {mechanism_id}",
        description="Fixture mechanism.",
        interaction_mechanism="use credential",
        version="1.0",
        admissibility_profile=profile or DeceptionAdmissibilityProfile(),
    )
    base.update(overrides)
    return DeceptionMechanism(**base)


def make_instance(*, occurrences, assets, locations, topology_edges=None, edges=None):
    graph = AttackGraph(nodes=occurrences, edges=edges or [])
    inventory = SIInventory(assets=assets, locations=locations, topology_edges=topology_edges or [])
    return SystemInstance(graph=graph, si_inventory=inventory)


def default_assets():
    return [
        Asset(
            asset_id="DC",
            asset_type="domain_controller",
            critical=False,
            accessible=True,
            properties={"services": ["ldap", "kerberos"], "artifacts": []},
        ),
        Asset(asset_id="WS01", asset_type="workstation", critical=False, accessible=True, properties={}),
    ]


def default_locations():
    return [
        Location(location_id="auth-store", location_type="credential_store", asset_id="DC"),
        Location(location_id="tmp-dir", location_type="filesystem", asset_id="WS01"),
        Location(location_id="floating", location_type="credential_store", asset_id=None),
    ]


def default_topology_edges():
    return [SITopologyEdge(source_asset_id="DC", target_asset_id="WS01", relation_type="network_adjacency", bidirectional=True)]


# ---------------------------------------------------------------------------
# A. Allowed(d, l)
# ---------------------------------------------------------------------------


class TestAllowed:
    def test_pass_when_location_type_listed(self):
        mechanism = make_mechanism(
            "DT-CRED", profile=DeceptionAdmissibilityProfile(allowed_location_types=["credential_store"])
        )
        location = default_locations()[0]
        assert evaluate_allowed(mechanism, location) == "pass"

    def test_fail_when_location_type_not_listed(self):
        mechanism = make_mechanism(
            "DT-CRED", profile=DeceptionAdmissibilityProfile(allowed_location_types=["credential_store"])
        )
        location = default_locations()[1]  # filesystem
        assert evaluate_allowed(mechanism, location) == "fail"

    def test_undetermined_when_list_empty(self):
        mechanism = make_mechanism("DT-EMPTY")
        location = default_locations()[0]
        assert evaluate_allowed(mechanism, location) == "undetermined"


# ---------------------------------------------------------------------------
# B. RequirementsSatisfied(d, l)
# ---------------------------------------------------------------------------


class TestRequirementsSatisfied:
    def test_pass_when_all_requirements_met(self):
        mechanism = make_mechanism(
            "DT-CRED",
            profile=DeceptionAdmissibilityProfile(
                required_asset_types=["domain_controller"], required_services=["ldap"]
            ),
        )
        location = default_locations()[0]
        asset_by_id = {a.asset_id: a for a in default_assets()}
        assert evaluate_requirements_satisfied(mechanism, location, asset_by_id) == "pass"

    def test_fail_when_asset_type_mismatch(self):
        mechanism = make_mechanism(
            "DT-CRED", profile=DeceptionAdmissibilityProfile(required_asset_types=["workstation"])
        )
        location = default_locations()[0]  # tied to DC (domain_controller)
        asset_by_id = {a.asset_id: a for a in default_assets()}
        assert evaluate_requirements_satisfied(mechanism, location, asset_by_id) == "fail"

    def test_fail_when_service_missing(self):
        mechanism = make_mechanism(
            "DT-CRED", profile=DeceptionAdmissibilityProfile(required_services=["smb"])
        )
        location = default_locations()[0]
        asset_by_id = {a.asset_id: a for a in default_assets()}
        assert evaluate_requirements_satisfied(mechanism, location, asset_by_id) == "fail"

    def test_undetermined_when_no_requirements_declared(self):
        mechanism = make_mechanism("DT-EMPTY")
        location = default_locations()[0]
        asset_by_id = {a.asset_id: a for a in default_assets()}
        assert evaluate_requirements_satisfied(mechanism, location, asset_by_id) == "undetermined"

    def test_fail_when_location_has_no_asset(self):
        mechanism = make_mechanism(
            "DT-CRED", profile=DeceptionAdmissibilityProfile(required_asset_types=["domain_controller"])
        )
        location = default_locations()[2]  # floating, asset_id=None
        asset_by_id = {a.asset_id: a for a in default_assets()}
        assert evaluate_requirements_satisfied(mechanism, location, asset_by_id) == "fail"


# ---------------------------------------------------------------------------
# C. Relevant(T_{i,h}, d, l)
# ---------------------------------------------------------------------------


class TestRelevant:
    def test_pass_when_same_asset(self):
        occurrence = TechniqueOccurrence(technique_id="T1078", asset_id="DC", attributes=make_attributes())
        location = default_locations()[0]  # asset_id=DC
        instance = make_instance(occurrences=[occurrence], assets=default_assets(), locations=default_locations())
        assert evaluate_relevant(occurrence, location, instance) == "pass"

    def test_pass_when_adjacent_via_topology(self):
        occurrence = TechniqueOccurrence(technique_id="T1078", asset_id="DC", attributes=make_attributes())
        location = default_locations()[1]  # asset_id=WS01
        instance = make_instance(
            occurrences=[occurrence],
            assets=default_assets(),
            locations=default_locations(),
            topology_edges=default_topology_edges(),
        )
        assert evaluate_relevant(occurrence, location, instance) == "pass"

    def test_fail_when_not_adjacent(self):
        occurrence = TechniqueOccurrence(technique_id="T1078", asset_id="DC", attributes=make_attributes())
        location = default_locations()[1]  # asset_id=WS01, no topology edge this time
        instance = make_instance(occurrences=[occurrence], assets=default_assets(), locations=default_locations())
        assert evaluate_relevant(occurrence, location, instance) == "fail"

    def test_undetermined_when_location_has_no_asset(self):
        occurrence = TechniqueOccurrence(technique_id="T1078", asset_id="DC", attributes=make_attributes())
        location = default_locations()[2]  # floating
        instance = make_instance(occurrences=[occurrence], assets=default_assets(), locations=default_locations())
        assert evaluate_relevant(occurrence, location, instance) == "undetermined"


# ---------------------------------------------------------------------------
# D. Rapport d'admissibilité complet
# ---------------------------------------------------------------------------


class TestAdmissibilityReport:
    def _instance(self):
        occurrences = [
            TechniqueOccurrence(technique_id="T1078", asset_id="DC", attributes=make_attributes()),
            TechniqueOccurrence(
                technique_id="T1041",
                asset_id="DC",
                attributes=make_attributes(impact_confidentiality=0.9),  # >= theta_c -> Terminal
            ),
        ]
        return make_instance(
            occurrences=occurrences,
            assets=default_assets(),
            locations=default_locations(),
            topology_edges=default_topology_edges(),
        )

    def _catalog(self):
        cred_mechanism = make_mechanism(
            "DT-CRED",
            profile=DeceptionAdmissibilityProfile(
                allowed_location_types=["credential_store"],
                required_asset_types=["domain_controller"],
                required_services=["ldap"],
            ),
        )
        undetermined_mechanism = make_mechanism("DT-EMPTY")
        return {"DT-CRED": cred_mechanism, "DT-EMPTY": undetermined_mechanism}

    def test_admissible_candidate_appears_in_c_i_h(self):
        report = build_admissibility_report(
            self._instance(), self._catalog(), {"T1078": ["DT-CRED"]}, **THETA
        )
        occ = report["occurrences"]["T1078@DC"]
        assert {"mechanism_id": "DT-CRED", "location_id": "auth-store"} in occ["C_i_h"]

    def test_d_i_derived_from_mapping(self):
        report = build_admissibility_report(
            self._instance(), self._catalog(), {"T1078": ["DT-CRED"]}, **THETA
        )
        assert report["occurrences"]["T1078@DC"]["D_i"] == ["DT-CRED"]

    def test_mechanism_not_in_mapping_rejected_without_evaluation(self):
        report = build_admissibility_report(
            self._instance(), self._catalog(), {"T1078": ["DT-CRED"]}, **THETA
        )
        occ = report["occurrences"]["T1078@DC"]
        empty_candidates = [c for c in occ["candidates"] if c["mechanism_id"] == "DT-EMPTY"]
        assert empty_candidates
        for c in empty_candidates:
            assert c["mapping"] == "fail"
            assert c["Autorise"] == "not_evaluated"
            assert c["admissible"] is False
            assert "mapping=faux" in c["rejection_reason"]

    def test_undetermined_profile_excludes_candidate(self):
        report = build_admissibility_report(
            self._instance(), self._catalog(), {"T1078": ["DT-EMPTY"]}, **THETA
        )
        occ = report["occurrences"]["T1078@DC"]
        assert occ["C_i_h"] == []

    def test_terminal_occurrence_has_no_candidates(self):
        report = build_admissibility_report(
            self._instance(), self._catalog(), {"T1041": ["DT-CRED"]}, **THETA
        )
        occ = report["occurrences"]["T1041@DC"]
        assert occ["is_terminal"] is True
        assert occ["candidates"] == []
        assert occ["C_i_h"] == []
        assert occ["D_i"] == []

    def test_rejection_reason_lists_failing_checks(self):
        report = build_admissibility_report(
            self._instance(), self._catalog(), {"T1078": ["DT-CRED"]}, **THETA
        )
        occ = report["occurrences"]["T1078@DC"]
        # DT-CRED contre tmp-dir (filesystem) : Autorise doit echouer (pas credential_store).
        rejected = next(c for c in occ["candidates"] if c["mechanism_id"] == "DT-CRED" and c["location_id"] == "tmp-dir")
        assert rejected["admissible"] is False
        assert "Autorise=fail" in rejected["rejection_reason"]

    def test_summary_counts_consistent(self):
        report = build_admissibility_report(
            self._instance(), self._catalog(), {"T1078": ["DT-CRED"]}, **THETA
        )
        summary = report["summary"]
        assert summary["occurrence_count"] == 2
        assert summary["terminal_occurrence_count"] == 1
        assert summary["admissible_count"] + summary["rejected_count"] == summary["candidate_count"]
        assert summary["admissible_count"] == 1

    def test_deterministic_output(self):
        instance = self._instance()
        catalog = self._catalog()
        mapping = {"T1078": ["DT-CRED"]}
        report_a = build_admissibility_report(instance, catalog, mapping, **THETA)
        report_b = build_admissibility_report(instance, catalog, mapping, **THETA)
        assert report_a == report_b


# ---------------------------------------------------------------------------
# E. Généralité minimale (pas de dépendance réseau/LLM)
# ---------------------------------------------------------------------------


class TestGenerality:
    def test_no_network_or_llm_dependency(self):
        import src.admissibility as module

        from pathlib import Path

        source = Path(module.__file__).read_text(encoding="utf-8").lower()
        for token in ("requests.get", "urllib.request", "openai", "anthropic", "httpx"):
            assert token not in source
