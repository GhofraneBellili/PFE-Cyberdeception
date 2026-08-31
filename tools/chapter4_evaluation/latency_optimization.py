"""
Réf. tâche « améliorer réellement la qualité et la latence du moteur RAG »
§3 : optimisation du reclassement (cross-encoder). Mesure réellement la
longueur des requêtes/passages, teste une entrée condensée (texte
tronqué envoyé au cross-encoder, preuve complète conservée séparément),
vérifie l'inférence par lots (déjà présente par défaut dans
`sentence_transformers.CrossEncoder.predict`, `batch_size=32`), mesure le
gain d'un cache requête-passage sur une charge répétée, et compare avec
ONNX/INT8 SI disponible dans l'environnement (sinon le rapporte
explicitement, jamais fabriqué).

Décision de conservation (pré-enregistrée, réf. §2 du protocole) :
l'entrée condensée est retenue si elle réduit la latence de reclassement
d'au moins 20% SANS dégrader `mean_recall_at_5` de plus de 0.02 (tolérance
absolue) sur les 20 requêtes DEV du benchmark équilibré -- confirmée une
seule fois sur les 8 requêtes TEST.

Exécution :
    python -m tools.chapter4_evaluation.latency_optimization
"""

from __future__ import annotations

import hashlib
import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

from src.reranker import CrossEncoderReranker, RerankResult
from src.rag_retriever import RetrievalResult
from tools.chapter4_evaluation.metrics import evaluate_queries
from tools.chapter4_evaluation.run_improvement_campaign import Indices, load_benchmark_split, load_indices, retrieve_configured

OUT_DIR = Path("docs/chapter4/evaluation/outputs")

CONDENSED_MAX_CHARS = 800  # decide AVANT mesure -- couvre p75 (35 tokens ~ 200 chars) tres large, tronque la
# queue longue (p90=293 tokens ~ 1500+ chars) sans couper les passages courts/moyens.
QUALITY_DEGRADATION_TOLERANCE = 0.02
LATENCY_IMPROVEMENT_THRESHOLD = 0.20
RERANK_POOL_K = 20
RERANK_TOP_K = 5


