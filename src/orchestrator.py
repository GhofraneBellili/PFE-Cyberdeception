"""
Réf. architecture : "19. Workflow complet d'exécution" (CLAUDE.md §19) et
section « Orchestrateur » de la tâche d'implémentation du chapitre 4.
Réf. tâche « maturation technique finale du chapitre 4 » §2/§3 : SP2 est
désormais le pipeline RAG CONTEXTUEL par candidat (production/reference
pipeline), plus l'ancien chemin à requête unique.

Point d'entrée unique enchaînant, sur une instance déjà validée :

    SP1 (admissibility)
    -> pour chaque candidat admissible (T_i,h,d,l) :
       RagCandidateContext -> Q_realism/Q_interaction/Q_effect
       -> CandidateEvidenceBundle (retrieval large + reranking +
          diversification, src/rag_evidence.py)
       -> AnnotationContext (evidence_by_family) -> annotation des 11
          sous-métriques (annotator_llm)
    -> validation + agrégation + gel (annotation_validator)
    -> coût (cost_engine) -> résolution de (P) (optimizer) -> propagation
    du risque de la configuration sélectionnée (risk_engine, avant/après)
    -> transformation de y* en Y* (reporter, §17.6)

Chaque étape est déjà testée indépendamment dans son propre module ; ce
module ne fait qu'assembler les appels et sérialiser les résultats
intermédiaires dans `runs/<run_id>/`, un fichier par étape (§16 de la
tâche : « Only create files actually produced »).

**production/reference SP2 contextual pipeline (ce module)** : `run_pipeline`
utilise EXCLUSIVEMENT `build_rag_candidate_context` ->
`build_rag_queries` -> `build_candidate_evidence_bundle` ->
`to_annotation_evidence` (réf. tâche §3). L'ancien chemin à requête
unique (`src/rag_retriever.py::retrieve`/`retrieve_semantic`/
`retrieve_hybrid`, un seul jeu de preuves envoyé identiquement aux 11
sous-métriques) reste disponible et testé comme **legacy/experimental
retrieval API** — utile en test, en baseline de comparaison, ou pour une
future évaluation expérimentale (chapitre 5) — mais N'EST PLUS appelé par
`run_pipeline` (réf. tâche §4).

**Objets chargés UNE SEULE FOIS par run, jamais par candidat** (réf.
tâche §12/§13) : `reranker`, `semantic_index`/`lexical_index`, `embedder`,
la configuration RAG (`retrieval_candidates`/`final_top_k`/
`diversity_max_per_document`/`hybrid_alpha`) — tous reçus déjà construits/
chargés par l'appelant (typiquement depuis un index RAG persisté,
`src/rag_index_store.py::load_rag_index`), jamais reconstruits dans la
boucle candidat par candidat.

**Invariant central du projet (LLM hors du chemin d'exécution)** :
l'annotation LLM (`annotator_llm`) n'est appelée qu'UNE SEULE fois par
candidat, avant le gel (`annotation_validator`) — jamais pendant
`cost_engine`/`risk_engine`/`optimizer`. Ce module ne réappelle jamais le
provider après le gel.

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.admissibility import build_admissibility_report
from src.annotation_validator import freeze_table
from src.annotator_llm import AnnotationProvider
from src.attack_runtime_knowledge import AttackRuntimeKnowledge
from src.cost_engine import compute_cost_by_mechanism
from src.optimizer import OptimizerError, solve
from src.rag_candidate_context import build_rag_candidate_context
from src.rag_config import (
    DEFAULT_DIVERSITY_MAX_PER_DOCUMENT,
    DEFAULT_FINAL_TOP_K,
    DEFAULT_RETRIEVAL_CANDIDATES,
)
from src.rag_evidence import build_candidate_evidence_bundle, candidate_evidence_bundle_to_dict, to_annotation_evidence
from src.rag_indexer import RagIndex, SemanticRagIndex
from src.rag_query_builder import build_rag_queries
from src.rag_retriever import DEFAULT_HYBRID_ALPHA
from src.reporter import build_deployment_report
from src.reranker import Reranker
from src.risk_engine import propagate_risk
from src.schemas import (
    AnnotationContext,
    AttackOccurrenceRef,
    DeceptionMechanism,
    DeceptionRef,
    GraphContext,
    OrganizationDeceptionCapability,
    SystemInstance,
)


class OrchestratorError(Exception):
    """Erreur d'orchestration du pipeline complet."""


