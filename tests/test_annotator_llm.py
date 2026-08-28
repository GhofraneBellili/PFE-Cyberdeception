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
    LlmOutputValidationError,
    RealLlmAnnotator,
    RuleBasedStubAnnotator,
    _build_evidence_block,
    _build_prompt,
    annotate_with_cache,
    detect_provider,
    deterministic_annotation_id,
)
from src.llm_provider import LlmProviderConfig, LlmProviderError
from src.schemas import (
    AttackOccurrenceRef,
    DeceptionEvidence,
    DeceptionRef,
    GraphContext,
    NodeAttributes,
    AnnotationContext,
)

FIXED_NOW = datetime(2026, 8, 27, tzinfo=timezone.utc)


def make_context(
    *,
    evidence_passages=("Decoy User Credential is a credential created to deceive an adversary.",),
    evidence_by_family=None,
):
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
        evidence_by_family=evidence_by_family,
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


# ---------------------------------------------------------------------------
# E. RealLlmAnnotator — réf. § tâche « intégrer un véritable provider LLM »
#
# AUCUN de ces tests n'appelle un service réel (§ tâche 12) : le transport
# HTTP est toujours une fonction mock déterministe injectée.
# ---------------------------------------------------------------------------

import json as _json  # noqa: E402 (import local, groupe de tests dédié)


def _valid_llm_payload(evidence_ids=("chunk_0",)):
    return {
        "annotations": [
            {
                "metric": metric,
                "score": 0.5,
                "confidence": 0.8,
                "justification": f"justification reelle pour {metric}",
                "evidence_ids": list(evidence_ids),
            }
            for metric in ELEVEN_METRICS
        ]
    }


def ollama_transport(response_body: dict):
    def transport(url, payload, headers, timeout):
        return {"message": {"content": _json.dumps(response_body)}}

    return transport


def failing_then_succeeding_transport(response_body: dict, *, fail_times: int):
    calls = {"count": 0}

    def transport(url, payload, headers, timeout):
        calls["count"] += 1
        if calls["count"] <= fail_times:
            raise LlmProviderError("erreur transitoire simulee")
        return {"message": {"content": _json.dumps(response_body)}}

    transport.calls = calls
    return transport


def ollama_config(**overrides):
    defaults = dict(provider="ollama", model="llama3", base_url="http://localhost:11434", max_retries=1)
    defaults.update(overrides)
    return LlmProviderConfig(**defaults)


class TestBuildPromptFamilyGrouping:
    """Réf. tâche « renforcer le RAG utilisé par SP2 », §14 : le prompt
    regroupe les preuves par famille de sous-métriques quand
    `evidence_by_family` est fourni, avec repli rétrocompatible (bloc plat
    historique) sinon."""

    def test_flat_block_when_no_evidence_by_family(self):
        context = make_context(evidence_passages=("Passage A.", "Passage B."))
        block = _build_evidence_block(context)
        assert "chunk_0" in block
        assert "chunk_1" in block
        assert "REALISM EVIDENCE" not in block

    def test_grouped_block_when_evidence_by_family_provided(self):
        context = make_context(
            evidence_passages=("Realism passage.", "Interaction passage.", "Effect passage."),
            evidence_by_family={"realism": ["chunk_0"], "interaction": ["chunk_1"], "effect": ["chunk_2"]},
        )
        block = _build_evidence_block(context)
        assert "REALISM EVIDENCE" in block
        assert "INTERACTION EVIDENCE" in block
        assert "PROGRESSION-EFFECT EVIDENCE" in block

    def test_realism_evidence_appears_only_once_not_duplicated_across_families(self):
        context = make_context(
            evidence_passages=("Realism passage.", "Interaction passage."),
            evidence_by_family={"realism": ["chunk_0"], "interaction": ["chunk_1"], "effect": []},
        )
        block = _build_evidence_block(context)
        assert block.count("Realism passage.") == 1
        assert block.count("Interaction passage.") == 1

    def test_empty_family_omitted_from_block(self):
        context = make_context(
            evidence_passages=("Realism passage.",),
            evidence_by_family={"realism": ["chunk_0"], "interaction": [], "effect": []},
        )
        block = _build_evidence_block(context)
        assert "INTERACTION EVIDENCE" not in block
        assert "PROGRESSION-EFFECT EVIDENCE" not in block

    def test_full_prompt_still_lists_all_evidence_ids(self):
        context = make_context(
            evidence_passages=("Realism passage.", "Interaction passage."),
            evidence_by_family={"realism": ["chunk_0"], "interaction": ["chunk_1"], "effect": []},
        )
        prompt = _build_prompt(context)
        assert "chunk_0" in prompt
        assert "chunk_1" in prompt

    def test_rule_based_stub_still_works_without_evidence_by_family(self):
        """Réf. rétrocompatibilité : RuleBasedStubAnnotator ne fournit
        jamais evidence_by_family — doit rester inchangé."""
        context = make_context(evidence_by_family=None)
        annotations = RuleBasedStubAnnotator().annotate(context, now=FIXED_NOW)
        assert len(annotations) == 11


