"""
Réf. architecture : CLAUDE.md — contrat technique du PFE Cyberdéception.

Tests unitaires de tools/deception_kb/literature_seed_builder.py (§25.4 :
pytest obligatoire).

100% hors ligne : les "fichiers locaux" utilisés ici sont des octets
synthétiques (pas de vrais PDF ni de dépendance à pdftotext) — le builder ne
lit que des octets bruts (pour le SHA-256) et un fichier texte déjà extrait
(.txt), jamais un PDF directement. Aucun test ne dépend d'Internet, d'un
DOI réel ou d'un vrai article scientifique. Les identifiants et textes
utilisés ici (ex. "doi_10.9999_fixture") sont des données de test
uniquement ; TestGenerality vérifie qu'aucune logique de production n'est
liée au cas d'usage de référence PFE.
"""

import hashlib
import json
from pathlib import Path

import pytest

from tools.deception_kb.literature_seed_builder import (
    DOCUMENTARY_THEMES,
    LiteratureSeedBuilderError,
    _run_cli,
    build_literature_document_seed,
    build_literature_evidence_seed,
    build_literature_seed_report,
    compute_doi_based_source_id,
    is_valid_fallback_source_id,
    read_evidence_candidates,
    read_literature_sources_registry,
    validate_literature_document_seed,
    validate_literature_evidence_seed,
    validate_literature_sources_registry,
)

FIXTURE_PDF_BYTES = b"%PDF-1.4 fixture content, not a real PDF, only bytes for SHA-256.\n"
FIXTURE_TEXT = (
    "Fixture Deception Paper\n\n"
    "Abstract\n"
    "This fixture paper discusses honeypots and honeytokens as deception "
    "mechanisms for cyber defense. It also covers decoy documents and "
    "attacker engagement.\n\n"
    "1. Introduction\n"
    "Deception delays and contains an intruder while collecting "
    "intelligence about their behavior.\n"
)


def make_source_entry(
    *,
    source_id="doi_10.9999_fixture",
    doi="10.9999/fixture",
    access_status="open_fulltext",
    raw_file=None,
    sha256=None,
    themes=None,
    year=2020,
    publication_type="journal-article",
):
    return {
        "source_id": source_id,
        "title": "Fixture Deception Paper",
        "authors": ["A. Fixture", "B. Fixture"],
        "year": year,
        "publication_type": publication_type,
        "venue": "Fixture Journal of Cyber Deception",
        "doi": doi,
        "official_url": "https://doi.org/10.9999/fixture" if doi else "https://example.org/fixture",
        "open_access_url": "https://example.org/fixture.pdf" if access_status == "open_fulltext" else None,
        "retrieval_date": "2026-08-23",
        "access_status": access_status,
        "relevance_summary": "Fixture summary for tests.",
        "search_queries": ["fixture deception query"],
        "inclusion_reasons": ["fixture_reason"],
        "exclusion_notes": "",
        "themes": themes if themes is not None else ["honeypot", "honeytoken"],
        "raw_file": raw_file,
        "sha256": sha256,
    }


def write_fixture_raw_file(tmp_path, source_id="doi_10.9999_fixture", pdf_bytes=None, text=None):
    pdf_bytes = FIXTURE_PDF_BYTES if pdf_bytes is None else pdf_bytes
    text = FIXTURE_TEXT if text is None else text
    raw_path = tmp_path / f"{source_id}.pdf"
    raw_path.write_bytes(pdf_bytes)
    text_path = tmp_path / f"{source_id}.txt"
    text_path.write_text(text, encoding="utf-8")
    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    return raw_path, sha256


def make_registry(tmp_path, entries=None):
    if entries is None:
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entries = [make_source_entry(raw_file=str(raw_path), sha256=sha256)]
    return {
        "schema": "deception_literature_sources",
        "schema_version": "1.0",
        "selection_method_version": "1.0",
        "sources": entries,
    }


def write_json(tmp_path, filename, data):
    path = tmp_path / filename
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# A. Identifiants stables
# ---------------------------------------------------------------------------


