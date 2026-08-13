"""
Réf. architecture : CLAUDE.md — contrat technique du PFE Cyberdéception.

Tests unitaires de src/knowledge_attack.py (§25.4 : pytest obligatoire).

Tous les bundles STIX utilisés ici sont synthétiques (créés dans tmp_path) :
aucun test ne dépend d'Internet ni du vrai enterprise-attack.json, la CI
tourne hors ligne. Les identifiants ATT&CK (T8001, T5555.010, ...) sont des
données de test uniquement ; TestGenerality vérifie explicitement qu'aucune
logique de production ne leur est liée.
"""

import json

import pytest

from src.knowledge_attack import (
    AttackKnowledgeError,
    DuplicateAttackTechniqueError,
    UnknownAttackTechniqueError,
    get_platforms,
    get_tactics,
    get_technique,
    has_technique,
    list_technique_ids,
    load_attack_knowledge,
    validate_graph_techniques,
)
from src.schemas import AttackGraph, NodeAttributes, TechniqueOccurrence

# ---------------------------------------------------------------------------
# Constructeurs auxiliaires
# ---------------------------------------------------------------------------


def make_attack_pattern(
    technique_id="T8001",
    *,
    stix_id=None,
    name="Synthetic Technique",
    description="Description synthétique de test.",
    tactics=("initial-access",),
    platforms=("Windows",),
    is_subtechnique=False,
    revoked=False,
    deprecated=False,
    version="1.0",
    url=None,
    include_external_id=True,
):
    """Construit un objet STIX 'attack-pattern' synthétique minimal."""
    stix_id = stix_id or f"attack-pattern--{technique_id.lower().replace('.', '-')}"
    url = url or f"https://attack.mitre.org/techniques/{technique_id.replace('.', '/')}"
    external_references = []
    if include_external_id:
        external_references.append(
            {"source_name": "mitre-attack", "external_id": technique_id, "url": url}
        )
    return {
        "type": "attack-pattern",
        "id": stix_id,
        "name": name,
        "description": description,
        "external_references": external_references,
        "kill_chain_phases": [
            {"kill_chain_name": "mitre-attack", "phase_name": tactic} for tactic in tactics
        ],
        "x_mitre_platforms": list(platforms),
        "x_mitre_is_subtechnique": is_subtechnique,
        "revoked": revoked,
        "x_mitre_deprecated": deprecated,
        "x_mitre_version": version,
    }


def write_bundle(tmp_path, objects, filename="bundle.json", bundle_type="bundle", spec_version="2.1"):
    payload = {
        "type": bundle_type,
        "id": "bundle--test-fixture",
        "spec_version": spec_version,
        "objects": objects,
    }
    path = tmp_path / filename
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def make_node_attributes(**overrides):
    base = dict(
        tactics=["execution"],
        outcomes=[],
        q_local_success=0.5,
        impact_confidentiality=0.5,
        impact_integrity=0.5,
        impact_availability=0.5,
        critical_asset=False,
        accessible_asset=True,
    )
    base.update(overrides)
    return base


def make_occurrence(technique_id, asset_id):
    return TechniqueOccurrence(
        technique_id=technique_id,
        asset_id=asset_id,
        attributes=NodeAttributes(**make_node_attributes()),
    )


# ---------------------------------------------------------------------------
# A. Chargement
# ---------------------------------------------------------------------------


