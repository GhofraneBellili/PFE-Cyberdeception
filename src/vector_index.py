"""
Réf. architecture : "9.1 Pipeline de construction de la KB déception"
(étape 7, index vectoriel) — réf. tâche « index vectoriel ».

Index vectoriel local et reproductible pour la similarité cosinus /
produit scalaire normalisé entre embeddings sémantiques. Utilise FAISS
si disponible (`faiss-cpu`), sinon un repli en mémoire pur NumPy
(recherche exhaustive) — jamais un service externe (Chroma/Pinecone/
Weaviate), conformément à la tâche.

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

try:
    import faiss

    FAISS_AVAILABLE = True
except ImportError:
    faiss = None
    FAISS_AVAILABLE = False


class VectorIndexError(Exception):
    """Erreur de construction ou de recherche dans l'index vectoriel."""


@dataclass(frozen=True)
class NumpyFlatIndex:
    """Réf. tâche « ou un index numpy local si FAISS pose un problème
    d'installation » — recherche exhaustive par produit scalaire sur des
    vecteurs déjà normalisés (équivalent à la similarité cosinus)."""

    vectors: np.ndarray  # (n, d), normalisés L2

    def search(self, query_vector: np.ndarray, top_k: int) -> list[tuple[int, float]]:
        scores = self.vectors @ query_vector
        top_k = min(top_k, len(scores))
        top_indices = np.argsort(-scores)[:top_k]
        return [(int(i), float(scores[i])) for i in top_indices]


def build_vector_index(vectors: np.ndarray) -> tuple[Any, str]:
    """Réf. tâche « préférer FAISS si possible ». Retourne
    `(index, backend)` où `backend` vaut `"faiss"` ou `"numpy"` — jamais
    caché, toujours rapporté pour traçabilité (§28)."""
    if vectors.ndim != 2:
        raise VectorIndexError(f"Les vecteurs doivent former une matrice (n, d) — reçu shape={vectors.shape}.")
    if FAISS_AVAILABLE:
        dimension = vectors.shape[1]
        index = faiss.IndexFlatIP(dimension)
        index.add(np.ascontiguousarray(vectors, dtype=np.float32))
        return index, "faiss"
    return NumpyFlatIndex(vectors=np.ascontiguousarray(vectors, dtype=np.float32)), "numpy"


def search_vector_index(index: Any, backend: str, query_vector: np.ndarray, top_k: int) -> list[tuple[int, float]]:
    """Réf. tâche « similarité cosinus / inner product normalisé, top-k »."""
    if top_k <= 0:
        raise VectorIndexError(f"top_k doit être strictement positif (valeur reçue : {top_k}).")
    query_vector = np.ascontiguousarray(query_vector, dtype=np.float32)
    if backend == "faiss":
        scores, indices = index.search(query_vector.reshape(1, -1), top_k)
        return [(int(i), float(s)) for i, s in zip(indices[0], scores[0]) if i != -1]
    if backend == "numpy":
        return index.search(query_vector, top_k)
    raise VectorIndexError(f"Backend d'index vectoriel inconnu : '{backend}'.")
