"""
Réf. architecture : CLAUDE.md §10 (SP1) — exemple exécutable minimal.

Produit une sortie RÉELLE (pas une fixture de test présentée comme un
résultat) de src/admissibility.py sur une petite instance synthétique
mais explicite, pour le chapitre 4 du mémoire (Capture 3).

Exécution :
    python -m examples.sp1_example

Sorties :
    docs/chapter4/outputs/sp1_candidates.json  (rapport complet, structuré)
    docs/chapter4/outputs/sp1_example.txt      (résumé lisible, notation verrouillée)
"""

from __future__ import annotations

import json
from pathlib import Path

from src.admissibility import build_admissibility_report
from src.schemas import (
    Asset,
    AttackGraph,
    DeceptionMechanism,
    Location,
    NodeAttributes,
    OrganizationDeceptionCapability,
    SIInventory,
    SITopologyEdge,
    SystemInstance,
    TechniqueOccurrence,
)

OUT_DIR = Path("docs/chapter4/outputs")


def build_example_instance() -> SystemInstance:
    """Petite instance explicite : une occurrence T1078 sur un contrôleur
    de domaine DC01, un poste de travail WS01 relié topologiquement, et un
    emplacement flottant sans actif associé (pour illustrer le cas
    'undetermined')."""
    occurrence = TechniqueOccurrence(
        technique_id="T1078",
        asset_id="DC01",
        attributes=NodeAttributes(
            tactics=["defense-evasion", "persistence", "privilege-escalation", "initial-access"],
            outcomes=[],
            q_local_success=0.75,
            impact_confidentiality=0.6,
            impact_integrity=0.2,
            impact_availability=0.1,
            critical_asset=False,
            accessible_asset=True,
        ),
    )
    graph = AttackGraph(nodes=[occurrence], edges=[])

    assets = [
        Asset(
            asset_id="DC01",
            asset_type="domain_controller",
            critical=False,
            accessible=True,
            properties={"services": ["ldap", "kerberos"], "artifacts": []},
        ),
        Asset(asset_id="WS01", asset_type="workstation", critical=False, accessible=True, properties={}),
    ]
    locations = [
        Location(location_id="auth-store", location_type="credential_store", asset_id="DC01"),
        Location(location_id="/tmp", location_type="filesystem", asset_id="WS01"),
    ]
    topology_edges = [
        SITopologyEdge(source_asset_id="DC01", target_asset_id="WS01", relation_type="network_adjacency", bidirectional=True)
    ]
    inventory = SIInventory(assets=assets, locations=locations, topology_edges=topology_edges)
    return SystemInstance(graph=graph, si_inventory=inventory)


def build_example_catalog() -> dict[str, DeceptionMechanism]:
    """Catalogue de CONNAISSANCES minimal — décrit ce que sont les
    mécanismes, jamais leur admissibilité dans une organisation donnée
    (réf. tâche « separate knowledge and organization capabilities »)."""
    duc = DeceptionMechanism(
        id="D3-DUC",
        name="Decoy User Credential",
        description="A Credential created for the purpose of deceiving an adversary.",
        interaction_mechanism="use credential",
        version="1.5.0",
    )
    df = DeceptionMechanism(
        id="D3-DF",
        name="Decoy File",
        description="A file created for the purposes of deceiving an adversary.",
        interaction_mechanism="file access",
        version="1.5.0",
    )
    return {"D3-DUC": duc, "D3-DF": df}


def build_example_organization_catalog() -> dict[str, OrganizationDeceptionCapability]:
    """Catalogue OPÉRATIONNEL d'une organisation fictive de démonstration
    — seule source des décisions Autorise/PrerequisSatisfaits de SP1."""
    duc = OrganizationDeceptionCapability(
        mechanism_id="D3-DUC",
        enabled=True,
        allowed_location_types=["credential_store"],
        allowed_asset_types=["domain_controller"],
        required_services=["ldap"],
    )
    df = OrganizationDeceptionCapability(
        mechanism_id="D3-DF",
        enabled=True,
        allowed_location_types=["filesystem"],
    )
    return {"D3-DUC": duc, "D3-DF": df}


def render_text_summary(report: dict) -> str:
    lines = [
        "SP1 - Resultats d'admissibilite",
        "-" * 66,
        f"{'Occurrence':<12}{'Mecanisme':<10}{'Emplacement':<14}{'Decision'}",
    ]
    for occurrence_id, occ in report["occurrences"].items():
        if occ["is_terminal"]:
            continue
        for candidate in occ["candidates"]:
            decision = "ADMISSIBLE" if candidate["admissible"] else f"REJETE ({candidate['rejection_reason']})"
            lines.append(
                f"{occurrence_id:<12}{candidate['mechanism_id']:<10}{candidate['location_id']:<14}{decision}"
            )
    lines.append("-" * 66)
    summary = report["summary"]
    lines.append(f"Candidats bruts : {summary['candidate_count']}")
    lines.append(f"Admissibles     : {summary['admissible_count']}")
    lines.append(f"Rejetes         : {summary['rejected_count']}")
    return "\n".join(lines) + "\n"


def main() -> None:
    instance = build_example_instance()
    catalog = build_example_catalog()
    organization_catalog = build_example_organization_catalog()
    mapping = {"T1078": ["D3-DUC", "D3-DF"]}

    report = build_admissibility_report(
        instance, catalog, organization_catalog, mapping, theta_c=0.8, theta_i=0.8, theta_a=0.8
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "sp1_candidates.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "sp1_example.txt").write_text(render_text_summary(report), encoding="utf-8")

    print(render_text_summary(report))
    print(f"JSON complet : {OUT_DIR / 'sp1_candidates.json'}")
    print(f"Resume texte : {OUT_DIR / 'sp1_example.txt'}")


if __name__ == "__main__":
    main()
