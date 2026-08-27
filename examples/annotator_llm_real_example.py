"""
Réf. architecture : CLAUDE.md §11 (SP2 — annotation LLM+RAG) — exemple
exécutable réel, tâche « produire une vraie exécution LLM ».

Détecte si un véritable provider LLM est exploitable dans cet
environnement (`src.annotator_llm.detect_provider`, variables
d'environnement `LLM_PROVIDER`/`LLM_MODEL`/`LLM_BASE_URL`/`LLM_API_KEY`)
et, si oui, exécute une annotation réelle sur un candidat SP1 réel avec
des preuves RAG réelles.

**CAS C (aucun provider réel disponible) : ce script n'écrit AUCUN
fichier `llm_annotation_real.json`** — fabriquer ce fichier avec des
valeurs de repli serait présenté comme un résultat LLM réel qu'il n'est
pas (§20, anti-fabrication). Le script affiche à la place la commande
exacte à exécuter localement pour produire une vraie annotation.

Exécution :
    python -m examples.annotator_llm_real_example

Sortie (UNIQUEMENT si un provider réel a été détecté et exécuté avec
succès) :
    docs/chapter4/outputs/llm_annotation_real.json
"""

from __future__ import annotations

import json
from pathlib import Path

from src.annotator_llm import detect_provider
from src.rag_indexer import build_index, load_d3fend_chunks, load_engage_chunks, load_literature_chunks
from src.rag_retriever import retrieve, to_deception_evidence
from src.schemas import AnnotationContext, AttackOccurrenceRef, DeceptionRef, GraphContext, NodeAttributes

STAGING_DIR = Path("data/deception/staging")
OUT_DIR = Path("docs/chapter4/outputs")

REPRODUCTION_COMMAND_OLLAMA = (
    "LLM_PROVIDER=ollama LLM_MODEL=<votre_modele_local> "
    "python -m examples.annotator_llm_real_example"
)
REPRODUCTION_COMMAND_OPENAI_COMPATIBLE = (
    "LLM_PROVIDER=openai_compatible LLM_MODEL=<modele> "
    "LLM_BASE_URL=<https://.../v1> LLM_API_KEY=<votre_cle> "
    "python -m examples.annotator_llm_real_example"
)


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
    detection = detect_provider()
    print(f"Provider detecte : {detection.annotation_type} -- {detection.reason}")

    if detection.annotation_type != "real_llm":
        print()
        print("Aucun provider LLM reel n'est exploitable dans cet environnement.")
        print("Ce script n'ecrit PAS docs/chapter4/outputs/llm_annotation_real.json")
        print("(anti-fabrication, §20) : produire ce fichier sans vrai LLM reviendrait")
        print("a presenter un resultat LLM reel qu'il n'est pas.")
        print()
        print("Pour executer une vraie annotation localement :")
        print()
        print("  Option A (Ollama local) :")
        print(f"    {REPRODUCTION_COMMAND_OLLAMA}")
        print()
        print("  Option B (endpoint OpenAI-compatible) :")
        print(f"    {REPRODUCTION_COMMAND_OPENAI_COMPATIBLE}")
        print()
        print("Le repli deterministe rule_based_stub reste disponible et teste ---")
        print("voir examples/annotator_llm_example.py / docs/chapter4/outputs/llm_annotation_example.json.")
        return

    index = build_index_from_staging()
    query = "decoy user credential in a credential store to deceive an adversary"
    retrieval_results = retrieve(index, query, top_k=3)
    retrieved_evidence = [to_deception_evidence(r) for r in retrieval_results]

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
        graph_context=GraphContext(),
        system_context={},
        retrieved_evidence=retrieved_evidence,
    )

    annotations = detection.provider.annotate(context)

    output = {
        "annotation_type": "real_llm",
        "provider": detection.details.get("provider"),
        "model": detection.details.get("model"),
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
    (OUT_DIR / "llm_annotation_real.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Annotation LLM REELLE produite avec le modele '{detection.details.get('model')}'.")
    print(f"Sortie : {OUT_DIR / 'llm_annotation_real.json'}")


if __name__ == "__main__":
    main()
