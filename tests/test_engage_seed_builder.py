"""
Réf. architecture : CLAUDE.md — contrat technique du PFE Cyberdéception.

Tests unitaires de tools/deception_kb/engage_seed_builder.py (§25.4 :
pytest obligatoire).

Toutes les fixtures MITRE Engage utilisées ici sont synthétiques (créées
dans tmp_path) : aucun test ne dépend d'Internet ni du vrai dépôt
mitre/engage, la CI tourne hors ligne. Les identifiants (EAC9001, T9001,
...) sont des données de test uniquement ; TestGenerality vérifie
explicitement qu'aucune logique de production n'est liée au cas d'usage de
référence PFE (T1003, T1078, DC, WS, DB).
"""

import hashlib
import json
from pathlib import Path

import pytest

from tools.deception_kb.engage_seed_builder import (
    EngageSeedBuilderError,
    _run_cli,
    build_engage_activity_seed,
    build_engage_attack_mapping_seed,
    build_engage_seed_report,
    merge_source_manifest,
    validate_engage_activity_seed,
    validate_engage_attack_mapping_seed,
)

FIXTURE_ENGAGE_VERSION = "9.9-fixture"
FIXTURE_SOURCE_REVISION = "f" * 40

# ---------------------------------------------------------------------------
# Fixtures synthétiques — reproduisent fidèlement les motifs réels observés
# dans MITRE Engage v1.0 (commit 5ae09f6f7511ebb6d35d70a9107490900380d3d8)
# ---------------------------------------------------------------------------


def write_json(tmp_path, filename, data):
    path = tmp_path / filename
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def default_activities():
    return [
        {
            "id": "EAC9001",
            "name": "Fixture Engagement Activity",
            "description": "Description synthétique d'activité.",
            "long_description": "Description longue synthétique d'activité.",
        },
        {
            "id": "SAC9001",
            "name": "Fixture Support Activity",
            "description": "Description synthétique de support.",
            "long_description": "Description longue synthétique de support.",
        },
    ]


def default_activity_details():
    return {
        "EAC9001": {
            "type": "Engagement",
            "goals": ["EGO9001"],
            "vulnerabilities": [{"id": "EAV9001", "eav": "Texte de vulnérabilité synthétique."}],
            "attack_techniques": [
                {"id": "T9001", "name": "Fixture Technique", "attack_tactics": ["discovery"]}
            ],
            "attack_tactics": [{"id": "TA9001", "name": "Fixture Tactic"}],
            "approaches": ["EAP9001"],
            "references": [
                {"id": "REF9001", "title": "Fixture Reference", "url": "https://example.org/ref9001"}
            ],
        },
        "SAC9001": {
            "type": "Strategic",
            "goals": ["SGO9001"],
            "vulnerabilities": [],
            "attack_techniques": [],
            "attack_tactics": [],
            "approaches": ["SAP9001"],
            "references": [],
        },
    }


def default_approaches():
    return [
        {
            "id": "EAP9001",
            "name": "Fixture Engagement Approach",
            "description": "Description synthétique d'approche.",
            "long_description": "Description longue synthétique d'approche.",
        },
        {
            "id": "SAP9001",
            "name": "Fixture Support Approach",
            "description": "Description synthétique d'approche de support.",
            "long_description": "Description longue synthétique d'approche de support.",
        },
    ]


def default_approach_details():
    return {
        "EAP9001": {
            "type": "Engagement",
            "goals": ["EGO9001"],
            "activities": ["EAC9001"],
            "name": "Fixture Engagement Approach",
            "description": "Description synthétique d'approche.",
            "long_description": "Description longue synthétique d'approche.",
        },
        "SAP9001": {
            "type": "Strategic",
            "goals": ["SGO9001"],
            "activities": ["SAC9001"],
            "name": "Fixture Support Approach",
            "description": "Description synthétique d'approche de support.",
            "long_description": "Description longue synthétique d'approche de support.",
        },
    }


def default_approach_activity_mappings():
    return [
        {"approach_id": "EAP9001", "activity_id": "EAC9001"},
        {"approach_id": "SAP9001", "activity_id": "SAC9001"},
    ]


