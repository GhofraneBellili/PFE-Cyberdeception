"""
Réf. tâche « campagne d'évaluation réelle RAG/LLM/système » §7/§8 : agrège
les fichiers de résultats DÉJÀ PRODUITS (jamais de valeur recalculée ou
supposée) en `evaluation_summary.json`, `run_manifest.json` et le résumé
lisible `evaluation_results.txt`. Toute section dont le fichier source est
absent est marquée explicitement comme non exécutée/bloquée -- jamais
omise silencieusement ni remplacée par une valeur inventée.

Exécution (après avoir lancé les autres scripts de ce paquet) :
    python -m tools.chapter4_evaluation.aggregate
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from tools.chapter4_evaluation.decision_robustness import DEFAULT_EPSILONS, DEFAULT_N_DRAWS
from tools.chapter4_evaluation.llm_evaluation import K_REPLAYS

OUT_DIR = Path("docs/chapter4/evaluation/outputs")

EXPECTED_FILES = (
    "retrieval_eval_full_corpus.json",
    "alpha_sweep.json",
    "reranker_ablation.json",
    "llm_conformity.json",
    "llm_evidence_grounding.json",
    "llm_stability_temp0.json",
    "decision_robustness.json",
    "performance.json",
)


def _load(name: str) -> dict | None:
    path = OUT_DIR / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _git_commit_sha() -> str | None:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception:
        return None


def build_run_manifest() -> dict:
    retrieval = _load("retrieval_eval_full_corpus.json")
    alpha_sweep = _load("alpha_sweep.json")
    ablation = _load("reranker_ablation.json")
    llm_conformity = _load("llm_conformity.json")
    stability = _load("llm_stability_temp0.json")
    robustness = _load("decision_robustness.json")

    produced_files = sorted(p.name for p in OUT_DIR.glob("*.json")) + sorted(p.name for p in OUT_DIR.glob("*.txt"))

    manifest = {
        "commit_sha": _git_commit_sha(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corpus": {
            "full_corpus_chunk_count": 1306,
            "full_corpus_chunk_count_measured": (
                retrieval["corpora"]["corpus_1306_full"]["chunk_count"] if retrieval else None
            ),
            "embedding_model": retrieval["embedding_model"] if retrieval else None,
        },
        "reranker_model": ablation["reranker_model"] if ablation else None,
        "llm": {
            "provider": llm_conformity["provider"] if llm_conformity else None,
            "model": llm_conformity["model"] if llm_conformity else None,
            "prompt_version": llm_conformity["prompt_version"] if llm_conformity else None,
            "temperature": llm_conformity["temperature"] if llm_conformity else None,
            "status": "executed" if llm_conformity else "blocked_no_real_provider",
        },
        "chosen_alpha": alpha_sweep["best_alpha"] if alpha_sweep else None,
        "k_replays_configured": K_REPLAYS,
        "k_replays_used": stability["replay_count_per_candidate"] if stability else None,
        "epsilons_configured": list(DEFAULT_EPSILONS),
        "epsilons_used": robustness["epsilons_tested"] if robustness else None,
        "n_draws_per_epsilon_configured": DEFAULT_N_DRAWS,
        "n_draws_per_epsilon_used": robustness["n_draws_per_level"] if robustness else None,
        "produced_files": produced_files,
    }
    return manifest


def build_evaluation_summary() -> dict:
    retrieval = _load("retrieval_eval_full_corpus.json")
    alpha_sweep = _load("alpha_sweep.json")
    ablation = _load("reranker_ablation.json")
    conformity = _load("llm_conformity.json")
    grounding = _load("llm_evidence_grounding.json")
    stability = _load("llm_stability_temp0.json")
    robustness = _load("decision_robustness.json")
    performance = _load("performance.json")

    summary = {"generated_at": datetime.now(timezone.utc).isoformat()}

    if retrieval:
        hybrid_full = retrieval["corpora"]["corpus_1306_full"]["modes"]["hybrid"]
        hybrid_149 = retrieval["corpora"]["corpus_149_deception_only"]["modes"]["hybrid"]
        summary["retrieval"] = {
            "status": "executed",
            "corpus_1306_hybrid_recall_at_5": hybrid_full["mean_recall_at_5"],
            "corpus_1306_hybrid_hit_rate_at_5": hybrid_full["mean_hit_rate_at_5"],
            "corpus_149_hybrid_recall_at_5": hybrid_149["mean_recall_at_5"],
            "delta_recall_at_5_149_to_1306": hybrid_full["mean_recall_at_5"] - hybrid_149["mean_recall_at_5"],
        }
    else:
        summary["retrieval"] = {"status": "not_run"}

    if alpha_sweep:
        summary["alpha_sweep"] = {"status": "executed", "best_alpha": alpha_sweep["best_alpha"], "alphas_tested": alpha_sweep["alphas_tested"]}
    else:
        summary["alpha_sweep"] = {"status": "not_run"}

    if ablation:
        summary["reranker_ablation"] = {"status": "executed", "recall_at_5_gain": ablation["delta"]["mean_recall_at_5"]}
    else:
        summary["reranker_ablation"] = {"status": "not_run"}

    if conformity and grounding:
        summary["llm_annotation"] = {
            "status": "executed",
            "conformity_rate": conformity["conformity_rate"],
            "grounding_rate": grounding["grounding_rate"],
            "mean_DE_stdev_temp0": stability["mean_DE_stdev"] if stability else None,
        }
    else:
        summary["llm_annotation"] = {"status": "blocked_no_real_provider"}

    if robustness:
        summary["decision_robustness"] = {
            "status": "executed",
            "levels": [
                {"epsilon": lvl["epsilon"], "identical_plan_rate": lvl["identical_plan_rate"], "identical_pareto_rate": lvl["identical_pareto_rate"]}
                for lvl in robustness["levels"]
            ],
        }
    else:
        summary["decision_robustness"] = {"status": "blocked_no_real_provider_or_no_frozen_table"}

    if performance:
        summary["performance"] = {
            "status": "executed",
            "small_instance_rag_seconds_per_candidate": performance["instances"]["small"]["rag_context_plus_retrieval_plus_reranking_mean_seconds_per_candidate"],
            "large_instance_rag_seconds_per_candidate": performance["instances"]["large"]["rag_context_plus_retrieval_plus_reranking_mean_seconds_per_candidate"],
            "llm_annotation_latency_available": performance["llm_annotation_latency"] is not None,
        }
    else:
        summary["performance"] = {"status": "not_run"}

    return summary


def build_text_report(summary: dict, manifest: dict) -> str:
    lines = [
        "Campagne d'evaluation reelle RAG/LLM/systeme -- resume",
        "=" * 70,
        f"Genere le : {summary['generated_at']}",
        f"Commit : {manifest['commit_sha']}",
        "",
    ]

    r = summary["retrieval"]
    lines.append("§2 Retrieval (corpus complet 1306 vs 149) : " + r["status"])
    if r["status"] == "executed":
        lines += [
            f"  Recall@5 hybride, corpus 1306 : {r['corpus_1306_hybrid_recall_at_5']:.3f}",
            f"  Recall@5 hybride, corpus 149  : {r['corpus_149_hybrid_recall_at_5']:.3f}",
            f"  Delta (1306 - 149) : {r['delta_recall_at_5_149_to_1306']:+.3f} "
            "(negatif = bruit ATT&CK, aucune verite terrain ATT&CK dans le jeu de requetes)",
        ]
    lines.append("")

    a = summary["alpha_sweep"]
    lines.append("§3 Balayage alpha : " + a["status"])
    if a["status"] == "executed":
        lines.append(f"  Meilleur alpha (Recall@5, corpus complet) : {a['best_alpha']} (teste : {a['alphas_tested']})")
    lines.append("")

    ab = summary["reranker_ablation"]
    lines.append("§3 Ablation reclassement (cross-encoder reel) : " + ab["status"])
    if ab["status"] == "executed":
        lines.append(f"  Gain Recall@5 avec reclassement : {ab['recall_at_5_gain']:+.3f}")
    lines.append("")

    llm = summary["llm_annotation"]
    lines.append("§4 Annotation LLM (conformite / ancrage / stabilite temp=0) : " + llm["status"])
    if llm["status"] == "executed":
        lines += [
            f"  Taux de conformite : {llm['conformity_rate']:.1%}",
            f"  Taux d'ancrage documentaire : {llm['grounding_rate']}",
            f"  Ecart-type moyen de DE (temperature=0) : {llm['mean_DE_stdev_temp0']}",
        ]
    else:
        lines.append("  Aucun provider LLM reel exploitable dans cet environnement -- aucun resultat fabrique.")
    lines.append("")

    rb = summary["decision_robustness"]
    lines.append("§5 Robustesse de la decision : " + rb["status"])
    if rb["status"] == "executed":
        for lvl in rb["levels"]:
            lines.append(f"  epsilon={lvl['epsilon']} : plan identique {lvl['identical_plan_rate']:.1%}, "
                          f"front de Pareto identique {lvl['identical_pareto_rate']:.1%}")
    else:
        lines.append("  Depend d'une table DE gelee reelle (§4) -- non executee dans cet environnement.")
    lines.append("")

    p = summary["performance"]
    lines.append("§6 Performance : " + p["status"])
    if p["status"] == "executed":
        lines += [
            f"  RAG (contexte+retrieval+reclassement), petite instance : {p['small_instance_rag_seconds_per_candidate']:.3f} s/candidat",
            f"  RAG (contexte+retrieval+reclassement), grande instance : {p['large_instance_rag_seconds_per_candidate']:.3f} s/candidat",
            f"  Latence d'annotation LLM disponible : {p['llm_annotation_latency_available']}",
        ]
    lines.append("")
    lines.append("=" * 70)
    lines.append(f"Fichiers produits : {', '.join(manifest['produced_files'])}")
    return "\n".join(lines) + "\n"


def main() -> None:
    manifest = build_run_manifest()
    summary = build_evaluation_summary()
    text_report = build_text_report(summary, manifest)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "run_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "evaluation_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "evaluation_results.txt").write_text(text_report, encoding="utf-8")
    print(text_report)
    print(f"Ecrit : run_manifest.json, evaluation_summary.json, evaluation_results.txt (dans {OUT_DIR})")


if __name__ == "__main__":
    main()
