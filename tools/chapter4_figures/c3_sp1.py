"""
Réf. tâche « finaliser les artefacts visuels du chapitre 4 » — Capture C3
(résultat réel de SP1).

Source : docs/chapter4/outputs/sp1_real_example.json (rapport complet,
catalogue et mapping réels, généré par `python -m examples.sp1_real_example`).
Chaque ligne du tableau est lue directement dans ce fichier, jamais
retapée à la main.

Sortie : docs/chapter4/screenshots/03_sp1/sp1_real_result.png
"""

from __future__ import annotations

import json
from pathlib import Path

from matplotlib.patches import Rectangle

from tools.chapter4_figures.common import (
    COLOR_ADMISSIBLE_BG,
    COLOR_ADMISSIBLE_TEXT,
    COLOR_BORDER,
    COLOR_HEADER_BG,
    COLOR_REJECTED_TEXT,
    COLOR_ROW_ALT_BG,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_MONO,
    FONT_SANS,
    new_figure,
    save_figure,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REPORT_PATH = REPO_ROOT / "docs" / "chapter4" / "outputs" / "sp1_real_example.json"
OUTPUT_PATH = REPO_ROOT / "docs" / "chapter4" / "screenshots" / "03_sp1" / "sp1_real_result.png"

COLUMNS = ["Occurrence", "Mécanisme", "Emplacement", "Autorise", "PrerequisSatisfaits", "Pertinent", "Décision"]
COLUMN_WIDTHS = [1.5, 0.85, 1.15, 1.2, 1.75, 1.2, 1.15]


def load_rows() -> tuple[list[list[str]], dict]:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    rows: list[list[str]] = []
    for occurrence_id, occ in report["occurrences"].items():
        for candidate in occ["candidates"]:
            decision = "ADMISSIBLE" if candidate["admissible"] else "REJETE"
            rows.append(
                [
                    occurrence_id,
                    candidate["mechanism_id"],
                    candidate["location_id"],
                    candidate["Autorise"],
                    candidate["PrerequisSatisfaits"],
                    candidate["Pertinent"],
                    decision,
                ]
            )
    return rows, report["summary"]


def generate(output_path: Path = OUTPUT_PATH) -> Path:
    rows, summary = load_rows()

    width = sum(COLUMN_WIDTHS) + 0.5
    row_height = 0.42
    header_height = 0.42
    title_block = 0.95
    summary_block = 0.7
    footer_block = 0.4
    height = title_block + header_height + row_height * len(rows) + summary_block + footer_block

    fig = new_figure(width, height)
    ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")

    margin = 0.25
    ax.text(
        margin, height - 0.3, "Résultat réel de SP1 — catalogue et mapping réels",
        fontsize=15, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="top", ha="left",
    )
    ax.text(
        margin, height - 0.65,
        "docs/chapter4/outputs/sp1_real_example.json — src/admissibility.py",
        fontsize=8.5, color=COLOR_TEXT_SECONDARY, family=FONT_SANS, va="top", ha="left", style="italic",
    )

    table_top = height - title_block
    col_x = [margin]
    for w in COLUMN_WIDTHS:
        col_x.append(col_x[-1] + w)

    # En-tête
    ax.add_patch(Rectangle((margin, table_top - header_height), sum(COLUMN_WIDTHS), header_height, facecolor=COLOR_HEADER_BG, edgecolor=COLOR_BORDER, linewidth=0.8))
    for i, col in enumerate(COLUMNS):
        ax.text(col_x[i] + 0.06, table_top - header_height / 2, col, fontsize=8.7, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="center", ha="left")

    y = table_top - header_height
    for row_index, row in enumerate(rows):
        is_admissible = row[-1] == "ADMISSIBLE"
        row_bg = COLOR_ADMISSIBLE_BG if is_admissible else (COLOR_ROW_ALT_BG if row_index % 2 else "#ffffff")
        ax.add_patch(Rectangle((margin, y - row_height), sum(COLUMN_WIDTHS), row_height, facecolor=row_bg, edgecolor="#dddddd", linewidth=0.5))
        for i, value in enumerate(row):
            color = COLOR_TEXT_PRIMARY
            weight = "normal"
            if i == len(row) - 1:
                color = COLOR_ADMISSIBLE_TEXT if is_admissible else COLOR_REJECTED_TEXT
                weight = "bold"
            elif value == "undetermined":
                color = "#8a6d1a"
            elif value == "fail":
                color = COLOR_REJECTED_TEXT
            elif value == "pass":
                color = COLOR_ADMISSIBLE_TEXT
            ax.text(col_x[i] + 0.06, y - row_height / 2, value, fontsize=8.3, color=color, family=FONT_MONO, fontweight=weight, va="center", ha="left")
        y -= row_height

    # Synthèse
    summary_top = y - 0.15
    summary_text = (
        f"Candidats bruts : {summary['candidate_count']}    |    "
        f"Admissibles : {summary['admissible_count']}    |    "
        f"Rejetés : {summary['rejected_count']}"
    )
    ax.add_patch(Rectangle((margin, summary_top - 0.5), sum(COLUMN_WIDTHS), 0.5, facecolor="#f0f0f0", edgecolor=COLOR_BORDER, linewidth=0.8))
    ax.text(margin + 0.15, summary_top - 0.25, summary_text, fontsize=10.5, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="center", ha="left")

    ax.text(
        margin, footer_block - 0.15,
        "Candidat réel admissible : T1039@FS01 / D3-DNR / shared-drive — après audit documentaire des prérequis "
        "(docs/chapter4/ADMISSIBILITY_EVIDENCE_AUDIT.md).",
        fontsize=8, color=COLOR_TEXT_SECONDARY, family=FONT_SANS, va="bottom", ha="left", style="italic",
    )

    save_figure(fig, output_path)
    return output_path


if __name__ == "__main__":
    path = generate()
    print(f"Genere : {path}")
