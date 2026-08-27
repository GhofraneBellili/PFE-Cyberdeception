"""
Réf. architecture : CLAUDE.md §10 (SP1) — réf. tâche « enrichir l'instance
technique SP1 » puis réf. tâche « separate knowledge and organization
capabilities » : instance runtime représentative de SP1, utilisant le
catalogue de CONNAISSANCES réel étendu (51 mécanismes,
`tools/deception_kb/catalog_builder.py`), le catalogue OPÉRATIONNEL d'une
organisation d'exemple (42 mécanismes référencés, 30 activés —
`examples/data/organization_deception_catalog.json`,
`examples/build_organization_catalog_example.py`) et le mapping M_{i,d}
réel (591 relations, `tools/deception_kb/mapping_builder.py`).

**Scénario** : deux points d'entrée (T1566 hameçonnage sur un poste de
travail WS01, T1190 exploitation d'une application web publique sur
WEB01) convergent vers une compromission d'identifiants sur un contrôleur
de domaine DC01 (T1110 force brute, T1003 dumping de credentials, T1078
comptes valides), puis exécution (T1059 sur un serveur d'application
APP01) qui diverge vers une phase de découverte/collecte sur un serveur
de fichiers FS01 (T1083, T1039) et une base de données DB01 (T1005),
avant de converger vers une exfiltration terminale (T1041 sur APP01,
impact élevé). Chaque actif a un rôle cohérent avec ce scénario — aucun
type d'actif n'a été ajouté seulement pour rendre un mécanisme
admissible (réf. tâche §11/§13, mise en garde explicite).

**SP1 est un module RUNTIME** (réf. tâche §6) : ce script appelle
`build_admissibility_report` avec le graphe/SI courants, le catalogue de
connaissances, le catalogue opérationnel de l'organisation et le mapping
— rien n'est pré-calculé hors ligne. La réduction observée
(`|D_knowledge|=51` -> `|D_org|=42` référencés/30 activés -> `|D_i|` par
technique -> `|C_i_h|`) provient entièrement de cet appel runtime, jamais
d'une réduction préalable du catalogue.

Exécution :
    python -m examples.sp1_extended_real_example

Sorties :
    docs/chapter4/outputs/sp1_extended_real_example.json
    docs/chapter4/outputs/sp1_extended_real_example.txt
"""

from __future__ import annotations

import json
from pathlib import Path

from src.admissibility import build_admissibility_report, enabled_mechanism_ids
from src.knowledge_deception import load_attack_deception_mapping, load_deception_catalog, to_sp1_mapping
from src.organization_catalog import capabilities_by_id, load_organization_catalog, validate_against_knowledge_catalog
from src.schemas import (
    Asset,
    AttackGraph,
    AttackGraphEdge,
    Location,
    NodeAttributes,
    SIInventory,
    SITopologyEdge,
    SystemInstance,
    TechniqueOccurrence,
)

CATALOG_PATH = Path("data/deception/deception_catalog.json")
MAPPING_PATH = Path("data/deception/attack_deception_mapping.json")
ORGANIZATION_CATALOG_PATH = Path("examples/data/organization_deception_catalog.json")
OUT_DIR = Path("docs/chapter4/outputs")

THETA = 0.85


def _occurrence(technique_id: str, asset_id: str, *, tactics: list[str], q: float, ic: float, ii: float, ia: float) -> TechniqueOccurrence:
    return TechniqueOccurrence(
        technique_id=technique_id,
        asset_id=asset_id,
        attributes=NodeAttributes(
            tactics=tactics,
            outcomes=[],
            q_local_success=q,
            impact_confidentiality=ic,
            impact_integrity=ii,
            impact_availability=ia,
            critical_asset=False,
            accessible_asset=asset_id in ("WS01", "WEB01"),
        ),
    )


