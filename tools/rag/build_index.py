"""
Réf. tâche « maturation technique finale du chapitre 4 », §10 « Builder
offline explicite ».

Point d'entrée OFFLINE unique du RAG contextuel de SP2 :

    ATT&CK + D3FEND + Engage + littérature (staging déjà versionné)
    -> chunking (déjà fait, réf. tools/attack_kb/, tools/deception_kb/)
    -> src/rag_indexer.py::load_*_chunks
    -> embeddings sémantiques (src/semantic_embedder.py)
    -> index vectoriel FAISS (src/vector_index.py)
    -> persistance (src/rag_index_store.py::save_rag_index)

Ce script ne fait AUCUN calcul de risque, AUCUNE sélection de mécanisme,
AUCUN appel LLM — uniquement la préparation OFFLINE du corpus RAG. La
partie ONLINE (`src/rag_index_store.py::load_rag_index`) recharge cet
index sans jamais recalculer les embeddings.

Exécution :
    python -m tools.rag.build_index --out-dir data/rag/index --corpus-version <version>

Sortie : `<out-dir>/{chunks.json, embeddings.npy, faiss.index?, manifest.json}`.
`data/rag/index/` reste volontairement GITIGNORÉ (artefact binaire
régénérable, réf. tâche §33) — seul `manifest.json` est recopié en preuve
versionnée du chapitre 4 (`docs/chapter4/outputs/rag_index_manifest.json`,
réf. `--manifest-proof-out`).

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

import json
from pathlib import Path

from src.rag_index_store import save_rag_index
from src.rag_indexer import Chunk, build_semantic_index, load_attack_chunks, load_d3fend_chunks, load_engage_chunks, load_literature_chunks

# Réf. même convention que examples/rag_sp2_context_example.py : versions
# de staging pinnées explicitement, mises à jour quand le staging est
# régénéré — pas des identifiants métier codés en dur (§12 de la tâche
# précédente), de simples pointeurs de version de fichier déjà versionné.
DEFAULT_ATTACK_STAGING_DIR = Path("data/attack/staging")
DEFAULT_D3FEND_SEED = Path("data/deception/staging/d3fend_deception_seed_1.5.0.json")
DEFAULT_ENGAGE_SEED = Path("data/deception/staging/engage_activity_seed_1.0.json")
DEFAULT_LITERATURE_SEED = Path("data/deception/staging/literature_evidence_seed_1.2.json")


class BuildRagIndexError(Exception):
    """Erreur de construction OFFLINE de l'index RAG persisté."""


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_full_corpus_chunks(
    *,
    attack_staging_dir: Path = DEFAULT_ATTACK_STAGING_DIR,
    d3fend_seed_path: Path = DEFAULT_D3FEND_SEED,
    engage_seed_path: Path = DEFAULT_ENGAGE_SEED,
    literature_seed_path: Path = DEFAULT_LITERATURE_SEED,
) -> list[Chunk]:
    """Réf. §10/§15 : assemble le corpus RAG complet à partir des QUATRE
    sources déjà versionnées — ATT&CK (`tools/attack_kb/`), D3FEND/Engage/
    littérature (`tools/deception_kb/`)."""
    # Réf. durcissement : le glob "attack_rag_seed_*.json" capte AUSSI le
    # rapport d'extraction "attack_rag_seed_report_<version>.json" (même
    # préfixe) — exclu explicitement, sous peine de charger silencieusement
    # 0 chunk ATT&CK (schéma "report" sans clé "techniques",
    # load_attack_chunks retournerait alors [] sans lever d'erreur).
    attack_seed_files = sorted(
        f for f in attack_staging_dir.glob("attack_rag_seed_*.json") if "_report_" not in f.name
    )
    if not attack_seed_files:
        raise BuildRagIndexError(
            f"Aucun staging ATT&CK trouvé dans '{attack_staging_dir}' — générer d'abord via "
            "'python -m tools.attack_kb.attack_seed_builder'."
        )

    attack_chunks = load_attack_chunks(_load_json(attack_seed_files[-1]))
    if not attack_chunks:
        raise BuildRagIndexError(
            f"'{attack_seed_files[-1]}' n'a produit AUCUN chunk ATT&CK — staging vide ou schéma inattendu, "
            "jamais un corpus silencieusement incomplet."
        )

    return (
        attack_chunks
        + load_d3fend_chunks(_load_json(d3fend_seed_path))
        + load_engage_chunks(_load_json(engage_seed_path))
        + load_literature_chunks(_load_json(literature_seed_path))
    )


def _run_cli(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Construit et persiste l'index RAG sémantique OFFLINE (ATT&CK+D3FEND+Engage+littérature)."
    )
    parser.add_argument("--out-dir", default="data/rag/index", help="Répertoire de sortie de l'index persisté.")
    parser.add_argument(
        "--corpus-version",
        required=True,
        help="Version du corpus indexé (ex. 'attack-19.2+deception-catalog-2.0') — jamais devinée.",
    )
    parser.add_argument("--embedding-model", default=None, help="Modèle sentence-transformers (défaut : RAG_EMBEDDING_MODEL / BAAI/bge-small-en-v1.5).")
    parser.add_argument(
        "--manifest-proof-out",
        default=None,
        help="Chemin optionnel où recopier le manifest comme preuve versionnée pour le chapitre 4.",
    )
    args = parser.parse_args(argv)

    from src.semantic_embedder import load_embedder

    chunks = build_full_corpus_chunks()
    embedder = load_embedder(args.embedding_model) if args.embedding_model else load_embedder()
    index = build_semantic_index(chunks, embedder=embedder)
    manifest = save_rag_index(index, args.out_dir, corpus_version=args.corpus_version)

    print(f"Index RAG persisté : {args.out_dir}")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))

    if args.manifest_proof_out:
        proof_path = Path(args.manifest_proof_out)
        proof_path.parent.mkdir(parents=True, exist_ok=True)
        proof_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Preuve manifest recopiée : {proof_path}")


if __name__ == "__main__":
    _run_cli()