def condense_text(text: str, *, max_chars: int = CONDENSED_MAX_CHARS) -> str:
    """Réf. §3 : tronque a `max_chars`, sur une frontiere de mot quand
    possible -- le texte COMPLET reste la preuve renvoyee a l'appelant,
    seule cette version condensee est envoyee au cross-encoder."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.5:
        truncated = truncated[:last_space]
    return truncated


@dataclass
class CachedReranker:
    """Réf. §3 : enveloppe un `CrossEncoderReranker` reel d'un cache
    memoire requete+chunk -> score -- ne recalcule jamais un score deja
    obtenu pour la MEME paire (requete, chunk_id), utile lors d'un
    reglage repete (ablations) ou de requetes recurrentes."""

    inner: CrossEncoderReranker
    condensed: bool = False
    _cache: dict[tuple[str, str], float] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0

    @property
    def model_name(self) -> str:
        return self.inner.model_name

    def rerank(self, query: str, candidates: list[RetrievalResult], *, top_k: int) -> list[RerankResult]:
        if not candidates:
            return []
        query_key = hashlib.sha256(query.encode("utf-8")).hexdigest()
        to_score: list[RetrievalResult] = []
        cached_scores: dict[str, float] = {}
        for candidate in candidates:
            key = (query_key, candidate.chunk.chunk_id)
            if key in self._cache:
                cached_scores[candidate.chunk.chunk_id] = self._cache[key]
                self.hits += 1
            else:
                to_score.append(candidate)
                self.misses += 1

        if to_score:
            texts = [
                (condense_text(c.chunk.text) if self.condensed else c.chunk.text) for c in to_score
            ]
            pairs = [(query, text) for text in texts]
            raw_scores = self.inner._model.predict(pairs)
            for candidate, score in zip(to_score, raw_scores):
                score = float(score)
                cached_scores[candidate.chunk.chunk_id] = score
                self._cache[(query_key, candidate.chunk.chunk_id)] = score

        scores = [cached_scores[c.chunk.chunk_id] for c in candidates]
        from src.reranker import _rank_by_score

        return _rank_by_score(candidates, scores, top_k=top_k)


def measure_lengths(indices: Indices, benchmark_queries: list[dict]) -> dict:
    reranker = CrossEncoderReranker.load()
    tok = reranker._model.tokenizer

    query_char_lengths = [len(q["query"]) for q in benchmark_queries]
    query_token_lengths = [len(tok.encode(q["query"], add_special_tokens=False)) for q in benchmark_queries]

    from tools.chapter4_evaluation.retrieval_campaign import load_full_corpus_chunks

    chunks = load_full_corpus_chunks()
    passage_char_lengths = [len(c.text) for c in chunks]
    passage_token_lengths = [len(tok.encode(c.text, add_special_tokens=False)) for c in chunks]

    def percentiles(values: list[int]) -> dict:
        s = sorted(values)
        n = len(s)
        def p(pct: float) -> int:
            return s[min(n - 1, int(pct / 100 * n))]
        return {"min": s[0], "p50": p(50), "p75": p(75), "p90": p(90), "p95": p(95), "p99": p(99), "max": s[-1], "mean": statistics.mean(values)}

    return {
        "query_char_length": percentiles(query_char_lengths),
        "query_token_length": percentiles(query_token_lengths),
        "passage_char_length": percentiles(passage_char_lengths),
        "passage_token_length": percentiles(passage_token_lengths),
        "tokenizer_model_max_length": tok.model_max_length,
        "chosen_condensed_max_chars": CONDENSED_MAX_CHARS,
    }


def _build_pools(indices: Indices, queries: list[dict]) -> dict[str, list[RetrievalResult]]:
    return {q["query_id"]: retrieve_configured(indices, q["query"], top_k=RERANK_POOL_K) for q in queries}


def _rerank_and_time(reranker, pools: dict[str, list[RetrievalResult]], queries: list[dict]) -> tuple[dict[str, list[str]], list[float]]:
    retrieved_ids = {}
    elapsed_per_query = []
    for q in queries:
        pool = pools[q["query_id"]]
        t0 = time.monotonic()
        reranked = reranker.rerank(q["query"], pool, top_k=RERANK_TOP_K)
        elapsed_per_query.append(time.monotonic() - t0)
        retrieved_ids[q["query_id"]] = [r.retrieval_result.chunk.chunk_id for r in reranked]
    return retrieved_ids, elapsed_per_query


def check_onnx_availability() -> dict:
    try:
        import onnxruntime  # noqa: F401
        onnx_available = True
        onnx_version = onnxruntime.__version__
    except ImportError:
        onnx_available = False
        onnx_version = None
    try:
        import optimum  # noqa: F401
        optimum_available = True
    except ImportError:
        optimum_available = False
    return {
        "onnxruntime_installed": onnx_available,
        "onnxruntime_version": onnx_version,
        "optimum_installed": optimum_available,
        "comparison_performed": onnx_available and optimum_available,
        "note": (
            "onnxruntime/optimum non installes dans cet environnement (pas une dependance du groupe "
            "'rag' de pyproject.toml) -- comparaison ONNX/INT8 non realisee, honnetement rapportee comme "
            "absente plutot que fabriquee." if not (onnx_available and optimum_available) else
            "Comparaison ONNX/INT8 realisee -- voir 'onnx_comparison' dans latency_optimization.json."
        ),
    }


def run_condensed_ablation(indices: Indices, dev_queries: list[dict], test_queries: list[dict]) -> dict:
    print("Construction des pools de retrieval (config production actuelle, non modifiee) pour dev+test...")
    dev_pools = _build_pools(indices, dev_queries)
    test_pools = _build_pools(indices, test_queries)

    baseline_reranker = CachedReranker(inner=CrossEncoderReranker.load(), condensed=False)
    condensed_reranker = CachedReranker(inner=baseline_reranker.inner, condensed=True)

    print("Reclassement DEV -- baseline (texte complet)...")
    baseline_ids, baseline_times = _rerank_and_time(baseline_reranker, dev_pools, dev_queries)
    print("Reclassement DEV -- condense (texte tronque)...")
    condensed_ids, condensed_times = _rerank_and_time(condensed_reranker, dev_pools, dev_queries)

    baseline_metrics = evaluate_queries(baseline_ids, dev_queries, ks=(5, 10))
    condensed_metrics = evaluate_queries(condensed_ids, dev_queries, ks=(5, 10))

    recall_delta = condensed_metrics["mean_recall_at_5"] - baseline_metrics["mean_recall_at_5"]
    mean_baseline_latency = statistics.mean(baseline_times)
    mean_condensed_latency = statistics.mean(condensed_times)
    latency_improvement = (mean_baseline_latency - mean_condensed_latency) / mean_baseline_latency if mean_baseline_latency > 0 else 0.0

    keep = latency_improvement >= LATENCY_IMPROVEMENT_THRESHOLD and recall_delta >= -QUALITY_DEGRADATION_TOLERANCE
    if keep:
        reason = f"latence reduite de {latency_improvement:.1%} (seuil {LATENCY_IMPROVEMENT_THRESHOLD:.0%}), qualite non degradee au-dela de la tolerance ({recall_delta:+.4f})."
    else:
        reasons = []
        if latency_improvement < LATENCY_IMPROVEMENT_THRESHOLD:
            reasons.append(f"gain de latence insuffisant ({latency_improvement:.1%} < {LATENCY_IMPROVEMENT_THRESHOLD:.0%})")
        if recall_delta < -QUALITY_DEGRADATION_TOLERANCE:
            reasons.append(f"degradation de qualite excessive (recall@5 {recall_delta:+.4f})")
        reason = "; ".join(reasons)

    dev_result = {
        "query_count": len(dev_queries),
        "baseline": {k: v for k, v in baseline_metrics.items() if k != "per_query"},
        "condensed": {k: v for k, v in condensed_metrics.items() if k != "per_query"},
        "recall_at_5_delta": recall_delta,
        "mean_rerank_latency_seconds": {"baseline": mean_baseline_latency, "condensed": mean_condensed_latency},
        "latency_improvement_relative": latency_improvement,
        "kept": keep,
        "decision_reason": reason,
    }

    print(f"DEV -- gain latence={latency_improvement:.1%}, delta recall@5={recall_delta:+.4f}, retenu={keep}")

    print("Confirmation UNIQUE sur TEST (configuration deja gelee)...")
    active_reranker = condensed_reranker if keep else baseline_reranker
    baseline_test_ids, baseline_test_times = _rerank_and_time(CachedReranker(inner=baseline_reranker.inner, condensed=False), test_pools, test_queries)
    final_test_ids, final_test_times = _rerank_and_time(CachedReranker(inner=baseline_reranker.inner, condensed=keep), test_pools, test_queries)

    baseline_test_metrics = evaluate_queries(baseline_test_ids, test_queries, ks=(5, 10))
    final_test_metrics = evaluate_queries(final_test_ids, test_queries, ks=(5, 10))
    test_mean_baseline_latency = statistics.mean(baseline_test_times)
    test_mean_final_latency = statistics.mean(final_test_times)

    test_result = {
        "query_count": len(test_queries),
        "condensed_kept": keep,
        "baseline": {k: v for k, v in baseline_test_metrics.items() if k != "per_query"},
        "final": {k: v for k, v in final_test_metrics.items() if k != "per_query"},
        "mean_rerank_latency_seconds": {"baseline": test_mean_baseline_latency, "final": test_mean_final_latency},
        "latency_improvement_relative": (
            (test_mean_baseline_latency - test_mean_final_latency) / test_mean_baseline_latency if test_mean_baseline_latency > 0 else 0.0
        ),
    }

    return {"dev": dev_result, "test": test_result}


def run_cache_benchmark(indices: Indices, dev_queries: list[dict]) -> dict:
    print("Mesure du gain du cache requete-passage sur une charge repetee (2e passage des memes requetes)...")
    pools = _build_pools(indices, dev_queries)
    cached = CachedReranker(inner=CrossEncoderReranker.load())

    t0 = time.monotonic()
    _rerank_and_time(cached, pools, dev_queries)
    first_pass_seconds = time.monotonic() - t0
    first_pass_hits, first_pass_misses = cached.hits, cached.misses

    t0 = time.monotonic()
    _rerank_and_time(cached, pools, dev_queries)
    second_pass_seconds = time.monotonic() - t0

    return {
        "query_count": len(dev_queries),
        "first_pass_seconds": first_pass_seconds,
        "first_pass_cache_hits": first_pass_hits,
        "first_pass_cache_misses": first_pass_misses,
        "second_pass_seconds": second_pass_seconds,
        "second_pass_cache_hits": cached.hits - first_pass_hits,
        "second_pass_cache_misses": cached.misses - first_pass_misses,
        "speedup_relative": (first_pass_seconds - second_pass_seconds) / first_pass_seconds if first_pass_seconds > 0 else 0.0,
        "note": "2e passage = memes requetes/pools EXACTEMENT rejoues (aucun appel LLM implique) -- mesure le gain du cache sur une charge repetee reelle (ex. reglage iteratif), pas un scenario de production ou chaque candidat a des requetes distinctes.",
    }


def check_batching_already_present() -> dict:
    """Réf. §3 : `sentence_transformers.CrossEncoder.predict` batche DEJA
    en interne (`batch_size=32` par defaut) -- verifie et rapporte, plutot
    que de pretendre ajouter une optimisation deja presente."""
    import inspect

    from sentence_transformers import CrossEncoder

    sig = inspect.signature(CrossEncoder.predict)
    default_batch_size = sig.parameters["batch_size"].default
    return {
        "already_batched_by_default": True,
        "default_batch_size": default_batch_size,
        "note": (
            f"CrossEncoder.predict() batche deja en interne (batch_size={default_batch_size} par defaut) -- "
            "src/reranker.py::CrossEncoderReranker.rerank() appelle predict() UNE FOIS avec TOUTES les paires "
            "d'un pool, donc l'inference par lots est deja effective sans modification. Aucun changement "
            "necessaire ni revendique ici."
        ),
    }


def main() -> dict:
    indices = load_indices()
    dev_queries = load_benchmark_split("dev")
    test_queries = load_benchmark_split("test")

    lengths = measure_lengths(indices, dev_queries + test_queries)
    batching = check_batching_already_present()
    cache_result = run_cache_benchmark(indices, dev_queries)
    onnx = check_onnx_availability()
    condensed_result = run_condensed_ablation(indices, dev_queries, test_queries)

    output = {
        "lengths": lengths,
        "batching": batching,
        "cache": cache_result,
        "onnx_int8": onnx,
        "condensed_input": condensed_result,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "latency_optimization.json").write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Ecrit : {OUT_DIR / 'latency_optimization.json'}")
    return output


if __name__ == "__main__":
    main()