def _json_default(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"Objet non sérialisable en JSON : {type(value)!r}.")


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8")


def run_pipeline(
    *,
    run_id: str,
    instance: SystemInstance,
    catalog: dict[str, DeceptionMechanism],
    organization_catalog: dict[str, OrganizationDeceptionCapability],
    mapping: dict[str, list[str]],
    lexical_index: RagIndex,
    semantic_index: SemanticRagIndex,
    reranker: Reranker,
    annotator: AnnotationProvider,
    cost_inputs_by_mechanism: dict[str, dict],
    horizon: float,
    budget_total: float,
    theta_c: float,
    theta_i: float,
    theta_a: float,
    q_by_occurrence: dict[str, float],
    impact_by_occurrence: dict[str, float],
    annotation_set_version: str,
    attack_kb: AttackRuntimeKnowledge | None = None,
    rag_embedder: object | None = None,
    retrieval_candidates: int | None = None,
    final_top_k: int | None = None,
    diversity_max_per_document: int | None = None,
    hybrid_alpha: float = DEFAULT_HYBRID_ALPHA,
    rag_index_manifest: dict | None = None,
    deception_catalog_version: str | None = None,
    organization_catalog_version: str | None = None,
    mapping_version: str | None = None,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    prompt_version: str | None = None,
    output_root: Path | str = Path("runs"),
) -> dict[str, Any]:
    """Réf. §19 (workflow complet) + réf. tâche « maturation technique
    finale du chapitre 4 » §2/§3 : enchaîne SP1 -> RAG CONTEXTUEL par
    candidat -> annotation -> gel -> coût -> `(P)` -> reporting
    avant/après, et sauvegarde chaque étape dans `runs/<run_id>/`.

    `catalog` : catalogue de CONNAISSANCES (réf. tâche « separate
    knowledge and organization capabilities ») — décrit ce que sont les
    mécanismes. `organization_catalog` : catalogue OPÉRATIONNEL de
    l'organisation (`dict[str, OrganizationDeceptionCapability]`, réf.
    `src/organization_catalog.py::capabilities_by_id`) — seule source des
    décisions Autorise/PrerequisSatisfaits de SP1 (`src/admissibility.py`).
    SP1 est exécuté ICI, au runtime, à partir du graphe/SI COURANTS —
    jamais pré-calculé hors ligne.

    **RAG contextuel (production/reference pipeline, réf. tâche §3)** :
    pour CHAQUE candidat admissible `(T_{i,h}, d, l)`,
    `build_rag_candidate_context` -> `build_rag_queries` ->
    `build_candidate_evidence_bundle` (`src/rag_evidence.py`, retrieval
    large + reranking + diversification sur `lexical_index`/
    `semantic_index`/`reranker`) -> `to_annotation_evidence`
    (`evidence_by_family`). L'ancien chemin à requête unique
    (`src/rag_retriever.py::retrieve`/`retrieve_semantic`/
    `retrieve_hybrid`) N'EST PLUS appelé ici — il reste une
    **legacy/experimental retrieval API**, disponible pour les tests et
    une future comparaison expérimentale (chapitre 5), mais plus le
    chemin de référence de `run_pipeline`.

    `lexical_index`/`semantic_index`/`reranker`/`attack_kb`/`rag_embedder`
    sont reçus DÉJÀ CONSTRUITS/CHARGÉS par l'appelant (typiquement depuis
    un index RAG persisté, `src/rag_index_store.py::load_rag_index`, et un
    reranker chargé une seule fois, `src/reranker.py::CrossEncoderReranker.load`)
    — jamais reconstruits ici, et jamais recréés par candidat (réf. tâche
    §12/§13) : un seul appel de `run_pipeline` les réutilise pour tous les
    candidats du run.

    `rag_index_manifest`/`deception_catalog_version`/
    `organization_catalog_version`/`mapping_version`/`llm_provider`/
    `llm_model`/`prompt_version` : métadonnées de traçabilité PUREMENT
    déclaratives (réf. tâche §14, jamais recalculées ni devinées ici) —
    fournies par l'appelant depuis les objets déjà chargés
    (`src/rag_index_store.py::load_rag_index` retourne exactement le
    manifest attendu par `rag_index_manifest` ;
    `src/annotator_llm.py::detect_provider` fournit `llm_provider`/
    `llm_model`). Toutes optionnelles (`None` par défaut, omises du
    `run_manifest` si non fournies) — jamais de valeur inventée en leur
    absence (§25.3). Ne jamais y inclure de clé API, secret ou jeton
    (réf. tâche §14).

    Retourne un résumé en mémoire (mêmes données que les fichiers écrits)
    pour usage programmatique immédiat, en plus de la persistance sur
    disque.
    """
    run_dir = Path(output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    input_manifest = {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "occurrence_count": len(instance.graph.nodes),
        "mechanism_ids": sorted(catalog),
        "organization_mechanism_ids": sorted(organization_catalog),
        "organization_enabled_count": sum(1 for c in organization_catalog.values() if c.enabled),
        "mapping": mapping,
        "horizon": horizon,
        "budget_total": budget_total,
        "theta_c": theta_c,
        "theta_i": theta_i,
        "theta_a": theta_a,
        "annotation_set_version": annotation_set_version,
        "rag": {
            "pipeline": "contextual_sp2",
            "corpus_chunk_count": len(semantic_index),
            "embedding_model": semantic_index.embedding_model,
            "vector_backend": semantic_index.backend,
            "reranker_model": reranker.model_name,
            "retrieval_candidates": retrieval_candidates if retrieval_candidates is not None else DEFAULT_RETRIEVAL_CANDIDATES,
            "final_top_k": final_top_k if final_top_k is not None else DEFAULT_FINAL_TOP_K,
            "diversity_max_per_document": diversity_max_per_document if diversity_max_per_document is not None else DEFAULT_DIVERSITY_MAX_PER_DOCUMENT,
            "hybrid_alpha": hybrid_alpha,
        },
    }
    _write_json(run_dir / "input_manifest.json", input_manifest)

    # --- SP1 : admissibilité -------------------------------------------------
    admissibility_report = build_admissibility_report(
        instance, catalog, organization_catalog, mapping, theta_c=theta_c, theta_i=theta_i, theta_a=theta_a
    )
    _write_json(run_dir / "candidates.json", admissibility_report)

    occurrence_by_id = {occ.occurrence_id: occ for occ in instance.graph.nodes}
    location_by_id = {loc.location_id: loc for loc in instance.si_inventory.locations}

    # --- RAG contextuel + annotation (une seule fois par candidat, avant
    # le gel) — réf. tâche §3 : RagCandidateContext -> 3 requêtes par
    # famille -> CandidateEvidenceBundle -> AnnotationContext ------------
    candidate_contexts_log: dict[str, dict] = {}
    rag_queries_log: dict[str, dict] = {}
    evidence_bundles_log: dict[str, dict] = {}
    annotations_raw: list[dict] = []
    candidates_for_freeze: list[tuple[str, str, str, list]] = []

    for occurrence_id, occ_report in admissibility_report["occurrences"].items():
        occurrence = occurrence_by_id[occurrence_id]
        for entry in occ_report["C_i_h"]:
            mechanism = catalog[entry["mechanism_id"]]
            location_id = entry["location_id"]
            location = location_by_id[location_id]

            candidate_context = build_rag_candidate_context(
                occurrence=occurrence,
                mechanism=mechanism,
                location=location,
                instance=instance,
                theta_c=theta_c,
                theta_i=theta_i,
                theta_a=theta_a,
                attack_kb=attack_kb,
            )
            queries = build_rag_queries(candidate_context)
            bundle = build_candidate_evidence_bundle(
                candidate_context,
                lexical_index=lexical_index,
                semantic_index=semantic_index,
                reranker=reranker,
                retrieval_candidates=retrieval_candidates,
                final_top_k=final_top_k,
                diversity_max_per_document=diversity_max_per_document,
                alpha=hybrid_alpha,
                embedder=rag_embedder,
            )
            retrieved_evidence, evidence_by_family = to_annotation_evidence(bundle)

            candidate_contexts_log[bundle.candidate_id] = candidate_context.model_dump(mode="json")
            rag_queries_log[bundle.candidate_id] = queries
            evidence_bundles_log[bundle.candidate_id] = candidate_evidence_bundle_to_dict(bundle)

            if not retrieved_evidence:
                raise OrchestratorError(
                    f"Aucune preuve RAG recuperee pour ({occurrence_id}, {mechanism.id}, {location_id}) : "
                    "annotation impossible sans preuve (§20, §25.3)."
                )
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
            annotations = annotator.annotate(context)
            annotations_raw.extend(a.model_dump(mode="json") for a in annotations)
            candidates_for_freeze.append((occurrence_id, mechanism.id, location_id, annotations))

    _write_json(run_dir / "candidate_contexts.json", candidate_contexts_log)
    _write_json(run_dir / "rag_queries.json", rag_queries_log)
    _write_json(run_dir / "evidence_bundles.json", evidence_bundles_log)
    _write_json(run_dir / "annotations_raw.json", annotations_raw)

    # --- Validation + agrégation + gel (§12-§13) -----------------------------
    frozen_table = freeze_table(candidates_for_freeze, annotation_set_version=annotation_set_version)
    _write_json(
        run_dir / "annotations_frozen.json",
        {
            "annotation_set_version": frozen_table.annotation_set_version,
            "frozen_at": frozen_table.frozen_at.isoformat(),
            "entries": [
                {
                    "annotation_id": e.annotation_id,
                    "occurrence_id": e.occurrence_id,
                    "mechanism_id": e.mechanism_id,
                    "location_id": e.location_id,
                    "model": e.model,
                    "prompt_version": e.prompt_version,
                    "evidence_ids": list(e.evidence_ids),
                    "submetrics": e.submetrics,
                    "Realisme": e.Realisme,
                    "P_interaction": e.P_interaction,
                    "P_engagement": e.P_engagement,
                    "Effet_prog": e.Effet_prog,
                    "DE": e.DE,
                    "confidence": e.confidence,
                }
                for e in frozen_table.entries
            ],
        },
    )

    # --- Coût (§15) -----------------------------------------------------------
    cost_by_mechanism_full = compute_cost_by_mechanism(horizon, cost_inputs_by_mechanism)
    cost_by_mechanism = {mechanism_id: values["Cost"] for mechanism_id, values in cost_by_mechanism_full.items()}
    _write_json(run_dir / "costs.json", cost_by_mechanism_full)

    # --- Résolution de (P) — plus aucun appel LLM à partir d'ici (§10.3) -----
    try:
        optimization_result = solve(
            instance.graph,
            admissibility_report,
            de_by_candidate=frozen_table.de_by_candidate(),
            cost_by_mechanism=cost_by_mechanism,
            budget_total=budget_total,
            q_by_occurrence=q_by_occurrence,
            impact_by_occurrence=impact_by_occurrence,
            theta_c=theta_c,
            theta_i=theta_i,
            theta_a=theta_a,
        )
    except OptimizerError as exc:
        raise OrchestratorError(f"Echec de la resolution de (P) : {exc}") from exc

    pareto_payload = [
        {"total_cost": ec.total_cost, "terminal_risks": ec.terminal_risks, "plan": ec.configuration.to_deployment_plan()}
        for ec in optimization_result["pareto_front"]
    ]
    _write_json(run_dir / "pareto.json", pareto_payload)

    selected = optimization_result["selected"]
    deployment_plan = selected.configuration.to_deployment_plan()
    _write_json(run_dir / "deployment_plan.json", deployment_plan)

    # --- Risque avant/après pour la configuration selectionnee (reporting) --
    risks_with = propagate_risk(
        instance.graph,
        q_by_occurrence=q_by_occurrence,
        de_by_occurrence=selected.configuration.de_by_occurrence,
        impact_by_occurrence=impact_by_occurrence,
    )
    risks_without = propagate_risk(
        instance.graph, q_by_occurrence=q_by_occurrence, de_by_occurrence={}, impact_by_occurrence=impact_by_occurrence
    )
    risks_payload = {
        "terminal_ids": optimization_result["terminal_ids"],
        "avec_deception": {occ_id: values["R"] for occ_id, values in risks_with.items()},
        "sans_deception": {occ_id: values["R"] for occ_id, values in risks_without.items()},
    }
    _write_json(run_dir / "risks.json", risks_payload)

    # --- Rapport Y* (§17.6) — assemble des valeurs deja calculees ------------
    report_rows = build_deployment_report(
        deployment_plan,
        risks_before=risks_payload["sans_deception"],
        risks_after=risks_payload["avec_deception"],
        frozen_table=frozen_table,
    )
    _write_json(
        run_dir / "deployment_report.json",
        [
            {
                "occurrence_id": row.occurrence_id,
                "mechanism_id": row.mechanism_id,
                "location_id": row.location_id,
                "cost": row.cost,
                "DE": row.de,
                "risk_before": row.risk_before,
                "risk_after": row.risk_after,
                "risk_variation": row.risk_variation,
                "risk_variation_relative": row.risk_variation_relative,
                "evidence_ids": list(row.evidence_ids),
            }
            for row in report_rows
        ],
    )

    # Réf. tâche §14 : traçabilité étendue du run — RAG/LLM/catalogues,
    # jamais de secret/clé API/jeton. Chaque bloc ne contient que des
    # champs réellement fournis (aucune valeur devinée, §25.3).
    rag_manifest_extra = {}
    if rag_index_manifest is not None:
        rag_manifest_extra = {
            "corpus_version": rag_index_manifest.get("corpus_version"),
            "corpus_hash": rag_index_manifest.get("corpus_hash"),
        }
    llm_traceability = {}
    if llm_provider is not None:
        llm_traceability["provider"] = llm_provider
    if llm_model is not None:
        llm_traceability["model"] = llm_model
    if prompt_version is not None:
        llm_traceability["prompt_version"] = prompt_version
    if annotation_set_version is not None:
        llm_traceability["annotation_set_version"] = annotation_set_version

    catalog_traceability = {}
    if deception_catalog_version is not None:
        catalog_traceability["deception_catalog_version"] = deception_catalog_version
    if organization_catalog_version is not None:
        catalog_traceability["organization_catalog_version"] = organization_catalog_version
    if mapping_version is not None:
        catalog_traceability["mapping_version"] = mapping_version

    run_manifest = {
        "run_id": run_id,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "candidates_evaluated": admissibility_report["summary"]["candidate_count"],
        "candidates_admissible": admissibility_report["summary"]["admissible_count"],
        "configurations_enumerated": optimization_result["configurations_enumerated"],
        "configurations_feasible": optimization_result["configurations_feasible"],
        "pareto_front_size": len(optimization_result["pareto_front"]),
        "rag": {**input_manifest["rag"], **rag_manifest_extra},
        "llm": llm_traceability,
        "catalog": catalog_traceability,
        "files": sorted(p.name for p in run_dir.glob("*.json")),
    }
    _write_json(run_dir / "run_manifest.json", run_manifest)

    return {
        "input_manifest": input_manifest,
        "admissibility_report": admissibility_report,
        "frozen_table": frozen_table,
        "cost_by_mechanism": cost_by_mechanism_full,
        "optimization_result": optimization_result,
        "deployment_plan": deployment_plan,
        "risks": risks_payload,
        "deployment_report": report_rows,
        "run_manifest": run_manifest,
        "run_dir": run_dir,
    }
