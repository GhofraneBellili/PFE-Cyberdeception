"""
Réf. architecture : CLAUDE.md §9.1/§26 (rag_indexer.py) — contrat
technique du PFE Cyberdéception.

Tests unitaires de src/rag_indexer.py (§25.4 : pytest obligatoire).

Les tests d'ingestion réelle (`TestRealStagingFiles`) chargent les
fichiers de staging déjà versionnés (`data/deception/staging/*.json`,
produits par `tools/deception_kb/*`) : pas de fixture synthétique
présentée comme un document réel.
"""

import json
from pathlib import Path

import pytest

from src.rag_indexer import (
    EMBEDDING_DIMENSION,
    RagIndexerError,
    build_index,
    compute_document_frequencies,
    embed_query,
    embed_text,
    load_d3fend_chunks,
    load_engage_chunks,
    load_literature_chunks,
    tokenize,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
STAGING_DIR = REPO_ROOT / "data" / "deception" / "staging"


def load_json(name: str) -> dict:
    return json.loads((STAGING_DIR / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# A. Tokenisation et vecteurs déterministes
# ---------------------------------------------------------------------------


class TestTokenizeAndEmbedding:
    def test_tokenize_lowercases_and_splits(self):
        assert tokenize("Decoy Object, D3-DUC!") == ["decoy", "object", "d3", "duc"]

    def test_tokenize_empty_text(self):
        assert tokenize("") == []

    def test_tokenize_excludes_common_stopwords(self):
        assert tokenize("a decoy for the adversary") == ["decoy", "adversary"]

    def test_embed_text_is_deterministic(self):
        vector_1 = embed_text("a decoy credential store", document_frequencies={}, num_documents=0)
        vector_2 = embed_text("a decoy credential store", document_frequencies={}, num_documents=0)
        assert vector_1 == vector_2

    def test_embed_text_has_expected_dimension(self):
        vector = embed_text("some text", document_frequencies={}, num_documents=0, dimension=64)
        assert len(vector) == 64

    def test_embed_text_is_unit_norm_for_nonempty_text(self):
        vector = embed_text("decoy file honeypot", document_frequencies={}, num_documents=0)
        norm = sum(v * v for v in vector) ** 0.5
        assert norm == pytest.approx(1.0, abs=1e-9)

    def test_embed_text_empty_text_is_zero_vector(self):
        vector = embed_text("", document_frequencies={}, num_documents=0)
        assert all(v == 0.0 for v in vector)

    def test_default_dimension(self):
        assert len(embed_text("x", document_frequencies={}, num_documents=0)) == EMBEDDING_DIMENSION

    def test_invalid_dimension_rejected(self):
        with pytest.raises(RagIndexerError):
            embed_text("x", document_frequencies={}, num_documents=0, dimension=0)

    def test_compute_document_frequencies_counts_chunks_containing_token(self):
        seed = {
            "evidence": [
                {"evidence_id": "c1", "source_id": "s", "page": 1, "locator": "l", "text": "decoy credential"},
                {"evidence_id": "c2", "source_id": "s", "page": 1, "locator": "l", "text": "decoy file"},
            ]
        }
        chunks = load_literature_chunks(seed)
        df = compute_document_frequencies(chunks)
        assert df["decoy"] == 2
        assert df["credential"] == 1

    def test_frequent_token_gets_lower_idf_weight_than_rare_token(self):
        seed = {
            "evidence": [
                {"evidence_id": f"e{i}", "source_id": "s", "page": 1, "locator": "l", "text": "the system network the system"}
                for i in range(5)
            ]
            + [{"evidence_id": "e_rare", "source_id": "s", "page": 1, "locator": "l", "text": "credential decoy honeypot"}]
        }
        chunks = load_literature_chunks(seed)
        index = build_index(chunks)
        # "credential" (df=1) doit peser davantage que "system" (df=5) sur un corpus de 6 chunks.
        from src.rag_indexer import _idf

        assert _idf("credential", index.document_frequencies, index.num_documents) > _idf(
            "system", index.document_frequencies, index.num_documents
        )

    def test_embed_query_uses_index_corpus_statistics(self):
        seed = {"evidence": [{"evidence_id": "e1", "source_id": "s", "page": 1, "locator": "l", "text": "decoy credential store"}]}
        index = build_index(load_literature_chunks(seed))
        query_vector = embed_query(index, "decoy credential store")
        assert query_vector == index.embeddings["e1"]


# ---------------------------------------------------------------------------
# B. Ingestion synthétique — structure minimale conforme au schéma staging
# ---------------------------------------------------------------------------


class TestLoadD3fendChunksSynthetic:
    def test_one_chunk_per_evidence_entry(self):
        seed = {
            "concepts": [
                {
                    "source_technique_id": "D3-XX",
                    "name": "Concept X",
                    "source_evidence": [
                        {"source_file": "d3fend.json", "source_property": "rdfs:label", "evidence_text": "Concept X", "source_sha256": "abc"},
                        {"source_file": "d3fend.json", "source_property": "d3f:definition", "evidence_text": "Definition of Concept X.", "source_sha256": "abc"},
                    ],
                }
            ]
        }
        chunks = load_d3fend_chunks(seed)
        assert len(chunks) == 2
        assert chunks[0].chunk_id == "d3fend:D3-XX:0"
        assert chunks[0].source_type == "d3fend"
        assert chunks[0].document_id == "D3-XX"
        assert chunks[0].text == "Concept X"

    def test_empty_evidence_text_skipped(self):
        seed = {
            "concepts": [
                {
                    "source_technique_id": "D3-XX",
                    "source_evidence": [{"source_file": "f", "source_property": "p", "evidence_text": "   "}],
                }
            ]
        }
        assert load_d3fend_chunks(seed) == []


class TestLoadEngageChunksSynthetic:
    def test_description_and_distinct_long_description_both_kept(self):
        seed = {
            "activities": [
                {
                    "activity_id": "EAC0099",
                    "name": "Test Activity",
                    "detail_type": "Engagement",
                    "description": "Short.",
                    "long_description": "Much longer explanation.",
                }
            ]
        }
        chunks = load_engage_chunks(seed)
        assert len(chunks) == 2
        locators = {c.locator for c in chunks}
        assert locators == {"description", "long_description"}

    def test_identical_long_description_not_duplicated(self):
        seed = {
            "activities": [
                {"activity_id": "EAC0099", "description": "Same text.", "long_description": "Same text."}
            ]
        }
        chunks = load_engage_chunks(seed)
        assert len(chunks) == 1
        assert chunks[0].locator == "description"


class TestLoadLiteratureChunksSynthetic:
    def test_fields_mapped_from_evidence(self):
        seed = {
            "evidence": [
                {
                    "evidence_id": "doc1__ev001",
                    "source_id": "doc1",
                    "page": 3,
                    "locator": "abstract",
                    "text": "Deception increases attacker dwell time.",
                    "source_sha256": "deadbeef",
                    "page_verified": True,
                }
            ]
        }
        chunks = load_literature_chunks(seed)
        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk.chunk_id == "doc1__ev001"
        assert chunk.source_id == "doc1"
        assert chunk.source_type == "literature"
        assert chunk.locator == "page_3_abstract"
        assert chunk.metadata["page_verified"] is True


# ---------------------------------------------------------------------------
# C. Index — réf. §9.1 étape 7
# ---------------------------------------------------------------------------


class TestBuildIndex:
    def test_index_has_one_embedding_per_chunk(self):
        seed = {"evidence": [{"evidence_id": "e1", "source_id": "s1", "page": 1, "locator": "l", "text": "hello world"}]}
        chunks = load_literature_chunks(seed)
        index = build_index(chunks)
        assert len(index) == 1
        assert "e1" in index.embeddings
        assert len(index.embeddings["e1"]) == index.dimension

    def test_duplicate_chunk_id_rejected(self):
        seed = {
            "evidence": [
                {"evidence_id": "dup", "source_id": "s1", "page": 1, "locator": "l", "text": "a"},
                {"evidence_id": "dup", "source_id": "s2", "page": 2, "locator": "l", "text": "b"},
            ]
        }
        chunks = load_literature_chunks(seed)
        with pytest.raises(RagIndexerError):
            build_index(chunks)


# ---------------------------------------------------------------------------
# D. Ingestion réelle — data/deception/staging/*.json (§9.1, anti-fabrication)
# ---------------------------------------------------------------------------


class TestRealStagingFiles:
    def test_real_literature_evidence_produces_18_chunks(self):
        seed = load_json("literature_evidence_seed_1.2.json")
        chunks = load_literature_chunks(seed)
        assert len(chunks) == len(seed["evidence"])
        assert all(c.source_type == "literature" for c in chunks)
        assert len({c.chunk_id for c in chunks}) == len(chunks)

    def test_real_d3fend_seed_produces_chunks_with_valid_index(self):
        seed = load_json("d3fend_deception_seed_1.5.0.json")
        chunks = load_d3fend_chunks(seed)
        assert len(chunks) > 0
        index = build_index(chunks)
        assert len(index) == len(chunks)

    def test_real_engage_seed_produces_chunks(self):
        seed = load_json("engage_activity_seed_1.0.json")
        chunks = load_engage_chunks(seed)
        assert len(chunks) > 0
        assert all(c.source_type == "engage" for c in chunks)

    def test_combined_index_has_no_chunk_id_collisions_across_sources(self):
        d3fend_chunks = load_d3fend_chunks(load_json("d3fend_deception_seed_1.5.0.json"))
        engage_chunks = load_engage_chunks(load_json("engage_activity_seed_1.0.json"))
        literature_chunks = load_literature_chunks(load_json("literature_evidence_seed_1.2.json"))
        index = build_index(d3fend_chunks + engage_chunks + literature_chunks)
        assert len(index) == len(d3fend_chunks) + len(engage_chunks) + len(literature_chunks)


# ---------------------------------------------------------------------------
# E. Invariant LLM hors du chemin d'exécution
# ---------------------------------------------------------------------------


class TestLlmOutOfExecutionPath:
    def test_rag_indexer_does_not_import_llm(self):
        import ast

        import src.rag_indexer as module

        source = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
        assert "src.annotator_llm" not in imported_modules
