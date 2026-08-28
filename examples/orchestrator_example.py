"""
Réf. architecture : CLAUDE.md §19 (Workflow complet d'exécution) — réf.
tâche « maturation technique finale du chapitre 4 » §24/§25/§26 : exemple
exécutable réel du pipeline complet, sur des DONNÉES RÉELLES du projet
(catalogue de connaissances, mapping M_{i,d}, catalogue opérationnel
d'organisation, index RAG persisté) et une INSTANCE PETITE (pour que
l'énumération exhaustive de l'optimiseur reste exécutable — réf. §26,
jamais de Top-K arbitraire pour contourner l'explosion combinatoire).

Enchaîne, réellement :

    SP1 (catalogue + mapping + organisation réels)
    -> RAG CONTEXTUEL (index RAG persisté rechargé, cross-encoder réel)
    -> annotation (repli déterministe rule_based_stub -- TECHNICAL
       INTEGRATION FALLBACK, jamais présenté comme une annotation LLM
       réelle, réf. §24 de la tâche)
    -> validation/agrégation/gel -> coût -> résolution de (P) ->
       reporting avant/après (src/orchestrator.py).

**`DE` provient du repli déterministe `rule_based_stub`** (aucune API
LLM réelle disponible dans cet environnement) — pas un résultat
expérimental du chapitre 5 ; ce script démontre uniquement que le
pipeline complet, désormais intégré autour du RAG contextuel, s'exécute
de bout en bout sur des données et un index RAG réels.

Prérequis : un index RAG persisté (`python -m tools.rag.build_index`,
réf. §10 de la tâche) -- ce script échoue explicitement s'il est absent,
il ne le reconstruit jamais silencieusement (réf. §23 de la tâche).

Exécution :
    python -m examples.orchestrator_example

Sorties :
    runs/chapter4-example/*.json               (régénérable, non versionné)
    docs/chapter4/outputs/pipeline_example.txt  (preuve d'exécution retenue)
"""

from __future__ import annotations

from pathlib import Path

from src.annotator_llm import RULE_BASED_STUB_MODEL_VERSION, RuleBasedStubAnnotator
from src.knowledge_attack import load_attack_knowledge
from src.knowledge_deception import load_attack_deception_mapping, load_deception_catalog, to_sp1_mapping
from src.orchestrator import OrchestratorError, run_pipeline
from src.organization_catalog import capabilities_by_id, load_organization_catalog, validate_against_knowledge_catalog
from src.rag_index_store import RagIndexStoreError, load_rag_index
from src.reporter import render_text_report
from src.reranker import CrossEncoderReranker
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
RAG_INDEX_DIR = Path("data/rag/index")
ATTACK_RAW_PATH = Path("data/attack/raw/enterprise-attack.json")
OUT_DIR = Path("docs/chapter4/outputs")
THETA = 0.85


def build_small_real_instance() -> SystemInstance:
    """Réf. tâche §25/§26 : instance PETITE (3 occurrences, 2 actifs, 2
    emplacements) mais dont l'admissibilité utilise les données RÉELLES
    du projet (catalogue 51 mécanismes, mapping 591 relations, catalogue
    organisationnel réel 42 référencés/30 activés) -- vérifié
    empiriquement (§26) : 3 candidats admissibles sur 2 occurrences non
    terminales, au plus 6 configurations pour l'énumération exhaustive
    (jamais un catalogue synthétique artificiel réduit à 1 mécanisme)."""
    t1566 = TechniqueOccurrence(
        technique_id="T1566",
        asset_id="WS01",
        attributes=NodeAttributes(
            tactics=["initial-access"],
            outcomes=[],
            q_local_success=0.5,
            impact_confidentiality=0.2,
            impact_integrity=0.1,
            impact_availability=0.1,
            critical_asset=False,
            accessible_asset=True,
        ),
    )
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
    graph = AttackGraph(
        nodes=[t1566, t1110, t1003],
        edges=[
            AttackGraphEdge(source_id="T1566@WS01", target_id="T1110.001@DC01"),
            AttackGraphEdge(source_id="T1110.001@DC01", target_id="T1003@DC01"),
        ],
    )
    assets = [
        Asset(asset_id="WS01", asset_type="workstation", critical=False, accessible=True, properties={"services": ["email"]}),
        Asset(asset_id="DC01", asset_type="domain_controller", critical=False, accessible=True, properties={"services": ["ldap"]}),
    ]
    locations = [
        Location(location_id="auth-store", location_type="credential_store", asset_id="DC01"),
        Location(location_id="mailbox-ws01", location_type="mailbox", asset_id="WS01"),
    ]
    topology_edges = [
        SITopologyEdge(source_asset_id="WS01", target_asset_id="DC01", relation_type="network_adjacency", bidirectional=True)
    ]
    return SystemInstance(graph=graph, si_inventory=SIInventory(assets=assets, locations=locations, topology_edges=topology_edges))


