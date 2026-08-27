"""
Réf. architecture : "9.1 Pipeline de construction de la KB déception"
(étape 7) et "26. Modules recommandés — rag_retriever.py" (CLAUDE.md
§9.1, §26).

Récupération des passages pertinents d'un `RagIndex` (baseline lexicale
TF-IDF), d'un `SemanticRagIndex` (moteur principal, réf. tâche « RAG
sémantique »), OU des deux fusionnés (`retrieve_hybrid`, réf. tâche §3 —
n'existe que parce que `docs/chapter4/outputs/rag_semantic_evaluation.json`
démontre un gain réel de Recall@5 par rapport au sémantique seul) — réf.
§11.2 « Entrées du LLM » : ce module fournit les preuves, il ne les
interprète pas et ne calcule aucune sous-métrique sémantique (rôle réservé
à `annotator_llm.py`). `to_deception_evidence` relie un `RetrievalResult`
au format attendu par `AnnotationContext.retrieved_evidence`
(`src/schemas.DeceptionEvidence`) — identique pour les trois moteurs.

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


def retrieve_semantic(
    index: "SemanticRagIndex",
    query: str,
    *,
    top_k: int = 5,
    source_type_filter: SourceType | None = None,
    embedder: object | None = None,
) -> list[RetrievalResult]:
    """Réf. tâche « nouvelle chaîne RAG » : récupère les `top_k` chunks
    les plus proches sémantiquement de `query` (similarité cosinus /
    produit scalaire normalisé, `src/vector_index.py`). Moteur PRINCIPAL
    du RAG à partir de cette tâche — `retrieve()` (TF-IDF) reste la
    baseline lexicale expérimentale.

    Si `source_type_filter` est fourni, sur-échantillonne l'index
    vectoriel (facteur x4, plafonné à la taille de l'index) puis filtre
    après coup — l'index vectoriel lui-même n'est pas partitionné par
    source_type (choix technique simple, cohérent avec un corpus de cette
    taille)."""
    from src.rag_indexer import SemanticRagIndex  # import différé : évite d'imposer numpy aux imports légers
    from src.vector_index import search_vector_index

    if top_k <= 0:
        raise RagRetrieverError(f"top_k doit être strictement positif (valeur reçue : {top_k}).")
    if len(index) == 0:
        return []

    from src.rag_indexer import embed_query_semantic

    query_vector = embed_query_semantic(index, query, embedder=embedder)

    search_k = min(len(index), top_k * 4) if source_type_filter is not None else top_k
    hits = search_vector_index(index.vector_index, index.backend, query_vector, search_k)

    results = []
    for chunk_index, score in hits:
        chunk = index.chunks[chunk_index]
        if source_type_filter is not None and chunk.source_type != source_type_filter:
            continue
        results.append(RetrievalResult(chunk=chunk, score=score))
    return results[:top_k]


# ---------------------------------------------------------------------------
# Retrieval hybride — réf. tâche « fusion lexical/sémantique, seulement si
# l'évaluation démontre un gain réel »
# ---------------------------------------------------------------------------

# alpha maximisant Recall@5 sur `data/rag/rag_eval_queries.json` (17
# requêtes réelles, vérité terrain relue humainement), testé parmi
# {0.5, 0.7, 0.8, 0.9} par `examples/rag_semantic_evaluation.py`. Résultat
# gelé dans `docs/chapter4/outputs/rag_semantic_evaluation.json` : hybride
# alpha=0.8 (Recall@5=0.470) bat le sémantique seul (0.396) et le lexical
# seul (0.331) — décision fondée sur cette mesure réelle, pas arbitraire.
DEFAULT_HYBRID_ALPHA = 0.8


def retrieve_hybrid(
    lexical_index: RagIndex,
    semantic_index: "SemanticRagIndex",
    query: str,
    *,
    top_k: int = 5,
    alpha: float = DEFAULT_HYBRID_ALPHA,
    source_type_filter: SourceType | None = None,
    embedder: object | None = None,
    fusion_pool_k: int | None = None,
) -> list[RetrievalResult]:
    """Réf. tâche §3 : `score_final = alpha * score_semantique +
    (1-alpha) * score_lexical`. N'existe QUE parce que
    `docs/chapter4/outputs/rag_semantic_evaluation.json` démontre un gain
    réel de Recall@5 par rapport au sémantique seul — sinon cette fonction
    n'aurait pas dû être ajoutée (réf. tâche : « si le sémantique seul est
    le meilleur, ne pas ajouter le mode hybride »).

    `lexical_index` et `semantic_index` doivent indexer le MÊME corpus
    (mêmes chunk_id) — un chunk absent du top du classement d'un des deux
    moteurs reçoit un score 0.0 sur ce classement (fusion standard, pas de
    valeur inventée)."""
    if not 0.0 <= alpha <= 1.0:
        raise RagRetrieverError(f"alpha doit être dans [0,1] (valeur reçue : {alpha}).")
    if top_k <= 0:
        raise RagRetrieverError(f"top_k doit être strictement positif (valeur reçue : {top_k}).")

    pool_k = fusion_pool_k if fusion_pool_k is not None else max(top_k * 4, 20)
    lexical_results = retrieve(lexical_index, query, top_k=pool_k)
    semantic_results = retrieve_semantic(semantic_index, query, top_k=pool_k, embedder=embedder)

    lexical_by_id = {r.chunk.chunk_id: r for r in lexical_results}
    semantic_by_id = {r.chunk.chunk_id: r for r in semantic_results}
    all_ids = set(lexical_by_id) | set(semantic_by_id)

    fused: list[RetrievalResult] = []
    for chunk_id in all_ids:
        lexical_score = lexical_by_id[chunk_id].score if chunk_id in lexical_by_id else 0.0
        semantic_score = semantic_by_id[chunk_id].score if chunk_id in semantic_by_id else 0.0
        chunk = semantic_by_id[chunk_id].chunk if chunk_id in semantic_by_id else lexical_by_id[chunk_id].chunk
        if source_type_filter is not None and chunk.source_type != source_type_filter:
            continue
        fused.append(RetrievalResult(chunk=chunk, score=alpha * semantic_score + (1 - alpha) * lexical_score))

    fused.sort(key=lambda result: result.score, reverse=True)
    return fused[:top_k]
