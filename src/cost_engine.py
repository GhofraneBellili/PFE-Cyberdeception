"""
Réf. architecture : "15. Coût" (CLAUDE.md §15, §26 — module `cost_engine.py`).

Cost(d;H) = C_deploy(d) + C_resource(d;H) + C_maintenance(d;H)  (§15)

- C_deploy(d)      = t_setup(d)*w_eng + L_data(d)*w_data + C_integration(d)          (§15.1)
- C_resource(d;H)  = H*[r_CPU*c_CPU + r_RAM*c_RAM + r_disk*c_disk + r_network*c_network]  (§15.2)
- C_maintenance(d;H) = H*[t_monitoring*w_eng + S_logs*w_storage + C_updates]         (§15.3)

Hypothèse de référence gelée (§15, à ne pas étendre sans décision
explicite) : le coût ne dépend pas de l'emplacement — Cost(d,l;H) =
Cost(d;H). L'extension `z_{d,l}` (§15, « extension future non requise »)
n'est PAS implémentée ici.

**Limite documentée, pas une omission silencieuse** : `DeceptionMechanism.
resource_requirements` (`src/schemas.py`) porte des champs texte libre
(`cpu`, `ram`, `disk`, `network`, ex. "2 vCPU" — non structurés, sans
schéma numérique fermé, réf. docstring de `DeceptionResourceRequirements`).
`cost_engine.py` ne tente PAS de parser ce texte libre en valeurs
numériques r_CPU/r_RAM/r_disk/r_network (cela reviendrait à deviner une
interprétation, §25.3). Ce module attend des paramètres numériques déjà
explicites, quelle qu'en soit l'origine (annotation manuelle, futur module
de normalisation non encore décidé — OPEN_DECISION).

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

from typing import TypedDict


class CostEngineError(Exception):
    """Erreur de calcul du coût SP-coût."""


class DeploymentCostParams(TypedDict):
    """Réf. §15.1 : paramètres de C_deploy(d)."""

    t_setup: float
    w_eng: float
    l_data: float
    w_data: float
    c_integration: float


class ResourceCostParams(TypedDict):
    """Réf. §15.2 : paramètres de C_resource(d;H)."""

    r_cpu: float
    c_cpu: float
    r_ram: float
    c_ram: float
    r_disk: float
    c_disk: float
    r_network: float
    c_network: float


class MaintenanceCostParams(TypedDict):
    """Réf. §15.3 : paramètres de C_maintenance(d;H)."""

    t_monitoring: float
    w_eng: float
    s_logs: float
    w_storage: float
    c_updates: float


def _reject_negative(**values: float) -> None:
    for name, value in values.items():
        if value < 0:
            raise CostEngineError(f"'{name}' doit être positif ou nul (valeur reçue : {value}).")


def compute_deployment_cost(params: DeploymentCostParams) -> float:
    """Réf. §15.1 : C_deploy(d) = t_setup*w_eng + L_data*w_data + C_integration."""
    _reject_negative(**params)
    return params["t_setup"] * params["w_eng"] + params["l_data"] * params["w_data"] + params["c_integration"]


def compute_resource_cost(horizon: float, params: ResourceCostParams) -> float:
    """Réf. §15.2 : C_resource(d;H) = H*[r_CPU*c_CPU + r_RAM*c_RAM + r_disk*c_disk + r_network*c_network]."""
    if horizon < 0:
        raise CostEngineError(f"L'horizon H doit être positif ou nul (valeur reçue : {horizon}).")
    _reject_negative(**params)
    return horizon * (
        params["r_cpu"] * params["c_cpu"]
        + params["r_ram"] * params["c_ram"]
        + params["r_disk"] * params["c_disk"]
        + params["r_network"] * params["c_network"]
    )


def compute_maintenance_cost(horizon: float, params: MaintenanceCostParams) -> float:
    """Réf. §15.3 : C_maintenance(d;H) = H*[t_monitoring*w_eng + S_logs*w_storage + C_updates]."""
    if horizon < 0:
        raise CostEngineError(f"L'horizon H doit être positif ou nul (valeur reçue : {horizon}).")
    _reject_negative(**params)
    return horizon * (
        params["t_monitoring"] * params["w_eng"] + params["s_logs"] * params["w_storage"] + params["c_updates"]
    )


def compute_mechanism_cost(
    *,
    horizon: float,
    deployment: DeploymentCostParams,
    resource: ResourceCostParams,
    maintenance: MaintenanceCostParams,
) -> dict[str, float]:
    """Réf. §15 : Cost(d;H) = C_deploy(d) + C_resource(d;H) + C_maintenance(d;H).

    Réf. §15 (hypothèse gelée) : ce résultat s'applique identiquement à
    tout emplacement `l` — Cost(d,l;H) = Cost(d;H), jamais recalculé par
    emplacement dans cette version de référence.
    """
    c_deploy = compute_deployment_cost(deployment)
    c_resource = compute_resource_cost(horizon, resource)
    c_maintenance = compute_maintenance_cost(horizon, maintenance)
    return {
        "C_deploy": c_deploy,
        "C_resource": c_resource,
        "C_maintenance": c_maintenance,
        "Cost": c_deploy + c_resource + c_maintenance,
    }


def compute_cost_by_mechanism(
    horizon: float,
    mechanism_cost_inputs: dict[str, dict],
) -> dict[str, dict[str, float]]:
    """Réf. §15/§16.2 : calcule Cost(d;H) pour chaque mécanisme d'un
    catalogue, à partir d'un dict {mechanism_id: {"deployment":...,
    "resource":..., "maintenance":...}}. Résultat directement réutilisable
    par le futur `optimizer.py` pour la contrainte budgétaire (§16.2),
    puisque le coût ne dépend pas de l'emplacement (§15)."""
    return {
        mechanism_id: compute_mechanism_cost(
            horizon=horizon,
            deployment=inputs["deployment"],
            resource=inputs["resource"],
            maintenance=inputs["maintenance"],
        )
        for mechanism_id, inputs in mechanism_cost_inputs.items()
    }
