"""
Réf. tâche « maturation technique finale du chapitre 4 », §5-§9 « Rendre
le RAG offline réellement persistant ».

Sauvegarde et rechargement d'un `SemanticRagIndex`
(`src/rag_indexer.py`) sur disque, pour que le runtime ONLINE puisse
faire `load index -> retrieve` SANS recalculer les embeddings
documentaires à chaque lancement — l'index reste un artefact produit
UNE FOIS par la phase OFFLINE (`tools/rag/build_index.py`).

Structure d'un index persisté (`out_dir`, réf. tâche §5) :

```
<out_dir>/
    chunks.json       # chunks tracés (chunk_id, source_type, text, ...)
    embeddings.npy     # vecteurs (n, d) float32, TOUJOURS sauvegardés
                        # (portable, backend-agnostique)
    faiss.index        # sérialisation FAISS native, SEULEMENT si
                        # l'index a été construit avec le backend faiss
                        # (chemin rapide au chargement, réf. §8)
    manifest.json       # métadonnées de traçabilité (§6)
```

**Compatibilité à l'ouverture** (§9) : `load_rag_index` vérifie
`schema_version`, `chunk_count`, la dimension des embeddings et,
lorsque `current_chunks` est fourni par l'appelant (corpus réellement
rechargé depuis le staging), le hash du corpus (`compute_corpus_hash`,
§7). Toute incompatibilité lève `RagIndexStoreError` — **jamais** un
repli silencieux vers un index périmé (§9, §23).

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from src.rag_indexer import Chunk, SemanticRagIndex, SourceType
from src.vector_index import FAISS_AVAILABLE, build_vector_index

if FAISS_AVAILABLE:
    import faiss

INDEX_SCHEMA_VERSION = "1.0"

_CHUNKS_FILENAME = "chunks.json"
_EMBEDDINGS_FILENAME = "embeddings.npy"
_FAISS_FILENAME = "faiss.index"
_MANIFEST_FILENAME = "manifest.json"


class RagIndexStoreError(Exception):
    """Erreur de sauvegarde, de chargement ou de compatibilité de l'index
    RAG persisté."""


# ---------------------------------------------------------------------------
# Hash déterministe du corpus (§7)
# ---------------------------------------------------------------------------


def compute_corpus_hash(chunks: tuple[Chunk, ...] | list[Chunk]) -> str:
    """Réf. §7 : hash déterministe du corpus RÉELLEMENT indexé, dépendant
    de `chunk_id`, `text_hash` (déjà l'empreinte du texte du chunk,
    réf. `src/rag_indexer.py::_text_hash`) et de `metadata` — sur un
    ORDRE NORMALISÉ (trié par `chunk_id`), pour que le hash soit
    indépendant de l'ordre d'itération réel du corpus. But : détecter
    qu'un index persisté ne correspond plus au corpus actuellement
    reconstruit depuis le staging (§9)."""
    ordered = sorted(chunks, key=lambda chunk: chunk.chunk_id)
    canonical = [
        {"chunk_id": chunk.chunk_id, "text_hash": chunk.text_hash, "metadata": chunk.metadata}
        for chunk in ordered
    ]
    payload = json.dumps(canonical, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _chunk_count_by_source(chunks: tuple[Chunk, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for chunk in chunks:
        counts[chunk.source_type] = counts.get(chunk.source_type, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Sauvegarde (§5, §6, §8)
# ---------------------------------------------------------------------------


def save_rag_index(index: SemanticRagIndex, out_dir: str | Path, *, corpus_version: str) -> dict:
    """Réf. §5/§6/§8 : persiste `index` dans `out_dir` (créé si absent) et
    retourne le manifest écrit. `corpus_version` est fourni explicitement
    par l'appelant (OFFLINE builder) — jamais devinée."""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    chunks_payload = [asdict(chunk) for chunk in index.chunks]
    (out_path / _CHUNKS_FILENAME).write_text(
        json.dumps(chunks_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    vectors = np.ascontiguousarray(index.vectors, dtype=np.float32)
    np.save(out_path / _EMBEDDINGS_FILENAME, vectors)

    faiss_path = out_path / _FAISS_FILENAME
    if index.backend == "faiss" and FAISS_AVAILABLE:
        faiss.write_index(index.vector_index, str(faiss_path))
    elif faiss_path.exists():
        # Réf. §9 : un ancien faiss.index d'une sauvegarde précédente ne
        # doit jamais rester silencieusement à côté d'un embeddings.npy
        # désormais backend="numpy" (incohérence au rechargement).
        faiss_path.unlink()

    manifest = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "corpus_version": corpus_version,
        "corpus_hash": compute_corpus_hash(index.chunks),
        "chunk_count": len(index.chunks),
        "chunk_count_by_source": _chunk_count_by_source(index.chunks),
        "embedding_model": index.embedding_model,
        "embedding_dimension": index.dimension,
        "vector_backend": index.backend,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (out_path / _MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest


# ---------------------------------------------------------------------------
# Chargement + vérification de compatibilité (§8, §9)
# ---------------------------------------------------------------------------


def read_rag_index_manifest(index_dir: str | Path) -> dict:
    """Réf. §6 : lit uniquement `manifest.json`, sans charger les
    embeddings — utile pour une inspection/traçabilité légère (run
    manifest, §14)."""
    manifest_path = Path(index_dir) / _MANIFEST_FILENAME
    if not manifest_path.exists():
        raise RagIndexStoreError(f"Aucun index RAG persisté trouvé dans '{index_dir}' (manifest.json absent).")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def load_rag_index(
    index_dir: str | Path,
    *,
    expected_embedding_model: str | None = None,
    current_chunks: tuple[Chunk, ...] | list[Chunk] | None = None,
) -> tuple[SemanticRagIndex, dict]:
    """Réf. §8/§9 : recharge un index persisté SANS ré-encoder aucun
    texte — retourne `(index, manifest)`.

    Vérifications de compatibilité (§9), chacune levant explicitement
    `RagIndexStoreError` en cas d'échec (jamais un repli silencieux) :
    - `schema_version` du manifest ;
    - `chunk_count` (cohérence manifest <-> `chunks.json` réellement lu) ;
    - dimension des embeddings (cohérence manifest <-> `embeddings.npy`) ;
    - `expected_embedding_model`, si fourni par l'appelant ;
    - hash du corpus, si `current_chunks` est fourni par l'appelant (le
      corpus réel reconstruit depuis le staging courant) — détecte un
      index périmé par rapport au corpus actuel (§7/§9).
    """
    index_path = Path(index_dir)
    manifest = read_rag_index_manifest(index_path)

    if manifest.get("schema_version") != INDEX_SCHEMA_VERSION:
        raise RagIndexStoreError(
            f"schema_version incompatible : index='{manifest.get('schema_version')}', "
            f"attendu='{INDEX_SCHEMA_VERSION}'."
        )

    chunks_path = index_path / _CHUNKS_FILENAME
    if not chunks_path.exists():
        raise RagIndexStoreError(f"Fichier '{_CHUNKS_FILENAME}' absent de l'index persisté '{index_path}'.")
    chunks_raw = json.loads(chunks_path.read_text(encoding="utf-8"))
    chunks = tuple(
        Chunk(
            chunk_id=c["chunk_id"],
            source_id=c["source_id"],
            source_type=c["source_type"],
            document_id=c["document_id"],
            locator=c["locator"],
            text=c["text"],
            text_hash=c["text_hash"],
            metadata=c.get("metadata", {}),
        )
        for c in chunks_raw
    )
    if len(chunks) != manifest.get("chunk_count"):
        raise RagIndexStoreError(
            f"chunk_count incohérent : manifest={manifest.get('chunk_count')}, "
            f"chunks.json réellement lu={len(chunks)}."
        )

    embeddings_path = index_path / _EMBEDDINGS_FILENAME
    if not embeddings_path.exists():
        raise RagIndexStoreError(f"Fichier '{_EMBEDDINGS_FILENAME}' absent de l'index persisté '{index_path}'.")
    vectors = np.load(embeddings_path)
    if vectors.shape[0] != len(chunks):
        raise RagIndexStoreError(
            f"embeddings.npy incohérent avec chunks.json : {vectors.shape[0]} vecteurs pour {len(chunks)} chunks."
        )
    if vectors.shape[1] != manifest.get("embedding_dimension"):
        raise RagIndexStoreError(
            f"Dimension d'embedding incohérente : manifest={manifest.get('embedding_dimension')}, "
            f"embeddings.npy={vectors.shape[1]}."
        )

    embedding_model = manifest.get("embedding_model")
    if expected_embedding_model is not None and expected_embedding_model != embedding_model:
        raise RagIndexStoreError(
            f"Modèle d'embedding incompatible : index persisté='{embedding_model}', "
            f"attendu='{expected_embedding_model}'."
        )

    if current_chunks is not None:
        current_hash = compute_corpus_hash(current_chunks)
        persisted_hash = manifest.get("corpus_hash")
        if current_hash != persisted_hash:
            raise RagIndexStoreError(
                f"corpus_hash incompatible : index persisté='{persisted_hash}', "
                f"corpus courant='{current_hash}' — l'index est PÉRIMÉ par rapport au corpus "
                "actuellement reconstruit depuis le staging (régénérer via "
                "'python -m tools.rag.build_index')."
            )

    faiss_path = index_path / _FAISS_FILENAME
    if manifest.get("vector_backend") == "faiss" and faiss_path.exists() and FAISS_AVAILABLE:
        vector_index = faiss.read_index(str(faiss_path))
        backend = "faiss"
    else:
        vector_index, backend = build_vector_index(vectors)

    semantic_index = SemanticRagIndex(
        chunks=chunks,
        vectors=vectors,
        vector_index=vector_index,
        backend=backend,
        embedding_model=embedding_model,
        dimension=manifest.get("embedding_dimension"),
    )
    return semantic_index, manifest
