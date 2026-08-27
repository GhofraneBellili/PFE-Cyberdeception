"""
Réf. architecture : CLAUDE.md §7/§9/§10 — réf. tâche « separate knowledge
and organization capabilities ».

Tests unitaires de src/organization_catalog.py (§25.4 : pytest obligatoire).
"""

import json

import pytest

from src.knowledge_deception import load_deception_catalog
from src.organization_catalog import (
    OrganizationCatalogError,
    capabilities_by_id,
    enabled_mechanism_ids,
    load_organization_catalog,
    validate_against_knowledge_catalog,
)
from src.schemas import OrganizationDeceptionCapability, OrganizationDeceptionCatalog

REAL_CATALOG_PATH = "data/deception/deception_catalog.json"


def make_org_catalog(capabilities=None) -> OrganizationDeceptionCatalog:
    return OrganizationDeceptionCatalog(
        organization_id="test-org", catalog_version="v1", capabilities=capabilities or []
    )


class TestLoadOrganizationCatalog:
    def test_loads_valid_file(self, tmp_path):
        path = tmp_path / "org.json"
        path.write_text(
            json.dumps(
                {
                    "organization_id": "acme",
                    "catalog_version": "v1",
                    "capabilities": [{"mechanism_id": "D3-DUC", "enabled": True}],
                }
            ),
            encoding="utf-8",
        )
        catalog = load_organization_catalog(path)
        assert catalog.organization_id == "acme"
        assert catalog.capabilities[0].mechanism_id == "D3-DUC"

    def test_invalid_json_raises(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_organization_catalog(path)

    def test_missing_required_field_raises(self, tmp_path):
        path = tmp_path / "org.json"
        path.write_text(json.dumps({"organization_id": "acme"}), encoding="utf-8")
        with pytest.raises(Exception):
            load_organization_catalog(path)


class TestValidateAgainstKnowledgeCatalog:
    def test_all_referenced_mechanisms_exist_passes(self):
        kb = load_deception_catalog(REAL_CATALOG_PATH)
        org = make_org_catalog([OrganizationDeceptionCapability(mechanism_id="D3-DUC", enabled=True)])
        validate_against_knowledge_catalog(org, kb)  # ne doit pas lever

    def test_orphan_mechanism_id_raises_with_id_listed(self):
        kb = load_deception_catalog(REAL_CATALOG_PATH)
        org = make_org_catalog(
            [
                OrganizationDeceptionCapability(mechanism_id="D3-DUC", enabled=True),
                OrganizationDeceptionCapability(mechanism_id="NOT-A-REAL-MECHANISM", enabled=True),
            ]
        )
        with pytest.raises(OrganizationCatalogError) as excinfo:
            validate_against_knowledge_catalog(org, kb)
        assert "NOT-A-REAL-MECHANISM" in str(excinfo.value)

    def test_multiple_orphans_all_listed_sorted(self):
        kb = load_deception_catalog(REAL_CATALOG_PATH)
        org = make_org_catalog(
            [
                OrganizationDeceptionCapability(mechanism_id="ZZZ-FAKE", enabled=True),
                OrganizationDeceptionCapability(mechanism_id="AAA-FAKE", enabled=True),
            ]
        )
        with pytest.raises(OrganizationCatalogError) as excinfo:
            validate_against_knowledge_catalog(org, kb)
        message = str(excinfo.value)
        assert message.index("AAA-FAKE") < message.index("ZZZ-FAKE")

    def test_empty_organization_catalog_passes(self):
        kb = load_deception_catalog(REAL_CATALOG_PATH)
        validate_against_knowledge_catalog(make_org_catalog(), kb)


class TestCapabilitiesById:
    def test_reduces_to_mapping_by_mechanism_id(self):
        org = make_org_catalog(
            [
                OrganizationDeceptionCapability(mechanism_id="D3-DUC", enabled=True),
                OrganizationDeceptionCapability(mechanism_id="D3-DNR", enabled=False),
            ]
        )
        table = capabilities_by_id(org)
        assert set(table.keys()) == {"D3-DUC", "D3-DNR"}
        assert table["D3-DUC"].enabled is True
        assert table["D3-DNR"].enabled is False

    def test_empty_catalog_yields_empty_table(self):
        assert dict(capabilities_by_id(make_org_catalog())) == {}


class TestEnabledMechanismIds:
    def test_only_enabled_true_included(self):
        org = make_org_catalog(
            [
                OrganizationDeceptionCapability(mechanism_id="D3-DUC", enabled=True),
                OrganizationDeceptionCapability(mechanism_id="D3-DNR", enabled=False),
                OrganizationDeceptionCapability(mechanism_id="D3-DF", enabled=True),
            ]
        )
        assert enabled_mechanism_ids(org) == frozenset({"D3-DUC", "D3-DF"})

    def test_deterministic_frozenset(self):
        org = make_org_catalog([OrganizationDeceptionCapability(mechanism_id="D3-DUC", enabled=True)])
        assert enabled_mechanism_ids(org) == enabled_mechanism_ids(org)


class TestRealOrganizationExampleFile:
    """Réf. tâche §3/§11 : le fichier d'exemple organisationnel réel doit
    référencer une grande partie du catalogue de connaissances (>= 26
    mécanismes) et rester valide vis-à-vis de celui-ci."""

    EXAMPLE_PATH = "examples/data/organization_deception_catalog.json"

    def test_example_file_loads_and_validates(self):
        import pathlib

        if not pathlib.Path(self.EXAMPLE_PATH).exists():
            pytest.skip(f"{self.EXAMPLE_PATH} n'existe pas encore.")
        kb = load_deception_catalog(REAL_CATALOG_PATH)
        org = load_organization_catalog(self.EXAMPLE_PATH)
        validate_against_knowledge_catalog(org, kb)
        assert len(org.capabilities) >= 26

    def test_example_file_has_both_enabled_and_disabled_mechanisms(self):
        import pathlib

        if not pathlib.Path(self.EXAMPLE_PATH).exists():
            pytest.skip(f"{self.EXAMPLE_PATH} n'existe pas encore.")
        org = load_organization_catalog(self.EXAMPLE_PATH)
        enabled = [c for c in org.capabilities if c.enabled]
        disabled = [c for c in org.capabilities if not c.enabled]
        assert enabled
        assert disabled
