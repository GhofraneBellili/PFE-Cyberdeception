"""
Réf. tâche « campagne d'évaluation réelle RAG/LLM/système » §4/§8 : tests
unitaires de `tools/chapter4_evaluation/llm_evaluation.py` — utilise le
MÊME patron de double de test que `tests/test_annotator_llm.py`
(`RealLlmAnnotator` réel avec un `transport` injecté déterministe, JAMAIS
un appel réseau réel), pour vérifier la logique de conformité/ancrage/
stabilité SANS dépendre d'un provider LLM réellement disponible.
"""

import json as _json

from src.annotation_validator import ELEVEN_METRICS
from src.annotator_llm import RealLlmAnnotator
from src.llm_provider import LlmProviderConfig
from src.schemas import AnnotationContext, AttackOccurrenceRef, DeceptionEvidence, DeceptionRef, GraphContext, NodeAttributes
from tools.chapter4_evaluation.llm_evaluation import (
    _attempt_raw_annotation,
    _extract_raw_evidence_citations,
    run_conformity_and_grounding,
    run_stability,
)
from tools.chapter4_evaluation.llm_fixed_candidates import FixedCandidate


def make_context(evidence_ids=("chunk_0", "chunk_1")):
    attributes = NodeAttributes(
        tactics=["credential-access"], outcomes=[], q_local_success=0.7,
        impact_confidentiality=0.6, impact_integrity=0.2, impact_availability=0.1,
        critical_asset=False, accessible_asset=True,
    )
    return AnnotationContext(
        attack_occurrence=AttackOccurrenceRef(technique_id="T1003", asset_id="DC01", attributes=attributes),
        deception=DeceptionRef(id="D3-DUC", name="Decoy User Credential"),
        placement="auth-store",
        graph_context=GraphContext(),
        system_context={},
        retrieved_evidence=[DeceptionEvidence(source=cid, passage=f"passage {cid}") for cid in evidence_ids],
    )


def valid_payload(evidence_ids=("chunk_0",)):
    return {
        "annotations": [
            {"metric": metric, "score": 0.5, "confidence": 0.8, "justification": f"justification {metric}", "evidence_ids": list(evidence_ids)}
            for metric in ELEVEN_METRICS
        ]
    }


def openai_config(**overrides):
    defaults = dict(provider="openai_compatible", model="test-model", base_url="https://example.invalid/v1", max_retries=0)
    defaults.update(overrides)
    return LlmProviderConfig(**defaults)


def openai_transport(response_body: dict):
    def transport(url, payload, headers, timeout):
        return {"choices": [{"message": {"content": _json.dumps(response_body)}}]}
    return transport


class TestExtractRawEvidenceCitations:
    def test_extracts_all_citations_across_metrics(self):
        raw = _json.dumps(valid_payload(evidence_ids=("chunk_0", "chunk_1")))
        citations = _extract_raw_evidence_citations(raw)
        assert len(citations) == len(ELEVEN_METRICS) * 2
        assert set(citations) == {"chunk_0", "chunk_1"}

    def test_returns_empty_list_for_malformed_json(self):
        assert _extract_raw_evidence_citations("not json") == []

    def test_returns_empty_list_for_none(self):
        assert _extract_raw_evidence_citations(None) == []

    def test_returns_empty_list_when_annotations_key_missing(self):
        assert _extract_raw_evidence_citations(_json.dumps({"foo": "bar"})) == []


class TestAttemptRawAnnotation:
    def test_conforme_true_for_valid_payload(self):
        context = make_context()
        annotator = RealLlmAnnotator(config=openai_config(), transport=openai_transport(valid_payload(("chunk_0",))))
        result = _attempt_raw_annotation(annotator, context)
        assert result["ok"] is True
        assert len(result["annotations"]) == len(ELEVEN_METRICS)
        assert result["elapsed_seconds"] >= 0.0

    def test_conforme_false_when_evidence_id_unknown(self):
        context = make_context(evidence_ids=("chunk_0",))
        annotator = RealLlmAnnotator(config=openai_config(), transport=openai_transport(valid_payload(("chunk_999",))))
        result = _attempt_raw_annotation(annotator, context)
        assert result["ok"] is False
        assert "validation_error" in result["error"]

    def test_conforme_false_when_metric_missing(self):
        context = make_context()
        payload = valid_payload()
        payload["annotations"] = payload["annotations"][:-1]  # une sous-metrique manquante
        annotator = RealLlmAnnotator(config=openai_config(), transport=openai_transport(payload))
        result = _attempt_raw_annotation(annotator, context)
        assert result["ok"] is False


class TestRunConformityAndGrounding:
    def test_fully_conforme_and_grounded(self):
        context = make_context(evidence_ids=("chunk_0", "chunk_1"))
        candidate = FixedCandidate(occurrence_id="T1003@DC01", mechanism_id="D3-DUC", location_id="auth-store", context=context)
        annotator = RealLlmAnnotator(config=openai_config(), transport=openai_transport(valid_payload(("chunk_0",))))

        conformity, grounding = run_conformity_and_grounding(annotator, [candidate])

        assert conformity["conformity_rate"] == 1.0
        assert conformity["conforme_count"] == 1
        assert grounding["grounding_rate"] == 1.0
        assert grounding["invalid_evidence_ids"] == []

    def test_invalid_evidence_id_counted_and_listed_not_hidden(self):
        context = make_context(evidence_ids=("chunk_0",))
        candidate = FixedCandidate(occurrence_id="T1003@DC01", mechanism_id="D3-DUC", location_id="auth-store", context=context)
        annotator = RealLlmAnnotator(config=openai_config(), transport=openai_transport(valid_payload(("chunk_ghost",))))

        conformity, grounding = run_conformity_and_grounding(annotator, [candidate])

        assert conformity["conformity_rate"] == 0.0
        assert "chunk_ghost" in grounding["invalid_evidence_ids"]
        assert grounding["grounding_rate"] == 0.0


class TestRunStability:
    def test_zero_stdev_when_transport_is_deterministic(self):
        context = make_context(evidence_ids=("chunk_0",))
        candidate = FixedCandidate(occurrence_id="T1003@DC01", mechanism_id="D3-DUC", location_id="auth-store", context=context)
        annotator = RealLlmAnnotator(config=openai_config(max_retries=0), transport=openai_transport(valid_payload(("chunk_0",))))

        stability = run_stability(annotator, [candidate], k=3)

        entry = stability["per_candidate"][0]
        assert entry["replay_count"] == 3
        assert entry["DE_stdev"] == 0.0
        assert stability["mean_DE_stdev"] == 0.0
