"""
Réf. architecture : CLAUDE.md §9.1 (pipeline RAG) — exemple exécutable
réel.

Ingeste les documents déjà versionnés hors ligne
(`data/deception/staging/*.json`, produits par `tools/deception_kb/*`),
construit un index réel (src/rag_indexer.py) et exécute une requête de
récupération réelle (src/rag_retriever.py), pour le chapitre 4 (Captures
4 et 5).

Exécution :
    python -m examples.rag_example

Sorties :
    docs/chapter4/outputs/rag_chunks_example.json    (échantillon de chunks réels)
    docs/chapter4/outputs/rag_retrieval_example.txt  (résultat réel de récupération)
"""

from __future__ import annotations

import json
from pathlib import Path

from src.rag_indexer import build_index, load_d3fend_chunks, load_engage_chunks, load_literature_chunks
from src.rag_retriever import retrieve

STAGING_DIR = Path("data/deception/staging")
OUT_DIR = Path("docs/chapter4/outputs")


def load_json(name: str) -> dict:
    return json.loads((STAGING_DIR / name).read_text(encoding="utf-8"))


def main() -> None:
    d3fend_chunks = load_d3fend_chunks(load_json("d3fend_deception_seed_1.5.0.json"))
    engage_chunks = load_engage_chunks(load_json("engage_activity_seed_1.0.json"))
    literature_chunks = load_literature_chunks(load_json("literature_evidence_seed_1.2.json"))
    all_chunks = d3fend_chunks + engage_chunks + literature_chunks
    index = build_index(all_chunks)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Capture 4 : échantillon réel de chunks (deux par source, premiers de la liste).
    sample = []
    for source_chunks in (d3fend_chunks, engage_chunks, literature_chunks):
        for chunk in source_chunks[:2]:
            sample.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "source_id": chunk.source_id,
                    "source_type": chunk.source_type,
                    "document_id": chunk.document_id,
                    "locator": chunk.locator,
                    "text": chunk.text,
                    "text_hash": chunk.text_hash,
                    "metadata": chunk.metadata,
                }
            )
    (OUT_DIR / "rag_chunks_example.json").write_text(json.dumps(sample, indent=2, ensure_ascii=False), encoding="utf-8")

    # Capture 5 : résultat réel de récupération.
    query = "decoy credential store to deceive an adversary on a domain controller"
    results = retrieve(index, query, top_k=5)

    lines = [
        "RAG - Resultat reel de recuperation (src/rag_retriever.py)",
        "-" * 78,
        f"Index : {len(index)} chunks ({len(d3fend_chunks)} D3FEND, {len(engage_chunks)} Engage, {len(literature_chunks)} litterature)",
        f"Requete : {query!r}",
        "-" * 78,
        f"{'Rang':<5}{'Score':<8}{'Type':<12}{'chunk_id':<28}Extrait",
    ]
    for rank, result in enumerate(results, start=1):
        snippet = result.chunk.text[:60] + ("..." if len(result.chunk.text) > 60 else "")
        lines.append(f"{rank:<5}{result.score:<8.3f}{result.chunk.source_type:<12}{result.chunk.chunk_id:<28}{snippet}")
    lines.append("-" * 78)
    text = "\n".join(lines) + "\n"
    (OUT_DIR / "rag_retrieval_example.txt").write_text(text, encoding="utf-8")

    print(text)
    print(f"Echantillon de chunks : {OUT_DIR / 'rag_chunks_example.json'}")
    print(f"Resultat de recuperation : {OUT_DIR / 'rag_retrieval_example.txt'}")


if __name__ == "__main__":
    main()
