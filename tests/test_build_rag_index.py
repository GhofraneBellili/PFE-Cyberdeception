"""
Réf. tâche « maturation technique finale du chapitre 4 », §10 « Builder
offline explicite ».

Tests unitaires de `tools/rag/build_index.py` (§25.4 : pytest
obligatoire). Bundles/staging synthétiques uniquement — aucun
téléchargement, aucune dépendance au vrai `enterprise-attack.json`.
"""

import json

import pytest

from tools.rag.build_index import BuildRagIndexError, build_full_corpus_chunks


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def make_attack_seed():
    return {
        "source_file": "enterprise-attack.json",
        "source_sha256": "abc",
        "techniques": [
            {
                "technique_id": "T8001",
                "name": "Synthetic Technique",
                "tactics": ["initial-access"],
                "platforms": ["Windows"],
                "revoked": False,
                "deprecated": False,
                "source_evidence": [{"source_property": "name", "evidence_text": "Synthetic Technique"}],
            }
        ],
    }


def make_attack_report():
    """Réf. durcissement : même préfixe de fichier que le seed, schéma
    DIFFÉRENT (pas de clé 'techniques') — doit être exclu, jamais chargé
    par erreur (réf. bug corrigé : sorted(...)[-1] captait ce fichier)."""
    return {"schema": "attack_rag_seed_report", "relevant_technique_count": 1}


def make_d3fend_seed():
    return {"concepts": [{"source_technique_id": "D3-XX", "source_evidence": [{"source_property": "p", "evidence_text": "D3FEND passage"}]}]}


def make_engage_seed():
    return {"activities": [{"activity_id": "EAC0099", "description": "Engage passage."}]}


def make_literature_seed():
    return {"evidence": [{"evidence_id": "doc1__ev001", "source_id": "doc1", "page": 1, "locator": "abstract", "text": "Literature passage."}]}


class TestBuildFullCorpusChunks:
    def test_excludes_report_file_from_attack_seed_selection(self, tmp_path):
        """Réf. durcissement (bug réel corrigé) : le glob
        'attack_rag_seed_*.json' capte AUSSI le rapport d'extraction
        (même préfixe) — doit être exclu, sous peine de charger
        silencieusement 0 chunk ATT&CK."""
        attack_dir = tmp_path / "attack_staging"
        attack_dir.mkdir()
        _write_json(attack_dir / "attack_rag_seed_1.0.json", make_attack_seed())
        _write_json(attack_dir / "attack_rag_seed_report_1.0.json", make_attack_report())

        d3fend_path = tmp_path / "d3fend_seed.json"
        engage_path = tmp_path / "engage_seed.json"
        literature_path = tmp_path / "literature_seed.json"
        _write_json(d3fend_path, make_d3fend_seed())
        _write_json(engage_path, make_engage_seed())
        _write_json(literature_path, make_literature_seed())

        chunks = build_full_corpus_chunks(
            attack_staging_dir=attack_dir,
            d3fend_seed_path=d3fend_path,
            engage_seed_path=engage_path,
            literature_seed_path=literature_path,
        )
        attack_chunks = [c for c in chunks if c.source_type == "attack"]
        assert len(attack_chunks) == 1
        assert attack_chunks[0].chunk_id == "attack:T8001:0"

    def test_combines_all_four_sources(self, tmp_path):
        attack_dir = tmp_path / "attack_staging"
        attack_dir.mkdir()
        _write_json(attack_dir / "attack_rag_seed_1.0.json", make_attack_seed())

        d3fend_path = tmp_path / "d3fend_seed.json"
        engage_path = tmp_path / "engage_seed.json"
        literature_path = tmp_path / "literature_seed.json"
        _write_json(d3fend_path, make_d3fend_seed())
        _write_json(engage_path, make_engage_seed())
        _write_json(literature_path, make_literature_seed())

        chunks = build_full_corpus_chunks(
            attack_staging_dir=attack_dir,
            d3fend_seed_path=d3fend_path,
            engage_seed_path=engage_path,
            literature_seed_path=literature_path,
        )
        assert {c.source_type for c in chunks} == {"attack", "d3fend", "engage", "literature"}

    def test_missing_attack_staging_raises_explicitly(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        with pytest.raises(BuildRagIndexError):
            build_full_corpus_chunks(attack_staging_dir=empty_dir)

    def test_real_attack_staging_produces_only_attack_chunks_not_report_content(self):
        """Réf. non-régression : le staging RÉEL déjà versionné
        (data/attack/staging/) ne doit produire QUE des chunks issus du
        seed, jamais un artefact du rapport."""
        from pathlib import Path

        attack_dir = Path("data/attack/staging")
        if not attack_dir.exists() or not list(attack_dir.glob("attack_rag_seed_*.json")):
            pytest.skip("Staging ATT&CK réel non généré dans cet environnement.")
        chunks = build_full_corpus_chunks(
            attack_staging_dir=attack_dir,
            d3fend_seed_path=Path("data/deception/staging/d3fend_deception_seed_1.5.0.json"),
            engage_seed_path=Path("data/deception/staging/engage_activity_seed_1.0.json"),
            literature_seed_path=Path("data/deception/staging/literature_evidence_seed_1.2.json"),
        )
        attack_chunks = [c for c in chunks if c.source_type == "attack"]
        assert len(attack_chunks) > 100  # le staging réel produit >1000 chunks ATT&CK
