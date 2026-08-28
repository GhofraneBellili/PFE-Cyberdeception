"""
Réf. architecture : CLAUDE.md §11.2 (entrées du LLM) — réf. tâche
« renforcer l'architecture et l'implémentation du module RAG utilisé par
SP2 », §22 « Exemple technique — un candidat admissible réel ».

Exemple exécutable réel : prend UN candidat réellement admissible produit
par SP1 (`examples.sp1_extended_real_example`, catalogue de connaissances
et catalogue organisationnel réels, mapping M_{i,d} réel), et exécute le
pipeline RAG contextuel ONLINE jusqu'à l'`CandidateEvidenceBundle` --
**PAS le LLM** (§22 : ce script montre l'IMPLÉMENTATION, pas une
performance ni une annotation).

Chaîne réellement exécutée :

    candidat REEL admissible (SP1)
    -> RagCandidateContext (src/rag_candidate_context.py)
    -> Q_realism / Q_interaction / Q_effect (src/rag_query_builder.py)
    -> corpus RAG REEL (ATT&CK + D3FEND + Engage + littérature déjà
       versionnés, data/attack/staging/ + data/deception/staging/)
    -> retrieval large (lexical + sémantique, src/rag_evidence.py)
    -> reranking contextuel RÉEL (cross-encoder sentence-transformers,
       src/reranker.py -- jamais simulé)
    -> diversification (§12)
    -> CandidateEvidenceBundle (§13)

`technique_name` (RagCandidateContext) reste `None` si
`data/attack/raw/enterprise-attack.json` n'est pas présent localement
(fichier officiel volumineux, jamais versionné -- voir
`data/attack/README.md`) : ce script ne fabrique jamais ce champ, il le
laisse simplement absent (§25.3). Le CORPUS RAG lui-même (chunks ATT&CK)
ne dépend PAS de ce fichier brut : il vient du staging déjà versionné
(`data/attack/staging/attack_rag_seed_*.json`), toujours disponible.

Exécution (télécharge réellement un modèle d'embeddings sémantiques et un
modèle de reranking si absents du cache local -- nécessite un accès
réseau la première fois) :
    python -m examples.rag_sp2_context_example

Sorties :
    docs/chapter4/outputs/rag_candidate_context_example.json
    docs/chapter4/outputs/rag_queries_example.json
    docs/chapter4/outputs/rag_evidence_bundle_example.json
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from src.admissibility import build_admissibility_report
from src.knowledge_attack import load_attack_knowledge
from src.knowledge_deception import load_attack_deception_mapping, load_deception_catalog, to_sp1_mapping
from src.organization_catalog import capabilities_by_id, load_organization_catalog, validate_against_knowledge_catalog
from src.rag_candidate_context import build_rag_candidate_context
from src.rag_evidence import build_candidate_evidence_bundle
from src.rag_indexer import build_index, build_semantic_index, load_attack_chunks, load_d3fend_chunks, load_engage_chunks, load_literature_chunks
from src.rag_query_builder import build_rag_queries
from src.reranker import CrossEncoderReranker
from examples.sp1_extended_real_example import build_example_instance

CATALOG_PATH = Path("data/deception/deception_catalog.json")
MAPPING_PATH = Path("data/deception/attack_deception_mapping.json")
ORGANIZATION_CATALOG_PATH = Path("examples/data/organization_deception_catalog.json")
ATTACK_RAW_PATH = Path("data/attack/raw/enterprise-attack.json")
ATTACK_STAGING_DIR = Path("data/attack/staging")
DECEPTION_STAGING_DIR = Path("data/deception/staging")
OUT_DIR = Path("docs/chapter4/outputs")

THETA = 0.85


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def find_first_admissible_candidate(report: dict) -> dict | None:
    """Réf. tâche §22 : le candidat vient de la sortie RÉELLE de SP1,
    jamais codé manuellement -- sélection déterministe (premier candidat
    rencontré dans l'ordre stable du rapport) pour la reproductibilité."""
    for occurrence_id, occ_report in report["occurrences"].items():
        for entry in occ_report["C_i_h"]:
            return {"occurrence_id": occurrence_id, "mechanism_id": entry["mechanism_id"], "location_id": entry["location_id"]}
    return None


def build_real_rag_indices():
    """Réf. §15/§16 : construit les index OFFLINE à partir des QUATRE
    sources déjà versionnées (ATT&CK + D3FEND + Engage + littérature) --
    jamais recalculé par candidat (§16)."""
    attack_seed_files = sorted(ATTACK_STAGING_DIR.glob("attack_rag_seed_*.json"))
    if not attack_seed_files:
        raise FileNotFoundError(
            "Aucun staging ATT&CK trouve dans data/attack/staging/ -- "
            "generer d'abord via tools.attack_kb.attack_seed_builder."
        )
    chunks = (
        load_attack_chunks(load_json(attack_seed_files[0]))
        + load_d3fend_chunks(load_json(DECEPTION_STAGING_DIR / "d3fend_deception_seed_1.5.0.json"))
        + load_engage_chunks(load_json(DECEPTION_STAGING_DIR / "engage_activity_seed_1.0.json"))
        + load_literature_chunks(load_json(DECEPTION_STAGING_DIR / "literature_evidence_seed_1.2.json"))
    )
    lexical_index = build_index(chunks)
    semantic_index = build_semantic_index(chunks)
    return lexical_index, semantic_index, len(chunks)


def _evidence_item_to_dict(item) -> dict:
    payload = dataclasses.asdict(item)
    return payload


def main() -> None:
    kb = load_deception_catalog(CATALOG_PATH)
    attack_mapping = load_attack_deception_mapping(MAPPING_PATH)
    sp1_mapping = to_sp1_mapping(attack_mapping, kb)
    organization_catalog = capabilities_by_id(load_organization_catalog(ORGANIZATION_CATALOG_PATH))
    validate_against_knowledge_catalog(load_organization_catalog(ORGANIZATION_CATALOG_PATH), kb)
    instance = build_example_instance()
    catalog = dict(kb.mechanisms_by_id)

    report = build_admissibility_report(
        instance, catalog, organization_catalog, sp1_mapping, theta_c=THETA, theta_i=THETA, theta_a=THETA
    )
    candidate = find_first_admissible_candidate(report)
    if candidate is None:
        print("CAS B : aucun candidat reellement admissible dans la sortie de SP1.")
        print("Ce script n'invente aucun candidat : rien a traiter pour le RAG contextuel.")
        return

    occurrence = next(occ for occ in instance.graph.nodes if occ.occurrence_id == candidate["occurrence_id"])
    mechanism = catalog[candidate["mechanism_id"]]
    location = next(loc for loc in instance.si_inventory.locations if loc.location_id == candidate["location_id"])
    print(f"Candidat REEL admissible recupere depuis SP1 : {candidate}")

    attack_kb = None
    if ATTACK_RAW_PATH.exists():
        attack_kb = load_attack_knowledge(ATTACK_RAW_PATH, include_revoked=True, include_deprecated=True)
        print(f"Base ATT&CK reelle chargee ({len(attack_kb.techniques_by_id)} techniques) : technique_name renseigne.")
    else:
        print(
            f"{ATTACK_RAW_PATH} absent (fichier officiel non versionne, voir data/attack/README.md) : "
            "technique_name restera None (jamais invente)."
        )

    candidate_context = build_rag_candidate_context(
        occurrence=occurrence,
        mechanism=mechanism,
        location=location,
        instance=instance,
        theta_c=THETA,
        theta_i=THETA,
        theta_a=THETA,
        attack_kb=attack_kb,
    )
    queries = build_rag_queries(candidate_context)

    print("Construction des index RAG reels (ATT&CK + D3FEND + Engage + litterature)...")
    lexical_index, semantic_index, chunk_count = build_real_rag_indices()
    print(f"Corpus indexe : {chunk_count} chunks.")

    print("Chargement du reranker cross-encoder REEL (peut telecharger le modele au premier lancement)...")
    reranker = CrossEncoderReranker.load()
    print(f"Reranker charge : {reranker.model_name}")

    print("Execution du pipeline retrieval large -> reranking -> diversification (3 familles)...")
    bundle = build_candidate_evidence_bundle(
        candidate_context,
        lexical_index=lexical_index,
        semantic_index=semantic_index,
        reranker=reranker,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    context_path = OUT_DIR / "rag_candidate_context_example.json"
    context_path.write_text(
        json.dumps(candidate_context.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    queries_path = OUT_DIR / "rag_queries_example.json"
    queries_path.write_text(
        json.dumps({"candidate": candidate, "queries": queries}, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    bundle_payload = {
        "candidate_id": bundle.candidate_id,
        "reranker_model": reranker.model_name,
        "corpus_chunk_count": chunk_count,
        "embedding_model": semantic_index.embedding_model,
        "vector_backend": semantic_index.backend,
        "families": {
            family_name: {
                "query": family.query,
                "evidence": [_evidence_item_to_dict(item) for item in family.evidence],
            }
            for family_name, family in bundle.families().items()
        },
    }
    bundle_path = OUT_DIR / "rag_evidence_bundle_example.json"
    bundle_path.write_text(json.dumps(bundle_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print(f"Ecrit : {context_path}")
    print(f"Ecrit : {queries_path}")
    print(f"Ecrit : {bundle_path}")
    for family_name, family in bundle.families().items():
        sources = sorted({item.source_type for item in family.evidence})
        print(f"  {family_name} : {len(family.evidence)} preuve(s), sources={sources}")


if __name__ == "__main__":
    main()
