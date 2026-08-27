"""
Réf. architecture : CLAUDE.md — contrat technique du PFE Cyberdéception.

Tests unitaires de src/knowledge_deception.py (§25.4 : pytest obligatoire).

Tous les catalogues JSON utilisés ici sont synthétiques (créés dans
tmp_path) : aucun test ne dépend d'Internet, de D3FEND réel, d'Engage réel
ni d'un LLM. Les identifiants (D-001, synth-mech-alpha, ...) sont des
données de test uniquement ; TestGenerality vérifie explicitement qu'aucune
logique de production n'est liée au cas d'usage de référence (DT11, DT12,
T1003, T1078, DC, WS, DB).
"""

import json

import pytest
from pydantic import ValidationError

from src.knowledge_deception import (
    DeceptionKnowledgeError,
    DuplicateDeceptionMechanismError,
    UnknownDeceptionMechanismError,
    get_admissibility_profile,
    get_deception,
    get_evidence,
    has_deception,
    list_deception_ids,
    load_attack_deception_mapping,
    load_deception_catalog,
    to_sp1_mapping,
    validate_deception_ids,
)

# ---------------------------------------------------------------------------
# Constructeurs auxiliaires
# ---------------------------------------------------------------------------


def make_mechanism_payload(
    deception_id="SYN-0001",
    *,
    name="Synthetic deception mechanism",
    description="Description synthétique de test.",
    target_artifacts=("credential_store",),
    requirements=("agent de journalisation",),
    possible_placements=("poste",),
    interaction_mechanism="Déclenche une alerte lors de l'utilisation.",
    realism_factors=("format cohérent",),
    progression_effects=("stop",),
    resource_requirements=None,
    maintenance_requirements=("rotation périodique",),
    evidence=None,
    version="1.0.0",
    admissibility_profile=None,
    metadata=None,
):
    """Construit un payload JSON de DeceptionMechanism valide par défaut,
    personnalisable via les paramètres."""
    if resource_requirements is None:
        resource_requirements = {
            "cpu": "faible",
            "ram": "faible",
            "disk": "faible",
            "network": "faible",
        }
    if evidence is None:
        evidence = [{"source": "Source synthétique", "passage": "Extrait synthétique de test."}]
    if admissibility_profile is None:
        admissibility_profile = {
            "allowed_location_types": [],
            "required_asset_types": [],
            "required_services": [],
            "required_artifacts": [],
            "exposure_mode": None,
            "metadata": {},
        }
    if metadata is None:
        metadata = {}
    return {
        "id": deception_id,
        "name": name,
        "description": description,
        "target_artifacts": list(target_artifacts),
        "requirements": list(requirements),
        "possible_placements": list(possible_placements),
        "interaction_mechanism": interaction_mechanism,
        "realism_factors": list(realism_factors),
        "progression_effects": list(progression_effects),
        "resource_requirements": resource_requirements,
        "maintenance_requirements": list(maintenance_requirements),
        "evidence": evidence,
        "version": version,
        "admissibility_profile": admissibility_profile,
        "metadata": metadata,
    }


def write_catalog(tmp_path, mechanisms, filename="catalog.json", catalog_version="1.0"):
    payload = {"catalog_version": catalog_version, "mechanisms": mechanisms}
    path = tmp_path / filename
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def write_mapping(tmp_path, relations, filename="mapping.json", mapping_version="1.0"):
    payload = {"mapping_version": mapping_version, "relations": relations}
    path = tmp_path / filename
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# A. Chargement
# ---------------------------------------------------------------------------


