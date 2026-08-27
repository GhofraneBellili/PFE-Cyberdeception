"""
Réf. architecture : CLAUDE.md §10 (SP1) — réf. tâche §16 « statistiques de
réduction SP1 ».

Calcule, sur l'instance runtime réelle de `examples/sp1_extended_real_example.py`
(catalogue de connaissances 51 mécanismes, catalogue opérationnel
organisationnel 42 référencés/30 activés, mapping M_{i,d} réel), les
statistiques de réduction demandées par la tâche : |D_knowledge| -> |D_org|
-> |D_i| par technique -> couples évalués -> rejets par critère ->
admissibles.

Exécution :
    python -m examples.sp1_runtime_statistics

Sorties :
    docs/chapter4/outputs/sp1_runtime_statistics.json
    docs/chapter4/outputs/sp1_runtime_statistics.txt
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from src.admissibility import build_admissibility_report, enabled_mechanism_ids
from src.knowledge_deception import load_attack_deception_mapping, load_deception_catalog, to_sp1_mapping
from src.organization_catalog import capabilities_by_id, load_organization_catalog, validate_against_knowledge_catalog
from examples.sp1_extended_real_example import CATALOG_PATH, MAPPING_PATH, ORGANIZATION_CATALOG_PATH, THETA, build_example_instance

OUT_DIR = Path("docs/chapter4/outputs")


def main() -> None:
    kb = load_deception_catalog(CATALOG_PATH)
    attack_mapping = load_attack_deception_mapping(MAPPING_PATH)
    sp1_mapping = to_sp1_mapping(attack_mapping, kb)

    organization_catalog_model = load_organization_catalog(ORGANIZATION_CATALOG_PATH)
    validate_against_knowledge_catalog(organization_catalog_model, kb)
    organization_catalog = dict(capabilities_by_id(organization_catalog_model))

    instance = build_example_instance()
    catalog = dict(kb.mechanisms_by_id)

    report = build_admissibility_report(
        instance, catalog, organization_catalog, sp1_mapping, theta_c=THETA, theta_i=THETA, theta_a=THETA
    )

    d_i_by_occurrence = {
        occurrence_id: len(occ["D_i"]) for occurrence_id, occ in report["occurrences"].items() if not occ["is_terminal"]
    }
    c_i_h_by_occurrence = {
        occurrence_id: len(occ["C_i_h"]) for occurrence_id, occ in report["occurrences"].items() if not occ["is_terminal"]
    }

    rejected_by_mapping = 0
    rejected_by_organization = 0
    rejected_by_autorise = 0
    rejected_by_prerequisites = 0
    rejected_by_pertinent = 0
    admissible_mechanism_ids: set[str] = set()
    occurrences_with_candidate = 0

    for occurrence_id, occ in report["occurrences"].items():
        if occ["is_terminal"]:
            continue
        has_admissible = False
        for candidate in occ["candidates"]:
            if candidate["mapping"] == "fail":
                rejected_by_mapping += 1
                continue
            if candidate["organization"] == "fail":
                rejected_by_organization += 1
                continue
            if candidate["Autorise"] != "pass":
                rejected_by_autorise += 1
            if candidate["PrerequisSatisfaits"] != "pass":
                rejected_by_prerequisites += 1
            if candidate["Pertinent"] != "pass":
                rejected_by_pertinent += 1
            if candidate["admissible"]:
                admissible_mechanism_ids.add(candidate["mechanism_id"])
                has_admissible = True
        if has_admissible:
            occurrences_with_candidate += 1

    d_i_values = list(d_i_by_occurrence.values())
    summary = report["summary"]

    result = {
        "d_knowledge_size": len(catalog),
        "d_org_referenced_size": len(organization_catalog),
        "d_org_enabled_size": len(enabled_mechanism_ids(organization_catalog)),
        "d_i_by_occurrence": d_i_by_occurrence,
        "d_i_stats": {
            "min": min(d_i_values),
            "max": max(d_i_values),
            "mean": sum(d_i_values) / len(d_i_values),
            "median": statistics.median(d_i_values),
        },
        "c_i_h_by_occurrence": c_i_h_by_occurrence,
        "candidate_pairs_evaluated": summary["candidate_count"],
        "rejected_by_mapping": rejected_by_mapping,
        "rejected_by_organization": rejected_by_organization,
        "rejected_by_autorise": rejected_by_autorise,
        "rejected_by_prerequisites_satisfied": rejected_by_prerequisites,
        "rejected_by_pertinent": rejected_by_pertinent,
        "admissible_count": summary["admissible_count"],
        "distinct_admissible_mechanisms": sorted(admissible_mechanism_ids),
        "distinct_admissible_mechanism_count": len(admissible_mechanism_ids),
        "occurrence_count_non_terminal": summary["occurrence_count"] - summary["terminal_occurrence_count"],
        "occurrences_with_at_least_one_candidate": occurrences_with_candidate,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "sp1_runtime_statistics.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "SP1 - Statistiques de reduction runtime (instance reelle)",
        "-" * 78,
        f"|D_knowledge| (catalogue de connaissances)      : {result['d_knowledge_size']}",
        f"|D_org| reference (catalogue operationnel)       : {result['d_org_referenced_size']}",
        f"|D_org| active (enabled=true)                    : {result['d_org_enabled_size']}",
        "-" * 78,
        "|D_i| par occurrence (D_i = D_org active INTER M_i,d) :",
    ]
    for occurrence_id, size in d_i_by_occurrence.items():
        lines.append(f"  {occurrence_id:<20} |D_i|={size:<3} |C_i_h|={c_i_h_by_occurrence[occurrence_id]}")
    lines += [
        f"  min={result['d_i_stats']['min']}  max={result['d_i_stats']['max']}  "
        f"mean={result['d_i_stats']['mean']:.2f}  median={result['d_i_stats']['median']}",
        "-" * 78,
        f"Couples (mecanisme x emplacement) evalues : {result['candidate_pairs_evaluated']}",
        f"  rejetes par mapping (M_i,d=0)            : {result['rejected_by_mapping']}",
        f"  rejetes par organization (non active/non reference) : {result['rejected_by_organization']}",
        f"  rejetes par Autorise                     : {result['rejected_by_autorise']}",
        f"  rejetes par PrerequisSatisfaits           : {result['rejected_by_prerequisites_satisfied']}",
        f"  rejetes par Pertinent                     : {result['rejected_by_pertinent']}",
        f"  ADMISSIBLES                                : {result['admissible_count']}",
        "-" * 78,
        f"Mecanismes admissibles distincts : {result['distinct_admissible_mechanism_count']} {result['distinct_admissible_mechanisms']}",
        f"Occurrences avec >=1 candidat admissible : {result['occurrences_with_at_least_one_candidate']} / {result['occurrence_count_non_terminal']}",
        "-" * 78,
        "Lecture : grand catalogue de connaissances -> reduction operationnelle (D_org) -> reduction",
        "contextuelle par technique (mapping, D_i) -> reduction par SP1 (Autorise/PrerequisSatisfaits/",
        "Pertinent) -> C_i_h. Chaque etage de reduction est visible et attribuable a un critere precis.",
    ]
    text = "\n".join(lines) + "\n"
    (OUT_DIR / "sp1_runtime_statistics.txt").write_text(text, encoding="utf-8")

    print(text)
    print(f"JSON : {OUT_DIR / 'sp1_runtime_statistics.json'}")


if __name__ == "__main__":
    main()
