"""
Réf. tâche « finaliser les artefacts visuels du chapitre 4 ».

Style graphique partagé par les 5 générateurs de figures (C1/C2/C3/C4/C7) :
fond blanc, texte noir/gris foncé, pas de thème terminal sombre, mise en
page sobre adaptée à une insertion `\\textwidth` dans un mémoire A4.

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # export PNG uniquement, aucun affichage interactif

import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Palette académique — réf. tâche §4 (contraintes visuelles)
# ---------------------------------------------------------------------------

COLOR_BACKGROUND = "#ffffff"
COLOR_TEXT_PRIMARY = "#1a1a1a"
COLOR_TEXT_SECONDARY = "#5a5a5a"
COLOR_BORDER = "#333333"
COLOR_HEADER_BG = "#e9e9e9"
COLOR_ROW_ALT_BG = "#f6f6f6"
COLOR_ADMISSIBLE_BG = "#dcecdc"
COLOR_REJECTED_TEXT = "#7a1f1f"
COLOR_ADMISSIBLE_TEXT = "#1f5c1f"

FONT_SANS = "DejaVu Sans"
FONT_MONO = "DejaVu Sans Mono"

DPI = 200


class FigureError(Exception):
    """Erreur de génération d'une figure du chapitre 4."""


def new_figure(width_in: float, height_in: float):
    """Réf. tâche §4 : fond blanc explicite, taille adaptée à
    `\\textwidth` (figures larges, hauteur proportionnelle au contenu)."""
    fig = plt.figure(figsize=(width_in, height_in), dpi=DPI, facecolor=COLOR_BACKGROUND)
    return fig


def save_figure(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, facecolor=COLOR_BACKGROUND, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def add_title(ax, text: str, *, y: float = 1.02, fontsize: float = 15) -> None:
    ax.text(
        0.0, y, text, transform=ax.transAxes, fontsize=fontsize, fontweight="bold",
        color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="bottom", ha="left",
    )


def add_subtitle(ax, text: str, *, y: float = 0.97, fontsize: float = 10) -> None:
    ax.text(
        0.0, y, text, transform=ax.transAxes, fontsize=fontsize, color=COLOR_TEXT_SECONDARY,
        family=FONT_SANS, va="top", ha="left",
    )


def add_source_note(ax, text: str, *, y: float = -0.02, fontsize: float = 8) -> None:
    ax.text(
        0.0, y, text, transform=ax.transAxes, fontsize=fontsize, color=COLOR_TEXT_SECONDARY,
        family=FONT_SANS, va="top", ha="left", style="italic",
    )


def truncate(text: str, max_length: int) -> str:
    text = text.replace("\n", " ").strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."
