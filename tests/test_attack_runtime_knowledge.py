"""
Réf. architecture : CLAUDE.md §8 — réf. tâche « dernière passe de
finition technique du chapitre 4 », §6-§10 « Supprimer la dépendance
runtime au fichier brut ATT&CK ».

Tests unitaires de `src/attack_runtime_knowledge.py` (§25.4 : pytest
obligatoire). Aucun test ici ne dépend du bundle STIX brut
`enterprise-attack.json` ni d'Internet — uniquement des stagings
synthétiques `attack_rag_seed`-compatibles.
"""

import json

import pytest

from src.attack_runtime_knowledge import (
    AttackRuntimeKnowledgeError,
    find_latest_attack_staging_file,
    get_technique,
    has_technique,
    load_attack_runtime_knowledge,
)


def make_staging(techniques: list[dict]) -> dict:
    return {"schema": "attack_rag_seed", "schema_version": "1.0", "techniques": techniques}


def write_staging(path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


# ---------------------------------------------------------------------------
# A. Chargement depuis le staging (§6-§7)
# ---------------------------------------------------------------------------


class TestLoadAttackRuntimeKnowledge:
    def test_loads_technique_level_fields(self, tmp_path):
        staging_path = tmp_path / "attack_rag_seed_1.0.json"
        write_staging(
            staging_path,
            make_staging(
                [
                    {
                        "technique_id": "T1003",
                        "name": "OS Credential Dumping",
                        "tactics": ["credential-access"],
                        "platforms": ["Windows", "Linux"],
                        "version": "2.0",
                        "revoked": False,
                        "deprecated": False,
                    }
                ]
            ),
        )
        kb = load_attack_runtime_knowledge(staging_path)
        assert len(kb) == 1
        technique = kb.techniques_by_id["T1003"]
        assert technique.name == "OS Credential Dumping"
        assert technique.tactics == ("credential-access",)
        assert technique.platforms == ("Windows", "Linux")
        assert technique.version == "2.0"
        assert technique.revoked is False
        assert technique.deprecated is False

    def test_preserves_revoked_and_deprecated_status(self, tmp_path):
        staging_path = tmp_path / "attack_rag_seed_1.0.json"
        write_staging(
            staging_path,
            make_staging(
                [{"technique_id": "T1562", "name": "Impair Defenses", "tactics": [], "platforms": [], "version": None, "revoked": True, "deprecated": False}]
            ),
        )
        kb = load_attack_runtime_knowledge(staging_path)
        assert kb.techniques_by_id["T1562"].revoked is True

    def test_missing_file_raises_explicitly(self, tmp_path):
        with pytest.raises(AttackRuntimeKnowledgeError):
            load_attack_runtime_knowledge(tmp_path / "does-not-exist.json")

    def test_malformed_staging_raises_explicitly(self, tmp_path):
        staging_path = tmp_path / "attack_rag_seed_bad.json"
        write_staging(staging_path, {"schema": "not_an_attack_seed"})
        with pytest.raises(AttackRuntimeKnowledgeError):
            load_attack_runtime_knowledge(staging_path)

    def test_never_reads_source_evidence_text(self, tmp_path):
        """Réf. §7 : les champs runtime viennent des champs déjà
        structurés au niveau technique, jamais reparsés depuis
        source_evidence (texte fragmenté, réservé à l'indexation RAG)."""
        staging_path = tmp_path / "attack_rag_seed_1.0.json"
        write_staging(
            staging_path,
            make_staging(
                [
                    {
                        "technique_id": "T1003",
                        "name": "OS Credential Dumping",
                        "tactics": ["credential-access"],
                        "platforms": [],
                        "version": None,
                        "revoked": False,
                        "deprecated": False,
                        "source_evidence": [{"source_property": "description", "evidence_text": "should never leak into runtime fields"}],
                    }
                ]
            ),
        )
        kb = load_attack_runtime_knowledge(staging_path)
        technique = kb.techniques_by_id["T1003"]
        assert not hasattr(technique, "description")
        assert not hasattr(technique, "source_evidence")


# ---------------------------------------------------------------------------
# B. Accès défensif — jamais d'invention (§10)
# ---------------------------------------------------------------------------


class TestHasAndGetTechnique:
    def test_has_technique_true_for_known_id(self, tmp_path):
        staging_path = tmp_path / "attack_rag_seed_1.0.json"
        write_staging(staging_path, make_staging([{"technique_id": "T1003", "name": "X", "tactics": [], "platforms": [], "version": None, "revoked": False, "deprecated": False}]))
        kb = load_attack_runtime_knowledge(staging_path)
        assert has_technique(kb, "T1003") is True

    def test_has_technique_false_for_unknown_id(self, tmp_path):
        staging_path = tmp_path / "attack_rag_seed_1.0.json"
        write_staging(staging_path, make_staging([]))
        kb = load_attack_runtime_knowledge(staging_path)
        assert has_technique(kb, "T9999") is False

    def test_get_technique_raises_key_error_for_unknown_id(self, tmp_path):
        staging_path = tmp_path / "attack_rag_seed_1.0.json"
        write_staging(staging_path, make_staging([]))
        kb = load_attack_runtime_knowledge(staging_path)
        with pytest.raises(KeyError):
            get_technique(kb, "T9999")


# ---------------------------------------------------------------------------
# C. Localisation du staging le plus récent (§7, durcissement partagé)
# ---------------------------------------------------------------------------


class TestFindLatestAttackStagingFile:
    def test_excludes_the_extraction_report(self, tmp_path):
        write_staging(tmp_path / "attack_rag_seed_1.0.json", make_staging([{"technique_id": "T1003", "name": "X", "tactics": [], "platforms": [], "version": None, "revoked": False, "deprecated": False}]))
        write_staging(tmp_path / "attack_rag_seed_report_1.0.json", {"schema": "attack_rag_seed_report"})
        found = find_latest_attack_staging_file(tmp_path)
        assert found.name == "attack_rag_seed_1.0.json"

    def test_picks_the_lexicographically_latest_seed(self, tmp_path):
        write_staging(tmp_path / "attack_rag_seed_1.0.json", make_staging([]))
        write_staging(tmp_path / "attack_rag_seed_2.0.json", make_staging([]))
        found = find_latest_attack_staging_file(tmp_path)
        assert found.name == "attack_rag_seed_2.0.json"

    def test_raises_explicitly_when_no_staging_present(self, tmp_path):
        with pytest.raises(AttackRuntimeKnowledgeError):
            find_latest_attack_staging_file(tmp_path)


# ---------------------------------------------------------------------------
# D. Staging réel déjà versionné — non-régression
# ---------------------------------------------------------------------------


class TestRealAttackStaging:
    def test_real_staging_loads_and_is_non_empty(self):
        from pathlib import Path

        staging_dir = Path("data/attack/staging")
        if not staging_dir.exists() or not list(staging_dir.glob("attack_rag_seed_*.json")):
            pytest.skip("Staging ATT&CK réel non généré dans cet environnement.")
        kb = load_attack_runtime_knowledge(find_latest_attack_staging_file(staging_dir))
        assert len(kb) > 100
        assert has_technique(kb, "T1003")
