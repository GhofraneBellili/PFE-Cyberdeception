"""
Réf. tâche « campagne d'évaluation réelle RAG/LLM/système » §4 : évaluation
RÉELLE de l'annotation LLM sur le jeu fixe de candidats admissibles
(`tools/chapter4_evaluation/llm_fixed_candidates.py`) :

    §4.1 conformité (sortie LLM brute conforme, sans les relances internes
         de `RealLlmAnnotator.annotate()`) ;
    §4.2 ancrage documentaire (tout evidence_id cité correspond réellement
         à un passage transmis dans le contexte) ;
    §4.3 stabilité température=0 (K>=5 rejeux de l'annotation, moyenne et
         écart-type de DE et des 11 sous-métriques par candidat).

Si aucun provider LLM réel n'est exploitable dans l'environnement courant
(`src.annotator_llm.detect_provider`), ce script s'ARRÊTE avec un message
clair et n'écrit AUCUN fichier `llm_*.json` présenté comme un résultat LLM
réel (réf. tâche §1/§4 — jamais de résultat fabriqué, jamais
RuleBasedStubAnnotator présenté comme un résultat LLM).

Aucune clé API n'est jamais affichée, journalisée ni écrite dans un fichier
de sortie — uniquement les scores/justifications/evidence_ids retournés par
le provider et les métadonnées non sensibles (`provider`, `model`).

Exécution :
    python -m tools.chapter4_evaluation.llm_evaluation
"""

from __future__ import annotations

import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from src.annotation_validator import ELEVEN_METRICS, freeze_candidate
from src.annotator_llm import (
    LlmOutputValidationError,
    LlmProviderError,
    RealLlmAnnotator,
    _build_prompt,
    _parse_and_validate_llm_output,
    detect_provider,
)
from tools.chapter4_evaluation.llm_fixed_candidates import FixedCandidatesError, build_fixed_annotation_candidates

OUT_DIR = Path("docs/chapter4/evaluation/outputs")
K_REPLAYS = 5


class LlmEvaluationBlocked(Exception):
    """Levée quand aucun provider LLM réel n'est exploitable — jamais
    contournée par un repli déterministe (réf. tâche §1/§4)."""


def _attempt_raw_annotation(annotator: RealLlmAnnotator, context):
    """Un SEUL appel réseau brut, SANS les relances internes de
    `RealLlmAnnotator.annotate()` — mesure la conformité d'une sortie LLM
    individuelle, pas le taux de succès après plusieurs tentatives."""
    prompt = _build_prompt(context)
    start = time.monotonic()
    try:
        raw_content = annotator._call_raw(prompt)
    except LlmProviderError as exc:
        return {"ok": False, "annotations": None, "error": f"provider_error: {exc}", "raw_content": None, "elapsed_seconds": time.monotonic() - start}
    elapsed = time.monotonic() - start
    try:
        annotations = _parse_and_validate_llm_output(
            raw_content,
            context=context,
            model=annotator.config.model,
            prompt_version=annotator.config.prompt_version,
            timestamp=datetime.now(timezone.utc),
        )
    except LlmOutputValidationError as exc:
        return {"ok": False, "annotations": None, "error": f"validation_error: {exc}", "raw_content": raw_content, "elapsed_seconds": elapsed}
    return {"ok": True, "annotations": annotations, "error": None, "raw_content": raw_content, "elapsed_seconds": elapsed}


def _extract_raw_evidence_citations(raw_content: str | None) -> list[str]:
    """Réf. §4.2 : extrait TOUS les evidence_ids cités dans une sortie LLM
    brute, indulgent sur le format (utile même si la sortie échoue par
    ailleurs la validation stricte pour une autre raison) — retourne une
    liste vide si le contenu n'est pas exploitable, jamais une erreur."""
    if not raw_content:
        return []
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, dict):
        return []
    raw_annotations = parsed.get("annotations")
    if not isinstance(raw_annotations, list):
        return []
    citations = []
    for item in raw_annotations:
        if isinstance(item, dict) and isinstance(item.get("evidence_ids"), list):
            citations.extend(e for e in item["evidence_ids"] if isinstance(e, str))
    return citations


def run_conformity_and_grounding(annotator: RealLlmAnnotator, candidates) -> tuple[dict, dict]:
    print(f"§4.1/§4.2 : conformite + ancrage documentaire sur {len(candidates)} candidats (1 appel brut chacun)...")
    per_candidate = []
    all_citations: list[tuple[str, bool]] = []  # (evidence_id, valide)

    for candidate in candidates:
        valid_ids = {item.source for item in candidate.context.retrieved_evidence}
        attempt = _attempt_raw_annotation(annotator, candidate.context)
        citations = _extract_raw_evidence_citations(attempt["raw_content"])
        for cid in citations:
            all_citations.append((cid, cid in valid_ids))

        per_candidate.append(
            {
                "occurrence_id": candidate.occurrence_id,
                "mechanism_id": candidate.mechanism_id,
                "location_id": candidate.location_id,
                "conforme": attempt["ok"],
                "error": attempt["error"],
                "elapsed_seconds": attempt["elapsed_seconds"],
                "cited_evidence_count": len(citations),
                "cited_evidence_valid_count": sum(1 for _, ok in [(c, c in valid_ids) for c in citations] if ok),
            }
        )

    conforme_count = sum(1 for p in per_candidate if p["conforme"])
    conformity = {
        "candidate_count": len(candidates),
        "conforme_count": conforme_count,
        "conformity_rate": conforme_count / len(candidates) if candidates else 0.0,
        "failures": [p for p in per_candidate if not p["conforme"]],
        "per_candidate": per_candidate,
    }

    total_citations = len(all_citations)
    valid_citations = sum(1 for _, ok in all_citations if ok)
    invalid_ids = sorted({cid for cid, ok in all_citations if not ok})
    grounding = {
        "total_evidence_citations": total_citations,
        "valid_evidence_citations": valid_citations,
        "grounding_rate": (valid_citations / total_citations) if total_citations else None,
        "invalid_evidence_ids": invalid_ids,
    }
    return conformity, grounding


