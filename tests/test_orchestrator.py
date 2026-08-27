"""
Réf. architecture : CLAUDE.md §19 (Workflow complet d'exécution) et
section « Orchestrateur » de la tâche d'implémentation du chapitre 4.

Tests unitaires de src/orchestrator.py (§25.4 : pytest obligatoire).
"""

import json

import pytest

from src.annotator_llm import RuleBasedStubAnnotator
from src.orchestrator import OrchestratorError, run_pipeline
from src.rag_indexer import Chunk, build_index
from src.schemas import (
    Asset,
    AttackGraph,
    AttackGraphEdge,
    DeceptionAdmissibilityProfile,
    DeceptionMechanism,
    Location,
    NodeAttributes,
    SIInventory,
    SITopologyEdge,
    SystemInstance,
    TechniqueOccurrence,
)

THETA = 0.85


def make_instance() -> SystemInstance:
    t1078 = TechniqueOccurrence(
        technique_id="T1078",
        asset_id="DC01",
        attributes=NodeAttributes(
            tactics=["initial-access", "persistence"],
            outcomes=[],
            q_local_success=0.75,
            impact_confidentiality=0.6,
            impact_integrity=0.2,
            impact_availability=0.1,
            critical_asset=False,
            accessible_asset=True,
        ),
    )
    t1003 = TechniqueOccurrence(
        technique_id="T1003",
        asset_id="DC01",
        attributes=NodeAttributes(
            tactics=["credential-access"],
            outcomes=[],
            q_local_success=0.65,
            impact_confidentiality=0.9,
            impact_integrity=0.2,
            impact_availability=0.1,
            critical_asset=False,
            accessible_asset=True,
        ),
    )
    graph = AttackGraph(nodes=[t1078, t1003], edges=[AttackGraphEdge(source_id="T1078@DC01", target_id="T1003@DC01")])
    assets = [
        Asset(
            asset_id="DC01",
            asset_type="domain_controller",
            critical=False,
            accessible=True,
            properties={"services": ["ldap"], "artifacts": []},
        ),
        Asset(asset_id="WS01", asset_type="workstation", critical=False, accessible=True, properties={}),
    ]
    locations = [
        Location(location_id="auth-store", location_type="credential_store", asset_id="DC01"),
        Location(location_id="/tmp", location_type="filesystem", asset_id="WS01"),
    ]
    topology_edges = [
        SITopologyEdge(source_asset_id="DC01", target_asset_id="WS01", relation_type="network_adjacency", bidirectional=True)
    ]
    return SystemInstance(graph=graph, si_inventory=SIInventory(assets=assets, locations=locations, topology_edges=topology_edges))


def make_catalog() -> dict[str, DeceptionMechanism]:
    duc = DeceptionMechanism(
        id="D3-DUC",
        name="Decoy User Credential",
        description="A Credential created for the purpose of deceiving an adversary.",
        interaction_mechanism="use credential",
        version="1.5.0",
        admissibility_profile=DeceptionAdmissibilityProfile(
            allowed_location_types=["credential_store"],
            required_asset_types=["domain_controller"],
            required_services=["ldap"],
        ),
    )
    return {"D3-DUC": duc}


def make_rag_index() -> object:
    chunks = [
        Chunk(
            chunk_id="c1",
            source_id="s1",
            source_type="literature",
            document_id="d1",
            locator="l",
            text="Decoy User Credential is a credential created to deceive an adversary on a domain controller.",
            text_hash="hash1",
        )
    ]
    return build_index(chunks)


def make_cost_inputs() -> dict[str, dict]:
    return {
        "D3-DUC": {
            "deployment": {"t_setup": 4.0, "w_eng": 50.0, "l_data": 1.0, "w_data": 20.0, "c_integration": 50.0},
            "resource": {"r_cpu": 0.5, "c_cpu": 0.02, "r_ram": 1.0, "c_ram": 0.01, "r_disk": 5.0, "c_disk": 0.001, "r_network": 0.1, "c_network": 0.05},
            "maintenance": {"t_monitoring": 0.1, "w_eng": 50.0, "s_logs": 0.5, "w_storage": 0.01, "c_updates": 0.2},
        }
    }


def run_kwargs(run_id: str, tmp_path, *, budget_total: float = 5000.0) -> dict:
    return dict(
        run_id=run_id,
        instance=make_instance(),
        catalog=make_catalog(),
        mapping={"T1078": ["D3-DUC"]},
        rag_index=make_rag_index(),
        annotator=RuleBasedStubAnnotator(),
        cost_inputs_by_mechanism=make_cost_inputs(),
        horizon=720.0,
        budget_total=budget_total,
        theta_c=THETA,
        theta_i=THETA,
        theta_a=THETA,
        q_by_occurrence={"T1078@DC01": 0.75, "T1003@DC01": 0.65},
        impact_by_occurrence={"T1078@DC01": 0.43, "T1003@DC01": 0.61},
        annotation_set_version="test-v1",
        output_root=tmp_path / "runs",
    )