def build_example_instance() -> SystemInstance:
    nodes = [
        _occurrence("T1566", "WS01", tactics=["initial-access"], q=0.5, ic=0.2, ii=0.1, ia=0.1),
        _occurrence("T1190", "WEB01", tactics=["initial-access"], q=0.4, ic=0.2, ii=0.1, ia=0.1),
        _occurrence("T1110", "DC01", tactics=["credential-access"], q=0.5, ic=0.3, ii=0.1, ia=0.1),
        _occurrence("T1003", "DC01", tactics=["credential-access"], q=0.6, ic=0.4, ii=0.1, ia=0.1),
        _occurrence(
            "T1078", "DC01", tactics=["defense-evasion", "persistence", "privilege-escalation", "initial-access"],
            q=0.7, ic=0.4, ii=0.2, ia=0.1,
        ),
        _occurrence("T1059", "APP01", tactics=["execution"], q=0.6, ic=0.3, ii=0.3, ia=0.1),
        _occurrence("T1083", "FS01", tactics=["discovery"], q=0.6, ic=0.2, ii=0.1, ia=0.1),
        _occurrence("T1005", "DB01", tactics=["collection"], q=0.5, ic=0.5, ii=0.1, ia=0.1),
        _occurrence("T1039", "FS01", tactics=["collection"], q=0.5, ic=0.5, ii=0.1, ia=0.1),
        # Terminal : impact confidentialite >= theta_c (0.9 >= 0.85) -> exfiltration.
        _occurrence("T1041", "APP01", tactics=["exfiltration"], q=0.6, ic=0.9, ii=0.2, ia=0.1),
    ]

    edges = [
        AttackGraphEdge(source_id="T1566@WS01", target_id="T1110@DC01"),
        AttackGraphEdge(source_id="T1190@WEB01", target_id="T1003@DC01"),
        AttackGraphEdge(source_id="T1110@DC01", target_id="T1078@DC01"),
        AttackGraphEdge(source_id="T1003@DC01", target_id="T1078@DC01"),
        AttackGraphEdge(source_id="T1078@DC01", target_id="T1059@APP01"),
        # Divergence (T1059 a deux enfants) : pas de branch_probability
        # explicite -> le moteur de risque appliquera 1/|Children| (§14.4).
        AttackGraphEdge(source_id="T1059@APP01", target_id="T1083@FS01"),
        AttackGraphEdge(source_id="T1059@APP01", target_id="T1005@DB01"),
        AttackGraphEdge(source_id="T1083@FS01", target_id="T1039@FS01"),
        # Convergence terminale (T1041 a deux parents).
        AttackGraphEdge(source_id="T1039@FS01", target_id="T1041@APP01"),
        AttackGraphEdge(source_id="T1005@DB01", target_id="T1041@APP01"),
    ]
    graph = AttackGraph(nodes=nodes, edges=edges)

    assets = [
        Asset(asset_id="WS01", asset_type="workstation", critical=False, accessible=True, properties={"services": ["email"]}),
        Asset(asset_id="WEB01", asset_type="web_application_server", critical=False, accessible=True, properties={}),
        Asset(asset_id="DC01", asset_type="domain_controller", critical=False, accessible=False, properties={}),
        Asset(asset_id="APP01", asset_type="application_server", critical=False, accessible=False, properties={}),
        Asset(asset_id="FS01", asset_type="file_server", critical=False, accessible=False, properties={}),
        Asset(asset_id="DB01", asset_type="database_server", critical=False, accessible=False, properties={}),
    ]

    locations = [
        Location(location_id="cred-store-dc01", location_type="credential_store", asset_id="DC01"),
        Location(location_id="mailbox-ws01", location_type="mailbox", asset_id="WS01"),
        Location(location_id="host-ws01", location_type="host", asset_id="WS01"),
        Location(location_id="host-dc01", location_type="host", asset_id="DC01"),
        Location(location_id="host-app01", location_type="host", asset_id="APP01"),
        Location(location_id="host-fs01", location_type="host", asset_id="FS01"),
        Location(location_id="host-db01", location_type="host", asset_id="DB01"),
        Location(location_id="account-dc01", location_type="account", asset_id="DC01"),
        Location(location_id="filesystem-fs01", location_type="filesystem", asset_id="FS01"),
        Location(location_id="network-resource-fs01", location_type="network_resource", asset_id="FS01"),
        Location(location_id="network-resource-web01", location_type="network_resource", asset_id="WEB01"),
        Location(location_id="network-share-fs01", location_type="network_share", asset_id="FS01"),
        Location(location_id="network-segment-core", location_type="network_segment", asset_id="DC01"),
    ]

    topology_edges = [
        SITopologyEdge(source_asset_id="WS01", target_asset_id="DC01", relation_type="network_adjacency", bidirectional=True),
        SITopologyEdge(source_asset_id="WEB01", target_asset_id="DC01", relation_type="network_adjacency", bidirectional=True),
        SITopologyEdge(source_asset_id="DC01", target_asset_id="APP01", relation_type="network_adjacency", bidirectional=True),
        SITopologyEdge(source_asset_id="APP01", target_asset_id="FS01", relation_type="network_adjacency", bidirectional=True),
        SITopologyEdge(source_asset_id="APP01", target_asset_id="DB01", relation_type="network_adjacency", bidirectional=True),
    ]

    inventory = SIInventory(assets=assets, locations=locations, topology_edges=topology_edges)
    return SystemInstance(graph=graph, si_inventory=inventory)


