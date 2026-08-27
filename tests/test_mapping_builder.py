"""
Réf. architecture : CLAUDE.md §10.2 (Mapping attaque ↔ déception, M_{i,d})
— contrat technique du PFE Cyberdéception.

Tests unitaires de tools/deception_kb/mapping_builder.py (§25.4 : pytest
obligatoire). Utilise le staging D3FEND réel et le catalogue réel déjà
construits — pas une fixture synthétique présentée comme un mapping réel.
"""

import json

import pytest

from tools.deception_kb.catalog_builder import CATALOG_PATH, build_catalog, build_expanded_catalog, write_catalog
from tools.deception_kb.mapping_builder import MappingBuilderError, build_expanded_mapping, build_mapping


@pytest.fixture(scope="module", autouse=True)
def ensure_real_expanded_catalog_exists():
    """Le mapping (v1 et étendu) se construit à partir du catalogue déjà
    écrit sur disque (data/deception/deception_catalog.json) — le
    (re)génère si absent, sans jamais le fabriquer différemment de
    catalog_builder.py. Le catalogue ÉTENDU (26 mécanismes) est
    volontairement utilisé ici : build_mapping() (v1) reste correct sur ce
    catalogue car il filtre déjà sur les seuls mechanism_id présents dans
    d3fend_attack_mapping_seed."""
    if not CATALOG_PATH.exists():
        write_catalog(build_expanded_catalog())


class TestBuildMappingFromRealData:
    def test_all_relations_reference_catalog_mechanisms(self):
        catalog = build_catalog()
        catalog_ids = {m["id"] for m in catalog["mechanisms"]}
        mapping = build_mapping()
        assert all(r["mechanism_id"] in catalog_ids for r in mapping["relations"])

    def test_relation_count_matches_declared_count(self):
        mapping = build_mapping()
        assert mapping["relation_count"] == len(mapping["relations"])

    def test_no_duplicate_relations(self):
        mapping = build_mapping()
        keys = [(r["attack_id"], r["mechanism_id"]) for r in mapping["relations"]]
        assert len(keys) == len(set(keys))

    def test_multiple_evidence_preserved_for_duplicated_raw_rows(self):
        """Réf. tâche §4 : au moins une relation connue pour avoir
        plusieurs lignes brutes (D3-DUC/T1558) doit conserver plusieurs
        preuves."""
        mapping = build_mapping()
        relation = next(r for r in mapping["relations"] if r["attack_id"] == "T1558" and r["mechanism_id"] == "D3-DUC")
        assert len(relation["evidence"]) >= 2

    def test_every_relation_has_provenance(self):
        mapping = build_mapping()
        for relation in mapping["relations"]:
            assert relation["origin"]
            assert relation["evidence"]
            for evidence in relation["evidence"]:
                assert evidence["source"]
                assert evidence["source_sha256"]

    def test_no_engage_relations_included(self):
        """Réf. docstring de module (périmètre v1) : uniquement D3FEND,
        Engage explicitement hors périmètre pour cette version."""
        mapping = build_mapping()
        engage_like_ids = {r["mechanism_id"] for r in mapping["relations"] if r["mechanism_id"].startswith("EAC")}
        assert engage_like_ids == set()

    def test_deterministic(self):
        mapping_1 = build_mapping()
        mapping_2 = build_mapping()
        assert mapping_1 == mapping_2

    def test_provenance_recorded(self):
        mapping = build_mapping()
        generated_from = mapping["generated_from"]
        assert generated_from["d3fend_attack_mapping_seed"]["sha256"]
        assert generated_from["deception_catalog"]["sha256"]


