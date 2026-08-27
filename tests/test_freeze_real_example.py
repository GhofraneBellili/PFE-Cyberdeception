"""
Réf. architecture : CLAUDE.md §13 — tâche « gel réel après LLM ».

Tests unitaires de examples/freeze_real_example.py (§25.4 : pytest
obligatoire). Utilise un payload synthétique au format produit par
examples/annotator_llm_real_example.py — pas un appel LLM réel.
"""

from datetime import datetime, timezone

import pytest

from examples.freeze_real_example import freeze_from_payload
from src.annotation_validator import ELEVEN_METRICS

FIXED_NOW = datetime(2026, 8, 27, tzinfo=timezone.utc).isoformat()


def make_real_llm_payload(*, scores=None):
    scores = scores or {}
    return {
        "annotation_type": "real_llm",
        "provider": "ollama",
        "model": "llama3",
        "candidate": {"occurrence_id": "T1039@FS01", "mechanism_id": "D3-DNR", "location_id": "shared-drive"},
        "retrieved_evidence": [{"source": "d3fend:D3-DNR:0", "passage": "..."}],
        "annotations": [
            {
                "metric": metric,
                "score": scores.get(metric, 0.6),
                "confidence": 0.8,
                "evidence": ["d3fend:D3-DNR:0"],
                "justification": f"justification reelle pour {metric}",
                "model_version": "llama3",
                "prompt_version": "real-llm-v1",
                "annotation_id": f"llama3:real-llm-v1:{metric}:abc123",
                "annotated_at": FIXED_NOW,
            }
            for metric in ELEVEN_METRICS
        ],
    }


class TestFreezeFromPayload:
    def test_freezes_candidate_from_real_llm_payload(self):
        frozen = freeze_from_payload(make_real_llm_payload())
        assert frozen.occurrence_id == "T1039@FS01"
        assert frozen.mechanism_id == "D3-DNR"
        assert frozen.location_id == "shared-drive"
        assert frozen.model == "llama3"
        assert frozen.DE == pytest.approx(frozen.P_engagement * frozen.Effet_prog)

    def test_aggregates_computed_by_code_not_by_llm(self):
        """Réf. §11.5 : les agrégats sont calculés à partir des scores
        bruts par annotation_validator, jamais lus tels quels depuis le
        payload LLM (qui n'en contient d'ailleurs aucun)."""
        payload = make_real_llm_payload(scores={"R_tech": 1.0, "R_context": 1.0, "R_perception": 1.0, "R_behavior": 1.0})
        frozen = freeze_from_payload(payload)
        assert frozen.Realisme == pytest.approx(1.0)

    def test_evidence_ids_preserved(self):
        frozen = freeze_from_payload(make_real_llm_payload())
        assert frozen.evidence_ids == ("d3fend:D3-DNR:0",)

    def test_missing_metric_in_payload_raises(self):
        payload = make_real_llm_payload()
        payload["annotations"] = payload["annotations"][:-1]
        with pytest.raises(Exception):
            freeze_from_payload(payload)


class TestNoFabricationWithoutRealAnnotation:
    def test_main_does_not_write_without_source_file(self, tmp_path, monkeypatch, capsys):
        import examples.freeze_real_example as module

        missing_path = tmp_path / "llm_annotation_real.json"
        monkeypatch.setattr(module, "REAL_ANNOTATION_PATH", missing_path)
        monkeypatch.setattr(module, "OUT_DIR", tmp_path)

        module.main()

        assert not (tmp_path / "frozen_annotations_real.json").exists()
        assert not (tmp_path / "frozen_annotations_real.csv").exists()
        captured = capsys.readouterr()
        assert "n'existe pas" in captured.out
