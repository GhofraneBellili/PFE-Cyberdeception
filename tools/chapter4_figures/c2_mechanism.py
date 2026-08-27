"""
Réf. tâche « finaliser les artefacts visuels du chapitre 4 » — Capture C2
(fiche d'un mécanisme réel du catalogue).

Source : data/deception/deception_catalog.json (mécanisme "D3-DNR" —
utilisé de préférence car il possède des propriétés d'admissibilité
réellement renseignées après l'audit documentaire, réf.
docs/chapter4/ADMISSIBILITY_EVIDENCE_AUDIT.md). Aucune valeur affichée
n'est inventée : chaque champ est lu directement dans le fichier JSON
réel, pas recopié à la main.

Sortie : docs/chapter4/screenshots/02_knowledge/deception_mechanism.png
"""

from __future__ import annotations

import json
from pathlib import Path

from matplotlib.patches import Rectangle

from tools.chapter4_figures.common import (
    COLOR_BORDER,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_MONO,
    FONT_SANS,
    new_figure,
    save_figure,
    truncate,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CATALOG_PATH = REPO_ROOT / "data" / "deception" / "deception_catalog.json"
OUTPUT_PATH = REPO_ROOT / "docs" / "chapter4" / "screenshots" / "02_knowledge" / "deception_mechanism.png"

MECHANISM_ID = "D3-DNR"


def load_mechanism(mechanism_id: str = MECHANISM_ID) -> dict:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return next(m for m in catalog["mechanisms"] if m["id"] == mechanism_id)


def generate(output_path: Path = OUTPUT_PATH) -> Path:
    mechanism = load_mechanism()
    profile = mechanism["admissibility_profile"]
    kb_evidence = next(e for e in mechanism["evidence"] if e["source"].endswith("kb-article"))
    kb_excerpt = truncate(kb_evidence["passage"].split("\n\n")[0].replace("## How it works\n", ""), 220)

    fields = [
        ("ID", mechanism["id"]),
        ("Nom", mechanism["name"]),
        ("Description", mechanism["description"]),
        ("Artefact cible (target_artifacts)", ", ".join(mechanism["target_artifacts"])),
        ("Emplacement possible (possible_placements)", ", ".join(mechanism["possible_placements"])),
        ("Type d'actif requis (required_asset_types)", ", ".join(profile["required_asset_types"])),
        ("Mécanisme d'interaction (interaction_mechanism)", mechanism["interaction_mechanism"]),
        ("Version", mechanism["version"]),
    ]

    width = 9.0
    row_height = 0.5
    header_height = 0.9
    evidence_height = 1.3
    footer_height = 0.55
    height = header_height + row_height * len(fields) + evidence_height + footer_height

    fig = new_figure(width, height)
    ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")

    margin = 0.25
    ax.text(
        margin, height - margin, "Fiche d'un mécanisme réel du catalogue de déception",
        fontsize=15, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="top", ha="left",
    )
    ax.text(
        margin, height - margin - 0.35,
        "data/deception/deception_catalog.json — catalogue réel, construit par tools/deception_kb/catalog_builder.py",
        fontsize=8.5, color=COLOR_TEXT_SECONDARY, family=FONT_SANS, va="top", ha="left", style="italic",
    )

    label_x = margin
    value_x = 3.7
    y = height - header_height
    for label, value in fields:
        ax.add_patch(
            Rectangle(
                (margin - 0.05, y - row_height + 0.08), width - 2 * (margin - 0.05), row_height - 0.08,
                fill=False, edgecolor="#dddddd", linewidth=0.6,
            )
        )
        ax.text(label_x, y - 0.12, label, fontsize=9.5, color=COLOR_TEXT_SECONDARY, family=FONT_SANS, va="top", ha="left")
        ax.text(
            value_x, y - 0.12, truncate(value, 52) or "(vide)", fontsize=10.5, color=COLOR_TEXT_PRIMARY,
            family=FONT_MONO, va="top", ha="left", fontweight="bold" if label == "ID" else "normal",
        )
        y -= row_height

    # Bloc de preuve documentaire
    evidence_top = y - 0.1
    ax.add_patch(
        Rectangle(
            (margin - 0.05, evidence_top - evidence_height + 0.1), width - 2 * (margin - 0.05), evidence_height - 0.15,
            fill=True, facecolor="#f6f6f6", edgecolor="#dddddd", linewidth=0.6,
        )
    )
    ax.text(
        label_x + 0.1, evidence_top - 0.12, f"Preuve documentaire — source : {kb_evidence['source']}",
        fontsize=9, color=COLOR_TEXT_SECONDARY, family=FONT_SANS, va="top", ha="left", fontweight="bold",
    )
    ax.text(
        label_x + 0.1, evidence_top - 0.45, f"« {kb_excerpt} »",
        fontsize=9.5, color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="top", ha="left", wrap=True,
    )

    ax.text(
        margin, footer_height - 0.25,
        "Note : required_asset_types renseigné après audit documentaire (§4.3.3 FINAL_TECHNICAL_REPORT.md) — "
        "aucune valeur inventée, traçable au passage ci-dessus.",
        fontsize=8, color=COLOR_TEXT_SECONDARY, family=FONT_SANS, va="bottom", ha="left", style="italic",
    )

    save_figure(fig, output_path)
    return output_path


if __name__ == "__main__":
    path = generate()
    print(f"Genere : {path}")
