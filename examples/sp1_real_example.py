"""
Réf. architecture : CLAUDE.md §10 (SP1) — exemple exécutable réel
utilisant le catalogue et le mapping RÉELS (pas une fixture synthétique).

Charge :
    data/deception/deception_catalog.json          (tools/deception_kb/catalog_builder.py)
    data/deception/attack_deception_mapping.json    (tools/deception_kb/mapping_builder.py)

et exécute src/admissibility.py sur une petite instance explicite dont
les technique_id (T1110.001, T1039) et les mécanismes (D3-DUC, D3-DNR)
proviennent réellement de ce mapping — pas choisis arbitrairement.

**Résultat réel (après l'audit documentaire des prérequis, réf.
`docs/chapter4/ADMISSIBILITY_EVIDENCE_AUDIT.md`)** : `D3-DNR` est le seul
mécanisme dont `admissibility_profile.required_asset_types` est
renseigné par une preuve documentaire directe (D3FEND kb-article :
« deployed to web application servers, network file shares... ») —
`RequirementsSatisfied` peut donc réellement évaluer `"pass"`/`"fail"`
pour lui, selon l'`asset_type` de l'emplacement candidat. Pour `D3-DF` et
`D3-DUC`, aucune preuve suffisante n'a été trouvée : `RequirementsSatisfied`
reste `"undetermined"` (politique prudente OPEN_DECISION 4, jamais
`"pass"` par défaut). Ce script rend ce contraste visible via le
diagnostic complet de SP1 (`rejection_reason`) — pas un résultat
uniforme masquant la nuance.

Exécution :
    python -m examples.sp1_real_example

Sorties :
    docs/chapter4/outputs/sp1_real_example.json  (rapport complet, structuré)
    docs/chapter4/outputs/sp1_real_example.txt   (résumé lisible)
"""

from __future__ import annotations

import json
from pathlib import Path

from src.admissibility import build_admissibility_report
from src.knowledge_deception import load_attack_deception_mapping, load_deception_catalog, to_sp1_mapping
from src.schemas import (
    Asset,
    AttackGraph,
    Location,
    NodeAttributes,
    SIInventory,
    SITopologyEdge,
    SystemInstance,
    TechniqueOccurrence,
)

CATALOG_PATH = Path("data/deception/deception_catalog.json")
MAPPING_PATH = Path("data/deception/attack_deception_mapping.json")
OUT_DIR = Path("docs/chapter4/outputs")


def build_example_instance() -> SystemInstance:
    """T1110.001 (Password Guessing, credential-access) sur un contrôleur
    de domaine DC01, et T1039 (Data from Network Shared Drive,
    collection) sur un serveur de fichiers FS01 — deux occurrences dont
    les technique_id apparaissent réellement dans le mapping M_{i,d}
    matérialisé (D3-DUC pour T1110.001, D3-DNR pour T1039)."""
    t1110 = TechniqueOccurrence(
        technique_id="T1110.001",
        asset_id="DC01",
        attributes=NodeAttributes(
            tactics=["credential-access"],
            outcomes=[],
            q_local_success=0.6,
            impact_confidentiality=0.5,
            impact_integrity=0.1,
            impact_availability=0.1,
            critical_asset=False,
            accessible_asset=True,
        ),
    )
    t1039 = TechniqueOccurrence(
        technique_id="T1039",
        asset_id="FS01",
        attributes=NodeAttributes(
            tactics=["collection"],
            outcomes=[],
            q_local_success=0.5,
            impact_confidentiality=0.4,
            impact_integrity=0.1,
            impact_availability=0.1,
            critical_asset=False,
            accessible_asset=True,
        ),
    )
    graph = AttackGraph(nodes=[t1110, t1039], edges=[])

    assets = [
        Asset(asset_id="DC01", asset_type="domain_controller", critical=False, accessible=True, properties={}),
        Asset(asset_id="FS01", asset_type="file_server", critical=False, accessible=True, properties={}),
    ]
    locations = [
        Location(location_id="auth-store", location_type="credential_store", asset_id="DC01"),
        Location(location_id="shared-drive", location_type="network_resource", asset_id="FS01"),
    ]
    inventory = SIInventory(assets=assets, locations=locations, topology_edges=[])
    return SystemInstance(graph=graph, si_inventory=inventory)


def render_text_summary(report: dict) -> str:
    lines = [
        "SP1 - Resultats d'admissibilite (catalogue et mapping REELS)",
        "-" * 78,
        f"{'Occurrence':<16}{'Mecanisme':<10}{'Emplacement':<14}{'Decision'}",
    ]
    for occurrence_id, occ in report["occurrences"].items():
        if occ["is_terminal"]:
            continue
        lines.append(f"D_i({occurrence_id}) = {occ['D_i']}")
        for candidate in occ["candidates"]:
            decision = "ADMISSIBLE" if candidate["admissible"] else f"REJETE ({candidate['rejection_reason']})"
            lines.append(
                f"{occurrence_id:<16}{candidate['mechanism_id']:<10}{candidate['location_id']:<14}{decision}"
            )
    lines.append("-" * 78)
    summary = report["summary"]
    lines.append(f"Candidats bruts : {summary['candidate_count']}")
    lines.append(f"Admissibles     : {summary['admissible_count']}")
    lines.append(f"Rejetes         : {summary['rejected_count']}")
    lines.append("-" * 78)
    lines.append(
        "Note : D3-DNR est le seul mecanisme dont required_asset_types est "
        "renseigne par une preuve documentaire directe (D3FEND kb-article) -- "
        "RequirementsSatisfied peut donc reellement passer pour lui. Pour D3-DF "
        "et D3-DUC, aucune preuve suffisante trouvee : RequirementsSatisfied "
        "reste 'undetermined' (politique prudente OPEN_DECISION 4). "
        "Voir docs/chapter4/ADMISSIBILITY_EVIDENCE_AUDIT.md."
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    kb = load_deception_catalog(CATALOG_PATH)
    attack_mapping = load_attack_deception_mapping(MAPPING_PATH)
    sp1_mapping = to_sp1_mapping(attack_mapping, kb)

    instance = build_example_instance()
    catalog = dict(kb.mechanisms_by_id)

    report = build_admissibility_report(instance, catalog, sp1_mapping, theta_c=0.85, theta_i=0.85, theta_a=0.85)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "sp1_real_example.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    text = render_text_summary(report)
    (OUT_DIR / "sp1_real_example.txt").write_text(text, encoding="utf-8")

    print(text)
    print(f"JSON complet : {OUT_DIR / 'sp1_real_example.json'}")
    print(f"Resume texte : {OUT_DIR / 'sp1_real_example.txt'}")


if __name__ == "__main__":
    main()
