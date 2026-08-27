"""
Réf. architecture : "12. Métriques déterministes du modèle" (§12.3-§12.7)
et "13. Validation et gel des annotations" (§13, §26 — module
`annotation_validator.py`).

Valide la complétude des 11 `Annotation` brutes d'un candidat
`(T_{i,h}, d, l)` (`src/annotator_llm.py`), calcule PAR CODE — jamais par
le LLM (§11.5, §12) — les agrégats déterministes `Realisme`,
`P_interaction`, `P_engagement`, `Effet_prog`, `DE` (notation verrouillée,
chapitre 4 §0), puis gèle le résultat dans une table versionnée
réutilisable par l'optimisation sans jamais rappeler le LLM (§13) :

    LLM+RAG -> Annotation -> Validation -> Table figée -> Optimisation

`FrozenAnnotationTable.de_by_candidate()` produit directement le
`de_by_candidate` attendu par `src/optimizer.build_candidates_from_admissibility`
(`dict[(occurrence_id, mechanism_id, location_id), float]`) — le pont
naturel entre SP2 gelé et `(P)`.

**Invariant central du projet (LLM hors du chemin d'exécution)** : ce
module n'importe jamais `src/risk_engine.py` ni `src/optimizer.py` — il
ne fait que valider/agréger/geler, jamais propager de risque ni résoudre
`(P)`.

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from src.schemas import Annotation

REALISM_METRICS: tuple[str, ...] = ("R_tech", "R_context", "R_perception", "R_behavior")
INTERACTION_METRICS: tuple[str, ...] = ("A_object", "A_action", "A_source")
EFFECTIVENESS_METRICS: tuple[str, ...] = ("S_stop", "S_redirect", "S_contain", "S_delay")
ELEVEN_METRICS: tuple[str, ...] = REALISM_METRICS + INTERACTION_METRICS + EFFECTIVENESS_METRICS


class AnnotationValidatorError(Exception):
    """Erreur de validation, d'agrégation ou de gel d'une annotation SP2."""


# ---------------------------------------------------------------------------
# Validation de complétude — réf. §13 (« Validation »)
# ---------------------------------------------------------------------------


def validate_candidate_annotations(annotations: list[Annotation]) -> dict[str, Annotation]:
    """Réf. §13 : vérifie que les 11 sous-métriques sont présentes, sans
    doublon, pour un même candidat `(T_{i,h}, d, l)`. Le bornage `[0,1]`
    et les champs obligatoires (justification, evidence non vides) sont
    déjà garantis par `Annotation` (Pydantic, `src/schemas.py`) — ce
    contrôle porte sur la COMPLÉTUDE de l'ensemble des 11, pas sur chaque
    champ individuellement."""
    by_metric: dict[str, Annotation] = {}
    for annotation in annotations:
        if annotation.metric in by_metric:
            raise AnnotationValidatorError(f"Sous-métrique dupliquée pour ce candidat : '{annotation.metric}'.")
        by_metric[annotation.metric] = annotation

    missing = set(ELEVEN_METRICS) - set(by_metric)
    if missing:
        raise AnnotationValidatorError(f"Sous-métriques manquantes pour ce candidat : {sorted(missing)}.")

    model_versions = {a.model_version for a in annotations}
    prompt_versions = {a.prompt_version for a in annotations}
    if len(model_versions) > 1 or len(prompt_versions) > 1:
        raise AnnotationValidatorError(
            "Les 11 sous-métriques d'un même candidat doivent partager le même "
            f"model_version/prompt_version (reçu : {model_versions} / {prompt_versions})."
        )
    return by_metric


# ---------------------------------------------------------------------------
# Agrégations déterministes — réf. §12.3 à §12.7 (jamais par le LLM, §11.5)
# ---------------------------------------------------------------------------


def _weighted_average(scores: dict[str, float], metrics: tuple[str, ...], weights: dict[str, float] | None) -> float:
    if weights is None:
        return sum(scores[m] for m in metrics) / len(metrics)
    if set(weights) != set(metrics):
        raise AnnotationValidatorError(f"Les poids fournis doivent couvrir exactement {metrics} (reçu : {sorted(weights)}).")
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise AnnotationValidatorError(f"La somme des poids doit valoir 1 (reçue : {sum(weights.values())}).")
    return sum(scores[m] * weights[m] for m in metrics)


def compute_realisme(by_metric: dict[str, Annotation], *, weights: dict[str, float] | None = None) -> float:
    """Réf. §12.3 : Realisme = moyenne(R_tech, R_context, R_perception, R_behavior)
    si aucune pondération spécifique n'est justifiée."""
    scores = {m: by_metric[m].score for m in REALISM_METRICS}
    return _weighted_average(scores, REALISM_METRICS, weights)


def compute_p_interaction(by_metric: dict[str, Annotation], *, weights: dict[str, float] | None = None) -> float:
    """Réf. §12.4 : P_interaction = moyenne(A_object, A_action, A_source)
    si aucune pondération spécifique n'est justifiée."""
    scores = {m: by_metric[m].score for m in INTERACTION_METRICS}
    return _weighted_average(scores, INTERACTION_METRICS, weights)


def compute_effet_prog(by_metric: dict[str, Annotation], *, weights: dict[str, float] | None = None) -> float:
    """Réf. §12.6 : Effet_prog = moyenne(S_stop, S_redirect, S_contain, S_delay)
    si aucune pondération spécifique n'est justifiée."""
    scores = {m: by_metric[m].score for m in EFFECTIVENESS_METRICS}
    return _weighted_average(scores, EFFECTIVENESS_METRICS, weights)


def compute_p_engagement(realisme: float, p_interaction: float) -> float:
    """Réf. §12.5 : P_engagement = Realisme x P_interaction."""
    return realisme * p_interaction


