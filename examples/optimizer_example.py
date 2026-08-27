"""
Réf. architecture : CLAUDE.md §16 (Problème global d'optimisation (P)) —
exemple exécutable réel.

Enchaîne SP1 (src/admissibility.py) -> coût (src/cost_engine.py) ->
optimiseur (src/optimizer.py) sur une petite instance explicite, pour
produire une sortie réellement calculée (pas une fixture de test
présentée comme un résultat).

**DE_{i,h,d,l} est ici une valeur ILLUSTRATIVE fournie directement en
entrée** (SP2 / annotation LLM ne sont pas encore implémentés à ce stade
— voir docs/chapter4/IMPLEMENTATION_REPORT.md, sections 5 à 7) : ce
script ne prétend pas produire un résultat expérimental du chapitre 5, il
démontre uniquement que le solveur (P) fonctionne de bout en bout sur des
entrées réelles de SP1/coût.

Réf. tâche « §8 » : le front de Pareto et le plan Y* final sont réservés
au chapitre 5 — cette sortie sert de preuve d'exécution interne, pas de
capture de chapitre 4.

Exécution :
    python -m examples.optimizer_example

Sortie :
    docs/chapter4/outputs/optimizer_example.txt
"""

from __future__ import annotations

from pathlib import Path

from src.admissibility import build_admissibility_report
from src.cost_engine import compute_cost_by_mechanism
from src.optimizer import solve
from src.risk_engine import compute_aggregated_impact
from src.schemas import (
    Asset,
    AttackGraph,
    AttackGraphEdge,
    DeceptionMechanism,
    Location,
    NodeAttributes,
    OrganizationDeceptionCapability,
    SIInventory,
    SITopologyEdge,
    SystemInstance,
    TechniqueOccurrence,
)

OUT_DIR = Path("docs/chapter4/outputs")
THETA_C, THETA_I, THETA_A = 0.85, 0.85, 0.85


def build_instance() -> SystemInstance:
    """T1078@DC01 (non terminal, 2 candidats admissibles) -> T1003@DC01
    (Terminal via I^C >= theta_C), graphe linéaire."""
    t1078 = TechniqueOccurrence(
        technique_id="T1078",
        asset_id="DC01",
        attributes=NodeAttributes(
            tactics=["initial-access", "persistence"],
            outcomes=[],
            q_local_success=0.75,
            impact_confidentiality=0.6,
            impact_integrity=0.2,
            impact_availability=0.1,
            critical_asset=False,
            accessible_asset=True,
        ),
    )
    t1003 = TechniqueOccurrence(
        technique_id="T1003",
        asset_id="DC01",
        attributes=NodeAttributes(
            tactics=["credential-access"],
            outcomes=[],
            q_local_success=0.65,
            impact_confidentiality=0.9,
            impact_integrity=0.2,
            impact_availability=0.1,
            critical_asset=False,
            accessible_asset=True,
        ),
    )
    graph = AttackGraph(
        nodes=[t1078, t1003],
        edges=[AttackGraphEdge(source_id="T1078@DC01", target_id="T1003@DC01")],
    )

    assets = [
        Asset(
            asset_id="DC01",
            asset_type="domain_controller",
            critical=False,
            accessible=True,
            properties={"services": ["ldap", "kerberos"], "artifacts": []},
        ),
        Asset(asset_id="WS01", asset_type="workstation", critical=False, accessible=True, properties={}),
    ]
    locations = [
        Location(location_id="auth-store", location_type="credential_store", asset_id="DC01"),
        Location(location_id="/tmp", location_type="filesystem", asset_id="WS01"),
    ]
    topology_edges = [
        SITopologyEdge(source_asset_id="DC01", target_asset_id="WS01", relation_type="network_adjacency", bidirectional=True)
    ]
    inventory = SIInventory(assets=assets, locations=locations, topology_edges=topology_edges)
    return SystemInstance(graph=graph, si_inventory=inventory)


def build_catalog() -> dict[str, DeceptionMechanism]:
    """Catalogue de CONNAISSANCES minimal (réf. tâche « separate knowledge
    and organization capabilities »)."""
    duc = DeceptionMechanism(
        id="D3-DUC",
        name="Decoy User Credential",
        description="A Credential created for the purpose of deceiving an adversary.",
        interaction_mechanism="use credential",
        version="1.5.0",
    )
    df = DeceptionMechanism(
        id="D3-DF",
        name="Decoy File",
        description="A file created for the purposes of deceiving an adversary.",
        interaction_mechanism="file access",
        version="1.5.0",
    )
    return {"D3-DUC": duc, "D3-DF": df}


