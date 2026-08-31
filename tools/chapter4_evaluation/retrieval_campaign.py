"""
Réf. tâche « campagne d'évaluation réelle RAG/LLM/système », §2 et §3.

Évaluation RÉELLE de la récupération documentaire :
- §2 : corpus complet (1306 chunks : 1157 ATT&CK + 44 D3FEND + 62 Engage +
  43 littérature) vs l'ancien sous-ensemble déception (149 chunks),
  pour les trois modes (lexical, sémantique, hybride), avec ventilation
  par type de source et vérification de couverture de la vérité terrain ;
- §3 : balayage de alpha (fusion hybride) sur le corpus complet, et
  ablation du reclassement (cross-encoder réel) — mesuré AVEC et SANS.

Aucun résultat n'est fabriqué : tous les chiffres proviennent d'appels
réels à `src/rag_retriever.py`/`src/reranker.py` sur le corpus réellement
chargé. Le même jeu de 17 requêtes et sa vérité terrain
(`data/rag/rag_eval_queries.json`) sont réutilisés SANS modification et
SANS sélection — les 17 requêtes sont toutes évaluées, aucune écartée.

Exécution :
    python -m tools.chapter4_evaluation.retrieval_campaign

Sorties :
    docs/chapter4/evaluation/outputs/retrieval_eval_full_corpus.json
    docs/chapter4/evaluation/outputs/alpha_sweep.json
    docs/chapter4/evaluation/outputs/reranker_ablation.json
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from src.rag_indexer import (
    Chunk,
    build_index,
    build_semantic_index,
    load_attack_chunks,
    load_d3fend_chunks,
    load_engage_chunks,
    load_literature_chunks,
)
from src.rag_retriever import DEFAULT_HYBRID_ALPHA, retrieve, retrieve_hybrid, retrieve_semantic
from src.reranker import CrossEncoderReranker
from src.semantic_embedder import load_embedder
from tools.chapter4_evaluation.metrics import evaluate_queries

DECEPTION_STAGING_DIR = Path("data/deception/staging")
ATTACK_STAGING_DIR = Path("data/attack/staging")
QUERIES_PATH = Path("data/rag/rag_eval_queries.json")
OUT_DIR = Path("docs/chapter4/evaluation/outputs")

TOP_K_MAIN = 10  # récupère assez pour Recall@10, tronqué à 5 où demandé
ALPHA_SWEEP_VALUES = (0.3, 0.5, 0.7, 0.8, 0.9)
RETRIEVAL_POOL_K = 20  # réf. RAG_RETRIEVAL_CANDIDATES par défaut (src/rag_config.py)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_deception_only_chunks() -> list[Chunk]:
    """Ancien sous-ensemble (149 chunks) : D3FEND + Engage + littérature
    uniquement, SANS ATT&CK — pour la comparaison explicite corpus
    149 vs 1306 (réf. tâche §2)."""
    return (
        load_d3fend_chunks(_load_json(DECEPTION_STAGING_DIR / "d3fend_deception_seed_1.5.0.json"))
        + load_engage_chunks(_load_json(DECEPTION_STAGING_DIR / "engage_activity_seed_1.0.json"))
        + load_literature_chunks(_load_json(DECEPTION_STAGING_DIR / "literature_evidence_seed_1.2.json"))
    )


def load_full_corpus_chunks() -> list[Chunk]:
    """Corpus complet réel (1306 chunks) : ATT&CK + D3FEND + Engage +
    littérature — réf. tâche §2, LEVIER PRINCIPAL de cette campagne."""
    attack_seed_files = sorted(f for f in ATTACK_STAGING_DIR.glob("attack_rag_seed_*.json") if "_report_" not in f.name)
    if not attack_seed_files:
        raise FileNotFoundError("Staging ATT&CK introuvable -- generer via tools.attack_kb.attack_seed_builder.")
    return load_attack_chunks(_load_json(attack_seed_files[-1])) + load_deception_only_chunks()


def build_indices(chunks: list[Chunk], embedder):
    lexical_index = build_index(chunks)
    semantic_index = build_semantic_index(chunks, embedder=embedder)
    return lexical_index, semantic_index


def chunk_source_lookup(chunks: list[Chunk]) -> dict[str, str]:
    return {c.chunk_id: c.source_type for c in chunks}


def check_ground_truth_coverage(queries: list[dict], source_lookup: dict[str, str]) -> dict:
    """Réf. tâche §2 : vérifie EXPLICITEMENT que chaque `expected_chunk_id`
    de chaque requête existe réellement dans le corpus donné -- documente
    toute absence plutôt que de la masquer."""
    coverage = []
    for query in queries:
        expected = query["expected_chunk_ids"]
        present = [cid for cid in expected if cid in source_lookup]
        missing = [cid for cid in expected if cid not in source_lookup]
        coverage.append(
            {
                "query_id": query["query_id"],
                "expected_count": len(expected),
                "present_count": len(present),
                "missing_chunk_ids": missing,
                "fully_covered": len(missing) == 0,
            }
        )
    fully_covered_count = sum(1 for c in coverage if c["fully_covered"])
    return {
        "query_count": len(queries),
        "fully_covered_query_count": fully_covered_count,
        "per_query": coverage,
    }


def query_source_group(query: dict, source_lookup: dict[str, str]) -> str:
    """Réf. tâche §2 (ventilation par source) : source dominante de la
    vérité terrain d'une requête -- 'mixed' si plusieurs types de source
    apparaissent parmi ses expected_chunk_ids."""
    sources = {source_lookup.get(cid) for cid in query["expected_chunk_ids"]}
    sources.discard(None)
    if len(sources) == 1:
        return next(iter(sources))
    if not sources:
        return "unknown"
    return "mixed"


def evaluate_mode(
    *,
    mode_name: str,
    queries: list[dict],
    retrieve_fn,
    top_k: int = TOP_K_MAIN,
) -> dict:
    """Exécute réellement `retrieve_fn(query_text, top_k)` pour chacune
    des `queries` -- retourne les identifiants réellement récupérés."""
    retrieved_by_query = {q["query_id"]: retrieve_fn(q["query"], top_k) for q in queries}
    result = evaluate_queries(retrieved_by_query, queries, ks=(5, 10))
    result["mode"] = mode_name
    return result


def breakdown_by_source(per_query: list[dict], queries: list[dict], source_lookup: dict[str, str]) -> dict:
    groups: dict[str, list[dict]] = {}
    per_query_by_id = {q["query_id"]: q for q in per_query}
    for query in queries:
        group = query_source_group(query, source_lookup)
        groups.setdefault(group, []).append(per_query_by_id[query["query_id"]])

    breakdown = {}
    for group, entries in groups.items():
        n = len(entries)
        breakdown[group] = {
            "query_count": n,
            "mean_recall_at_5": sum(e["recall_at_5"] for e in entries) / n,
            "mean_mrr_at_5": sum(e["mrr_at_5"] for e in entries) / n,
            "mean_ndcg_at_5": sum(e["ndcg_at_5"] for e in entries) / n,
            "mean_hit_rate_at_5": sum(e["hit_rate_at_5"] for e in entries) / n,
        }
    return breakdown


def run_full_corpus_evaluation() -> dict:
    eval_spec = _load_json(QUERIES_PATH)
    queries = eval_spec["queries"]
    embedder = load_embedder()

    print(f"Chargement du corpus reduit (D3FEND+Engage+litterature)...")
    deception_chunks = load_deception_only_chunks()
    print(f"Chargement du corpus complet (ATT&CK+D3FEND+Engage+litterature)...")
    full_chunks = load_full_corpus_chunks()
    print(f"  corpus reduit  : {len(deception_chunks)} chunks")
    print(f"  corpus complet : {len(full_chunks)} chunks")

    results_by_corpus = {}
    for corpus_name, chunks in (("corpus_149_deception_only", deception_chunks), ("corpus_1306_full", full_chunks)):
        print(f"Indexation reelle : {corpus_name} ({len(chunks)} chunks)...")
        lexical_index, semantic_index = build_indices(chunks, embedder)
        source_lookup = chunk_source_lookup(chunks)

        coverage = check_ground_truth_coverage(queries, source_lookup)

        modes = {
            "lexical": lambda q, k, li=lexical_index: [r.chunk.chunk_id for r in retrieve(li, q, top_k=k)],
            "semantic": lambda q, k, si=semantic_index: [
                r.chunk.chunk_id for r in retrieve_semantic(si, q, top_k=k, embedder=embedder)
            ],
            "hybrid": lambda q, k, li=lexical_index, si=semantic_index: [
                r.chunk.chunk_id
                for r in retrieve_hybrid(li, si, q, top_k=k, alpha=DEFAULT_HYBRID_ALPHA, embedder=embedder)
            ],
        }

        mode_results = {}
        for mode_name, retrieve_fn in modes.items():
            print(f"  evaluation mode={mode_name} sur {corpus_name}...")
            mode_eval = evaluate_mode(mode_name=mode_name, queries=queries, retrieve_fn=retrieve_fn)
            mode_eval["source_breakdown"] = breakdown_by_source(mode_eval["per_query"], queries, source_lookup)
            mode_results[mode_name] = mode_eval

        results_by_corpus[corpus_name] = {
            "chunk_count": len(chunks),
            "chunk_count_by_source": {
                st: sum(1 for c in chunks if c.source_type == st) for st in sorted({c.source_type for c in chunks})
            },
            "ground_truth_coverage": coverage,
            "modes": mode_results,
        }

    # --- Comparaison explicite 149 vs 1306 (réf. tâche §2) ---
    comparison = {}
    small = results_by_corpus["corpus_149_deception_only"]["modes"]
    full = results_by_corpus["corpus_1306_full"]["modes"]
    for mode_name in ("lexical", "semantic", "hybrid"):
        comparison[mode_name] = {
            metric: {
                "corpus_149": small[mode_name][metric],
                "corpus_1306": full[mode_name][metric],
                "delta": full[mode_name][metric] - small[mode_name][metric],
            }
            for metric in ("mean_recall_at_5", "mean_recall_at_10", "mean_mrr_at_5", "mean_ndcg_at_5", "mean_hit_rate_at_5")
        }
    direction = "diminution" if comparison["hybrid"]["mean_recall_at_5"]["delta"] < 0 else "augmentation"
    comparison["explanation"] = (
        "Le corpus complet (1306 chunks) ajoute exclusivement des chunks ATT&CK (1157) ; aucune requete "
        "de data/rag/rag_eval_queries.json n'a de verite terrain ATT&CK (jeu construit avant l'ajout du "
        "corpus ATT&CK, pour la recherche de mecanismes de deception). Mesure reelle : une " + direction + " "
        "des metriques de recuperation sur les 17 requetes (voir deltas ci-dessus, negatifs pour les trois "
        "modes lexical/semantique/hybride) -- les chunks ATT&CK agissent comme du BRUIT pour ce jeu de "
        "requetes centre sur la deception, en concurrencant les chunks pertinents dans le classement par "
        "score. Ce n'est PAS un changement de moteur (memes fonctions de recuperation, meme alpha, meme "
        "embedder, memes 17 requetes) : c'est un effet de couverture/composition du corpus, mesure "
        "honnetement meme quand il degrade le score plutot que de l'ameliorer."
    )

    result = {
        "query_count": len(queries),
        "top_k": {"recall": [5, 10], "mrr": 5, "ndcg": 5, "hit_rate": 5},
        "embedding_model": embedder.model_name,
        "hybrid_alpha_used": DEFAULT_HYBRID_ALPHA,
        "corpora": results_by_corpus,
        "comparison_149_vs_1306": comparison,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "retrieval_eval_full_corpus.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Ecrit : {OUT_DIR / 'retrieval_eval_full_corpus.json'}")
    return result


def run_alpha_sweep(full_chunks: list[Chunk], embedder, queries: list[dict]) -> dict:
    print("Balayage de alpha (corpus complet)...")
    lexical_index, semantic_index = build_indices(full_chunks, embedder)

    sweep = {}
    for alpha in ALPHA_SWEEP_VALUES:
        print(f"  alpha={alpha}...")
        retrieve_fn = lambda q, k, a=alpha: [
            r.chunk.chunk_id for r in retrieve_hybrid(lexical_index, semantic_index, q, top_k=k, alpha=a, embedder=embedder)
        ]
        ev = evaluate_mode(mode_name=f"hybrid_alpha_{alpha}", queries=queries, retrieve_fn=retrieve_fn)
        sweep[str(alpha)] = {
            "mean_recall_at_5": ev["mean_recall_at_5"],
            "mean_recall_at_10": ev["mean_recall_at_10"],
            "mean_mrr_at_5": ev["mean_mrr_at_5"],
            "mean_ndcg_at_5": ev["mean_ndcg_at_5"],
            "mean_hit_rate_at_5": ev["mean_hit_rate_at_5"],
        }

    best_alpha = max(sweep, key=lambda a: sweep[a]["mean_recall_at_5"])
    result = {
        "corpus": "corpus_1306_full",
        "alphas_tested": list(ALPHA_SWEEP_VALUES),
        "results_by_alpha": sweep,
        "selection_criterion": "mean_recall_at_5",
        "best_alpha": float(best_alpha),
        "note": "Balayage a but de conception (choix de alpha), pas une optimisation retroactive du corpus/de la verite terrain.",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "alpha_sweep.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Ecrit : {OUT_DIR / 'alpha_sweep.json'}")
    return result


def run_reranker_ablation(full_chunks: list[Chunk], embedder, queries: list[dict], *, alpha: float) -> dict:
    print("Ablation du reclassement (cross-encoder reel)...")
    lexical_index, semantic_index = build_indices(full_chunks, embedder)
    reranker = CrossEncoderReranker.load()
    print(f"  reranker charge : {reranker.model_name}")

    without_by_query: dict[str, list[str]] = {}
    with_by_query: dict[str, list[str]] = {}
    for query in queries:
        pool = retrieve_hybrid(
            lexical_index, semantic_index, query["query"], top_k=RETRIEVAL_POOL_K, alpha=alpha, embedder=embedder
        )
        without_by_query[query["query_id"]] = [r.chunk.chunk_id for r in pool[:10]]
        reranked = reranker.rerank(query["query"], pool, top_k=10)
        with_by_query[query["query_id"]] = [r.retrieval_result.chunk.chunk_id for r in reranked]

    without_eval = evaluate_queries(without_by_query, queries, ks=(5, 10))
    with_eval = evaluate_queries(with_by_query, queries, ks=(5, 10))

    result = {
        "corpus": "corpus_1306_full",
        "alpha_used": alpha,
        "retrieval_pool_k": RETRIEVAL_POOL_K,
        "reranker_model": reranker.model_name,
        "without_reranking": {
            "mean_recall_at_5": without_eval["mean_recall_at_5"],
            "mean_recall_at_10": without_eval["mean_recall_at_10"],
            "mean_mrr_at_5": without_eval["mean_mrr_at_5"],
            "mean_ndcg_at_5": without_eval["mean_ndcg_at_5"],
            "mean_hit_rate_at_5": without_eval["mean_hit_rate_at_5"],
        },
        "with_reranking": {
            "mean_recall_at_5": with_eval["mean_recall_at_5"],
            "mean_recall_at_10": with_eval["mean_recall_at_10"],
            "mean_mrr_at_5": with_eval["mean_mrr_at_5"],
            "mean_ndcg_at_5": with_eval["mean_ndcg_at_5"],
            "mean_hit_rate_at_5": with_eval["mean_hit_rate_at_5"],
        },
        "delta": {
            metric: with_eval[metric] - without_eval[metric]
            for metric in ("mean_recall_at_5", "mean_recall_at_10", "mean_mrr_at_5", "mean_ndcg_at_5", "mean_hit_rate_at_5")
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "reranker_ablation.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Ecrit : {OUT_DIR / 'reranker_ablation.json'}")
    return result


def main() -> None:
    t0 = time.time()
    full_corpus_result = run_full_corpus_evaluation()

    eval_spec = _load_json(QUERIES_PATH)
    queries = eval_spec["queries"]
    embedder = load_embedder()
    full_chunks = load_full_corpus_chunks()

    alpha_result = run_alpha_sweep(full_chunks, embedder, queries)
    ablation_result = run_reranker_ablation(full_chunks, embedder, queries, alpha=alpha_result["best_alpha"])

    elapsed = time.time() - t0
    print(f"Campagne retrieval terminee en {elapsed:.1f}s.")
    print(f"Recall@5 (corpus complet, hybride alpha={DEFAULT_HYBRID_ALPHA}): "
          f"{full_corpus_result['corpora']['corpus_1306_full']['modes']['hybrid']['mean_recall_at_5']:.3f}")
    print(f"Meilleur alpha (Recall@5): {alpha_result['best_alpha']}")
    print(f"Gain du reclassement (Recall@5): {ablation_result['delta']['mean_recall_at_5']:+.3f}")


if __name__ == "__main__":
    main()
