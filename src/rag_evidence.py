"""
Réf. architecture : "11.2 Entrées du LLM" (CLAUDE.md §11.2) — réf. tâche
« renforcer l'architecture et l'implémentation du module RAG utilisé par
SP2 », §8 à §14 « Retrieval en deux étapes, reranking contextuel,
diversité des preuves, structuration en `CandidateEvidenceBundle` ».

Pipeline ONLINE complet d'un candidat déjà admissible `(T_{i,h}, d, l)`
(réf. §16, chaîne cible) :

```
RagCandidateContext -> build_rag_queries -> {Q_realism, Q_interaction, Q_effect}
    -> pour chaque requête :
        Stage A (RETRIEVAL LARGE, §8) : lexical top-N + sémantique top-N
            -> fusion/dédoublonnage (mêmes scores que retrieve_hybrid,
               mais individuellement conservés : sémantique/lexical/hybride)
        Stage B (RERANKING, §9/§10) : cross-encoder contextuel sur le pool
            fusionné -> reranker_score + final_rank
        Diversification (§12) : quota MAX de chunks par document_id,
            appliqué APRÈS le reranking, jamais un quota par source_type
    -> CandidateEvidenceBundle{candidate_id, realism, interaction, effect}
```

Ce module ne calcule AUCUNE sous-métrique (§11.5) : il ne fait que
récupérer, reranker et structurer des preuves documentaires. Aucun appel
LLM ici (§10 SP2, invariant central du projet).

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.rag_config import (
    resolve_diversity_max_per_document,
    resolve_final_top_k,
    resolve_retrieval_candidates,
)
from src.rag_indexer import Chunk, RagIndex, SemanticRagIndex, SourceType
from src.rag_query_builder import build_rag_queries
from src.rag_retriever import DEFAULT_HYBRID_ALPHA, RetrievalResult, retrieve, retrieve_semantic
from src.reranker import RerankResult, Reranker
from src.schemas import DeceptionEvidence, RagCandidateContext


class RagEvidenceError(Exception):
    """Erreur de construction du pipeline de retrieval contextuel SP2."""


# ---------------------------------------------------------------------------
# Stage A — RETRIEVAL LARGE (§8) : fusion lexical/sémantique en conservant
# les trois scores individuellement (à la différence de
# src/rag_retriever.py::retrieve_hybrid, qui ne conserve que le score fusionné)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoredCandidate:
    """Un chunk du pool large, avec ses trois scores conservés
    individuellement (réf. §10/§13, traçabilité complète)."""

    chunk: Chunk
    semantic_score: float
    lexical_score: float
    hybrid_score: float


def retrieve_large_pool(
    lexical_index: RagIndex,
    semantic_index: SemanticRagIndex,
    query: str,
    *,
    pool_k: int,
    alpha: float = DEFAULT_HYBRID_ALPHA,
    embedder: object | None = None,
) -> list[ScoredCandidate]:
    """Réf. §8 « RETRIEVAL LARGE » (stage A) : même formule de fusion que
    `retrieve_hybrid` (`score_hybride = alpha * score_sémantique + (1-alpha)
    * score_lexical`), mais retourne les TROIS scores par chunk plutôt que
    seulement le score fusionné — nécessaire pour que le reranking (stage
    B) et le `CandidateEvidenceBundle` (§13) restent pleinement traçables."""
    if pool_k <= 0:
        raise RagEvidenceError(f"pool_k doit être strictement positif (valeur reçue : {pool_k}).")

    lexical_results = retrieve(lexical_index, query, top_k=pool_k)
    semantic_results = retrieve_semantic(semantic_index, query, top_k=pool_k, embedder=embedder)

    lexical_by_id = {result.chunk.chunk_id: result for result in lexical_results}
    semantic_by_id = {result.chunk.chunk_id: result for result in semantic_results}
    all_ids = set(lexical_by_id) | set(semantic_by_id)

    scored: list[ScoredCandidate] = []
    for chunk_id in all_ids:
        lexical_score = lexical_by_id[chunk_id].score if chunk_id in lexical_by_id else 0.0
        semantic_score = semantic_by_id[chunk_id].score if chunk_id in semantic_by_id else 0.0
        chunk = semantic_by_id[chunk_id].chunk if chunk_id in semantic_by_id else lexical_by_id[chunk_id].chunk
        hybrid_score = alpha * semantic_score + (1 - alpha) * lexical_score
        scored.append(
            ScoredCandidate(chunk=chunk, semantic_score=semantic_score, lexical_score=lexical_score, hybrid_score=hybrid_score)
        )
    scored.sort(key=lambda candidate: candidate.hybrid_score, reverse=True)
    return scored


# ---------------------------------------------------------------------------
# Diversification (§12) — appliquée APRÈS le reranking, jamais un quota
# rigide par source_type, jamais avant le reranking (la diversité reste
# secondaire à la pertinence)
# ---------------------------------------------------------------------------


def diversify_by_document(
    ranked: list[RerankResult],
    *,
    max_per_document: int,
    top_k: int,
) -> list[RerankResult]:
    """Réf. §12 : parcourt `ranked` (déjà trié par pertinence décroissante
    par le reranker) et ne retient AU PLUS `max_per_document` chunks issus
    du même `document_id`, en conservant l'ordre de pertinence — un chunk
    qui dépasserait le quota de son document est simplement SAUTÉ (jamais
    supprimé silencieusement du pool si une place reste disponible plus
    loin), jamais un quota artificiel par `source_type` (réf. §12 : « ne
    jamais forcer un 1 ATT&CK + 1 D3FEND + 1 littérature »). `final_rank`
    est réassigné séquentiellement sur le résultat diversifié."""
    if max_per_document <= 0:
        raise RagEvidenceError(f"max_per_document doit être strictement positif (valeur reçue : {max_per_document}).")

    counts: dict[str, int] = {}
    kept: list[RerankResult] = []
    for item in ranked:
        document_id = item.retrieval_result.chunk.document_id
        if counts.get(document_id, 0) >= max_per_document:
            continue
        counts[document_id] = counts.get(document_id, 0) + 1
        kept.append(item)
        if len(kept) >= top_k:
            break

    return [
        RerankResult(retrieval_result=item.retrieval_result, reranker_score=item.reranker_score, final_rank=rank)
        for rank, item in enumerate(kept, start=1)
    ]


# ---------------------------------------------------------------------------
# Structuration finale — CandidateEvidenceBundle (§13)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceItem:
    """Réf. §13 : un élément de preuve retenu dans le top-k final d'une
    famille, avec TOUS les scores intermédiaires (§10) pour une
    traçabilité complète."""

    chunk_id: str
    source_type: SourceType
    source_id: str
    text: str
    final_rank: int
    semantic_score: float
    lexical_score: float
    hybrid_score: float
    reranker_score: float
    metadata: dict
    provenance: dict


@dataclass(frozen=True)
class FamilyEvidence:
    """Réf. §13 : `{query, evidence[]}` pour une famille de sous-métriques
    (realism/interaction/effect)."""

    query: str
    evidence: tuple[EvidenceItem, ...]


@dataclass(frozen=True)
class CandidateEvidenceBundle:
    """Réf. §13 : sortie structurée du pipeline RAG contextuel pour un
    candidat admissible — `{candidate_id, realism, interaction, effect}`."""

    candidate_id: str
    realism: FamilyEvidence
    interaction: FamilyEvidence
    effect: FamilyEvidence

    def families(self) -> dict[str, FamilyEvidence]:
        return {"realism": self.realism, "interaction": self.interaction, "effect": self.effect}


def build_family_evidence(
    *,
    query: str,
    lexical_index: RagIndex,
    semantic_index: SemanticRagIndex,
    reranker: Reranker,
    retrieval_candidates: int,
    final_top_k: int,
    diversity_max_per_document: int,
    alpha: float = DEFAULT_HYBRID_ALPHA,
    embedder: object | None = None,
) -> FamilyEvidence:
    """Réf. §8-§13 : exécute le pipeline complet (stage A -> stage B ->
    diversification) pour UNE requête (une famille de sous-métriques)."""
    pool = retrieve_large_pool(
        lexical_index, semantic_index, query, pool_k=retrieval_candidates, alpha=alpha, embedder=embedder
    )
    if not pool:
        return FamilyEvidence(query=query, evidence=())

    scores_by_chunk_id = {candidate.chunk.chunk_id: candidate for candidate in pool}
    pool_as_retrieval_results = [
        RetrievalResult(chunk=candidate.chunk, score=candidate.hybrid_score) for candidate in pool
    ]

    # Réf. §12 : le reranker reçoit un pool STRICTEMENT plus large que
    # final_top_k, pour laisser à la diversification une marge réelle de
    # choix plutôt que de tronquer avant même d'avoir pu diversifier.
    rerank_pool_k = min(len(pool_as_retrieval_results), max(final_top_k * 3, final_top_k))
    reranked = reranker.rerank(query, pool_as_retrieval_results, top_k=rerank_pool_k)
    diversified = diversify_by_document(reranked, max_per_document=diversity_max_per_document, top_k=final_top_k)

    evidence_items = tuple(
        EvidenceItem(
            chunk_id=item.retrieval_result.chunk.chunk_id,
            source_type=item.retrieval_result.chunk.source_type,
            source_id=item.retrieval_result.chunk.source_id,
            text=item.retrieval_result.chunk.text,
            final_rank=item.final_rank,
            semantic_score=scores_by_chunk_id[item.retrieval_result.chunk.chunk_id].semantic_score,
            lexical_score=scores_by_chunk_id[item.retrieval_result.chunk.chunk_id].lexical_score,
            hybrid_score=scores_by_chunk_id[item.retrieval_result.chunk.chunk_id].hybrid_score,
            reranker_score=item.reranker_score,
            metadata=dict(item.retrieval_result.chunk.metadata),
            provenance={
                "document_id": item.retrieval_result.chunk.document_id,
                "locator": item.retrieval_result.chunk.locator,
                "text_hash": item.retrieval_result.chunk.text_hash,
            },
        )
        for item in diversified
    )
    return FamilyEvidence(query=query, evidence=evidence_items)


def build_candidate_evidence_bundle(
    candidate_context: RagCandidateContext,
    *,
    lexical_index: RagIndex,
    semantic_index: SemanticRagIndex,
    reranker: Reranker,
    retrieval_candidates: int | None = None,
    final_top_k: int | None = None,
    diversity_max_per_document: int | None = None,
    alpha: float = DEFAULT_HYBRID_ALPHA,
    embedder: object | None = None,
    env: dict[str, str] | None = None,
) -> CandidateEvidenceBundle:
    """Réf. §7-§13 : point d'entrée unique du pipeline ONLINE — construit
    les trois requêtes déterministes (§6/§7), exécute le retrieval en deux
    étapes + diversification (§8-§12) pour chacune, et assemble le
    `CandidateEvidenceBundle` (§13). Paramètres de configuration résolus
    via `src/rag_config.py` (paramètre explicite > variable d'environnement
    > défaut documenté) si non fournis explicitement."""
    queries = build_rag_queries(candidate_context)
    resolved_retrieval_candidates = resolve_retrieval_candidates(retrieval_candidates, env=env)
    resolved_final_top_k = resolve_final_top_k(final_top_k, env=env)
    resolved_diversity_max_per_document = resolve_diversity_max_per_document(diversity_max_per_document, env=env)

    families = {
        family: build_family_evidence(
            query=query_text,
            lexical_index=lexical_index,
            semantic_index=semantic_index,
            reranker=reranker,
            retrieval_candidates=resolved_retrieval_candidates,
            final_top_k=resolved_final_top_k,
            diversity_max_per_document=resolved_diversity_max_per_document,
            alpha=alpha,
            embedder=embedder,
        )
        for family, query_text in queries.items()
    }

    candidate_id = f"{candidate_context.occurrence_id}|{candidate_context.mechanism_id}|{candidate_context.location_id}"
    return CandidateEvidenceBundle(
        candidate_id=candidate_id,
        realism=families["realism"],
        interaction=families["interaction"],
        effect=families["effect"],
    )


# ---------------------------------------------------------------------------
# Adaptation vers AnnotationContext (§14) — préparation de l'entrée LLM
# ---------------------------------------------------------------------------


def to_annotation_evidence(bundle: CandidateEvidenceBundle) -> tuple[list[DeceptionEvidence], dict[str, list[str]]]:
    """Réf. §14 : convertit un `CandidateEvidenceBundle` en
    `(retrieved_evidence, evidence_by_family)`, le format attendu par
    `AnnotationContext` (`src/schemas.py`) — un même `chunk_id` récupéré
    par plusieurs familles n'apparaît qu'UNE fois dans `retrieved_evidence`
    (jamais un doublon de texte), mais reste référencé dans chaque famille
    concernée via `evidence_by_family`."""
    retrieved_evidence: dict[str, DeceptionEvidence] = {}
    evidence_by_family: dict[str, list[str]] = {}

    for family_name, family_evidence in bundle.families().items():
        sources: list[str] = []
        for item in family_evidence.evidence:
            if item.chunk_id not in retrieved_evidence:
                retrieved_evidence[item.chunk_id] = DeceptionEvidence(source=item.chunk_id, passage=item.text)
            sources.append(item.chunk_id)
        evidence_by_family[family_name] = sources

    return list(retrieved_evidence.values()), evidence_by_family


# ---------------------------------------------------------------------------
# Sérialisation JSON — réf. tâche « maturation technique finale du
# chapitre 4 », §15/§16 (traçabilité par candidat, artefacts de run)
# ---------------------------------------------------------------------------


def candidate_evidence_bundle_to_dict(bundle: CandidateEvidenceBundle) -> dict:
    """Réf. §15/§16 : représentation JSON complète d'un
    `CandidateEvidenceBundle` (traçabilité par candidat dans
    `runs/<run_id>/evidence_bundles.json`, réutilisée aussi par
    `examples/rag_sp2_context_example.py`) — dataclasses -> dict, jamais
    une perte de champ."""
    return {
        "candidate_id": bundle.candidate_id,
        "families": {
            family_name: {
                "query": family.query,
                "evidence": [
                    {
                        "chunk_id": item.chunk_id,
                        "source_type": item.source_type,
                        "source_id": item.source_id,
                        "text": item.text,
                        "final_rank": item.final_rank,
                        "semantic_score": item.semantic_score,
                        "lexical_score": item.lexical_score,
                        "hybrid_score": item.hybrid_score,
                        "reranker_score": item.reranker_score,
                        "metadata": item.metadata,
                        "provenance": item.provenance,
                    }
                    for item in family.evidence
                ],
            }
            for family_name, family in bundle.families().items()
        },
    }
