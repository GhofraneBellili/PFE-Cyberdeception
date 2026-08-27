"""
Réf. architecture : CLAUDE.md §15 (Coût) — contrat technique du PFE
Cyberdéception.

Tests unitaires de src/cost_engine.py (§25.4 : pytest obligatoire).
"""

import pytest

from src.cost_engine import (
    CostEngineError,
    compute_cost_by_mechanism,
    compute_deployment_cost,
    compute_maintenance_cost,
    compute_mechanism_cost,
    compute_resource_cost,
)


def default_deployment():
    return {"t_setup": 4.0, "w_eng": 50.0, "l_data": 2.0, "w_data": 10.0, "c_integration": 100.0}


def default_resource():
    return {
        "r_cpu": 1.0,
        "c_cpu": 5.0,
        "r_ram": 2.0,
        "c_ram": 2.0,
        "r_disk": 10.0,
        "c_disk": 0.1,
        "r_network": 1.0,
        "c_network": 3.0,
    }


def default_maintenance():
    return {"t_monitoring": 1.0, "w_eng": 50.0, "s_logs": 5.0, "w_storage": 0.2, "c_updates": 20.0}


class TestDeploymentCost:
    def test_formula(self):
        # 4*50 + 2*10 + 100 = 200 + 20 + 100 = 320
        assert compute_deployment_cost(default_deployment()) == pytest.approx(320.0)

    def test_negative_rejected(self):
        params = default_deployment()
        params["t_setup"] = -1.0
        with pytest.raises(CostEngineError):
            compute_deployment_cost(params)


class TestResourceCost:
    def test_formula(self):
        # H=10 * (1*5 + 2*2 + 10*0.1 + 1*3) = 10 * (5+4+1+3) = 10*13 = 130
        assert compute_resource_cost(10.0, default_resource()) == pytest.approx(130.0)

    def test_zero_horizon(self):
        assert compute_resource_cost(0.0, default_resource()) == 0.0

    def test_negative_horizon_rejected(self):
        with pytest.raises(CostEngineError):
            compute_resource_cost(-1.0, default_resource())

    def test_negative_rate_rejected(self):
        params = default_resource()
        params["c_cpu"] = -5.0
        with pytest.raises(CostEngineError):
            compute_resource_cost(10.0, params)


class TestMaintenanceCost:
    def test_formula(self):
        # H=10 * (1*50 + 5*0.2 + 20) = 10 * (50+1+20) = 10*71 = 710
        assert compute_maintenance_cost(10.0, default_maintenance()) == pytest.approx(710.0)

    def test_negative_horizon_rejected(self):
        with pytest.raises(CostEngineError):
            compute_maintenance_cost(-1.0, default_maintenance())


class TestMechanismCost:
    def test_total_is_sum_of_three_components(self):
        result = compute_mechanism_cost(
            horizon=10.0, deployment=default_deployment(), resource=default_resource(), maintenance=default_maintenance()
        )
        assert result["C_deploy"] == pytest.approx(320.0)
        assert result["C_resource"] == pytest.approx(130.0)
        assert result["C_maintenance"] == pytest.approx(710.0)
        assert result["Cost"] == pytest.approx(320.0 + 130.0 + 710.0)

    def test_deterministic(self):
        kwargs = dict(horizon=10.0, deployment=default_deployment(), resource=default_resource(), maintenance=default_maintenance())
        assert compute_mechanism_cost(**kwargs) == compute_mechanism_cost(**kwargs)


class TestCostByMechanism:
    def test_cost_independent_of_location_by_construction(self):
        """Réf. §15 hypothèse gelée : Cost(d,l;H) = Cost(d;H) — ce module
        ne prend jamais 'l' en paramètre, donc ne peut structurellement
        pas faire varier le coût par emplacement."""
        inputs = {
            "D3-DUC": {"deployment": default_deployment(), "resource": default_resource(), "maintenance": default_maintenance()}
        }
        result = compute_cost_by_mechanism(10.0, inputs)
        assert set(result.keys()) == {"D3-DUC"}
        assert result["D3-DUC"]["Cost"] == pytest.approx(320.0 + 130.0 + 710.0)

    def test_multiple_mechanisms(self):
        inputs = {
            "D3-DUC": {"deployment": default_deployment(), "resource": default_resource(), "maintenance": default_maintenance()},
            "D3-DF": {"deployment": default_deployment(), "resource": default_resource(), "maintenance": default_maintenance()},
        }
        result = compute_cost_by_mechanism(5.0, inputs)
        assert set(result.keys()) == {"D3-DUC", "D3-DF"}
        assert result["D3-DUC"]["Cost"] == result["D3-DF"]["Cost"]


class TestGenerality:
    def test_no_network_or_llm_dependency(self):
        from pathlib import Path

        import src.cost_engine as module

        source = Path(module.__file__).read_text(encoding="utf-8").lower()
        for token in ("requests.get", "urllib.request", "openai", "anthropic", "httpx"):
            assert token not in source