def build_organization_catalog() -> dict[str, OrganizationDeceptionCapability]:
    """Catalogue OPÉRATIONNEL d'une organisation d'exemple."""
    return {
        "D3-DUC": OrganizationDeceptionCapability(
            mechanism_id="D3-DUC",
            enabled=True,
            allowed_location_types=["credential_store"],
            allowed_asset_types=["domain_controller"],
            required_services=["ldap"],
        ),
        "D3-DF": OrganizationDeceptionCapability(
            mechanism_id="D3-DF",
            enabled=True,
            allowed_location_types=["filesystem"],
        ),
    }


def main() -> None:
    instance = build_instance()
    catalog = build_catalog()
    organization_catalog = build_organization_catalog()
    mapping = {"T1078": ["D3-DUC", "D3-DF"]}

    admissibility_report = build_admissibility_report(
        instance, catalog, organization_catalog, mapping, theta_c=THETA_C, theta_i=THETA_I, theta_a=THETA_A
    )

    horizon = 720.0
    cost_inputs = {
        "D3-DUC": {
            "deployment": {"t_setup": 4.0, "w_eng": 50.0, "l_data": 1.0, "w_data": 20.0, "c_integration": 50.0},
            "resource": {"r_cpu": 0.5, "c_cpu": 0.02, "r_ram": 1.0, "c_ram": 0.01, "r_disk": 5.0, "c_disk": 0.001, "r_network": 0.1, "c_network": 0.05},
            "maintenance": {"t_monitoring": 0.1, "w_eng": 50.0, "s_logs": 0.5, "w_storage": 0.01, "c_updates": 0.2},
        },
        "D3-DF": {
            "deployment": {"t_setup": 2.0, "w_eng": 50.0, "l_data": 0.5, "w_data": 20.0, "c_integration": 20.0},
            "resource": {"r_cpu": 0.2, "c_cpu": 0.02, "r_ram": 0.5, "c_ram": 0.01, "r_disk": 20.0, "c_disk": 0.001, "r_network": 0.05, "c_network": 0.05},
            "maintenance": {"t_monitoring": 0.05, "w_eng": 50.0, "s_logs": 1.0, "w_storage": 0.01, "c_updates": 0.1},
        },
    }
    cost_by_mechanism = {
        mechanism_id: values["Cost"] for mechanism_id, values in compute_cost_by_mechanism(horizon, cost_inputs).items()
    }

    # DE illustratif (SP2 non implémenté) — pas une sortie LLM réelle.
    de_by_candidate = {
        ("T1078@DC01", "D3-DUC", "auth-store"): 0.42,
        ("T1078@DC01", "D3-DF", "/tmp"): 0.25,
    }

    q_by_occurrence = {"T1078@DC01": 0.75, "T1003@DC01": 0.65}
    impact_by_occurrence = {
        "T1078@DC01": compute_aggregated_impact(0.6, 0.2, 0.1),
        "T1003@DC01": compute_aggregated_impact(0.9, 0.2, 0.1),
    }
    budget_total = 5000.0

    result = solve(
        instance.graph,
        admissibility_report,
        de_by_candidate=de_by_candidate,
        cost_by_mechanism=cost_by_mechanism,
        budget_total=budget_total,
        q_by_occurrence=q_by_occurrence,
        impact_by_occurrence=impact_by_occurrence,
        theta_c=THETA_C,
        theta_i=THETA_I,
        theta_a=THETA_A,
    )

    lines = [
        "Optimizer - resultats reels (DE illustratif, SP2 non implemente)",
        "-" * 70,
        f"Occurrences Terminal : {result['terminal_ids']}",
        f"Configurations enumerees : {result['configurations_enumerated']}",
        f"Configurations faisables (budget={budget_total}) : {result['configurations_feasible']}",
        "",
        "Front de Pareto (risques terminaux) :",
    ]
    for evaluated in result["pareto_front"]:
        plan = evaluated.configuration.to_deployment_plan()
        plan_desc = ", ".join(f"{p['mechanism_id']}@{p['location_id']}" for p in plan) or "(aucune deception)"
        lines.append(f"  cout={evaluated.total_cost:>9.2f}  risques={evaluated.terminal_risks}  plan=[{plan_desc}]")

    selected = result["selected"]
    selected_plan = selected.configuration.to_deployment_plan()
    lines.append("")
    lines.append("Selection illustrative (somme des risques terminaux, politique explicite) :")
    lines.append(f"  cout={selected.total_cost:.2f}  risques={selected.terminal_risks}")
    lines.append(f"  plan Y* = {selected_plan}")

    text = "\n".join(lines) + "\n"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "optimizer_example.txt").write_text(text, encoding="utf-8")
    print(text)
    print(f"Resume texte : {OUT_DIR / 'optimizer_example.txt'}")


if __name__ == "__main__":
    main()
