"""
Réf. architecture : CLAUDE.md §9.1/§26 (rag_retriever.py) — contrat
technique du PFE Cyberdéception.

Tests unitaires de src/rag_retriever.py (§25.4 : pytest obligatoire).
"""

from pathlib import Path

import numpy as np
import pytest

from src.rag_indexer import Chunk, build_index, build_semantic_index, load_literature_chunks
from src.rag_retriever import RagRetrieverError, cosine_similarity, retrieve, retrieve_hybrid, retrieve_semantic

REPO_ROOT = Path(__file__).resolve().parent.parent
STAGING_DIR = REPO_ROOT / "data" / "deception" / "staging"


def load_json(name: str) -> dict:
    import json

    return json.loads((STAGING_DIR / name).read_text(encoding="utf-8"))


class FakeEmbedder:
    """Embedder déterministe factice utilisé pour le retrieval sémantique
    sans dépendance réseau (réf. tâche §18)."""

    def __init__(self, model_name: str = "fake-embedder-test-v1", dimension: int = 8):
        self.model_name = model_name
        self.dimension = dimension
        # Vecteurs de base orthogonaux associés à des mots-clés du corpus
        # de test, pour que la similarité sémantique simulée soit
        # interprétable dans les assertions (et non un simple hachage).
        self._topic_axes = {
            "credential": 0,
            "honeypot": 0,
            "decoy": 0,
            "network": 1,
            "firewall": 1,
            "segment": 1,
            "fruit": 2,
            "banana": 2,
            "apple": 2,
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


def _chunk(chunk_id: str, text: str, source_type: str = "literature") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        source_id="s",
        source_type=source_type,
        document_id="doc",
        locator="l",
        text=text,
        text_hash="hash",
    )


def small_semantic_index():
    chunks = [
        _chunk("e_credential", "decoy credential store honeypot for adversary", source_type="literature"),
        _chunk("e_network", "network segment topology firewall routing", source_type="d3fend"),
        _chunk("e_fruit", "apple banana fruit salad recipe", source_type="literature"),
    ]
    return build_semantic_index(chunks, embedder=FakeEmbedder())


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
# C. Retrieval sémantique — moteur RAG principal, réf. tâche « RAG sémantique »
# ---------------------------------------------------------------------------


class TestRetrieveSemantic:
    def test_top_result_is_most_similar_chunk(self):
        index = small_semantic_index()
        results = retrieve_semantic(index, "decoy credential honeypot", top_k=1, embedder=FakeEmbedder())
        assert len(results) == 1
        assert results[0].chunk.chunk_id == "e_credential"

    def test_results_sorted_descending_by_score(self):
        index = small_semantic_index()
        results = retrieve_semantic(index, "credential honeypot decoy", top_k=3, embedder=FakeEmbedder())
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_top_k_limits_result_count(self):
        index = small_semantic_index()
        results = retrieve_semantic(index, "decoy", top_k=2, embedder=FakeEmbedder())
        assert len(results) == 2

    def test_source_type_filter(self):
        index = small_semantic_index()
        results = retrieve_semantic(index, "decoy", top_k=10, source_type_filter="literature", embedder=FakeEmbedder())
        assert all(r.chunk.source_type == "literature" for r in results)
        results_other = retrieve_semantic(index, "network", top_k=10, source_type_filter="engage", embedder=FakeEmbedder())
        assert results_other == []

    def test_invalid_top_k_rejected(self):
        index = small_semantic_index()
        with pytest.raises(RagRetrieverError):
            retrieve_semantic(index, "decoy", top_k=0, embedder=FakeEmbedder())

    def test_empty_index_returns_empty_list(self):
        index = build_semantic_index([], embedder=FakeEmbedder())
        assert retrieve_semantic(index, "anything", embedder=FakeEmbedder()) == []

    def test_provenance_preserved_in_results(self):
        index = small_semantic_index()
        results = retrieve_semantic(index, "decoy credential", top_k=1, embedder=FakeEmbedder())
        chunk = results[0].chunk
        assert chunk.chunk_id == "e_credential"
        assert chunk.source_id == "s"
        assert chunk.text_hash == "hash"

    def test_deterministic_result_for_a_given_index(self):
        index = small_semantic_index()
        results_a = retrieve_semantic(index, "decoy credential", top_k=3, embedder=FakeEmbedder())
        results_b = retrieve_semantic(index, "decoy credential", top_k=3, embedder=FakeEmbedder())
        assert [r.chunk.chunk_id for r in results_a] == [r.chunk.chunk_id for r in results_b]
        assert [r.score for r in results_a] == pytest.approx([r.score for r in results_b])