def default_references():
    return [
        {
            "id": "REF9001",
            "title": "Fixture Reference",
            "url": "https://example.org/ref9001",
            "activity_id": "EAC9001",
        }
    ]


def default_attack_mapping_entries():
    return [
        {
            "attack_id": "T9001",
            "attack_technique": "Fixture Technique",
            "eav_id": "EAV9001",
            "eav": "Texte de vulnérabilité synthétique.",
            "eac_id": "EAC9001",
            "eac": "Fixture Engagement Activity",
        }
    ]


def write_engage_fixture_set(
    tmp_path,
    *,
    activities=None,
    activity_details=None,
    approaches=None,
    approach_details=None,
    approach_activity_mappings=None,
    references=None,
):
    return {
        "activities": write_json(
            tmp_path, "activities.json", activities if activities is not None else default_activities()
        ),
        "activity_details": write_json(
            tmp_path,
            "activity_details.json",
            activity_details if activity_details is not None else default_activity_details(),
        ),
        "approaches": write_json(
            tmp_path, "approaches.json", approaches if approaches is not None else default_approaches()
        ),
        "approach_details": write_json(
            tmp_path,
            "approach_details.json",
            approach_details if approach_details is not None else default_approach_details(),
        ),
        "approach_activity_mappings": write_json(
            tmp_path,
            "approach_activity_mappings.json",
            approach_activity_mappings
            if approach_activity_mappings is not None
            else default_approach_activity_mappings(),
        ),
        "references": write_json(
            tmp_path, "references.json", references if references is not None else default_references()
        ),
    }


def write_attack_mapping_file(tmp_path, entries=None, filename="attack_mapping.json"):
    return write_json(tmp_path, filename, entries if entries is not None else default_attack_mapping_entries())


def build_seed_from_fixture(tmp_path, **overrides):
    paths = write_engage_fixture_set(tmp_path, **overrides)
    return build_engage_activity_seed(
        activities_path=paths["activities"],
        activity_details_path=paths["activity_details"],
        approaches_path=paths["approaches"],
        approach_details_path=paths["approach_details"],
        approach_activity_mappings_path=paths["approach_activity_mappings"],
        references_path=paths["references"],
        engage_version=FIXTURE_ENGAGE_VERSION,
        source_revision=FIXTURE_SOURCE_REVISION,
    )


# ---------------------------------------------------------------------------
# A. Construction du seed d'activités / approches
# ---------------------------------------------------------------------------


