"""
Réf. architecture : CLAUDE.md §8 — réf. tâche « renforcer le RAG utilisé
par SP2 », §3 « Ajouter MITRE ATT&CK au corpus RAG ».

Tests unitaires de `tools/attack_kb/attack_seed_builder.py` (§25.4 :
pytest obligatoire).

Les bundles STIX synthétiques sont construits localement (jamais le vrai
`enterprise-attack.json`, jamais téléchargés pendant `pytest`) —
`TestRealStagingFile` est la seule classe qui charge le staging RÉEL déjà
versionné (`data/attack/staging/attack_rag_seed_19.2.json`), à l'image de
`TestRealStagingFiles` dans `tests/test_rag_indexer.py`.
"""

import json
from pathlib import Path

import pytest

from src.knowledge_attack import load_attack_knowledge
from tools.attack_kb.attack_seed_builder import (
    AttackSeedBuilderError,
    build_attack_rag_seed,
    build_attack_seed_report,
    build_technique_entry,
    relevant_technique_ids,
    validate_attack_seed,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
ATTACK_STAGING_DIR = REPO_ROOT / "data" / "attack" / "staging"


def make_attack_pattern(
    technique_id="T8001",
    *,
    name="Synthetic Technique",
    description="Description synthétique de test.",
    tactics=("initial-access",),
    platforms=("Windows",),
    revoked=False,
    deprecated=False,
    version="1.0",
):
    stix_id = f"attack-pattern--{technique_id.lower().replace('.', '-')}"
    return {
        "type": "attack-pattern",
        "id": stix_id,
        "name": name,
        "description": description,
        "external_references": [
            {
                "source_name": "mitre-attack",
                "external_id": technique_id,
                "url": f"https://attack.mitre.org/techniques/{technique_id.replace('.', '/')}",
            }
        ],
        "kill_chain_phases": [{"kill_chain_name": "mitre-attack", "phase_name": t} for t in tactics],
        "x_mitre_platforms": list(platforms),
        "revoked": revoked,
        "x_mitre_deprecated": deprecated,
        "x_mitre_version": version,
    }


def write_bundle(tmp_path, objects):
    path = tmp_path / "bundle.json"
    payload = {"type": "bundle", "id": "bundle--test-fixture", "spec_version": "2.1", "objects": objects}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def make_mapping(attack_ids):
    return {
        "schema": "attack_deception_mapping",
        "relations": [{"attack_id": attack_id, "mechanism_id": f"M{i}"} for i, attack_id in enumerate(attack_ids)],
    }


# ---------------------------------------------------------------------------
# A. Périmètre : techniques pertinentes
# ---------------------------------------------------------------------------


class TestRelevantTechniqueIds:
    def test_extracts_distinct_sorted_ids(self):
        mapping = make_mapping(["T1003", "T1001", "T1003"])
        assert relevant_technique_ids(mapping) == ["T1001", "T1003"]

    def test_rejects_mapping_without_relations(self):
        with pytest.raises(AttackSeedBuilderError):
            relevant_technique_ids({"schema": "x"})


# ---------------------------------------------------------------------------
# B. Construction d'une entrée technique — plusieurs chunks par technique
# ---------------------------------------------------------------------------


class TestBuildTechniqueEntry:
    def test_produces_multiple_source_evidence_entries(self, tmp_path):
        bundle_path = write_bundle(tmp_path, [make_attack_pattern("T8001", tactics=("initial-access", "execution"))])
        kb = load_attack_knowledge(bundle_path)
        entry = build_technique_entry(kb.techniques_by_id["T8001"])
        # name + description + 2 tactiques + platforms = 5 preuves
        assert len(entry["source_evidence"]) == 5
        properties = {e["source_property"] for e in entry["source_evidence"]}
        assert {"name", "description", "tactic", "platforms"} <= properties

    def test_evidence_text_is_verbatim_source_text(self, tmp_path):
        bundle_path = write_bundle(tmp_path, [make_attack_pattern("T8001", name="Exact Name")])
        kb = load_attack_knowledge(bundle_path)
        entry = build_technique_entry(kb.techniques_by_id["T8001"])
        name_evidence = next(e for e in entry["source_evidence"] if e["source_property"] == "name")
        assert name_evidence["evidence_text"] == "Exact Name"

    def test_preserves_revoked_and_deprecated_status(self, tmp_path):
        bundle_path = write_bundle(tmp_path, [make_attack_pattern("T8001", revoked=True)])
        kb = load_attack_knowledge(bundle_path, include_revoked=True)
        entry = build_technique_entry(kb.techniques_by_id["T8001"])
        assert entry["revoked"] is True
        assert entry["deprecated"] is False


# ---------------------------------------------------------------------------
# C. Construction du seed complet — jamais de texte inventé, revoked/deprecated
#    conservés, techniques absentes reportées explicitement
# ---------------------------------------------------------------------------


class TestBuildAttackRagSeed:
    def test_includes_only_mapping_referenced_techniques(self, tmp_path):
        bundle_path = write_bundle(
            tmp_path, [make_attack_pattern("T8001"), make_attack_pattern("T8002"), make_attack_pattern("T8003")]
        )
        kb = load_attack_knowledge(bundle_path)
        mapping = make_mapping(["T8001", "T8002"])
        seed = build_attack_rag_seed(kb, mapping, release_version="test-1.0")
        included_ids = {t["technique_id"] for t in seed["techniques"]}
        assert included_ids == {"T8001", "T8002"}

    def test_reports_missing_technique_ids_explicitly(self, tmp_path):
        bundle_path = write_bundle(tmp_path, [make_attack_pattern("T8001")])
        kb = load_attack_knowledge(bundle_path)
        mapping = make_mapping(["T8001", "T9999"])
        seed = build_attack_rag_seed(kb, mapping, release_version="test-1.0")
        assert seed["missing_technique_ids"] == ["T9999"]
        assert {t["technique_id"] for t in seed["techniques"]} == {"T8001"}

    def test_includes_revoked_and_deprecated_when_kb_loaded_with_them(self, tmp_path):
        bundle_path = write_bundle(tmp_path, [make_attack_pattern("T8001", revoked=True)])
        kb = load_attack_knowledge(bundle_path, include_revoked=True, include_deprecated=True)
        mapping = make_mapping(["T8001"])
        seed = build_attack_rag_seed(kb, mapping, release_version="test-1.0")
        assert len(seed["techniques"]) == 1
        assert seed["techniques"][0]["revoked"] is True

    def test_excludes_revoked_technique_when_kb_loaded_without_them(self, tmp_path):
        bundle_path = write_bundle(tmp_path, [make_attack_pattern("T8001", revoked=True)])
        kb = load_attack_knowledge(bundle_path)  # défauts : include_revoked=False
        mapping = make_mapping(["T8001"])
        seed = build_attack_rag_seed(kb, mapping, release_version="test-1.0")
        assert seed["missing_technique_ids"] == ["T8001"]


# ---------------------------------------------------------------------------
# D. Validation
# ---------------------------------------------------------------------------


class TestValidateAttackSeed:
    def test_valid_seed_passes(self, tmp_path):
        bundle_path = write_bundle(tmp_path, [make_attack_pattern("T8001")])
        kb = load_attack_knowledge(bundle_path)
        seed = build_attack_rag_seed(kb, make_mapping(["T8001"]), release_version="test-1.0")
        validate_attack_seed(seed)  # ne lève pas

    def test_rejects_duplicate_technique_id(self):
        seed = {
            "techniques": [
                {"technique_id": "T8001", "source_evidence": [{"source_property": "name", "evidence_text": "x"}]},
                {"technique_id": "T8001", "source_evidence": [{"source_property": "name", "evidence_text": "y"}]},
            ]
        }
        with pytest.raises(AttackSeedBuilderError):
            validate_attack_seed(seed)

    def test_rejects_technique_without_evidence(self):
        seed = {"techniques": [{"technique_id": "T8001", "source_evidence": []}]}
        with pytest.raises(AttackSeedBuilderError):
            validate_attack_seed(seed)


# ---------------------------------------------------------------------------
# E. Rapport
# ---------------------------------------------------------------------------


class TestBuildAttackSeedReport:
    def test_report_counts_are_consistent(self, tmp_path):
        bundle_path = write_bundle(tmp_path, [make_attack_pattern("T8001")])
        kb = load_attack_knowledge(bundle_path)
        seed = build_attack_rag_seed(kb, make_mapping(["T8001", "T9999"]), release_version="test-1.0")
        report = build_attack_seed_report(seed, manifest_entries=[])
        assert report["relevant_technique_count"] == 2
        assert report["included_technique_count"] == 1
        assert report["missing_technique_count"] == 1
        assert report["missing_technique_ids"] == ["T9999"]
        assert report["chunk_count"] == sum(len(t["source_evidence"]) for t in seed["techniques"])


# ---------------------------------------------------------------------------
# F. Staging réel déjà versionné — provenance MITRE authentique
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not ATTACK_STAGING_DIR.exists(), reason="Staging ATT&CK réel non généré dans cet environnement.")
class TestRealStagingFile:
    def test_real_staging_file_is_internally_consistent(self):
        staging_files = sorted(ATTACK_STAGING_DIR.glob("attack_rag_seed_*.json"))
        assert staging_files, "Aucun fichier attack_rag_seed_*.json versionné."
        seed = json.loads(staging_files[0].read_text(encoding="utf-8"))
        validate_attack_seed(seed)  # ne lève pas
        assert seed["missing_technique_ids"] == []
        assert len(seed["techniques"]) == seed["relevance_scope"]["relevant_technique_count"]

    def test_real_staging_file_preserves_verbatim_mitre_text(self):
        staging_files = sorted(ATTACK_STAGING_DIR.glob("attack_rag_seed_*.json"))
        seed = json.loads(staging_files[0].read_text(encoding="utf-8"))
        first_technique = seed["techniques"][0]
        name_evidence = next(e for e in first_technique["source_evidence"] if e["source_property"] == "name")
        assert name_evidence["evidence_text"] == first_technique["name"]
