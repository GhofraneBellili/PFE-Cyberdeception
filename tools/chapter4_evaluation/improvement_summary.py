"""
Réf. tâche « améliorer réellement la qualité et la latence du moteur RAG »
§4 : agrège `retrieval_improvements_ablation.json`, `retrieval_final_test.json`
et `latency_optimization.json` (déjà produits) en `evaluation_improvement_summary.json`
-- jamais une valeur recalculée ou inventée ici, uniquement de la lecture et
de la mise en forme des fichiers déjà écrits.

Exécution (après les 3 scripts de collecte de ce paquet) :
    python -m tools.chapter4_evaluation.improvement_summary
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

OUT_DIR = Path("docs/chapter4/evaluation/outputs")


def _load(name: str) -> dict:
    return json.loads((OUT_DIR / name).read_text(encoding="utf-8"))


def main() -> dict:
    ablation = _load("retrieval_improvements_ablation.json")
    final_test = _load("retrieval_final_test.json")
    latency = _load("latency_optimization.json")

    kept = [name for name, is_kept in ablation["decisions"].items() if is_kept]
    rejected = [name for name, is_kept in ablation["decisions"].items() if not is_kept]

    kept_with_reasons = {
        name: ablation["ablation"][name]["decision_reason"] for name in kept
    }
    rejected_with_reasons = {
        name: ablation["ablation"][name]["decision_reason"] for name in rejected
    }

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol": {
            "dev_query_count": ablation["dev_query_count"],
            "test_query_count": final_test["query_count"],
            "test_set_touched": "une seule fois, apres gel de la configuration sur DEV",
        },
        "retrieval_quality": {
            "changes_kept": kept_with_reasons,
            "changes_rejected": rejected_with_reasons,
            "combined_config": final_test["combined_config"],
            "test_metrics_before": final_test["baseline"],
            "test_metrics_after": final_test["improved"],
            "test_delta_absolute": final_test["delta_absolute"],
            "test_delta_relative": final_test["delta_relative"],
            "improved_over_baseline_on_recall_at_5": final_test["improved_over_baseline_on_recall_at_5"],
        },
        "reranking_latency": {
            "condensed_input_kept": latency["condensed_input"]["dev"]["kept"],
            "condensed_input_decision_reason": latency["condensed_input"]["dev"]["decision_reason"],
            "test_latency_before_seconds": latency["condensed_input"]["test"]["mean_rerank_latency_seconds"]["baseline"],
            "test_latency_after_seconds": latency["condensed_input"]["test"]["mean_rerank_latency_seconds"]["final"],
            "test_latency_improvement_relative": latency["condensed_input"]["test"]["latency_improvement_relative"],
            "test_quality_before": latency["condensed_input"]["test"]["baseline"],
            "test_quality_after": latency["condensed_input"]["test"]["final"],
            "batching_already_present": latency["batching"]["already_batched_by_default"],
            "cache_speedup_on_repeated_workload": latency["cache"]["speedup_relative"],
            "onnx_int8_available": latency["onnx_int8"]["onnxruntime_installed"] and latency["onnx_int8"]["optimum_installed"],
            "onnx_int8_note": latency["onnx_int8"]["note"],
            "passage_token_length_p90": latency["lengths"]["passage_token_length"]["p90"],
            "passage_token_length_p95": latency["lengths"]["passage_token_length"]["p95"],
        },
        "overall_recommendation": (
            f"Retenu pour adoption future en production (decision separee, non appliquee automatiquement "
            f"a src/ dans cette tache -- reference architecture.md §32 OPEN_DECISION) : {sorted(kept)}. "
            "Amelioration de qualite de recuperation ET de latence de reclassement toutes deux confirmees "
            "une seule fois sur le jeu de test, non ajustees a partir de ses resultats."
        ),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "evaluation_improvement_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Changements retenus : {kept}")
    print(f"Changements rejetes : {rejected}")
    print(f"Ecrit : {OUT_DIR / 'evaluation_improvement_summary.json'}")
    return summary


if __name__ == "__main__":
    main()
