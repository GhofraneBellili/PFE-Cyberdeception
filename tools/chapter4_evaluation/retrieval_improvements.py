"""
Réf. tâche « améliorer réellement la qualité et la latence du moteur RAG »
§2 : implémentation des variantes A-F, isolées dans ce module (jamais dans
`src/` -- le pipeline de référence du chapitre 4 reste inchangé tant que
l'intégration en production n'est pas une décision explicite séparée,
réf. CLAUDE.md §32 OPEN_DECISION). Chaque variante est une fonction pure
`(query, top_k) -> list[RetrievalResult]` construite sur les MÊMES index
réels (corpus complet 1306 chunks) que la baseline, pour une comparaison
strictement à variable unique.

A. BM25 (Okapi) au lieu du TF-IDF hashe -- même tokenizer que la baseline
   (`src.rag_indexer.tokenize`), pour ne comparer que le schéma de score.
B. Préfixe d'instruction BGE côté requête uniquement (recommandation
   officielle du modèle `BAAI/bge-*`), embeddings déjà normalisés L2 par
   `SentenceTransformerEmbedder` (aucun changement necessaire de ce côté).
C. Reciprocal Rank Fusion (k=60, valeur standard de la littérature,
   jamais ajustée sur nos données) au lieu de la fusion par score alpha.
D. Augmentation contrôlée du pool avant reclassement (pool_k plus grand).
E. Déduplication quasi-exacte des passages du pool (Jaccard de tokens).
F. Routage par type de source déterminé SEULEMENT à partir du texte de la
   requête (règles lexicales déterministes, jamais depuis la vérité
   terrain).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from src.rag_indexer import Chunk, RagIndex, SemanticRagIndex, tokenize
from src.rag_retriever import DEFAULT_HYBRID_ALPHA, RetrievalResult, retrieve, retrieve_semantic

# ---------------------------------------------------------------------------
# A. BM25 (Okapi), k1/b : valeurs standard de la litterature (Robertson &
# Zaragoza), jamais ajustees sur ce corpus.
# ---------------------------------------------------------------------------

BM25_K1 = 1.5
BM25_B = 0.75


@dataclass(frozen=True)
class Bm25Index:
    chunks: tuple[Chunk, ...]
    doc_freqs: dict[str, int]
    doc_lengths: dict[str, int]
    term_freqs: dict[str, dict[str, int]]
    avg_doc_length: float
    num_documents: int


def build_bm25_index(chunks: list[Chunk]) -> Bm25Index:
    doc_freqs: dict[str, int] = {}
    doc_lengths: dict[str, int] = {}
    term_freqs: dict[str, dict[str, int]] = {}
    total_length = 0
    for chunk in chunks:
        tokens = tokenize(chunk.text)
        doc_lengths[chunk.chunk_id] = len(tokens)
        total_length += len(tokens)
        tf: dict[str, int] = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1
        term_freqs[chunk.chunk_id] = tf
        for token in tf:
            doc_freqs[token] = doc_freqs.get(token, 0) + 1
    n = len(chunks)
    return Bm25Index(
        chunks=tuple(chunks), doc_freqs=doc_freqs, doc_lengths=doc_lengths, term_freqs=term_freqs,
        avg_doc_length=(total_length / n if n else 0.0), num_documents=n,
    )


def _bm25_score(index: Bm25Index, query_tokens: list[str], chunk_id: str) -> float:
    tf = index.term_freqs[chunk_id]
    dl = index.doc_lengths[chunk_id]
    score = 0.0
    for token in query_tokens:
        f = tf.get(token, 0)
        if f == 0:
            continue
        n_t = index.doc_freqs.get(token, 0)
        idf = math.log((index.num_documents - n_t + 0.5) / (n_t + 0.5) + 1.0)
        denom = f + BM25_K1 * (1 - BM25_B + BM25_B * dl / index.avg_doc_length)
        score += idf * (f * (BM25_K1 + 1)) / denom
    return score


def retrieve_bm25(index: Bm25Index, query: str, *, top_k: int) -> list[RetrievalResult]:
    query_tokens = tokenize(query)
    scored = [(chunk, _bm25_score(index, query_tokens, chunk.chunk_id)) for chunk in index.chunks]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [RetrievalResult(chunk=chunk, score=score) for chunk, score in scored[:top_k]]


def _minmax_normalize(results: list[RetrievalResult]) -> dict[str, float]:
    if not results:
        return {}
    scores = [r.score for r in results]
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return {r.chunk.chunk_id: 1.0 for r in results}
    return {r.chunk.chunk_id: (r.score - lo) / (hi - lo) for r in results}


def retrieve_bm25_semantic_hybrid(
    bm25_index: Bm25Index, semantic_index: SemanticRagIndex, query: str, *,
    top_k: int, pool_k: int, alpha: float = DEFAULT_HYBRID_ALPHA, embedder: object | None = None,
) -> list[RetrievalResult]:
    """Réf. §2.A : même formule de fusion alpha que la baseline, mais le
    cote lexical est BM25 (normalise min-max sur le pool, les scores BM25
    n'etant pas bornes) au lieu du TF-IDF hashe cosinus (deja dans [0,1])."""
    bm25_results = retrieve_bm25(bm25_index, query, top_k=pool_k)
    semantic_results = retrieve_semantic(semantic_index, query, top_k=pool_k, embedder=embedder)
    bm25_norm = _minmax_normalize(bm25_results)
    chunk_by_id = {r.chunk.chunk_id: r.chunk for r in bm25_results}
    semantic_by_id = {r.chunk.chunk_id: r.score for r in semantic_results}
    for r in semantic_results:
        chunk_by_id.setdefault(r.chunk.chunk_id, r.chunk)

    all_ids = set(bm25_norm) | set(semantic_by_id)
    fused = []
    for chunk_id in all_ids:
        hybrid = alpha * semantic_by_id.get(chunk_id, 0.0) + (1 - alpha) * bm25_norm.get(chunk_id, 0.0)
        fused.append(RetrievalResult(chunk=chunk_by_id[chunk_id], score=hybrid))
    fused.sort(key=lambda r: r.score, reverse=True)
    return fused[:top_k]


# ---------------------------------------------------------------------------
# B. Instruction de requete BGE (recommandation officielle du modele,
# cote requete uniquement) -- reference : carte de modele BAAI/bge-*.
# ---------------------------------------------------------------------------

BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


def retrieve_hybrid_with_bge_instruction(
    lexical_index: RagIndex, semantic_index: SemanticRagIndex, query: str, *,
    top_k: int, pool_k: int | None = None, alpha: float = DEFAULT_HYBRID_ALPHA, embedder: object | None = None,
) -> list[RetrievalResult]:
    """Réf. §2.B : identique a `retrieve_hybrid` sauf que la requete
    envoyee au cote SEMANTIQUE porte le prefixe d'instruction BGE (le
    cote lexical recoit le texte brut, la comparaison lexicale n'a pas de
    notion d'instruction)."""
    effective_pool_k = pool_k if pool_k is not None else max(top_k, DEFAULT_POOL_K)
    lexical_results = retrieve(lexical_index, query, top_k=effective_pool_k)
    semantic_results = retrieve_semantic(semantic_index, BGE_QUERY_INSTRUCTION + query, top_k=effective_pool_k, embedder=embedder)

    lexical_by_id = {r.chunk.chunk_id: r.score for r in lexical_results}
    semantic_by_id = {r.chunk.chunk_id: r.score for r in semantic_results}
    chunk_by_id = {r.chunk.chunk_id: r.chunk for r in lexical_results}
    for r in semantic_results:
        chunk_by_id.setdefault(r.chunk.chunk_id, r.chunk)

    all_ids = set(lexical_by_id) | set(semantic_by_id)
    fused = [
        RetrievalResult(chunk=chunk_by_id[cid], score=alpha * semantic_by_id.get(cid, 0.0) + (1 - alpha) * lexical_by_id.get(cid, 0.0))
        for cid in all_ids
    ]
    fused.sort(key=lambda r: r.score, reverse=True)
    return fused[:top_k]


# ---------------------------------------------------------------------------
# C. Reciprocal Rank Fusion -- k=60 (valeur standard, Cormack et al. 2009),
# jamais ajustee sur nos donnees.
# ---------------------------------------------------------------------------

RRF_K = 60


def retrieve_rrf(
    lexical_index: RagIndex, semantic_index: SemanticRagIndex, query: str, *,
    top_k: int, pool_k: int, embedder: object | None = None,
) -> list[RetrievalResult]:
    lexical_results = retrieve(lexical_index, query, top_k=pool_k)
    semantic_results = retrieve_semantic(semantic_index, query, top_k=pool_k, embedder=embedder)

    chunk_by_id = {r.chunk.chunk_id: r.chunk for r in lexical_results}
    for r in semantic_results:
        chunk_by_id.setdefault(r.chunk.chunk_id, r.chunk)

    rrf_scores: dict[str, float] = {}
    for rank, r in enumerate(lexical_results, start=1):
        rrf_scores[r.chunk.chunk_id] = rrf_scores.get(r.chunk.chunk_id, 0.0) + 1.0 / (RRF_K + rank)
    for rank, r in enumerate(semantic_results, start=1):
        rrf_scores[r.chunk.chunk_id] = rrf_scores.get(r.chunk.chunk_id, 0.0) + 1.0 / (RRF_K + rank)

    ranked = sorted(rrf_scores.items(), key=lambda pair: pair[1], reverse=True)
    return [RetrievalResult(chunk=chunk_by_id[cid], score=score) for cid, score in ranked[:top_k]]


# ---------------------------------------------------------------------------
# E. Deduplication quasi-exacte (Jaccard de tokens) du pool, AVANT
# troncature -- reduit le gaspillage du budget de reclassement sur des
# passages redondants.
# ---------------------------------------------------------------------------

DEDUP_JACCARD_THRESHOLD = 0.8


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def deduplicate_pool(results: list[RetrievalResult], *, threshold: float = DEDUP_JACCARD_THRESHOLD) -> list[RetrievalResult]:
    """Réf. §2.E : parcourt `results` (deja trie par pertinence
    decroissante) et supprime tout chunk dont le contenu (ensemble de
    tokens) chevauche a >= `threshold` un chunk DEJA CONSERVE de rang
    superieur -- le chunk le mieux classe des deux est toujours garde."""
    kept: list[RetrievalResult] = []
    kept_token_sets: list[set[str]] = []
    for result in results:
        tokens = set(tokenize(result.chunk.text))
        if any(_jaccard(tokens, kept_tokens) >= threshold for kept_tokens in kept_token_sets):
            continue
        kept.append(result)
        kept_token_sets.append(tokens)
    return kept


# ---------------------------------------------------------------------------
# F. Routage par type de source determine UNIQUEMENT depuis le texte de la
# requete -- regles lexicales deterministes, aucune fuite de verite
# terrain. Repli explicite (aucune restriction) si aucune regle ne
# correspond, pour ne jamais reduire silencieusement le rappel.
# ---------------------------------------------------------------------------

_ATTACK_PATTERN = re.compile(r"\bT\d{4}(\.\d{3})?\b", re.IGNORECASE)
_ROUTING_KEYWORDS: dict[str, tuple[str, ...]] = {
    "attack": ("adversary", "adversaries", "attacker", "technique", "exploit", "exfiltrat", "credential", "brute force", "phishing", "command", "script"),
    "engage": ("monitor", "detect", "capture", "analyze", "activity", "traffic", "log"),
    "d3fend": ("decoy", "honeypot", "honeyfile", "honeytoken", "deceive", "artifact", "concept"),
    "literature": ("study", "research", "empirical", "taxonomy", "article", "paper", "review"),
}


def guess_source_types_from_query(query: str) -> tuple[str, ...] | None:
    """Retourne un tuple de `source_type` a privilegier, ou `None` si
    aucune regle ne correspond avec confiance (repli : pas de routage)."""
    query_lower = query.lower()
    if _ATTACK_PATTERN.search(query):
        return ("attack",)
    matched = [source for source, keywords in _ROUTING_KEYWORDS.items() if any(kw in query_lower for kw in keywords)]
    if not matched:
        return None
    return tuple(matched)


def retrieve_hybrid_with_routing(
    lexical_index: RagIndex, semantic_index: SemanticRagIndex, query: str, *,
    top_k: int, pool_k: int | None = None, alpha: float = DEFAULT_HYBRID_ALPHA, embedder: object | None = None,
) -> list[RetrievalResult]:
    """Réf. §2.F : execute le retrieval hybride normal (meme pool que la
    baseline), puis, SI le routage identifie un/des type(s) de source
    avec confiance, place les chunks de ce(s) type(s) en tete (stable,
    ordre de pertinence conserve a l'interieur de chaque groupe) -- ne
    supprime JAMAIS un resultat, pour ne pas risquer de perdre un chunk
    pertinent d'un autre type si le routage se trompe."""
    from src.rag_evidence import retrieve_large_pool

    effective_pool_k = pool_k if pool_k is not None else DEFAULT_POOL_K
    pool = retrieve_large_pool(lexical_index, semantic_index, query, pool_k=effective_pool_k, alpha=alpha, embedder=embedder)
    results = [RetrievalResult(chunk=c.chunk, score=c.hybrid_score) for c in pool]
    guessed = guess_source_types_from_query(query)
    if not guessed:
        return results[:top_k]
    preferred = [r for r in results if r.chunk.source_type in guessed]
    other = [r for r in results if r.chunk.source_type not in guessed]
    return (preferred + other)[:top_k]


# ---------------------------------------------------------------------------
# D. Augmentation controlee du pool -- simple parametre pool_k reutilise
# par `src.rag_evidence.retrieve_large_pool`/`src.rag_retriever.retrieve_hybrid`
# (voir campagne d'evaluation : compare pool_k=20 (defaut production) vs
# pool_k=40, meme reste du pipeline).
# ---------------------------------------------------------------------------

DEFAULT_POOL_K = 20
AUGMENTED_POOL_K = 40
