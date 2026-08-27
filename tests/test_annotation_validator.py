"""
Réf. architecture : CLAUDE.md §12.3-§12.7 (agrégations déterministes) et
§13 (validation et gel des annotations) — contrat technique du PFE
Cyberdéception.

Tests unitaires de src/annotation_validator.py (§25.4 : pytest obligatoire).
"""

from datetime import datetime, timezone

import pytest

from src.annotation_validator import (
    ELEVEN_METRICS,
    AnnotationValidatorError,
    FrozenAnnotationTable,
    compute_de,
    compute_effet_prog,
    compute_p_engagement,
    compute_p_interaction,
    compute_realisme,
    freeze_candidate,
    freeze_table,
    validate_candidate_annotations,
)
from src.schemas import Annotation

FIXED_NOW = datetime(2026, 8, 27, tzinfo=timezone.utc)


def make_annotations(*, scores: dict[str, float] | None = None, model_version="rule_based_stub", prompt_version="v1"):
    scores = scores or {}
    annotations = []
    for metric in ELEVEN_METRICS:
        score = scores.get(metric, 0.5)
        annotations.append(
            Annotation(
                metric=metric,
                score=score,
                justification=f"justification for {metric}",
                evidence=["chunk_1", "chunk_2"],
                confidence=0.8,
                model_version=model_version,
                prompt_version=prompt_version,
                annotated_at=FIXED_NOW,
                annotation_id=f"raw:{metric}",
            )
        )
    return annotations


# ---------------------------------------------------------------------------
# A. Validation de complétude — réf. §13
# ---------------------------------------------------------------------------


class TestValidateCandidateAnnotations:
    def test_valid_eleven_metrics_pass(self):
        by_metric = validate_candidate_annotations(make_annotations())
        assert set(by_metric) == set(ELEVEN_METRICS)

    def test_missing_metric_rejected(self):
        annotations = [a for a in make_annotations() if a.metric != "S_delay"]
        with pytest.raises(AnnotationValidatorError):
            validate_candidate_annotations(annotations)

    def test_duplicate_metric_rejected(self):
        annotations = make_annotations()
        annotations.append(annotations[0])
        with pytest.raises(AnnotationValidatorError):
            validate_candidate_annotations(annotations)

    def test_inconsistent_model_version_rejected(self):
        annotations = make_annotations()
        annotations[0] = annotations[0].model_copy(update={"model_version": "other_model"})
        with pytest.raises(AnnotationValidatorError):
            validate_candidate_annotations(annotations)


# ---------------------------------------------------------------------------
# B. Agrégations déterministes — réf. §12.3 à §12.7
# ---------------------------------------------------------------------------


class TestAggregations:
    def test_realisme_default_equal_weights(self):
        scores = {"R_tech": 0.8, "R_context": 0.6, "R_perception": 0.4, "R_behavior": 0.2}
        by_metric = validate_candidate_annotations(make_annotations(scores=scores))
        assert compute_realisme(by_metric) == pytest.approx((0.8 + 0.6 + 0.4 + 0.2) / 4)

    def test_p_interaction_default_equal_weights(self):
        scores = {"A_object": 0.9, "A_action": 0.3, "A_source": 0.6}
        by_metric = validate_candidate_annotations(make_annotations(scores=scores))
        assert compute_p_interaction(by_metric) == pytest.approx((0.9 + 0.3 + 0.6) / 3)

    def test_effet_prog_default_equal_weights(self):
        scores = {"S_stop": 0.5, "S_redirect": 0.7, "S_contain": 0.1, "S_delay": 0.3}
        by_metric = validate_candidate_annotations(make_annotations(scores=scores))
        assert compute_effet_prog(by_metric) == pytest.approx((0.5 + 0.7 + 0.1 + 0.3) / 4)

    def test_p_engagement_is_product(self):
        assert compute_p_engagement(0.8, 0.5) == pytest.approx(0.4)

    def test_de_is_product(self):
        assert compute_de(0.4, 0.6) == pytest.approx(0.24)

    def test_full_chain_matches_reference_example_shape(self):
        """Réf. §0bis (ancre de validation) : la chaîne Realisme x
        P_interaction x Effet_prog doit reproduire un DE=0.429 pour les
        mêmes composantes que celles supposées par CLAUDE.md §20.4
        (P_engage=0.70, Effectiveness_prog=0.60 -> DE=0.42, proche de
        l'arrondi 0.429 utilisé par l'ancre de la tâche)."""
        realism_scores = {"R_tech": 0.70, "R_context": 0.70, "R_perception": 0.70, "R_behavior": 0.70}
        interaction_scores = {"A_object": 1.0, "A_action": 1.0, "A_source": 1.0}
        effectiveness_scores = {"S_stop": 0.60, "S_redirect": 0.60, "S_contain": 0.60, "S_delay": 0.60}
        by_metric = validate_candidate_annotations(
            make_annotations(scores={**realism_scores, **interaction_scores, **effectiveness_scores})
        )
        realisme = compute_realisme(by_metric)
        p_interaction = compute_p_interaction(by_metric)
        p_engagement = compute_p_engagement(realisme, p_interaction)
        effet_prog = compute_effet_prog(by_metric)
        de = compute_de(p_engagement, effet_prog)
        assert p_engagement == pytest.approx(0.70)
        assert de == pytest.approx(0.42)

    def test_custom_weights_must_sum_to_one(self):
        by_metric = validate_candidate_annotations(make_annotations())
        with pytest.raises(AnnotationValidatorError):
            compute_realisme(by_metric, weights={"R_tech": 0.5, "R_context": 0.5, "R_perception": 0.5, "R_behavior": 0.5})

    def test_custom_weights_applied(self):
        scores = {"R_tech": 1.0, "R_context": 0.0, "R_perception": 0.0, "R_behavior": 0.0}
        by_metric = validate_candidate_annotations(make_annotations(scores=scores))
        weights = {"R_tech": 1.0, "R_context": 0.0, "R_perception": 0.0, "R_behavior": 0.0}
        assert compute_realisme(by_metric, weights=weights) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# C. Gel d'un candidat — réf. §13
