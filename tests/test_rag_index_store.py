"""
Réf. tâche « maturation technique finale du chapitre 4 », §5 à §9 et
§21/§22 « Rendre le RAG offline réellement persistant ».

Tests unitaires de `src/rag_index_store.py` (§25.4 : pytest obligatoire).
Aucun modèle réel n'est téléchargé pendant `pytest` — `build_semantic_index`
est toujours appelé avec un `FakeEmbedder` déterministe.
"""

import numpy as np
import pytest

from src.rag_indexer import Chunk, RagIndex, build_semantic_index
from src.rag_index_store import (
    INDEX_SCHEMA_VERSION,
    RagIndexStoreError,
    compute_corpus_hash,
    load_rag_index,
    read_rag_index_manifest,
    rebuild_lexical_index,
    save_rag_index,
)
from src.rag_retriever import retrieve_semantic


class FakeEmbedder:
    """Réf. tâche §36 : embedder déterministe factice, aucun téléchargement."""

    model_name = "fake-embedder-test-v1"
    dimension = 4

    def encode(self, texts):
        vectors = []
        for text in texts:
            seed = sum(ord(c) for c in text) or 1
            rng = np.random.default_rng(seed)
            vector = rng.normal(size=self.dimension).astype(np.float32)
            norm = np.linalg.norm(vector)
            vectors.append(vector / norm if norm > 0 else vector)
        return np.asarray(vectors, dtype=np.float32)


def _chunk(chunk_id: str, text: str, *, source_type="literature", document_id="doc", metadata=None) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        source_id=document_id,
        source_type=source_type,
        document_id=document_id,
        locator="l",
        text=text,
        text_hash=f"hash-{chunk_id}",
        metadata=metadata or {},
    )


def make_chunks() -> list[Chunk]:
    return [
        _chunk("c1", "decoy credential lures the attacker", source_type="d3fend", document_id="doc-A"),
        _chunk("c2", "phishing email redirected to a monitored mailbox", source_type="engage", document_id="doc-B"),
        _chunk("c3", "attackers may exploit a public application", source_type="attack", document_id="doc-C"),
    ]


def make_index():
    return build_semantic_index(make_chunks(), embedder=FakeEmbedder())


# ---------------------------------------------------------------------------
# A. Hash déterministe du corpus (§7)
# ---------------------------------------------------------------------------


class TestComputeCorpusHash:
    def test_same_chunks_same_hash_regardless_of_order(self):
        chunks = make_chunks()
        hash_a = compute_corpus_hash(chunks)
        hash_b = compute_corpus_hash(list(reversed(chunks)))
        assert hash_a == hash_b

    def test_different_text_hash_changes_corpus_hash(self):
        chunks = make_chunks()
        mutated = list(chunks)
        mutated[0] = _chunk("c1", "decoy credential lures the attacker", document_id="doc-A")
        object.__setattr__(mutated[0], "text_hash", "different-hash")
        assert compute_corpus_hash(chunks) != compute_corpus_hash(mutated)

    def test_different_metadata_changes_corpus_hash(self):
        chunks = make_chunks()
        mutated = list(chunks)
        mutated[0] = _chunk("c1", "decoy credential lures the attacker", document_id="doc-A", metadata={"revoked": True})
        assert compute_corpus_hash(chunks) != compute_corpus_hash(mutated)

    def test_extra_chunk_changes_corpus_hash(self):
        chunks = make_chunks()
        extended = chunks + [_chunk("c4", "an extra passage")]
        assert compute_corpus_hash(chunks) != compute_corpus_hash(extended)

    def test_deterministic_across_calls(self):
        chunks = make_chunks()
        assert compute_corpus_hash(chunks) == compute_corpus_hash(chunks)


# ---------------------------------------------------------------------------
# B. Sauvegarde (§5/§6/§8)
# ---------------------------------------------------------------------------


