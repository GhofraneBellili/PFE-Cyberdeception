"""
Réf. architecture : CLAUDE.md §9.1/§26 (rag_retriever.py) — contrat
technique du PFE Cyberdéception.

Tests unitaires de src/rag_retriever.py (§25.4 : pytest obligatoire).
"""

from pathlib import Path

import pytest

from src.rag_indexer import build_index, load_literature_chunks
from src.rag_retriever import RagRetrieverError, cosine_similarity, retrieve

REPO_ROOT = Path(__file__).resolve().parent.parent
STAGING_DIR = REPO_ROOT / "data" / "deception" / "staging"


def load_json(name: str) -> dict:
    import json

    return json.loads((STAGING_DIR / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# A. Similarité cosinus
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    def test_identical_vectors_score_one(self):
        assert cosine_similarity((1.0, 0.0), (1.0, 0.0)) == pytest.approx(1.0)

    def test_orthogonal_vectors_score_zero(self):
        assert cosine_similarity((1.0, 0.0), (0.0, 1.0)) == pytest.approx(0.0)

    def test_zero_vector_scores_zero(self):
        assert cosine_similarity((0.0, 0.0), (1.0, 0.0)) == 0.0

    def test_mismatched_dimension_rejected(self):
        with pytest.raises(RagRetrieverError):
            cosine_similarity((1.0,), (1.0, 0.0))


# ---------------------------------------------------------------------------
# B. Retrieval sur un petit index synthétique
# ---------------------------------------------------------------------------


def small_index():
    seed = {
        "evidence": [
            {"evidence_id": "e_credential", "source_id": "s1", "page": 1, "locator": "l", "text": "decoy credential store honeypot for adversary"},
            {"evidence_id": "e_network", "source_id": "s2", "page": 1, "locator": "l", "text": "network segment topology routing firewall"},
            {"evidence_id": "e_fruit", "source_id": "s3", "page": 1, "locator": "l", "text": "apples oranges bananas fruit salad recipe"},
        ]
    }
    return build_index(load_literature_chunks(seed))


class TestRetrieve:
    def test_top_result_is_most_similar_chunk(self):
        index = small_index()
        results = retrieve(index, "decoy credential honeypot", top_k=1)
        assert len(results) == 1
        assert results[0].chunk.chunk_id == "e_credential"

    def test_results_sorted_descending_by_score(self):
        index = small_index()
        results = retrieve(index, "credential honeypot decoy", top_k=3)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_top_k_limits_result_count(self):
        index = small_index()
        results = retrieve(index, "decoy", top_k=2)
        assert len(results) == 2

    def test_source_type_filter(self):
        index = small_index()
        results = retrieve(index, "decoy", top_k=10, source_type_filter="literature")
        assert all(r.chunk.source_type == "literature" for r in results)
        results_other = retrieve(index, "decoy", top_k=10, source_type_filter="d3fend")
        assert results_other == []

    def test_invalid_top_k_rejected(self):
        index = small_index()
        with pytest.raises(RagRetrieverError):
            retrieve(index, "decoy", top_k=0)

    def test_empty_index_returns_empty_list(self):
        index = build_index([])
        assert retrieve(index, "anything") == []


# ---------------------------------------------------------------------------
# C. Invariant LLM hors du chemin d'exécution
# ---------------------------------------------------------------------------


class TestLlmOutOfExecutionPath:
    def test_rag_retriever_does_not_import_llm(self):
        import ast

        import src.rag_retriever as module

        source = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
        assert "src.annotator_llm" not in imported_modules
