"""
Réf. tâche « améliorer réellement la qualité et la latence du moteur RAG »
§4 : les 2 figures requises, générées STRICTEMENT à partir des fichiers
JSON déjà produits (jamais une valeur retapée à la main).

Exécution :
    python -m tools.chapter4_evaluation.improvement_figures
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.chapter4_figures.common import COLOR_BORDER, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, FONT_SANS, add_source_note, add_title, new_figure, save_figure

OUT_DIR = Path("docs/chapter4/evaluation/outputs")
SCREENSHOTS_DIR = Path("docs/chapter4/evaluation/screenshots")
BAR_COLORS = ["#3b6ea5", "#5a9e6f", "#c08a3e", "#8a5a9e", "#b5533e"]


def _load(name: str) -> dict:
    return json.loads((OUT_DIR / name).read_text(encoding="utf-8"))


def figure_retrieval_before_after() -> Path:
    output_path = SCREENSHOTS_DIR / "retrieval_before_after.png"
    final_test = _load("retrieval_final_test.json")

    metrics = ["mean_recall_at_5", "mean_recall_at_10", "mean_mrr_at_5", "mean_ndcg_at_5", "mean_hit_rate_at_5"]
    labels = ["Recall@5", "Recall@10", "MRR@5", "nDCG@5", "hit-rate@5"]
    before = [final_test["baseline"][m] for m in metrics]
    after = [final_test["improved"][m] for m in metrics]

    fig = new_figure(9.0, 5.0)
    ax = fig.add_axes((0.1, 0.15, 0.85, 0.62))
    title_ax = fig.add_axes((0, 0.88, 1, 0.1))
    title_ax.axis("off")
    add_title(title_ax, f"Recuperation -- avant/apres amelioration (jeu TEST, {final_test['query_count']} requetes, confirmation unique)")

    x = list(range(len(labels)))
    width = 0.35
    ax.bar([i - width / 2 for i in x], before, width=width, label="avant (baseline production)", color=BAR_COLORS[0], edgecolor=COLOR_BORDER)
    ax.bar([i + width / 2 for i in x], after, width=width, label="apres (BM25 + instruction BGE + requetes enrichies)", color=BAR_COLORS[1], edgecolor=COLOR_BORDER)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9, family=FONT_SANS, color=COLOR_TEXT_PRIMARY)
    ax.set_ylabel("score", fontsize=9, family=FONT_SANS, color=COLOR_TEXT_PRIMARY)
    ax.legend(fontsize=8, frameon=False, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)

    for i, (b, a) in enumerate(zip(before, after)):
        delta = a - b
        ax.text(i, max(b, a) + 0.02, f"{delta:+.3f}", ha="center", fontsize=7.5, color=COLOR_TEXT_SECONDARY, family=FONT_SANS)

    add_source_note(ax, "Source : retrieval_final_test.json. Combinaison retenue sur DEV (jamais ajustee sur TEST) : BM25 + instruction de requete BGE.", y=-0.16)
    save_figure(fig, output_path)
    return output_path


def figure_latency_before_after() -> Path:
    output_path = SCREENSHOTS_DIR / "latency_before_after.png"
    latency = _load("latency_optimization.json")
    condensed_test = latency["condensed_input"]["test"]
    cache = latency["cache"]

    fig = new_figure(9.0, 5.0)
    ax1 = fig.add_axes((0.08, 0.15, 0.4, 0.62))
    ax2 = fig.add_axes((0.56, 0.15, 0.4, 0.62))
    title_ax = fig.add_axes((0, 0.88, 1, 0.1))
    title_ax.axis("off")
    add_title(title_ax, f"Latence de reclassement -- avant/apres optimisation (jeu TEST, {condensed_test['query_count']} requetes)")

    lat_before = condensed_test["mean_rerank_latency_seconds"]["baseline"]
    lat_after = condensed_test["mean_rerank_latency_seconds"]["final"]
    ax1.bar(["avant\n(texte complet)", "apres\n(texte condense)"], [lat_before, lat_after], color=[BAR_COLORS[0], BAR_COLORS[1]], edgecolor=COLOR_BORDER)
    ax1.set_ylabel("secondes / requete", fontsize=9, family=FONT_SANS, color=COLOR_TEXT_PRIMARY)
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.text(0.5, max(lat_before, lat_after) * 1.05, f"{-condensed_test['latency_improvement_relative']:.1%}",
              ha="center", fontsize=9, color=COLOR_TEXT_SECONDARY, family=FONT_SANS, transform=ax1.transData)

    cache_vals = [cache["first_pass_seconds"], cache["second_pass_seconds"]]
    ax2.bar(["1er passage\n(sans cache)", "2e passage\n(avec cache)"], cache_vals, color=[BAR_COLORS[2], BAR_COLORS[3]], edgecolor=COLOR_BORDER)
    ax2.set_ylabel(f"secondes / {cache['query_count']} requetes", fontsize=9, family=FONT_SANS, color=COLOR_TEXT_PRIMARY)
    ax2.spines[["top", "right"]].set_visible(False)

    add_source_note(ax1, "Source : latency_optimization.json (condensed_input.test).", y=-0.18)
    add_source_note(ax2, "Cache sur charge repetee (memes requetes rejouees, DEV).", y=-0.18)
    save_figure(fig, output_path)
    return output_path


def main() -> None:
    for generator in (figure_retrieval_before_after, figure_latency_before_after):
        path = generator()
        print(f"Genere : {path}")


if __name__ == "__main__":
    main()