class TestSaveRagIndex:
    def test_writes_expected_files(self, tmp_path):
        index = make_index()
        save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        out_dir = tmp_path / "index"
        assert (out_dir / "chunks.json").exists()
        assert (out_dir / "embeddings.npy").exists()
        assert (out_dir / "manifest.json").exists()

    def test_manifest_has_required_fields(self, tmp_path):
        index = make_index()
        manifest = save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        for key in (
            "schema_version", "corpus_version", "corpus_hash", "chunk_count",
            "chunk_count_by_source", "embedding_model", "embedding_dimension",
            "vector_backend", "created_at",
        ):
            assert key in manifest

    def test_manifest_chunk_count_by_source_is_accurate(self, tmp_path):
        index = make_index()
        manifest = save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        assert manifest["chunk_count_by_source"] == {"d3fend": 1, "engage": 1, "attack": 1}

    def test_manifest_schema_version_matches_constant(self, tmp_path):
        index = make_index()
        manifest = save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        assert manifest["schema_version"] == INDEX_SCHEMA_VERSION

    def test_never_fabricates_a_faiss_file_for_numpy_backend(self, tmp_path):
        index = make_index()
        object.__setattr__(index, "backend", "numpy")
        save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        assert not (tmp_path / "index" / "faiss.index").exists()


# ---------------------------------------------------------------------------
# C. read_rag_index_manifest — inspection légère
# ---------------------------------------------------------------------------


class TestReadRagIndexManifest:
    def test_reads_without_loading_embeddings(self, tmp_path):
        index = make_index()
        save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        manifest = read_rag_index_manifest(tmp_path / "index")
        assert manifest["chunk_count"] == 3

    def test_missing_manifest_raises(self, tmp_path):
        with pytest.raises(RagIndexStoreError):
            read_rag_index_manifest(tmp_path / "does-not-exist")


# ---------------------------------------------------------------------------
# D. Chargement — round-trip OFFLINE/ONLINE (§21)
# ---------------------------------------------------------------------------


class TestLoadRagIndexRoundTrip:
    def test_reloaded_index_has_same_chunk_count(self, tmp_path):
        index = make_index()
        save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        reloaded, manifest = load_rag_index(tmp_path / "index")
        assert len(reloaded) == len(index)

    def test_reloaded_index_preserves_chunk_content(self, tmp_path):
        index = make_index()
        save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        reloaded, _ = load_rag_index(tmp_path / "index")
        original_ids = {c.chunk_id for c in index.chunks}
        reloaded_ids = {c.chunk_id for c in reloaded.chunks}
        assert original_ids == reloaded_ids

    def test_retrieval_after_reload_matches_retrieval_before_save(self, tmp_path):
        """Réf. §21 : retrieval après rechargement == retrieval avant
        sauvegarde, à tolérance numérique raisonnable."""
        index = make_index()
        save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        reloaded, _ = load_rag_index(tmp_path / "index")

        query = "decoy credential lures the attacker"
        results_before = retrieve_semantic(index, query, top_k=3, embedder=FakeEmbedder())
        results_after = retrieve_semantic(reloaded, query, top_k=3, embedder=FakeEmbedder())

        assert [r.chunk.chunk_id for r in results_before] == [r.chunk.chunk_id for r in results_after]
        for before, after in zip(results_before, results_after):
            assert before.score == pytest.approx(after.score, abs=1e-5)

    def test_reload_never_reencodes_text(self, tmp_path, monkeypatch):
        """Réf. §8/§11 : recharger un index persisté ne doit JAMAIS
        ré-encoder le texte des chunks — vérifié en faisant échouer
        FakeEmbedder.encode si elle est appelée pendant load_rag_index."""
        index = make_index()
        save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")

        def _forbidden_encode(self, texts):
            raise AssertionError("load_rag_index ne doit jamais ré-encoder les textes des chunks.")

        monkeypatch.setattr(FakeEmbedder, "encode", _forbidden_encode)
        load_rag_index(tmp_path / "index")  # ne doit pas lever


# ---------------------------------------------------------------------------
# E. Index périmé — vérification de compatibilité (§9/§22)
# ---------------------------------------------------------------------------


