"""
Réf. architecture : CLAUDE.md §14 (SP3) / prompt d'implémentation §0bis
(ancre de validation) — exemple exécutable réel.

Rejoue le scénario de référence (T1566/T1190 -> T1003 -> T1078 -> T1059 ->
T1041, déception DE=0.429 sur T1003 uniquement) avec/sans déception, et
produit une sortie RÉELLE de src/risk_engine.py pour le chapitre 4
(Capture 8). Les valeurs numériques ici reproduites sont exactement
celles vérifiées par tests/test_risk_engine.py::TestReferenceExample —
aucune valeur n'est recopiée à la main : ce script appelle le même code
de production.

Exécution :
    python -m examples.sp3_example

Sorties :
    docs/chapter4/outputs/risk_example.csv
    docs/chapter4/outputs/risk_example.txt
"""

from __future__ import annotations

import csv
from pathlib import Path

from src.risk_engine import compute_aggregated_impact, propagate_risk
from src.schemas import AttackGraph, AttackGraphEdge, NodeAttributes, TechniqueOccurrence

OUT_DIR = Path("docs/chapter4/outputs")


def make_occurrence(technique_id: str, asset_id: str, *, tactics=None) -> TechniqueOccurrence:
    return TechniqueOccurrence(
        technique_id=technique_id,
        asset_id=asset_id,
        attributes=NodeAttributes(
            tactics=tactics or ["execution"],
            outcomes=[],
            q_local_success=0.5,
            impact_confidentiality=0.5,
            impact_integrity=0.5,
            impact_availability=0.5,
            critical_asset=False,
            accessible_asset=True,
        ),
    )


def build_reference_graph() -> AttackGraph:
    nodes = [
        make_occurrence("T1566", "H1", tactics=["initial-access"]),
        make_occurrence("T1190", "H2", tactics=["initial-access"]),
        make_occurrence("T1003", "H3"),
        make_occurrence("T1078", "H3"),
        make_occurrence("T1059", "H4"),
        make_occurrence("T1057", "H5"),
        make_occurrence("T1082", "H6"),
        make_occurrence("T1041", "H7"),
    ]
    edges = [
        AttackGraphEdge(source_id="T1566@H1", target_id="T1003@H3"),
        AttackGraphEdge(source_id="T1190@H2", target_id="T1003@H3"),
        AttackGraphEdge(source_id="T1003@H3", target_id="T1078@H3"),
        AttackGraphEdge(source_id="T1078@H3", target_id="T1059@H4"),
        AttackGraphEdge(source_id="T1078@H3", target_id="T1057@H5"),
        AttackGraphEdge(source_id="T1078@H3", target_id="T1082@H6"),
        AttackGraphEdge(source_id="T1059@H4", target_id="T1041@H7"),
    ]
    return AttackGraph(nodes=nodes, edges=edges)


def reference_inputs() -> tuple[dict[str, float], dict[str, float]]:
    q = {
        "T1566@H1": 0.55,
        "T1190@H2": 0.35,
        "T1003@H3": 0.80,
        "T1078@H3": 0.75,
        "T1059@H4": 0.55,
        "T1057@H5": 0.5,
        "T1082@H6": 0.5,
        "T1041@H7": 0.70,
    }
    impact = {occ: 0.5 for occ in q}
    impact["T1041@H7"] = compute_aggregated_impact(1.0, 0.2, 0.1)  # I = 0.67
    return q, impact


def render_table(results: dict[str, dict], title: str) -> str:
    lines = [title, "-" * 66, f"{'Noeud':<12}{'A':<10}{'Gamma':<10}{'P':<10}{'I':<10}{'R'}"]
    for occurrence_id, values in results.items():
        lines.append(
            f"{occurrence_id:<12}{values['A']:<10.4f}{values['Gamma']:<10.4f}"
            f"{values['P']:<10.4f}{values['I']:<10.4f}{values['R']:.4f}"
        )
    return "\n".join(lines)


def main() -> None:
    graph = build_reference_graph()
    q, impact = reference_inputs()

    results_with = propagate_risk(graph, q_by_occurrence=q, de_by_occurrence={"T1003@H3": 0.429}, impact_by_occurrence=impact)
    results_without = propagate_risk(graph, q_by_occurrence=q, de_by_occurrence={}, impact_by_occurrence=impact)

    r_avec = results_with["T1041@H7"]["R"]
    r_sans = results_without["T1041@H7"]["R"]
    reduction = (r_sans - r_avec) / r_sans

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUT_DIR / "risk_example.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["scenario", "Noeud", "A", "Gamma", "P", "I", "R", "DE"])
        for scenario_name, results in (("avec_deception", results_with), ("sans_deception", results_without)):
            for occurrence_id, values in results.items():
                writer.writerow(
                    [scenario_name, occurrence_id, values["A"], values["Gamma"], values["P"], values["I"], values["R"], values["DE"]]
                )

    text_report = (
        render_table(results_with, "SP3 - Avec deception (DE=0.429 sur T1003)")
        + "\n\n"
        + render_table(results_without, "SP3 - Sans deception")
        + "\n\n"
        + "-" * 66
        + f"\nR_avec_deception (T1041) = {r_avec:.4f}\n"
        + f"R_sans_deception (T1041) = {r_sans:.4f}\n"
        + f"Reduction relative        = {reduction * 100:.1f} %\n"
    )
    (OUT_DIR / "risk_example.txt").write_text(text_report, encoding="utf-8")

    print(text_report)
    print(f"CSV complet  : {OUT_DIR / 'risk_example.csv'}")
    print(f"Resume texte : {OUT_DIR / 'risk_example.txt'}")


if __name__ == "__main__":
    main()