class TestActivitySeedBuilding:
    def test_valid_synthetic_source_builds_seed(self, tmp_path):
        seed = build_seed_from_fixture(tmp_path)
        assert seed["schema"] == "engage_activity_seed"
        assert seed["engage_version"] == FIXTURE_ENGAGE_VERSION
        assert seed["source_revision"] == FIXTURE_SOURCE_REVISION
        assert len(seed["activities"]) == 2
        assert len(seed["approaches"]) == 2

    def test_id_name_description_long_description_conserved(self, tmp_path):
        seed = build_seed_from_fixture(tmp_path)
        by_id = {a["activity_id"]: a for a in seed["activities"]}
        eac = by_id["EAC9001"]
        assert eac["name"] == "Fixture Engagement Activity"
        assert eac["description"] == "Description synthétique d'activité."
        assert eac["long_description"] == "Description longue synthétique d'activité."

    def test_activity_details_joined(self, tmp_path):
        seed = build_seed_from_fixture(tmp_path)
        by_id = {a["activity_id"]: a for a in seed["activities"]}
        eac = by_id["EAC9001"]
        assert eac["detail_type"] == "Engagement"
        assert eac["goal_ids"] == ["EGO9001"]
        assert eac["vulnerabilities"] == [
            {"vulnerability_id": "EAV9001", "vulnerability_text": "Texte de vulnérabilité synthétique."}
        ]
        assert eac["attack_techniques"] == [
            {
                "attack_id": "T9001",
                "attack_technique_name": "Fixture Technique",
                "attack_tactic_labels": ["discovery"],
            }
        ]
        assert eac["attack_tactics"] == [{"attack_tactic_id": "TA9001", "attack_tactic_name": "Fixture Tactic"}]

    def test_activity_approach_join(self, tmp_path):
        seed = build_seed_from_fixture(tmp_path)
        by_id = {a["activity_id"]: a for a in seed["activities"]}
        assert by_id["EAC9001"]["approach_ids"] == ["EAP9001"]
        assert by_id["EAC9001"]["approach_names"] == ["Fixture Engagement Approach"]

    def test_activity_with_multiple_approaches(self, tmp_path):
        mappings = [
            {"approach_id": "EAP9001", "activity_id": "EAC9001"},
            {"approach_id": "SAP9001", "activity_id": "EAC9001"},
        ]
        details = default_activity_details()
        details["SAC9001"]["approaches"] = []
        seed = build_seed_from_fixture(
            tmp_path, activity_details=details, approach_activity_mappings=mappings
        )
        by_id = {a["activity_id"]: a for a in seed["activities"]}
        assert set(by_id["EAC9001"]["approach_ids"]) == {"EAP9001", "SAP9001"}

    def test_eac_sac_families_distinct(self, tmp_path):
        seed = build_seed_from_fixture(tmp_path)
        by_id = {a["activity_id"]: a for a in seed["activities"]}
        assert by_id["EAC9001"]["activity_family"] == "EAC"
        assert by_id["SAC9001"]["activity_family"] == "SAC"

    def test_eap_sap_families_distinct(self, tmp_path):
        seed = build_seed_from_fixture(tmp_path)
        by_id = {a["approach_id"]: a for a in seed["approaches"]}
        assert by_id["EAP9001"]["approach_family"] == "EAP"
        assert by_id["SAP9001"]["approach_family"] == "SAP"

    def test_unrecognized_activity_prefix_rejected(self, tmp_path):
        activities = default_activities()
        activities.append(
            {"id": "XYZ9001", "name": "Unknown prefix", "description": "d", "long_description": "ld"}
        )
        with pytest.raises(EngageSeedBuilderError):
            build_seed_from_fixture(tmp_path, activities=activities)

    def test_approach_references_from_standalone_references_file(self, tmp_path):
        """Réf. constat d'inspection : references.json['activity_id'] peut
        référencer un approach_id (observé sur SAP0001/SAP0002 du vrai
        jeu de données)."""
        references = default_references() + [
            {
                "id": "REF9002",
                "title": "Fixture Approach Reference",
                "url": "https://example.org/ref9002",
                "activity_id": "SAP9001",
            }
        ]
        seed = build_seed_from_fixture(tmp_path, references=references)
        by_id = {a["approach_id"]: a for a in seed["approaches"]}
        assert by_id["SAP9001"]["references"] == [
            {"reference_id": "REF9002", "title": "Fixture Approach Reference", "url": "https://example.org/ref9002"}
        ]

    def test_source_hashes_match_file_bytes(self, tmp_path):
        paths = write_engage_fixture_set(tmp_path)
        seed = build_engage_activity_seed(
            activities_path=paths["activities"],
            activity_details_path=paths["activity_details"],
            approaches_path=paths["approaches"],
            approach_details_path=paths["approach_details"],
            approach_activity_mappings_path=paths["approach_activity_mappings"],
            references_path=paths["references"],
            engage_version=FIXTURE_ENGAGE_VERSION,
            source_revision=FIXTURE_SOURCE_REVISION,
        )
        expected = hashlib.sha256(paths["activities"].read_bytes()).hexdigest()
        assert seed["source_files"]["activities"]["sha256"] == expected


# ---------------------------------------------------------------------------
# B. Validation du staging activités/approches
# ---------------------------------------------------------------------------