class TestRealLlmAnnotator:
    def test_valid_response_produces_eleven_annotations(self):
        annotator = RealLlmAnnotator(config=ollama_config(), transport=ollama_transport(_valid_llm_payload()))
        annotations = annotator.annotate(make_context(), now=FIXED_NOW)
        assert len(annotations) == 11
        assert {a.metric for a in annotations} == set(ELEVEN_METRICS)
        assert all(a.model_version == "llama3" for a in annotations)

    def test_no_evidence_raises_before_calling_transport(self):
        called = {"count": 0}

        def transport(url, payload, headers, timeout):
            called["count"] += 1
            return {"message": {"content": _json.dumps(_valid_llm_payload())}}

        annotator = RealLlmAnnotator(config=ollama_config(), transport=transport)
        with pytest.raises(AnnotatorLlmError):
            annotator.annotate(make_context(evidence_passages=()), now=FIXED_NOW)
        assert called["count"] == 0

    def test_missing_metric_rejected(self):
        payload = _valid_llm_payload()
        payload["annotations"] = payload["annotations"][:-1]  # retire S_delay
        annotator = RealLlmAnnotator(config=ollama_config(max_retries=0), transport=ollama_transport(payload))
        with pytest.raises(LlmProviderError):
            annotator.annotate(make_context(), now=FIXED_NOW)

    def test_duplicate_metric_rejected(self):
        payload = _valid_llm_payload()
        payload["annotations"].append(dict(payload["annotations"][0]))
        annotator = RealLlmAnnotator(config=ollama_config(max_retries=0), transport=ollama_transport(payload))
        with pytest.raises(LlmProviderError):
            annotator.annotate(make_context(), now=FIXED_NOW)

    def test_out_of_bounds_score_rejected(self):
        payload = _valid_llm_payload()
        payload["annotations"][0]["score"] = 1.5
        annotator = RealLlmAnnotator(config=ollama_config(max_retries=0), transport=ollama_transport(payload))
        with pytest.raises(LlmProviderError):
            annotator.annotate(make_context(), now=FIXED_NOW)

    def test_unknown_evidence_id_rejected(self):
        payload = _valid_llm_payload(evidence_ids=("chunk_that_does_not_exist",))
        annotator = RealLlmAnnotator(config=ollama_config(max_retries=0), transport=ollama_transport(payload))
        with pytest.raises(LlmProviderError):
            annotator.annotate(make_context(), now=FIXED_NOW)

    def test_malformed_json_rejected(self):
        def transport(url, payload, headers, timeout):
            return {"message": {"content": "not valid json {"}}

        annotator = RealLlmAnnotator(config=ollama_config(max_retries=0), transport=transport)
        with pytest.raises(LlmProviderError):
            annotator.annotate(make_context(), now=FIXED_NOW)

    def test_missing_annotations_key_rejected(self):
        def transport(url, payload, headers, timeout):
            return {"message": {"content": _json.dumps({"wrong_key": []})}}

        annotator = RealLlmAnnotator(config=ollama_config(max_retries=0), transport=transport)
        with pytest.raises(LlmProviderError):
            annotator.annotate(make_context(), now=FIXED_NOW)

    def test_never_invents_a_replacement_value(self):
        """Réf. § tâche 1 : une sortie invalide est REJETEE, jamais
        remplacee silencieusement -- l'exception doit porter l'erreur
        de validation reelle, pas un resultat de repli deguise."""
        payload = _valid_llm_payload()
        payload["annotations"][0]["evidence_ids"] = []
        annotator = RealLlmAnnotator(config=ollama_config(max_retries=0), transport=ollama_transport(payload))
        with pytest.raises(LlmProviderError) as exc_info:
            annotator.annotate(make_context(), now=FIXED_NOW)
        assert "evidence_ids" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, LlmOutputValidationError)

    def test_transient_error_retried_then_succeeds(self):
        transport = failing_then_succeeding_transport(_valid_llm_payload(), fail_times=1)
        annotator = RealLlmAnnotator(config=ollama_config(max_retries=2), transport=transport)
        annotations = annotator.annotate(make_context(), now=FIXED_NOW)
        assert len(annotations) == 11
        assert transport.calls["count"] == 2

    def test_retries_exhausted_raises(self):
        transport = failing_then_succeeding_transport(_valid_llm_payload(), fail_times=99)
        annotator = RealLlmAnnotator(config=ollama_config(max_retries=1), transport=transport)
        with pytest.raises(LlmProviderError):
            annotator.annotate(make_context(), now=FIXED_NOW)
        assert transport.calls["count"] == 2  # 1 tentative initiale + 1 retry

    def test_openai_compatible_provider_uses_choices_shape(self):
        config = LlmProviderConfig(provider="openai_compatible", model="gpt-x", base_url="https://api.example.com", max_retries=0)

        def transport(url, payload, headers, timeout):
            return {"choices": [{"message": {"content": _json.dumps(_valid_llm_payload())}}]}

        annotator = RealLlmAnnotator(config=config, transport=transport)
        annotations = annotator.annotate(make_context(), now=FIXED_NOW)
        assert len(annotations) == 11
        assert all(a.model_version == "gpt-x" for a in annotations)

    def test_never_calls_a_real_network_service(self, monkeypatch):
        """Garde-fou explicite : si le code appelait jamais
        urllib.request.urlopen malgre le transport injecte, ce test
        echouerait -- verifie que le transport mock est bien exclusif."""
        import urllib.request

        def forbidden(*args, **kwargs):
            raise AssertionError("Aucun appel reseau reel ne doit avoir lieu pendant les tests (§ tache 12).")

        monkeypatch.setattr(urllib.request, "urlopen", forbidden)
        annotator = RealLlmAnnotator(config=ollama_config(), transport=ollama_transport(_valid_llm_payload()))
        annotations = annotator.annotate(make_context(), now=FIXED_NOW)
        assert len(annotations) == 11


