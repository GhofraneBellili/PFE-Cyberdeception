"""
Réf. tâche « separate knowledge and organization capabilities » §18 :
figure distinguant explicitement OFFLINE (préparation des connaissances)
et ONLINE (construction contextuelle de C_i_h par SP1, au runtime).

Contenu structurel fixe (pas dérivé d'un fichier de sortie — c'est un
diagramme d'architecture, réf. même registre que C1) ; les COMPTEURS
affichés dans chaque bloc sont réels, lus dans
docs/chapter4/outputs/{catalog_statistics,sp1_runtime_statistics}.json.

Sortie : docs/chapter4/screenshots/01_architecture/offline_online_architecture.png
"""

from __future__ import annotations

import json
from pathlib import Path

from matplotlib.patches import FancyArrow, FancyBboxPatch, Rectangle

from tools.chapter4_figures.common import (
    COLOR_BORDER,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_MONO,
    FONT_SANS,
    new_figure,
    save_figure,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CATALOG_STATS_PATH = REPO_ROOT / "docs" / "chapter4" / "outputs" / "catalog_statistics.json"
SP1_STATS_PATH = REPO_ROOT / "docs" / "chapter4" / "outputs" / "sp1_runtime_statistics.json"
OUTPUT_PATH = REPO_ROOT / "docs" / "chapter4" / "screenshots" / "01_architecture" / "offline_online_architecture.png"

OFFLINE_BG = "#eef2f8"
ONLINE_BG = "#eef8ef"
BOX_BG = "#ffffff"
ARROW_COLOR = "#555555"


def _box(ax, x, y, w, h, label, *, fontsize=9.2, sub=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06", facecolor=BOX_BG, edgecolor=COLOR_BORDER, linewidth=0.9))
    if sub:
        ax.text(x + w / 2, y + h / 2 + 0.09, label, fontsize=fontsize, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="center", ha="center")
        ax.text(x + w / 2, y + h / 2 - 0.15, sub, fontsize=7.3, color=COLOR_TEXT_SECONDARY, family=FONT_MONO, va="center", ha="center")
    else:
        ax.text(x + w / 2, y + h / 2, label, fontsize=fontsize, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="center", ha="center")


def _harrow(ax, x0, x1, y):
    ax.add_patch(FancyArrow(x0, y, x1 - x0, 0, width=0.012, head_width=0.09, head_length=0.12, color=ARROW_COLOR, length_includes_head=True))


def _varrow(ax, x, y0, y1):
    ax.add_patch(FancyArrow(x, y0, 0, y1 - y0, width=0.012, head_width=0.09, head_length=0.1, color=ARROW_COLOR, length_includes_head=True))


def generate(output_path: Path = OUTPUT_PATH) -> Path:
    catalog_stats = json.loads(CATALOG_STATS_PATH.read_text(encoding="utf-8"))
    sp1_stats = json.loads(SP1_STATS_PATH.read_text(encoding="utf-8"))

    width, height = 12.4, 9.6
    fig = new_figure(width, height)
    ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")

    margin = 0.35
    ax.text(margin, height - 0.4, "Architecture OFFLINE / ONLINE (réf. tâche §18)", fontsize=16, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="top", ha="left")
    ax.text(margin, height - 0.75, "SP1 est un module runtime : il ne pré-calcule jamais C_i_h pendant la préparation offline de la KB.", fontsize=9, color=COLOR_TEXT_SECONDARY, family=FONT_SANS, va="top", ha="left", style="italic")

    # --- Bloc OFFLINE ---
    offline_top, offline_h = height - 1.1, 3.0
    offline_bottom = offline_top - offline_h
    ax.add_patch(Rectangle((margin, offline_bottom), width - 2 * margin, offline_h, facecolor=OFFLINE_BG, edgecolor=COLOR_BORDER, linewidth=1.1))
    ax.text(margin + 0.2, offline_top - 0.28, "OFFLINE — préparation des connaissances générales", fontsize=11.5, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="top", ha="left")

    src_w, src_h = 2.1, 0.85
    src_y = offline_top - 1.15
    sources = ["ATT&CK", "D3FEND", "Engage", "Littérature\nscientifique"]
    src_gap = (width - 2 * margin - 4 * src_w) / 5
    src_xs = []
    for i, name in enumerate(sources):
        x = margin + src_gap + i * (src_w + src_gap)
        src_xs.append(x)
        _box(ax, x, src_y, src_w, src_h, name)

    kb_w, kb_h = width - 2 * margin - 1.0, 0.95
    kb_x = margin + 0.5
    kb_y = offline_bottom + 0.35
    _box(
        ax, kb_x, kb_y, kb_w, kb_h,
        "Knowledge Base",
        sub=(
            f"deception knowledge catalog ({catalog_stats['mechanism_count']} mécanismes) | "
            f"M_i,d ({catalog_stats['attack_deception_relation_count']} relations) | RAG index"
        ),
        fontsize=10.5,
    )
    center_top = sum(src_xs) / len(src_xs) + src_w / 2
    _varrow(ax, kb_x + kb_w / 2, src_y - 0.03, kb_y + kb_h + 0.03)

    # --- Bloc ONLINE ---
    online_top = offline_bottom - 0.55
    online_h = 4.0
    online_bottom = online_top - online_h
    ax.add_patch(Rectangle((margin, online_bottom), width - 2 * margin, online_h, facecolor=ONLINE_BG, edgecolor=COLOR_BORDER, linewidth=1.1))
    ax.text(margin + 0.2, online_top - 0.28, "ONLINE — construction contextuelle de C_i_h (runtime, par appel)", fontsize=11.5, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="top", ha="left")

    _varrow(ax, kb_x + kb_w / 2, offline_bottom - 0.03, online_top - 0.35 - 0.03)

    ctx_w, ctx_h = 3.15, 0.85
    ctx_y = online_top - 1.15
    contexts = [
        (f"Catalogue opérationnel\nde l'organisation", f"|D_org| référencé={sp1_stats['d_org_referenced_size']} activé={sp1_stats['d_org_enabled_size']}"),
        ("Inventaire SI courant\n+ topologie", None),
        ("Graphe d'attaque\ncourant G", None),
    ]
    ctx_gap = (width - 2 * margin - 3 * ctx_w) / 4
    ctx_centers = []
    for i, (name, sub) in enumerate(contexts):
        x = margin + ctx_gap + i * (ctx_w + ctx_gap)
        ctx_centers.append(x + ctx_w / 2)
        _box(ax, x, ctx_y, ctx_w, ctx_h, name, sub=sub, fontsize=9.5)

    sp1_w, sp1_h = 3.6, 0.85
    sp1_x = margin + (width - 2 * margin - sp1_w) / 2
    sp1_y = ctx_y - 1.05
    _box(ax, sp1_x, sp1_y, sp1_w, sp1_h, "SP1", sub=f"D_i, L_i,h,d, Autorise, PrerequisSatisfaits, Pertinent", fontsize=11)
    for cx in ctx_centers:
        _varrow(ax, cx, ctx_y - 0.03, sp1_y + sp1_h + 0.03)

    chain_y = sp1_y - 0.75
    chain_w, chain_h = 1.75, 0.6
    chain_labels = [f"C_i_h ({sp1_stats['admissible_count']})", "SP2", "SP3", "optimizer", "Y*"]
    chain_gap = (width - 2 * margin - len(chain_labels) * chain_w) / (len(chain_labels) + 1)
    x = margin + chain_gap
    prev_center = None
    for label in chain_labels:
        _box(ax, x, chain_y, chain_w, chain_h, label, fontsize=9.5)
        center = x + chain_w / 2
        if prev_center is not None:
            _harrow(ax, prev_center + chain_w / 2, center - chain_w / 2, chain_y + chain_h / 2)
        prev_center = center
        x += chain_w + chain_gap
    _varrow(ax, sp1_x + sp1_w / 2, sp1_y - 0.03, chain_y + chain_h + 0.03)

    ax.text(
        margin, online_bottom - 0.3,
        "Aucun appel LLM pendant l'optimisation (§17.5). Le budget n'intervient jamais dans SP1 (§7-§8 de la tâche).",
        fontsize=8, color=COLOR_TEXT_SECONDARY, family=FONT_SANS, va="top", ha="left", style="italic",
    )

    save_figure(fig, output_path)
    return output_path


if __name__ == "__main__":
    path = generate()
    print(f"Genere : {path}")
