"""
Réf. architecture : CLAUDE.md §9.1 (pipeline RAG) — réf. tâche « comparer
RAG lexical (TF-IDF haché) vs RAG sémantique (embeddings) et démontrer
l'amélioration, pas seulement l'affirmer ».

Charge le jeu de requêtes d'évaluation `data/rag/rag_eval_queries.json`
(vérité terrain construite par relecture humaine directe du corpus réel,
voir `justification` par requête), construit les deux index sur le MÊME
corpus réel (`data/deception/staging/*.json`), exécute chaque requête sur
les deux moteurs, et calcule Recall@5 / MRR@5 / nDCG@5 réellement — aucun
résultat n'est fabriqué ou supposé.

Exécution :
    python -m examples.rag_semantic_evaluation

Sorties :
    docs/chapter4/outputs/rag_semantic_evaluation.json
    docs/chapter4/outputs/rag_semantic_evaluation.txt
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from src.rag_indexer import build_index, build_semantic_index, load_d3fend_chunks, load_engage_chunks, load_literature_chunks
from src.rag_retriever import retrieve, retrieve_hybrid, retrieve_semantic
from src.semantic_embedder import load_embedder

STAGING_DIR = Path("data/deception/staging")
QUERIES_PATH = Path("data/rag/rag_eval_queries.json")
OUT_DIR = Path("docs/chapter4/outputs")
TOP_K = 5
HYBRID_ALPHAS_TO_TEST = (0.5, 0.7, 0.8, 0.9)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_all_chunks():
    d3fend_chunks = load_d3fend_chunks(load_json(STAGING_DIR / "d3fend_deception_seed_1.5.0.json"))
    engage_chunks = load_engage_chunks(load_json(STAGING_DIR / "engage_activity_seed_1.0.json"))
    literature_chunks = load_literature_chunks(load_json(STAGING_DIR / "literature_evidence_seed_1.2.json"))
    return d3fend_chunks + engage_chunks + literature_chunks


def recall_at_k(retrieved_ids: list[str], expected_ids: set[str], k: int) -> float:
    if not expected_ids:
        raise ValueError("expected_ids ne doit jamais être vide (vérité terrain absente).")
    hits = len(set(retrieved_ids[:k]) & expected_ids)
    return hits / len(expected_ids)


def mrr_at_k(retrieved_ids: list[str], expected_ids: set[str], k: int) -> float:
    for rank, chunk_id in enumerate(retrieved_ids[:k], start=1):
        if chunk_id in expected_ids:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved_ids: list[str], expected_ids: set[str], k: int) -> float:
    dcg = 0.0
    for rank, chunk_id in enumerate(retrieved_ids[:k], start=1):
        relevance = 1.0 if chunk_id in expected_ids else 0.0
        dcg += relevance / math.log2(rank + 1)
    ideal_hits = min(len(expected_ids), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def evaluate_engine(name: str, retrieved_by_query: dict[str, list[str]], queries: list[dict]) -> dict:
    per_query = []
    for query in queries:
        expected = set(query["expected_chunk_ids"])
        retrieved = retrieved_by_query[query["query_id"]]
        per_query.append(
            {
                "query_id": query["query_id"],
                "topic": query["topic"],
                "recall_at_5": recall_at_k(retrieved, expected, TOP_K),
                "mrr_at_5": mrr_at_k(retrieved, expected, TOP_K),
                "ndcg_at_5": ndcg_at_k(retrieved, expected, TOP_K),
                "retrieved_top5": retrieved[:TOP_K],
            }
        )
    n = len(per_query)
    return {
        "engine": name,
        "mean_recall_at_5": sum(q["recall_at_5"] for q in per_query) / n,
        "mean_mrr_at_5": sum(q["mrr_at_5"] for q in per_query) / n,
        "mean_ndcg_at_5": sum(q["ndcg_at_5"] for q in per_query) / n,
        "per_query": per_query,
    }


def main() -> None:
    eval_spec = load_json(QUERIES_PATH)
    queries = eval_spec["queries"]

    all_chunks = load_all_chunks()
    lexical_index = build_index(all_chunks)

    embedder = load_embedder()
    semantic_index = build_semantic_index(all_chunks, embedder=embedder)

    # top_k élargi pour le rappel@5 brut (au-delà de 5, sert uniquement à
    # illustrer le classement complet dans le JSON de sortie).
    lexical_retrieved: dict[str, list[str]] = {
        query["query_id"]: [r.chunk.chunk_id for r in retrieve(lexical_index, query["query"], top_k=TOP_K)]
        for query in queries
    }
    semantic_retrieved: dict[str, list[str]] = {
        query["query_id"]: [
            r.chunk.chunk_id for r in retrieve_semantic(semantic_index, query["query"], top_k=TOP_K, embedder=embedder)
        ]
        for query in queries
    }

    lexical_eval = evaluate_engine("lexical_tfidf", lexical_retrieved, queries)
    semantic_eval = evaluate_engine("semantic_embeddings", semantic_retrieved, queries)

    # --- Phase 3 : fusion hybride (src.rag_retriever.retrieve_hybrid),
    # seulement évaluée ici pour décider si elle apporte un gain réel ---
    hybrid_candidates = []
    for alpha in HYBRID_ALPHAS_TO_TEST:
        hybrid_retrieved = {
            query["query_id"]: [
                r.chunk.chunk_id
                for r in retrieve_hybrid(lexical_index, semantic_index, query["query"], top_k=TOP_K, alpha=alpha, embedder=embedder)
            ]
            for query in queries
        }
        hybrid_eval = evaluate_engine(f"hybrid_alpha_{alpha}", hybrid_retrieved, queries)
        hybrid_candidates.append((alpha, hybrid_eval))

    best_alpha, best_hybrid_eval = max(hybrid_candidates, key=lambda pair: pair[1]["mean_recall_at_5"])
    semantic_alone_is_best = semantic_eval["mean_recall_at_5"] >= best_hybrid_eval["mean_recall_at_5"]

    decision = {
        "hybrid_tested_alphas": list(HYBRID_ALPHAS_TO_TEST),
        "hybrid_results_by_alpha": {
            f"alpha_{alpha}": {
                "mean_recall_at_5": ev["mean_recall_at_5"],
                "mean_mrr_at_5": ev["mean_mrr_at_5"],
                "mean_ndcg_at_5": ev["mean_ndcg_at_5"],
            }
            for alpha, ev in hybrid_candidates
        },
        "best_alpha_by_recall_at_5": best_alpha,
        "semantic_alone_mean_recall_at_5": semantic_eval["mean_recall_at_5"],
        "best_hybrid_mean_recall_at_5": best_hybrid_eval["mean_recall_at_5"],
        "semantic_alone_is_best_or_tied": semantic_alone_is_best,
        "final_mode_selected": "semantic" if semantic_alone_is_best else f"hybrid_alpha_{best_alpha}",
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result = {
        "corpus": {
            "chunk_count": len(all_chunks),
            "embedding_model": semantic_index.embedding_model,
            "embedding_dimension": semantic_index.dimension,
            "vector_index_backend": semantic_index.backend,
        },
        "top_k": TOP_K,
        "query_count": len(queries),
        "lexical_tfidf": lexical_eval,
        "semantic_embeddings": semantic_eval,
        "hybrid_decision": decision,
    }
    (OUT_DIR / "rag_semantic_evaluation.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "RAG - Evaluation lexicale (TF-IDF) vs semantique (embeddings) - reel",
        "-" * 78,
        f"Corpus : {len(all_chunks)} chunks reels (data/deception/staging/*.json)",
        f"Modele semantique : {semantic_index.embedding_model} (dim={semantic_index.dimension}, backend={semantic_index.backend})",
        f"Requetes : {len(queries)} (data/rag/rag_eval_queries.json)",
        f"Metrique top-k : {TOP_K}",
        "-" * 78,
        f"{'Moteur':<22}{'Recall@5':<12}{'MRR@5':<12}{'nDCG@5':<12}",
        f"{'Lexical (TF-IDF)':<22}{lexical_eval['mean_recall_at_5']:<12.3f}{lexical_eval['mean_mrr_at_5']:<12.3f}{lexical_eval['mean_ndcg_at_5']:<12.3f}",
        f"{'Semantique':<22}{semantic_eval['mean_recall_at_5']:<12.3f}{semantic_eval['mean_mrr_at_5']:<12.3f}{semantic_eval['mean_ndcg_at_5']:<12.3f}",
        f"{'Hybride (meilleur)':<22}{best_hybrid_eval['mean_recall_at_5']:<12.3f}{best_hybrid_eval['mean_mrr_at_5']:<12.3f}{best_hybrid_eval['mean_ndcg_at_5']:<12.3f}  (alpha={best_alpha})",
        "-" * 78,
        f"Mode retenu (reel, calcule) : {decision['final_mode_selected']}",
        "-" * 78,
        f"{'Requete':<22}{'Topic':<26}{'Recall@5 lex':<14}{'Recall@5 sem':<14}",
    ]
    lexical_by_id = {q["query_id"]: q for q in lexical_eval["per_query"]}
    semantic_by_id = {q["query_id"]: q for q in semantic_eval["per_query"]}
    for query in queries:
        qid = query["query_id"]
        lines.append(
            f"{qid:<22}{query['topic'][:25]:<26}"
            f"{lexical_by_id[qid]['recall_at_5']:<14.3f}{semantic_by_id[qid]['recall_at_5']:<14.3f}"
        )
    lines.append("-" * 78)
    text = "\n".join(lines) + "\n"
    (OUT_DIR / "rag_semantic_evaluation.txt").write_text(text, encoding="utf-8")

    print(text)
    print(f"JSON : {OUT_DIR / 'rag_semantic_evaluation.json'}")


if __name__ == "__main__":
    main()
