"""
Réf. tâche « renforcer l'architecture et l'implémentation du module RAG
utilisé par SP2 », §9/§10 « Reranking contextuel ».

Tests unitaires de `src/reranker.py` (§25.4 : pytest obligatoire).

La suite standard (`pytest`) n'utilise QUE `DeterministicFakeReranker` —
aucun modèle réel n'est téléchargé pendant `pytest` (réf. tâche §28, même
principe que les mocks HTTP du provider LLM réel). `TestCrossEncoderReranker`
(marqueur `real_reranker`, exclu par défaut, réf. `pyproject.toml`) exerce
le VRAI modèle `sentence-transformers.CrossEncoder` — seulement si lancé
explicitement avec `pytest -m real_reranker`.
"""

import pytest

from src.rag_indexer import Chunk
from src.rag_retriever import RetrievalResult
from src.reranker import CrossEncoderReranker, DeterministicFakeReranker, RerankerError


def _chunk(chunk_id: str, text: str, document_id: str = "doc") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        source_id="s",
        source_type="literature",
        document_id=document_id,
        locator="l",
        text=text,
        text_hash="hash",
    )


def _results(*pairs: tuple[str, str]) -> list[RetrievalResult]:
    return [RetrievalResult(chunk=_chunk(chunk_id, text), score=0.0) for chunk_id, text in pairs]


# ---------------------------------------------------------------------------
# A. DeterministicFakeReranker — contrat du pipeline (double de test)
# ---------------------------------------------------------------------------


class TestDeterministicFakeReranker:
    def test_reranks_by_lexical_overlap_with_query(self):
        reranker = DeterministicFakeReranker()
        candidates = _results(
            ("c1", "decoy credential honeypot lure"),
            ("c2", "completely unrelated weather forecast"),
        )
        results = reranker.rerank("decoy credential honeypot", candidates, top_k=2)
        assert results[0].retrieval_result.chunk.chunk_id == "c1"

    def test_preserves_chunk_ids(self):
        reranker = DeterministicFakeReranker()
        candidates = _results(("c1", "decoy credential"), ("c2", "honeypot lure"))
        results = reranker.rerank("decoy credential honeypot", candidates, top_k=2)
        result_ids = {r.retrieval_result.chunk.chunk_id for r in results}
        assert result_ids == {"c1", "c2"}

    def test_respects_requested_top_k(self):
        reranker = DeterministicFakeReranker()
        candidates = _results(("c1", "a"), ("c2", "b"), ("c3", "c"))
        results = reranker.rerank("a b c", candidates, top_k=2)
        assert len(results) == 2

    def test_final_rank_starts_at_one_and_is_sequential(self):
        reranker = DeterministicFakeReranker()
        candidates = _results(("c1", "decoy"), ("c2", "credential"), ("c3", "honeypot"))
        results = reranker.rerank("decoy credential honeypot", candidates, top_k=3)
        assert [r.final_rank for r in results] == [1, 2, 3]

    def test_empty_candidates_returns_empty_list(self):
        reranker = DeterministicFakeReranker()
        assert reranker.rerank("anything", [], top_k=5) == []

    def test_model_name_clearly_marked_as_test_double(self):
        reranker = DeterministicFakeReranker()
        assert "fake" in reranker.model_name.lower()
        assert "test" in reranker.model_name.lower()

    def test_deterministic_same_inputs_same_output(self):
        reranker = DeterministicFakeReranker()
        candidates = _results(("c1", "decoy credential"), ("c2", "honeypot lure"))
        results_a = reranker.rerank("decoy credential", candidates, top_k=2)
        results_b = reranker.rerank("decoy credential", candidates, top_k=2)
        assert [(r.retrieval_result.chunk.chunk_id, r.reranker_score) for r in results_a] == [
            (r.retrieval_result.chunk.chunk_id, r.reranker_score) for r in results_b
        ]


# ---------------------------------------------------------------------------
# B. CrossEncoderReranker — chargement paresseux, jamais à l'import (§9)
# ---------------------------------------------------------------------------


class TestCrossEncoderRerankerLazyLoading:
    def test_direct_construction_without_model_raises_on_rerank(self):
        reranker = CrossEncoderReranker(model_name="not-loaded")
        with pytest.raises(RerankerError):
            reranker.rerank("query", _results(("c1", "text")), top_k=1)

    def test_empty_candidates_returns_empty_without_needing_a_model(self):
        reranker = CrossEncoderReranker(model_name="not-loaded")
        assert reranker.rerank("query", [], top_k=1) == []


# ---------------------------------------------------------------------------
# C. Intégration réelle — modèle cross-encoder réellement téléchargé et
# exécuté (§9 : « ne jamais simuler un reranker ») — marqueur real_reranker,
# exclu par défaut (réf. pyproject.toml)
# ---------------------------------------------------------------------------


@pytest.mark.real_reranker
class TestCrossEncoderRerankerReal:
    def test_real_cross_encoder_ranks_relevant_passage_first(self):
        reranker = CrossEncoderReranker.load()
        candidates = _results(
            ("irrelevant", "The weather today is sunny with a chance of rain."),
            ("relevant", "A decoy credential is placed to lure an attacker into using it."),
        )
        results = reranker.rerank("decoy credential lure attacker", candidates, top_k=2)
        assert results[0].retrieval_result.chunk.chunk_id == "relevant"
        assert results[0].reranker_score > results[1].reranker_score

    def test_real_cross_encoder_preserves_all_chunk_ids(self):
        reranker = CrossEncoderReranker.load()
        candidates = _results(("c1", "a"), ("c2", "b"), ("c3", "c"))
        results = reranker.rerank("query", candidates, top_k=3)
        assert {r.retrieval_result.chunk.chunk_id for r in results} == {"c1", "c2", "c3"}
