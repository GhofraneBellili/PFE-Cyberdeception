"""
Réf. architecture : CLAUDE.md — contrat technique du PFE Cyberdéception.

Tests unitaires de tools/deception_kb/d3fend_seed_builder.py (§25.4 : pytest
obligatoire).

Tous les fichiers utilisés ici sont des fixtures STIX/JSON-LD synthétiques
créées dans tmp_path : la CI ne dépend ni d'Internet, ni du vrai D3FEND
1.5.0. Les noms de concepts utilisés (ExampleLureRoot, ...) sont
volontairement fictifs et différents à la fois du cas de référence PFE
(T1003, T1078, DC, WS, DB) et des vrais noms de classes D3FEND, afin de
démontrer que le parseur ne contient aucune logique spécifique à un
ensemble de techniques particulier.
"""

import hashlib
import json
from pathlib import Path

import pytest

from tools.deception_kb.d3fend_seed_builder import (
    D3fendSeedBuilderError,
    _run_cli,
    build_d3fend_attack_mapping_seed,
    build_d3fend_deception_seed,
    build_manifest_entry,
    build_seed_report,
    build_source_manifest,
    validate_attack_mapping_seed,
    validate_deception_seed,
)

D3F_BASE = "http://d3fend.mitre.org/ontologies/d3fend.owl#"

# ---------------------------------------------------------------------------
# Fixtures synthétiques
# ---------------------------------------------------------------------------


def make_ontology_graph(*, duplicate_d3fend_id=False):
    """Ontologie JSON-LD synthétique reproduisant fidèlement les motifs
    réels observés dans D3FEND 1.5.0 : @graph, d3f:enables, rdfs:subClassOf
    avec restrictions OWL (nœuds blancs), d3f:kb-article, d3f:kb-reference,
    d3f:spoofs, hiérarchie sur plusieurs niveaux."""
    graph = [
        {
            "@id": "d3f:Deceive",
            "@type": ["owl:Class", "owl:NamedIndividual", "d3f:DefensiveTactic"],
            "d3f:definition": "Fixture deceive tactic.",
            "rdfs:label": "Deceive",
            "rdfs:subClassOf": {"@id": "d3f:DefensiveTactic"},
        },
        {
            "@id": "d3f:Harden",
            "@type": ["owl:Class", "d3f:DefensiveTactic"],
            "rdfs:label": "Harden",
        },
        # Technique appartenant à une AUTRE tactique : doit être exclue.
        {
            "@id": "d3f:UnrelatedTechnique",
            "@type": ["owl:Class", "d3f:DefensiveTechnique"],
            "d3f:d3fend-id": "D3-UT",
            "d3f:enables": {"@id": "d3f:Harden"},
            "rdfs:label": "Unrelated Technique",
            "rdfs:subClassOf": [{"@id": "d3f:DefensiveTechnique"}],
        },
        # Racine de la branche Deceive (motif réel : enables direct +
        # restriction OWL équivalente).
        {
            "@id": "d3f:ExampleLureRoot",
            "@type": ["owl:Class", "owl:NamedIndividual", "d3f:ExampleLureRoot"],
            "d3f:d3fend-id": "D3-ELR",
            "d3f:definition": "Fixture root lure technique.",
            "d3f:kb-article": "## Technique Overview\nFixture overview text.",
            "d3f:enables": {"@id": "d3f:Deceive"},
            "d3f:synonym": "FixtureSynonym",
            "rdfs:label": "Example Lure Root",
            "rdfs:subClassOf": [
                {"@id": "d3f:DefensiveTechnique"},
                {"@id": "_:restrictionBlank1"},
            ],
        },
        {
            "@id": "_:restrictionBlank1",
            "@type": "owl:Restriction",
            "owl:onProperty": {"@id": "d3f:enables"},
            "owl:someValuesFrom": {"@id": "d3f:Deceive"},
        },
        # Enfant direct (non-leaf : possède lui-même un enfant plus bas).
        {
            "@id": "d3f:ExampleLureChildA",
            "@type": ["owl:Class"],
            "d3f:d3fend-id": "D3-ELCA-DUP" if duplicate_d3fend_id else "D3-ELCA",
            "d3f:definition": "Fixture child A definition.",
            "d3f:kb-article": "## How it works\nFixture child A article.",
            "d3f:spoofs": {"@id": "d3f:ExampleArtifact"},
            "d3f:kb-reference": {"@id": "d3f:Reference-FixtureRefA"},
            "rdfs:label": "Example Lure Child A",
            "rdfs:subClassOf": [{"@id": "d3f:ExampleLureRoot"}],
        },
        # Petit-enfant (feuille réelle).
        {
            "@id": "d3f:ExampleLureGrandchild",
            "@type": ["owl:Class"],
            "d3f:d3fend-id": "D3-ELG",
            "d3f:definition": "Fixture grandchild definition.",
            "rdfs:label": "Example Lure Grandchild",
            "rdfs:subClassOf": [{"@id": "d3f:ExampleLureChildA"}],
        },
        {
            "@id": "d3f:Reference-FixtureRefA",
            "@type": ["owl:NamedIndividual", "d3f:InternetArticleReference"],
            "d3f:kb-reference-title": "Fixture Reference Title",
            "d3f:has-link": {"@type": "xsd:anyURI", "@value": "https://example.org/fixture-ref"},
            "d3f:kb-author": "Fixture Author",
            "d3f:kb-organization": "Fixture Org",
            "rdfs:label": "Reference - Fixture",
        },
    ]
    if duplicate_d3fend_id:
        # Second nœud @id distinct partageant le même d3fend-id qu'un autre
        # concept de la branche : doit être détecté comme doublon.
        graph.append(
            {
                "@id": "d3f:ExampleLureChildB",
                "@type": ["owl:Class"],
                "d3f:d3fend-id": "D3-ELCA-DUP",
                "d3f:definition": "Fixture duplicate id child.",
                "rdfs:label": "Example Lure Child B",
                "rdfs:subClassOf": [{"@id": "d3f:ExampleLureRoot"}],
            }
        )
    return {
        "@context": {
            "d3f": D3F_BASE,
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "owl": "http://www.w3.org/2002/07/owl#",
        },
        "@graph": graph,
    }


