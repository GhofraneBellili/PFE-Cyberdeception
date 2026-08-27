"""
Réf. architecture : CLAUDE.md §19 (Workflow complet d'exécution) —
exemple exécutable réel du pipeline complet.

Enchaîne, sur une instance réelle et un index RAG réel (documents
D3FEND/Engage/littérature déjà versionnés) : SP1 -> RAG -> annotation
(repli déterministe `rule_based_stub`) -> validation/agrégation/gel ->
coût -> résolution de `(P)` -> reporting avant/après (src/orchestrator.py).

**`DE` provient du repli déterministe `rule_based_stub`** (aucune API
LLM réelle disponible dans cet environnement) — pas un résultat
expérimental du chapitre 5 ; ce script démontre uniquement que le
pipeline complet s'exécute de bout en bout sur des sorties réelles de
chaque module.

Exécution :
    python -m examples.orchestrator_example

Sorties :
    runs/chapter4-example/*.json               (régénérable, non versionné)
    docs/chapter4/outputs/pipeline_example.txt  (preuve d'exécution retenue)
"""

from __future__ import annotations

import json
from pathlib import Path

from src.annotator_llm import RuleBasedStubAnnotator
from src.orchestrator import run_pipeline
from src.rag_indexer import build_index, load_d3fend_chunks, load_engage_chunks, load_literature_chunks
from src.reporter import render_text_report
from src.schemas import (
    Asset,
    AttackGraph,
    AttackGraphEdge,
    DeceptionAdmissibilityProfile,
    DeceptionMechanism,
    Location,
    NodeAttributes,
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
    graph = AttackGraph(nodes=[t1078, t1003], edges=[AttackGraphEdge(source_id="T1078@DC01", target_id="T1003@DC01")])
    assets = [
        Asset(
            asset_id="DC01",
            asset_type="domain_controller",
            critical=False,
            accessible=True,
            properties={"services": ["ldap"], "artifacts": []},
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
    duc = DeceptionMechanism(
        id="D3-DUC",
        name="Decoy User Credential",
        description="A Credential created for the purpose of deceiving an adversary.",
        interaction_mechanism="use credential",
        version="1.5.0",
        admissibility_profile=DeceptionAdmissibilityProfile(
            allowed_location_types=["credential_store"],
            required_asset_types=["domain_controller"],
            required_services=["ldap"],
        ),
    )
    return {"D3-DUC": duc}


def build_rag_index():
    chunks = (
        load_d3fend_chunks(load_json("d3fend_deception_seed_1.5.0.json"))
        + load_engage_chunks(load_json("engage_activity_seed_1.0.json"))
        + load_literature_chunks(load_json("literature_evidence_seed_1.2.json"))
    )
    return build_index(chunks)


def main() -> None:
    result = run_pipeline(
        run_id="chapter4-example",
        instance=build_instance(),
        catalog=build_catalog(),
        mapping={"T1078": ["D3-DUC"]},
        rag_index=build_rag_index(),
        annotator=RuleBasedStubAnnotator(),
        cost_inputs_by_mechanism={
            "D3-DUC": {
                "deployment": {"t_setup": 4.0, "w_eng": 50.0, "l_data": 1.0, "w_data": 20.0, "c_integration": 50.0},
                "resource": {"r_cpu": 0.5, "c_cpu": 0.02, "r_ram": 1.0, "c_ram": 0.01, "r_disk": 5.0, "c_disk": 0.001, "r_network": 0.1, "c_network": 0.05},
                "maintenance": {"t_monitoring": 0.1, "w_eng": 50.0, "s_logs": 0.5, "w_storage": 0.01, "c_updates": 0.2},
            }
        },
        horizon=720.0,
        budget_total=5000.0,
        theta_c=THETA,
        theta_i=THETA,
        theta_a=THETA,
        q_by_occurrence={"T1078@DC01": 0.75, "T1003@DC01": 0.65},
        impact_by_occurrence={"T1078@DC01": 0.43, "T1003@DC01": 0.61},
        annotation_set_version="chapter4-example-v1",
    )

    manifest = result["run_manifest"]
    risks = result["risks"]
    lines = [
        "Pipeline complet - resultat reel (src/orchestrator.py)",
        "-" * 70,
        f"run_id : {manifest['run_id']}",
        f"Fichiers ecrits (runs/{manifest['run_id']}/) : {', '.join(manifest['files'])}",
        f"Candidats evalues / admissibles : {manifest['candidates_evaluated']} / {manifest['candidates_admissible']}",
        f"Configurations enumerees / faisables : {manifest['configurations_enumerated']} / {manifest['configurations_feasible']}",
        f"Taille du front de Pareto : {manifest['pareto_front_size']}",
        "",
        "Rapport de deploiement Y* (src/reporter.py, illustratif, DE issu du repli rule_based_stub) :",
        render_text_report(result["deployment_report"]).rstrip("\n"),
        "",
        "Risque terminal (T1003@DC01) :",
        f"  avec deception : {risks['avec_deception']['T1003@DC01']:.4f}",
        f"  sans deception : {risks['sans_deception']['T1003@DC01']:.4f}",
        "-" * 70,
        "Note : DE issu du repli deterministe rule_based_stub (aucune API LLM",
        "reelle disponible) -- preuve d'execution bout-en-bout, pas un resultat",
        "experimental du chapitre 5.",
    ]
    text = "\n".join(lines) + "\n"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "pipeline_example.txt").write_text(text, encoding="utf-8")
    print(text)
    print(f"Details complets : runs/{manifest['run_id']}/")
    print(f"Resume texte : {OUT_DIR / 'pipeline_example.txt'}")


if __name__ == "__main__":
    main()
