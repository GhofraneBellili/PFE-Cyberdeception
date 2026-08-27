"""
Réf. architecture : CLAUDE.md §11 (SP2 — annotation LLM+RAG) — réf. tâche
Phase 20 « test d'intégration optionnel pour un vrai LLM ».

Test d'INTÉGRATION optionnel : ne s'exécute que si un provider LLM réel
est réellement configuré et joignable dans l'environnement (`LLM_PROVIDER`
+ variables associées, réf. `src/llm_provider.py::config_from_env`).
Toujours ignoré (`skip`) sinon — jamais un échec silencieux, jamais un
appel réseau implicite pendant la CI normale.

Exécution explicite :
    pytest -m real_llm -v

La suite normale (`pytest`) ignore ce fichier par défaut (`-m` non
demandé n'exclut pas le test, mais son corps se `skip` lui-même dès que
`detect_provider()` ne retourne pas `annotation_type == "real_llm"` — donc
aucune dépendance réseau n'est introduite dans la CI standard).
"""

from __future__ import annotations

import pytest

from src.annotator_llm import detect_provider
from src.rag_indexer import build_index, load_d3fend_chunks, load_engage_chunks, load_literature_chunks
from src.rag_retriever import retrieve, to_deception_evidence
from src.schemas import (
    AnnotationContext,
    AnnotationMetricName,
    AttackOccurrenceRef,
    DeceptionRef,
    GraphContext,
    NodeAttributes,
)

STAGING_DIR = __import__("pathlib").Path("data/deception/staging")

ALL_ELEVEN_METRICS: set[AnnotationMetricName] = {
    "R_tech",
    "R_context",
    "R_perception",
    "R_behavior",
    "A_object",
    "A_action",
    "A_source",
    "S_stop",
    "S_redirect",
    "S_contain",
    "S_delay",
}

FORBIDDEN_DERIVED_KEYWORDS = (
    "p_engagement",
    "p_engage",
    "effect_prog",
    "effectiveness_prog",
    "deceptioneffect",
    "de_score",
    "realism_score",
    "interaction_likelihood",
)


def _load_json(name: str) -> dict:
    import json

    return json.loads((STAGING_DIR / name).read_text(encoding="utf-8"))


def _real_index():
    chunks = (
        load_d3fend_chunks(_load_json("d3fend_deception_seed_1.5.0.json"))
        + load_engage_chunks(_load_json("engage_activity_seed_1.0.json"))
        + load_literature_chunks(_load_json("literature_evidence_seed_1.2.json"))
    )
    return build_index(chunks)


@pytest.mark.real_llm
class TestRealLlmIntegration:
    def test_real_provider_produces_exactly_eleven_valid_metrics(self):
        detection = detect_provider()
        if detection.annotation_type != "real_llm":
            pytest.skip(f"Aucun provider LLM reel configure/joignable : {detection.reason}")

        index = _real_index()
        query = "decoy user credential to deceive an adversary attempting credential access"
        results = retrieve(index, query, top_k=3)
        assert results, "Le RAG lexical reel doit retourner au moins une preuve pour cette requete."
        retrieved_evidence = [to_deception_evidence(r) for r in results]

        context = AnnotationContext(
            attack_occurrence=AttackOccurrenceRef(
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
            ),
            deception=DeceptionRef(id="D3-DUC", name="Decoy User Credential"),
            placement="auth-store",
            graph_context=GraphContext(),
            system_context={},
            retrieved_evidence=retrieved_evidence,
        )

        annotations = detection.provider.annotate(context)

        metrics_seen = {a.metric for a in annotations}
        assert metrics_seen == ALL_ELEVEN_METRICS, f"11 sous-metriques attendues exactement, obtenu : {sorted(metrics_seen)}"
        assert len(annotations) == 11

        for annotation in annotations:
            assert 0.0 <= annotation.score <= 1.0, f"{annotation.metric} score hors bornes : {annotation.score}"
            assert 0.0 <= annotation.confidence <= 1.0, f"{annotation.metric} confidence hors bornes : {annotation.confidence}"
            assert annotation.evidence, f"{annotation.metric} sans evidence_ids"
            for evidence_id in annotation.evidence:
                assert isinstance(evidence_id, str) and evidence_id.strip()
            assert annotation.justification.strip()
            assert annotation.model_version
            assert annotation.prompt_version

    def test_real_provider_never_returns_a_derived_formula_field(self):
        """Réf. §11.5 : le LLM ne calcule jamais Realism/InteractionLikelihood/
        P_engagement/Effectiveness_prog/DE — vérifié ici en s'assurant
        qu'aucun nom de métrique retourné ne correspond à une formule
        dérivée (le schema Annotation limite déjà `metric` aux 11 valeurs
        de AnnotationMetricName, donc structurellement impossible ; ce
        test documente explicitement l'invariant plutôt que de le
        supposer implicite)."""
        detection = detect_provider()
        if detection.annotation_type != "real_llm":
            pytest.skip(f"Aucun provider LLM reel configure/joignable : {detection.reason}")

        index = _real_index()
        results = retrieve(index, "decoy network resource honeypot for adversary lateral movement", top_k=3)
        retrieved_evidence = [to_deception_evidence(r) for r in results]

        context = AnnotationContext(
            attack_occurrence=AttackOccurrenceRef(
                technique_id="T1039",
                asset_id="FS01",
                attributes=NodeAttributes(
                    tactics=["collection"],
                    outcomes=[],
                    q_local_success=0.5,
                    impact_confidentiality=0.4,
                    impact_integrity=0.1,
                    impact_availability=0.1,
                    critical_asset=False,
                    accessible_asset=True,
                ),
            ),
            deception=DeceptionRef(id="D3-DNR", name="Decoy Network Resource"),
            placement="shared-drive",
            graph_context=GraphContext(),
            system_context={},
            retrieved_evidence=retrieved_evidence,
        )

        annotations = detection.provider.annotate(context)
        for annotation in annotations:
            assert annotation.metric in ALL_ELEVEN_METRICS
            lowered_justification = annotation.justification.lower()
            for forbidden in FORBIDDEN_DERIVED_KEYWORDS:
                assert forbidden not in lowered_justification.replace(" ", "_"), (
                    f"La justification de {annotation.metric} semble contenir une formule derivee "
                    f"interdite ('{forbidden}') : le LLM ne doit jamais calculer P_engagement/DE/etc."
                )
