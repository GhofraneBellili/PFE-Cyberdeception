"""
Réf. tâche « finaliser les artefacts visuels du chapitre 4 » puis réf.
tâche « separate knowledge and organization capabilities » (§17 : mettre
à jour C3 pour représenter D_org -> D_i -> Autorise -> PrerequisSatisfaits
-> Pertinent -> C_i_h) — Capture C3 (résultat réel de SP1, runtime).

Sources (jamais retapées à la main) :
- docs/chapter4/outputs/sp1_runtime_statistics.json (tailles D_knowledge/
  D_org, rejets par critère)
- docs/chapter4/outputs/sp1_extended_real_example.json (candidats
  admissibles réels, pour le tableau du bas)

Sortie : docs/chapter4/screenshots/03_sp1/sp1_real_result.png
"""

from __future__ import annotations

import json
from pathlib import Path

from matplotlib.patches import FancyArrow, Rectangle

from tools.chapter4_figures.common import (
    COLOR_ADMISSIBLE_BG,
    COLOR_ADMISSIBLE_TEXT,
    COLOR_BORDER,
    COLOR_HEADER_BG,
    COLOR_ROW_ALT_BG,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_MONO,
    FONT_SANS,
    new_figure,
    save_figure,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATS_PATH = REPO_ROOT / "docs" / "chapter4" / "outputs" / "sp1_runtime_statistics.json"
REPORT_PATH = REPO_ROOT / "docs" / "chapter4" / "outputs" / "sp1_extended_real_example.json"
OUTPUT_PATH = REPO_ROOT / "docs" / "chapter4" / "screenshots" / "03_sp1" / "sp1_real_result.png"

FUNNEL_COLOR = "#3a6ea5"


def compute_funnel_stages() -> list[tuple[str, int]]:
    """Réduction SÉQUENTIELLE réelle (pas une somme de rejets qui se
    chevauchent) : combien de couples (mécanisme, emplacement) survivent
    après chaque critère successif, dans l'ordre réellement évalué par
    src/admissibility.py::_build_candidate_diagnostic."""
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    all_candidates = [c for occ in report["occurrences"].values() for c in occ["candidates"]]

    total = len(all_candidates)
    after_mapping = [c for c in all_candidates if c["mapping"] == "pass"]
    after_organization = [c for c in after_mapping if c["organization"] == "pass"]
    after_autorise = [c for c in after_organization if c["Autorise"] == "pass"]
    after_prerequisites = [c for c in after_autorise if c["PrerequisSatisfaits"] == "pass"]
    after_pertinent = [c for c in after_prerequisites if c["Pertinent"] == "pass"]

    # Réf. tâche §17 : le premier stade (couples bruts évalués, 51
    # mécanismes x 13 emplacements x 9 occurrences) est affiché séparément
    # (texte, pas une barre) — sa taille écrase visuellement toute
    # comparaison avec les stades suivants sur une échelle linéaire commune.
    return total, [
        ("après mapping (M_i,d = 1)", len(after_mapping)),
        ("après organization (référencé + activé)", len(after_organization)),
        ("après Autorise", len(after_autorise)),
        ("après PrerequisSatisfaits", len(after_prerequisites)),
        ("C_i_h final (après Pertinent)", len(after_pertinent)),
    ]


def load_admissible_rows() -> list[list[str]]:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    rows: list[list[str]] = []
    for occurrence_id, occ in report["occurrences"].items():
        for candidate in occ["candidates"]:
            if candidate["admissible"]:
                rows.append([occurrence_id, candidate["mechanism_id"], candidate["location_id"]])
    return rows


def generate(output_path: Path = OUTPUT_PATH) -> Path:
    stats = json.loads(STATS_PATH.read_text(encoding="utf-8"))
    total_evaluated, funnel = compute_funnel_stages()
    rows = load_admissible_rows()

    width = 11.0
    stage_gap = 0.95
    funnel_block = 0.5 + stage_gap * len(funnel)
    row_height = 0.30
    header_height = 0.34
    table_title_block = 0.5
    footer_block = 0.55
    height = 1.5 + funnel_block + table_title_block + header_height + row_height * len(rows) + footer_block

    fig = new_figure(width, height)
    ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")

    margin = 0.3
    ax.text(
        margin, height - 0.35, "SP1 (runtime) — réduction D_knowledge → D_org → D_i → C_i_h",
        fontsize=15, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="top", ha="left",
    )
    ax.text(
        margin, height - 0.7,
        "docs/chapter4/outputs/sp1_runtime_statistics.json + sp1_extended_real_example.json — src/admissibility.py",
        fontsize=8.5, color=COLOR_TEXT_SECONDARY, family=FONT_SANS, va="top", ha="left", style="italic",
    )

    top_line_y = height - 1.05
    ax.text(
        margin, top_line_y,
        f"|D_knowledge| = {stats['d_knowledge_size']}     |D_org| référencé = {stats['d_org_referenced_size']}"
        f"     |D_org| activé = {stats['d_org_enabled_size']}     couples (mécanisme x emplacement) évalués = {total_evaluated}",
        fontsize=9.5, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_MONO, va="top", ha="left", wrap=True,
    )

    # --- Entonnoir de réduction séquentielle (à partir du premier stade
    # réellement évalué, mapping M_i,d — le total brut de 51 x 13 x 9 est
    # rapporté en texte ci-dessus, pas dans la barre : sa taille écrase
    # visuellement toute comparaison avec les stades suivants).
    funnel_top = top_line_y - 0.6
    max_value = funnel[0][1]
    label_col_width = 3.1
    bar_max_width = width - 2 * margin - label_col_width - 1.2
    bar_height = 0.42

    y = funnel_top
    for i, (label, value) in enumerate(funnel):
        bar_width = max(0.12, (value / max_value) * bar_max_width)
        is_final = i == len(funnel) - 1
        color = COLOR_ADMISSIBLE_TEXT if is_final else FUNNEL_COLOR
        label_x = margin + label_col_width
        ax.text(margin, y - bar_height / 2, label, fontsize=8.6, color=COLOR_TEXT_SECONDARY, family=FONT_SANS, va="center", ha="left")
        ax.add_patch(Rectangle((label_x, y - bar_height), bar_width, bar_height, facecolor=color, edgecolor=COLOR_BORDER, linewidth=0.6))
        ax.text(label_x + bar_width + 0.15, y - bar_height / 2, f"{value}", fontsize=10, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_MONO, va="center", ha="left")
        if i < len(funnel) - 1:
            ax.add_patch(
                FancyArrow(
                    label_x + 0.25, y - bar_height - 0.06, 0, -(stage_gap - bar_height - 0.14),
                    width=0.012, head_width=0.09, head_length=0.09, color=COLOR_TEXT_SECONDARY, length_includes_head=True,
                )
            )
        y -= stage_gap

    # --- Tableau des candidats réellement admissibles ---
    table_top = y - 0.15
    ax.text(margin, table_top, f"Candidats réellement admissibles ({len(rows)})", fontsize=11.5, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="top", ha="left")

    columns = ["Occurrence", "Mécanisme", "Emplacement"]
    col_widths = [2.2, 1.6, 2.6]
    table_top -= table_title_block
    col_x = [margin]
    for w in col_widths:
        col_x.append(col_x[-1] + w)

    ax.add_patch(Rectangle((margin, table_top - header_height), sum(col_widths), header_height, facecolor=COLOR_HEADER_BG, edgecolor=COLOR_BORDER, linewidth=0.8))
    for i, col in enumerate(columns):
        ax.text(col_x[i] + 0.06, table_top - header_height / 2, col, fontsize=8.5, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="center", ha="left")

    y = table_top - header_height
    for row_index, row in enumerate(rows):
        row_bg = COLOR_ADMISSIBLE_BG if row_index % 2 == 0 else COLOR_ROW_ALT_BG
        ax.add_patch(Rectangle((margin, y - row_height), sum(col_widths), row_height, facecolor=row_bg, edgecolor="#dddddd", linewidth=0.4))
        for i, value in enumerate(row):
            ax.text(col_x[i] + 0.06, y - row_height / 2, value, fontsize=7.6, color=COLOR_TEXT_PRIMARY, family=FONT_MONO, va="center", ha="left")
        y -= row_height

    ax.text(
        margin, footer_block - 0.2,
        f"Mécanismes admissibles distincts : {stats['distinct_admissible_mechanism_count']} "
        f"({', '.join(stats['distinct_admissible_mechanisms'])}) — "
        f"occurrences couvertes : {stats['occurrences_with_at_least_one_candidate']}/{stats['occurrence_count_non_terminal']}.",
        fontsize=7.8, color=COLOR_TEXT_SECONDARY, family=FONT_SANS, va="bottom", ha="left", style="italic", wrap=True,
    )

    save_figure(fig, output_path)
    return output_path


if __name__ == "__main__":
    path = generate()
    print(f"Genere : {path}")
