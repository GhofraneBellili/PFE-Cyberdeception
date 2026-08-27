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
from tools.deception_kb.catalog_builder import CatalogBuilderError, build_catalog, build_expanded_catalog


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

    def test_admissibility_profile_required_fields_left_empty_unless_audited(self):
        """Réf. docstring de module + docs/chapter4/ADMISSIBILITY_EVIDENCE_AUDIT.md :
        required_services/required_artifacts restent vides pour tous les
        mécanismes (aucune preuve) ; required_asset_types reste vide sauf
        pour D3-DNR (seul cas où l'audit a trouvé une preuve documentaire
        directe — jamais inventé)."""
        catalog = build_catalog()
        for raw_mechanism in catalog["mechanisms"]:
            profile = raw_mechanism["admissibility_profile"]
            assert profile["required_services"] == []
            assert profile["required_artifacts"] == []
            if raw_mechanism["id"] == "D3-DNR":
                assert profile["required_asset_types"] == ["file_server", "web_application_server"]
            else:
                assert profile["required_asset_types"] == []

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
        # Réf. audit : "made available as a local or network resource" (kb-article)
        # -> network_share ajouté en complément de filesystem (dérivé de target_artifacts).
        assert df["admissibility_profile"]["allowed_location_types"] == ["filesystem", "network_share"]
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


class TestBuildExpandedCatalog:
    """Réf. tâche « étendre le catalogue à >= 25 mécanismes réels » (§4-§8) :
    tests sur le catalogue étendu réel (D3FEND + MITRE Engage + littérature
    déjà versionnés), pas une fixture synthétique."""

    def test_at_least_25_mechanisms(self):
        catalog = build_expanded_catalog()
        assert len(catalog["mechanisms"]) >= 25

    def test_all_ids_unique(self):
        catalog = build_expanded_catalog()
        ids = [m["id"] for m in catalog["mechanisms"]]
        assert len(ids) == len(set(ids))

    def test_all_names_non_empty(self):
        catalog = build_expanded_catalog()
        for mechanism in catalog["mechanisms"]:
            assert mechanism["name"].strip()

    def test_no_exact_name_and_description_duplication(self):
        """Réf. §8 (audit de déduplication) : deux mécanismes distincts ne
        doivent jamais partager exactement le même (name, description) —
        signe d'une fiche dupliquée plutôt que fusionnée."""
        catalog = build_expanded_catalog()
        pairs = [(m["name"], m["description"]) for m in catalog["mechanisms"]]
        assert len(pairs) == len(set(pairs))

    def test_every_mechanism_has_at_least_one_evidence(self):
        catalog = build_expanded_catalog()
        for mechanism in catalog["mechanisms"]:
            assert len(mechanism["evidence"]) > 0, f"{mechanism['id']} sans preuve"

    def test_every_mechanism_validates_against_schema(self):
        catalog = build_expanded_catalog()
        for raw_mechanism in catalog["mechanisms"]:
            mechanism = DeceptionMechanism.model_validate(raw_mechanism)
            assert mechanism.id == raw_mechanism["id"]

    def test_v1_three_mechanisms_still_present_unchanged(self):
        """Le périmètre v1 (build_catalog) doit rester un sous-ensemble
        inchangé de l'extension, jamais recalculé différemment."""
        base = build_catalog()
        expanded = build_expanded_catalog()
        expanded_by_id = {m["id"]: m for m in expanded["mechanisms"]}
        for mechanism in base["mechanisms"]:
            assert expanded_by_id[mechanism["id"]] == mechanism

    def test_persona_merged_not_duplicated(self):
        """Réf. §8 : EAC0012 (Personas) est fusionné dans D3-DP, jamais un
        id de catalogue séparé."""
        catalog = build_expanded_catalog()
        ids = {m["id"] for m in catalog["mechanisms"]}
        assert "EAC0012" not in ids
        assert "D3-DP" in ids
        excluded_ids = {e["id"] for e in catalog["excluded_concepts"]}
        assert "EAC0012" in excluded_ids

    def test_engage_strategic_activities_all_excluded(self):
        """Réf. §6 : les activités MITRE Engage de type Strategic (SAC*)
        ne sont jamais des mécanismes déployables."""
        catalog = build_expanded_catalog()
        ids = {m["id"] for m in catalog["mechanisms"]}
        assert not any(mechanism_id.startswith("SAC") for mechanism_id in ids)

    def test_every_excluded_concept_has_a_reason(self):
        catalog = build_expanded_catalog()
        for excluded in catalog["excluded_concepts"]:
            assert excluded["reason"].strip()

    def test_provenance_recorded_for_all_four_sources(self):
        catalog = build_expanded_catalog()
        generated_from = catalog["generated_from"]
        for key in ("d3fend_deception_seed", "d3fend_attack_mapping_seed", "engage_activity_seed", "literature_evidence_seed"):
            assert generated_from[key]["sha256"]

    def test_deterministic(self):
        catalog_1 = build_expanded_catalog()
        catalog_2 = build_expanded_catalog()
        assert catalog_1 == catalog_2

    def test_mechanism_families_present(self):
        """Réf. §10 (statistiques de couverture) : au moins D3FEND, Engage
        et littérature sont représentés parmi les mécanismes catalogués."""
        catalog = build_expanded_catalog()
        ids = {m["id"] for m in catalog["mechanisms"]}
        assert any(mechanism_id.startswith("D3-") for mechanism_id in ids)
        assert any(mechanism_id.startswith("EAC") for mechanism_id in ids)
        assert any(mechanism_id.startswith("LIT-") for mechanism_id in ids)


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