class TestRetrieveHybrid:
    def test_alpha_one_top_result_matches_semantic_only(self):
        lexical_index = small_index()
        semantic_index = small_semantic_index()
        hybrid_results = retrieve_hybrid(
            lexical_index, semantic_index, "decoy credential honeypot", top_k=1, alpha=1.0, embedder=FakeEmbedder()
        )
        semantic_results = retrieve_semantic(semantic_index, "decoy credential honeypot", top_k=1, embedder=FakeEmbedder())
        assert hybrid_results[0].chunk.chunk_id == semantic_results[0].chunk.chunk_id
        assert hybrid_results[0].score == pytest.approx(semantic_results[0].score)

    def test_alpha_zero_top_result_matches_lexical_only(self):
        lexical_index = small_index()
        semantic_index = small_semantic_index()
        hybrid_results = retrieve_hybrid(
            lexical_index, semantic_index, "decoy credential honeypot", top_k=1, alpha=0.0, embedder=FakeEmbedder()
        )
        lexical_results = retrieve(lexical_index, "decoy credential honeypot", top_k=1)
        assert hybrid_results[0].chunk.chunk_id == lexical_results[0].chunk.chunk_id
        assert hybrid_results[0].score == pytest.approx(lexical_results[0].score)

    def test_fused_score_matches_weighted_formula(self):
        lexical_index = small_index()
        semantic_index = small_semantic_index()
        alpha = 0.7
        hybrid_results = retrieve_hybrid(
            lexical_index, semantic_index, "decoy credential honeypot", top_k=3, alpha=alpha, embedder=FakeEmbedder()
        )
        lexical_by_id = {r.chunk.chunk_id: r.score for r in retrieve(lexical_index, "decoy credential honeypot", top_k=3)}
        semantic_by_id = {
            r.chunk.chunk_id: r.score
            for r in retrieve_semantic(semantic_index, "decoy credential honeypot", top_k=3, embedder=FakeEmbedder())
        }
        for result in hybrid_results:
            expected_score = alpha * semantic_by_id[result.chunk.chunk_id] + (1 - alpha) * lexical_by_id[result.chunk.chunk_id]
            assert result.score == pytest.approx(expected_score)

    def test_results_sorted_descending_by_fused_score(self):
        lexical_index = small_index()
        semantic_index = small_semantic_index()
        results = retrieve_hybrid(
            lexical_index, semantic_index, "credential honeypot decoy", top_k=3, alpha=0.8, embedder=FakeEmbedder()
        )
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_top_k_limits_result_count(self):
        lexical_index = small_index()
        semantic_index = small_semantic_index()
        results = retrieve_hybrid(lexical_index, semantic_index, "decoy", top_k=2, alpha=0.8, embedder=FakeEmbedder())
        assert len(results) == 2

    def test_invalid_alpha_rejected(self):
        lexical_index = small_index()
        semantic_index = small_semantic_index()
        with pytest.raises(RagRetrieverError):
            retrieve_hybrid(lexical_index, semantic_index, "decoy", alpha=1.5, embedder=FakeEmbedder())

    def test_invalid_top_k_rejected(self):
        lexical_index = small_index()
        semantic_index = small_semantic_index()
        with pytest.raises(RagRetrieverError):
            retrieve_hybrid(lexical_index, semantic_index, "decoy", top_k=0, embedder=FakeEmbedder())

    def test_source_type_filter(self):
        lexical_index = small_index()
        semantic_index = small_semantic_index()
        results = retrieve_hybrid(
            lexical_index, semantic_index, "decoy", top_k=10, alpha=0.8, source_type_filter="literature", embedder=FakeEmbedder()
        )
        assert all(r.chunk.source_type == "literature" for r in results)


class TestRetrieveSemanticVsLexicalNoRagDependencyLeak:
    def test_semantic_and_lexical_retrieval_are_independently_computed(self):
        """Les deux moteurs partagent les mêmes `Chunk` mais pas le même
        espace vectoriel : aucune valeur du RAG lexical ne doit fuiter
        dans le RAG sémantique (comparaison quantitative réelle en
        Phase 2, `docs/chapter4/outputs/rag_semantic_evaluation.*`)."""
        chunks = [
            _chunk("e_credential", "decoy credential store honeypot for adversary"),
            _chunk("e_network", "network segment topology firewall routing"),
        ]
        lexical_index = build_index(chunks)
        semantic_index = build_semantic_index(chunks, embedder=FakeEmbedder())
        lexical_results = retrieve(lexical_index, "decoy credential", top_k=2)
        semantic_results = retrieve_semantic(semantic_index, "decoy credential", top_k=2, embedder=FakeEmbedder())
        assert [r.chunk.chunk_id for r in lexical_results] == [r.chunk.chunk_id for r in semantic_results]
        # Les scores proviennent de deux calculs distincts (IDF haché vs
        # produit scalaire d'embeddings) : rien ne garantit qu'ils soient
        # égaux, seulement qu'ils sont chacun dans [-1, 1].
        for result in lexical_results + semantic_results:
            assert -1.0 - 1e-6 <= result.score <= 1.0 + 1e-6


# ---------------------------------------------------------------------------
# D. Invariant LLM hors du chemin d'exécution
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
