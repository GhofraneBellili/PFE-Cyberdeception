"""
Réf. architecture : CLAUDE.md §11.2 — réf. tâche « renforcer le RAG
utilisé par SP2 », §8 à §14 « Retrieval en deux étapes, reranking
contextuel, diversité des preuves, `CandidateEvidenceBundle` ».

Tests unitaires de `src/rag_evidence.py` (§25.4 : pytest obligatoire) —
couvre les critères §19-F (RETRIEVAL LARGE), §19-G (fusion/dédoublonnage),
§19-H/I (le reranker préserve chunk_id et les scores intermédiaires),
§19-J (le top-k final respecte le nombre demandé), §19-K (le bundle a
trois familles), §19-L (traçabilité des evidence_ids), §19-M (aucun
budget dans le RAG).

`DeterministicFakeReranker` est utilisé partout ici — aucun modèle réel
n'est téléchargé pendant `pytest` (réf. tâche §28).
"""

import numpy as np
import pytest

from src.rag_indexer import Chunk, build_index, build_semantic_index
from src.rag_evidence import (
    CandidateEvidenceBundle,
    RagEvidenceError,
    build_candidate_evidence_bundle,
    build_family_evidence,
    diversify_by_document,
    retrieve_large_pool,
    to_annotation_evidence,
)
from src.rag_retriever import RetrievalResult
from src.reranker import DeterministicFakeReranker
from src.schemas import RagCandidateContext, RagGraphContext, SIPlacementContext


class FakeEmbedder:
    """Réf. tâche §18 : embedder déterministe factice, aucune dépendance
    réseau — même principe que `tests/test_rag_retriever.py::FakeEmbedder`."""

    def __init__(self, model_name: str = "fake-embedder-test-v1", dimension: int = 8):
        self.model_name = model_name
        self.dimension = dimension
        self._topic_axes = {
            "decoy": 0,
            "credential": 0,
            "honeytoken": 0,
            "email": 1,
            "phishing": 1,
            "mailbox": 1,
        }

    def encode(self, texts):
        vectors = []
        for text in texts:
            vector = np.zeros(self.dimension, dtype=np.float32)
            words = text.lower().replace(",", " ").split()
            matched = False
            for word in words:
                if word in self._topic_axes:
                    vector[self._topic_axes[word]] += 1.0
                    matched = True
            if not matched:
                seed = sum(ord(c) for c in text) or 1
                rng = np.random.default_rng(seed)
                vector = rng.normal(size=self.dimension).astype(np.float32)
            norm = np.linalg.norm(vector)
            vectors.append(vector / norm if norm > 0 else vector)
        return np.asarray(vectors, dtype=np.float32)


def _chunk(chunk_id: str, text: str, *, source_type="literature", document_id="doc") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        source_id=document_id,
        source_type=source_type,
        document_id=document_id,
        locator="l",
        text=text,
        text_hash="hash",
    )


def make_corpus_chunks() -> list[Chunk]:
    return [
        _chunk("c1", "decoy credential lures the attacker into a fake honeytoken", source_type="d3fend", document_id="doc-A"),
        _chunk("c2", "decoy credential store contains fabricated honeytoken entries", source_type="d3fend", document_id="doc-A"),
        _chunk("c3", "decoy credential monitored for unauthorized access attempts", source_type="d3fend", document_id="doc-A"),
        _chunk("c4", "email phishing mailbox redirected to a monitored decoy", source_type="engage", document_id="doc-B"),
        _chunk("c5", "phishing email attachment detonated in a sandboxed mailbox", source_type="engage", document_id="doc-B"),
        _chunk("c6", "completely unrelated passage about network segmentation", source_type="attack", document_id="doc-C"),
    ]


def make_indices():
    chunks = make_corpus_chunks()
    lexical_index = build_index(chunks)
    semantic_index = build_semantic_index(chunks, embedder=FakeEmbedder())
    return lexical_index, semantic_index