class TestActivitySeedValidation:
    def test_valid_seed_accepted(self, tmp_path):
        seed = build_seed_from_fixture(tmp_path)
        validate_engage_activity_seed(seed)  # ne doit pas lever

    def test_approach_referencing_unknown_activity_rejected(self, tmp_path):
        seed = build_seed_from_fixture(tmp_path)
        seed["approaches"][0]["activity_ids"].append("EAC_GHOST")
        with pytest.raises(EngageSeedBuilderError):
            validate_engage_activity_seed(seed)

    def test_activity_referencing_unknown_approach_rejected(self, tmp_path):
        seed = build_seed_from_fixture(tmp_path)
        seed["activities"][0]["approach_ids"].append("EAP_GHOST")
        with pytest.raises(EngageSeedBuilderError):
            validate_engage_activity_seed(seed)

    def test_duplicate_activity_id_rejected(self, tmp_path):
        seed = build_seed_from_fixture(tmp_path)
        seed["activities"].append(dict(seed["activities"][0]))
        with pytest.raises(EngageSeedBuilderError):
            validate_engage_activity_seed(seed)


# ---------------------------------------------------------------------------
# C. Mappings Engage -> ATT&CK et déduplication
# ---------------------------------------------------------------------------


class TestAttackMappingSeed:
    def test_valid_mapping_extracted(self, tmp_path):
        activity_seed = build_seed_from_fixture(tmp_path)
        path = write_attack_mapping_file(tmp_path)
        mapping_seed = build_engage_attack_mapping_seed(
            path, activity_seed, engage_version=FIXTURE_ENGAGE_VERSION, source_revision=FIXTURE_SOURCE_REVISION
        )
        assert len(mapping_seed["mappings"]) == 1
        entry = mapping_seed["mappings"][0]
        assert entry["attack_id"] == "T9001"
        assert entry["adversary_vulnerability_id"] == "EAV9001"
        assert entry["adversary_vulnerability_text"] == "Texte de vulnérabilité synthétique."
        assert entry["engage_activity_id"] == "EAC9001"
        assert entry["origin"] == "mitre_engage_v1.0"
        assert entry["source_revision"] == FIXTURE_SOURCE_REVISION
        assert "confidence" not in entry

    def test_malformed_attack_id_filtered(self, tmp_path):
        activity_seed = build_seed_from_fixture(tmp_path)
        entries = default_attack_mapping_entries() + [
            {
                "attack_id": "not-an-attack-id",
                "attack_technique": "Bogus",
                "eav_id": "EAV9002",
                "eav": "Texte.",
                "eac_id": "EAC9001",
                "eac": "Fixture Engagement Activity",
            }
        ]
        path = write_attack_mapping_file(tmp_path, entries)
        mapping_seed = build_engage_attack_mapping_seed(
            path, activity_seed, engage_version=FIXTURE_ENGAGE_VERSION, source_revision=FIXTURE_SOURCE_REVISION
        )
        assert [m["attack_id"] for m in mapping_seed["mappings"]] == ["T9001"]

    def test_exact_duplicate_bindings_deduplicated(self, tmp_path):
        activity_seed = build_seed_from_fixture(tmp_path)
        entries = default_attack_mapping_entries() * 2
        path = write_attack_mapping_file(tmp_path, entries)
        mapping_seed = build_engage_attack_mapping_seed(
            path, activity_seed, engage_version=FIXTURE_ENGAGE_VERSION, source_revision=FIXTURE_SOURCE_REVISION
        )
        assert mapping_seed["raw_mapping_count"] == 2
        assert mapping_seed["unique_mapping_count"] == 1
        assert len(mapping_seed["mappings"]) == 1

    def test_same_attack_id_and_activity_different_eav_both_kept(self, tmp_path):
        """§20 : même attack_id + EAC mais EAV différente -> deux relations
        distinctes conservées (la clé de déduplication inclut eav_id)."""
        activity_seed = build_seed_from_fixture(tmp_path)
        entries = [
            {
                "attack_id": "T9001",
                "attack_technique": "Fixture Technique",
                "eav_id": "EAV9001",
                "eav": "Première vulnérabilité.",
                "eac_id": "EAC9001",
                "eac": "Fixture Engagement Activity",
            },
            {
                "attack_id": "T9001",
                "attack_technique": "Fixture Technique",
                "eav_id": "EAV9002",
                "eav": "Seconde vulnérabilité.",
                "eac_id": "EAC9001",
                "eac": "Fixture Engagement Activity",
            },
        ]
        path = write_attack_mapping_file(tmp_path, entries)
        mapping_seed = build_engage_attack_mapping_seed(
            path, activity_seed, engage_version=FIXTURE_ENGAGE_VERSION, source_revision=FIXTURE_SOURCE_REVISION
        )
        assert mapping_seed["unique_mapping_count"] == 2
        assert mapping_seed["unique_attack_activity_pair_count"] == 1

    def test_order_preserved_first_occurrence_kept(self, tmp_path):
        activity_seed = build_seed_from_fixture(tmp_path)
        base = default_attack_mapping_entries()[0]
        other = {**base, "eav_id": "EAV9002", "eav": "Autre vulnérabilité."}
        entries = [base, other, dict(base)]
        path = write_attack_mapping_file(tmp_path, entries)
        mapping_seed = build_engage_attack_mapping_seed(
            path, activity_seed, engage_version=FIXTURE_ENGAGE_VERSION, source_revision=FIXTURE_SOURCE_REVISION
        )
        assert [m["adversary_vulnerability_id"] for m in mapping_seed["mappings"]] == ["EAV9001", "EAV9002"]


