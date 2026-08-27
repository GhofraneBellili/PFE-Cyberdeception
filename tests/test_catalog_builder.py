"""
Réf. architecture : CLAUDE.md §9.1 (pipeline de construction de la KB
déception) — contrat technique du PFE Cyberdéception.

Tests unitaires de tools/deception_kb/catalog_builder.py (§25.4 : pytest
obligatoire). Utilise le staging D3FEND réel déjà versionné
(data/deception/staging/) — pas une fixture synthétique présentée comme
un catalogue réel.
"""

import pytest

from src.schemas import DeceptionMechanism
from tools.deception_kb.catalog_builder import CatalogBuilderError, build_catalog


class TestBuildCatalogFromRealStaging:
    def test_only_leaf_concepts_with_direct_attack_mapping_are_included(self):
        catalog = build_catalog()
        mechanism_ids = {m["id"] for m in catalog["mechanisms"]}
        assert mechanism_ids == {"D3-DF", "D3-DUC", "D3-DNR"}

    def test_parent_concepts_excluded_with_reason(self):
        catalog = build_catalog()
        excluded_ids = {e["id"]: e["reason"] for e in catalog["excluded_concepts"]}
        assert "is_leaf=false" in excluded_ids["D3-DO"]
        assert "is_leaf=false" in excluded_ids["D3-DE"]

    def test_leaves_without_attack_mapping_excluded_with_reason(self):
        catalog = build_catalog()
        excluded_ids = {e["id"]: e["reason"] for e in catalog["excluded_concepts"]}
        for leaf_id in ("D3-DP", "D3-DST", "D3-DPR", "D3-CHN", "D3-SHN", "D3-IHN"):
            assert leaf_id in excluded_ids
            assert "ATT&CK" in excluded_ids[leaf_id]

    def test_every_mechanism_validates_against_schema(self):
        catalog = build_catalog()
        for raw_mechanism in catalog["mechanisms"]:
            mechanism = DeceptionMechanism.model_validate(raw_mechanism)
            assert mechanism.id == raw_mechanism["id"]

    def test_every_mechanism_has_nonempty_evidence(self):
        catalog = build_catalog()
        for raw_mechanism in catalog["mechanisms"]:
            assert len(raw_mechanism["evidence"]) > 0

    def test_admissibility_profile_required_fields_left_empty(self):
        """Réf. docstring de module : aucune preuve documentaire ne
        justifie required_asset_types/services/artifacts — laissés vides,
        jamais inventés."""
        catalog = build_catalog()
        for raw_mechanism in catalog["mechanisms"]:
            profile = raw_mechanism["admissibility_profile"]
            assert profile["required_asset_types"] == []
            assert profile["required_services"] == []
            assert profile["required_artifacts"] == []

    def test_progression_effects_left_empty(self):
        """Réf. docstring de module : progression_effects appartient au
        modèle du chapitre 3 (SP2), pas à D3FEND — jamais inventé ici."""
        catalog = build_catalog()
        for raw_mechanism in catalog["mechanisms"]:
            assert raw_mechanism["progression_effects"] == []

    def test_interaction_mechanism_derived_from_real_relations(self):
        catalog = build_catalog()
        duc = next(m for m in catalog["mechanisms"] if m["id"] == "D3-DUC")
        assert "accesses" in duc["interaction_mechanism"]

    def test_location_type_derived_from_artifact(self):
        catalog = build_catalog()
        duc = next(m for m in catalog["mechanisms"] if m["id"] == "D3-DUC")
        assert duc["admissibility_profile"]["allowed_location_types"] == ["credential_store"]
        df = next(m for m in catalog["mechanisms"] if m["id"] == "D3-DF")
        assert df["admissibility_profile"]["allowed_location_types"] == ["filesystem"]
        dnr = next(m for m in catalog["mechanisms"] if m["id"] == "D3-DNR")
        assert dnr["admissibility_profile"]["allowed_location_types"] == ["network_resource"]

    def test_provenance_recorded(self):
        catalog = build_catalog()
        generated_from = catalog["generated_from"]
        assert generated_from["d3fend_deception_seed"]["sha256"]
        assert generated_from["d3fend_attack_mapping_seed"]["sha256"]
        assert catalog["catalog_version"]

    def test_deterministic(self):
        catalog_1 = build_catalog()
        catalog_2 = build_catalog()
        assert catalog_1 == catalog_2


class TestBuildCatalogMissingMappings:
    def test_raises_if_no_mechanism_survives(self, tmp_path):
        import json

        empty_seed = {
            "release_version": "1.5.0",
            "concepts": [
                {
                    "source_technique_id": "D3-XX",
                    "name": "X",
                    "definition": "def",
                    "is_leaf": True,
                    "artifacts": [],
                    "source_evidence": [],
                }
            ],
        }
        empty_mapping = {"release_version": "1.5.0", "mappings": []}
        seed_path = tmp_path / "seed.json"
        mapping_path = tmp_path / "mapping.json"
        seed_path.write_text(json.dumps(empty_seed), encoding="utf-8")
        mapping_path.write_text(json.dumps(empty_mapping), encoding="utf-8")

        with pytest.raises(CatalogBuilderError):
            build_catalog(deception_seed_path=seed_path, attack_mapping_path=mapping_path)
