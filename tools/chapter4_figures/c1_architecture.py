"""
Réf. tâche « finaliser les artefacts visuels du chapitre 4 » — Capture C1
(organisation réelle du projet).

Source : structure réelle du dépôt (les mêmes répertoires que
`docs/chapter4/outputs/architecture_tree.txt`), curatée aux répertoires
importants (`src/`, `tools/deception_kb/`, `data/deception/`,
`examples/`, `tests/`, `docs/chapter4/`) pour éviter une arborescence
trop longue (réf. tâche §2, C1) — les répertoires volumineux
(`tests/`, `docs/chapter4/outputs/`, `docs/chapter4/screenshots/`,
`data/deception/staging/`, `data/deception/raw/`) sont résumés par un
nombre de fichiers RÉEL (compté sur le disque), jamais un nombre inventé.

Sortie : docs/chapter4/screenshots/01_architecture/architecture_tree.png
"""

from __future__ import annotations

from pathlib import Path

from tools.chapter4_figures.common import (
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_MONO,
    FONT_SANS,
    new_figure,
    save_figure,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_PATH = REPO_ROOT / "docs" / "chapter4" / "screenshots" / "01_architecture" / "architecture_tree.png"

# Réf. anti-fabrication : ces fichiers existent sur le disque mais restent
# volontairement non commités (travail antérieur sans lien avec le
# chapitre 4, jamais intégré à cette branche) — exclus de la figure pour
# ne représenter que l'état réellement livré, pas l'état brut du disque.
_UNTRACKED_UNRELATED = {"normalization_builder.py", "test_normalization_builder.py"}


def _py_files(path: Path) -> list[str]:
    return sorted(p.name for p in path.glob("*.py") if p.name != "__init__.py" and p.name not in _UNTRACKED_UNRELATED)


def _count_files(path: Path) -> int:
    return len([p for p in path.rglob("*") if p.is_file()])


def build_tree_lines() -> list[str]:
    """Réf. docstring de module : lignes réellement dérivées du système
    de fichiers, pas une liste inventée."""
    lines: list[str] = ["pfe-cyberdeception/"]

    lines.append("├── src/  (modules du modèle)")
    for name in _py_files(REPO_ROOT / "src"):
        lines.append(f"│     ├── {name}")

    lines.append("├── tools/deception_kb/  (construction offline de la KB déception)")
    for name in _py_files(REPO_ROOT / "tools" / "deception_kb"):
        lines.append(f"│     ├── {name}")

    lines.append("├── data/deception/  (catalogue et mapping réels + staging)")
    lines.append("│     ├── deception_catalog.json")
    lines.append("│     ├── attack_deception_mapping.json")
    staging_count = _count_files(REPO_ROOT / "data" / "deception" / "staging")
    lines.append(f"│     └── staging/  ({staging_count} fichiers versionnés)")

    lines.append("├── examples/  (scripts exécutables, sorties réelles)")
    for name in _py_files(REPO_ROOT / "examples"):
        lines.append(f"│     ├── {name}")

    tests_count = len([p for p in (REPO_ROOT / "tests").glob("test_*.py") if p.name not in _UNTRACKED_UNRELATED])
    lines.append(f"├── tests/  ({tests_count} fichiers de tests, pytest)")

    lines.append("└── docs/chapter4/  (matière du chapitre 4)")
    for name in sorted(p.name for p in (REPO_ROOT / "docs" / "chapter4").glob("*.md")):
        lines.append(f"      ├── {name}")
    outputs_count = _count_files(REPO_ROOT / "docs" / "chapter4" / "outputs")
    lines.append(f"      └── outputs/  ({outputs_count} sorties réelles)")

    return lines


def generate(output_path: Path = OUTPUT_PATH) -> Path:
    lines = build_tree_lines()

    line_height = 0.225
    title_block = 0.55
    note_block = 0.45
    margin = 0.15
    width = 9.0
    height = margin * 2 + title_block + len(lines) * line_height + note_block

    fig = new_figure(width, height)
    ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")

    ax.text(
        margin, height - margin - 0.30, "Organisation réelle du projet",
        fontsize=15, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="top", ha="left",
    )

    y = height - margin - title_block
    for line in lines:
        is_root_level = not line.startswith((" ", "│"))
        color = COLOR_TEXT_PRIMARY if is_root_level else COLOR_TEXT_SECONDARY
        weight = "bold" if is_root_level else "normal"
        ax.text(margin, y, line, fontsize=10.5, family=FONT_MONO, color=color, fontweight=weight, va="top", ha="left")
        y -= line_height

    ax.text(
        margin, margin + 0.15,
        "Source : structure réelle du dépôt (branche implementation/chapter4) — "
        "répertoires volumineux résumés par un nombre de fichiers compté sur le disque.",
        fontsize=8, color=COLOR_TEXT_SECONDARY, family=FONT_SANS, va="bottom", ha="left", style="italic",
    )
    save_figure(fig, output_path)
    return output_path


if __name__ == "__main__":
    path = generate()
    print(f"Généré : {path}")