# ---------------------------------------------------------------------------
# D. Validation des mappings
# ---------------------------------------------------------------------------


class TestAttackMappingValidation:
    def test_valid_mapping_seed_accepted(self, tmp_path):
        activity_seed = build_seed_from_fixture(tmp_path)
        path = write_attack_mapping_file(tmp_path)
        mapping_seed = build_engage_attack_mapping_seed(
            path, activity_seed, engage_version=FIXTURE_ENGAGE_VERSION, source_revision=FIXTURE_SOURCE_REVISION
        )
        validate_engage_attack_mapping_seed(mapping_seed, activity_seed)  # ne doit pas lever

    def test_mapping_referencing_unknown_activity_rejected(self, tmp_path):
        activity_seed = build_seed_from_fixture(tmp_path)
        rogue_seed = {
            "mappings": [
                {
                    "attack_id": "T9001",
                    "adversary_vulnerability_id": "EAV9001",
                    "engage_activity_id": "EAC_GHOST",
                    "source_sha256": "a" * 64,
                }
            ]
        }
        with pytest.raises(EngageSeedBuilderError):
            validate_engage_attack_mapping_seed(rogue_seed, activity_seed)

    def test_malformed_attack_id_rejected_at_validation(self, tmp_path):
        activity_seed = build_seed_from_fixture(tmp_path)
        bad_seed = {
            "mappings": [
                {
                    "attack_id": "not-an-attack-id",
                    "adversary_vulnerability_id": "EAV9001",
                    "engage_activity_id": "EAC9001",
                    "source_sha256": "a" * 64,
                }
            ]
        }
        with pytest.raises(EngageSeedBuilderError):
            validate_engage_attack_mapping_seed(bad_seed, activity_seed)

    def test_exact_duplicate_relation_rejected(self, tmp_path):
        activity_seed = build_seed_from_fixture(tmp_path)
        entry = {
            "attack_id": "T9001",
            "adversary_vulnerability_id": "EAV9001",
            "engage_activity_id": "EAC9001",
            "source_sha256": "a" * 64,
        }
        corrupted_seed = {"mappings": [entry, dict(entry)]}
        with pytest.raises(EngageSeedBuilderError):
            validate_engage_attack_mapping_seed(corrupted_seed, activity_seed)


# ---------------------------------------------------------------------------
# E. Déterminisme
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_input_same_output(self, tmp_path):
        seed_a = build_seed_from_fixture(tmp_path)
        seed_b = build_seed_from_fixture(tmp_path)
        assert seed_a == seed_b


# ---------------------------------------------------------------------------
# F. Rapport et manifest
# ---------------------------------------------------------------------------


