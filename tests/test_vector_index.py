"""
Réf. architecture : CLAUDE.md §9.1/§26 — contrat technique du PFE
Cyberdéception, réf. tâche « index vectoriel local (FAISS ou repli
NumPy) ».

Tests unitaires de src/vector_index.py (§25.4 : pytest obligatoire).
Aucun accès réseau ni service externe (Chroma/Pinecone/Weaviate) : tout
est local, en mémoire.
"""

from __future__ import annotations

import numpy as np
import pytest

from src import vector_index as vi


def _normalized(vectors: list[list[float]]) -> np.ndarray:
    array = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    return array / norms


class TestBuildVectorIndex:
    def test_backend_is_explicitly_reported(self):
        vectors = _normalized([[1.0, 0.0], [0.0, 1.0]])
        index, backend = vi.build_vector_index(vectors)
        assert backend in ("faiss", "numpy")
        assert index is not None

    def test_rejects_non_2d_array(self):
        with pytest.raises(vi.VectorIndexError):
            vi.build_vector_index(np.array([1.0, 2.0, 3.0], dtype=np.float32))


class TestSearchVectorIndexFaissOrDefaultBackend:
    def test_search_returns_most_similar_vector_first(self):
        vectors = _normalized([[1.0, 0.0], [0.0, 1.0], [0.9, 0.1]])
        index, backend = vi.build_vector_index(vectors)
        query = _normalized([[1.0, 0.05]])[0]
        hits = vi.search_vector_index(index, backend, query, top_k=2)
        assert hits[0][0] == 0  # le vecteur [1,0] est le plus proche de la requête

    def test_top_k_limits_result_count(self):
        vectors = _normalized([[1.0, 0.0], [0.0, 1.0], [0.9, 0.1]])
        index, backend = vi.build_vector_index(vectors)
        hits = vi.search_vector_index(index, backend, vectors[0], top_k=1)
        assert len(hits) == 1

    def test_invalid_top_k_rejected(self):
        vectors = _normalized([[1.0, 0.0]])
        index, backend = vi.build_vector_index(vectors)
        with pytest.raises(vi.VectorIndexError):
            vi.search_vector_index(index, backend, vectors[0], top_k=0)

    def test_unknown_backend_rejected(self):
        vectors = _normalized([[1.0, 0.0]])
        index, _ = vi.build_vector_index(vectors)
        with pytest.raises(vi.VectorIndexError):
            vi.search_vector_index(index, "unknown_backend", vectors[0], top_k=1)


class TestNumpyFlatIndexFallbackForced:
    """Force le repli NumPy indépendamment de la présence réelle de FAISS
    dans l'environnement, pour garantir que le repli est testé même quand
    faiss-cpu est installé."""

    def test_numpy_backend_used_when_faiss_unavailable(self, monkeypatch):
        monkeypatch.setattr(vi, "FAISS_AVAILABLE", False)
        vectors = _normalized([[1.0, 0.0], [0.0, 1.0]])
        index, backend = vi.build_vector_index(vectors)
        assert backend == "numpy"
        assert isinstance(index, vi.NumpyFlatIndex)

    def test_numpy_flat_index_search_matches_dot_product_ranking(self):
        vectors = _normalized([[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]])
        index = vi.NumpyFlatIndex(vectors=vectors)
        query = _normalized([[0.0, 1.0]])[0]
        hits = index.search(query, top_k=3)
        ranked_indices = [i for i, _ in hits]
        assert ranked_indices[0] == 1  # [0,1] identique à la requête
        scores = [score for _, score in hits]
        assert scores == sorted(scores, reverse=True)