def write_ontology(tmp_path, filename="ontology.json", **kwargs):
    payload = make_ontology_graph(**kwargs)
    path = tmp_path / filename
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def make_binding(def_tech_local, attack_id, *, framework_key="enterprise", **overrides):
    binding = {
        "def_tech": {"type": "uri", "value": f"{D3F_BASE}{def_tech_local}"},
        "def_tech_label": {"type": "literal", "value": def_tech_local},
        "off_tech_id": {"type": "literal", "value": attack_id},
        "off_tech_label": {"type": "literal", "value": "Fixture Offensive Technique"},
        "def_artifact_rel_label": {"type": "literal", "value": "fixture-def-relation"},
        "def_artifact_label": {"type": "literal", "value": "Fixture Artifact"},
        "off_artifact_rel_label": {"type": "literal", "value": "fixture-off-relation"},
        "framework_key": {"type": "literal", "value": framework_key},
    }
    binding.update(overrides)
    return binding


def write_mappings(tmp_path, bindings, filename="mappings.json"):
    payload = {"head": {"vars": []}, "results": {"bindings": bindings}}
    path = tmp_path / filename
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# A. Chargement / construction du seed de concepts
# ---------------------------------------------------------------------------


class TestDeceptionSeedBuilding:
    def test_valid_synthetic_source_builds_seed(self, tmp_path):
        path = write_ontology(tmp_path)
        seed = build_d3fend_deception_seed(path, release_version="9.9.9-fixture")
        assert seed["schema"] == "d3fend_deception_seed"
        assert seed["release_version"] == "9.9.9-fixture"
        assert len(seed["concepts"]) == 3  # root + child + grandchild

    def test_hierarchy_reconstructed(self, tmp_path):
        path = write_ontology(tmp_path)
        seed = build_d3fend_deception_seed(path, release_version="9.9.9-fixture")
        by_id = {c["source_technique_id"]: c for c in seed["concepts"]}
        assert by_id["D3-ELR"]["parent_ids"] == []
        assert by_id["D3-ELCA"]["parent_ids"] == ["D3-ELR"]
        assert by_id["D3-ELG"]["parent_ids"] == ["D3-ELCA"]

    def test_deceive_descendants_only_unrelated_excluded(self, tmp_path):
        path = write_ontology(tmp_path)
        seed = build_d3fend_deception_seed(path, release_version="9.9.9-fixture")
        ids = {c["source_technique_id"] for c in seed["concepts"]}
        assert ids == {"D3-ELR", "D3-ELCA", "D3-ELG"}
        assert "D3-UT" not in ids  # appartient à Harden, pas à Deceive

    def test_parent_and_child_ids_consistent(self, tmp_path):
        path = write_ontology(tmp_path)
        seed = build_d3fend_deception_seed(path, release_version="9.9.9-fixture")
        by_id = {c["source_technique_id"]: c for c in seed["concepts"]}
        assert by_id["D3-ELR"]["child_ids"] == ["D3-ELCA"]
        assert by_id["D3-ELCA"]["child_ids"] == ["D3-ELG"]
        assert by_id["D3-ELG"]["child_ids"] == []

    def test_is_leaf_correct_at_each_level(self, tmp_path):
        path = write_ontology(tmp_path)
        seed = build_d3fend_deception_seed(path, release_version="9.9.9-fixture")
        by_id = {c["source_technique_id"]: c for c in seed["concepts"]}
        assert by_id["D3-ELR"]["is_leaf"] is False
        assert by_id["D3-ELCA"]["is_leaf"] is False
        assert by_id["D3-ELG"]["is_leaf"] is True

    def test_duplicate_d3fend_id_rejected_by_validation(self, tmp_path):
        path = write_ontology(tmp_path, duplicate_d3fend_id=True)
        seed = build_d3fend_deception_seed(path, release_version="9.9.9-fixture")
        with pytest.raises(D3fendSeedBuilderError):
            validate_deception_seed(seed)

    def test_provenance_conserved(self, tmp_path):
        path = write_ontology(tmp_path)
        seed = build_d3fend_deception_seed(path, release_version="9.9.9-fixture")
        by_id = {c["source_technique_id"]: c for c in seed["concepts"]}
        evidence = by_id["D3-ELR"]["source_evidence"]
        assert len(evidence) >= 1
        definition_evidence = next(e for e in evidence if e["source_property"] == "d3f:definition")
        assert definition_evidence["evidence_text"] == "Fixture root lure technique."
        assert definition_evidence["source_entity"] == "d3f:ExampleLureRoot"
        assert definition_evidence["source_file"] == "d3fend.json"
        assert definition_evidence["source_sha256"] == seed["source_sha256"]

    def test_references_resolved(self, tmp_path):
        path = write_ontology(tmp_path)
        seed = build_d3fend_deception_seed(path, release_version="9.9.9-fixture")
        by_id = {c["source_technique_id"]: c for c in seed["concepts"]}
        refs = by_id["D3-ELCA"]["references"]
        assert refs == [
            {
                "title": "Fixture Reference Title",
                "url": "https://example.org/fixture-ref",
                "author": "Fixture Author",
                "organization": "Fixture Org",
            }
        ]

    def test_source_hash_matches_file_bytes(self, tmp_path):
        path = write_ontology(tmp_path)
        seed = build_d3fend_deception_seed(path, release_version="9.9.9-fixture")
        expected = hashlib.sha256(path.read_bytes()).hexdigest()
        assert seed["source_sha256"] == expected

    def test_invalid_root_rejected(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({"not": "a graph"}), encoding="utf-8")
        with pytest.raises(D3fendSeedBuilderError):
            build_d3fend_deception_seed(path, release_version="9.9.9-fixture")


