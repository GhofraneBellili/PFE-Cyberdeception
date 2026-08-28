"""
Réf. tâche « finaliser les artefacts visuels du chapitre 4 » — Capture C7
(orchestration).

Source : docs/chapter4/outputs/pipeline_example.txt (généré par
`python -m examples.orchestrator_example`). Cette figure sert
UNIQUEMENT à démontrer l'intégration technique de l'orchestrateur — les
valeurs expérimentales de risque/Pareto (réservées au chapitre 5) ne
sont volontairement PAS mises en avant : seule l'étape « Risques » est
cochée comme complétée, sans afficher les valeurs numériques.

Sortie : docs/chapter4/screenshots/09_pipeline/pipeline_result.png
"""

from __future__ import annotations

import re
from pathlib import Path

from matplotlib.patches import Circle, Rectangle

from tools.chapter4_figures.common import (
    COLOR_ADMISSIBLE_TEXT,
    COLOR_BORDER,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_MONO,
    FONT_SANS,
    new_figure,
    save_figure,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PIPELINE_PATH = REPO_ROOT / "docs" / "chapter4" / "outputs" / "pipeline_example.txt"
OUTPUT_PATH = REPO_ROOT / "docs" / "chapter4" / "screenshots" / "09_pipeline" / "pipeline_result.png"

STEPS = [
    "Candidats (SP1)",
    "Contexte RAG (RagCandidateContext)",
    "Requêtes Q_realism/Q_interaction/Q_effect",
    "Retrieval + reranking + diversification",
    "CandidateEvidenceBundle",
    "Annotations (SP2)",
    "Table figée",
    "Coûts",
    "Plan (optimisation)",
    "Risques",
    "Manifest",
]


def load_pipeline_summary() -> dict:
    text = PIPELINE_PATH.read_text(encoding="utf-8")
    run_id = re.search(r"run_id\s*:\s*(\S+)", text).group(1)
    files_line = re.search(r"Fichiers ecrits.*?:\s*(.+)", text).group(1)
    files = sorted(f.strip() for f in files_line.split(","))
    candidates = re.search(r"Candidats evalues / admissibles\s*:\s*(\d+)\s*/\s*(\d+)", text)
    return {
        "run_id": run_id,
        "files": files,
        "candidates_evaluated": candidates.group(1),
        "candidates_admissible": candidates.group(2),
    }


def generate(output_path: Path = OUTPUT_PATH) -> Path:
    summary = load_pipeline_summary()
    files = summary["files"]

    width = 9.5
    title_block = 1.35
    steps_block = 0.35 * ((len(STEPS) + 1) // 2) + 0.4
    files_block = 0.32 * len(files) + 0.55
    footer_block = 0.55
    height = title_block + steps_block + files_block + footer_block

    fig = new_figure(width, height)
    ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")

    margin = 0.3
    ax.text(margin, height - 0.32, "Orchestration du pipeline complet", fontsize=15, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="top", ha="left")
    ax.text(
        margin, height - 0.65,
        f"run_id : {summary['run_id']}   —   candidats évalués : {summary['candidates_evaluated']}   —   admissibles : {summary['candidates_admissible']}",
        fontsize=10, color=COLOR_TEXT_PRIMARY, family=FONT_MONO, va="top", ha="left",
    )
    ax.text(
        margin, height - 0.95,
        "src/orchestrator.py — même pipeline RAG contextuel que C4 : SP1 → contexte → 3 requêtes → retrieval+reranking "
        "→ evidence bundle → annotation → gel → coût → (P) → risque → rapport",
        fontsize=8.5, color=COLOR_TEXT_SECONDARY, family=FONT_SANS, va="top", ha="left", style="italic",
    )

    # Bloc étapes (2 colonnes, coche verte = étape completee)
    steps_top = height - title_block
    ax.text(margin, steps_top, "Étapes exécutées", fontsize=10.5, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="top", ha="left")
    col_width = (width - 2 * margin) / 2
    row_h = 0.35
    rows_per_col = (len(STEPS) + 1) // 2
    for i, step in enumerate(STEPS):
        col = i // rows_per_col
        row = i % rows_per_col
        x = margin + col * col_width
        y = steps_top - 0.4 - row * row_h
        ax.add_patch(Circle((x + 0.09, y - 0.03), 0.075, facecolor=COLOR_ADMISSIBLE_TEXT, edgecolor="none"))
        ax.text(x + 0.09, y - 0.03, "✓", fontsize=8, color="white", family=FONT_SANS, va="center", ha="center", fontweight="bold")
        ax.text(x + 0.28, y - 0.03, step, fontsize=9, color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="center", ha="left")

    # Bloc fichiers produits
    files_top = steps_top - steps_block
    ax.text(margin, files_top, f"Fichiers produits — runs/{summary['run_id']}/ ({len(files)} fichiers)", fontsize=10.5, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="top", ha="left")
    ax.add_patch(
        Rectangle(
            (margin, files_top - files_block + 0.35), width - 2 * margin, files_block - 0.45,
            facecolor="#f6f6f6", edgecolor="#dddddd", linewidth=0.6,
        )
    )
    y = files_top - 0.32
    for f in files:
        ax.text(margin + 0.2, y, f"• {f}", fontsize=9, color=COLOR_TEXT_PRIMARY, family=FONT_MONO, va="top", ha="left")
        y -= 0.32

    ax.text(
        margin, footer_block - 0.2,
        "Note : les valeurs de risque et le front de Pareto (analyse quantitative) sont réservés au chapitre 5 — "
        "cette figure démontre uniquement l'intégration technique du pipeline.",
        fontsize=8, color=COLOR_TEXT_SECONDARY, family=FONT_SANS, va="bottom", ha="left", style="italic",
    )

    save_figure(fig, output_path)
    return output_path


if __name__ == "__main__":
    path = generate()
    print(f"Genere : {path}")