def render_text_summary(report: dict, *, d_knowledge_size: int, d_org_referenced: int, d_org_enabled: int) -> str:
    lines = [
        "SP1 runtime - instance riche (catalogue de connaissances + catalogue organisationnel + mapping REELS)",
        "-" * 96,
        f"|D_knowledge| = {d_knowledge_size}   |D_org| (reference) = {d_org_referenced}   |D_org| (enabled) = {d_org_enabled}",
        "-" * 96,
        f"{'Occurrence':<16}{'Mecanisme':<12}{'Emplacement':<24}{'Decision'}",
    ]
    admissible_mechanisms: set[str] = set()
    admissible_occurrences: set[str] = set()
    for occurrence_id, occ in report["occurrences"].items():
        if occ["is_terminal"]:
            lines.append(f"{occurrence_id} : TERMINAL (C_i_h = vide par construction, §6)")
            continue
        lines.append(f"D_i({occurrence_id}) = {occ['D_i']}  (|D_i|={len(occ['D_i'])})")
        for candidate in occ["candidates"]:
            if not candidate["admissible"]:
                continue
            admissible_mechanisms.add(candidate["mechanism_id"])
            admissible_occurrences.add(occurrence_id)
            lines.append(f"{occurrence_id:<16}{candidate['mechanism_id']:<12}{candidate['location_id']:<24}ADMISSIBLE")
    lines.append("-" * 96)
    summary = report["summary"]
    lines.append(f"|D_org| (enabled, rapporte par SP1) : {summary['d_org_size']}")
    lines.append(f"Occurrences (non terminales) : {summary['occurrence_count'] - summary['terminal_occurrence_count']}")
    lines.append(f"Occurrences terminales        : {summary['terminal_occurrence_count']}")
    lines.append(f"Candidats bruts (mecanisme x emplacement evalues) : {summary['candidate_count']}")
    lines.append(f"Admissibles                    : {summary['admissible_count']}")
    lines.append(f"Rejetes                        : {summary['rejected_count']}")
    lines.append(f"Occurrences couvertes par >=1 admissible : {len(admissible_occurrences)} ({sorted(admissible_occurrences)})")
    lines.append(f"Mecanismes admissibles distincts          : {len(admissible_mechanisms)} ({sorted(admissible_mechanisms)})")
    lines.append("-" * 96)
    lines.append(
        "Chaine de reduction observee (ref. tache SS6/SS16) : "
        f"|D_knowledge|={d_knowledge_size} -> |D_org| reference={d_org_referenced} -> |D_org| active={d_org_enabled} "
        f"-> somme des |D_i| par occurrence -> {summary['admissible_count']} candidats reellement admissibles. "
        "Cette reduction est realisee entierement par SP1 au runtime (mapping, Autorise, PrerequisSatisfaits, "
        "Pertinent), jamais par une reduction prealable du catalogue de connaissances."
    )
    lines.append(
        "Note (SS10) : PrerequisSatisfaits reste 'undetermined (missing organization configuration)' "
        "(jamais admissible) tant que l'organisation n'a pas renseigne allowed_asset_types/required_services/"
        "required_artifacts pour un mecanisme active -- ce n'est plus une limite documentaire D3FEND (le "
        "catalogue de connaissances n'est plus consulte pour cette decision), mais une configuration "
        "organisationnelle non encore fournie -- voir examples/build_organization_catalog_example.py."
    )
    return "\n".join(lines) + "\n"


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

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "sp1_extended_real_example.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    text = render_text_summary(
        report,
        d_knowledge_size=len(catalog),
        d_org_referenced=len(organization_catalog),
        d_org_enabled=len(enabled_mechanism_ids(organization_catalog)),
    )
    (OUT_DIR / "sp1_extended_real_example.txt").write_text(text, encoding="utf-8")

    print(text)
    print(f"JSON complet : {OUT_DIR / 'sp1_extended_real_example.json'}")
    print(f"Resume texte : {OUT_DIR / 'sp1_extended_real_example.txt'}")


if __name__ == "__main__":
    main()
