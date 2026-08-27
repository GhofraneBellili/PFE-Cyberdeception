"""
Réf. architecture : CLAUDE.md §13 (Validation et gel des annotations) —
exemple exécutable réel.

Enchaîne SP1 (src/admissibility.py) -> RAG (src/rag_indexer.py /
src/rag_retriever.py) -> annotation des 11 sous-métriques
(src/annotator_llm.py, repli déterministe `rule_based_stub`) ->
validation + agrégation déterministe + gel (src/annotation_validator.py),
pour produire une table d'annotations figée réelle, directement
réutilisable par l'optimisation (`FrozenAnnotationTable.de_by_candidate()`)
sans jamais rappeler le LLM.

**`DE` provient ici du repli déterministe `rule_based_stub`** (aucune API
LLM réelle disponible dans cet environnement) — pas un résultat
expérimental du chapitre 5.

Exécution :
    python -m examples.freeze_example

Sortie :
    docs/chapter4/outputs/frozen_annotations_example.csv
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from src.admissibility import build_admissibility_report
from src.annotation_validator import freeze_table
from src.annotator_llm import ELEVEN_METRICS, RuleBasedStubAnnotator
from src.rag_indexer import build_index, load_d3fend_chunks, load_engage_chunks, load_literature_chunks
from src.rag_retriever import retrieve, to_deception_evidence
from src.schemas import (
    Asset,
    AttackGraph,
    AttackOccurrenceRef,
    DeceptionMechanism,
    DeceptionRef,
    GraphContext,
    Location,
    NodeAttributes,
    OrganizationDeceptionCapability,
    SIInventory,
    SITopologyEdge,
    SystemInstance,
    TechniqueOccurrence,
)

STAGING_DIR = Path("data/deception/staging")
OUT_DIR = Path("docs/chapter4/outputs")
THETA = 0.85


def load_json(name: str) -> dict:
    return json.loads((STAGING_DIR / name).read_text(encoding="utf-8"))


def build_instance() -> SystemInstance:
    """Même petite instance que examples/optimizer_example.py : T1078@DC01
    (non terminal, candidats SP1) -> T1003@DC01 (Terminal)."""
    t1078 = TechniqueOccurrence(
        technique_id="T1078",
        asset_id="DC01",
        attributes=NodeAttributes(
            tactics=["initial-access", "persistence"],
            outcomes=[],
            q_local_success=0.75,
            impact_confidentiality=0.6,
            impact_integrity=0.2,
            impact_availability=0.1,
            critical_asset=False,
            accessible_asset=True,
        ),
    )
    t1003 = TechniqueOccurrence(
        technique_id="T1003",
        asset_id="DC01",
        attributes=NodeAttributes(
            tactics=["credential-access"],
            outcomes=[],
            q_local_success=0.65,
            impact_confidentiality=0.9,
            impact_integrity=0.2,
            impact_availability=0.1,
            critical_asset=False,
            accessible_asset=True,
        ),
    )
    from src.schemas import AttackGraphEdge

    graph = AttackGraph(nodes=[t1078, t1003], edges=[AttackGraphEdge(source_id="T1078@DC01", target_id="T1003@DC01")])
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
    return SystemInstance(graph=graph, si_inventory=SIInventory(assets=assets, locations=locations, topology_edges=topology_edges))


def build_catalog() -> dict[str, DeceptionMechanism]:
    """Catalogue de CONNAISSANCES minimal (réf. tâche « separate knowledge
    and organization capabilities »)."""
    duc = DeceptionMechanism(
        id="D3-DUC",
        name="Decoy User Credential",
        description="A Credential created for the purpose of deceiving an adversary.",
        interaction_mechanism="use credential",
        version="1.5.0",
    )
    return {"D3-DUC": duc}


def build_organization_catalog() -> dict[str, OrganizationDeceptionCapability]:
    """Catalogue OPÉRATIONNEL d'une organisation d'exemple."""
    return {
        "D3-DUC": OrganizationDeceptionCapability(
            mechanism_id="D3-DUC",
            enabled=True,
            allowed_location_types=["credential_store"],
            allowed_asset_types=["domain_controller"],
            required_services=["ldap"],
        )
    }


def build_rag_index():
    chunks = (
        load_d3fend_chunks(load_json("d3fend_deception_seed_1.5.0.json"))
        + load_engage_chunks(load_json("engage_activity_seed_1.0.json"))
        + load_literature_chunks(load_json("literature_evidence_seed_1.2.json"))
    )
    return build_index(chunks)


def main() -> None:
    instance = build_instance()
    catalog = build_catalog()
    organization_catalog = build_organization_catalog()
    mapping = {"T1078": ["D3-DUC"]}

    admissibility_report = build_admissibility_report(
        instance, catalog, organization_catalog, mapping, theta_c=THETA, theta_i=THETA, theta_a=THETA
    )
    index = build_rag_index()
    annotator = RuleBasedStubAnnotator()

    occurrence_by_id = {occ.occurrence_id: occ for occ in instance.graph.nodes}
    candidates_for_freeze = []
    for occurrence_id, occ_report in admissibility_report["occurrences"].items():
        occurrence = occurrence_by_id[occurrence_id]
        for entry in occ_report["C_i_h"]:
            mechanism = catalog[entry["mechanism_id"]]
            query = f"{mechanism.name} {mechanism.description}"
            retrieval_results = retrieve(index, query, top_k=3)
            context = AttackOccurrenceRef(
                technique_id=occurrence.technique_id, asset_id=occurrence.asset_id, attributes=occurrence.attributes
            )
            from src.schemas import AnnotationContext

            annotation_context = AnnotationContext(
                attack_occurrence=context,
                deception=DeceptionRef(id=mechanism.id, name=mechanism.name),
                placement=entry["location_id"],
                graph_context=GraphContext(),
                system_context={},
                retrieved_evidence=[to_deception_evidence(r) for r in retrieval_results],
            )
            annotations = annotator.annotate(annotation_context)
            candidates_for_freeze.append((occurrence_id, entry["mechanism_id"], entry["location_id"], annotations))

    table = freeze_table(candidates_for_freeze, annotation_set_version="chapter4-example-v1")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = (
        ["annotation_id", "occurrence_id", "mechanism_id", "location_id", "model", "prompt_version"]
        + list(ELEVEN_METRICS)
        + ["Realisme", "P_interaction", "P_engagement", "Effet_prog", "DE", "confidence", "evidence_ids", "annotation_set_version"]
    )
    with (OUT_DIR / "frozen_annotations_example.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for entry in table.entries:
            row = {
                "annotation_id": entry.annotation_id,
                "occurrence_id": entry.occurrence_id,
                "mechanism_id": entry.mechanism_id,
                "location_id": entry.location_id,
                "model": entry.model,
                "prompt_version": entry.prompt_version,
                "Realisme": f"{entry.Realisme:.4f}",
                "P_interaction": f"{entry.P_interaction:.4f}",
                "P_engagement": f"{entry.P_engagement:.4f}",
                "Effet_prog": f"{entry.Effet_prog:.4f}",
                "DE": f"{entry.DE:.4f}",
                "confidence": f"{entry.confidence:.4f}",
                "evidence_ids": ";".join(entry.evidence_ids),
                "annotation_set_version": entry.annotation_set_version,
            }
            for metric in ELEVEN_METRICS:
                row[metric] = f"{entry.submetrics[metric]:.4f}"
            writer.writerow(row)

    print(f"Table figee : {len(table)} candidat(s) — annotation_set_version={table.annotation_set_version}")
    for entry in table.entries:
        print(
            f"  {entry.occurrence_id} / {entry.mechanism_id} / {entry.location_id} : "
            f"Realisme={entry.Realisme:.3f} P_interaction={entry.P_interaction:.3f} "
            f"P_engagement={entry.P_engagement:.3f} Effet_prog={entry.Effet_prog:.3f} DE={entry.DE:.3f}"
        )
    print(f"de_by_candidate() -> {table.de_by_candidate()}")
    print(f"Sortie : {OUT_DIR / 'frozen_annotations_example.csv'}")


if __name__ == "__main__":
    main()