def main() -> None:
    kb = load_deception_catalog(CATALOG_PATH)
    attack_mapping = load_attack_deception_mapping(MAPPING_PATH)
    sp1_mapping = to_sp1_mapping(attack_mapping, kb)
    organization_catalog = load_organization_catalog(ORGANIZATION_CATALOG_PATH)
    validate_against_knowledge_catalog(organization_catalog, kb)
    organization_catalog_by_id = capabilities_by_id(organization_catalog)

    if not RAG_INDEX_DIR.exists():
        raise OrchestratorError(
            f"Aucun index RAG persisté trouvé dans '{RAG_INDEX_DIR}'. Réf. tâche §10/§23 : ce script ne "
            "reconstruit jamais silencieusement un index -- générer d'abord via :\n"
            "    python -m tools.rag.build_index --out-dir data/rag/index "
            "--corpus-version <version> --manifest-proof-out docs/chapter4/outputs/rag_index_manifest.json"
        )
    try:
        semantic_index, rag_index_manifest = load_rag_index(RAG_INDEX_DIR)
    except RagIndexStoreError as exc:
        raise OrchestratorError(f"Index RAG persisté incompatible ou corrompu : {exc}") from exc

    # Réf. §5/§16 : l'index lexical baseline reste construit à partir des
    # MÊMES chunks que l'index sémantique persisté -- même corpus, jamais
    # une recombinaison silencieusement différente.
    from src.rag_indexer import build_index

    lexical_index = build_index(list(semantic_index.chunks))

    print(f"Index RAG persisté rechargé : {RAG_INDEX_DIR} ({len(semantic_index)} chunks, sans ré-encodage).")

    print("Chargement du reranker cross-encoder REEL (une seule fois pour tout le run)...")
    reranker = CrossEncoderReranker.load()
    print(f"Reranker charge : {reranker.model_name}")

    attack_kb = None
    if ATTACK_RAW_PATH.exists():
        attack_kb = load_attack_knowledge(ATTACK_RAW_PATH, include_revoked=True, include_deprecated=True)

    try:
        result = run_pipeline(
            run_id="chapter4-example",
            instance=build_small_real_instance(),
            catalog=dict(kb.mechanisms_by_id),
            organization_catalog=organization_catalog_by_id,
            mapping=sp1_mapping,
            lexical_index=lexical_index,
            semantic_index=semantic_index,
            reranker=reranker,
            attack_kb=attack_kb,
            # Réf. tâche §24 : TECHNICAL INTEGRATION FALLBACK -- ce repli
            # déterministe démontre l'intégration technique bout-en-bout,
            # il n'est JAMAIS une annotation LLM réelle (voir docstring de
            # module et src/annotator_llm.py::RuleBasedStubAnnotator).
            annotator=RuleBasedStubAnnotator(),
            cost_inputs_by_mechanism={
                mechanism_id: {
                    "deployment": {"t_setup": 4.0, "w_eng": 50.0, "l_data": 1.0, "w_data": 20.0, "c_integration": 50.0},
                    "resource": {"r_cpu": 0.5, "c_cpu": 0.02, "r_ram": 1.0, "c_ram": 0.01, "r_disk": 5.0, "c_disk": 0.001, "r_network": 0.1, "c_network": 0.05},
                    "maintenance": {"t_monitoring": 0.1, "w_eng": 50.0, "s_logs": 0.5, "w_storage": 0.01, "c_updates": 0.2},
                }
                for mechanism_id in kb.mechanisms_by_id
            },
            horizon=720.0,
            budget_total=5000.0,
            theta_c=THETA,
            theta_i=THETA,
            theta_a=THETA,
            q_by_occurrence={"T1566@WS01": 0.5, "T1110.001@DC01": 0.6, "T1003@DC01": 0.65},
            impact_by_occurrence={"T1566@WS01": 0.14, "T1110.001@DC01": 0.35, "T1003@DC01": 0.61},
            annotation_set_version="chapter4-example-v1",
            rag_index_manifest=rag_index_manifest,
            deception_catalog_version=kb.catalog_version,
            organization_catalog_version=organization_catalog.catalog_version,
            mapping_version=attack_mapping.mapping_version,
            llm_provider=RULE_BASED_STUB_MODEL_VERSION,
            llm_model=RULE_BASED_STUB_MODEL_VERSION,
            prompt_version=RuleBasedStubAnnotator().prompt_version,
        )
    except OrchestratorError as exc:
        print(f"CAS B : aucun plan de deploiement produit -- {exc}")
        return

    manifest = result["run_manifest"]
    risks = result["risks"]
    admissible_count = manifest["candidates_admissible"]
    deployment_plan = result["deployment_plan"]
    lines = [
        "Pipeline complet - resultat reel (src/orchestrator.py, RAG contextuel)",
        "-" * 70,
        f"run_id : {manifest['run_id']}",
        f"Fichiers ecrits (runs/{manifest['run_id']}/) : {', '.join(manifest['files'])}",
        f"Catalogue de connaissances : {kb.catalog_version} ({len(kb.mechanisms_by_id)} mecanismes)",
        f"Catalogue operationnel : {organization_catalog.catalog_version} ({len(organization_catalog_by_id)} references)",
        f"Mapping M_i,d : {attack_mapping.mapping_version}",
        f"Index RAG : {manifest['rag']['corpus_chunk_count']} chunks, modele={manifest['rag']['embedding_model']}, "
        f"backend={manifest['rag']['vector_backend']}, reranker={manifest['rag']['reranker_model']}",
        f"Candidats evalues / admissibles : {manifest['candidates_evaluated']} / {admissible_count}",
        f"Configurations enumerees / faisables : {manifest['configurations_enumerated']} / {manifest['configurations_feasible']}",
        f"Taille du front de Pareto : {manifest['pareto_front_size']}",
        "",
    ]
    if deployment_plan:
        lines += [
            "Rapport de deploiement Y* (src/reporter.py, illustratif, DE issu du repli rule_based_stub) :",
            render_text_report(result["deployment_report"]).rstrip("\n"),
            "",
            "Risque terminal (T1003@DC01) :",
            f"  avec deception : {risks['avec_deception']['T1003@DC01']:.4f}",
            f"  sans deception : {risks['sans_deception']['T1003@DC01']:.4f}",
        ]
    else:
        lines += ["Plan de deploiement Y* : VIDE (aucune configuration realisable sous le budget donne)."]
    lines += [
        "-" * 70,
        "Note : DE issu du repli deterministe rule_based_stub (TECHNICAL INTEGRATION",
        "FALLBACK -- aucune API LLM reelle disponible) -- preuve d'execution",
        "bout-en-bout du RAG contextuel, pas un resultat experimental du chapitre 5.",
    ]
    text = "\n".join(lines) + "\n"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "pipeline_example.txt").write_text(text, encoding="utf-8")
    print(text)
    print(f"Details complets : runs/{manifest['run_id']}/")
    print(f"Resume texte : {OUT_DIR / 'pipeline_example.txt'}")


if __name__ == "__main__":
    main()
