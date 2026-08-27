"""
Réf. architecture : "19. Workflow complet d'exécution" (CLAUDE.md §19) et
section « Orchestrateur » de la tâche d'implémentation du chapitre 4.

Point d'entrée unique enchaînant, sur une instance déjà validée :

    SP1 (admissibility) -> RAG (rag_indexer/rag_retriever) ->
    annotation des 11 sous-métriques (annotator_llm) ->
    validation + agrégation + gel (annotation_validator) ->
    coût (cost_engine) -> résolution de (P) (optimizer) -> propagation
    du risque de la configuration sélectionnée (risk_engine, avant/après)
    -> transformation de y* en Y* (reporter, §17.6)

Chaque étape est déjà testée indépendamment dans son propre module ; ce
module ne fait qu'assembler les appels et sérialiser les résultats
intermédiaires dans `runs/<run_id>/`, un fichier par étape (§16 de la
tâche : « Only create files actually produced »).

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
from src.cost_engine import compute_cost_by_mechanism
from src.optimizer import OptimizerError, solve
from src.rag_indexer import RagIndex, SemanticRagIndex
from src.rag_retriever import DEFAULT_HYBRID_ALPHA, retrieve, retrieve_hybrid, retrieve_semantic, to_deception_evidence
from src.reporter import build_deployment_report
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
    rag_index: RagIndex | SemanticRagIndex,
    rag_hybrid_lexical_index: RagIndex | None = None,
    rag_hybrid_alpha: float = DEFAULT_HYBRID_ALPHA,
    rag_embedder: object | None = None,
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
    top_k_evidence: int = 3,
    output_root: Path | str = Path("runs"),
) -> dict[str, Any]:
    """Réf. §19 (workflow complet) : enchaîne SP1 -> RAG -> annotation ->
    gel -> coût -> `(P)` -> reporting avant/après, et sauvegarde chaque
    étape dans `runs/<run_id>/`.

    `catalog` : catalogue de CONNAISSANCES (réf. tâche « separate
    knowledge and organization capabilities ») — décrit ce que sont les
    mécanismes. `organization_catalog` : catalogue OPÉRATIONNEL de
    l'organisation (`dict[str, OrganizationDeceptionCapability]`, réf.
    `src/organization_catalog.py::capabilities_by_id`) — seule source des
    décisions Autorise/PrerequisSatisfaits de SP1 (`src/admissibility.py`).
    SP1 est exécuté ICI, au runtime, à partir du graphe/SI COURANTS —
    jamais pré-calculé hors ligne.

    Trois moteurs RAG possibles pour `rag_index`, réf. tâche « RAG
    sémantique » / §3 « fusion hybride » :
    - `RagIndex` (lexical TF-IDF, baseline) ;
    - `SemanticRagIndex` seul (moteur principal) ;
    - `SemanticRagIndex` + `rag_hybrid_lexical_index` (fusion hybride,
      `DEFAULT_HYBRID_ALPHA` déterminé par
      `docs/chapter4/outputs/rag_semantic_evaluation.json`) — mode retenu
      pour la relecture finale car il obtient le meilleur Recall@5 mesuré.

    `rag_embedder` : embedder déjà chargé (`src.semantic_embedder.load_embedder`),
    réutilisé pour CHAQUE requête sémantique/hybride de la boucle
    d'annotation — évite de recharger un modèle `sentence-transformers`
    candidat par candidat. Ignoré si `rag_index` est un `RagIndex` lexical
    pur. `None` par défaut : `retrieve_semantic`/`retrieve_hybrid`
    rechargent alors le modèle déclaré par l'index à chaque appel (utile
    en test avec un embedder factice injecté directement dans l'index).

    Retourne un résumé en mémoire (mêmes données que les fichiers écrits)
    pour usage programmatique immédiat, en plus de la persistance sur
    disque.
    """
    run_dir = Path(output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    if rag_hybrid_lexical_index is not None and not isinstance(rag_index, SemanticRagIndex):
        raise OrchestratorError(
            "rag_hybrid_lexical_index n'est utilisable qu'avec rag_index de type SemanticRagIndex (fusion hybride)."
        )
    if rag_hybrid_lexical_index is not None:
        rag_engine_label = f"hybrid_alpha_{rag_hybrid_alpha}"
    elif isinstance(rag_index, SemanticRagIndex):
        rag_engine_label = "semantic"
    else:
        rag_engine_label = "lexical_tfidf"

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
        "rag_index_size": len(rag_index),
        "rag_engine": rag_engine_label,
    }
    _write_json(run_dir / "input_manifest.json", input_manifest)

    # --- SP1 : admissibilité -------------------------------------------------
    admissibility_report = build_admissibility_report(
        instance, catalog, organization_catalog, mapping, theta_c=theta_c, theta_i=theta_i, theta_a=theta_a
    )
    _write_json(run_dir / "candidates.json", admissibility_report)

    occurrence_by_id = {occ.occurrence_id: occ for occ in instance.graph.nodes}

    # --- RAG + annotation (une seule fois par candidat, avant le gel) -------
    retrieval_log: list[dict] = []
    annotations_raw: list[dict] = []
    candidates_for_freeze: list[tuple[str, str, str, list]] = []

    for occurrence_id, occ_report in admissibility_report["occurrences"].items():
        occurrence = occurrence_by_id[occurrence_id]
        for entry in occ_report["C_i_h"]:
            mechanism = catalog[entry["mechanism_id"]]
            location_id = entry["location_id"]
            query = f"{mechanism.name} {mechanism.description}"
            if rag_hybrid_lexical_index is not None:
                results = retrieve_hybrid(
                    rag_hybrid_lexical_index, rag_index, query, top_k=top_k_evidence, alpha=rag_hybrid_alpha, embedder=rag_embedder
                )
            elif isinstance(rag_index, SemanticRagIndex):
                results = retrieve_semantic(rag_index, query, top_k=top_k_evidence, embedder=rag_embedder)
            else:
                results = retrieve(rag_index, query, top_k=top_k_evidence)
            retrieval_log.append(
                {
                    "occurrence_id": occurrence_id,
                    "mechanism_id": mechanism.id,
                    "location_id": location_id,
                    "query": query,
                    "results": [{"chunk_id": r.chunk.chunk_id, "score": r.score} for r in results],
                }
            )
            if not results:
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
                retrieved_evidence=[to_deception_evidence(r) for r in results],
            )
            annotations = annotator.annotate(context)
            annotations_raw.extend(a.model_dump(mode="json") for a in annotations)
            candidates_for_freeze.append((occurrence_id, mechanism.id, location_id, annotations))

    _write_json(run_dir / "retrieval.json", retrieval_log)
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

    run_manifest = {
        "run_id": run_id,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "candidates_evaluated": admissibility_report["summary"]["candidate_count"],
        "candidates_admissible": admissibility_report["summary"]["admissible_count"],
        "configurations_enumerated": optimization_result["configurations_enumerated"],
        "configurations_feasible": optimization_result["configurations_feasible"],
        "pareto_front_size": len(optimization_result["pareto_front"]),
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
