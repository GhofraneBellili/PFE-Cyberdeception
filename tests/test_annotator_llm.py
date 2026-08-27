"""
Réf. architecture : CLAUDE.md §11 (SP2 — annotation LLM+RAG) — contrat
technique du PFE Cyberdéception.

Tests unitaires de src/annotator_llm.py (§25.4 : pytest obligatoire).

`RuleBasedStubAnnotator` est un repli déterministe explicite (aucune API
LLM réelle disponible dans cet environnement, §20 anti-fabrication) : ces
tests vérifient son comportement déterministe et ses garde-fous, pas la
qualité sémantique d'une vraie annotation LLM.
"""

from datetime import datetime, timezone

import pytest

from src.annotator_llm import (
    ELEVEN_METRICS,
    AnnotationCache,
    AnnotatorLlmError,
    RuleBasedStubAnnotator,
    annotate_with_cache,
    deterministic_annotation_id,
)
from src.schemas import (
    AttackOccurrenceRef,
    DeceptionEvidence,
    DeceptionRef,
    GraphContext,
    NodeAttributes,
    AnnotationContext,
)

FIXED_NOW = datetime(2026, 8, 27, tzinfo=timezone.utc)


def make_context(*, evidence_passages=("Decoy User Credential is a credential created to deceive an adversary.",)):
    attributes = NodeAttributes(
        tactics=["credential-access"],
        outcomes=[],
        q_local_success=0.7,
        impact_confidentiality=0.6,
        impact_integrity=0.2,
        impact_availability=0.1,
        critical_asset=False,
        accessible_asset=True,
    )
    return AnnotationContext(
        attack_occurrence=AttackOccurrenceRef(technique_id="T1003", asset_id="DC01", attributes=attributes),
        deception=DeceptionRef(id="D3-DUC", name="Decoy User Credential"),
        placement="auth-store",
        graph_context=GraphContext(),
        system_context={},
        retrieved_evidence=[
            DeceptionEvidence(source=f"chunk_{i}", passage=passage) for i, passage in enumerate(evidence_passages)
        ],
    )


# ---------------------------------------------------------------------------
# A. RuleBasedStubAnnotator — garde-fous et déterminisme
# ---------------------------------------------------------------------------


class TestRuleBasedStubAnnotator:
    def test_produces_exactly_eleven_annotations(self):
        annotator = RuleBasedStubAnnotator()
        annotations = annotator.annotate(make_context(), now=FIXED_NOW)
        assert len(annotations) == 11
        assert {a.metric for a in annotations} == set(ELEVEN_METRICS)

    def test_model_version_marked_as_stub(self):
        annotator = RuleBasedStubAnnotator()
        annotations = annotator.annotate(make_context(), now=FIXED_NOW)
        assert all(a.model_version == "rule_based_stub" for a in annotations)

    def test_no_evidence_raises(self):
        context = make_context(evidence_passages=())
        annotator = RuleBasedStubAnnotator()
        with pytest.raises(AnnotatorLlmError):
            annotator.annotate(context, now=FIXED_NOW)

    def test_deterministic_for_identical_context(self):
        annotator = RuleBasedStubAnnotator()
        context = make_context()
        annotations_1 = annotator.annotate(context, now=FIXED_NOW)
        annotations_2 = annotator.annotate(context, now=FIXED_NOW)
        assert [a.model_dump() for a in annotations_1] == [a.model_dump() for a in annotations_2]

    def test_higher_lexical_overlap_yields_higher_score(self):
        annotator = RuleBasedStubAnnotator()
        relevant_context = make_context(
            evidence_passages=("T1003 credential-access Decoy User Credential auth-store",)
        )
        irrelevant_context = make_context(evidence_passages=("apples oranges bananas fruit salad",))
        relevant_score = annotator.annotate(relevant_context, now=FIXED_NOW)[0].score
        irrelevant_score = annotator.annotate(irrelevant_context, now=FIXED_NOW)[0].score
        assert relevant_score > irrelevant_score

    def test_more_evidence_yields_higher_confidence(self):
        annotator = RuleBasedStubAnnotator(evidence_saturation=3)
        one_evidence = make_context(evidence_passages=("decoy credential",))
        three_evidence = make_context(evidence_passages=("decoy credential", "another passage", "a third one"))
        confidence_one = annotator.annotate(one_evidence, now=FIXED_NOW)[0].confidence
        confidence_three = annotator.annotate(three_evidence, now=FIXED_NOW)[0].confidence
        assert confidence_three > confidence_one

    def test_evidence_ids_match_context_sources(self):
        context = make_context()
        annotator = RuleBasedStubAnnotator()
        annotations = annotator.annotate(context, now=FIXED_NOW)
        assert annotations[0].evidence == [item.source for item in context.retrieved_evidence]

    def test_scores_and_confidence_within_unit_interval(self):
        annotator = RuleBasedStubAnnotator()
        annotations = annotator.annotate(make_context(), now=FIXED_NOW)
        assert all(0.0 <= a.score <= 1.0 for a in annotations)
        assert all(0.0 <= a.confidence <= 1.0 for a in annotations)


