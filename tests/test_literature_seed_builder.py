"""
Réf. architecture : CLAUDE.md — contrat technique du PFE Cyberdéception.

Tests unitaires de tools/deception_kb/literature_seed_builder.py (§25.4 :
pytest obligatoire), durcis en phase 4B.3-H (schéma bibliographique 1.1,
vérification page par page) puis 4B.3-H2 (schéma de staging 1.2 :
distinction stricte pagination observable / pagination absente —
page_verified=true implique désormais pagination_available=true).

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
    extract_page_structure,
    is_valid_fallback_source_id,
    read_evidence_candidates,
    read_literature_sources_registry,
    validate_literature_document_seed,
    validate_literature_evidence_seed,
    validate_literature_sources_registry,
)

FIXTURE_PDF_BYTES = b"%PDF-1.4 fixture content, not a real PDF, only bytes for SHA-256.\n"

# Deux pages synthétiques séparées par un form-feed (\x0c), comme produit
# nativement par pdftotext entre deux pages réelles d'un PDF.
FIXTURE_PAGE_1 = (
    "Fixture Deception Paper\n\n"
    "Abstract\n"
    "This fixture paper discusses honeypots and honeytokens as deception "
    "mechanisms for cyber defense.\n"
)
FIXTURE_PAGE_2 = (
    "1. Introduction\n"
    "It also covers decoy documents and attacker engagement.\n"
    "Deception delays and contains an intruder while collecting "
    "intelligence about their behavior.\n"
)
FIXTURE_TEXT = FIXTURE_PAGE_1 + "\x0c" + FIXTURE_PAGE_2

# Même contenu que FIXTURE_TEXT mais sans aucun séparateur de page — simule
# une extraction où pdftotext n'a pas produit de "\x0c" (pagination perdue).
FIXTURE_TEXT_NO_PAGE_SEPARATORS = FIXTURE_PAGE_1 + FIXTURE_PAGE_2


def make_provenance(provider="Crossref", fields=None):
    return [
        {
            "provider": provider,
            "url": "https://api.crossref.org/works/10.9999/fixture",
            "retrieval_date": "2026-08-23",
            "verified_fields": fields or ["title", "authors", "publication_doi"],
        }
    ]


def make_source_entry(
    *,
    source_id="doi_10.9999_fixture",
    publication_doi="10.9999/fixture",
    repository_doi=None,
    repository_identifier=None,
    access_status="open_fulltext",
    raw_file=None,
    sha256=None,
    themes=None,
    bibliographic_year=2020,
    published_online_year=None,
    published_print_year=None,
    publication_type="journal-article",
    peer_review_status="peer_reviewed",
    peer_review_basis="Fixture venue evaluee par les pairs.",
    metadata_notes="",
    metadata_provenance=None,
):
    return {
        "source_id": source_id,
        "title": "Fixture Deception Paper",
        "authors": ["A. Fixture", "B. Fixture"],
        "bibliographic_year": bibliographic_year,
        "published_online_year": published_online_year,
        "published_print_year": published_print_year,
        "publication_type": publication_type,
        "venue": "Fixture Journal of Cyber Deception",
        "publication_doi": publication_doi,
        "repository_doi": repository_doi,
        "repository_identifier": repository_identifier,
        "official_url": "https://doi.org/10.9999/fixture" if publication_doi else "https://example.org/fixture",
        "open_access_url": "https://example.org/fixture.pdf" if access_status == "open_fulltext" else None,
        "retrieval_date": "2026-08-23",
        "access_status": access_status,
        "peer_review_status": peer_review_status,
        "peer_review_basis": peer_review_basis,
        "relevance_summary": "Fixture summary for tests.",
        "search_queries": ["fixture deception query"],
        "inclusion_reasons": ["fixture_reason"],
        "exclusion_notes": "",
        "metadata_notes": metadata_notes,
        "metadata_provenance": metadata_provenance if metadata_provenance is not None else make_provenance(),
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
        "schema_version": "1.1",
        "selection_method_version": "1.1",
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
# B. Découpage par page
# ---------------------------------------------------------------------------


class TestPageSplitting:
    def test_splits_on_form_feed(self):
        structure = extract_page_structure("page one\x0cpage two\x0cpage three")
        assert structure["pagination_available"] is True
        assert structure["pages"] == ["page one", "page two", "page three"]

    def test_no_separator_means_pagination_unavailable(self):
        """§4 : un texte sans séparateur de page ne doit JAMAIS être assimilé
        à un document d'une seule page vérifiée — pagination_available doit
        être False, et aucune page ne doit être renvoyée comme fiable."""
        structure = extract_page_structure("only page content, no separator at all")
        assert structure["pagination_available"] is False
        assert structure["pages"] == []

    def test_terminal_form_feed_does_not_create_phantom_page(self):
        """Réf. micro-correctif : pdftotext termine aussi la dernière page
        par '\\f' — un document de 2 pages ne doit jamais devenir 3 pages."""
        structure = extract_page_structure("page1\x0cpage2\x0c")
        assert structure["pagination_available"] is True
        assert structure["pages"] == ["page1", "page2"]

    def test_no_terminal_form_feed_unaffected(self):
        structure = extract_page_structure("page1\x0cpage2")
        assert structure["pagination_available"] is True
        assert structure["pages"] == ["page1", "page2"]

    def test_internal_empty_page_preserved_only_terminal_artifact_removed(self):
        """Une page interne réellement vide ('\\f\\f') n'est jamais
        confondue avec l'artefact terminal — seul ce dernier est retiré."""
        structure = extract_page_structure("page1\x0c\x0cpage3\x0c")
        assert structure["pagination_available"] is True
        assert structure["pages"] == ["page1", "", "page3"]