def make_candidate_context(**overrides) -> RagCandidateContext:
    base = dict(
        occurrence_id="T1566@WS01",
        technique_id="T1566",
        technique_name="Phishing",
        tactics=["initial-access"],
        asset_id="WS01",
        asset_type="workstation",
        mechanism_id="D1",
        mechanism_name="Decoy Mailbox",
        mechanism_description="A decoy mailbox lures phishing payloads.",
        target_artifacts=["email"],
        interaction_mechanism="attacker sends a phishing email to the decoy credential mailbox",
        location_id="mailbox-ws01",
        location_type="mailbox",
        si_context=SIPlacementContext(relevant_services=["email"], relevant_artifacts=[]),
        graph_context=RagGraphContext(
            direct_parent_technique_ids=[],
            direct_child_technique_ids=["T1110"],
            is_entry=True,
            is_terminal=False,
            neighboring_tactics=["credential-access"],
        ),
    )
    base.update(overrides)
    return RagCandidateContext(**base)


# ---------------------------------------------------------------------------
# A. Stage A — RETRIEVAL LARGE (§19-F) et fusion (§19-G)
# ---------------------------------------------------------------------------


class TestRetrieveLargePool:
    def test_returns_candidates_from_both_engines(self):
        lexical_index, semantic_index = make_indices()
        pool = retrieve_large_pool(
            lexical_index, semantic_index, "decoy credential honeytoken", pool_k=10, embedder=FakeEmbedder()
        )
        assert len(pool) > 0

    def test_fused_pool_deduplicates_by_chunk_id(self):
        lexical_index, semantic_index = make_indices()
        pool = retrieve_large_pool(
            lexical_index, semantic_index, "decoy credential honeytoken", pool_k=10, embedder=FakeEmbedder()
        )
        chunk_ids = [candidate.chunk.chunk_id for candidate in pool]
        assert len(chunk_ids) == len(set(chunk_ids))

    def test_each_candidate_keeps_three_distinct_scores(self):
        lexical_index, semantic_index = make_indices()
        pool = retrieve_large_pool(
            lexical_index, semantic_index, "decoy credential honeytoken", pool_k=10, embedder=FakeEmbedder()
        )
        top = pool[0]
        assert isinstance(top.semantic_score, float)
        assert isinstance(top.lexical_score, float)
        assert isinstance(top.hybrid_score, float)

    def test_rejects_non_positive_pool_k(self):
        lexical_index, semantic_index = make_indices()
        with pytest.raises(RagEvidenceError):
            retrieve_large_pool(lexical_index, semantic_index, "query", pool_k=0)


# ---------------------------------------------------------------------------
# B. Diversification (§12) — après reranking, quota par document_id
# ---------------------------------------------------------------------------


class TestDiversifyByDocument:
    def test_limits_chunks_per_document(self):
        lexical_index, semantic_index = make_indices()
        pool = retrieve_large_pool(
            lexical_index, semantic_index, "decoy credential honeytoken", pool_k=10, embedder=FakeEmbedder()
        )
        results = [RetrievalResult(chunk=c.chunk, score=c.hybrid_score) for c in pool]
        reranked = DeterministicFakeReranker().rerank("decoy credential honeytoken", results, top_k=len(results))
        diversified = diversify_by_document(reranked, max_per_document=1, top_k=5)
        document_ids = [item.retrieval_result.chunk.document_id for item in diversified]
        assert len(document_ids) == len(set(document_ids))

    def test_respects_top_k_even_with_generous_quota(self):
        lexical_index, semantic_index = make_indices()
        pool = retrieve_large_pool(
            lexical_index, semantic_index, "decoy credential honeytoken", pool_k=10, embedder=FakeEmbedder()
        )
        results = [RetrievalResult(chunk=c.chunk, score=c.hybrid_score) for c in pool]
        reranked = DeterministicFakeReranker().rerank("decoy credential honeytoken", results, top_k=len(results))
        diversified = diversify_by_document(reranked, max_per_document=10, top_k=3)
        assert len(diversified) == 3

    def test_final_rank_reassigned_sequentially(self):
        lexical_index, semantic_index = make_indices()
        pool = retrieve_large_pool(
            lexical_index, semantic_index, "decoy credential honeytoken", pool_k=10, embedder=FakeEmbedder()
        )
        results = [RetrievalResult(chunk=c.chunk, score=c.hybrid_score) for c in pool]
        reranked = DeterministicFakeReranker().rerank("decoy credential honeytoken", results, top_k=len(results))
        diversified = diversify_by_document(reranked, max_per_document=1, top_k=3)
        assert [item.final_rank for item in diversified] == list(range(1, len(diversified) + 1))

    def test_rejects_non_positive_max_per_document(self):
        with pytest.raises(RagEvidenceError):
            diversify_by_document([], max_per_document=0, top_k=5)