# ---------------------------------------------------------------------------
# B. Mappings D3FEND -> ATT&CK
# ---------------------------------------------------------------------------


class TestAttackMappingSeed:
    def _deception_seed(self, tmp_path):
        return build_d3fend_deception_seed(write_ontology(tmp_path), release_version="9.9.9-fixture")

    def test_attack_mapping_extracted(self, tmp_path):
        deception_seed = self._deception_seed(tmp_path)
        bindings = [make_binding("ExampleLureChildA", "T9001")]
        path = write_mappings(tmp_path, bindings)
        mapping_seed = build_d3fend_attack_mapping_seed(
            path, deception_seed, release_version="9.9.9-fixture", d3fend_iri_base=D3F_BASE
        )
        assert len(mapping_seed["mappings"]) == 1
        entry = mapping_seed["mappings"][0]
        assert entry["d3fend_id"] == "D3-ELCA"
        assert entry["attack_id"] == "T9001"
        assert entry["origin"] == "d3fend_inferred"
        assert "confidence" not in entry  # aucune confiance inventée (réf. §12)

    def test_mapping_outside_seed_filtered(self, tmp_path):
        """Une technique D3FEND absente du seed (ex. hors branche Deceive)
        est silencieusement exclue par la construction : règle documentée
        dans build_d3fend_attack_mapping_seed."""
        deception_seed = self._deception_seed(tmp_path)
        bindings = [
            make_binding("ExampleLureChildA", "T9001"),
            make_binding("UnrelatedTechnique", "T9002"),
        ]
        path = write_mappings(tmp_path, bindings)
        mapping_seed = build_d3fend_attack_mapping_seed(
            path, deception_seed, release_version="9.9.9-fixture", d3fend_iri_base=D3F_BASE
        )
        attack_ids = {m["attack_id"] for m in mapping_seed["mappings"]}
        assert attack_ids == {"T9001"}

    def test_non_enterprise_framework_filtered(self, tmp_path):
        """framework_key différent de 'enterprise' (ex. 'sparta') est
        exclu : périmètre ATT&CK Enterprise de CLAUDE.md §8."""
        deception_seed = self._deception_seed(tmp_path)
        bindings = [
            make_binding("ExampleLureChildA", "T9001", framework_key="enterprise"),
            make_binding("ExampleLureChildA", "PER-0005", framework_key="sparta"),
        ]
        path = write_mappings(tmp_path, bindings)
        mapping_seed = build_d3fend_attack_mapping_seed(
            path, deception_seed, release_version="9.9.9-fixture", d3fend_iri_base=D3F_BASE
        )
        assert [m["attack_id"] for m in mapping_seed["mappings"]] == ["T9001"]

    def test_validate_rejects_mapping_referencing_technique_outside_seed(self, tmp_path):
        deception_seed = self._deception_seed(tmp_path)
        rogue_mapping_seed = {
            "mappings": [
                {
                    "d3fend_id": "D3-GHOST",
                    "attack_id": "T9001",
                    "source_sha256": "a" * 64,
                }
            ]
        }
        with pytest.raises(D3fendSeedBuilderError):
            validate_attack_mapping_seed(rogue_mapping_seed, deception_seed)

    def test_validate_rejects_malformed_attack_id(self, tmp_path):
        deception_seed = self._deception_seed(tmp_path)
        bad_mapping_seed = {
            "mappings": [
                {
                    "d3fend_id": "D3-ELCA",
                    "attack_id": "not-an-attack-id",
                    "source_sha256": "a" * 64,
                }
            ]
        }
        with pytest.raises(D3fendSeedBuilderError):
            validate_attack_mapping_seed(bad_mapping_seed, deception_seed)

    def test_validate_accepts_well_formed_mapping_seed(self, tmp_path):
        deception_seed = self._deception_seed(tmp_path)
        bindings = [make_binding("ExampleLureChildA", "T9001.001")]
        path = write_mappings(tmp_path, bindings)
        mapping_seed = build_d3fend_attack_mapping_seed(
            path, deception_seed, release_version="9.9.9-fixture", d3fend_iri_base=D3F_BASE
        )
        validate_attack_mapping_seed(mapping_seed, deception_seed)  # ne doit pas lever