class TestStaleIndexDetection:
    def test_corpus_hash_mismatch_raises_explicitly(self, tmp_path):
        index = make_index()
        save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        different_chunks = make_chunks() + [_chunk("c-extra", "a new passage not in the persisted index")]
        with pytest.raises(RagIndexStoreError):
            load_rag_index(tmp_path / "index", current_chunks=different_chunks)

    def test_matching_corpus_hash_does_not_raise(self, tmp_path):
        index = make_index()
        save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        reloaded, _ = load_rag_index(tmp_path / "index", current_chunks=make_chunks())
        assert len(reloaded) == 3

    def test_embedding_model_mismatch_raises_explicitly(self, tmp_path):
        index = make_index()
        save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        with pytest.raises(RagIndexStoreError):
            load_rag_index(tmp_path / "index", expected_embedding_model="some-other-model")

    def test_schema_version_mismatch_raises_explicitly(self, tmp_path):
        import json

        index = make_index()
        save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        manifest_path = tmp_path / "index" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["schema_version"] = "999.0"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(RagIndexStoreError):
            load_rag_index(tmp_path / "index")

    def test_dimension_mismatch_raises_explicitly(self, tmp_path):
        import json

        index = make_index()
        save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        manifest_path = tmp_path / "index" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["embedding_dimension"] = manifest["embedding_dimension"] + 1
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(RagIndexStoreError):
            load_rag_index(tmp_path / "index")

    def test_chunk_count_mismatch_raises_explicitly(self, tmp_path):
        import json

        index = make_index()
        save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        manifest_path = tmp_path / "index" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["chunk_count"] = manifest["chunk_count"] + 1
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(RagIndexStoreError):
            load_rag_index(tmp_path / "index")

    def test_missing_manifest_raises_explicitly(self, tmp_path):
        with pytest.raises(RagIndexStoreError):
            load_rag_index(tmp_path / "does-not-exist")

    def test_never_silently_falls_back_to_a_stale_index(self, tmp_path):
        """Réf. §23 : aucune incompatibilité ne doit jamais être avalée
        silencieusement — chaque cas de TestStaleIndexDetection lève
        RagIndexStoreError, jamais un warning ignoré ni un index chargé
        malgré tout."""
        index = make_index()
        save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        with pytest.raises(RagIndexStoreError):
            load_rag_index(tmp_path / "index", expected_embedding_model="wrong-model")

    def test_missing_embeddings_file_raises_explicitly(self, tmp_path):
        """Réf. §23 : « embeddings manquants » -> erreur explicite, jamais
        un index vide ou reconstruit à la volée."""
        index = make_index()
        save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        (tmp_path / "index" / "embeddings.npy").unlink()
        with pytest.raises(RagIndexStoreError):
            load_rag_index(tmp_path / "index")

    def test_corrupted_chunks_file_raises_explicitly(self, tmp_path):
        """Réf. §23 : « corpus corrompu » -> erreur explicite (ici JSON
        syntaxiquement invalide), jamais un repli silencieux."""
        index = make_index()
        save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        (tmp_path / "index" / "chunks.json").write_text("{not valid json", encoding="utf-8")
        with pytest.raises(Exception):
            load_rag_index(tmp_path / "index")

    def test_missing_chunks_file_raises_explicitly(self, tmp_path):
        index = make_index()
        save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        (tmp_path / "index" / "chunks.json").unlink()
        with pytest.raises(RagIndexStoreError):
            load_rag_index(tmp_path / "index")


# ---------------------------------------------------------------------------
# F. Composante lexicale — OPTION B (réf. tâche « dernière passe de
# finition technique », §4/§5/§22-E)
# ---------------------------------------------------------------------------


class TestRebuildLexicalIndex:
    def test_returns_a_rag_index(self, tmp_path):
        index = make_index()
        save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        reloaded, _ = load_rag_index(tmp_path / "index")
        lexical_index = rebuild_lexical_index(reloaded)
        assert isinstance(lexical_index, RagIndex)

    def test_same_chunk_ids_as_semantic_index(self, tmp_path):
        index = make_index()
        save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        reloaded, _ = load_rag_index(tmp_path / "index")
        lexical_index = rebuild_lexical_index(reloaded)
        semantic_ids = {c.chunk_id for c in reloaded.chunks}
        lexical_ids = {c.chunk_id for c in lexical_index.chunks}
        assert semantic_ids == lexical_ids

    def test_never_touches_the_semantic_embedder(self, tmp_path, monkeypatch):
        """Réf. §5 : la reconstruction lexicale ne doit jamais invoquer un
        embedder sémantique (aucun modèle sentence-transformers)."""
        index = make_index()
        save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        reloaded, _ = load_rag_index(tmp_path / "index")

        def _forbidden(*args, **kwargs):
            raise AssertionError("rebuild_lexical_index ne doit jamais charger un embedder sémantique.")

        monkeypatch.setattr("src.semantic_embedder.load_embedder", _forbidden)
        rebuild_lexical_index(reloaded)  # ne doit pas lever

    def test_deterministic_across_calls(self, tmp_path):
        index = make_index()
        save_rag_index(index, tmp_path / "index", corpus_version="test-1.0")
        reloaded, _ = load_rag_index(tmp_path / "index")
        lexical_a = rebuild_lexical_index(reloaded)
        lexical_b = rebuild_lexical_index(reloaded)
        assert lexical_a.embeddings == lexical_b.embeddings
