"""
Réf. tâche « améliorer réellement la qualité et la latence du moteur RAG »
§5 : tests unitaires des composants déterministes de
`tools/chapter4_evaluation/retrieval_improvements.py` et
`tools/chapter4_evaluation/latency_optimization.py` -- calcul pur, aucune
dépendance modèle/réseau.
"""

from dataclasses import dataclass

import pytest

from src.rag_indexer import Chunk
from src.rag_retriever import RetrievalResult
from tools.chapter4_evaluation.latency_optimization import CONDENSED_MAX_CHARS, condense_text
from tools.chapter4_evaluation.retrieval_improvements import (
    build_bm25_index,
    deduplicate_pool,
    guess_source_types_from_query,
    retrieve_bm25,
)


def make_chunk(chunk_id: str, text: str, source_type: str = "attack") -> Chunk:
    return Chunk(
        chunk_id=chunk_id, source_id="src", source_type=source_type, document_id="doc",
        locator="description", text=text, text_hash="hash",
    )


CHUNKS = [
    make_chunk("c1", "phishing messages used by adversaries to gain initial access"),
    make_chunk("c2", "brute force guessing of account passwords"),
    make_chunk("c3", "completely unrelated passage about weather forecasting"),
]


class TestBm25:
    def test_relevant_chunk_scores_higher_than_irrelevant(self):
        index = build_bm25_index(CHUNKS)
        results = retrieve_bm25(index, "phishing initial access adversaries", top_k=3)
        assert results[0].chunk.chunk_id == "c1"
        assert results[0].score > 0.0

    def test_top_k_respected(self):
        index = build_bm25_index(CHUNKS)
        results = retrieve_bm25(index, "adversaries", top_k=2)
        assert len(results) == 2

    def test_unknown_query_terms_do_not_crash(self):
        index = build_bm25_index(CHUNKS)
        results = retrieve_bm25(index, "zzzznonexistentterm", top_k=3)
        assert len(results) == 3
        assert all(r.score == 0.0 for r in results)


class TestDeduplicatePool:
    def test_near_duplicate_removed_keeps_higher_ranked(self):
        # tokens identiques (memes mots-cles significatifs, ordre/mot-outil differents) -> Jaccard = 1.0
        chunk_a = make_chunk("a", "phishing messages used by adversaries to gain initial access to systems")
        chunk_b = make_chunk("b", "the phishing messages, used by adversaries, gain initial access to systems")
        chunk_c = make_chunk("c", "completely unrelated passage about weather forecasting patterns")
        results = [RetrievalResult(chunk=chunk_a, score=0.9), RetrievalResult(chunk=chunk_b, score=0.8), RetrievalResult(chunk=chunk_c, score=0.7)]
        deduped = deduplicate_pool(results, threshold=0.8)
        ids = [r.chunk.chunk_id for r in deduped]
        assert "a" in ids
        assert "b" not in ids  # quasi-doublon de "a", de rang inferieur
        assert "c" in ids

    def test_distinct_passages_all_kept(self):
        results = [RetrievalResult(chunk=c, score=1.0 - i * 0.1) for i, c in enumerate(CHUNKS)]
        deduped = deduplicate_pool(results, threshold=0.8)
        assert len(deduped) == len(CHUNKS)

    def test_empty_pool_returns_empty(self):
        assert deduplicate_pool([]) == []


class TestQueryRouting:
    def test_technique_id_pattern_routes_to_attack(self):
        assert guess_source_types_from_query("mitigation for T1566 phishing") == ("attack",)

    def test_monitoring_keyword_routes_to_engage(self):
        result = guess_source_types_from_query("monitor network traffic to detect activity")
        assert result is not None
        assert "engage" in result

    def test_no_match_returns_none(self):
        assert guess_source_types_from_query("xyzzy foobar qux") is None


class TestCondenseText:
    def test_short_text_unchanged(self):
        text = "short passage"
        assert condense_text(text) == text

    def test_long_text_truncated_to_max_chars(self):
        text = "word " * 500
        condensed = condense_text(text, max_chars=100)
        assert len(condensed) <= 100

    def test_truncation_prefers_word_boundary(self):
        text = "a" * 90 + " " + "b" * 90
        condensed = condense_text(text, max_chars=95)
        # coupe au dernier espace (fin du mot "a"*90) plutot qu'au milieu du mot "b"*90
        assert condensed == "a" * 90
        assert "b" not in condensed

    def test_default_max_chars_constant_is_positive(self):
        assert CONDENSED_MAX_CHARS > 0
