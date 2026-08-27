"""
Réf. architecture : CLAUDE.md §11 (SP2 — annotation LLM+RAG) — exemple
exécutable réel.

Enchaîne RAG (src/rag_indexer.py / src/rag_retriever.py) -> contexte
d'annotation (§27, src/schemas.AnnotationContext) -> annotation des 11
sous-métriques (src/annotator_llm.py, repli déterministe
`rule_based_stub` — aucune API LLM réelle disponible dans cet
environnement), pour un candidat SP1 réel (T1078@DC01, D3-DUC,
auth-store).

**Ceci N'EST PAS un résultat LLM réel** : le score est produit par
`RuleBasedStubAnnotator`, un repli déterministe explicitement marqué
`model_version="rule_based_stub"` — jamais présenté comme une annotation
sémantique réelle ni comme un résultat expérimental du chapitre 5.

Exécution :
    python -m examples.annotator_llm_example

Sortie :
    docs/chapter4/outputs/llm_annotation_example.json
"""

from __future__ import annotations

import json
from pathlib import Path

from src.annotator_llm import RuleBasedStubAnnotator
from src.rag_indexer import build_index, load_d3fend_chunks, load_engage_chunks, load_literature_chunks
from src.rag_retriever import retrieve, to_deception_evidence
from src.schemas import AnnotationContext, AttackOccurrenceRef, DeceptionRef, GraphContext, NodeAttributes

STAGING_DIR = Path("data/deception/staging")
OUT_DIR = Path("docs/chapter4/outputs")


def load_json(name: str) -> dict:
    return json.loads((STAGING_DIR / name).read_text(encoding="utf-8"))


def build_index_from_staging():
    chunks = (
        load_d3fend_chunks(load_json("d3fend_deception_seed_1.5.0.json"))
        + load_engage_chunks(load_json("engage_activity_seed_1.0.json"))
        + load_literature_chunks(load_json("literature_evidence_seed_1.2.json"))
    )
    return build_index(chunks)


def main() -> None:
    index = build_index_from_staging()

    query = "decoy user credential in a credential store to deceive an adversary"
    retrieval_results = retrieve(index, query, top_k=3)
    retrieved_evidence = [to_deception_evidence(result) for result in retrieval_results]

    context = AnnotationContext(
        attack_occurrence=AttackOccurrenceRef(
            technique_id="T1078",
            asset_id="DC01",
            attributes=NodeAttributes(
                tactics=["initial-access", "persistence"],
                outcomes=[],
                q_local_success=0.75,
                impact_confidentiality=0.6,
                impact_integrity=0.2,
                impact_availability=0.1,
                critical_asset=False,
                accessible_asset=True,
            ),
        ),
        deception=DeceptionRef(id="D3-DUC", name="Decoy User Credential"),
        placement="auth-store",
        graph_context=GraphContext(parents=[], children=[], terminal_paths=[]),
        system_context={},
        retrieved_evidence=retrieved_evidence,
    )

    annotator = RuleBasedStubAnnotator()
    annotations = annotator.annotate(context)

    output = {
        "note": (
            "Annotation produite par le repli deterministe rule_based_stub "
            "(aucune API LLM reelle disponible) — PAS un resultat LLM reel "
            "ni un resultat experimental du chapitre 5."
        ),
        "candidate": {
            "occurrence_id": context.attack_occurrence.occurrence_id,
            "mechanism_id": context.deception.id,
            "location_id": context.placement,
        },
        "retrieved_evidence": [{"source": e.source, "passage": e.passage} for e in retrieved_evidence],
        "annotations": [
            {
                "metric": a.metric,
                "score": a.score,
                "confidence": a.confidence,
                "evidence": a.evidence,
                "justification": a.justification,
                "model_version": a.model_version,
                "prompt_version": a.prompt_version,
                "annotation_id": a.annotation_id,
                "annotated_at": a.annotated_at.isoformat() if a.annotated_at else None,
            }
            for a in annotations
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "llm_annotation_example.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Candidat : {output['candidate']}")
    print(f"Preuves recuperees : {[e.source for e in retrieved_evidence]}")
    print(f"11 sous-metriques (score identique, stub deterministe) : score={annotations[0].score:.3f}, confidence={annotations[0].confidence:.3f}")
    print(f"Sortie complete : {OUT_DIR / 'llm_annotation_example.json'}")


if __name__ == "__main__":
    main()