# ---------------------------------------------------------------------------
# C. Pipeline par famille — reranker préserve chunk_id (§19-H) et scores (§19-I)
# ---------------------------------------------------------------------------


class TestBuildFamilyEvidence:
    def test_evidence_chunk_ids_come_from_the_corpus(self):
        lexical_index, semantic_index = make_indices()
        family = build_family_evidence(
            query="decoy credential honeytoken",
            lexical_index=lexical_index,
            semantic_index=semantic_index,
            reranker=DeterministicFakeReranker(),
            retrieval_candidates=10,
            final_top_k=3,
            diversity_max_per_document=2,
            embedder=FakeEmbedder(),
        )
        corpus_ids = {c.chunk_id for c in make_corpus_chunks()}
        assert all(item.chunk_id in corpus_ids for item in family.evidence)

    def test_evidence_carries_all_intermediate_scores(self):
        lexical_index, semantic_index = make_indices()
        family = build_family_evidence(
            query="decoy credential honeytoken",
            lexical_index=lexical_index,
            semantic_index=semantic_index,
            reranker=DeterministicFakeReranker(),
            retrieval_candidates=10,
            final_top_k=3,
            diversity_max_per_document=2,
            embedder=FakeEmbedder(),
        )
        for item in family.evidence:
            assert isinstance(item.semantic_score, float)
            assert isinstance(item.lexical_score, float)
            assert isinstance(item.hybrid_score, float)
            assert isinstance(item.reranker_score, float)
            assert isinstance(item.final_rank, int)

    def test_respects_final_top_k(self):
        lexical_index, semantic_index = make_indices()
        family = build_family_evidence(
            query="decoy credential honeytoken",
            lexical_index=lexical_index,
            semantic_index=semantic_index,
            reranker=DeterministicFakeReranker(),
            retrieval_candidates=10,
            final_top_k=2,
            diversity_max_per_document=5,
            embedder=FakeEmbedder(),
        )
        assert len(family.evidence) <= 2

    def test_empty_pool_returns_empty_evidence(self):
        empty_lexical = build_index([])
        empty_semantic = build_semantic_index([], embedder=FakeEmbedder())
        family = build_family_evidence(
            query="anything",
            lexical_index=empty_lexical,
            semantic_index=empty_semantic,
            reranker=DeterministicFakeReranker(),
            retrieval_candidates=10,
            final_top_k=3,
            diversity_max_per_document=2,
        )
        assert family.evidence == ()


# ---------------------------------------------------------------------------
# D. Bundle complet (§19-K, §19-J) — trois familles, top-k respecté
# ---------------------------------------------------------------------------