# ---------------------------------------------------------------------------
# B (durcissement). Déduplication documentaire des mappings
# ---------------------------------------------------------------------------


class TestDeduplication:
    def _deception_seed(self, tmp_path):
        return build_d3fend_deception_seed(write_ontology(tmp_path), release_version="9.9.9-fixture")

    def test_exact_duplicate_bindings_deduplicated(self, tmp_path):
        deception_seed = self._deception_seed(tmp_path)
        bindings = [
            make_binding("ExampleLureChildA", "T9001"),
            make_binding("ExampleLureChildA", "T9001"),  # strictement identique
        ]
        path = write_mappings(tmp_path, bindings)
        mapping_seed = build_d3fend_attack_mapping_seed(
            path, deception_seed, release_version="9.9.9-fixture", d3fend_iri_base=D3F_BASE
        )
        assert mapping_seed["raw_binding_count"] == 2
        assert mapping_seed["unique_relation_count"] == 1
        assert len(mapping_seed["mappings"]) == 1

    def test_different_relation_path_both_kept(self, tmp_path):
        """Même d3fend_id + même attack_id, mais un chemin d'artefacts
        différent : ce sont deux preuves documentaires distinctes, jamais
        fusionnées."""
        deception_seed = self._deception_seed(tmp_path)
        bindings = [
            make_binding(
                "ExampleLureChildA",
                "T9001",
                def_artifact_rel_label={"type": "literal", "value": "relation-A"},
            ),
            make_binding(
                "ExampleLureChildA",
                "T9001",
                def_artifact_rel_label={"type": "literal", "value": "relation-B"},
            ),
        ]
        path = write_mappings(tmp_path, bindings)
        mapping_seed = build_d3fend_attack_mapping_seed(
            path, deception_seed, release_version="9.9.9-fixture", d3fend_iri_base=D3F_BASE
        )
        assert mapping_seed["raw_binding_count"] == 2
        assert mapping_seed["unique_relation_count"] == 2
        assert len(mapping_seed["mappings"]) == 2

    def test_multiple_relations_same_pair_counted_once(self, tmp_path):
        deception_seed = self._deception_seed(tmp_path)
        bindings = [
            make_binding(
                "ExampleLureChildA",
                "T9001",
                def_artifact_rel_label={"type": "literal", "value": "relation-A"},
            ),
            make_binding(
                "ExampleLureChildA",
                "T9001",
                def_artifact_rel_label={"type": "literal", "value": "relation-B"},
            ),
        ]
        path = write_mappings(tmp_path, bindings)
        mapping_seed = build_d3fend_attack_mapping_seed(
            path, deception_seed, release_version="9.9.9-fixture", d3fend_iri_base=D3F_BASE
        )
        assert mapping_seed["unique_relation_count"] == 2
        assert mapping_seed["unique_d3fend_attack_pair_count"] == 1

    def test_order_preserved_first_occurrence_kept(self, tmp_path):
        deception_seed = self._deception_seed(tmp_path)
        bindings = [
            make_binding("ExampleLureChildA", "T9001"),
            make_binding("ExampleLureChildA", "T9002"),
            make_binding("ExampleLureChildA", "T9001"),  # doublon du premier
        ]
        path = write_mappings(tmp_path, bindings)
        mapping_seed = build_d3fend_attack_mapping_seed(
            path, deception_seed, release_version="9.9.9-fixture", d3fend_iri_base=D3F_BASE
        )
        assert [m["attack_id"] for m in mapping_seed["mappings"]] == ["T9001", "T9002"]

    def test_validate_rejects_exact_duplicate_relation(self, tmp_path):
        deception_seed = self._deception_seed(tmp_path)
        relation_path = {
            "def_artifact_relation": "relation-A",
            "shared_artifact": "Fixture Artifact",
            "off_artifact_relation": "fixture-off-relation",
        }
        duplicated_entry = {
            "d3fend_id": "D3-ELCA",
            "attack_id": "T9001",
            "relation_path": relation_path,
            "framework": "enterprise",
            "source": "fixture",
            "source_sha256": "a" * 64,
            "origin": "d3fend_inferred",
        }
        corrupted_mapping_seed = {"mappings": [duplicated_entry, dict(duplicated_entry)]}
        with pytest.raises(D3fendSeedBuilderError):
            validate_attack_mapping_seed(corrupted_mapping_seed, deception_seed)

    def test_validate_accepts_same_pair_different_relation_path(self, tmp_path):
        """Ne rejette jamais deux relations qui partagent seulement
        (d3fend_id, attack_id) si leur relation_path diffère."""
        deception_seed = self._deception_seed(tmp_path)
        base_entry = {
            "d3fend_id": "D3-ELCA",
            "attack_id": "T9001",
            "framework": "enterprise",
            "source": "fixture",
            "source_sha256": "a" * 64,
            "origin": "d3fend_inferred",
        }
        entry_a = {
            **base_entry,
            "relation_path": {
                "def_artifact_relation": "relation-A",
                "shared_artifact": "Artifact",
                "off_artifact_relation": "off-relation",
            },
        }
        entry_b = {
            **base_entry,
            "relation_path": {
                "def_artifact_relation": "relation-B",
                "shared_artifact": "Artifact",
                "off_artifact_relation": "off-relation",
            },
        }
        mapping_seed = {"mappings": [entry_a, entry_b]}
        validate_attack_mapping_seed(mapping_seed, deception_seed)  # ne doit pas lever


