"""
Réf. tâche « améliorer réellement la qualité et la latence du moteur RAG »
§2 : orchestre l'ablation A-G sur le jeu DEV du benchmark équilibré, gèle
UNE configuration combinée à partir des seules preuves DEV (jamais du jeu
de test), puis confirme cette configuration UNE SEULE FOIS sur le jeu TEST.

Décision de conservation (§2, pré-enregistrée AVANT toute mesure) : une
variante est retenue pour la configuration combinée si, sur DEV,
`mean_recall_at_5` s'améliore ET `mean_hit_rate_at_5` ne régresse pas.
Rejetée sinon, avec la métrique précise en cause -- jamais une décision
esthétique ou a posteriori sur le jeu de test.

Exécution :
    python -m tools.chapter4_evaluation.run_improvement_campaign
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from src.rag_indexer import RagIndex, SemanticRagIndex, build_index, build_semantic_index
from src.rag_retriever import DEFAULT_HYBRID_ALPHA, RetrievalResult, retrieve, retrieve_semantic
from src.semantic_embedder import load_embedder
from tools.chapter4_evaluation.metrics import evaluate_queries
from tools.chapter4_evaluation.retrieval_campaign import load_full_corpus_chunks
from tools.chapter4_evaluation.retrieval_improvements import (
    BGE_QUERY_INSTRUCTION,
    RRF_K,
    Bm25Index,
    build_bm25_index,
    deduplicate_pool,
    guess_source_types_from_query,
    retrieve_bm25,
    _minmax_normalize,
)

OUT_DIR = Path("docs/chapter4/evaluation/outputs")
BENCHMARK_PATH = OUT_DIR / "benchmark_balanced.json"

RECALL_TOLERANCE = 1e-9


@dataclass(frozen=True)
class Indices:
    lexical: RagIndex
    semantic: SemanticRagIndex
    bm25: Bm25Index
    embedder: object


def load_indices() -> Indices:
    chunks = load_full_corpus_chunks()
    embedder = load_embedder()
    lexical = build_index(chunks)
    semantic = build_semantic_index(chunks, embedder=embedder)
    bm25 = build_bm25_index(chunks)
    return Indices(lexical=lexical, semantic=semantic, bm25=bm25, embedder=embedder)


def load_benchmark_split(split: str) -> list[dict]:
    benchmark = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    return [q for q in benchmark["queries"] if q["split"] == split]


# ---------------------------------------------------------------------------
# Configuration combinee -- un seul point de dispatch, pilote par des
# indicateurs, pour eviter une explosion combinatoire de fonctions.
# ---------------------------------------------------------------------------


PRODUCTION_DEFAULT_POOL_K = 20  # src.rag_config.DEFAULT_RETRIEVAL_CANDIDATES -- pool reel de production,
# INDEPENDANT de final_top_k (a la difference du pool_k auto-calcule par
# l'API historique retrieve_hybrid() seule) -- reference correcte pour
# isoler l'effet de l'augmentation de pool (variante D).


def _lexical_side(indices: Indices, query: str, *, use_bm25: bool, pool_k: int) -> list[RetrievalResult]:
    if use_bm25:
        return retrieve_bm25(indices.bm25, query, top_k=pool_k)
    return retrieve(indices.lexical, query, top_k=pool_k)


def _semantic_side(indices: Indices, query: str, *, use_bge_instruction: bool, pool_k: int) -> list[RetrievalResult]:
    effective_query = (BGE_QUERY_INSTRUCTION + query) if use_bge_instruction else query
    return retrieve_semantic(indices.semantic, effective_query, top_k=pool_k, embedder=indices.embedder)


def retrieve_configured(
    indices: Indices, query: str, *, top_k: int,
    use_bm25: bool = False, use_bge_instruction: bool = False, fusion: str = "alpha",
    pool_k: int | None = None, use_dedup: bool = False, use_routing: bool = False,
) -> list[RetrievalResult]:
    """Réf. §2 : dispatcher COMPOSITIONNEL -- chaque dimension (A cote
    lexical, B cote semantique, C methode de fusion, D taille de pool, E
    deduplication, F routage) est appliquee independamment des autres,
    pour que la configuration combinee (§2, apres decision sur DEV) puisse
    reellement cumuler plusieurs ameliorations retenues simultanement, au
    lieu de n'en appliquer qu'une seule par priorite arbitraire.

    Chemin lexical/semantique : `retrieve`/`retrieve_semantic`
    (`src.rag_retriever`), memes fonctions que le pool de production
    (`src.rag_evidence.retrieve_large_pool`, stage A) -- jamais l'API
    legacy `retrieve_hybrid` seule, dont le parametre `top_k` conflate a
    tort taille de sortie et taille de pool de fusion."""
    effective_pool_k = pool_k if pool_k is not None else PRODUCTION_DEFAULT_POOL_K

    lexical_results = _lexical_side(indices, query, use_bm25=use_bm25, pool_k=effective_pool_k)
    semantic_results = _semantic_side(indices, query, use_bge_instruction=use_bge_instruction, pool_k=effective_pool_k)

    chunk_by_id = {r.chunk.chunk_id: r.chunk for r in lexical_results}
    for r in semantic_results:
        chunk_by_id.setdefault(r.chunk.chunk_id, r.chunk)

    if fusion == "rrf":
        rrf_scores: dict[str, float] = {}
        for rank, r in enumerate(lexical_results, start=1):
            rrf_scores[r.chunk.chunk_id] = rrf_scores.get(r.chunk.chunk_id, 0.0) + 1.0 / (RRF_K + rank)
        for rank, r in enumerate(semantic_results, start=1):
            rrf_scores[r.chunk.chunk_id] = rrf_scores.get(r.chunk.chunk_id, 0.0) + 1.0 / (RRF_K + rank)
        results = [
            RetrievalResult(chunk=chunk_by_id[cid], score=score)
            for cid, score in sorted(rrf_scores.items(), key=lambda pair: pair[1], reverse=True)
        ]
    else:
        lexical_by_id = _minmax_normalize(lexical_results) if use_bm25 else {r.chunk.chunk_id: r.score for r in lexical_results}
        semantic_by_id = {r.chunk.chunk_id: r.score for r in semantic_results}
        all_ids = set(lexical_by_id) | set(semantic_by_id)
        results = [
            RetrievalResult(
                chunk=chunk_by_id[cid],
                score=DEFAULT_HYBRID_ALPHA * semantic_by_id.get(cid, 0.0) + (1 - DEFAULT_HYBRID_ALPHA) * lexical_by_id.get(cid, 0.0),
            )
            for cid in all_ids
        ]
        results.sort(key=lambda r: r.score, reverse=True)

    if use_routing:
        guessed = guess_source_types_from_query(query)
        if guessed:
            preferred = [r for r in results if r.chunk.source_type in guessed]
            other = [r for r in results if r.chunk.source_type not in guessed]
            results = preferred + other

    if use_dedup:
        results = deduplicate_pool(results)

    return results[:top_k]


def _retrieved_ids_for_queries(indices: Indices, queries: list[dict], retrieve_fn, top_k: int) -> dict[str, list[str]]:
    return {q["query_id"]: [r.chunk.chunk_id for r in retrieve_fn(indices, q["query"], top_k=top_k)] for q in queries}


def evaluate_variant(indices: Indices, queries: list[dict], retrieve_fn, **kwargs) -> dict:
    retrieved = {q["query_id"]: [r.chunk.chunk_id for r in retrieve_fn(indices, q["query"], top_k=10, **kwargs)] for q in queries}
    return evaluate_queries(retrieved, queries, ks=(5, 10))


def decide_keep(baseline: dict, variant: dict) -> tuple[bool, str]:
    recall_delta = variant["mean_recall_at_5"] - baseline["mean_recall_at_5"]
    hit_rate_delta = variant["mean_hit_rate_at_5"] - baseline["mean_hit_rate_at_5"]
    if recall_delta > RECALL_TOLERANCE and hit_rate_delta >= -RECALL_TOLERANCE:
        return True, f"mean_recall_at_5 ameliore ({recall_delta:+.4f}), hit_rate_at_5 non degrade ({hit_rate_delta:+.4f})."
    reasons = []
    if recall_delta <= RECALL_TOLERANCE:
        reasons.append(f"mean_recall_at_5 non ameliore ({recall_delta:+.4f})")
    if hit_rate_delta < -RECALL_TOLERANCE:
        reasons.append(f"mean_hit_rate_at_5 degrade ({hit_rate_delta:+.4f})")
    return False, "; ".join(reasons)


def _strip_per_query(metrics: dict) -> dict:
    return {k: v for k, v in metrics.items() if k != "per_query"}


def run_ablation(indices: Indices, dev_queries: list[dict]) -> dict:
    print(f"Ablation A-F sur {len(dev_queries)} requetes DEV...")
    baseline = evaluate_variant(indices, dev_queries, lambda idx, q, top_k: retrieve_configured(idx, q, top_k=top_k))

    variants = {
        "A_bm25": dict(use_bm25=True),
        "B_bge_instruction": dict(use_bge_instruction=True),
        "C_rrf": dict(fusion="rrf"),
        "D_pool_augmentation": dict(pool_k=40),
        "E_dedup": dict(use_dedup=True),
        "F_source_routing": dict(use_routing=True),
    }

    ablation = {"baseline": _strip_per_query(baseline)}
    decisions = {}
    for name, kwargs in variants.items():
        print(f"  variante {name}...")
        result = evaluate_variant(indices, dev_queries, lambda idx, q, top_k, kw=kwargs: retrieve_configured(idx, q, top_k=top_k, **kw))
        keep, reason = decide_keep(baseline, result)
        ablation[name] = {
            **_strip_per_query(result),
            "delta_vs_baseline": {
                metric: result[metric] - baseline[metric]
                for metric in ("mean_recall_at_5", "mean_recall_at_10", "mean_mrr_at_5", "mean_ndcg_at_5", "mean_hit_rate_at_5")
            },
            "kept": keep,
            "decision_reason": reason,
        }
        decisions[name] = keep

    return ablation, decisions


def run_enriched_query_ablation(indices: Indices, all_queries: list[dict]) -> dict:
    """Réf. §2.G : requetes ATT&CK/Engage/litterature nouvelles possedent
    a la fois une version enrichie (`query`) et minimale (`query_minimal`,
    juste le nom de la technique/du mecanisme) -- meme verite terrain,
    seul le texte de requete change."""
    candidates = [q for q in all_queries if q.get("query_minimal")]
    print(f"Ablation G (requete enrichie vs minimale) sur {len(candidates)} requetes ({'/'.join(sorted({q['split'] for q in candidates}))})...")

    enriched = {q["query_id"]: [r.chunk.chunk_id for r in retrieve_configured(indices, q["query"], top_k=10)] for q in candidates}
    minimal = {q["query_id"]: [r.chunk.chunk_id for r in retrieve_configured(indices, q["query_minimal"], top_k=10)] for q in candidates}

    enriched_metrics = _strip_per_query(evaluate_queries(enriched, candidates, ks=(5, 10)))
    minimal_metrics = _strip_per_query(evaluate_queries(minimal, candidates, ks=(5, 10)))
    keep, reason = decide_keep(minimal_metrics, enriched_metrics)
    return {
        "query_count": len(candidates),
        "query_ids": [q["query_id"] for q in candidates],
        "minimal_query": minimal_metrics,
        "enriched_query": enriched_metrics,
        "delta_enriched_minus_minimal": {
            metric: enriched_metrics[metric] - minimal_metrics[metric]
            for metric in ("mean_recall_at_5", "mean_recall_at_10", "mean_mrr_at_5", "mean_ndcg_at_5", "mean_hit_rate_at_5")
        },
        "kept": keep,
        "decision_reason": reason,
    }


def build_combined_config(decisions: dict) -> dict:
    config = {}
    if decisions.get("A_bm25"):
        config["use_bm25"] = True
    if decisions.get("B_bge_instruction"):
        config["use_bge_instruction"] = True
    if decisions.get("C_rrf"):
        config["fusion"] = "rrf"
    if decisions.get("D_pool_augmentation"):
        config["pool_k"] = 40
    if decisions.get("E_dedup"):
        config["use_dedup"] = True
    if decisions.get("F_source_routing"):
        config["use_routing"] = True
    return config


def run_final_test(indices: Indices, test_queries: list[dict], combined_config: dict) -> dict:
    print(f"Confirmation UNIQUE sur {len(test_queries)} requetes TEST (configuration deja gelee)...")
    baseline = _strip_per_query(evaluate_variant(indices, test_queries, lambda idx, q, top_k: retrieve_configured(idx, q, top_k=top_k)))
    improved = _strip_per_query(evaluate_variant(indices, test_queries, lambda idx, q, top_k: retrieve_configured(idx, q, top_k=top_k, **combined_config)))

    delta_abs = {
        metric: improved[metric] - baseline[metric]
        for metric in ("mean_recall_at_5", "mean_recall_at_10", "mean_mrr_at_5", "mean_ndcg_at_5", "mean_hit_rate_at_5")
    }
    delta_rel = {
        metric: (delta_abs[metric] / baseline[metric] if baseline[metric] > 0 else None)
        for metric in delta_abs
    }
    return {
        "query_count": len(test_queries),
        "combined_config": combined_config,
        "composition_note": (
            "retrieve_configured() compose reellement toutes les dimensions retenues simultanement "
            "(cote lexical A, cote semantique B, fusion C, taille de pool D, routage F appliques en "
            "serie, deduplication E en dernier) -- ce n'est jamais une seule variante appliquee par "
            "priorite arbitraire."
        ),
        "baseline": baseline,
        "improved": improved,
        "delta_absolute": delta_abs,
        "delta_relative": delta_rel,
        "improved_over_baseline_on_recall_at_5": delta_abs["mean_recall_at_5"] > 0,
    }


def main() -> dict:
    t0 = time.time()
    indices = load_indices()
    dev_queries = load_benchmark_split("dev")
    test_queries = load_benchmark_split("test")
    all_queries = dev_queries + test_queries

    ablation, decisions = run_ablation(indices, dev_queries)
    g_result = run_enriched_query_ablation(indices, all_queries)
    ablation["G_enriched_query"] = g_result
    decisions["G_enriched_query"] = g_result["kept"]

    combined_config = build_combined_config(decisions)
    final_test = run_final_test(indices, test_queries, combined_config)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "retrieval_improvements_ablation.json").write_text(
        json.dumps({"dev_query_count": len(dev_queries), "ablation": ablation, "decisions": decisions}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (OUT_DIR / "retrieval_final_test.json").write_text(json.dumps(final_test, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Termine en {time.time()-t0:.1f}s.")
    print(f"Decisions : {decisions}")
    print(f"Configuration combinee retenue (DEV) : {combined_config}")
    print(f"Test (confirmation unique) -- Recall@5 baseline={final_test['baseline']['mean_recall_at_5']:.3f}, "
          f"ameliore={final_test['improved']['mean_recall_at_5']:.3f}")
    print(f"Ecrit : retrieval_improvements_ablation.json, retrieval_final_test.json")
    return {"ablation": ablation, "decisions": decisions, "combined_config": combined_config, "final_test": final_test}


if __name__ == "__main__":
    main()