class TestSourceId:
    def test_doi_based_source_id_deterministic(self):
        assert compute_doi_based_source_id("10.1145/3214305") == "doi_10.1145_3214305"
        assert compute_doi_based_source_id("10.1145/3214305") == compute_doi_based_source_id("10.1145/3214305")

    def test_doi_based_source_id_case_insensitive(self):
        assert compute_doi_based_source_id("10.1109/CCST.2017.8167793") == compute_doi_based_source_id(
            "10.1109/ccst.2017.8167793"
        )

    def test_fallback_source_id_rejects_paper_n_pattern(self):
        assert is_valid_fallback_source_id("paper1") is False
        assert is_valid_fallback_source_id("paper42") is False

    def test_fallback_source_id_accepts_documented_convention(self):
        assert is_valid_fallback_source_id("usenixsec2004_provos_virtual_honeypot_framework") is True
        assert is_valid_fallback_source_id("arxiv_1804.06196") is True

    def test_fallback_source_id_rejects_spaces_and_uppercase(self):
        assert is_valid_fallback_source_id("Paper With Spaces") is False


# ---------------------------------------------------------------------------
# B. Validation du registre
# ---------------------------------------------------------------------------


class TestRegistryValidation:
    def test_valid_registry_accepted(self, tmp_path):
        registry = make_registry(tmp_path)
        validate_literature_sources_registry(registry)  # ne doit pas lever

    def test_source_with_doi(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(raw_file=str(raw_path), sha256=sha256, doi="10.9999/fixture")
        registry = make_registry(tmp_path, [entry])
        validate_literature_sources_registry(registry)
        assert entry["source_id"] == compute_doi_based_source_id("10.9999/fixture")

    def test_source_without_doi(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path, source_id="venue2020_author_title")
        entry = make_source_entry(
            source_id="venue2020_author_title", doi=None, raw_file=str(raw_path), sha256=sha256
        )
        registry = make_registry(tmp_path, [entry])
        validate_literature_sources_registry(registry)  # ne doit pas lever

    def test_source_id_inconsistent_with_doi_rejected(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path, source_id="wrong_id")
        entry = make_source_entry(
            source_id="wrong_id", doi="10.9999/fixture", raw_file=str(raw_path), sha256=sha256
        )
        registry = make_registry(tmp_path, [entry])
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_sources_registry(registry)

    def test_duplicate_doi_rejected(self, tmp_path):
        raw1, sha1 = write_fixture_raw_file(tmp_path, source_id="doi_10.9999_fixture")
        raw2, sha2 = write_fixture_raw_file(tmp_path, source_id="doi_10.9999_fixture_dup")
        entry1 = make_source_entry(raw_file=str(raw1), sha256=sha1, doi="10.9999/fixture")
        entry2 = make_source_entry(
            source_id="doi_10.9999_fixture_dup",
            raw_file=str(raw2),
            sha256=sha2,
            doi="10.9999/FIXTURE",  # même DOI, casse différente
        )
        registry = make_registry(tmp_path, [entry1, entry2])
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_sources_registry(registry)

    def test_duplicate_source_id_rejected(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(raw_file=str(raw_path), sha256=sha256)
        registry = make_registry(tmp_path, [entry, dict(entry)])
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_sources_registry(registry)

    def test_missing_required_field_rejected(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(raw_file=str(raw_path), sha256=sha256)
        del entry["relevance_summary"]
        registry = make_registry(tmp_path, [entry])
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_sources_registry(registry)

    def test_metadata_only_access_status_accepted(self):
        entry = make_source_entry(access_status="metadata_only", raw_file=None, sha256=None)
        registry = {
            "schema": "deception_literature_sources",
            "schema_version": "1.0",
            "selection_method_version": "1.0",
            "sources": [entry],
        }
        validate_literature_sources_registry(registry)  # ne doit pas lever

    def test_open_fulltext_without_raw_file_rejected(self):
        entry = make_source_entry(access_status="open_fulltext", raw_file=None, sha256=None)
        registry = {
            "schema": "deception_literature_sources",
            "schema_version": "1.0",
            "selection_method_version": "1.0",
            "sources": [entry],
        }
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_sources_registry(registry)

    def test_metadata_only_with_raw_file_rejected(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(access_status="metadata_only", raw_file=str(raw_path), sha256=sha256)
        registry = make_registry(tmp_path, [entry])
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_sources_registry(registry)

    def test_unknown_theme_rejected(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(raw_file=str(raw_path), sha256=sha256, themes=["not_a_real_theme"])
        registry = make_registry(tmp_path, [entry])
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_sources_registry(registry)

    def test_invalid_access_status_rejected(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(raw_file=str(raw_path), sha256=sha256)
        entry["access_status"] = "totally_invented_status"
        registry = make_registry(tmp_path, [entry])
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_sources_registry(registry)


# ---------------------------------------------------------------------------
# C. Construction et validation du staging document
# ---------------------------------------------------------------------------


class TestDocumentSeedBuilding:
    def test_valid_document_seed_built(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        assert document_seed["schema"] == "literature_document_seed"
        assert len(document_seed["documents"]) == 1
        doc = document_seed["documents"][0]
        assert doc["extraction"]["word_count"] > 0

    def test_metadata_only_document_has_no_extraction(self):
        entry = make_source_entry(access_status="metadata_only", raw_file=None, sha256=None)
        registry = {
            "schema": "deception_literature_sources",
            "schema_version": "1.0",
            "selection_method_version": "1.0",
            "sources": [entry],
        }
        document_seed = build_literature_document_seed(registry)
        assert document_seed["documents"][0]["extraction"] is None

    def test_open_fulltext_but_file_missing_rejected(self, tmp_path):
        missing_path = tmp_path / "does_not_exist.pdf"
        entry = make_source_entry(raw_file=str(missing_path), sha256="a" * 64)
        registry = make_registry(tmp_path, [entry])
        with pytest.raises(LiteratureSeedBuilderError):
            build_literature_document_seed(registry)

    def test_open_fulltext_sha256_mismatch_rejected(self, tmp_path):
        raw_path, _real_sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(raw_file=str(raw_path), sha256="0" * 64)
        registry = make_registry(tmp_path, [entry])
        with pytest.raises(LiteratureSeedBuilderError):
            build_literature_document_seed(registry)

    def test_open_fulltext_without_text_sidecar_rejected(self, tmp_path):
        raw_path = tmp_path / "doi_10.9999_fixture.pdf"
        raw_path.write_bytes(FIXTURE_PDF_BYTES)
        sha256 = hashlib.sha256(FIXTURE_PDF_BYTES).hexdigest()
        entry = make_source_entry(raw_file=str(raw_path), sha256=sha256)
        registry = make_registry(tmp_path, [entry])
        with pytest.raises(LiteratureSeedBuilderError):
            build_literature_document_seed(registry)

    def test_document_seed_validation_accepts_valid(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        validate_literature_document_seed(document_seed)  # ne doit pas lever

    def test_document_seed_validation_rejects_duplicate(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        document_seed["documents"].append(dict(document_seed["documents"][0]))
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_document_seed(document_seed)


# ---------------------------------------------------------------------------
# D. Passages courts (evidence)
# ---------------------------------------------------------------------------


class TestEvidenceSeedBuilding:
    def test_valid_passage_accepted(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        candidates = [
            {
                "source_id": "doi_10.9999_fixture",
                "page": 1,
                "locator": "abstract",
                "text": "This fixture paper discusses honeypots and honeytokens as deception mechanisms for cyber defense.",
            }
        ]
        evidence_seed = build_literature_evidence_seed(document_seed, candidates)
        assert len(evidence_seed["evidence"]) == 1
        assert evidence_seed["evidence"][0]["evidence_id"] == "doi_10.9999_fixture__ev001"
        assert evidence_seed["evidence"][0]["page"] == 1
        assert evidence_seed["evidence"][0]["locator"] == "abstract"

    def test_passage_source_nonexistent_rejected(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        candidates = [{"source_id": "ghost_source", "page": 1, "locator": "abstract", "text": "Ghost text."}]
        with pytest.raises(LiteratureSeedBuilderError):
            build_literature_evidence_seed(document_seed, candidates)

    def test_passage_on_metadata_only_source_rejected(self, tmp_path):
        entry = make_source_entry(access_status="metadata_only", raw_file=None, sha256=None)
        registry = {
            "schema": "deception_literature_sources",
            "schema_version": "1.0",
            "selection_method_version": "1.0",
            "sources": [entry],
        }
        document_seed = build_literature_document_seed(registry)
        candidates = [
            {"source_id": entry["source_id"], "page": 1, "locator": "abstract", "text": "Some text."}
        ]
        with pytest.raises(LiteratureSeedBuilderError):
            build_literature_evidence_seed(document_seed, candidates)

    def test_passage_not_found_verbatim_rejected(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        candidates = [
            {
                "source_id": "doi_10.9999_fixture",
                "page": 1,
                "locator": "abstract",
                "text": "This sentence was never written in the fixture paper at all.",
            }
        ]
        with pytest.raises(LiteratureSeedBuilderError):
            build_literature_evidence_seed(document_seed, candidates)

    def test_passage_exceeding_length_limit_rejected(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        long_text = "Deception delays and contains an intruder. " * 20  # bien > 500 caractères
        candidates = [{"source_id": "doi_10.9999_fixture", "page": 1, "locator": "body_text", "text": long_text}]
        with pytest.raises(LiteratureSeedBuilderError):
            build_literature_evidence_seed(document_seed, candidates)

    def test_page_and_locator_conserved(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        candidates = [
            {
                "source_id": "doi_10.9999_fixture",
                "page": 2,
                "locator": "section_1_introduction",
                "text": "Deception delays and contains an intruder while collecting",
            }
        ]
        evidence_seed = build_literature_evidence_seed(document_seed, candidates)
        entry = evidence_seed["evidence"][0]
        assert entry["page"] == 2
        assert entry["locator"] == "section_1_introduction"

    def test_exact_duplicate_passage_rejected(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        candidate = {
            "source_id": "doi_10.9999_fixture",
            "page": 1,
            "locator": "abstract",
            "text": "It also covers decoy documents and attacker engagement.",
        }
        with pytest.raises(LiteratureSeedBuilderError):
            build_literature_evidence_seed(document_seed, [candidate, dict(candidate)])

    def test_evidence_seed_validation_accepts_valid(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        candidates = [
            {
                "source_id": "doi_10.9999_fixture",
                "page": 1,
                "locator": "abstract",
                "text": "It also covers decoy documents and attacker engagement.",
            }
        ]
        evidence_seed = build_literature_evidence_seed(document_seed, candidates)
        validate_literature_evidence_seed(evidence_seed, document_seed)  # ne doit pas lever

    def test_evidence_seed_validation_rejects_orphan_source(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        corrupted = {
            "schema": "literature_evidence_seed",
            "schema_version": "1.0",
            "selection_method_version": "1.0",
            "evidence": [
                {
                    "evidence_id": "ghost__ev001",
                    "source_id": "ghost_source",
                    "page": 1,
                    "locator": "abstract",
                    "text": "Ghost text.",
                    "source_sha256": "a" * 64,
                }
            ],
        }
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_evidence_seed(corrupted, document_seed)


# ---------------------------------------------------------------------------
# E. Déterminisme
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_registry_same_document_seed(self, tmp_path):
        registry = make_registry(tmp_path)
        seed_a = build_literature_document_seed(registry)
        seed_b = build_literature_document_seed(registry)
        assert seed_a == seed_b

    def test_same_candidates_same_evidence_seed(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        candidates = [
            {
                "source_id": "doi_10.9999_fixture",
                "page": 1,
                "locator": "abstract",
                "text": "It also covers decoy documents and attacker engagement.",
            }
        ]
        seed_a = build_literature_evidence_seed(document_seed, candidates)
        seed_b = build_literature_evidence_seed(document_seed, candidates)
        assert seed_a == seed_b

    def test_evidence_order_deterministic(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        candidates = [
            {"source_id": "doi_10.9999_fixture", "page": 1, "locator": "abstract",
             "text": "This fixture paper discusses honeypots and honeytokens as deception mechanisms for cyber defense."},
            {"source_id": "doi_10.9999_fixture", "page": 1, "locator": "body_text",
             "text": "It also covers decoy documents and attacker engagement."},
        ]
        evidence_seed = build_literature_evidence_seed(document_seed, candidates)
        ids = [e["evidence_id"] for e in evidence_seed["evidence"]]
        assert ids == ["doi_10.9999_fixture__ev001", "doi_10.9999_fixture__ev002"]


# ---------------------------------------------------------------------------
# F. Rapport de couverture
# ---------------------------------------------------------------------------


class TestReport:
    def test_report_counts(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        candidates = [
            {
                "source_id": "doi_10.9999_fixture",
                "page": 1,
                "locator": "abstract",
                "text": "It also covers decoy documents and attacker engagement.",
            }
        ]
        evidence_seed = build_literature_evidence_seed(document_seed, candidates)
        report = build_literature_seed_report(document_seed, evidence_seed)
        assert report["source_count"] == 1
        assert report["peer_reviewed_count"] == 1
        assert report["open_fulltext_count"] == 1
        assert report["metadata_only_count"] == 0
        assert report["sources_with_doi"] == 1
        assert report["evidence_count"] == 1
        assert report["theme_coverage"]["honeypot"] == 1
        assert report["year_range"] == {"min": 2020, "max": 2020}

    def test_coverage_gaps_reported_not_invented(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        evidence_seed = build_literature_evidence_seed(document_seed, [])
        report = build_literature_seed_report(document_seed, evidence_seed)
        # Le fixture registry ne couvre que honeypot/honeytoken : le reste
        # de la taxonomie documentaire doit apparaître en lacune, jamais
        # comblé artificiellement.
        assert set(report["coverage_gaps"]) == set(DOCUMENTARY_THEMES) - {"honeypot", "honeytoken"}

    def test_preprint_not_counted_as_peer_reviewed(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(raw_file=str(raw_path), sha256=sha256, publication_type="preprint")
        registry = make_registry(tmp_path, [entry])
        document_seed = build_literature_document_seed(registry)
        evidence_seed = build_literature_evidence_seed(document_seed, [])
        report = build_literature_seed_report(document_seed, evidence_seed)
        assert report["peer_reviewed_count"] == 0
        assert report["publication_type_counts"] == {"preprint": 1}


# ---------------------------------------------------------------------------
# G. CLI offline
# ---------------------------------------------------------------------------


class TestCli:
    def test_cli_generates_staging_and_report(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(raw_file=str(raw_path), sha256=sha256)
        registry = make_registry(tmp_path, [entry])
        registry_path = write_json(tmp_path, "literature_sources.json", registry)
        candidates_path = write_json(
            tmp_path,
            "evidence_candidates.json",
            {
                "evidence_candidates": [
                    {
                        "source_id": "doi_10.9999_fixture",
                        "page": 1,
                        "locator": "abstract",
                        "text": "It also covers decoy documents and attacker engagement.",
                    }
                ]
            },
        )
        out_dir = tmp_path / "staging"

        _run_cli(
            [
                "--registry", str(registry_path),
                "--evidence-candidates", str(candidates_path),
                "--out-dir", str(out_dir),
                "--version", "9.9-fixture",
            ]
        )

        doc_path = out_dir / "literature_document_seed_9.9-fixture.json"
        ev_path = out_dir / "literature_evidence_seed_9.9-fixture.json"
        report_path = out_dir / "literature_seed_report_9.9-fixture.json"
        assert doc_path.exists()
        assert ev_path.exists()
        assert report_path.exists()

        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["source_count"] == 1
        assert report["evidence_count"] == 1

    def test_cli_rejects_invalid_registry(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(raw_file=str(raw_path), sha256=sha256)
        del entry["venue"]
        registry = make_registry(tmp_path, [entry])
        registry_path = write_json(tmp_path, "literature_sources.json", registry)
        candidates_path = write_json(tmp_path, "evidence_candidates.json", {"evidence_candidates": []})

        with pytest.raises(LiteratureSeedBuilderError):
            _run_cli(
                [
                    "--registry", str(registry_path),
                    "--evidence-candidates", str(candidates_path),
                    "--out-dir", str(tmp_path / "staging"),
                ]
            )

    def test_read_helpers_reject_wrong_schema(self, tmp_path):
        bad_path = write_json(tmp_path, "bad.json", {"schema": "not_the_right_schema", "sources": []})
        with pytest.raises(LiteratureSeedBuilderError):
            read_literature_sources_registry(bad_path)

    def test_read_evidence_candidates_rejects_wrong_shape(self, tmp_path):
        bad_path = write_json(tmp_path, "bad_evidence.json", {"not_evidence_candidates": []})
        with pytest.raises(LiteratureSeedBuilderError):
            read_evidence_candidates(bad_path)


# ---------------------------------------------------------------------------
# H. Généralité — aucune logique liée au cas d'usage de référence
# ---------------------------------------------------------------------------


class TestGenerality:
    def test_no_hardcoded_pfe_reference_case(self):
        import tools.deception_kb.literature_seed_builder as builder_module

        source = Path(builder_module.__file__).read_text(encoding="utf-8")
        forbidden = [
            "T1003", "T1078", "T1566", "T1190", "T1059", "T1041",
            '"DC"', "'DC'", '"WS"', "'WS'", '"DB"', "'DB'",
        ]
        for token in forbidden:
            assert token not in source, f"identifiant/motif interdit trouvé : {token}"

    def test_no_llm_or_rag_dependency(self):
        import tools.deception_kb.literature_seed_builder as builder_module

        source = Path(builder_module.__file__).read_text(encoding="utf-8").lower()
        forbidden = [
            "openai", "anthropic", "ollama", "embedding", "vector",
            "langchain", "llamaindex", "chromadb", "pinecone", "faiss",
        ]
        for token in forbidden:
            assert token not in source, f"dépendance LLM/RAG interdite trouvée : {token}"

    def test_no_network_calls_in_builder(self):
        import tools.deception_kb.literature_seed_builder as builder_module

        source = Path(builder_module.__file__).read_text(encoding="utf-8").lower()
        forbidden = ["requests.get", "urllib.request", "httpx", "http.client"]
        for token in forbidden:
            assert token not in source, f"appel réseau interdit trouvé dans le builder : {token}"