class TestRunPipeline:
    def test_creates_all_expected_files(self, tmp_path):
        result = run_pipeline(**run_kwargs("run-001", tmp_path))
        run_dir = result["run_dir"]
        expected_files = {
            "input_manifest.json",
            "candidates.json",
            "retrieval.json",
            "annotations_raw.json",
            "annotations_frozen.json",
            "costs.json",
            "pareto.json",
            "deployment_plan.json",
            "risks.json",
            "deployment_report.json",
            "run_manifest.json",
        }
        actual_files = {p.name for p in run_dir.glob("*.json")}
        assert expected_files <= actual_files

    def test_input_manifest_has_no_stray_budget_leak_downstream(self, tmp_path):
        result = run_pipeline(**run_kwargs("run-002", tmp_path))
        # Le contexte d'annotation (deja valide par AnnotationContext) ne doit
        # jamais avoir vu le budget — verifie indirectement via l'absence
        # d'erreur de validation Pydantic pendant l'execution complete.
        assert result["run_manifest"]["status"] == "completed"

    def test_deployment_plan_matches_optimizer_selection(self, tmp_path):
        result = run_pipeline(**run_kwargs("run-003", tmp_path))
        plan = result["deployment_plan"]
        selected = result["optimization_result"]["selected"].configuration.to_deployment_plan()
        assert plan == selected

    def test_risks_contain_avec_and_sans_deception(self, tmp_path):
        result = run_pipeline(**run_kwargs("run-004", tmp_path))
        risks = result["risks"]
        assert "T1003@DC01" in risks["avec_deception"]
        assert "T1003@DC01" in risks["sans_deception"]

    def test_frozen_table_de_used_by_optimizer(self, tmp_path):
        result = run_pipeline(**run_kwargs("run-005", tmp_path))
        de_map = result["frozen_table"].de_by_candidate()
        assert de_map  # au moins un candidat gelé
        # Le DE gelé doit être celui effectivement utilisé pour évaluer les
        # risques (cohérence bout-en-bout).
        for (occurrence_id, mechanism_id, location_id), de in de_map.items():
            plan_entries = [p for p in result["deployment_plan"] if p["occurrence_id"] == occurrence_id]
            if plan_entries:
                assert plan_entries[0]["DE"] == pytest.approx(de)

    def test_deployment_report_matches_plan_and_risks(self, tmp_path):
        """Réf. §17.6 : Y* (deployment_report) doit reprendre exactement le
        plan et les risques avant/après déjà calculés, sans les
        recalculer."""
        result = run_pipeline(**run_kwargs("run-009", tmp_path))
        plan = result["deployment_plan"]
        rows = result["deployment_report"]
        assert len(rows) == len(plan)
        for row, placement in zip(rows, plan):
            assert row.occurrence_id == placement["occurrence_id"]
            assert row.cost == pytest.approx(placement["Cost"])
            assert row.de == pytest.approx(placement["DE"])
            assert row.risk_before == pytest.approx(result["risks"]["sans_deception"][row.occurrence_id])
            assert row.risk_after == pytest.approx(result["risks"]["avec_deception"][row.occurrence_id])

    def test_report_row_variation_is_zero_while_terminal_risk_differs(self, tmp_path):
        """Documente un comportement attendu (pas un bug, réf. docstring de
        src/reporter.py) : la ligne de rapport pour l'occurrence PROTEGEE
        (non terminale, T1078@DC01) affiche une variation nulle -- Gamma
        agit sur la transmission vers les enfants (§14.3), jamais sur le
        risque propre de l'occurrence -- alors que le risque de l'occurrence
        TERMINALE en aval (T1003@DC01) diminue reellement."""
        result = run_pipeline(**run_kwargs("run-010", tmp_path))
        report_row = result["deployment_report"][0]
        assert report_row.occurrence_id == "T1078@DC01"
        assert report_row.risk_variation == pytest.approx(0.0, abs=1e-9)

        terminal_before = result["risks"]["sans_deception"]["T1003@DC01"]
        terminal_after = result["risks"]["avec_deception"]["T1003@DC01"]
        assert terminal_after < terminal_before

    def test_run_manifest_json_is_readable(self, tmp_path):
        result = run_pipeline(**run_kwargs("run-006", tmp_path))
        manifest_path = result["run_dir"] / "run_manifest.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert payload["run_id"] == "run-006"
        assert payload["status"] == "completed"

    def test_budget_too_low_raises_orchestrator_error(self, tmp_path):
        with pytest.raises(OrchestratorError):
            run_pipeline(**run_kwargs("run-007", tmp_path, budget_total=-1.0))


class TestLlmOutOfExecutionPath:
    def test_orchestrator_calls_annotator_only_before_freeze(self, tmp_path):
        """Reformule l'invariant central : le provider d'annotation n'est
        jamais rappelé après le gel — vérifié en comptant les appels d'un
        annotateur instrumenté."""

        class CountingAnnotator(RuleBasedStubAnnotator):
            def __init__(self):
                super().__init__()
                self.calls = 0

            def annotate(self, context, *, now=None):
                self.calls += 1
                return super().annotate(context, now=now)

        annotator = CountingAnnotator()
        kwargs = run_kwargs("run-008", tmp_path)
        kwargs["annotator"] = annotator
        result = run_pipeline(**kwargs)
        admissible_count = result["admissibility_report"]["summary"]["admissible_count"]
        assert annotator.calls == admissible_count