# ---------------------------------------------------------------------------


class TestFreezeCandidate:
    def test_frozen_annotation_carries_all_aggregates(self):
        frozen = freeze_candidate(
            occurrence_id="T1078@DC01",
            mechanism_id="D3-DUC",
            location_id="auth-store",
            annotations=make_annotations(),
            annotation_set_version="v1",
        )
        assert frozen.occurrence_id == "T1078@DC01"
        assert frozen.DE == pytest.approx(frozen.P_engagement * frozen.Effet_prog)
        assert frozen.P_engagement == pytest.approx(frozen.Realisme * frozen.P_interaction)
        assert set(frozen.submetrics) == set(ELEVEN_METRICS)

    def test_evidence_ids_deduplicated_and_sorted(self):
        frozen = freeze_candidate(
            occurrence_id="T1078@DC01",
            mechanism_id="D3-DUC",
            location_id="auth-store",
            annotations=make_annotations(),
            annotation_set_version="v1",
        )
        assert frozen.evidence_ids == ("chunk_1", "chunk_2")

    def test_deterministic_id_stable_for_identical_inputs(self):
        kwargs = dict(
            occurrence_id="T1078@DC01",
            mechanism_id="D3-DUC",
            location_id="auth-store",
            annotations=make_annotations(),
            annotation_set_version="v1",
        )
        frozen_1 = freeze_candidate(**kwargs)
        frozen_2 = freeze_candidate(**kwargs)
        assert frozen_1.annotation_id == frozen_2.annotation_id


# ---------------------------------------------------------------------------
# D. Table figée — réf. §13
# ---------------------------------------------------------------------------


class TestFreezeTable:
    def test_freeze_multiple_candidates(self):
        table = freeze_table(
            [
                ("T1078@DC01", "D3-DUC", "auth-store", make_annotations(scores={"S_stop": 0.9})),
                ("T1078@DC01", "D3-DF", "/tmp", make_annotations(scores={"S_stop": 0.1})),
            ],
            annotation_set_version="v1",
            now=FIXED_NOW,
        )
        assert len(table) == 2
        assert table.frozen_at == FIXED_NOW

    def test_duplicate_candidate_rejected(self):
        candidates = [
            ("T1078@DC01", "D3-DUC", "auth-store", make_annotations()),
            ("T1078@DC01", "D3-DUC", "auth-store", make_annotations()),
        ]
        with pytest.raises(AnnotationValidatorError):
            freeze_table(candidates, annotation_set_version="v1", now=FIXED_NOW)

    def test_get_returns_matching_entry(self):
        table = freeze_table(
            [("T1078@DC01", "D3-DUC", "auth-store", make_annotations())],
            annotation_set_version="v1",
            now=FIXED_NOW,
        )
        entry = table.get("T1078@DC01", "D3-DUC", "auth-store")
        assert entry is not None
        assert entry.mechanism_id == "D3-DUC"
        assert table.get("nonexistent", "x", "y") is None

    def test_de_by_candidate_bridges_to_optimizer_shape(self):
        """Réf. pont SP2 gelé -> (P) : de_by_candidate() doit produire
        exactement le format attendu par
        src.optimizer.build_candidates_from_admissibility."""
        table = freeze_table(
            [("T1078@DC01", "D3-DUC", "auth-store", make_annotations(scores={"S_stop": 0.8, "S_redirect": 0.8, "S_contain": 0.8, "S_delay": 0.8}))],
            annotation_set_version="v1",
            now=FIXED_NOW,
        )
        de_map = table.de_by_candidate()
        assert de_map == {("T1078@DC01", "D3-DUC", "auth-store"): table.entries[0].DE}

    def test_table_is_immutable(self):
        table = freeze_table(
            [("T1078@DC01", "D3-DUC", "auth-store", make_annotations())],
            annotation_set_version="v1",
            now=FIXED_NOW,
        )
        with pytest.raises(Exception):
            table.entries = ()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# E. Invariant LLM hors du chemin d'exécution
# ---------------------------------------------------------------------------


class TestLlmOutOfExecutionPath:
    def test_module_does_not_import_risk_engine_or_optimizer(self):
        import ast
        from pathlib import Path

        import src.annotation_validator as module

        source = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
        assert not (imported_modules & {"src.risk_engine", "src.optimizer"})