class TestReportAndManifest:
    def test_seed_report_counts(self, tmp_path):
        activity_seed = build_seed_from_fixture(tmp_path)
        path = write_attack_mapping_file(tmp_path)
        mapping_seed = build_engage_attack_mapping_seed(
            path, activity_seed, engage_version=FIXTURE_ENGAGE_VERSION, source_revision=FIXTURE_SOURCE_REVISION
        )
        report = build_engage_seed_report(activity_seed, mapping_seed, manifest_entries=[])
        assert report["activity_count"] == 2
        assert report["engagement_activity_count"] == 1
        assert report["support_activity_count"] == 1
        assert report["approach_count"] == 2
        assert report["raw_attack_mapping_count"] == 1
        assert report["unique_attack_mapping_count"] == 1
        assert report["unique_attack_activity_pair_count"] == 1
        assert report["number_of_attack_ids"] == 1
        assert report["number_of_adversary_vulnerabilities"] == 1

    def test_merge_source_manifest_preserves_existing_entries(self, tmp_path):
        manifest_path = tmp_path / "source_manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema": "deception_source_manifest",
                    "schema_version": "1.0",
                    "sources": [{"source_id": "d3fend-ontology-1.5.0", "provider": "MITRE"}],
                }
            ),
            encoding="utf-8",
        )
        merged = merge_source_manifest(
            manifest_path, [{"source_id": "engage-activities-1.0", "provider": "MITRE"}]
        )
        ids = {s["source_id"] for s in merged["sources"]}
        assert ids == {"d3fend-ontology-1.5.0", "engage-activities-1.0"}

    def test_merge_source_manifest_replaces_matching_source_id(self, tmp_path):
        manifest_path = tmp_path / "source_manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema": "deception_source_manifest",
                    "schema_version": "1.0",
                    "sources": [{"source_id": "engage-activities-1.0", "sha256": "old"}],
                }
            ),
            encoding="utf-8",
        )
        merged = merge_source_manifest(
            manifest_path, [{"source_id": "engage-activities-1.0", "sha256": "new"}]
        )
        assert len(merged["sources"]) == 1
        assert merged["sources"][0]["sha256"] == "new"

    def test_merge_source_manifest_creates_new_file_if_absent(self, tmp_path):
        manifest_path = tmp_path / "does_not_exist.json"
        merged = merge_source_manifest(manifest_path, [{"source_id": "engage-activities-1.0"}])
        assert len(merged["sources"]) == 1


# ---------------------------------------------------------------------------
# G. CLI offline
# ---------------------------------------------------------------------------


