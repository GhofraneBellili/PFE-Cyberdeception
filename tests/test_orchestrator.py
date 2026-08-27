"""
Réf. architecture : CLAUDE.md §19 (Workflow complet d'exécution) et
section « Orchestrateur » de la tâche d'implémentation du chapitre 4.

Tests unitaires de src/orchestrator.py (§25.4 : pytest obligatoire).
"""

import json
from pathlib import Path

import pytest

from src.annotator_llm import RuleBasedStubAnnotator
from src.orchestrator import OrchestratorError, run_pipeline
from src.rag_indexer import Chunk, build_index, build_semantic_index
from src.schemas import (
    Asset,
    AttackGraph,
    AttackGraphEdge,
    DeceptionAdmissibilityProfile,
    DeceptionMechanism,
    Location,
    NodeAttributes,
    OrganizationDeceptionCapability,
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


def make_organization_catalog() -> dict[str, OrganizationDeceptionCapability]:
    """Réf. tâche « separate knowledge and organization capabilities » :
    catalogue OPÉRATIONNEL d'une organisation fictive de test — seule
    source des décisions Autorise/PrerequisSatisfaits de SP1, distincte de
    `make_catalog()` (connaissance)."""
    return {
        "D3-DUC": OrganizationDeceptionCapability(
            mechanism_id="D3-DUC",
            enabled=True,
            allowed_location_types=["credential_store"],
            allowed_asset_types=["domain_controller"],
            required_services=["ldap"],
        )
    }


def make_rag_chunks() -> list[Chunk]:
    return [
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


def make_rag_index() -> object:
    return build_index(make_rag_chunks())


class FakeEmbedder:
    """Embedder déterministe factice — aucune dépendance réseau pendant
    `pytest` (réf. tâche §18)."""

    model_name = "fake-embedder-test-v1"
    dimension = 4

    def encode(self, texts):
        import numpy as np

        vectors = []
        for text in texts:
            seed = sum(ord(c) for c in text) or 1
            rng = np.random.default_rng(seed)
            vector = rng.normal(size=self.dimension).astype(np.float32)
            norm = np.linalg.norm(vector)
            vectors.append(vector / norm if norm > 0 else vector)
        return np.asarray(vectors, dtype=np.float32)


def make_semantic_rag_index() -> object:
    return build_semantic_index(make_rag_chunks(), embedder=FakeEmbedder())


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
        organization_catalog=make_organization_catalog(),
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


class TestRunPipelineRagEngineDispatch:
    """Réf. tâche « RAG sémantique » / §3 « fusion hybride » : run_pipeline
    doit fonctionner avec les trois moteurs RAG, sans jamais télécharger de
    modèle pendant pytest (embedder factice injecté)."""

    def test_lexical_engine_reported_in_manifest(self, tmp_path):
        result = run_pipeline(**run_kwargs("run-rag-lexical", tmp_path))
        assert result["input_manifest"]["rag_engine"] == "lexical_tfidf"

    def test_semantic_engine_completes_and_is_reported(self, tmp_path):
        kwargs = run_kwargs("run-rag-semantic", tmp_path)
        kwargs["rag_index"] = make_semantic_rag_index()
        kwargs["rag_embedder"] = FakeEmbedder()
        result = run_pipeline(**kwargs)
        assert result["input_manifest"]["rag_engine"] == "semantic"
        assert result["run_manifest"]["status"] == "completed"

    def test_hybrid_engine_completes_and_is_reported(self, tmp_path):
        kwargs = run_kwargs("run-rag-hybrid", tmp_path)
        kwargs["rag_index"] = make_semantic_rag_index()
        kwargs["rag_hybrid_lexical_index"] = make_rag_index()
        kwargs["rag_hybrid_alpha"] = 0.8
        kwargs["rag_embedder"] = FakeEmbedder()
        result = run_pipeline(**kwargs)
        assert result["input_manifest"]["rag_engine"] == "hybrid_alpha_0.8"
        assert result["run_manifest"]["status"] == "completed"

    def test_hybrid_lexical_index_with_lexical_only_rag_index_rejected(self, tmp_path):
        kwargs = run_kwargs("run-rag-invalid", tmp_path)
        kwargs["rag_hybrid_lexical_index"] = make_rag_index()  # rag_index reste lexical (make_rag_index())
        with pytest.raises(OrchestratorError):
            run_pipeline(**kwargs)


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


# ---------------------------------------------------------------------------
# Pipeline avec le catalogue et le mapping REELS — réf. § tâche 12
# ---------------------------------------------------------------------------


class TestPipelineWithRealCatalogAndMapping:
    """Réf. tâche 12 (session précédente) + réf. tâche « separate
    knowledge and organization capabilities » (cette session) : "pipeline
    utilisant catalogue + mapping réels".

    Charge data/deception/deception_catalog.json et
    data/deception/attack_deception_mapping.json (construits par
    tools/deception_kb/catalog_builder.py / mapping_builder.py) et fait
    tourner l'orchestrateur complet dessus, sur une instance qui n'exerce
    QUE D3-DUC (T1110.001@DC01 -> T1003@DC01). Le catalogue de
    CONNAISSANCES réel (26 mécanismes) ne fournit plus aucune donnée
    d'admissibilité (champ hérité `admissibility_profile` non consulté) :
    l'admissibilité vient exclusivement d'un catalogue OPÉRATIONNEL de
    test (`_organization_catalog`, ci-dessous), qui active D3-DUC avec des
    prérequis satisfaits par l'instance -> `C_i_h` non vide, plan de
    déploiement produit. Vérifie que le pipeline complet fonctionne de
    bout en bout avec le catalogue de connaissances réel.
    """

    def _real_instance(self):
        t1110 = TechniqueOccurrence(
            technique_id="T1110.001",
            asset_id="DC01",
            attributes=NodeAttributes(
                tactics=["credential-access"],
                outcomes=[],
                q_local_success=0.6,
                impact_confidentiality=0.5,
                impact_integrity=0.1,
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
        graph = AttackGraph(nodes=[t1110, t1003], edges=[AttackGraphEdge(source_id="T1110.001@DC01", target_id="T1003@DC01")])
        assets = [
            Asset(
                asset_id="DC01",
                asset_type="domain_controller",
                critical=False,
                accessible=True,
                properties={"services": ["ldap"]},
            )
        ]
        locations = [Location(location_id="auth-store", location_type="credential_store", asset_id="DC01")]
        return SystemInstance(graph=graph, si_inventory=SIInventory(assets=assets, locations=locations, topology_edges=[]))

    def _organization_catalog(self) -> dict[str, OrganizationDeceptionCapability]:
        """Réf. tâche « separate knowledge and organization capabilities » :
        seule D3-DUC est activée par cette organisation de test, avec des
        prérequis opérationnels satisfaits par `_real_instance` — le
        catalogue de connaissances réel (26 mécanismes) n'influence pas
        cette décision."""
        return {
            "D3-DUC": OrganizationDeceptionCapability(
                mechanism_id="D3-DUC",
                enabled=True,
                allowed_location_types=["credential_store"],
                allowed_asset_types=["domain_controller"],
                required_services=["ldap"],
            )
        }

    def test_pipeline_completes_with_real_catalog_and_mapping(self, tmp_path):
        from src.knowledge_deception import load_attack_deception_mapping, load_deception_catalog, to_sp1_mapping

        catalog_path = Path("data/deception/deception_catalog.json")
        mapping_path = Path("data/deception/attack_deception_mapping.json")
        if not catalog_path.exists() or not mapping_path.exists():
            pytest.skip("Catalogue/mapping réels non générés (tools/deception_kb/catalog_builder.py + mapping_builder.py).")

        kb = load_deception_catalog(catalog_path)
        attack_mapping = load_attack_deception_mapping(mapping_path)
        sp1_mapping = to_sp1_mapping(attack_mapping, kb)

        chunks = [
            Chunk(
                chunk_id="c1",
                source_id="s1",
                source_type="literature",
                document_id="d1",
                locator="l",
                text="Decoy User Credential is a credential created to deceive an adversary.",
                text_hash="hash1",
            )
        ]

        result = run_pipeline(
            run_id="run-real-catalog",
            instance=self._real_instance(),
            catalog=dict(kb.mechanisms_by_id),
            organization_catalog=self._organization_catalog(),
            mapping=sp1_mapping,
            rag_index=build_index(chunks),
            annotator=RuleBasedStubAnnotator(),
            cost_inputs_by_mechanism={
                mechanism_id: {
                    "deployment": {"t_setup": 1.0, "w_eng": 50.0, "l_data": 1.0, "w_data": 20.0, "c_integration": 10.0},
                    "resource": {"r_cpu": 0.1, "c_cpu": 0.02, "r_ram": 0.1, "c_ram": 0.01, "r_disk": 1.0, "c_disk": 0.001, "r_network": 0.1, "c_network": 0.05},
                    "maintenance": {"t_monitoring": 0.05, "w_eng": 50.0, "s_logs": 0.1, "w_storage": 0.01, "c_updates": 0.1},
                }
                for mechanism_id in kb.mechanisms_by_id
            },
            horizon=168.0,
            budget_total=1_000_000.0,
            theta_c=0.85,
            theta_i=0.85,
            theta_a=0.85,
            q_by_occurrence={"T1110.001@DC01": 0.6, "T1003@DC01": 0.65},
            impact_by_occurrence={"T1110.001@DC01": 0.4, "T1003@DC01": 0.61},
            annotation_set_version="test-real-catalog-v1",
            output_root=tmp_path / "runs",
        )

        assert result["run_manifest"]["status"] == "completed"
        # Réf. docstring de classe : D3-DUC active par l'organisation avec
        # des prerequis satisfaits par l'instance -> candidat reellement
        # admissible, plan de deploiement non vide.
        assert result["admissibility_report"]["occurrences"]["T1110.001@DC01"]["D_i"] == ["D3-DUC"]
        assert result["admissibility_report"]["summary"]["admissible_count"] == 1
        assert len(result["deployment_plan"]) == 1
        assert result["deployment_plan"][0]["mechanism_id"] == "D3-DUC"
