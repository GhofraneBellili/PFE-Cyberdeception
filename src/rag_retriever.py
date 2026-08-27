"""
Réf. architecture : "9.1 Pipeline de construction de la KB déception"
(étape 7) et "26. Modules recommandés — rag_retriever.py" (CLAUDE.md
§9.1, §26).

Récupération des passages pertinents d'un `RagIndex`
(`src/rag_indexer.py`) pour une requête contextuelle donnée — réf. §11.2
« Entrées du LLM » : ce module fournit les preuves, il ne les interprète
pas et ne calcule aucune sous-métrique sémantique (rôle réservé à
`annotator_llm.py`). `to_deception_evidence` relie un `RetrievalResult` au
format attendu par `AnnotationContext.retrieved_evidence`
(`src/schemas.DeceptionEvidence`).

**Invariant central du projet (LLM hors du chemin d'exécution)** : ce
module n'importe jamais `src/annotator_llm.py`. Il ne fait aucun appel
réseau : la similarité est calculée uniquement à partir des vecteurs déjà
présents dans l'index (`src/rag_indexer.py`).

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from src.rag_indexer import Chunk, RagIndex, SourceType, embed_query
from src.schemas import DeceptionEvidence


class RagRetrieverError(Exception):
    """Erreur de récupération des preuves RAG."""


@dataclass(frozen=True)
class RetrievalResult:
    """Un chunk récupéré pour une requête, avec son score de similarité."""

    chunk: Chunk
    score: float


def cosine_similarity(vector_a: tuple[float, ...], vector_b: tuple[float, ...]) -> float:
    """Similarité cosinus entre deux vecteurs de même dimension."""
    if len(vector_a) != len(vector_b):
        raise RagRetrieverError("Les vecteurs comparés doivent avoir la même dimension.")
    dot = sum(a * b for a, b in zip(vector_a, vector_b))
    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def retrieve(
    index: RagIndex,
    query: str,
    *,
    top_k: int = 5,
    source_type_filter: SourceType | None = None,
) -> list[RetrievalResult]:
    """Réf. §9.1 étape 7 : récupère les `top_k` chunks les plus similaires
    à `query` (similarité cosinus sur les vecteurs de `src/rag_indexer.py`),
    optionnellement restreints à un `source_type`. Aucune valeur inventée :
    un index vide retourne une liste vide, jamais une erreur ni un
    résultat fabriqué."""
    if top_k <= 0:
        raise RagRetrieverError(f"top_k doit être strictement positif (valeur reçue : {top_k}).")

    query_vector = embed_query(index, query)
    candidates = [
        RetrievalResult(chunk=chunk, score=cosine_similarity(query_vector, index.embeddings[chunk.chunk_id]))
        for chunk in index.chunks
        if source_type_filter is None or chunk.source_type == source_type_filter
    ]
    candidates.sort(key=lambda result: result.score, reverse=True)
    return candidates[:top_k]


def to_deception_evidence(result: RetrievalResult) -> DeceptionEvidence:
    """Réf. §27 : convertit un `RetrievalResult` en `DeceptionEvidence`
    (`source`=chunk_id, `passage`=texte du chunk), format attendu par
    `AnnotationContext.retrieved_evidence` (`src/annotator_llm.py`)."""
    return DeceptionEvidence(source=result.chunk.chunk_id, passage=result.chunk.text)