class TestLoading:
    def test_valid_bundle_loaded(self, tmp_path):
        path = write_bundle(tmp_path, [make_attack_pattern("T8001")])
        kb = load_attack_knowledge(path)
        assert has_technique(kb, "T8001")
        assert kb.source_path == path
        assert kb.bundle_type == "bundle"
        assert kb.spec_version == "2.1"

    def test_syntactically_invalid_json_rejected(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{ceci n'est pas du JSON valide", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_attack_knowledge(path)

    def test_invalid_root_rejected(self, tmp_path):
        path = tmp_path / "list_root.json"
        path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with pytest.raises(AttackKnowledgeError):
            load_attack_knowledge(path)

    def test_missing_objects_rejected(self, tmp_path):
        path = tmp_path / "no_objects.json"
        path.write_text(json.dumps({"type": "bundle"}), encoding="utf-8")
        with pytest.raises(AttackKnowledgeError):
            load_attack_knowledge(path)

    def test_objects_not_list_rejected(self, tmp_path):
        path = tmp_path / "bad_objects.json"
        path.write_text(
            json.dumps({"type": "bundle", "objects": "not-a-list"}), encoding="utf-8"
        )
        with pytest.raises(AttackKnowledgeError):
            load_attack_knowledge(path)


# ---------------------------------------------------------------------------
# B. Extraction
# ---------------------------------------------------------------------------


class TestExtraction:
    def test_attack_pattern_extracted(self, tmp_path):
        path = write_bundle(tmp_path, [make_attack_pattern("T8001")])
        kb = load_attack_knowledge(path)
        assert list_technique_ids(kb) == ["T8001"]

    def test_non_attack_pattern_object_ignored(self, tmp_path):
        other = {"type": "course-of-action", "id": "course-of-action--x", "name": "Mitigation"}
        path = write_bundle(tmp_path, [other, make_attack_pattern("T8001")])
        kb = load_attack_knowledge(path)
        assert list_technique_ids(kb) == ["T8001"]

    def test_technique_id_extracted_from_external_references(self, tmp_path):
        path = write_bundle(tmp_path, [make_attack_pattern("T8001.002")])
        kb = load_attack_knowledge(path)
        assert has_technique(kb, "T8001.002")

    def test_stix_id_conserved(self, tmp_path):
        path = write_bundle(
            tmp_path, [make_attack_pattern("T8001", stix_id="attack-pattern--fixed-uuid")]
        )
        kb = load_attack_knowledge(path)
        assert get_technique(kb, "T8001").stix_id == "attack-pattern--fixed-uuid"

    def test_name_conserved(self, tmp_path):
        path = write_bundle(tmp_path, [make_attack_pattern("T8001", name="Nom synthétique")])
        kb = load_attack_knowledge(path)
        assert get_technique(kb, "T8001").name == "Nom synthétique"

    def test_description_conserved(self, tmp_path):
        path = write_bundle(
            tmp_path,
            [make_attack_pattern("T8001", description="Texte de description synthétique.")],
        )
        kb = load_attack_knowledge(path)
        assert get_technique(kb, "T8001").description == "Texte de description synthétique."

    def test_tactics_extracted(self, tmp_path):
        path = write_bundle(
            tmp_path, [make_attack_pattern("T8001", tactics=("initial-access", "execution"))]
        )
        kb = load_attack_knowledge(path)
        assert get_tactics(kb, "T8001") == ("initial-access", "execution")

    def test_platforms_extracted(self, tmp_path):
        path = write_bundle(tmp_path, [make_attack_pattern("T8001", platforms=("Windows", "Linux"))])
        kb = load_attack_knowledge(path)
        assert get_platforms(kb, "T8001") == ("Windows", "Linux")

    def test_version_extracted(self, tmp_path):
        path = write_bundle(tmp_path, [make_attack_pattern("T8001", version="2.3")])
        kb = load_attack_knowledge(path)
        assert get_technique(kb, "T8001").version == "2.3"

    def test_external_url_extracted(self, tmp_path):
        path = write_bundle(
            tmp_path, [make_attack_pattern("T8001", url="https://example.org/T8001")]
        )
        kb = load_attack_knowledge(path)
        assert get_technique(kb, "T8001").external_url == "https://example.org/T8001"


# ---------------------------------------------------------------------------
# C. Identifiants
# ---------------------------------------------------------------------------


class TestIdentifiers:
    def test_main_technique_supported(self, tmp_path):
        path = write_bundle(tmp_path, [make_attack_pattern("T8001")])
        kb = load_attack_knowledge(path)
        assert has_technique(kb, "T8001")

    def test_subtechnique_supported(self, tmp_path):
        path = write_bundle(
            tmp_path, [make_attack_pattern("T8001.001", is_subtechnique=True)]
        )
        kb = load_attack_knowledge(path)
        assert get_technique(kb, "T8001.001").is_subtechnique is True

    def test_attack_pattern_without_external_id_ignored(self, tmp_path):
        path = write_bundle(tmp_path, [make_attack_pattern("T8001", include_external_id=False)])
        kb = load_attack_knowledge(path)
        assert list_technique_ids(kb) == []

    def test_duplicate_technique_id_rejected(self, tmp_path):
        pattern_a = make_attack_pattern("T8001", stix_id="attack-pattern--a")
        pattern_b = make_attack_pattern("T8001", stix_id="attack-pattern--b")
        path = write_bundle(tmp_path, [pattern_a, pattern_b])
        with pytest.raises(DuplicateAttackTechniqueError):
            load_attack_knowledge(path)

    def test_duplicate_not_raised_when_one_copy_filtered_out_by_default(self, tmp_path):
        """Choix retenu (documenté dans le rapport de cette étape) : le
        contrôle de doublon porte sur les techniques effectivement retenues
        après filtrage revoked/deprecated, pas sur les objets bruts du
        bundle — c'est cet ensemble-là que techniques_by_id doit garder non
        ambigu."""
        active_pattern = make_attack_pattern("T8001", revoked=False, stix_id="attack-pattern--active")
        revoked_pattern = make_attack_pattern("T8001", revoked=True, stix_id="attack-pattern--revoked")
        path = write_bundle(tmp_path, [active_pattern, revoked_pattern])
        kb = load_attack_knowledge(path)
        assert get_technique(kb, "T8001").revoked is False


# ---------------------------------------------------------------------------
# D. Revoked / deprecated
# ---------------------------------------------------------------------------


class TestRevokedDeprecated:
    def test_revoked_excluded_by_default(self, tmp_path):
        path = write_bundle(tmp_path, [make_attack_pattern("T8001", revoked=True)])
        kb = load_attack_knowledge(path)
        assert not has_technique(kb, "T8001")

    def test_deprecated_excluded_by_default(self, tmp_path):
        path = write_bundle(tmp_path, [make_attack_pattern("T8001", deprecated=True)])
        kb = load_attack_knowledge(path)
        assert not has_technique(kb, "T8001")

    def test_include_revoked_true(self, tmp_path):
        path = write_bundle(tmp_path, [make_attack_pattern("T8001", revoked=True)])
        kb = load_attack_knowledge(path, include_revoked=True)
        assert has_technique(kb, "T8001")
        assert get_technique(kb, "T8001").revoked is True

    def test_include_deprecated_true(self, tmp_path):
        path = write_bundle(tmp_path, [make_attack_pattern("T8001", deprecated=True)])
        kb = load_attack_knowledge(path, include_deprecated=True)
        assert has_technique(kb, "T8001")
        assert get_technique(kb, "T8001").deprecated is True

    def test_revoked_and_deprecated_are_independent(self, tmp_path):
        """Ne jamais confondre revoked et deprecated : une technique revoked
        mais non deprecated doit rester exclue par include_deprecated seul,
        et réciproquement."""
        revoked_pattern = make_attack_pattern(
            "T8001", revoked=True, deprecated=False, stix_id="attack-pattern--rev"
        )
        deprecated_pattern = make_attack_pattern(
            "T8002", revoked=False, deprecated=True, stix_id="attack-pattern--dep"
        )
        path = write_bundle(tmp_path, [revoked_pattern, deprecated_pattern])

        kb_default = load_attack_knowledge(path)
        assert not has_technique(kb_default, "T8001")
        assert not has_technique(kb_default, "T8002")

        kb_revoked_only = load_attack_knowledge(path, include_revoked=True)
        assert has_technique(kb_revoked_only, "T8001")
        assert not has_technique(kb_revoked_only, "T8002")

        kb_deprecated_only = load_attack_knowledge(path, include_deprecated=True)
        assert not has_technique(kb_deprecated_only, "T8001")
        assert has_technique(kb_deprecated_only, "T8002")


# ---------------------------------------------------------------------------
# E. Accès
# ---------------------------------------------------------------------------


class TestAccess:
    def test_get_technique_valid(self, tmp_path):
        path = write_bundle(tmp_path, [make_attack_pattern("T8001")])
        kb = load_attack_knowledge(path)
        assert get_technique(kb, "T8001").technique_id == "T8001"

    def test_get_technique_unknown_rejected(self, tmp_path):
        path = write_bundle(tmp_path, [make_attack_pattern("T8001")])
        kb = load_attack_knowledge(path)
        with pytest.raises(UnknownAttackTechniqueError):
            get_technique(kb, "T9999")

    def test_has_technique_true_false(self, tmp_path):
        path = write_bundle(tmp_path, [make_attack_pattern("T8001")])
        kb = load_attack_knowledge(path)
        assert has_technique(kb, "T8001") is True
        assert has_technique(kb, "T9999") is False

    def test_list_technique_ids_stable(self, tmp_path):
        path = write_bundle(
            tmp_path,
            [
                make_attack_pattern("T8003", stix_id="attack-pattern--3"),
                make_attack_pattern("T8001", stix_id="attack-pattern--1"),
                make_attack_pattern("T8002", stix_id="attack-pattern--2"),
            ],
        )
        kb = load_attack_knowledge(path)
        assert list_technique_ids(kb) == ["T8003", "T8001", "T8002"]

    def test_get_tactics(self, tmp_path):
        path = write_bundle(tmp_path, [make_attack_pattern("T8001", tactics=("execution",))])
        kb = load_attack_knowledge(path)
        assert get_tactics(kb, "T8001") == ("execution",)

    def test_get_platforms(self, tmp_path):
        path = write_bundle(tmp_path, [make_attack_pattern("T8001", platforms=("Linux",))])
        kb = load_attack_knowledge(path)
        assert get_platforms(kb, "T8001") == ("Linux",)


# ---------------------------------------------------------------------------
# F. Validation d'un graphe contre la KB
# ---------------------------------------------------------------------------


class TestGraphValidation:
    def test_validate_graph_all_known_accepted(self, tmp_path):
        path = write_bundle(
            tmp_path,
            [make_attack_pattern("T8001", stix_id="a1"), make_attack_pattern("T8002", stix_id="a2")],
        )
        kb = load_attack_knowledge(path)
        graph = AttackGraph(
            nodes=[make_occurrence("T8001", "HOST-A"), make_occurrence("T8002", "HOST-B")],
            edges=[],
        )
        validate_graph_techniques(graph, kb)  # ne doit pas lever

    def test_validate_graph_unknown_technique_rejected(self, tmp_path):
        path = write_bundle(tmp_path, [make_attack_pattern("T8001")])
        kb = load_attack_knowledge(path)
        graph = AttackGraph(nodes=[make_occurrence("T9001", "HOST-A")], edges=[])
        with pytest.raises(UnknownAttackTechniqueError):
            validate_graph_techniques(graph, kb)

    def test_validate_graph_multiple_unknown_all_listed(self, tmp_path):
        path = write_bundle(tmp_path, [make_attack_pattern("T8001")])
        kb = load_attack_knowledge(path)
        graph = AttackGraph(
            nodes=[make_occurrence("T9002", "HOST-A"), make_occurrence("T9001", "HOST-B")],
            edges=[],
        )
        with pytest.raises(UnknownAttackTechniqueError) as exc_info:
            validate_graph_techniques(graph, kb)
        message = str(exc_info.value)
        assert "T9001" in message
        assert "T9002" in message

    def test_validate_graph_does_not_mutate_graph(self, tmp_path):
        path = write_bundle(tmp_path, [make_attack_pattern("T8001")])
        kb = load_attack_knowledge(path)
        graph = AttackGraph(nodes=[make_occurrence("T8001", "HOST-A")], edges=[])
        snapshot = graph.model_dump()
        validate_graph_techniques(graph, kb)
        assert graph.model_dump() == snapshot


# ---------------------------------------------------------------------------
# G. Généralité — aucune logique liée au cas d'usage de référence (§20)
# ---------------------------------------------------------------------------


class TestGenerality:
    def test_generic_ids_unrelated_to_reference_case(self, tmp_path):
        """Le cas de référence de CLAUDE.md (§20) utilise T1566, T1190,
        T1003, T1078, T1059, T1041. Ce test utilise un ensemble totalement
        différent pour démontrer qu'aucune logique de production n'y est
        liée."""
        pattern = make_attack_pattern(
            "T5555.010",
            name="Technique fictive de test",
            tactics=("collection",),
            platforms=("macOS",),
        )
        path = write_bundle(tmp_path, [pattern])
        kb = load_attack_knowledge(path)

        assert has_technique(kb, "T5555.010")
        record = get_technique(kb, "T5555.010")
        assert record.tactics == ("collection",)
        assert record.platforms == ("macOS",)

        graph = AttackGraph(nodes=[make_occurrence("T5555.010", "FICTIONAL-ASSET")], edges=[])
        validate_graph_techniques(graph, kb)  # ne doit pas lever