class TestCli:
    def test_cli_produces_staging_report_and_manifest(self, tmp_path):
        paths = write_engage_fixture_set(tmp_path)
        mapping_path = write_attack_mapping_file(tmp_path)
        out_dir = tmp_path / "staging"
        manifest_path = tmp_path / "manifest" / "source_manifest.json"

        _run_cli(
            [
                "--activities",
                str(paths["activities"]),
                "--activity-details",
                str(paths["activity_details"]),
                "--approaches",
                str(paths["approaches"]),
                "--approach-details",
                str(paths["approach_details"]),
                "--approach-activity-mappings",
                str(paths["approach_activity_mappings"]),
                "--attack-mapping",
                str(mapping_path),
                "--references",
                str(paths["references"]),
                "--engage-version",
                FIXTURE_ENGAGE_VERSION,
                "--source-revision",
                FIXTURE_SOURCE_REVISION,
                "--retrieval-date",
                "2026-01-15",
                "--out-dir",
                str(out_dir),
                "--manifest",
                str(manifest_path),
            ]
        )

        activity_seed_path = out_dir / f"engage_activity_seed_{FIXTURE_ENGAGE_VERSION}.json"
        mapping_seed_path = out_dir / f"engage_attack_mapping_seed_{FIXTURE_ENGAGE_VERSION}.json"
        report_path = out_dir / f"engage_seed_report_{FIXTURE_ENGAGE_VERSION}.json"

        assert activity_seed_path.exists()
        assert mapping_seed_path.exists()
        assert report_path.exists()
        assert manifest_path.exists()

        report = json.loads(report_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert report["sources"] != []
        assert {s["source_id"] for s in report["sources"]} <= {s["source_id"] for s in manifest["sources"]}
        assert all(s["framework"] == "MITRE Engage" for s in manifest["sources"])
        assert all(s["source_revision"] == FIXTURE_SOURCE_REVISION for s in manifest["sources"])

    def test_cli_preserves_existing_manifest_entries(self, tmp_path):
        paths = write_engage_fixture_set(tmp_path)
        mapping_path = write_attack_mapping_file(tmp_path)
        manifest_path = tmp_path / "source_manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema": "deception_source_manifest",
                    "schema_version": "1.0",
                    "sources": [{"source_id": "d3fend-ontology-1.5.0", "provider": "MITRE"}],
                }
            ),
            encoding="utf-8",
        )

        _run_cli(
            [
                "--activities",
                str(paths["activities"]),
                "--activity-details",
                str(paths["activity_details"]),
                "--approaches",
                str(paths["approaches"]),
                "--approach-details",
                str(paths["approach_details"]),
                "--approach-activity-mappings",
                str(paths["approach_activity_mappings"]),
                "--attack-mapping",
                str(mapping_path),
                "--references",
                str(paths["references"]),
                "--engage-version",
                FIXTURE_ENGAGE_VERSION,
                "--source-revision",
                FIXTURE_SOURCE_REVISION,
                "--retrieval-date",
                "2026-01-15",
                "--out-dir",
                str(tmp_path / "staging"),
                "--manifest",
                str(manifest_path),
            ]
        )

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        ids = {s["source_id"] for s in manifest["sources"]}
        assert "d3fend-ontology-1.5.0" in ids

    def test_cli_rejects_malformed_retrieval_date(self, tmp_path):
        paths = write_engage_fixture_set(tmp_path)
        mapping_path = write_attack_mapping_file(tmp_path)
        with pytest.raises(EngageSeedBuilderError):
            _run_cli(
                [
                    "--activities",
                    str(paths["activities"]),
                    "--activity-details",
                    str(paths["activity_details"]),
                    "--approaches",
                    str(paths["approaches"]),
                    "--approach-details",
                    str(paths["approach_details"]),
                    "--approach-activity-mappings",
                    str(paths["approach_activity_mappings"]),
                    "--attack-mapping",
                    str(mapping_path),
                    "--references",
                    str(paths["references"]),
                    "--engage-version",
                    FIXTURE_ENGAGE_VERSION,
                    "--source-revision",
                    FIXTURE_SOURCE_REVISION,
                    "--retrieval-date",
                    "not-a-date",
                    "--out-dir",
                    str(tmp_path / "staging"),
                    "--manifest",
                    str(tmp_path / "source_manifest.json"),
                ]
            )


# ---------------------------------------------------------------------------
# H. Généralité — aucune logique liée au cas d'usage de référence
# ---------------------------------------------------------------------------


class TestGenerality:
    def test_no_hardcoded_pfe_reference_case(self):
        import tools.deception_kb.engage_seed_builder as builder_module

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
        ]
        for token in forbidden:
            assert token not in source, f"identifiant/motif interdit trouvé : {token}"

    def test_different_activity_and_approach_ids_still_work(self, tmp_path):
        activities = [
            {
                "id": "EAC1234",
                "name": "Totally Different Activity",
                "description": "d",
                "long_description": "ld",
            }
        ]
        activity_details = {
            "EAC1234": {
                "type": "Engagement",
                "goals": [],
                "vulnerabilities": [],
                "attack_techniques": [],
                "attack_tactics": [],
                "approaches": [],
                "references": [],
            }
        }
        approaches = [
            {"id": "EAP5678", "name": "Totally Different Approach", "description": "d", "long_description": "ld"}
        ]
        approach_details = {
            "EAP5678": {
                "type": "Engagement",
                "goals": [],
                "activities": ["EAC1234"],
                "name": "Totally Different Approach",
                "description": "d",
                "long_description": "ld",
            }
        }
        mappings = [{"approach_id": "EAP5678", "activity_id": "EAC1234"}]
        seed = build_seed_from_fixture(
            tmp_path,
            activities=activities,
            activity_details=activity_details,
            approaches=approaches,
            approach_details=approach_details,
            approach_activity_mappings=mappings,
            references=[],
        )
        assert seed["activities"][0]["activity_id"] == "EAC1234"
        assert seed["activities"][0]["approach_ids"] == ["EAP5678"]