class TestBuildExpandedMapping:
    """Réf. tâche §9 (reconstruire M_{i,d}, distinguer DIRECT/DÉRIVÉ) :
    tests sur le mapping étendu réel (catalogue 26 mécanismes déjà écrit
    sur disque + staging D3FEND/Engage réels)."""

    def test_relation_count_matches_declared_count(self):
        mapping = build_expanded_mapping()
        assert mapping["relation_count"] == len(mapping["relations"])

    def test_direct_and_derived_counts_sum_to_total(self):
        mapping = build_expanded_mapping()
        assert mapping["direct_relation_count"] + mapping["derived_relation_count"] == mapping["relation_count"]

    def test_every_relation_has_valid_mapping_type(self):
        mapping = build_expanded_mapping()
        for relation in mapping["relations"]:
            assert relation["mapping_type"] in ("direct", "derived")

    def test_d3fend_relations_are_derived_with_rule(self):
        mapping = build_expanded_mapping()
        d3fend_relations = [r for r in mapping["relations"] if r["mechanism_id"] in ("D3-DF", "D3-DUC", "D3-DNR")]
        assert d3fend_relations
        for relation in d3fend_relations:
            assert relation["mapping_type"] == "derived"
            assert relation["derivation_rule"]

    def test_engage_relations_are_direct_without_derivation_rule(self):
        mapping = build_expanded_mapping()
        engage_relations = [r for r in mapping["relations"] if r["mechanism_id"].startswith("EAC")]
        assert engage_relations
        for relation in engage_relations:
            assert relation["mapping_type"] == "direct"
            assert relation["derivation_rule"] is None

    def test_no_orphan_relation_all_mechanism_ids_in_catalog(self):
        catalog = build_expanded_catalog()
        catalog_ids = {m["id"] for m in catalog["mechanisms"]}
        mapping = build_expanded_mapping()
        for relation in mapping["relations"]:
            assert relation["mechanism_id"] in catalog_ids

    def test_extended_d3fend_and_literature_mechanisms_have_no_relations(self):
        """Réf. §9 : aucune relation n'est fabriquée pour les mécanismes
        sans preuve documentaire de relation ATT&CK dans les stagings
        disponibles (limite documentée, jamais comblée artificiellement)."""
        mapping = build_expanded_mapping()
        mechanism_ids_with_relations = {r["mechanism_id"] for r in mapping["relations"]}
        for mechanism_id in ("D3-DP", "D3-DST", "D3-DPR", "D3-CHN", "D3-SHN", "D3-IHN", "LIT-HONEYPOT", "LIT-HONEYTOKEN"):
            assert mechanism_id not in mechanism_ids_with_relations

    def test_no_duplicate_relations(self):
        mapping = build_expanded_mapping()
        keys = [(r["attack_id"], r["mechanism_id"]) for r in mapping["relations"]]
        assert len(keys) == len(set(keys))

    def test_every_relation_has_provenance(self):
        mapping = build_expanded_mapping()
        for relation in mapping["relations"]:
            assert relation["origin"]
            assert relation["evidence"]

    def test_more_relations_than_v1(self):
        v1_mapping = build_mapping()
        expanded_mapping = build_expanded_mapping()
        assert expanded_mapping["relation_count"] > v1_mapping["relation_count"]

    def test_more_distinct_attack_techniques_covered_than_v1(self):
        v1_mapping = build_mapping()
        expanded_mapping = build_expanded_mapping()
        v1_techniques = {r["attack_id"] for r in v1_mapping["relations"]}
        expanded_techniques = {r["attack_id"] for r in expanded_mapping["relations"]}
        assert len(expanded_techniques) > len(v1_techniques)

    def test_deterministic(self):
        mapping_1 = build_expanded_mapping()
        mapping_2 = build_expanded_mapping()
        assert mapping_1 == mapping_2

    def test_provenance_recorded(self):
        mapping = build_expanded_mapping()
        generated_from = mapping["generated_from"]
        assert generated_from["d3fend_attack_mapping_seed"]["sha256"]
        assert generated_from["engage_attack_mapping_seed"]["sha256"]
        assert generated_from["deception_catalog"]["sha256"]


class TestBuildMappingErrorHandling:
    def test_empty_catalog_raises(self, tmp_path):
        empty_catalog = {"catalog_version": "v0", "mechanisms": []}
        catalog_path = tmp_path / "empty_catalog.json"
        catalog_path.write_text(json.dumps(empty_catalog), encoding="utf-8")

        with pytest.raises(MappingBuilderError):
            build_mapping(catalog_path=catalog_path)

    def test_catalog_with_unmapped_mechanism_raises(self, tmp_path):
        unmapped_catalog = {"catalog_version": "v0", "mechanisms": [{"id": "D3-NOT-REAL"}]}
        catalog_path = tmp_path / "unmapped_catalog.json"
        catalog_path.write_text(json.dumps(unmapped_catalog), encoding="utf-8")

        with pytest.raises(MappingBuilderError):
            build_mapping(catalog_path=catalog_path)