# ---------------------------------------------------------------------------
# C. Déterminisme
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_output_order_deterministic(self, tmp_path):
        path = write_ontology(tmp_path)
        seed = build_d3fend_deception_seed(path, release_version="9.9.9-fixture")
        ids = [c["source_technique_id"] for c in seed["concepts"]]
        assert ids == ["D3-ELR", "D3-ELCA", "D3-ELG"]

    def test_same_input_same_output(self, tmp_path):
        path = write_ontology(tmp_path)
        seed_a = build_d3fend_deception_seed(path, release_version="9.9.9-fixture")
        seed_b = build_d3fend_deception_seed(path, release_version="9.9.9-fixture")
        assert seed_a == seed_b


# ---------------------------------------------------------------------------
# D. Rapport et manifest
# ---------------------------------------------------------------------------


class TestReportAndManifest:
    def test_seed_report_counts(self, tmp_path):
        deception_seed = build_d3fend_deception_seed(
            write_ontology(tmp_path), release_version="9.9.9-fixture"
        )
        bindings = [make_binding("ExampleLureChildA", "T9001")]
        mapping_seed = build_d3fend_attack_mapping_seed(
            write_mappings(tmp_path, bindings),
            deception_seed,
            release_version="9.9.9-fixture",
            d3fend_iri_base=D3F_BASE,
        )
        report = build_seed_report(deception_seed, mapping_seed, manifest_entries=[])
        assert report["concept_count"] == 3
        assert report["leaf_count"] == 1
        assert report["parent_count"] == 2
        assert report["raw_attack_binding_count"] == 1
        assert report["unique_attack_relation_count"] == 1
        assert report["unique_d3fend_attack_pair_count"] == 1
        assert report["extracted_ids"] == ["D3-ELCA", "D3-ELG", "D3-ELR"]

    def test_source_manifest_structure(self):
        manifest = build_source_manifest(
            [
                {
                    "source_id": "fixture-source",
                    "provider": "MITRE",
                    "sha256": "a" * 64,
                }
            ]
        )
        assert manifest["schema"] == "deception_source_manifest"
        assert manifest["sources"][0]["provider"] == "MITRE"

    def test_manifest_entry_hashes_match_seed_hashes(self, tmp_path):
        """§13.C : construit le manifest avec des URLs et une date
        synthétiques, mais les hashes réels des fixtures — vérifie la
        cohérence manifest <-> seed/mapping_seed exigée par le durcissement
        §11."""
        ontology_path = write_ontology(tmp_path)
        deception_seed = build_d3fend_deception_seed(ontology_path, release_version="9.9.9-fixture")
        mappings_path = write_mappings(tmp_path, [make_binding("ExampleLureChildA", "T9001")])
        mapping_seed = build_d3fend_attack_mapping_seed(
            mappings_path, deception_seed, release_version="9.9.9-fixture", d3fend_iri_base=D3F_BASE
        )

        ontology_entry = build_manifest_entry(
            source_id="fixture-ontology",
            source_name="Fixture Ontology",
            release_version="9.9.9-fixture",
            official_url="https://example.org/fixture/d3fend.json",
            local_filename=str(ontology_path),
            sha256=deception_seed["source_sha256"],
            source_type="json-ld",
            retrieval_date="2026-01-15",
            role="ontology",
        )
        mappings_entry = build_manifest_entry(
            source_id="fixture-mappings",
            source_name="Fixture Mappings",
            release_version="9.9.9-fixture",
            official_url="https://example.org/fixture/mappings.json",
            local_filename=str(mappings_path),
            sha256=mapping_seed["source_sha256"],
            source_type="sparql-results-json",
            retrieval_date="2026-01-15",
            role="inferred_mappings",
        )
        manifest = build_source_manifest([ontology_entry, mappings_entry])

        assert manifest["sources"][0]["sha256"] == deception_seed["source_sha256"]
        assert manifest["sources"][0]["sha256"] == hashlib.sha256(ontology_path.read_bytes()).hexdigest()
        assert manifest["sources"][1]["sha256"] == mapping_seed["source_sha256"]
        assert manifest["sources"][1]["sha256"] == hashlib.sha256(mappings_path.read_bytes()).hexdigest()
        assert manifest["sources"][0]["provider"] == "MITRE"
        assert manifest["sources"][0]["retrieval_date"] == "2026-01-15"


