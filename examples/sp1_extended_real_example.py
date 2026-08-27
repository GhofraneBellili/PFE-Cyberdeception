"""
Réf. architecture : CLAUDE.md §10 (SP1) — réf. tâche « enrichir l'instance
technique SP1 » (Phase 11) : instance PIPELINE-ILLUSTRATION plus riche que
`examples/sp1_real_example.py` (12 candidats bruts, 1 seul admissible),
utilisant le catalogue et le mapping RÉELS ÉTENDUS (26 mécanismes, 591
relations M_{i,d} — `tools/deception_kb/catalog_builder.py`,
`tools/deception_kb/mapping_builder.py`).

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
admissible (réf. tâche §11, mise en garde explicite).

**Constat honnête (réf. tâche §11 : « si un seul candidat admissible,
analyser la cause, ne pas relâcher SP1 »)** : `src/admissibility.py`
retourne `PrerequisSatisfaits = "undetermined"` (jamais admissible) tant
que `required_asset_types`/`required_services`/`required_artifacts` du
mécanisme sont TOUS vides (politique prudente OPEN_DECISION 4). Après
relecture ciblée des sources documentaires (réf.
`docs/chapter4/CATALOG_AUDIT.md`, section 6bis), exactement **3
mécanismes** sur 26 disposent d'un prérequis documenté :
D3-DNR (déjà audité), EAC0009 et EAC0021 (infrastructure de messagerie).
Ce n'est donc pas un manque de richesse d'instance qui limitait SP1 à 1
seul candidat admissible, mais un manque de preuve documentaire de
prérequis — cette instance le rend visible en couvrant délibérément les
occurrences où ces 3 mécanismes interviennent réellement dans D_i.

Exécution :
    python -m examples.sp1_extended_real_example

Sorties :
    docs/chapter4/outputs/sp1_extended_real_example.json
    docs/chapter4/outputs/sp1_extended_real_example.txt
"""

from __future__ import annotations

import json
from pathlib import Path

from src.admissibility import build_admissibility_report
from src.knowledge_deception import load_attack_deception_mapping, load_deception_catalog, to_sp1_mapping
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


def render_text_summary(report: dict) -> str:
    lines = [
        "SP1 etendu - instance riche (catalogue et mapping REELS, 26 mecanismes)",
        "-" * 88,
        f"{'Occurrence':<16}{'Mecanisme':<12}{'Emplacement':<24}{'Decision'}",
    ]
    admissible_mechanisms: set[str] = set()
    admissible_occurrences: set[str] = set()
    for occurrence_id, occ in report["occurrences"].items():
        if occ["is_terminal"]:
            lines.append(f"{occurrence_id} : TERMINAL (C_i_h = vide par construction, §6)")
            continue
        lines.append(f"D_i({occurrence_id}) = {occ['D_i']}")
        for candidate in occ["candidates"]:
            if not candidate["admissible"]:
                continue
            admissible_mechanisms.add(candidate["mechanism_id"])
            admissible_occurrences.add(occurrence_id)
            lines.append(f"{occurrence_id:<16}{candidate['mechanism_id']:<12}{candidate['location_id']:<24}ADMISSIBLE")
    lines.append("-" * 88)
    summary = report["summary"]
    lines.append(f"Occurrences (non terminales) : {summary['occurrence_count'] - summary['terminal_occurrence_count']}")
    lines.append(f"Occurrences terminales        : {summary['terminal_occurrence_count']}")
    lines.append(f"Candidats bruts                : {summary['candidate_count']}")
    lines.append(f"Admissibles                    : {summary['admissible_count']}")
    lines.append(f"Rejetes                        : {summary['rejected_count']}")
    lines.append(f"Occurrences couvertes par >=1 admissible : {len(admissible_occurrences)} ({sorted(admissible_occurrences)})")
    lines.append(f"Mecanismes admissibles distincts          : {len(admissible_mechanisms)} ({sorted(admissible_mechanisms)})")
    lines.append("-" * 88)
    lines.append(
        "Analyse (§11) : PrerequisSatisfaits reste 'undetermined' (jamais admissible) tant que "
        "required_asset_types/required_services/required_artifacts du mecanisme sont TOUS vides "
        "(politique prudente OPEN_DECISION 4). Seuls D3-DNR, EAC0009 et EAC0021 disposent d'un "
        "prerequis documente (docs/chapter4/CATALOG_AUDIT.md, section 6bis) : ce n'est donc pas un "
        "manque de richesse d'instance qui limitait SP1 a 1 seul candidat admissible auparavant, "
        "mais un manque de preuve documentaire de prerequis pour les 23 autres mecanismes -- limite "
        "documentee, pas comblee artificiellement."
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    kb = load_deception_catalog(CATALOG_PATH)
    attack_mapping = load_attack_deception_mapping(MAPPING_PATH)
    sp1_mapping = to_sp1_mapping(attack_mapping, kb)

    instance = build_example_instance()
    catalog = dict(kb.mechanisms_by_id)

    report = build_admissibility_report(instance, catalog, sp1_mapping, theta_c=THETA, theta_i=THETA, theta_a=THETA)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "sp1_extended_real_example.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    text = render_text_summary(report)
    (OUT_DIR / "sp1_extended_real_example.txt").write_text(text, encoding="utf-8")

    print(text)
    print(f"JSON complet : {OUT_DIR / 'sp1_extended_real_example.json'}")
    print(f"Resume texte : {OUT_DIR / 'sp1_extended_real_example.txt'}")


if __name__ == "__main__":
    main()