class TestBuildCandidateEvidenceBundle:
    def test_bundle_has_three_families(self):
        lexical_index, semantic_index = make_indices()
        context = make_candidate_context()
        bundle = build_candidate_evidence_bundle(
            context,
            lexical_index=lexical_index,
            semantic_index=semantic_index,
            reranker=DeterministicFakeReranker(),
            retrieval_candidates=10,
            final_top_k=2,
            diversity_max_per_document=2,
            embedder=FakeEmbedder(),
        )
        assert isinstance(bundle, CandidateEvidenceBundle)
        assert set(bundle.families().keys()) == {"realism", "interaction", "effect"}

    def test_each_family_respects_requested_top_k(self):
        lexical_index, semantic_index = make_indices()
        context = make_candidate_context()
        bundle = build_candidate_evidence_bundle(
            context,
            lexical_index=lexical_index,
            semantic_index=semantic_index,
            reranker=DeterministicFakeReranker(),
            retrieval_candidates=10,
            final_top_k=2,
            diversity_max_per_document=2,
            embedder=FakeEmbedder(),
        )
        for family in bundle.families().values():
            assert len(family.evidence) <= 2

    def test_candidate_id_derived_from_context(self):
        lexical_index, semantic_index = make_indices()
        context = make_candidate_context()
        bundle = build_candidate_evidence_bundle(
            context,
            lexical_index=lexical_index,
            semantic_index=semantic_index,
            reranker=DeterministicFakeReranker(),
            retrieval_candidates=10,
            final_top_k=2,
            diversity_max_per_document=2,
            embedder=FakeEmbedder(),
        )
        assert context.occurrence_id in bundle.candidate_id
        assert context.mechanism_id in bundle.candidate_id
        assert context.location_id in bundle.candidate_id

    def test_config_resolved_from_env_when_not_explicit(self, monkeypatch):
        lexical_index, semantic_index = make_indices()
        context = make_candidate_context()
        monkeypatch.setenv("RAG_FINAL_TOP_K", "1")
        bundle = build_candidate_evidence_bundle(
            context,
            lexical_index=lexical_index,
            semantic_index=semantic_index,
            reranker=DeterministicFakeReranker(),
            embedder=FakeEmbedder(),
        )
        for family in bundle.families().values():
            assert len(family.evidence) <= 1


# ---------------------------------------------------------------------------
# E. Traçabilité vers AnnotationContext (§14, §19-L)
# ---------------------------------------------------------------------------


class TestToAnnotationEvidence:
    def test_deduplicates_evidence_shared_across_families(self):
        lexical_index, semantic_index = make_indices()
        context = make_candidate_context()
        bundle = build_candidate_evidence_bundle(
            context,
            lexical_index=lexical_index,
            semantic_index=semantic_index,
            reranker=DeterministicFakeReranker(),
            retrieval_candidates=10,
            final_top_k=5,
            diversity_max_per_document=5,
            embedder=FakeEmbedder(),
        )
        retrieved_evidence, evidence_by_family = to_annotation_evidence(bundle)
        assert len(retrieved_evidence) == len({e.source for e in retrieved_evidence})

    def test_evidence_by_family_only_references_known_sources(self):
        lexical_index, semantic_index = make_indices()
        context = make_candidate_context()
        bundle = build_candidate_evidence_bundle(
            context,
            lexical_index=lexical_index,
            semantic_index=semantic_index,
            reranker=DeterministicFakeReranker(),
            retrieval_candidates=10,
            final_top_k=3,
            diversity_max_per_document=2,
            embedder=FakeEmbedder(),
        )
        retrieved_evidence, evidence_by_family = to_annotation_evidence(bundle)
        known_sources = {e.source for e in retrieved_evidence}
        for sources in evidence_by_family.values():
            assert set(sources) <= known_sources

    def test_evidence_by_family_has_three_keys(self):
        lexical_index, semantic_index = make_indices()
        context = make_candidate_context()
        bundle = build_candidate_evidence_bundle(
            context,
            lexical_index=lexical_index,
            semantic_index=semantic_index,
            reranker=DeterministicFakeReranker(),
            retrieval_candidates=10,
            final_top_k=2,
            diversity_max_per_document=2,
            embedder=FakeEmbedder(),
        )
        _, evidence_by_family = to_annotation_evidence(bundle)
        assert set(evidence_by_family.keys()) == {"realism", "interaction", "effect"}


# ---------------------------------------------------------------------------
# F. Aucun budget dans le pipeline RAG (§19-M)
# ---------------------------------------------------------------------------


class TestNoBudgetInRagPipeline:
    def test_build_candidate_evidence_bundle_signature_has_no_budget_parameter(self):
        import inspect

        signature = inspect.signature(build_candidate_evidence_bundle)
        forbidden = {"budget", "b_total", "budget_total", "total_budget", "cost"}
        assert forbidden.isdisjoint(signature.parameters.keys())
