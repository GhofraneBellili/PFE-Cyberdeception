"""
Réf. architecture : CLAUDE.md §19 (Workflow complet d'exécution) et
section « Orchestrateur » de la tâche d'implémentation du chapitre 4.
Réf. tâche « maturation technique finale du chapitre 4 » §2/§3/§18/§19 :
`run_pipeline` utilise désormais EXCLUSIVEMENT le RAG contextuel par
candidat (`RagCandidateContext` -> 3 requêtes par famille ->
`CandidateEvidenceBundle` -> `evidence_by_family`) — plus l'ancien chemin
à requête unique.

Tests unitaires de src/orchestrator.py (§25.4 : pytest obligatoire).
`DeterministicFakeReranker` est utilisé partout ici — aucun modèle réel
n'est téléchargé pendant `pytest` (réf. tâche §36).
"""

import json
from pathlib import Path

import pytest

from src.annotator_llm import RuleBasedStubAnnotator
from src.orchestrator import OrchestratorError, run_pipeline
from src.rag_indexer import Chunk, build_index, build_semantic_index
from src.reranker import DeterministicFakeReranker
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
        target_artifacts=["credential"],
        interaction_mechanism="attacker uses the decoy credential to authenticate",
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
    """Réf. tâche §19 : contenu volontairement différencié par thème
    (réalisme du leurre / interaction attaquant / effet défensif) pour
    que le test « trois familles réellement utilisées » ait un signal à
    vérifier, pas seulement une structure vide."""
    return [
        Chunk(
            chunk_id="c-realism",
            source_id="s1",
            source_type="literature",
            document_id="d1",
            locator="l",
            text="A decoy user credential is technically plausible when placed in a domain controller credential store.",
            text_hash="hash1",
        ),
        Chunk(
            chunk_id="c-interaction",
            source_id="s2",
            source_type="d3fend",
            document_id="d2",
            locator="l",
            text="The attacker uses the decoy credential to authenticate, interacting with a fake account object.",
            text_hash="hash2",
        ),
        Chunk(
            chunk_id="c-effect",
            source_id="s3",
            source_type="engage",
            document_id="d3",
            locator="l",
            text="Using the decoy credential redirects and contains the adversary progression toward the domain controller.",
            text_hash="hash3",
        ),
    ]


def make_rag_index() -> object:
    return build_index(make_rag_chunks())


class FakeEmbedder:
    """Embedder déterministe factice — aucune dépendance réseau pendant
    `pytest` (réf. tâche §36)."""

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


def make_reranker() -> DeterministicFakeReranker:
    return DeterministicFakeReranker()


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
        lexical_index=make_rag_index(),
        semantic_index=make_semantic_rag_index(),
        reranker=make_reranker(),
        rag_embedder=FakeEmbedder(),
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
            "candidate_contexts.json",
            "rag_queries.json",
            "evidence_bundles.json",
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


class TestRunPipelineContextualRag:
    """Réf. tâche « maturation technique finale du chapitre 4 » §2/§3/§18/
    §19 : `run_pipeline` utilise EXCLUSIVEMENT le pipeline RAG contextuel
    (RagCandidateContext -> 3 requêtes -> CandidateEvidenceBundle ->
    evidence_by_family) — plus aucun autre chemin RAG."""

    def test_input_manifest_reports_contextual_pipeline(self, tmp_path):
        result = run_pipeline(**run_kwargs("run-rag-001", tmp_path))
        rag_info = result["input_manifest"]["rag"]
        assert rag_info["pipeline"] == "contextual_sp2"
        assert rag_info["corpus_chunk_count"] == 3
        assert rag_info["embedding_model"] == "fake-embedder-test-v1"
        assert rag_info["reranker_model"] == "deterministic-fake-reranker-test-double"

    def test_candidate_contexts_file_indexed_by_candidate_id(self, tmp_path):
        result = run_pipeline(**run_kwargs("run-rag-002", tmp_path))
        payload = json.loads((result["run_dir"] / "candidate_contexts.json").read_text(encoding="utf-8"))
        assert payload  # au moins un candidat admissible
        for candidate_id, context in payload.items():
            assert "|" in candidate_id
            assert context["mechanism_id"] == "D3-DUC"
            assert "occurrence_id" in context

    def test_rag_queries_file_has_three_distinct_queries_per_candidate(self, tmp_path):
        result = run_pipeline(**run_kwargs("run-rag-003", tmp_path))
        payload = json.loads((result["run_dir"] / "rag_queries.json").read_text(encoding="utf-8"))
        assert payload
        for candidate_id, queries in payload.items():
            assert set(queries.keys()) == {"realism", "interaction", "effect"}
            assert len({queries["realism"], queries["interaction"], queries["effect"]}) == 3

    def test_evidence_bundles_file_has_three_families_with_evidence(self, tmp_path):
        result = run_pipeline(**run_kwargs("run-rag-004", tmp_path))
        payload = json.loads((result["run_dir"] / "evidence_bundles.json").read_text(encoding="utf-8"))
        assert payload
        for candidate_id, bundle in payload.items():
            assert set(bundle["families"].keys()) == {"realism", "interaction", "effect"}
            for family in bundle["families"].values():
                assert family["evidence"]  # au moins une preuve par famille
                for item in family["evidence"]:
                    assert {
                        "chunk_id", "source_type", "source_id", "text", "final_rank",
                        "semantic_score", "lexical_score", "hybrid_score", "reranker_score",
                        "metadata", "provenance",
                    } <= set(item.keys())


