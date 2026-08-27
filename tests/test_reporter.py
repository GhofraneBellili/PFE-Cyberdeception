"""
Réf. architecture : CLAUDE.md §17.6 (Reporter) — contrat technique du PFE
Cyberdéception.

Tests unitaires de src/reporter.py (§25.4 : pytest obligatoire).
"""

import pytest

from src.reporter import ReporterError, build_deployment_report, render_text_report


def sample_plan():
    return [{"occurrence_id": "T1078@DC01", "mechanism_id": "D3-DUC", "location_id": "auth-store", "DE": 0.42, "Cost": 4039.2}]


class TestBuildDeploymentReport:
    def test_row_carries_all_fields(self):
        rows = build_deployment_report(
            sample_plan(),
            risks_before={"T1078@DC01": 0.30},
            risks_after={"T1078@DC01": 0.18},
        )
        assert len(rows) == 1
        row = rows[0]
        assert row.occurrence_id == "T1078@DC01"
        assert row.mechanism_id == "D3-DUC"
        assert row.location_id == "auth-store"
        assert row.cost == pytest.approx(4039.2)
        assert row.de == pytest.approx(0.42)
        assert row.risk_before == pytest.approx(0.30)
        assert row.risk_after == pytest.approx(0.18)
        assert row.risk_variation == pytest.approx(-0.12)
        assert row.risk_variation_relative == pytest.approx(-0.4)

    def test_empty_plan_yields_empty_report(self):
        rows = build_deployment_report([], risks_before={}, risks_after={})
        assert rows == []

    def test_missing_risk_before_raises(self):
        with pytest.raises(ReporterError):
            build_deployment_report(sample_plan(), risks_before={}, risks_after={"T1078@DC01": 0.18})

    def test_missing_risk_after_raises(self):
        with pytest.raises(ReporterError):
            build_deployment_report(sample_plan(), risks_before={"T1078@DC01": 0.30}, risks_after={})

    def test_zero_risk_before_yields_no_relative_variation(self):
        rows = build_deployment_report(
            sample_plan(), risks_before={"T1078@DC01": 0.0}, risks_after={"T1078@DC01": 0.0}
        )
        assert rows[0].risk_variation_relative is None

    def test_evidence_ids_joined_from_frozen_table(self):
        from datetime import datetime, timezone

        from src.annotation_validator import freeze_table
        from src.schemas import Annotation

        annotations = [
            Annotation(
                metric=metric,
                score=0.5,
                justification="j",
                evidence=["chunk_a", "chunk_b"],
                confidence=0.8,
                model_version="rule_based_stub",
                prompt_version="v1",
                annotated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                annotation_id=f"raw:{metric}",
            )
            for metric in (
                "R_tech", "R_context", "R_perception", "R_behavior",
                "A_object", "A_action", "A_source",
                "S_stop", "S_redirect", "S_contain", "S_delay",
            )
        ]
        table = freeze_table(
            [("T1078@DC01", "D3-DUC", "auth-store", annotations)], annotation_set_version="v1"
        )
        rows = build_deployment_report(
            sample_plan(), risks_before={"T1078@DC01": 0.30}, risks_after={"T1078@DC01": 0.18}, frozen_table=table
        )
        assert rows[0].evidence_ids == ("chunk_a", "chunk_b")

    def test_no_matching_frozen_entry_yields_empty_evidence(self):
        from src.annotation_validator import freeze_table

        table = freeze_table([], annotation_set_version="v1")
        rows = build_deployment_report(
            sample_plan(), risks_before={"T1078@DC01": 0.30}, risks_after={"T1078@DC01": 0.18}, frozen_table=table
        )
        assert rows[0].evidence_ids == ()


class TestRenderTextReport:
    def test_empty_rows_message(self):
        assert "vide" in render_text_report([]).lower()

    def test_nonempty_rows_include_occurrence_and_mechanism(self):
        rows = build_deployment_report(
            sample_plan(), risks_before={"T1078@DC01": 0.30}, risks_after={"T1078@DC01": 0.18}
        )
        text = render_text_report(rows)
        assert "T1078@DC01" in text
        assert "D3-DUC" in text


class TestLlmOutOfExecutionPath:
    def test_reporter_does_not_import_llm_or_rag(self):
        import ast
        from pathlib import Path

        import src.reporter as module

        source = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
        forbidden = {
            "src.annotator_llm",
            "src.rag_indexer",
            "src.rag_retriever",
            "src.semantic_embedder",
            "src.vector_index",
        }
        assert not (imported_modules & forbidden)