# ---------------------------------------------------------------------------
# D. CLI offline — manifest et rapport reproductibles
# ---------------------------------------------------------------------------


class TestCli:
    def test_cli_produces_seed_mapping_report_and_manifest(self, tmp_path, capsys):
        ontology_path = write_ontology(tmp_path)
        mappings_path = write_mappings(tmp_path, [make_binding("ExampleLureChildA", "T9001")])
        out_dir = tmp_path / "staging"
        manifest_path = tmp_path / "manifest" / "source_manifest.json"

        _run_cli(
            [
                "--ontology",
                str(ontology_path),
                "--mappings",
                str(mappings_path),
                "--release-version",
                "9.9.9-fixture",
                "--ontology-url",
                "https://example.org/fixture/d3fend.json",
                "--mappings-url",
                "https://example.org/fixture/mappings.json",
                "--retrieval-date",
                "2026-01-15",
                "--out-dir",
                str(out_dir),
                "--manifest-out",
                str(manifest_path),
            ]
        )

        seed_path = out_dir / "d3fend_deception_seed_9.9.9-fixture.json"
        mapping_path = out_dir / "d3fend_attack_mapping_seed_9.9.9-fixture.json"
        report_path = out_dir / "d3fend_seed_report_9.9.9-fixture.json"

        assert seed_path.exists()
        assert mapping_path.exists()
        assert report_path.exists()
        assert manifest_path.exists()

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        report = json.loads(report_path.read_text(encoding="utf-8"))

        assert report["sources"] == manifest["sources"]
        assert report["sources"] != []
        assert len(manifest["sources"]) == 2
        assert {s["role"] for s in manifest["sources"]} == {"ontology", "inferred_mappings"}

    def test_cli_rejects_malformed_retrieval_date(self, tmp_path):
        ontology_path = write_ontology(tmp_path)
        mappings_path = write_mappings(tmp_path, [make_binding("ExampleLureChildA", "T9001")])
        with pytest.raises(D3fendSeedBuilderError):
            _run_cli(
                [
                    "--ontology",
                    str(ontology_path),
                    "--mappings",
                    str(mappings_path),
                    "--release-version",
                    "9.9.9-fixture",
                    "--ontology-url",
                    "https://example.org/fixture/d3fend.json",
                    "--mappings-url",
                    "https://example.org/fixture/mappings.json",
                    "--retrieval-date",
                    "not-a-date",
                    "--out-dir",
                    str(tmp_path / "staging"),
                    "--manifest-out",
                    str(tmp_path / "source_manifest.json"),
                ]
            )


