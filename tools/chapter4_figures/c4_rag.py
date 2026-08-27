"""
Réf. tâche « finaliser les artefacts visuels du chapitre 4 » — Capture C4
(retrieval RAG réel).

Source : docs/chapter4/outputs/rag_retrieval_example.txt (généré par
`python -m examples.rag_example`, colonnes de largeur fixe :
rang(5)/score(8)/type(12)/chunk_id(28)/extrait, réf. examples/rag_example.py).
Chaque ligne du tableau est extraite directement de ce fichier, jamais
retapée à la main. Limité aux 5 premiers résultats déjà présents dans le
fichier source.

Sortie : docs/chapter4/screenshots/04_rag/rag_retrieval.png
"""

from __future__ import annotations

import re
from pathlib import Path

from matplotlib.patches import Rectangle

from tools.chapter4_figures.common import (
    COLOR_BORDER,
    COLOR_HEADER_BG,
    COLOR_ROW_ALT_BG,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_MONO,
    FONT_SANS,
    new_figure,
    save_figure,
    truncate,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RETRIEVAL_PATH = REPO_ROOT / "docs" / "chapter4" / "outputs" / "rag_retrieval_example.txt"
OUTPUT_PATH = REPO_ROOT / "docs" / "chapter4" / "screenshots" / "04_rag" / "rag_retrieval.png"

COLUMNS = ["Rang", "Score", "Type", "chunk_id", "Extrait"]
COLUMN_WIDTHS = [0.6, 0.75, 1.0, 2.5, 4.4]


def load_retrieval() -> tuple[str, str, list[list[str]]]:
    """Réf. docstring de module : parse le fichier texte réel par
    tokenisation (rang/score/type/chunk_id ne contiennent jamais
    d'espace) plutôt que par largeur de colonne fixe — le format source
    (`examples/rag_example.py`, `{chunk_id:<28}`) ne tronque PAS les
    chunk_id plus longs que 28 caractères, ce qui décale les colonnes à
    largeur fixe pour certaines lignes réelles (ex. identifiants Engage
    longs)."""
    lines = RETRIEVAL_PATH.read_text(encoding="utf-8").splitlines()
    index_line = next(line for line in lines if line.startswith("Index"))
    query_line = next(line for line in lines if line.startswith("Requete"))
    query = re.search(r"'(.*)'", query_line).group(1)

    header_index = next(i for i, line in enumerate(lines) if line.startswith("Rang"))
    rows: list[list[str]] = []
    for line in lines[header_index + 1 :]:
        if line.startswith("---") or not line.strip():
            continue
        rank, score, source_type, rest = line.split(maxsplit=3)
        chunk_id, _, excerpt = rest.partition(" ")
        rows.append([rank, score, source_type, chunk_id, excerpt.strip()])
    return index_line.strip(), query, rows


def generate(output_path: Path = OUTPUT_PATH) -> Path:
    index_line, query, rows = load_retrieval()
    rows = rows[:5]

    width = sum(COLUMN_WIDTHS) + 0.5
    row_height = 0.55
    header_height = 0.42
    title_block = 1.35
    footer_block = 0.4
    height = title_block + header_height + row_height * len(rows) + footer_block

    fig = new_figure(width, height)
    ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")

    margin = 0.25
    ax.text(margin, height - 0.3, "Retrieval RAG réel", fontsize=15, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="top", ha="left")
    ax.text(
        margin, height - 0.62, f"Requête : « {truncate(query, 75)} »",
        fontsize=9.5, color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="top", ha="left",
    )
    ax.text(
        margin, height - 0.92, index_line,
        fontsize=8.5, color=COLOR_TEXT_SECONDARY, family=FONT_SANS, va="top", ha="left", style="italic",
    )

    table_top = height - title_block
    col_x = [margin]
    for w in COLUMN_WIDTHS:
        col_x.append(col_x[-1] + w)

    ax.add_patch(Rectangle((margin, table_top - header_height), sum(COLUMN_WIDTHS), header_height, facecolor=COLOR_HEADER_BG, edgecolor=COLOR_BORDER, linewidth=0.8))
    for i, col in enumerate(COLUMNS):
        ax.text(col_x[i] + 0.06, table_top - header_height / 2, col, fontsize=9.5, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="center", ha="left")

    y = table_top - header_height
    for row_index, row in enumerate(rows):
        row_bg = COLOR_ROW_ALT_BG if row_index % 2 else "#ffffff"
        ax.add_patch(Rectangle((margin, y - row_height), sum(COLUMN_WIDTHS), row_height, facecolor=row_bg, edgecolor="#dddddd", linewidth=0.5))
        rank, score, source_type, chunk_id, excerpt = row
        ax.text(col_x[0] + 0.12, y - row_height / 2, rank, fontsize=10, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="center", ha="left")
        ax.text(col_x[1] + 0.06, y - row_height / 2, score, fontsize=9.5, color=COLOR_TEXT_PRIMARY, family=FONT_MONO, va="center", ha="left")
        ax.text(col_x[2] + 0.06, y - row_height / 2, source_type, fontsize=9.5, color=COLOR_TEXT_SECONDARY, family=FONT_SANS, va="center", ha="left")
        ax.text(col_x[3] + 0.06, y - row_height / 2, truncate(chunk_id, 30), fontsize=9, color=COLOR_TEXT_PRIMARY, family=FONT_MONO, va="center", ha="left")
        ax.text(col_x[4] + 0.06, y - row_height / 2, truncate(excerpt, 55), fontsize=9.5, color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="center", ha="left")
        y -= row_height

    ax.text(
        margin, footer_block - 0.15,
        "Source : docs/chapter4/outputs/rag_retrieval_example.txt — src/rag_indexer.py / src/rag_retriever.py "
        "(TF-IDF haché + similarité cosinus).",
        fontsize=8, color=COLOR_TEXT_SECONDARY, family=FONT_SANS, va="bottom", ha="left", style="italic",
    )

    save_figure(fig, output_path)
    return output_path


if __name__ == "__main__":
    path = generate()
    print(f"Genere : {path}")