class TestLoading:
    def test_valid_catalog_loaded(self, tmp_path):
        path = write_catalog(tmp_path, [make_mechanism_payload("D-001")])
        kb = load_deception_catalog(path)
        assert has_deception(kb, "D-001")
        assert kb.catalog_version == "1.0"
        assert kb.source_path == path

    def test_syntactically_invalid_json_rejected(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{ceci n'est pas du JSON valide", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_deception_catalog(path)

    def test_non_object_root_rejected(self, tmp_path):
        path = tmp_path / "list_root.json"
        path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with pytest.raises(DeceptionKnowledgeError):
            load_deception_catalog(path)

    def test_catalog_version_missing_rejected(self, tmp_path):
        payload = {"mechanisms": [make_mechanism_payload("D-001")]}
        path = tmp_path / "no_version.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(DeceptionKnowledgeError):
            load_deception_catalog(path)

    def test_catalog_version_wrong_type_rejected(self, tmp_path):
        payload = {"catalog_version": 1.0, "mechanisms": [make_mechanism_payload("D-001")]}
        path = tmp_path / "bad_version_type.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(DeceptionKnowledgeError):
            load_deception_catalog(path)

    def test_catalog_version_empty_rejected(self, tmp_path):
        payload = {"catalog_version": "   ", "mechanisms": [make_mechanism_payload("D-001")]}
        path = tmp_path / "empty_version.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(DeceptionKnowledgeError):
            load_deception_catalog(path)

    def test_mechanisms_missing_rejected(self, tmp_path):
        payload = {"catalog_version": "1.0"}
        path = tmp_path / "no_mechanisms.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(DeceptionKnowledgeError):
            load_deception_catalog(path)

    def test_mechanisms_not_list_rejected(self, tmp_path):
        payload = {"catalog_version": "1.0", "mechanisms": "not-a-list"}
        path = tmp_path / "bad_mechanisms.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(DeceptionKnowledgeError):
            load_deception_catalog(path)


# ---------------------------------------------------------------------------
# B. Validation DeceptionMechanism
# ---------------------------------------------------------------------------


class TestMechanismValidation:
    def test_mechanism_valid_loaded(self, tmp_path):
        path = write_catalog(tmp_path, [make_mechanism_payload("D-001")])
        kb = load_deception_catalog(path)
        assert has_deception(kb, "D-001")

    def test_id_conserved_exactly(self, tmp_path):
        path = write_catalog(tmp_path, [make_mechanism_payload("D-Synthetic-042")])
        kb = load_deception_catalog(path)
        assert get_deception(kb, "D-Synthetic-042").id == "D-Synthetic-042"

    def test_name_conserved(self, tmp_path):
        path = write_catalog(tmp_path, [make_mechanism_payload("D-001", name="Nom synthétique")])
        kb = load_deception_catalog(path)
        assert get_deception(kb, "D-001").name == "Nom synthétique"

    def test_description_conserved(self, tmp_path):
        path = write_catalog(
            tmp_path, [make_mechanism_payload("D-001", description="Texte synthétique.")]
        )
        kb = load_deception_catalog(path)
        assert get_deception(kb, "D-001").description == "Texte synthétique."

    def test_target_artifacts_conserved(self, tmp_path):
        path = write_catalog(
            tmp_path,
            [make_mechanism_payload("D-001", target_artifacts=("artifact_a", "artifact_b"))],
        )
        kb = load_deception_catalog(path)
        assert get_deception(kb, "D-001").target_artifacts == ["artifact_a", "artifact_b"]

    def test_requirements_conserved(self, tmp_path):
        path = write_catalog(tmp_path, [make_mechanism_payload("D-001", requirements=("req_a",))])
        kb = load_deception_catalog(path)
        assert get_deception(kb, "D-001").requirements == ["req_a"]

    def test_possible_placements_conserved(self, tmp_path):
        path = write_catalog(
            tmp_path, [make_mechanism_payload("D-001", possible_placements=("placement_a",))]
        )
        kb = load_deception_catalog(path)
        assert get_deception(kb, "D-001").possible_placements == ["placement_a"]

    def test_interaction_mechanism_conserved(self, tmp_path):
        path = write_catalog(
            tmp_path,
            [make_mechanism_payload("D-001", interaction_mechanism="Mécanisme synthétique.")],
        )
        kb = load_deception_catalog(path)
        assert get_deception(kb, "D-001").interaction_mechanism == "Mécanisme synthétique."

    def test_realism_factors_conserved(self, tmp_path):
        path = write_catalog(
            tmp_path, [make_mechanism_payload("D-001", realism_factors=("facteur_a",))]
        )
        kb = load_deception_catalog(path)
        assert get_deception(kb, "D-001").realism_factors == ["facteur_a"]

    def test_progression_effects_conserved(self, tmp_path):
        path = write_catalog(
            tmp_path, [make_mechanism_payload("D-001", progression_effects=("stop", "delay"))]
        )
        kb = load_deception_catalog(path)
        assert get_deception(kb, "D-001").progression_effects == ["stop", "delay"]

    def test_resource_requirements_conserved(self, tmp_path):
        path = write_catalog(
            tmp_path,
            [
                make_mechanism_payload(
                    "D-001",
                    resource_requirements={
                        "cpu": "faible",
                        "ram": "moyen",
                        "disk": "négligeable",
                        "network": "faible",
                    },
                )
            ],
        )
        kb = load_deception_catalog(path)
        record = get_deception(kb, "D-001")
        assert record.resource_requirements.cpu == "faible"
        assert record.resource_requirements.ram == "moyen"
        assert record.resource_requirements.disk == "négligeable"
        assert record.resource_requirements.network == "faible"

    def test_maintenance_requirements_conserved(self, tmp_path):
        path = write_catalog(
            tmp_path, [make_mechanism_payload("D-001", maintenance_requirements=("maint_a",))]
        )
        kb = load_deception_catalog(path)
        assert get_deception(kb, "D-001").maintenance_requirements == ["maint_a"]

    def test_version_conserved(self, tmp_path):
        path = write_catalog(tmp_path, [make_mechanism_payload("D-001", version="3.2.1")])
        kb = load_deception_catalog(path)
        assert get_deception(kb, "D-001").version == "3.2.1"

    def test_metadata_conserved(self, tmp_path):
        path = write_catalog(
            tmp_path, [make_mechanism_payload("D-001", metadata={"internal_note": "valeur"})]
        )
        kb = load_deception_catalog(path)
        assert get_deception(kb, "D-001").metadata == {"internal_note": "valeur"}

    def test_admissibility_profile_conserved(self, tmp_path):
        profile = {
            "allowed_location_types": ["poste"],
            "required_asset_types": ["windows"],
            "required_services": ["smb"],
            "required_artifacts": ["credential_store"],
            "exposure_mode": "passive",
            "metadata": {},
        }
        path = write_catalog(
            tmp_path, [make_mechanism_payload("D-001", admissibility_profile=profile)]
        )
        kb = load_deception_catalog(path)
        loaded_profile = get_admissibility_profile(kb, "D-001")
        assert loaded_profile.allowed_location_types == ["poste"]
        assert loaded_profile.exposure_mode == "passive"


# ---------------------------------------------------------------------------
# C. Identifiants
# ---------------------------------------------------------------------------


class TestIdentifiers:
    def test_free_form_id_accepted(self, tmp_path):
        path = write_catalog(tmp_path, [make_mechanism_payload("d3f:DecoyObject")])
        kb = load_deception_catalog(path)
        assert has_deception(kb, "d3f:DecoyObject")

    def test_non_dtxx_id_accepted(self, tmp_path):
        """Au moins un identifiant qui ne suit pas le format DTxx."""
        path = write_catalog(tmp_path, [make_mechanism_payload("engage:decoy-credentials")])
        kb = load_deception_catalog(path)
        assert has_deception(kb, "engage:decoy-credentials")

    def test_duplicate_id_rejected(self, tmp_path):
        """Aucune fusion automatique : un doublon lève, il ne garde ni le
        premier ni le dernier silencieusement."""
        path = write_catalog(
            tmp_path,
            [
                make_mechanism_payload("D-001", name="Première fiche"),
                make_mechanism_payload("D-001", name="Seconde fiche"),
            ],
        )
        with pytest.raises(DuplicateDeceptionMechanismError):
            load_deception_catalog(path)


# ---------------------------------------------------------------------------
# D. Evidence
# ---------------------------------------------------------------------------


class TestEvidence:
    def test_mechanism_with_valid_evidence_accepted(self, tmp_path):
        path = write_catalog(
            tmp_path,
            [
                make_mechanism_payload(
                    "D-001", evidence=[{"source": "Source A", "passage": "Extrait A."}]
                )
            ],
        )
        kb = load_deception_catalog(path)
        assert has_deception(kb, "D-001")

    def test_empty_evidence_rejected_by_knowledge_deception(self, tmp_path):
        """Règle plus stricte que le schéma Pydantic seul (§8 de la tâche) :
        une fiche validée doit posséder au moins une preuve."""
        path = write_catalog(tmp_path, [make_mechanism_payload("D-001", evidence=[])])
        with pytest.raises(DeceptionKnowledgeError):
            load_deception_catalog(path)

    def test_evidence_empty_source_rejected(self, tmp_path):
        path = write_catalog(
            tmp_path,
            [make_mechanism_payload("D-001", evidence=[{"source": "", "passage": "Extrait."}])],
        )
        with pytest.raises(ValidationError):
            load_deception_catalog(path)

    def test_evidence_empty_passage_rejected(self, tmp_path):
        path = write_catalog(
            tmp_path,
            [make_mechanism_payload("D-001", evidence=[{"source": "Source", "passage": ""}])],
        )
        with pytest.raises(ValidationError):
            load_deception_catalog(path)

    def test_multiple_evidence_conserved_in_order(self, tmp_path):
        evidence = [
            {"source": "Source A", "passage": "Extrait A."},
            {"source": "Source B", "passage": "Extrait B."},
        ]
        path = write_catalog(tmp_path, [make_mechanism_payload("D-001", evidence=evidence)])
        kb = load_deception_catalog(path)
        loaded = get_evidence(kb, "D-001")
        assert [e.source for e in loaded] == ["Source A", "Source B"]


# ---------------------------------------------------------------------------
# E. Accès
# ---------------------------------------------------------------------------


class TestAccess:
    def test_get_deception_known(self, tmp_path):
        path = write_catalog(tmp_path, [make_mechanism_payload("D-001")])
        kb = load_deception_catalog(path)
        assert get_deception(kb, "D-001").id == "D-001"

    def test_get_deception_unknown_rejected(self, tmp_path):
        path = write_catalog(tmp_path, [make_mechanism_payload("D-001")])
        kb = load_deception_catalog(path)
        with pytest.raises(UnknownDeceptionMechanismError):
            get_deception(kb, "D-999")

    def test_has_deception_true(self, tmp_path):
        path = write_catalog(tmp_path, [make_mechanism_payload("D-001")])
        kb = load_deception_catalog(path)
        assert has_deception(kb, "D-001") is True

    def test_has_deception_false(self, tmp_path):
        path = write_catalog(tmp_path, [make_mechanism_payload("D-001")])
        kb = load_deception_catalog(path)
        assert has_deception(kb, "D-999") is False

    def test_list_deception_ids_stable(self, tmp_path):
        path = write_catalog(
            tmp_path,
            [
                make_mechanism_payload("D-003"),
                make_mechanism_payload("D-001"),
                make_mechanism_payload("D-002"),
            ],
        )
        kb = load_deception_catalog(path)
        assert list_deception_ids(kb) == ["D-003", "D-001", "D-002"]

    def test_get_evidence(self, tmp_path):
        path = write_catalog(
            tmp_path, [make_mechanism_payload("D-001", evidence=[{"source": "S", "passage": "P"}])]
        )
        kb = load_deception_catalog(path)
        evidence = get_evidence(kb, "D-001")
        assert evidence[0].source == "S"

    def test_get_admissibility_profile(self, tmp_path):
        path = write_catalog(tmp_path, [make_mechanism_payload("D-001")])
        kb = load_deception_catalog(path)
        profile = get_admissibility_profile(kb, "D-001")
        assert profile.allowed_location_types == []


# ---------------------------------------------------------------------------
# F. Catalogue fermé
# ---------------------------------------------------------------------------


class TestClosedCatalog:
    def test_validate_deception_ids_accepts_known(self, tmp_path):
        path = write_catalog(
            tmp_path, [make_mechanism_payload("D-001"), make_mechanism_payload("D-002")]
        )
        kb = load_deception_catalog(path)
        validate_deception_ids(["D-001", "D-002"], kb)  # ne doit pas lever

    def test_validate_deception_ids_unknown_rejected(self, tmp_path):
        path = write_catalog(tmp_path, [make_mechanism_payload("D-001")])
        kb = load_deception_catalog(path)
        with pytest.raises(UnknownDeceptionMechanismError):
            validate_deception_ids(["D-999"], kb)

    def test_validate_deception_ids_multiple_unknown_all_listed(self, tmp_path):
        path = write_catalog(tmp_path, [make_mechanism_payload("D-001")])
        kb = load_deception_catalog(path)
        with pytest.raises(UnknownDeceptionMechanismError) as exc_info:
            validate_deception_ids(["D-Y", "D-X"], kb)
        message = str(exc_info.value)
        assert "D-X" in message
        assert "D-Y" in message

    def test_validate_deception_ids_duplicate_input_not_ambiguous(self, tmp_path):
        path = write_catalog(tmp_path, [make_mechanism_payload("D-001")])
        kb = load_deception_catalog(path)
        with pytest.raises(UnknownDeceptionMechanismError) as exc_info:
            validate_deception_ids(["D-999", "D-999", "D-999"], kb)
        message = str(exc_info.value)
        assert message.count("D-999") == 1


# ---------------------------------------------------------------------------
# G. Hash / provenance
# ---------------------------------------------------------------------------


class TestProvenance:
    def test_source_path_correct(self, tmp_path):
        path = write_catalog(tmp_path, [make_mechanism_payload("D-001")])
        kb = load_deception_catalog(path)
        assert kb.source_path == path

    def test_source_sha256_computed(self, tmp_path):
        path = write_catalog(tmp_path, [make_mechanism_payload("D-001")])
        kb = load_deception_catalog(path)
        assert len(kb.source_sha256) == 64
        int(kb.source_sha256, 16)  # doit être une chaîne hexadécimale valide

    def test_same_file_same_hash(self, tmp_path):
        path = write_catalog(tmp_path, [make_mechanism_payload("D-001")])
        kb_a = load_deception_catalog(path)
        kb_b = load_deception_catalog(path)
        assert kb_a.source_sha256 == kb_b.source_sha256

    def test_modified_content_different_hash(self, tmp_path):
        path = write_catalog(tmp_path, [make_mechanism_payload("D-001")])
        kb_before = load_deception_catalog(path)
        path.write_text(
            json.dumps(
                {"catalog_version": "1.1", "mechanisms": [make_mechanism_payload("D-001")]}
            ),
            encoding="utf-8",
        )
        kb_after = load_deception_catalog(path)
        assert kb_before.source_sha256 != kb_after.source_sha256


# ---------------------------------------------------------------------------
# H. Généralité — aucune logique liée au cas d'usage de référence
# ---------------------------------------------------------------------------


class TestGenerality:
    def test_generic_ids_unrelated_to_reference_case(self, tmp_path):
        """Ni DT11/DT12 ni T1003/T1078/DC/WS/DB : identifiants totalement
        différents pour démontrer l'absence de logique spécifique."""
        mechanisms = [
            make_mechanism_payload("synth-mech-alpha", name="Alpha"),
            make_mechanism_payload("synth-mech-beta", name="Beta"),
        ]
        path = write_catalog(tmp_path, mechanisms)
        kb = load_deception_catalog(path)
        assert set(list_deception_ids(kb)) == {"synth-mech-alpha", "synth-mech-beta"}
        assert get_deception(kb, "synth-mech-alpha").name == "Alpha"


# ---------------------------------------------------------------------------
# I. Non-interprétation SP1
# ---------------------------------------------------------------------------


class TestNoSp1Interpretation:
    def test_empty_allowed_location_types_loaded_without_sp1_semantics(self, tmp_path):
        """Une liste vide est chargée et conservée telle quelle ; sa
        sémantique (aucune restriction connue vs. aucun emplacement
        autorisé) appartient au futur SP1, pas à ce module."""
        profile = {
            "allowed_location_types": [],
            "required_asset_types": [],
            "required_services": [],
            "required_artifacts": [],
            "exposure_mode": None,
            "metadata": {},
        }
        path = write_catalog(
            tmp_path, [make_mechanism_payload("D-001", admissibility_profile=profile)]
        )
        kb = load_deception_catalog(path)
        loaded_profile = get_admissibility_profile(kb, "D-001")
        assert loaded_profile.allowed_location_types == []


# ---------------------------------------------------------------------------
# Immutabilité de l'index
# ---------------------------------------------------------------------------


class TestImmutability:
    def test_mechanisms_by_id_is_read_only(self, tmp_path):
        path = write_catalog(tmp_path, [make_mechanism_payload("D-001")])
        kb = load_deception_catalog(path)
        with pytest.raises(TypeError):
            kb.mechanisms_by_id["NEW"] = get_deception(kb, "D-001")


# ---------------------------------------------------------------------------
# J. Mapping M_{i,d} — réf. §10.2 (synthétique uniquement, cf. docstring
# de module ; le mapping réel est couvert par tests/test_mapping_builder.py)
# ---------------------------------------------------------------------------


def make_relation(attack_id="T1078", mechanism_id="D-001", evidence=None, origin="synthetic"):
    if evidence is None:
        evidence = [{"source": "synthetic.json", "relation_path": {}}]
    return {"attack_id": attack_id, "mechanism_id": mechanism_id, "evidence": evidence, "origin": origin}


class TestLoadAttackDeceptionMapping:
    def test_loads_valid_mapping(self, tmp_path):
        path = write_mapping(tmp_path, [make_relation()])
        mapping = load_attack_deception_mapping(path)
        assert mapping.mapping_version == "1.0"
        assert len(mapping.relations) == 1
        assert mapping.relations[0]["attack_id"] == "T1078"

    def test_missing_mapping_version_rejected(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({"relations": []}), encoding="utf-8")
        with pytest.raises(DeceptionKnowledgeError):
            load_attack_deception_mapping(path)

    def test_relation_missing_attack_id_rejected(self, tmp_path):
        bad_relation = {"mechanism_id": "D-001", "evidence": [], "origin": "synthetic"}
        path = write_mapping(tmp_path, [bad_relation])
        with pytest.raises(DeceptionKnowledgeError):
            load_attack_deception_mapping(path)

    def test_relation_missing_mechanism_id_rejected(self, tmp_path):
        bad_relation = {"attack_id": "T1078", "evidence": [], "origin": "synthetic"}
        path = write_mapping(tmp_path, [bad_relation])
        with pytest.raises(DeceptionKnowledgeError):
            load_attack_deception_mapping(path)

    def test_non_object_root_rejected(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with pytest.raises(DeceptionKnowledgeError):
            load_attack_deception_mapping(path)

    def test_relations_immutable(self, tmp_path):
        path = write_mapping(tmp_path, [make_relation()])
        mapping = load_attack_deception_mapping(path)
        with pytest.raises(TypeError):
            mapping.relations[0]["attack_id"] = "T9999"


class TestToSp1Mapping:
    def test_reduces_to_technique_to_mechanisms_dict(self, tmp_path):
        path = write_mapping(
            tmp_path,
            [
                make_relation(attack_id="T1078", mechanism_id="D-001"),
                make_relation(attack_id="T1078", mechanism_id="D-002"),
                make_relation(attack_id="T1003", mechanism_id="D-001"),
            ],
        )
        mapping = load_attack_deception_mapping(path)
        sp1_mapping = to_sp1_mapping(mapping)
        assert sp1_mapping == {"T1078": ["D-001", "D-002"], "T1003": ["D-001"]}

    def test_validates_against_catalog_when_provided(self, tmp_path):
        catalog_path = write_catalog(tmp_path, [make_mechanism_payload("D-001")])
        kb = load_deception_catalog(catalog_path)
        mapping_path = write_mapping(tmp_path, [make_relation(mechanism_id="D-001")])
        mapping = load_attack_deception_mapping(mapping_path)
        # Ne doit pas lever : D-001 appartient au catalogue.
        assert to_sp1_mapping(mapping, kb) == {"T1078": ["D-001"]}

    def test_unknown_mechanism_id_rejected_against_catalog(self, tmp_path):
        catalog_path = write_catalog(tmp_path, [make_mechanism_payload("D-001")])
        kb = load_deception_catalog(catalog_path)
        mapping_path = write_mapping(tmp_path, [make_relation(mechanism_id="D-999-UNKNOWN")])
        mapping = load_attack_deception_mapping(mapping_path)
        with pytest.raises(UnknownDeceptionMechanismError):
            to_sp1_mapping(mapping, kb)
