"""
Réf. tâche « campagne d'évaluation réelle RAG/LLM/système » §4 : construction
du jeu FIXE et documenté de candidats admissibles réels utilisé par toutes
les analyses d'annotation LLM (conformité, ancrage, stabilité) — réutilise
STRICTEMENT les mêmes données et le même chemin de construction que
`examples/orchestrator_example.py::build_small_real_instance` (catalogue de
connaissances réel, mapping réel, catalogue organisationnel réel, index RAG
persisté réel, reranker cross-encoder réel), jamais un catalogue synthétique
réduit.

Ne modifie rien dans `src/` ni dans `examples/` (« CHAPTER 4 IMPLEMENTATION
FROZEN ») — importe et réutilise tel quel.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from examples.orchestrator_example import (
    ATTACK_STAGING_DIR,
    CATALOG_PATH,
    MAPPING_PATH,
    ORGANIZATION_CATALOG_PATH,
    RAG_INDEX_DIR,
    THETA,
    build_small_real_instance,
)
from src.admissibility import build_admissibility_report
from src.attack_runtime_knowledge import find_latest_attack_staging_file, load_attack_runtime_knowledge
from src.knowledge_deception import load_attack_deception_mapping, load_deception_catalog, to_sp1_mapping
from src.organization_catalog import capabilities_by_id, load_organization_catalog, validate_against_knowledge_catalog
from src.rag_candidate_context import build_rag_candidate_context
from src.rag_evidence import build_candidate_evidence_bundle, to_annotation_evidence
from src.rag_index_store import RagIndexStoreError, load_rag_index, rebuild_lexical_index
from src.rag_query_builder import build_rag_queries
from src.reranker import CrossEncoderReranker
from src.schemas import AnnotationContext, AttackOccurrenceRef, DeceptionRef, GraphContext, SystemInstance


class FixedCandidatesError(Exception):
    """Erreur de construction du jeu fixe de candidats admissibles réels."""


@dataclass(frozen=True)
class FixedCandidate:
    occurrence_id: str
    mechanism_id: str
    location_id: str
    context: AnnotationContext


def build_fixed_annotation_candidates() -> tuple[list[FixedCandidate], dict, dict]:
    """Construit RÉELLEMENT (aucune donnée synthétique) les contextes
    d'annotation des candidats admissibles de l'instance de référence à 3
    occurrences (`build_small_real_instance`) — même chemin exact que
    `run_pipeline` (SP1 -> RagCandidateContext -> requêtes -> evidence
    bundle -> AnnotationContext), rejoué ici hors de `run_pipeline` pour
    pouvoir appeler l'annotateur plusieurs fois par candidat (§4.3)."""
    kb = load_deception_catalog(CATALOG_PATH)
    attack_mapping = load_attack_deception_mapping(MAPPING_PATH)
    sp1_mapping = to_sp1_mapping(attack_mapping, kb)
    organization_catalog = load_organization_catalog(ORGANIZATION_CATALOG_PATH)
    validate_against_knowledge_catalog(organization_catalog, kb)
    organization_catalog_by_id = capabilities_by_id(organization_catalog)

    if not RAG_INDEX_DIR.exists():
        raise FixedCandidatesError(f"Index RAG persiste introuvable : {RAG_INDEX_DIR}.")
    try:
        semantic_index, rag_index_manifest = load_rag_index(RAG_INDEX_DIR)
    except RagIndexStoreError as exc:
        raise FixedCandidatesError(f"Index RAG persiste incompatible ou corrompu : {exc}") from exc
    lexical_index = rebuild_lexical_index(semantic_index)
    reranker = CrossEncoderReranker.load()
    attack_kb = load_attack_runtime_knowledge(find_latest_attack_staging_file(ATTACK_STAGING_DIR))

    instance: SystemInstance = build_small_real_instance()
    admissibility_report = build_admissibility_report(
        instance, dict(kb.mechanisms_by_id), organization_catalog_by_id, sp1_mapping, theta_c=THETA, theta_i=THETA, theta_a=THETA
    )

    occurrence_by_id = {occ.occurrence_id: occ for occ in instance.graph.nodes}
    location_by_id = {loc.location_id: loc for loc in instance.si_inventory.locations}

    candidates: list[FixedCandidate] = []
    for occurrence_id, occ_report in admissibility_report["occurrences"].items():
        occurrence = occurrence_by_id[occurrence_id]
        for entry in occ_report["C_i_h"]:
            mechanism = kb.mechanisms_by_id[entry["mechanism_id"]]
            location_id = entry["location_id"]
            location = location_by_id[location_id]

            candidate_context = build_rag_candidate_context(
                occurrence=occurrence, mechanism=mechanism, location=location, instance=instance,
                theta_c=THETA, theta_i=THETA, theta_a=THETA, attack_kb=attack_kb,
            )
            bundle = build_candidate_evidence_bundle(
                candidate_context, lexical_index=lexical_index, semantic_index=semantic_index, reranker=reranker,
            )
            retrieved_evidence, evidence_by_family = to_annotation_evidence(bundle)
            if not retrieved_evidence:
                raise FixedCandidatesError(f"Aucune preuve RAG pour {occurrence_id}/{mechanism.id}/{location_id}.")

            context = AnnotationContext(
                attack_occurrence=AttackOccurrenceRef(
                    technique_id=occurrence.technique_id, asset_id=occurrence.asset_id, attributes=occurrence.attributes
                ),
                deception=DeceptionRef(id=mechanism.id, name=mechanism.name),
                placement=location_id,
                graph_context=GraphContext(),
                system_context={},
                retrieved_evidence=retrieved_evidence,
                evidence_by_family=evidence_by_family,
            )
            candidates.append(
                FixedCandidate(occurrence_id=occurrence_id, mechanism_id=mechanism.id, location_id=location_id, context=context)
            )

    metadata = {
        "instance": "build_small_real_instance (examples/orchestrator_example.py)",
        "candidate_count": len(candidates),
        "candidate_ids": [f"{c.occurrence_id}|{c.mechanism_id}|{c.location_id}" for c in candidates],
        "rag_corpus_chunk_count": len(semantic_index),
        "rag_embedding_model": semantic_index.embedding_model,
        "reranker_model": reranker.model_name,
        "rag_index_manifest": rag_index_manifest,
    }
    reusable = {
        "system_instance": instance,
        "admissibility_report": admissibility_report,
        "deception_catalog": dict(kb.mechanisms_by_id),
    }
    return candidates, metadata, reusable