# ---------------------------------------------------------------------------
# C. Validation du registre — DOI / dates / peer review / provenance
# ---------------------------------------------------------------------------


class TestRegistryValidationDoi:
    def test_valid_registry_accepted(self, tmp_path):
        registry = make_registry(tmp_path)
        validate_literature_sources_registry(registry)

    def test_source_with_publication_doi(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(raw_file=str(raw_path), sha256=sha256, publication_doi="10.9999/fixture")
        registry = make_registry(tmp_path, [entry])
        validate_literature_sources_registry(registry)
        assert entry["source_id"] == compute_doi_based_source_id("10.9999/fixture")

    def test_source_with_repository_doi_only(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path, source_id="arxiv_9999.00000")
        entry = make_source_entry(
            source_id="arxiv_9999.00000",
            publication_doi=None,
            repository_doi="10.48550/arXiv.9999.00000",
            repository_identifier="arXiv:9999.00000",
            raw_file=str(raw_path),
            sha256=sha256,
            publication_type="preprint",
            peer_review_status="not_peer_reviewed",
            metadata_provenance=make_provenance(provider="DataCite"),
        )
        registry = make_registry(tmp_path, [entry])
        validate_literature_sources_registry(registry)  # ne doit pas lever

    def test_source_without_any_doi(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path, source_id="venue2020_author_title")
        entry = make_source_entry(
            source_id="venue2020_author_title",
            publication_doi=None,
            raw_file=str(raw_path),
            sha256=sha256,
        )
        registry = make_registry(tmp_path, [entry])
        validate_literature_sources_registry(registry)  # ne doit pas lever

    def test_source_id_inconsistent_with_publication_doi_rejected(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path, source_id="wrong_id")
        entry = make_source_entry(
            source_id="wrong_id", publication_doi="10.9999/fixture", raw_file=str(raw_path), sha256=sha256
        )
        registry = make_registry(tmp_path, [entry])
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_sources_registry(registry)

    def test_duplicate_publication_doi_rejected(self, tmp_path):
        raw1, sha1 = write_fixture_raw_file(tmp_path, source_id="doi_10.9999_fixture")
        raw2, sha2 = write_fixture_raw_file(tmp_path, source_id="doi_10.9999_fixture_dup")
        entry1 = make_source_entry(raw_file=str(raw1), sha256=sha1, publication_doi="10.9999/fixture")
        entry2 = make_source_entry(
            source_id="doi_10.9999_fixture_dup",
            raw_file=str(raw2),
            sha256=sha2,
            publication_doi="10.9999/FIXTURE",  # même DOI, casse différente
        )
        registry = make_registry(tmp_path, [entry1, entry2])
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_sources_registry(registry)

    def test_duplicate_repository_doi_rejected(self, tmp_path):
        raw1, sha1 = write_fixture_raw_file(tmp_path, source_id="arxiv_1111.11111")
        raw2, sha2 = write_fixture_raw_file(tmp_path, source_id="arxiv_2222.22222")
        common_repo_doi = "10.48550/arXiv.1111.11111"
        entry1 = make_source_entry(
            source_id="arxiv_1111.11111", publication_doi=None, repository_doi=common_repo_doi,
            raw_file=str(raw1), sha256=sha1,
        )
        entry2 = make_source_entry(
            source_id="arxiv_2222.22222", publication_doi=None, repository_doi=common_repo_doi,
            raw_file=str(raw2), sha256=sha2,
        )
        registry = make_registry(tmp_path, [entry1, entry2])
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_sources_registry(registry)

    def test_publication_doi_equal_to_repository_doi_rejected(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(
            raw_file=str(raw_path), sha256=sha256,
            publication_doi="10.9999/fixture", repository_doi="10.9999/FIXTURE",
        )
        registry = make_registry(tmp_path, [entry])
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


class TestRegistryValidationDates:
    def test_bibliographic_year_required(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(raw_file=str(raw_path), sha256=sha256, bibliographic_year=None)
        registry = make_registry(tmp_path, [entry])
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_sources_registry(registry)

    def test_online_and_print_years_may_be_null(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(
            raw_file=str(raw_path), sha256=sha256,
            bibliographic_year=2020, published_online_year=None, published_print_year=None,
        )
        registry = make_registry(tmp_path, [entry])
        validate_literature_sources_registry(registry)  # ne doit pas lever

    def test_online_and_print_years_when_present(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(
            raw_file=str(raw_path), sha256=sha256,
            bibliographic_year=2018, published_online_year=2018, published_print_year=2019,
        )
        registry = make_registry(tmp_path, [entry])
        validate_literature_sources_registry(registry)  # ne doit pas lever

    def test_non_integer_year_rejected(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(raw_file=str(raw_path), sha256=sha256)
        entry["published_online_year"] = "2020"  # chaîne, pas un entier
        registry = make_registry(tmp_path, [entry])
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_sources_registry(registry)


class TestRegistryValidationPeerReview:
    def test_peer_reviewed_accepted(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(raw_file=str(raw_path), sha256=sha256, peer_review_status="peer_reviewed")
        registry = make_registry(tmp_path, [entry])
        validate_literature_sources_registry(registry)

    def test_not_peer_reviewed_accepted(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(raw_file=str(raw_path), sha256=sha256, peer_review_status="not_peer_reviewed")
        registry = make_registry(tmp_path, [entry])
        validate_literature_sources_registry(registry)

    def test_unknown_peer_review_accepted(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(raw_file=str(raw_path), sha256=sha256, peer_review_status="unknown")
        registry = make_registry(tmp_path, [entry])
        validate_literature_sources_registry(registry)

    def test_invalid_peer_review_status_rejected(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(raw_file=str(raw_path), sha256=sha256)
        entry["peer_review_status"] = "definitely_reviewed_trust_me"
        registry = make_registry(tmp_path, [entry])
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_sources_registry(registry)

    def test_missing_peer_review_basis_rejected(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(raw_file=str(raw_path), sha256=sha256, peer_review_basis="")
        registry = make_registry(tmp_path, [entry])
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_sources_registry(registry)

    def test_publication_type_does_not_imply_peer_review(self, tmp_path):
        """§19 : un conference-paper avec peer_review_status='unknown' doit
        rester 'unknown' — jamais requalifié en 'peer_reviewed' du simple
        fait de son publication_type."""
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(
            raw_file=str(raw_path), sha256=sha256,
            publication_type="conference-paper", peer_review_status="unknown",
        )
        registry = make_registry(tmp_path, [entry])
        validate_literature_sources_registry(registry)
        document_seed = build_literature_document_seed(registry)
        report = build_literature_seed_report(document_seed, {"evidence": []})
        assert report["peer_reviewed_count"] == 0
        assert report["unknown_peer_review_count"] == 1


class TestRegistryValidationProvenance:
    def test_empty_provenance_rejected(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(raw_file=str(raw_path), sha256=sha256, metadata_provenance=[])
        registry = make_registry(tmp_path, [entry])
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_sources_registry(registry)

    def test_incomplete_provenance_entry_rejected(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(raw_file=str(raw_path), sha256=sha256)
        entry["metadata_provenance"] = [{"provider": "Crossref"}]  # champs manquants
        registry = make_registry(tmp_path, [entry])
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_sources_registry(registry)


class TestRegistryValidationAccessAndThemes:
    def test_metadata_only_access_status_accepted(self):
        entry = make_source_entry(access_status="metadata_only", raw_file=None, sha256=None)
        registry = {
            "schema": "deception_literature_sources", "schema_version": "1.1",
            "selection_method_version": "1.1", "sources": [entry],
        }
        validate_literature_sources_registry(registry)

    def test_open_fulltext_without_raw_file_rejected(self):
        entry = make_source_entry(access_status="open_fulltext", raw_file=None, sha256=None)
        registry = {
            "schema": "deception_literature_sources", "schema_version": "1.1",
            "selection_method_version": "1.1", "sources": [entry],
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
# D. Construction et validation du staging document
# ---------------------------------------------------------------------------


class TestDocumentSeedBuilding:
    def test_valid_document_seed_built(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        assert document_seed["schema"] == "literature_document_seed"
        assert document_seed["schema_version"] == "1.2"
        assert len(document_seed["documents"]) == 1
        doc = document_seed["documents"][0]
        assert doc["extraction"]["word_count"] > 0
        assert doc["extraction"]["page_count"] == 2
        assert doc["extraction"]["pagination_available"] is True

    def test_metadata_only_document_has_no_extraction(self):
        entry = make_source_entry(access_status="metadata_only", raw_file=None, sha256=None)
        registry = {
            "schema": "deception_literature_sources", "schema_version": "1.1",
            "selection_method_version": "1.1", "sources": [entry],
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
        validate_literature_document_seed(document_seed)

    def test_document_seed_validation_rejects_duplicate(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        document_seed["documents"].append(dict(document_seed["documents"][0]))
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_document_seed(document_seed)

    def test_document_seed_carries_new_bibliographic_fields(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(
            raw_file=str(raw_path), sha256=sha256,
            bibliographic_year=2018, published_online_year=2018, published_print_year=2019,
        )
        registry = make_registry(tmp_path, [entry])
        document_seed = build_literature_document_seed(registry)
        doc = document_seed["documents"][0]
        assert doc["bibliographic_year"] == 2018
        assert doc["published_online_year"] == 2018
        assert doc["published_print_year"] == 2019
        assert doc["peer_review_status"] == "peer_reviewed"
        assert doc["metadata_provenance"]


# ---------------------------------------------------------------------------
# E. Passages courts — vérification page par page
# ---------------------------------------------------------------------------


class TestEvidencePageVerification:
    def test_passage_on_declared_page_accepted(self, tmp_path):
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
        entry = evidence_seed["evidence"][0]
        assert entry["page"] == 1
        assert entry["page_verified"] is True

    def test_passage_present_but_on_wrong_declared_page_rejected(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        # Ce texte est réellement sur la page 1, pas la page 2.
        candidates = [
            {
                "source_id": "doi_10.9999_fixture",
                "page": 2,
                "locator": "abstract",
                "text": "This fixture paper discusses honeypots and honeytokens as deception mechanisms for cyber defense.",
            }
        ]
        with pytest.raises(LiteratureSeedBuilderError):
            build_literature_evidence_seed(document_seed, candidates)

    def test_passage_on_second_page_accepted(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        candidates = [
            {
                "source_id": "doi_10.9999_fixture",
                "page": 2,
                "locator": "body_text",
                "text": "It also covers decoy documents and attacker engagement.",
            }
        ]
        evidence_seed = build_literature_evidence_seed(document_seed, candidates)
        assert evidence_seed["evidence"][0]["page"] == 2
        assert evidence_seed["evidence"][0]["page_verified"] is True

    def test_nonexistent_page_rejected(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        candidates = [
            {
                "source_id": "doi_10.9999_fixture",
                "page": 99,
                "locator": "abstract",
                "text": "This fixture paper discusses honeypots and honeytokens as deception mechanisms for cyber defense.",
            }
        ]
        with pytest.raises(LiteratureSeedBuilderError):
            build_literature_evidence_seed(document_seed, candidates)

    def test_page_zero_rejected(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        candidates = [
            {"source_id": "doi_10.9999_fixture", "page": 0, "locator": "abstract", "text": "irrelevant"}
        ]
        with pytest.raises(LiteratureSeedBuilderError):
            build_literature_evidence_seed(document_seed, candidates)

    def test_document_without_page_separators_has_no_verifiable_pagination(self, tmp_path):
        """§4/§6 : une extraction sans '\\x0c' ne doit jamais être assimilée
        à un document d'une seule page vérifiée."""
        raw_path, sha256 = write_fixture_raw_file(
            tmp_path, source_id="doi_10.9999_nosep", text="No page separators in this extraction at all."
        )
        entry = make_source_entry(source_id="doi_10.9999_nosep", raw_file=str(raw_path), sha256=sha256)
        registry = make_registry(tmp_path, [entry])
        document_seed = build_literature_document_seed(registry)
        extraction = document_seed["documents"][0]["extraction"]
        assert extraction["pagination_available"] is False
        assert extraction["page_count"] is None

    def test_page_one_rejected_when_pagination_unavailable(self, tmp_path):
        """§7 : même 'page: 1' ne doit jamais être accepté silencieusement
        quand la pagination n'est pas observable — c'est le coeur du
        durcissement 4B.3-H2."""
        raw_path, sha256 = write_fixture_raw_file(
            tmp_path, source_id="doi_10.9999_nosep", text="No page separators in this extraction at all."
        )
        entry = make_source_entry(source_id="doi_10.9999_nosep", raw_file=str(raw_path), sha256=sha256)
        registry = make_registry(tmp_path, [entry])
        document_seed = build_literature_document_seed(registry)
        candidates = [
            {"source_id": "doi_10.9999_nosep", "page": 1, "locator": "body_text", "text": "No page separators in this extraction at all."}
        ]
        with pytest.raises(LiteratureSeedBuilderError):
            build_literature_evidence_seed(document_seed, candidates)

    def test_page_two_rejected_when_pagination_unavailable(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(
            tmp_path, source_id="doi_10.9999_nosep", text="No page separators in this extraction at all."
        )
        entry = make_source_entry(source_id="doi_10.9999_nosep", raw_file=str(raw_path), sha256=sha256)
        registry = make_registry(tmp_path, [entry])
        document_seed = build_literature_document_seed(registry)
        candidates = [
            {"source_id": "doi_10.9999_nosep", "page": 2, "locator": "body_text", "text": "No page separators in this extraction at all."}
        ]
        with pytest.raises(LiteratureSeedBuilderError):
            build_literature_evidence_seed(document_seed, candidates)

    def test_evidence_seed_validation_rejects_page_verified_without_pagination_available(self, tmp_path):
        """§9 : invariant page_verified=true ⇒ pagination_available=true,
        vérifié même si le champ evidence a été falsifié après coup."""
        raw_path, sha256 = write_fixture_raw_file(
            tmp_path, source_id="doi_10.9999_nosep", text="No page separators in this extraction at all."
        )
        entry = make_source_entry(source_id="doi_10.9999_nosep", raw_file=str(raw_path), sha256=sha256)
        registry = make_registry(tmp_path, [entry])
        document_seed = build_literature_document_seed(registry)
        forged_evidence_seed = {
            "schema": "literature_evidence_seed", "schema_version": "1.2",
            "selection_method_version": "1.1",
            "evidence": [
                {
                    "evidence_id": "doi_10.9999_nosep__ev001", "source_id": "doi_10.9999_nosep",
                    "page": 1, "locator": "body_text",
                    "text": "No page separators in this extraction at all.",
                    "source_sha256": sha256, "page_verified": True,
                }
            ],
        }
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_evidence_seed(forged_evidence_seed, document_seed)

    def test_same_passage_appearing_on_multiple_pages_must_match_declared_page(self, tmp_path):
        text = "Repeated sentence used as a passage on both pages.\x0cRepeated sentence used as a passage on both pages."
        raw_path, sha256 = write_fixture_raw_file(tmp_path, source_id="doi_10.9999_repeat", text=text)
        entry = make_source_entry(source_id="doi_10.9999_repeat", raw_file=str(raw_path), sha256=sha256)
        registry = make_registry(tmp_path, [entry])
        document_seed = build_literature_document_seed(registry)
        for page in (1, 2):
            candidates = [
                {
                    "source_id": "doi_10.9999_repeat",
                    "page": page,
                    "locator": "body_text",
                    "text": "Repeated sentence used as a passage on both pages.",
                }
            ]
            evidence_seed = build_literature_evidence_seed(document_seed, candidates)
            assert evidence_seed["evidence"][0]["page"] == page

    def test_passage_source_nonexistent_rejected(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        candidates = [{"source_id": "ghost_source", "page": 1, "locator": "abstract", "text": "Ghost text."}]
        with pytest.raises(LiteratureSeedBuilderError):
            build_literature_evidence_seed(document_seed, candidates)

    def test_passage_on_metadata_only_source_rejected(self, tmp_path):
        entry = make_source_entry(access_status="metadata_only", raw_file=None, sha256=None)
        registry = {
            "schema": "deception_literature_sources", "schema_version": "1.1",
            "selection_method_version": "1.1", "sources": [entry],
        }
        document_seed = build_literature_document_seed(registry)
        candidates = [
            {"source_id": entry["source_id"], "page": 1, "locator": "abstract", "text": "Some text."}
        ]
        with pytest.raises(LiteratureSeedBuilderError):
            build_literature_evidence_seed(document_seed, candidates)

    def test_passage_not_found_anywhere_rejected(self, tmp_path):
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
        long_text = "Deception delays and contains an intruder. " * 20
        candidates = [{"source_id": "doi_10.9999_fixture", "page": 2, "locator": "body_text", "text": long_text}]
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
            "page": 2,
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
                "page": 2,
                "locator": "abstract",
                "text": "It also covers decoy documents and attacker engagement.",
            }
        ]
        evidence_seed = build_literature_evidence_seed(document_seed, candidates)
        validate_literature_evidence_seed(evidence_seed, document_seed)

    def test_evidence_seed_validation_rejects_orphan_source(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        corrupted = {
            "schema": "literature_evidence_seed", "schema_version": "1.2",
            "selection_method_version": "1.1",
            "evidence": [
                {
                    "evidence_id": "ghost__ev001", "source_id": "ghost_source", "page": 1,
                    "locator": "abstract", "text": "Ghost text.", "source_sha256": "a" * 64,
                    "page_verified": True,
                }
            ],
        }
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_evidence_seed(corrupted, document_seed)

    def test_evidence_seed_validation_rejects_unverified_page(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        candidates = [
            {"source_id": "doi_10.9999_fixture", "page": 2, "locator": "abstract",
             "text": "It also covers decoy documents and attacker engagement."}
        ]
        evidence_seed = build_literature_evidence_seed(document_seed, candidates)
        evidence_seed["evidence"][0]["page_verified"] = False
        with pytest.raises(LiteratureSeedBuilderError):
            validate_literature_evidence_seed(evidence_seed, document_seed)


# ---------------------------------------------------------------------------
# F. Déterminisme
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
            {"source_id": "doi_10.9999_fixture", "page": 2, "locator": "abstract",
             "text": "It also covers decoy documents and attacker engagement."}
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
            {"source_id": "doi_10.9999_fixture", "page": 2, "locator": "body_text",
             "text": "It also covers decoy documents and attacker engagement."},
        ]
        evidence_seed = build_literature_evidence_seed(document_seed, candidates)
        ids = [e["evidence_id"] for e in evidence_seed["evidence"]]
        assert ids == ["doi_10.9999_fixture__ev001", "doi_10.9999_fixture__ev002"]


# ---------------------------------------------------------------------------
# G. Rapport de couverture durci
# ---------------------------------------------------------------------------


class TestReport:
    def test_report_counts(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        candidates = [
            {"source_id": "doi_10.9999_fixture", "page": 2, "locator": "abstract",
             "text": "It also covers decoy documents and attacker engagement."}
        ]
        evidence_seed = build_literature_evidence_seed(document_seed, candidates)
        report = build_literature_seed_report(document_seed, evidence_seed)
        assert report["schema_version"] == "1.2"
        assert report["source_count"] == 1
        assert report["peer_reviewed_count"] == 1
        assert report["not_peer_reviewed_count"] == 0
        assert report["unknown_peer_review_count"] == 0
        assert report["open_fulltext_count"] == 1
        assert report["metadata_only_count"] == 0
        assert report["abstract_only_count"] == 0
        assert report["unavailable_count"] == 0
        assert report["access_status_counts"]["open_fulltext"] == 1
        assert report["sources_with_publication_doi"] == 1
        assert report["sources_with_repository_doi"] == 0
        assert report["evidence_count"] == 1
        assert report["verified_page_evidence_count"] == 1
        assert report["documents_with_verified_pagination_count"] == 1
        assert report["documents_without_verified_pagination_count"] == 0
        assert report["theme_coverage"]["honeypot"] == 1
        assert report["year_range"] == {"min": 2020, "max": 2020}

    def test_report_counts_document_without_pagination(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(
            tmp_path, source_id="doi_10.9999_nosep", text="No page separators in this extraction at all."
        )
        entry = make_source_entry(source_id="doi_10.9999_nosep", raw_file=str(raw_path), sha256=sha256)
        registry = make_registry(tmp_path, [entry])
        document_seed = build_literature_document_seed(registry)
        evidence_seed = build_literature_evidence_seed(document_seed, [])
        report = build_literature_seed_report(document_seed, evidence_seed)
        assert report["documents_with_verified_pagination_count"] == 0
        assert report["documents_without_verified_pagination_count"] == 1

    def test_coverage_gaps_reported_not_invented(self, tmp_path):
        registry = make_registry(tmp_path)
        document_seed = build_literature_document_seed(registry)
        evidence_seed = build_literature_evidence_seed(document_seed, [])
        report = build_literature_seed_report(document_seed, evidence_seed)
        assert set(report["coverage_gaps"]) == set(DOCUMENTARY_THEMES) - {"honeypot", "honeytoken"}

    def test_preprint_not_counted_as_peer_reviewed(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(
            raw_file=str(raw_path), sha256=sha256, publication_type="preprint",
            peer_review_status="not_peer_reviewed",
        )
        registry = make_registry(tmp_path, [entry])
        document_seed = build_literature_document_seed(registry)
        evidence_seed = build_literature_evidence_seed(document_seed, [])
        report = build_literature_seed_report(document_seed, evidence_seed)
        assert report["peer_reviewed_count"] == 0
        assert report["not_peer_reviewed_count"] == 1
        assert report["publication_type_counts"] == {"preprint": 1}

    def test_access_status_counters_independent(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        open_entry = make_source_entry(raw_file=str(raw_path), sha256=sha256)
        metadata_entry = make_source_entry(
            source_id="venue2021_other_paper", publication_doi=None,
            access_status="metadata_only", raw_file=None, sha256=None,
        )
        abstract_entry = make_source_entry(
            source_id="venue2022_third_paper", publication_doi=None,
            access_status="abstract_only", raw_file=None, sha256=None,
        )
        unavailable_entry = make_source_entry(
            source_id="venue2023_fourth_paper", publication_doi=None,
            access_status="unavailable", raw_file=None, sha256=None,
        )
        registry = make_registry(tmp_path, [open_entry, metadata_entry, abstract_entry, unavailable_entry])
        document_seed = build_literature_document_seed(registry)
        evidence_seed = build_literature_evidence_seed(document_seed, [])
        report = build_literature_seed_report(document_seed, evidence_seed)
        assert report["open_fulltext_count"] == 1
        assert report["metadata_only_count"] == 1
        assert report["abstract_only_count"] == 1
        assert report["unavailable_count"] == 1
        assert report["source_count"] == 4

    def test_repository_doi_counted_separately_from_publication_doi(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path, source_id="arxiv_9999.00000")
        entry = make_source_entry(
            source_id="arxiv_9999.00000", publication_doi=None,
            repository_doi="10.48550/arXiv.9999.00000", repository_identifier="arXiv:9999.00000",
            raw_file=str(raw_path), sha256=sha256, publication_type="preprint",
            peer_review_status="not_peer_reviewed", metadata_provenance=make_provenance(provider="DataCite"),
        )
        registry = make_registry(tmp_path, [entry])
        document_seed = build_literature_document_seed(registry)
        evidence_seed = build_literature_evidence_seed(document_seed, [])
        report = build_literature_seed_report(document_seed, evidence_seed)
        assert report["sources_with_publication_doi"] == 0
        assert report["sources_with_repository_doi"] == 1


# ---------------------------------------------------------------------------
# H. CLI offline
# ---------------------------------------------------------------------------


class TestCli:
    def test_cli_generates_staging_and_report(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(raw_file=str(raw_path), sha256=sha256)
        registry = make_registry(tmp_path, [entry])
        registry_path = write_json(tmp_path, "literature_sources.json", registry)
        candidates_path = write_json(
            tmp_path, "evidence_candidates.json",
            {"evidence_candidates": [
                {"source_id": "doi_10.9999_fixture", "page": 2, "locator": "abstract",
                 "text": "It also covers decoy documents and attacker engagement."}
            ]},
        )
        out_dir = tmp_path / "staging"

        _run_cli(
            ["--registry", str(registry_path), "--evidence-candidates", str(candidates_path),
             "--out-dir", str(out_dir), "--version", "9.9-fixture"]
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
        assert report["verified_page_evidence_count"] == 1

    def test_cli_rejects_invalid_registry(self, tmp_path):
        raw_path, sha256 = write_fixture_raw_file(tmp_path)
        entry = make_source_entry(raw_file=str(raw_path), sha256=sha256)
        del entry["venue"]
        registry = make_registry(tmp_path, [entry])
        registry_path = write_json(tmp_path, "literature_sources.json", registry)
        candidates_path = write_json(tmp_path, "evidence_candidates.json", {"evidence_candidates": []})

        with pytest.raises(LiteratureSeedBuilderError):
            _run_cli(
                ["--registry", str(registry_path), "--evidence-candidates", str(candidates_path),
                 "--out-dir", str(tmp_path / "staging")]
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
# I. Généralité — aucune logique liée au cas d'usage de référence
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
