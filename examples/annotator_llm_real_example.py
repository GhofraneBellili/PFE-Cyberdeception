"""
Réf. architecture : CLAUDE.md §11 (SP2 — annotation LLM+RAG) — exemple
exécutable réel, tâche « produire une vraie exécution LLM ».

Réf. tâche « fermer la dernière rupture » : le candidat annoté ici est
récupéré DIRECTEMENT depuis la sortie réelle de SP1
(`examples.sp1_real_example`, catalogue et mapping réels), jamais codé
manuellement. La chaîne est donc réellement :

    catalogue réel -> mapping réel -> SP1 -> candidat réel admissible
    -> retrieval RAG -> RealLlmAnnotator (ou repli documenté si aucun
    provider réel n'est disponible, jamais un stub exécuté dans cette
    chaîne).

Si `build_admissibility_report` ne produit aucun candidat admissible
(`C_{i,h}=∅`, réf. `docs/chapter4/ADMISSIBILITY_EVIDENCE_AUDIT.md`), ce
script s'arrête et le documente clairement — il n'invente jamais un
candidat pour pouvoir continuer.

**CAS C (aucun provider réel disponible) : ce script n'écrit AUCUN
fichier `llm_annotation_real.json`** — fabriquer ce fichier avec des
valeurs de repli serait présenté comme un résultat LLM réel qu'il n'est
pas (§20, anti-fabrication). Le script affiche à la place la commande
exacte à exécuter localement pour produire une vraie annotation.

Exécution :
    python -m examples.annotator_llm_real_example

Sortie (UNIQUEMENT si un provider réel a été détecté ET qu'un candidat
réellement admissible existe) :
    docs/chapter4/outputs/llm_annotation_real.json
"""

from __future__ import annotations

import json
from pathlib import Path

from src.admissibility import build_admissibility_report
from src.annotator_llm import detect_provider
from src.knowledge_deception import load_attack_deception_mapping, load_deception_catalog, to_sp1_mapping
from src.rag_indexer import build_index, load_d3fend_chunks, load_engage_chunks, load_literature_chunks
from src.rag_retriever import retrieve, to_deception_evidence
from src.schemas import AnnotationContext, AttackOccurrenceRef, DeceptionRef, GraphContext
from examples.sp1_real_example import CATALOG_PATH, MAPPING_PATH, build_example_instance

STAGING_DIR = Path("data/deception/staging")
OUT_DIR = Path("docs/chapter4/outputs")
THETA = 0.85

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


def find_first_admissible_candidate(report: dict) -> dict | None:
    """Réf. tâche : le candidat vient de la sortie RÉELLE de SP1, jamais
    codé manuellement. Retourne None si C_{i,h}=∅ partout (CAS B)."""
    for occurrence_id, occ_report in report["occurrences"].items():
        for entry in occ_report["C_i_h"]:
            return {"occurrence_id": occurrence_id, "mechanism_id": entry["mechanism_id"], "location_id": entry["location_id"]}
    return None


def main() -> None:
    kb = load_deception_catalog(CATALOG_PATH)
    attack_mapping = load_attack_deception_mapping(MAPPING_PATH)
    sp1_mapping = to_sp1_mapping(attack_mapping, kb)
    instance = build_example_instance()
    catalog = dict(kb.mechanisms_by_id)

    report = build_admissibility_report(instance, catalog, sp1_mapping, theta_c=THETA, theta_i=THETA, theta_a=THETA)
    candidate = find_first_admissible_candidate(report)

    if candidate is None:
        print("CAS B : aucun candidat reellement admissible dans la sortie de SP1")
        print("(C_i_h = vide partout, voir docs/chapter4/ADMISSIBILITY_EVIDENCE_AUDIT.md).")
        print("Ce script n'invente aucun candidat : rien a annoter.")
        return

    occurrence = next(occ for occ in instance.graph.nodes if occ.occurrence_id == candidate["occurrence_id"])
    mechanism = catalog[candidate["mechanism_id"]]
    print(f"Candidat REEL admissible recupere depuis SP1 : {candidate}")

    detection = detect_provider()
    print(f"Provider detecte : {detection.annotation_type} -- {detection.reason}")

    if detection.annotation_type != "real_llm":
        print()
        print("Aucun provider LLM reel n'est exploitable dans cet environnement.")
        print("Ce script n'ecrit PAS docs/chapter4/outputs/llm_annotation_real.json")
        print("(anti-fabrication, §20) : produire ce fichier sans vrai LLM reviendrait")
        print("a presenter un resultat LLM reel qu'il n'est pas.")
        print()
        print("Pour executer une vraie annotation localement sur CE candidat reel :")
        print()
        print("  Option A (Ollama local) :")
        print(f"    {REPRODUCTION_COMMAND_OLLAMA}")
        print()
        print("  Option B (endpoint OpenAI-compatible) :")
        print(f"    {REPRODUCTION_COMMAND_OPENAI_COMPATIBLE}")
        print()
        print("Le repli deterministe rule_based_stub reste disponible et teste ---")
        print("voir examples/annotator_llm_example.py / docs/chapter4/outputs/llm_annotation_example.json")
        print("(NE fait PAS partie de cette chaine catalogue->mapping->SP1->candidat reel).")
        return

    index = build_index_from_staging()
    query = f"{mechanism.name} {mechanism.description}"
    retrieval_results = retrieve(index, query, top_k=3)
    retrieved_evidence = [to_deception_evidence(r) for r in retrieval_results]

    context = AnnotationContext(
        attack_occurrence=AttackOccurrenceRef(
            technique_id=occurrence.technique_id, asset_id=occurrence.asset_id, attributes=occurrence.attributes
        ),
        deception=DeceptionRef(id=mechanism.id, name=mechanism.name),
        placement=candidate["location_id"],
        graph_context=GraphContext(),
        system_context={},
        retrieved_evidence=retrieved_evidence,
    )

    annotations = detection.provider.annotate(context)

    output = {
        "annotation_type": "real_llm",
        "provider": detection.details.get("provider"),
        "model": detection.details.get("model"),
        "candidate_source": "examples.sp1_real_example (catalogue et mapping reels, candidat reellement admissible)",
        "candidate": candidate,
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