class TestThreeFamiliesGenuinelyUsed:
    """Réf. tâche §19 : le pipeline principal NE reconvertit PAS les
    preuves en un unique bloc générique — realism evidence va aux
    métriques realism, interaction evidence aux métriques interaction,
    effect evidence aux métriques effect (vérifié via
    AnnotationContext.evidence_by_family, effectivement transmis à
    l'annotateur)."""

    def test_annotation_context_receives_evidence_by_family(self, tmp_path):
        captured_contexts = []

        class CapturingAnnotator(RuleBasedStubAnnotator):
            def annotate(self, context, *, now=None):
                captured_contexts.append(context)
                return super().annotate(context, now=now)

        kwargs = run_kwargs("run-families-001", tmp_path)
        kwargs["annotator"] = CapturingAnnotator()
        # Réf. §19 : corpus de test volontairement minuscule (3 chunks) —
        # sans restreindre le top-k final, les 3 chunks seraient retenus
        # identiquement par les trois familles (aucune marge de tri).
        # final_top_k=1 force chaque famille à retenir son chunk le plus
        # pertinent au sens du reranker déterministe (chevauchement
        # lexical avec sa propre requête), donc à réellement diverger.
        kwargs["final_top_k"] = 1
        run_pipeline(**kwargs)

        assert captured_contexts
        for context in captured_contexts:
            assert context.evidence_by_family is not None
            assert set(context.evidence_by_family.keys()) == {"realism", "interaction", "effect"}
            # Réf. §19 : les trois familles ne référencent pas exactement le
            # même ensemble de sources — sinon ce serait un bloc générique
            # unique déguisé en trois familles.
            families_evidence_sets = [frozenset(sources) for sources in context.evidence_by_family.values()]
            assert len(set(families_evidence_sets)) > 1


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


class TestRunManifestTraceability:
    """Réf. tâche §14 : run_manifest.json porte les métadonnées RAG/LLM/
    catalogue fournies par l'appelant — jamais de secret/clé API."""

    def test_optional_traceability_fields_included_when_provided(self, tmp_path):
        kwargs = run_kwargs("run-trace-001", tmp_path)
        kwargs["rag_index_manifest"] = {"corpus_version": "test-corpus-1.0", "corpus_hash": "deadbeef"}
        kwargs["deception_catalog_version"] = "catalog-2.0"
        kwargs["organization_catalog_version"] = "org-1.0"
        kwargs["mapping_version"] = "mapping-2.0"
        kwargs["llm_provider"] = "rule_based_stub"
        kwargs["llm_model"] = "rule_based_stub"
        kwargs["prompt_version"] = "rule_based_stub-v1"
        result = run_pipeline(**kwargs)
        manifest = result["run_manifest"]
        assert manifest["rag"]["corpus_version"] == "test-corpus-1.0"
        assert manifest["rag"]["corpus_hash"] == "deadbeef"
        assert manifest["catalog"]["deception_catalog_version"] == "catalog-2.0"
        assert manifest["catalog"]["organization_catalog_version"] == "org-1.0"
        assert manifest["catalog"]["mapping_version"] == "mapping-2.0"
        assert manifest["llm"]["provider"] == "rule_based_stub"
        assert manifest["llm"]["model"] == "rule_based_stub"

    def test_no_api_key_or_secret_ever_included(self, tmp_path):
        import inspect

        signature = inspect.signature(run_pipeline)
        forbidden = {"api_key", "secret", "token"}
        assert forbidden.isdisjoint(signature.parameters.keys())

    def test_optional_traceability_fields_absent_when_not_provided(self, tmp_path):
        result = run_pipeline(**run_kwargs("run-trace-002", tmp_path))
        manifest = result["run_manifest"]
        # annotation_set_version est un paramètre OBLIGATOIRE de
        # run_pipeline (toujours connu) : il reste dans le bloc "llm" même
        # sans provider/model/prompt_version explicites.
        assert manifest["llm"] == {"annotation_set_version": "test-v1"}
        assert manifest["catalog"] == {}


# ---------------------------------------------------------------------------
# Pipeline avec le catalogue et le mapping REELS — réf. § tâche 12
# ---------------------------------------------------------------------------


class TestPipelineWithRealCatalogAndMapping:
    """Réf. tâche 12 (session précédente) + réf. tâche « separate
    knowledge and organization capabilities » (session suivante) + réf.
    tâche « maturation technique finale du chapitre 4 » (RAG contextuel).

    Charge data/deception/deception_catalog.json et
    data/deception/attack_deception_mapping.json (construits par
    tools/deception_kb/catalog_builder.py / mapping_builder.py) et fait
    tourner l'orchestrateur complet dessus, sur une instance qui n'exerce
    QUE D3-DUC (T1110.001@DC01 -> T1003@DC01). Le catalogue de
    CONNAISSANCES réel (51 mécanismes) ne fournit plus aucune donnée
    d'admissibilité (champ hérité `admissibility_profile` non consulté) :
    l'admissibilité vient exclusivement d'un catalogue OPÉRATIONNEL de
    test (`_organization_catalog`, ci-dessous), qui active D3-DUC avec des
    prérequis satisfaits par l'instance -> `C_i_h` non vide, plan de
    déploiement produit. Vérifie que le pipeline complet fonctionne de
    bout en bout avec le catalogue de connaissances réel et le RAG
    contextuel.
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
        catalogue de connaissances réel (51 mécanismes) n'influence pas
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

        chunks = make_rag_chunks()

        result = run_pipeline(
            run_id="run-real-catalog",
            instance=self._real_instance(),
            catalog=dict(kb.mechanisms_by_id),
            organization_catalog=self._organization_catalog(),
            mapping=sp1_mapping,
            lexical_index=build_index(chunks),
            semantic_index=build_semantic_index(chunks, embedder=FakeEmbedder()),
            reranker=make_reranker(),
            rag_embedder=FakeEmbedder(),
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
