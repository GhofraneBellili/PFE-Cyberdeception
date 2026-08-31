"""
Réf. tâche « campagne d'évaluation réelle RAG/LLM/système » §7 : les 8
figures de la campagne d'évaluation, générées STRICTEMENT à partir des
fichiers JSON déjà produits dans `docs/chapter4/evaluation/outputs/`
(jamais une valeur retapée à la main). Une section dont le fichier source
est absent (ex. §4/§5 bloqués sans provider LLM réel) produit une figure
explicite « section non exécutée » plutôt que d'être omise ou de fabriquer
des barres.

Exécution (après les scripts de collecte de ce paquet) :
    python -m tools.chapter4_evaluation.figures
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.chapter4_figures.common import (
    COLOR_BACKGROUND,
    COLOR_BORDER,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_SANS,
    add_source_note,
    add_subtitle,
    add_title,
    new_figure,
    save_figure,
)

OUT_DIR = Path("docs/chapter4/evaluation/outputs")
SCREENSHOTS_DIR = Path("docs/chapter4/evaluation/screenshots")

BAR_COLORS = ["#3b6ea5", "#5a9e6f", "#c08a3e", "#8a5a9e", "#b5533e"]


def _load(name: str) -> dict | None:
    path = OUT_DIR / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _blocked_figure(output_path: Path, title: str, reason: str) -> Path:
    fig = new_figure(9.0, 3.0)
    ax = fig.add_axes((0.05, 0.15, 0.9, 0.7))
    ax.axis("off")
    add_title(ax, title)
    ax.text(
        0.0, 0.4, f"Section non executee dans cet environnement : {reason}",
        transform=ax.transAxes, fontsize=11, color=COLOR_TEXT_SECONDARY, family=FONT_SANS, va="center", ha="left",
    )
    add_source_note(ax, "Aucune donnee fabriquee -- reference tache §1/§4/§5.", y=0.0)
    save_figure(fig, output_path)
    return output_path


def _grouped_bar(ax, *, group_labels: list[str], series: dict[str, list[float]], ylabel: str) -> None:
    n_groups = len(group_labels)
    n_series = len(series)
    bar_width = 0.8 / n_series
    x = list(range(n_groups))
    for i, (series_name, values) in enumerate(series.items()):
        offsets = [xi + (i - (n_series - 1) / 2) * bar_width for xi in x]
        ax.bar(offsets, values, width=bar_width, label=series_name, color=BAR_COLORS[i % len(BAR_COLORS)], edgecolor=COLOR_BORDER, linewidth=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels(group_labels, fontsize=9, family=FONT_SANS, color=COLOR_TEXT_PRIMARY)
    ax.set_ylabel(ylabel, fontsize=9, family=FONT_SANS, color=COLOR_TEXT_PRIMARY)
    ax.legend(fontsize=8, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=COLOR_TEXT_SECONDARY)


def figure_retrieval_modes_full_corpus() -> Path:
    output_path = SCREENSHOTS_DIR / "retrieval_modes_full_corpus.png"
    data = _load("retrieval_eval_full_corpus.json")
    if data is None:
        return _blocked_figure(output_path, "Recuperation par mode (corpus complet)", "retrieval_eval_full_corpus.json absent")

    modes = data["corpora"]["corpus_1306_full"]["modes"]
    fig = new_figure(8.5, 4.5)
    ax = fig.add_axes((0.1, 0.15, 0.85, 0.65))
    add_title(fig.add_axes((0, 0.9, 1, 0.08), frame_on=False), "Recuperation par mode -- corpus complet (1306 chunks)")
    fig.axes[-1].axis("off")
    _grouped_bar(
        ax,
        group_labels=["lexical", "semantic", "hybrid"],
        series={
            "Recall@5": [modes[m]["mean_recall_at_5"] for m in ("lexical", "semantic", "hybrid")],
            "MRR@5": [modes[m]["mean_mrr_at_5"] for m in ("lexical", "semantic", "hybrid")],
            "nDCG@5": [modes[m]["mean_ndcg_at_5"] for m in ("lexical", "semantic", "hybrid")],
        },
        ylabel="score",
    )
    add_source_note(fig.axes[0], f"Source : retrieval_eval_full_corpus.json ({data['query_count']} requetes reelles).", y=-0.18)
    save_figure(fig, output_path)
    return output_path


def figure_retrieval_149_vs_1306() -> Path:
    output_path = SCREENSHOTS_DIR / "retrieval_149_vs_1306.png"
    data = _load("retrieval_eval_full_corpus.json")
    if data is None:
        return _blocked_figure(output_path, "Corpus 149 vs 1306 (Recall@5)", "retrieval_eval_full_corpus.json absent")

    comparison = data["comparison_149_vs_1306"]
    fig = new_figure(8.5, 4.5)
    ax = fig.add_axes((0.1, 0.15, 0.85, 0.65))
    add_title(fig.add_axes((0, 0.9, 1, 0.08), frame_on=False), "Recall@5 -- corpus reduit (149) vs corpus complet (1306)")
    fig.axes[-1].axis("off")
    modes = ("lexical", "semantic", "hybrid")
    _grouped_bar(
        ax, group_labels=list(modes),
        series={
            "corpus 149 (deception seule)": [comparison[m]["mean_recall_at_5"]["corpus_149"] for m in modes],
            "corpus 1306 (complet)": [comparison[m]["mean_recall_at_5"]["corpus_1306"] for m in modes],
        },
        ylabel="Recall@5",
    )
    add_source_note(fig.axes[0], "Source : retrieval_eval_full_corpus.json, comparison_149_vs_1306.", y=-0.18)
    save_figure(fig, output_path)
    return output_path


def figure_alpha_sweep() -> Path:
    output_path = SCREENSHOTS_DIR / "alpha_sweep.png"
    data = _load("alpha_sweep.json")
    if data is None:
        return _blocked_figure(output_path, "Balayage alpha (fusion hybride)", "alpha_sweep.json absent")

    alphas = data["alphas_tested"]
    results = data["results_by_alpha"]
    fig = new_figure(8.0, 4.5)
    ax = fig.add_axes((0.12, 0.15, 0.8, 0.65))
    add_title(fig.add_axes((0, 0.9, 1, 0.08), frame_on=False), "Balayage de alpha -- corpus complet (1306 chunks)")
    fig.axes[-1].axis("off")
    recall5 = [results[str(a)]["mean_recall_at_5"] for a in alphas]
    mrr5 = [results[str(a)]["mean_mrr_at_5"] for a in alphas]
    ax.plot(alphas, recall5, marker="o", color=BAR_COLORS[0], label="Recall@5")
    ax.plot(alphas, mrr5, marker="s", color=BAR_COLORS[1], label="MRR@5")
    ax.axvline(data["best_alpha"], color=COLOR_TEXT_SECONDARY, linestyle="--", linewidth=1, label=f"alpha retenu={data['best_alpha']}")
    ax.set_xlabel("alpha", fontsize=9, family=FONT_SANS, color=COLOR_TEXT_PRIMARY)
    ax.set_ylabel("score", fontsize=9, family=FONT_SANS, color=COLOR_TEXT_PRIMARY)
    ax.legend(fontsize=8, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    add_source_note(ax, "Source : alpha_sweep.json.", y=-0.18)
    save_figure(fig, output_path)
    return output_path


def figure_reranker_ablation() -> Path:
    output_path = SCREENSHOTS_DIR / "reranker_ablation.png"
    data = _load("reranker_ablation.json")
    if data is None:
        return _blocked_figure(output_path, "Ablation du reclassement (cross-encoder)", "reranker_ablation.json absent")

    metrics = ["mean_recall_at_5", "mean_mrr_at_5", "mean_ndcg_at_5", "mean_hit_rate_at_5"]
    labels = ["Recall@5", "MRR@5", "nDCG@5", "hit-rate@5"]
    fig = new_figure(8.5, 4.5)
    ax = fig.add_axes((0.1, 0.15, 0.85, 0.65))
    add_title(fig.add_axes((0, 0.9, 1, 0.08), frame_on=False), "Ablation du reclassement cross-encoder -- corpus complet")
    fig.axes[-1].axis("off")
    _grouped_bar(
        ax, group_labels=labels,
        series={
            "sans reclassement": [data["without_reranking"][m] for m in metrics],
            "avec reclassement": [data["with_reranking"][m] for m in metrics],
        },
        ylabel="score",
    )
    add_source_note(fig.axes[0], f"Source : reranker_ablation.json (modele : {data['reranker_model']}).", y=-0.18)
    save_figure(fig, output_path)
    return output_path


def figure_llm_conformity_grounding() -> Path:
    output_path = SCREENSHOTS_DIR / "llm_conformity_grounding.png"
    conformity = _load("llm_conformity.json")
    grounding = _load("llm_evidence_grounding.json")
    if conformity is None or grounding is None:
        return _blocked_figure(output_path, "Conformite et ancrage documentaire LLM", "aucun provider LLM reel exploitable (§4)")

    fig = new_figure(6.0, 4.5)
    ax = fig.add_axes((0.15, 0.15, 0.75, 0.65))
    add_title(fig.add_axes((0, 0.9, 1, 0.08), frame_on=False), "Annotation LLM -- conformite et ancrage documentaire")
    fig.axes[-1].axis("off")
    values = [conformity["conformity_rate"], grounding["grounding_rate"] or 0.0]
    ax.bar(["conformite", "ancrage"], values, color=[BAR_COLORS[0], BAR_COLORS[1]], edgecolor=COLOR_BORDER)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("taux", fontsize=9, family=FONT_SANS, color=COLOR_TEXT_PRIMARY)
    ax.spines[["top", "right"]].set_visible(False)
    add_source_note(fig.axes[0], f"Source : llm_conformity.json, llm_evidence_grounding.json (modele : {conformity['model']}).", y=-0.18)
    save_figure(fig, output_path)
    return output_path


def figure_de_stability_temp0() -> Path:
    output_path = SCREENSHOTS_DIR / "de_stability_temp0.png"
    data = _load("llm_stability_temp0.json")
    if data is None:
        return _blocked_figure(output_path, "Stabilite de DE (temperature=0)", "aucun provider LLM reel exploitable (§4)")

    labels = [f"{p['occurrence_id']}\n{p['mechanism_id']}" for p in data["per_candidate"]]
    stdevs = [p["DE_stdev"] for p in data["per_candidate"]]
    fig = new_figure(7.5, 4.5)
    ax = fig.add_axes((0.12, 0.2, 0.83, 0.6))
    add_title(fig.add_axes((0, 0.9, 1, 0.08), frame_on=False), f"Ecart-type de DE sur {data['replay_count_per_candidate']} rejeux (temperature=0)")
    fig.axes[-1].axis("off")
    ax.bar(labels, stdevs, color=BAR_COLORS[3], edgecolor=COLOR_BORDER)
    ax.axhline(data["mean_DE_stdev"], color=COLOR_TEXT_SECONDARY, linestyle="--", linewidth=1, label=f"moyenne={data['mean_DE_stdev']:.4f}")
    ax.set_ylabel("ecart-type de DE", fontsize=9, family=FONT_SANS, color=COLOR_TEXT_PRIMARY)
    ax.legend(fontsize=8, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="x", labelsize=7)
    add_source_note(fig.axes[0], "Source : llm_stability_temp0.json.", y=-0.22)
    save_figure(fig, output_path)
    return output_path


def figure_decision_robustness() -> Path:
    output_path = SCREENSHOTS_DIR / "decision_robustness.png"
    data = _load("decision_robustness.json")
    if data is None:
        return _blocked_figure(output_path, "Robustesse de la decision", "table DE gelee reelle indisponible (§4/§5)")

    epsilons = [str(lvl["epsilon"]) for lvl in data["levels"]]
    fig = new_figure(7.5, 4.5)
    ax = fig.add_axes((0.12, 0.15, 0.83, 0.65))
    add_title(fig.add_axes((0, 0.9, 1, 0.08), frame_on=False), "Robustesse de la decision au bruit d'annotation")
    fig.axes[-1].axis("off")
    _grouped_bar(
        ax, group_labels=epsilons,
        series={
            "plan identique": [lvl["identical_plan_rate"] for lvl in data["levels"]],
            "front de Pareto identique": [lvl["identical_pareto_rate"] for lvl in data["levels"]],
        },
        ylabel="taux",
    )
    ax.set_xlabel("epsilon", fontsize=9, family=FONT_SANS, color=COLOR_TEXT_PRIMARY)
    ax.set_ylim(0, 1.05)
    add_source_note(fig.axes[0], f"Source : decision_robustness.json ({data['n_draws_per_level']} tirages/niveau).", y=-0.18)
    save_figure(fig, output_path)
    return output_path


def figure_performance_scaling() -> Path:
    output_path = SCREENSHOTS_DIR / "performance_scaling.png"
    data = _load("performance.json")
    if data is None:
        return _blocked_figure(output_path, "Passage a l'echelle (performance)", "performance.json absent")

    small = data["instances"]["small"]
    large = data["instances"]["large"]
    fig = new_figure(7.5, 4.5)
    ax = fig.add_axes((0.15, 0.15, 0.8, 0.65))
    add_title(fig.add_axes((0, 0.9, 1, 0.08), frame_on=False), "Latence RAG (contexte+retrieval+reclassement) par candidat")
    fig.axes[-1].axis("off")
    labels = [
        f"petite\n({small['occurrence_count']} occ., {small['admissible_candidate_count']} cand.)",
        f"grande\n({large['occurrence_count']} occ., {large['admissible_candidate_count']} cand.)",
    ]
    values = [
        small["rag_context_plus_retrieval_plus_reranking_mean_seconds_per_candidate"],
        large["rag_context_plus_retrieval_plus_reranking_mean_seconds_per_candidate"],
    ]
    ax.bar(labels, values, color=[BAR_COLORS[0], BAR_COLORS[4]], edgecolor=COLOR_BORDER)
    ax.set_ylabel("secondes / candidat", fontsize=9, family=FONT_SANS, color=COLOR_TEXT_PRIMARY)
    ax.spines[["top", "right"]].set_visible(False)
    add_source_note(fig.axes[0], "Source : performance.json.", y=-0.18)
    save_figure(fig, output_path)
    return output_path


ALL_FIGURES = (
    figure_retrieval_modes_full_corpus,
    figure_retrieval_149_vs_1306,
    figure_alpha_sweep,
    figure_reranker_ablation,
    figure_llm_conformity_grounding,
    figure_de_stability_temp0,
    figure_decision_robustness,
    figure_performance_scaling,
)


def main() -> None:
    for generator in ALL_FIGURES:
        path = generator()
        print(f"Genere : {path}")


if __name__ == "__main__":
    main()