def compute_de(p_engagement: float, effet_prog: float) -> float:
    """Réf. §12.7 : DE = P_engagement x Effet_prog."""
    return p_engagement * effet_prog


# ---------------------------------------------------------------------------
# Gel de la table d'annotations — réf. §13
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FrozenAnnotation:
    """Réf. §13 : une ligne figée de la table d'annotations pour un
    candidat `(T_{i,h}, d, l)` — les 11 scores bruts + les 5 agrégats
    déterministes, prêts à être consommés par `cost_engine`/`optimizer`
    sans jamais rappeler le LLM."""

    annotation_id: str
    occurrence_id: str
    mechanism_id: str
    location_id: str
    model: str
    prompt_version: str
    evidence_ids: tuple[str, ...]
    submetrics: dict[str, float]
    Realisme: float
    P_interaction: float
    P_engagement: float
    Effet_prog: float
    DE: float
    confidence: float
    annotation_set_version: str


def _deterministic_frozen_id(
    *, occurrence_id: str, mechanism_id: str, location_id: str, model: str, prompt_version: str, annotation_set_version: str
) -> str:
    canonical = json.dumps(
        {
            "occurrence_id": occurrence_id,
            "mechanism_id": mechanism_id,
            "location_id": location_id,
            "model": model,
            "prompt_version": prompt_version,
            "annotation_set_version": annotation_set_version,
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"frozen:{digest}"


def freeze_candidate(
    *,
    occurrence_id: str,
    mechanism_id: str,
    location_id: str,
    annotations: list[Annotation],
    annotation_set_version: str,
) -> FrozenAnnotation:
    """Réf. §13 : valide, agrège (§12.3-§12.7) et gèle les 11 annotations
    d'un candidat en une `FrozenAnnotation`."""
    by_metric = validate_candidate_annotations(annotations)

    realisme = compute_realisme(by_metric)
    p_interaction = compute_p_interaction(by_metric)
    p_engagement = compute_p_engagement(realisme, p_interaction)
    effet_prog = compute_effet_prog(by_metric)
    de = compute_de(p_engagement, effet_prog)

    evidence_ids = tuple(sorted({source for a in annotations for source in a.evidence}))
    confidence = sum(a.confidence for a in annotations) / len(annotations)
    model = annotations[0].model_version or "unknown"
    prompt_version = annotations[0].prompt_version or "unknown"

    annotation_id = _deterministic_frozen_id(
        occurrence_id=occurrence_id,
        mechanism_id=mechanism_id,
        location_id=location_id,
        model=model,
        prompt_version=prompt_version,
        annotation_set_version=annotation_set_version,
    )

    return FrozenAnnotation(
        annotation_id=annotation_id,
        occurrence_id=occurrence_id,
        mechanism_id=mechanism_id,
        location_id=location_id,
        model=model,
        prompt_version=prompt_version,
        evidence_ids=evidence_ids,
        submetrics={metric: by_metric[metric].score for metric in ELEVEN_METRICS},
        Realisme=realisme,
        P_interaction=p_interaction,
        P_engagement=p_engagement,
        Effet_prog=effet_prog,
        DE=de,
        confidence=confidence,
        annotation_set_version=annotation_set_version,
    )


@dataclass(frozen=True)
class FrozenAnnotationTable:
    """Réf. §13 : table figée et versionnée — « une fois gelée, aucun
    score ne doit être recalculé arbitrairement ; aucun appel LLM n'est
    nécessaire pendant l'optimisation ». Immuable (`entries` est un tuple,
    la dataclass est `frozen=True`)."""

    entries: tuple[FrozenAnnotation, ...]
    annotation_set_version: str
    frozen_at: datetime

    def __len__(self) -> int:
        return len(self.entries)

    def get(self, occurrence_id: str, mechanism_id: str, location_id: str) -> FrozenAnnotation | None:
        for entry in self.entries:
            if (entry.occurrence_id, entry.mechanism_id, entry.location_id) == (occurrence_id, mechanism_id, location_id):
                return entry
        return None

    def de_by_candidate(self) -> dict[tuple[str, str, str], float]:
        """Réf. pont SP2 gelé -> `(P)` : produit directement le
        `de_by_candidate` attendu par
        `src.optimizer.build_candidates_from_admissibility`."""
        return {(e.occurrence_id, e.mechanism_id, e.location_id): e.DE for e in self.entries}


def freeze_table(
    candidates: list[tuple[str, str, str, list[Annotation]]],
    *,
    annotation_set_version: str,
    now: datetime | None = None,
) -> FrozenAnnotationTable:
    """Réf. §13 : gèle plusieurs candidats `(occurrence_id, mechanism_id,
    location_id, annotations)` en une `FrozenAnnotationTable` unique.
    Rejette tout doublon `(occurrence_id, mechanism_id, location_id)`
    (aucune ligne écrasée silencieusement)."""
    seen: set[tuple[str, str, str]] = set()
    entries = []
    for occurrence_id, mechanism_id, location_id, annotations in candidates:
        key = (occurrence_id, mechanism_id, location_id)
        if key in seen:
            raise AnnotationValidatorError(f"Candidat en double dans le gel de la table : {key}.")
        seen.add(key)
        entries.append(
            freeze_candidate(
                occurrence_id=occurrence_id,
                mechanism_id=mechanism_id,
                location_id=location_id,
                annotations=annotations,
                annotation_set_version=annotation_set_version,
            )
        )
    return FrozenAnnotationTable(
        entries=tuple(entries),
        annotation_set_version=annotation_set_version,
        frozen_at=now if now is not None else datetime.now(timezone.utc),
    )