# ---------------------------------------------------------------------------
# B. Identifiant déterministe
# ---------------------------------------------------------------------------


class TestDeterministicAnnotationId:
    def test_same_context_same_id(self):
        context = make_context()
        id_1 = deterministic_annotation_id(context, metric="R_tech", model_version="rule_based_stub", prompt_version="v1")
        id_2 = deterministic_annotation_id(context, metric="R_tech", model_version="rule_based_stub", prompt_version="v1")
        assert id_1 == id_2

    def test_different_metric_different_id(self):
        context = make_context()
        id_r_tech = deterministic_annotation_id(context, metric="R_tech", model_version="m", prompt_version="v1")
        id_s_stop = deterministic_annotation_id(context, metric="S_stop", model_version="m", prompt_version="v1")
        assert id_r_tech != id_s_stop


# ---------------------------------------------------------------------------
# C. Cache — réf. reproductibilité LLM (rejeu sans ré-appel)
# ---------------------------------------------------------------------------


class _CountingProvider:
    def __init__(self, annotator: RuleBasedStubAnnotator):
        self._annotator = annotator
        self.call_count = 0

    def annotate(self, context, *, now=None):
        self.call_count += 1
        return self._annotator.annotate(context, now=now)


class TestAnnotationCache:
    def test_second_call_with_identical_context_replays_cache(self):
        provider = _CountingProvider(RuleBasedStubAnnotator())
        cache = AnnotationCache()
        context = make_context()

        first = annotate_with_cache(provider, context, cache, model_version="rule_based_stub", prompt_version="v1", now=FIXED_NOW)
        second = annotate_with_cache(provider, context, cache, model_version="rule_based_stub", prompt_version="v1", now=FIXED_NOW)

        assert provider.call_count == 1
        assert [a.model_dump() for a in first] == [a.model_dump() for a in second]

    def test_different_context_triggers_new_call(self):
        provider = _CountingProvider(RuleBasedStubAnnotator())
        cache = AnnotationCache()

        annotate_with_cache(provider, make_context(), cache, model_version="rule_based_stub", prompt_version="v1", now=FIXED_NOW)
        annotate_with_cache(
            provider,
            make_context(evidence_passages=("a completely different passage",)),
            cache,
            model_version="rule_based_stub",
            prompt_version="v1",
            now=FIXED_NOW,
        )
        assert provider.call_count == 2
        assert len(cache) == 2


# ---------------------------------------------------------------------------
# D. Invariant — le LLM/stub ne calcule jamais les agrégats SP2
# ---------------------------------------------------------------------------


class TestNeverComputesAggregates:
    def test_module_does_not_import_risk_engine_or_optimizer(self):
        import ast
        from pathlib import Path

        import src.annotator_llm as module

        source = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
        assert not (imported_modules & {"src.risk_engine", "src.optimizer"})
