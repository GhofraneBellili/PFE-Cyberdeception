"""
Réf. architecture : CLAUDE.md §10 (SP1) — contrat technique du PFE
Cyberdéception. Réf. tâche « separate knowledge and organization
capabilities » : SP1 est un module RUNTIME, l'admissibilité vient
exclusivement du catalogue OPÉRATIONNEL de l'organisation
(`OrganizationDeceptionCapability`), jamais du catalogue de connaissances
(`DeceptionMechanism.admissibility_profile`, champ hérité non consulté).

Les identifiants ATT&CK et actifs utilisés ici (T1078, T1041, DC, WS01,
...) reprennent volontairement le scénario de référence de CLAUDE.md §20 :
contrairement aux couches offline de préparation de données (D3FEND/
Engage/littérature), SP1 implémente directement la formalisation du
chapitre 3 et doit être validé sur ce scénario, pas sur un cas
générique arbitraire. Le moteur lui-même (src/admissibility.py) ne code
en dur aucun de ces identifiants (vérifié par TestGenericity).
"""

import pytest

from src.admissibility import (
    build_admissibility_report,
    enabled_mechanism_ids,
    evaluate_allowed,
    evaluate_relevant,
    evaluate_requirements_satisfied,
)
from src.schemas import (
    Asset,
    AttackGraph,
    DeceptionMechanism,
    Location,
    NodeAttributes,
    OrganizationDeceptionCapability,
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


def make_mechanism(mechanism_id, **overrides):
    """Fiche de CONNAISSANCE minimale — plus aucun admissibility_profile
    pertinent pour ces tests (champ hérité, non consulté par
    src/admissibility.py depuis la séparation connaissance/organisation)."""
    base = dict(
        id=mechanism_id,
        name=f"Fixture {mechanism_id}",
        description="Fixture mechanism.",
        interaction_mechanism="use credential",
        version="1.0",
    )
    base.update(overrides)
    return DeceptionMechanism(**base)


def make_capability(mechanism_id, *, enabled=True, **overrides):
    base = dict(mechanism_id=mechanism_id, enabled=enabled)
    base.update(overrides)
    return OrganizationDeceptionCapability(**base)


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
# A. enabled_mechanism_ids (D_org)
# ---------------------------------------------------------------------------


class TestEnabledMechanismIds:
    def test_only_enabled_mechanisms_included(self):
        org = {
            "DT-A": make_capability("DT-A", enabled=True),
            "DT-B": make_capability("DT-B", enabled=False),
        }
        assert enabled_mechanism_ids(org) == frozenset({"DT-A"})

    def test_empty_organization_catalog_yields_empty_d_org(self):
        assert enabled_mechanism_ids({}) == frozenset()


# ---------------------------------------------------------------------------
# B. Allowed(d, l) — réf. tâche §7
# ---------------------------------------------------------------------------


class TestAllowed:
    def test_pass_when_location_type_listed(self):
        capability = make_capability("DT-CRED", allowed_location_types=["credential_store"])
        location = default_locations()[0]
        assert evaluate_allowed(capability, location) == "pass"

    def test_fail_when_location_type_not_listed(self):
        capability = make_capability("DT-CRED", allowed_location_types=["credential_store"])
        location = default_locations()[1]  # filesystem
        assert evaluate_allowed(capability, location) == "fail"

    def test_undetermined_when_list_empty(self):
        capability = make_capability("DT-EMPTY")
        location = default_locations()[0]
        assert evaluate_allowed(capability, location) == "undetermined"

    def test_fail_when_location_explicitly_forbidden(self):
        capability = make_capability(
            "DT-CRED", allowed_location_types=["credential_store"], forbidden_locations=["auth-store"]
        )
        location = default_locations()[0]
        assert evaluate_allowed(capability, location) == "fail"

    def test_fail_when_capability_absent(self):
        assert evaluate_allowed(None, default_locations()[0]) == "fail"


# ---------------------------------------------------------------------------
# C. RequirementsSatisfied(d, l) — réf. tâche §8
# ---------------------------------------------------------------------------


class TestRequirementsSatisfied:
    def test_pass_when_all_requirements_met(self):
        capability = make_capability(
            "DT-CRED", allowed_asset_types=["domain_controller"], required_services=["ldap"]
        )
        location = default_locations()[0]
        asset_by_id = {a.asset_id: a for a in default_assets()}
        assert evaluate_requirements_satisfied(capability, location, asset_by_id) == "pass"

    def test_fail_when_asset_type_not_allowed(self):
        capability = make_capability("DT-CRED", allowed_asset_types=["workstation"])
        location = default_locations()[0]  # tied to DC (domain_controller)
        asset_by_id = {a.asset_id: a for a in default_assets()}
        assert evaluate_requirements_satisfied(capability, location, asset_by_id) == "fail"

    def test_fail_when_asset_type_forbidden(self):
        capability = make_capability("DT-CRED", forbidden_asset_types=["domain_controller"])
        location = default_locations()[0]
        asset_by_id = {a.asset_id: a for a in default_assets()}
        assert evaluate_requirements_satisfied(capability, location, asset_by_id) == "fail"

    def test_fail_when_service_missing(self):
        capability = make_capability("DT-CRED", required_services=["smb"])
        location = default_locations()[0]
        asset_by_id = {a.asset_id: a for a in default_assets()}
        assert evaluate_requirements_satisfied(capability, location, asset_by_id) == "fail"

    def test_fail_when_artifact_missing(self):
        capability = make_capability("DT-CRED", required_artifacts=["kerberos_ticket"])
        location = default_locations()[0]
        asset_by_id = {a.asset_id: a for a in default_assets()}
        assert evaluate_requirements_satisfied(capability, location, asset_by_id) == "fail"

    def test_undetermined_when_no_requirements_declared(self):
        capability = make_capability("DT-EMPTY")
        location = default_locations()[0]
        asset_by_id = {a.asset_id: a for a in default_assets()}
        assert evaluate_requirements_satisfied(capability, location, asset_by_id) == "undetermined"

    def test_fail_when_location_has_no_asset(self):
        capability = make_capability("DT-CRED", allowed_asset_types=["domain_controller"])
        location = default_locations()[2]  # floating, asset_id=None
        asset_by_id = {a.asset_id: a for a in default_assets()}
        assert evaluate_requirements_satisfied(capability, location, asset_by_id) == "fail"

    def test_fail_when_capability_absent(self):
        location = default_locations()[0]
        asset_by_id = {a.asset_id: a for a in default_assets()}
        assert evaluate_requirements_satisfied(None, location, asset_by_id) == "fail"


# ---------------------------------------------------------------------------
# D. Relevant(T_{i,h}, d, l) — inchangé
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
# E. Rapport d'admissibilité complet (réf. tâche §15, critères A-L)
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
        return {
            "DT-CRED": make_mechanism("DT-CRED"),
            "DT-EMPTY": make_mechanism("DT-EMPTY"),
            "DT-DISABLED": make_mechanism("DT-DISABLED"),
            "DT-UNREFERENCED": make_mechanism("DT-UNREFERENCED"),
        }

    def _organization_catalog(self):
        return {
            "DT-CRED": make_capability(
                "DT-CRED",
                enabled=True,
                allowed_location_types=["credential_store"],
                allowed_asset_types=["domain_controller"],
                required_services=["ldap"],
            ),
            "DT-EMPTY": make_capability("DT-EMPTY", enabled=True),
            "DT-DISABLED": make_capability("DT-DISABLED", enabled=False),
            # DT-UNREFERENCED volontairement absent : mécanisme du
            # catalogue de connaissances jamais référencé par l'organisation.
        }

    def test_admissible_candidate_appears_in_c_i_h(self):
        report = build_admissibility_report(
            self._instance(), self._catalog(), self._organization_catalog(), {"T1078": ["DT-CRED"]}, **THETA
        )
        occ = report["occurrences"]["T1078@DC"]
        assert {"mechanism_id": "DT-CRED", "location_id": "auth-store"} in occ["C_i_h"]

    def test_d_i_is_mapping_intersected_with_d_org(self):
        """Réf. tâche §5 : D_i = { d ∈ D_org | M_{i,d}=1 } — DT-DISABLED
        est dans le mapping mais pas dans D_org (desactive), donc absent
        de D_i."""
        report = build_admissibility_report(
            self._instance(),
            self._catalog(),
            self._organization_catalog(),
            {"T1078": ["DT-CRED", "DT-DISABLED"]},
            **THETA,
        )
        assert report["occurrences"]["T1078@DC"]["D_i"] == ["DT-CRED"]

    def test_criterion_a_mechanism_absent_from_organization_catalog_never_in_d_i(self):
        report = build_admissibility_report(
            self._instance(),
            self._catalog(),
            self._organization_catalog(),
            {"T1078": ["DT-UNREFERENCED"]},
            **THETA,
        )
        occ = report["occurrences"]["T1078@DC"]
        assert occ["D_i"] == []
        assert occ["C_i_h"] == []
        unreferenced = [c for c in occ["candidates"] if c["mechanism_id"] == "DT-UNREFERENCED"]
        assert unreferenced
        for c in unreferenced:
            assert c["organization"] == "fail"
            assert c["admissible"] is False
            assert "absent du catalogue operationnel" in c["rejection_reason"]

    def test_criterion_b_disabled_mechanism_never_admissible(self):
        report = build_admissibility_report(
            self._instance(), self._catalog(), self._organization_catalog(), {"T1078": ["DT-DISABLED"]}, **THETA
        )
        occ = report["occurrences"]["T1078@DC"]
        assert occ["C_i_h"] == []
        disabled = [c for c in occ["candidates"] if c["mechanism_id"] == "DT-DISABLED"]
        assert disabled
        for c in disabled:
            assert c["organization"] == "fail"
            assert c["admissible"] is False
            assert "desactive" in c["rejection_reason"]

    def test_criterion_c_mapping_zero_excludes_mechanism(self):
        report = build_admissibility_report(
            self._instance(), self._catalog(), self._organization_catalog(), {"T1078": ["DT-EMPTY"]}, **THETA
        )
        occ = report["occurrences"]["T1078@DC"]
        cred_candidates = [c for c in occ["candidates"] if c["mechanism_id"] == "DT-CRED"]
        assert cred_candidates
        for c in cred_candidates:
            assert c["mapping"] == "fail"
            assert c["Autorise"] == "not_evaluated"
            assert c["admissible"] is False
            assert "mapping=faux" in c["rejection_reason"]

    def test_criterion_d_location_not_allowed_autorise_fails(self):
        report = build_admissibility_report(
            self._instance(), self._catalog(), self._organization_catalog(), {"T1078": ["DT-CRED"]}, **THETA
        )
        occ = report["occurrences"]["T1078@DC"]
        rejected = next(c for c in occ["candidates"] if c["mechanism_id"] == "DT-CRED" and c["location_id"] == "tmp-dir")
        assert rejected["Autorise"] == "fail"
        assert rejected["admissible"] is False

    def test_criterion_e_si_prerequisite_satisfied_pass(self):
        report = build_admissibility_report(
            self._instance(), self._catalog(), self._organization_catalog(), {"T1078": ["DT-CRED"]}, **THETA
        )
        occ = report["occurrences"]["T1078@DC"]
        candidate = next(c for c in occ["candidates"] if c["mechanism_id"] == "DT-CRED" and c["location_id"] == "auth-store")
        assert candidate["PrerequisSatisfaits"] == "pass"

    def test_criterion_f_si_prerequisite_missing_fail(self):
        org = self._organization_catalog()
        org["DT-CRED"] = make_capability(
            "DT-CRED",
            enabled=True,
            allowed_location_types=["credential_store"],
            required_services=["smb"],  # absent de l'actif DC
        )
        report = build_admissibility_report(
            self._instance(), self._catalog(), org, {"T1078": ["DT-CRED"]}, **THETA
        )
        occ = report["occurrences"]["T1078@DC"]
        candidate = next(c for c in occ["candidates"] if c["mechanism_id"] == "DT-CRED" and c["location_id"] == "auth-store")
        assert candidate["PrerequisSatisfaits"] == "fail"

    def test_criterion_g_insufficient_organization_configuration_undetermined(self):
        report = build_admissibility_report(
            self._instance(), self._catalog(), self._organization_catalog(), {"T1078": ["DT-EMPTY"]}, **THETA
        )
        occ = report["occurrences"]["T1078@DC"]
        candidate = next(c for c in occ["candidates"] if c["mechanism_id"] == "DT-EMPTY" and c["location_id"] == "auth-store")
        assert candidate["Autorise"] == "undetermined"
        assert candidate["PrerequisSatisfaits"] == "undetermined"
        assert candidate["admissible"] is False
        assert "missing organization configuration" in candidate["rejection_reason"]

    def test_criterion_h_contextually_irrelevant_location_pertinent_fails(self):
        org = self._organization_catalog()
        org["DT-CRED"] = make_capability(
            "DT-CRED", enabled=True, allowed_location_types=["filesystem"]
        )
        # tmp-dir (filesystem, asset WS01) n'est pas topologiquement relie a DC ici (pas d'edge).
        occurrence = TechniqueOccurrence(technique_id="T1078", asset_id="DC", attributes=make_attributes())
        instance = make_instance(occurrences=[occurrence], assets=default_assets(), locations=default_locations())
        report = build_admissibility_report(instance, self._catalog(), org, {"T1078": ["DT-CRED"]}, **THETA)
        occ = report["occurrences"]["T1078@DC"]
        candidate = next(c for c in occ["candidates"] if c["mechanism_id"] == "DT-CRED" and c["location_id"] == "tmp-dir")
        assert candidate["Pertinent"] == "fail"
        assert candidate["admissible"] is False

    def test_criterion_i_terminal_node_has_no_candidates(self):
        report = build_admissibility_report(
            self._instance(), self._catalog(), self._organization_catalog(), {"T1041": ["DT-CRED"]}, **THETA
        )
        occ = report["occurrences"]["T1041@DC"]
        assert occ["is_terminal"] is True
        assert occ["candidates"] == []
        assert occ["C_i_h"] == []
        assert occ["D_i"] == []

    def test_criterion_j_same_organization_different_graph_different_c_i_h(self):
        """Réf. tâche §14 : même D_org + M, graphes différents -> C_i_h
        différents — preuve que SP1 dépend réellement du contexte online."""
        org = self._organization_catalog()
        mapping = {"T1078": ["DT-CRED"]}

        occurrence_g1 = TechniqueOccurrence(technique_id="T1078", asset_id="DC", attributes=make_attributes())
        instance_g1 = make_instance(occurrences=[occurrence_g1], assets=default_assets(), locations=default_locations())
        report_g1 = build_admissibility_report(instance_g1, self._catalog(), org, mapping, **THETA)

        occurrence_g2 = TechniqueOccurrence(technique_id="T1078", asset_id="WS01", attributes=make_attributes())
        instance_g2 = make_instance(occurrences=[occurrence_g2], assets=default_assets(), locations=default_locations())
        report_g2 = build_admissibility_report(instance_g2, self._catalog(), org, mapping, **THETA)

        c_i_h_g1 = report_g1["occurrences"]["T1078@DC"]["C_i_h"]
        c_i_h_g2 = report_g2["occurrences"]["T1078@WS01"]["C_i_h"]
        assert c_i_h_g1 != c_i_h_g2
        assert c_i_h_g1  # T1078@DC : auth-store admissible (DT-CRED)
        assert c_i_h_g2 == []  # T1078@WS01 : aucun emplacement credential_store colocalise/adjacent

    def test_criterion_k_no_llm_dependency(self):
        import ast
        from pathlib import Path

        source = Path("src/admissibility.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
        assert "src.annotator_llm" not in imported_modules

    def test_criterion_l_no_budget_dependency(self):
        import inspect

        import src.admissibility as module

        source = inspect.getsource(module)
        for token in ("budget", "Budget", "B_total"):
            assert token not in source

    def test_d_org_size_reported_in_summary(self):
        report = build_admissibility_report(
            self._instance(), self._catalog(), self._organization_catalog(), {"T1078": ["DT-CRED"]}, **THETA
        )
        assert report["summary"]["d_org_size"] == 2  # DT-CRED + DT-EMPTY (enabled), DT-DISABLED exclu

    def test_summary_counts_consistent(self):
        report = build_admissibility_report(
            self._instance(), self._catalog(), self._organization_catalog(), {"T1078": ["DT-CRED"]}, **THETA
        )
        summary = report["summary"]
        assert summary["occurrence_count"] == 2
        assert summary["terminal_occurrence_count"] == 1
        assert summary["admissible_count"] + summary["rejected_count"] == summary["candidate_count"]
        assert summary["admissible_count"] == 1

    def test_deterministic_output(self):
        instance = self._instance()
        catalog = self._catalog()
        org = self._organization_catalog()
        mapping = {"T1078": ["DT-CRED"]}
        report_a = build_admissibility_report(instance, catalog, org, mapping, **THETA)
        report_b = build_admissibility_report(instance, catalog, org, mapping, **THETA)
        assert report_a == report_b


# ---------------------------------------------------------------------------
# F. Généricité — réf. tâche §12 : aucun identifiant codé en dur dans le
# moteur SP1 lui-même
# ---------------------------------------------------------------------------


class TestGenericity:
    def test_no_network_or_llm_dependency(self):
        import src.admissibility as module
        from pathlib import Path

        source = Path(module.__file__).read_text(encoding="utf-8").lower()
        for token in ("requests.get", "urllib.request", "openai", "anthropic", "httpx"):
            assert token not in source

    def test_engine_has_no_hardcoded_domain_identifiers(self):
        """Réf. tâche §12 : aucun mechanism_id/attack_id/asset_id/location_id
        de scénario codé en dur dans src/admissibility.py — le moteur doit
        rester générique, prouvé par le fait que d'autres identifiants
        totalement différents (voir test_engine_works_with_arbitrary_identifiers)
        produisent le même comportement."""
        import src.admissibility as module
        from pathlib import Path

        source = Path(module.__file__).read_text(encoding="utf-8")
        for forbidden in ("D3-DNR", "D3-DUC", "EAC0009", "EAC0021", "T1078", "T1039", "FS01", "WS01", "DC01"):
            assert forbidden not in source

    def test_engine_works_with_arbitrary_identifiers(self):
        """Le même moteur, appliqué à des identifiants totalement
        arbitraires (sans rapport avec le scénario de référence), produit
        un résultat cohérent — preuve de généricité."""
        mechanism = make_mechanism("ZZZ-999")
        capability = make_capability(
            "ZZZ-999", enabled=True, allowed_location_types=["weird_place"], allowed_asset_types=["odd_asset"]
        )
        occurrence = TechniqueOccurrence(
            technique_id="T9999.001", asset_id="ASSET-ALPHA", attributes=make_attributes()
        )
        asset = Asset(asset_id="ASSET-ALPHA", asset_type="odd_asset", critical=False, accessible=True, properties={})
        location = Location(location_id="LOC-OMEGA", location_type="weird_place", asset_id="ASSET-ALPHA")
        instance = make_instance(occurrences=[occurrence], assets=[asset], locations=[location])
        report = build_admissibility_report(
            instance, {"ZZZ-999": mechanism}, {"ZZZ-999": capability}, {"T9999.001": ["ZZZ-999"]}, **THETA
        )
        occ = report["occurrences"]["T9999.001@ASSET-ALPHA"]
        assert {"mechanism_id": "ZZZ-999", "location_id": "LOC-OMEGA"} in occ["C_i_h"]