# ---------------------------------------------------------------------------
# F. detect_provider — réf. § tâche 2 (CAS A/B/C)
# ---------------------------------------------------------------------------


class TestDetectProvider:
    def test_cas_c_no_configuration_falls_back_to_stub(self):
        result = detect_provider({})
        assert result.annotation_type == "rule_based_stub"
        assert isinstance(result.provider, RuleBasedStubAnnotator)

    def test_cas_b_openai_compatible_configured_selects_real_provider(self):
        result = detect_provider(
            {"LLM_PROVIDER": "openai_compatible", "LLM_MODEL": "gpt-x", "LLM_BASE_URL": "https://api.example.com"}
        )
        assert result.annotation_type == "real_llm"
        assert isinstance(result.provider, RealLlmAnnotator)
        assert result.details["model"] == "gpt-x"

    def test_cas_a_ollama_model_available_selects_real_provider(self):
        result = detect_provider(
            {"LLM_PROVIDER": "ollama", "LLM_MODEL": "llama3"},
            list_ollama_models=lambda base_url, timeout: ["llama3", "mistral"],
        )
        assert result.annotation_type == "real_llm"
        assert result.details["model"] == "llama3"

    def test_cas_a_ollama_model_not_available_falls_back_to_stub(self):
        result = detect_provider(
            {"LLM_PROVIDER": "ollama", "LLM_MODEL": "nonexistent-model"},
            list_ollama_models=lambda base_url, timeout: ["llama3"],
        )
        assert result.annotation_type == "rule_based_stub"
        assert "nonexistent-model" in result.reason

    def test_cas_a_ollama_no_model_specified_picks_first_available(self):
        result = detect_provider(
            {"LLM_PROVIDER": "ollama"},
            list_ollama_models=lambda base_url, timeout: ["mistral", "llama3"],
        )
        assert result.annotation_type == "real_llm"
        assert result.details["model"] == "mistral"

    def test_cas_a_ollama_unreachable_falls_back_to_stub(self):
        def raise_unreachable(base_url, timeout):
            raise LlmProviderError("connexion refusee (mock)")

        result = detect_provider({"LLM_PROVIDER": "ollama", "LLM_MODEL": "llama3"}, list_ollama_models=raise_unreachable)
        assert result.annotation_type == "rule_based_stub"
        assert "injoignable" in result.reason

    def test_cas_a_ollama_no_models_available_falls_back_to_stub(self):
        result = detect_provider({"LLM_PROVIDER": "ollama"}, list_ollama_models=lambda base_url, timeout: [])
        assert result.annotation_type == "rule_based_stub"

    def test_detect_provider_never_calls_real_network(self, monkeypatch):
        import urllib.request

        def forbidden(*args, **kwargs):
            raise AssertionError("Aucun appel reseau reel ne doit avoir lieu pendant les tests (§ tache 12).")

        monkeypatch.setattr(urllib.request, "urlopen", forbidden)
        result = detect_provider(
            {"LLM_PROVIDER": "ollama", "LLM_MODEL": "llama3"},
            list_ollama_models=lambda base_url, timeout: ["llama3"],
        )
        assert result.annotation_type == "real_llm"
