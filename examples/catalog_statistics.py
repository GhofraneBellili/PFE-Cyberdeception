"""
Réf. architecture : CLAUDE.md §9/§10 — réf. tâche §10 « statistiques de
couverture du nouveau catalogue » : vérifie réellement que « 125
techniques -> 3 mécanismes » n'est plus la situation dominante, à partir
du catalogue et du mapping ÉTENDUS déjà écrits sur disque
(`data/deception/deception_catalog.json`,
`data/deception/attack_deception_mapping.json`,
`tools/deception_kb/catalog_builder.py`,
`tools/deception_kb/mapping_builder.py`).

Exécution :
    python -m examples.catalog_statistics

Sorties :
    docs/chapter4/outputs/catalog_statistics.json
    docs/chapter4/outputs/catalog_statistics.txt
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path

CATALOG_PATH = Path("data/deception/deception_catalog.json")
MAPPING_PATH = Path("data/deception/attack_deception_mapping.json")
OUT_DIR = Path("docs/chapter4/outputs")


def mechanism_family(mechanism_id: str) -> str:
    if mechanism_id.startswith("D3-"):
        return "d3fend"
    if mechanism_id.startswith("EAC") or mechanism_id.startswith("SAC"):
        return "engage"
    if mechanism_id.startswith("LIT-"):
        return "literature"
    return "other"


def main() -> None:
    catalog = json.loads(CATALOG_PATH.read_bytes().decode("utf-8"))
    mapping = json.loads(MAPPING_PATH.read_bytes().decode("utf-8"))

    mechanisms = catalog["mechanisms"]
    relations = mapping["relations"]

    family_counts = Counter(mechanism_family(m["id"]) for m in mechanisms)
    mapped_mechanism_ids = {r["mechanism_id"] for r in relations}
    unmapped_mechanism_ids = sorted({m["id"] for m in mechanisms} - mapped_mechanism_ids)

    techniques_per_mechanism = Counter(r["mechanism_id"] for r in relations)
    mechanisms_per_technique = Counter(r["attack_id"] for r in relations)

    mechanisms_per_technique_values = list(mechanisms_per_technique.values())
    techniques_per_mechanism_values = list(techniques_per_mechanism.values())

    direct_count = sum(1 for r in relations if r["mapping_type"] == "direct")
    derived_count = sum(1 for r in relations if r["mapping_type"] == "derived")

    result = {
        "catalog_version": catalog["catalog_version"],
        "mapping_version": mapping["mapping_version"],
        "mechanism_count": len(mechanisms),
        "mechanism_count_by_family": dict(family_counts),
        "mechanisms_with_attack_mapping": len(mapped_mechanism_ids),
        "mechanisms_without_attack_mapping": len(unmapped_mechanism_ids),
        "mechanisms_without_attack_mapping_ids": unmapped_mechanism_ids,
        "attack_deception_relation_count": len(relations),
        "relation_count_direct": direct_count,
        "relation_count_derived": derived_count,
        "distinct_attack_techniques_covered": len(mechanisms_per_technique),
        "mechanisms_per_technique": {
            "min": min(mechanisms_per_technique_values),
            "max": max(mechanisms_per_technique_values),
            "mean": sum(mechanisms_per_technique_values) / len(mechanisms_per_technique_values),
            "median": statistics.median(mechanisms_per_technique_values),
        },
        "techniques_per_mechanism": {
            "min": min(techniques_per_mechanism_values),
            "max": max(techniques_per_mechanism_values),
            "mean": sum(techniques_per_mechanism_values) / len(techniques_per_mechanism_values),
            "median": statistics.median(techniques_per_mechanism_values),
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "catalog_statistics.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "Catalogue de deception - statistiques de couverture reelles",
        "-" * 78,
        f"Catalogue : {result['catalog_version']}  ({result['mechanism_count']} mecanismes)",
        f"Mapping   : {result['mapping_version']}  ({result['attack_deception_relation_count']} relations M_i,d)",
        "-" * 78,
        "Mecanismes par famille :",
    ]
    for family, count in sorted(family_counts.items()):
        lines.append(f"  {family:<12} {count}")
    lines += [
        "-" * 78,
        f"Mecanismes avec >=1 mapping ATT&CK : {result['mechanisms_with_attack_mapping']} / {result['mechanism_count']}",
        f"Mecanismes sans mapping ATT&CK      : {result['mechanisms_without_attack_mapping']} ({', '.join(unmapped_mechanism_ids)})",
        "-" * 78,
        f"Relations M_i,d directes (MITRE Engage) : {direct_count}",
        f"Relations M_i,d derivees (D3FEND SPARQL) : {derived_count}",
        f"Techniques ATT&CK distinctes couvertes   : {result['distinct_attack_techniques_covered']}",
        "-" * 78,
        "Mecanismes par technique ATT&CK (parmi les techniques couvertes) :",
        f"  min={result['mechanisms_per_technique']['min']}  max={result['mechanisms_per_technique']['max']}  "
        f"mean={result['mechanisms_per_technique']['mean']:.2f}  median={result['mechanisms_per_technique']['median']}",
        "Techniques ATT&CK par mecanisme (parmi les mecanismes mappes) :",
        f"  min={result['techniques_per_mechanism']['min']}  max={result['techniques_per_mechanism']['max']}  "
        f"mean={result['techniques_per_mechanism']['mean']:.2f}  median={result['techniques_per_mechanism']['median']}",
        "-" * 78,
    ]
    text = "\n".join(lines) + "\n"
    (OUT_DIR / "catalog_statistics.txt").write_text(text, encoding="utf-8")

    print(text)
    print(f"JSON : {OUT_DIR / 'catalog_statistics.json'}")


if __name__ == "__main__":
    main()