# ---------------------------------------------------------------------------
# E. Généralité — aucune logique liée au cas d'usage de référence
# ---------------------------------------------------------------------------


class TestGenerality:
    def test_no_hardcoded_pfe_reference_case_or_deception_id_list(self):
        """Réf. tâche §7/§15 : le parseur ne doit contenir ni une liste
        DECEPTION_IDS codée en dur, ni un identifiant du cas de référence
        PFE (T1003, T1078, T1566, T1190, T1059, T1041, DC, WS, DB)."""
        import tools.deception_kb.d3fend_seed_builder as builder_module

        source = Path(builder_module.__file__).read_text(encoding="utf-8")
        forbidden = [
            "T1003",
            "T1078",
            "T1566",
            "T1190",
            "T1059",
            "T1041",
            '"DC"',
            "'DC'",
            '"WS"',
            "'WS'",
            '"DB"',
            "'DB'",
            "DECEPTION_IDS",
        ]
        for token in forbidden:
            assert token not in source, f"identifiant/motif interdit trouvé : {token}"

    def test_different_synthetic_hierarchy_shape_still_works(self, tmp_path):
        """Une hiérarchie synthétique différente (largeur au lieu de
        profondeur) doit être traitée sans aucune adaptation du code."""
        graph = {
            "@context": {"d3f": D3F_BASE, "rdfs": "http://www.w3.org/2000/01/rdf-schema#"},
            "@graph": [
                {"@id": "d3f:Deceive", "rdfs:label": "Deceive"},
                {
                    "@id": "d3f:WideRoot",
                    "d3f:d3fend-id": "D3-WR",
                    "d3f:enables": {"@id": "d3f:Deceive"},
                    "rdfs:label": "Wide Root",
                    "rdfs:subClassOf": [{"@id": "d3f:DefensiveTechnique"}],
                },
                {
                    "@id": "d3f:WideChildOne",
                    "d3f:d3fend-id": "D3-WC1",
                    "rdfs:label": "Wide Child One",
                    "rdfs:subClassOf": [{"@id": "d3f:WideRoot"}],
                },
                {
                    "@id": "d3f:WideChildTwo",
                    "d3f:d3fend-id": "D3-WC2",
                    "rdfs:label": "Wide Child Two",
                    "rdfs:subClassOf": [{"@id": "d3f:WideRoot"}],
                },
            ],
        }
        path = tmp_path / "wide.json"
        path.write_text(json.dumps(graph), encoding="utf-8")
        seed = build_d3fend_deception_seed(path, release_version="9.9.9-fixture")
        by_id = {c["source_technique_id"]: c for c in seed["concepts"]}
        assert set(by_id) == {"D3-WR", "D3-WC1", "D3-WC2"}
        assert by_id["D3-WR"]["child_ids"] == ["D3-WC1", "D3-WC2"]
        assert by_id["D3-WR"]["is_leaf"] is False
        assert by_id["D3-WC1"]["is_leaf"] is True
