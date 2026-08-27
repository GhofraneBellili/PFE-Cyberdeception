"""
Réf. tâche « finaliser les artefacts visuels du chapitre 4 » + réf. tâche
« separate knowledge and organization capabilities » §17-§18.

Point d'entrée unique régénérant les 6 figures PNG C1/C2/C3/C4/C7/C8 à
partir des sorties réelles du dépôt. C5/C6 ne sont volontairement pas
générées ici (dépendent d'une exécution LLM réelle absente de cet
environnement).

Exécution :
    python -m tools.chapter4_figures.generate_all
"""

from __future__ import annotations

from tools.chapter4_figures import c1_architecture, c2_mechanism, c3_sp1, c4_rag, c7_pipeline, c8_offline_online


def main() -> None:
    generators = [
        ("C1", c1_architecture.generate),
        ("C2", c2_mechanism.generate),
        ("C3", c3_sp1.generate),
        ("C4", c4_rag.generate),
        ("C7", c7_pipeline.generate),
        ("C8", c8_offline_online.generate),
    ]
    for label, generate in generators:
        path = generate()
        print(f"{label} -> {path}")


if __name__ == "__main__":
    main()