def run_stability(annotator: RealLlmAnnotator, candidates, *, k: int = K_REPLAYS) -> dict:
    print(f"§4.3 : stabilite temperature=0 -- {k} rejeux x {len(candidates)} candidats "
          f"({k * len(candidates)} appels reels, appel direct annotate(), cache contourne)...")
    per_candidate = []
    for candidate in candidates:
        replays = []
        for replay_index in range(k):
            annotations = annotator.annotate(candidate.context)
            frozen = freeze_candidate(
                occurrence_id=candidate.occurrence_id,
                mechanism_id=candidate.mechanism_id,
                location_id=candidate.location_id,
                annotations=annotations,
                annotation_set_version=f"stability-replay-{replay_index}",
            )
            replays.append({"replay_index": replay_index, "DE": frozen.DE, "submetrics": dict(frozen.submetrics)})

        de_values = [r["DE"] for r in replays]
        submetric_stats = {}
        for metric in ELEVEN_METRICS:
            values = [r["submetrics"][metric] for r in replays]
            submetric_stats[metric] = {
                "mean": statistics.mean(values),
                "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
                "values": values,
            }
        per_candidate.append(
            {
                "occurrence_id": candidate.occurrence_id,
                "mechanism_id": candidate.mechanism_id,
                "location_id": candidate.location_id,
                "replay_count": k,
                "DE_mean": statistics.mean(de_values),
                "DE_stdev": statistics.stdev(de_values) if len(de_values) > 1 else 0.0,
                "DE_values": de_values,
                "submetrics": submetric_stats,
            }
        )

    mean_de_stdev = statistics.mean(p["DE_stdev"] for p in per_candidate) if per_candidate else None
    return {
        "replay_count_per_candidate": k,
        "candidate_count": len(candidates),
        "mean_DE_stdev": mean_de_stdev,
        "per_candidate": per_candidate,
    }


def main() -> dict:
    detection = detect_provider()
    if detection.annotation_type != "real_llm":
        message = (
            f"BLOQUE (reference tache section 4) : aucun provider LLM reel exploitable "
            f"(raison : {detection.reason}). Conformement a la consigne, aucun fichier "
            f"llm_conformity.json / llm_evidence_grounding.json / llm_stability_temp0.json "
            f"n'est produit -- aucun resultat LLM n'est fabrique."
        )
        print(message)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "llm_evaluation_blocked.txt").write_text(message + "\n", encoding="utf-8")
        return {"blocked": True, "reason": detection.reason}

    annotator: RealLlmAnnotator = detection.provider
    print(f"Provider LLM reel detecte : {annotator.config.provider} / {annotator.config.model} "
          f"(temperature={annotator.config.temperature}).")

    try:
        candidates, candidates_metadata, _reusable = build_fixed_annotation_candidates()
    except FixedCandidatesError as exc:
        message = f"BLOQUE (reference tache section 4) : construction du jeu fixe de candidats impossible : {exc}"
        print(message)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "llm_evaluation_blocked.txt").write_text(message + "\n", encoding="utf-8")
        return {"blocked": True, "reason": str(exc)}

    print(f"Jeu fixe de candidats : {candidates_metadata['candidate_count']} candidats admissibles reels "
          f"({candidates_metadata['candidate_ids']}).")

    conformity, grounding = run_conformity_and_grounding(annotator, candidates)
    stability = run_stability(annotator, candidates, k=K_REPLAYS)

    common_meta = {
        "provider": annotator.config.provider,
        "model": annotator.config.model,
        "temperature": annotator.config.temperature,
        "prompt_version": annotator.config.prompt_version,
        "candidates": candidates_metadata,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    conformity_out = {**common_meta, **conformity}
    grounding_out = {**common_meta, **grounding}
    stability_out = {**common_meta, **stability}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "llm_conformity.json").write_text(json.dumps(conformity_out, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "llm_evidence_grounding.json").write_text(json.dumps(grounding_out, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "llm_stability_temp0.json").write_text(json.dumps(stability_out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Conformite : {conformity['conforme_count']}/{conformity['candidate_count']} "
          f"({conformity['conformity_rate']:.1%})")
    print(f"Ancrage : {grounding['valid_evidence_citations']}/{grounding['total_evidence_citations']} "
          f"({grounding['grounding_rate']})")
    print(f"Stabilite -- ecart-type moyen de DE : {stability['mean_DE_stdev']}")
    print(f"Ecrit : {OUT_DIR / 'llm_conformity.json'}, llm_evidence_grounding.json, llm_stability_temp0.json")
    return {"blocked": False, "conformity": conformity, "grounding": grounding, "stability": stability}


if __name__ == "__main__":
    main()
