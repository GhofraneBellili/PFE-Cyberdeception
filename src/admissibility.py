"""
Réf. architecture : "10. SP1 — Construction de l'espace admissible"
(CLAUDE.md §10, §26 — module `admissibility.py`).

Construction de D_i, Allowed, RequirementsSatisfied, Relevant, L_{i,h,d}
et C_{i,h} pour une instance de système d'information déjà validée
(`SystemInstance`) et un catalogue de mécanismes de déception déjà chargé
(`DeceptionKnowledgeBase` / `dict[str, DeceptionMechanism]`).

SP1 ne calcule ni P_engagement, ni Effet_prog, ni DE, ni le risque (§10.1) :
il détermine uniquement quels couples (mécanisme, emplacement) sont
ADMISSIBLES pour chaque occurrence d'attaque — pas encore lesquels seront
sélectionnés (cela appartient à l'optimiseur, §10.5).

Portée de cette implémentation initiale (« petite instance », réf. tâche
« profondeur de SP1 ») :

- **M_{i,d}** (mapping technique ATT&CK → déceptions applicables) est reçu
  en paramètre, jamais reconstruit ici depuis D3FEND/Engage/littérature :
  sa construction/validation dépend d'OPEN_DECISION 5 (CLAUDE.md §32,
  README.md), non résolue à ce stade. SP1 consomme un mapping déjà donné.
- **Allowed(d, l)** : `l.location_type ∈ d.admissibility_profile.allowed_location_types`.
- **RequirementsSatisfied(d, l)** : les listes non vides de
  `required_asset_types`/`required_services`/`required_artifacts` du
  profil sont comparées à l'actif associé à `l` (`asset_type` et
  `properties["services"]`/`properties["artifacts"]` — convention
  documentée ci-dessous, `Asset.properties` n'ayant pas de schéma fermé).
- **Relevant(T_{i,h}, d, l)** : simplifiée à une relation topologique
  directe (même actif, ou arête `SITopologyEdge` à un saut entre
  `T_{i,h}.asset_id` et `l.asset_id`) — PAS une analyse complète des
  chemins vers les nœuds terminaux ni des voisins du graphe d'attaque.
  Limite documentée, pas une omission silencieuse (voir
  `docs/chapter4/IMPLEMENTATION_REPORT.md`, section SP1).

OPEN_DECISION 4 (listes vides de `DeceptionAdmissibilityProfile`, non
résolue) : lorsque les listes pertinentes d'un profil sont **toutes
vides**, le résultat du critère correspondant est `"undetermined"` — ni
`pass` ni `fail` — et le candidat est exclu de `C_{i,h}` par défaut
prudent (aucune admission n'est jamais devinée). Ce choix est documenté
explicitement et n'est PAS une résolution de l'OPEN_DECISION : une future
décision explicite pourra le remplacer.

Réf. §6 (nœuds terminaux) : aucune variable de déploiement n'est créée
sur une occurrence Terminal — `C_{i,h} = ∅` par construction pour ces
occurrences, jamais calculé puis filtré après coup.

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

from typing import Literal

from src.graph_builder import is_terminal_node
from src.schemas import Asset, DeceptionMechanism, Location, SystemInstance, TechniqueOccurrence

CheckOutcome = Literal["pass", "fail", "undetermined", "not_evaluated"]


class AdmissibilityError(Exception):
    """Erreur de construction de l'espace admissible SP1."""


def _asset_by_id(instance: SystemInstance) -> dict[str, Asset]:
    return {asset.asset_id: asset for asset in instance.si_inventory.assets}


def _adjacent_asset_ids(instance: SystemInstance, asset_id: str) -> set[str]:
    """Réf. §10.4 Relevant : actifs directement reliés à `asset_id` par une
    arête topologique (à un saut, sens direct ou, si bidirectional, sens
    inverse aussi)."""
    adjacent: set[str] = set()
    for edge in instance.si_inventory.topology_edges:
        if edge.source_asset_id == asset_id:
            adjacent.add(edge.target_asset_id)
        if edge.bidirectional and edge.target_asset_id == asset_id:
            adjacent.add(edge.source_asset_id)
    return adjacent


def evaluate_allowed(mechanism: DeceptionMechanism, location: Location) -> CheckOutcome:
    """Réf. §10.4 « Allowed(d, l) »."""
    allowed_types = mechanism.admissibility_profile.allowed_location_types
    if not allowed_types:
        return "undetermined"
    if location.location_type is None:
        return "fail"
    return "pass" if location.location_type in allowed_types else "fail"


def evaluate_requirements_satisfied(
    mechanism: DeceptionMechanism, location: Location, asset_by_id: dict[str, Asset]
) -> CheckOutcome:
    """Réf. §10.4 « RequirementsSatisfied(d, l) »."""
    profile = mechanism.admissibility_profile
    if not (profile.required_asset_types or profile.required_services or profile.required_artifacts):
        return "undetermined"

    asset = asset_by_id.get(location.asset_id) if location.asset_id else None
    if asset is None:
        return "fail"

    if profile.required_asset_types and asset.asset_type not in profile.required_asset_types:
        return "fail"

    available_services = set(asset.properties.get("services", []) or [])
    if profile.required_services and not set(profile.required_services).issubset(available_services):
        return "fail"

    available_artifacts = set(asset.properties.get("artifacts", []) or [])
    if profile.required_artifacts and not set(profile.required_artifacts).issubset(available_artifacts):
        return "fail"

    return "pass"


def evaluate_relevant(occurrence: TechniqueOccurrence, location: Location, instance: SystemInstance) -> CheckOutcome:
    """Réf. §10.4 « Relevant(T_{i,h}, d, l) », simplifiée à la relation
    topologique directe entre `h` et `l` (voir limites en tête de module)."""
    if location.asset_id is None:
        return "undetermined"
    if location.asset_id == occurrence.asset_id:
        return "pass"
    adjacent = _adjacent_asset_ids(instance, occurrence.asset_id)
    return "pass" if location.asset_id in adjacent else "fail"


def _build_candidate_diagnostic(
    occurrence: TechniqueOccurrence,
    mechanism: DeceptionMechanism,
    location: Location,
    *,
    in_mapping: bool,
    asset_by_id: dict[str, Asset],
    instance: SystemInstance,
) -> dict:
    diagnostic = {
        "occurrence_id": occurrence.occurrence_id,
        "mechanism_id": mechanism.id,
        "location_id": location.location_id,
        "mapping": "pass" if in_mapping else "fail",
    }

    if not in_mapping:
        diagnostic.update(
            {
                "Autorise": "not_evaluated",
                "PrerequisSatisfaits": "not_evaluated",
                "Pertinent": "not_evaluated",
                "admissible": False,
                "rejection_reason": "mapping=faux (mecanisme absent de D_i pour cette technique)",
            }
        )
        return diagnostic

    autorise = evaluate_allowed(mechanism, location)
    prerequis = evaluate_requirements_satisfied(mechanism, location, asset_by_id)
    pertinent = evaluate_relevant(occurrence, location, instance)

    admissible = autorise == "pass" and prerequis == "pass" and pertinent == "pass"
    rejection_reason = None
    if not admissible:
        failing = [
            f"{name}={value}"
            for name, value in (("Autorise", autorise), ("PrerequisSatisfaits", prerequis), ("Pertinent", pertinent))
            if value != "pass"
        ]
        rejection_reason = ", ".join(failing)

    diagnostic.update(
        {
            "Autorise": autorise,
            "PrerequisSatisfaits": prerequis,
            "Pertinent": pertinent,
            "admissible": admissible,
            "rejection_reason": rejection_reason,
        }
    )
    return diagnostic


def build_admissibility_report(
    instance: SystemInstance,
    catalog: dict[str, DeceptionMechanism],
    mapping: dict[str, list[str]],
    *,
    theta_c: float,
    theta_i: float,
    theta_a: float,
) -> dict:
    """Réf. §10.6 (pseudo-algorithme SP1). Construit, pour chaque
    occurrence non terminale du graphe, le diagnostic complet
    Autorise/PrerequisSatisfaits/Pertinent pour tous les couples
    (mécanisme du catalogue, emplacement du SI), puis en dérive `D_i`,
    `L_i_h_d` et `C_i_h`.

    `mapping` représente M_{i,d} : technique_id -> liste d'identifiants de
    mécanismes applicables. Fourni explicitement par l'appelant — jamais
    reconstruit ici (OPEN_DECISION 5, non résolue).

    Réf. §6 : aucune occurrence Terminal ne reçoit de candidats — C_i_h
    reste vide par construction pour ces occurrences.
    """
    asset_by_id = _asset_by_id(instance)
    locations = instance.si_inventory.locations

    occurrences_report: dict[str, dict] = {}
    for occurrence in instance.graph.nodes:
        occurrence_id = occurrence.occurrence_id
        is_terminal = is_terminal_node(occurrence, theta_c, theta_i, theta_a)

        if is_terminal:
            occurrences_report[occurrence_id] = {
                "is_terminal": True,
                "D_i": [],
                "candidates": [],
                "C_i_h": [],
            }
            continue

        d_i = sorted(mapping.get(occurrence.technique_id, []))
        candidates = []
        c_i_h = []
        for mechanism_id, mechanism in sorted(catalog.items()):
            in_mapping = mechanism_id in d_i
            for location in locations:
                diagnostic = _build_candidate_diagnostic(
                    occurrence,
                    mechanism,
                    location,
                    in_mapping=in_mapping,
                    asset_by_id=asset_by_id,
                    instance=instance,
                )
                candidates.append(diagnostic)
                if diagnostic["admissible"]:
                    c_i_h.append({"mechanism_id": mechanism.id, "location_id": location.location_id})

        occurrences_report[occurrence_id] = {
            "is_terminal": False,
            "D_i": d_i,
            "candidates": candidates,
            "C_i_h": c_i_h,
        }

    total_candidates = sum(len(o["candidates"]) for o in occurrences_report.values())
    total_admissible = sum(len(o["C_i_h"]) for o in occurrences_report.values())

    return {
        "schema": "sp1_admissibility_report",
        "schema_version": "1.0",
        "occurrences": occurrences_report,
        "summary": {
            "occurrence_count": len(occurrences_report),
            "terminal_occurrence_count": sum(1 for o in occurrences_report.values() if o["is_terminal"]),
            "candidate_count": total_candidates,
            "admissible_count": total_admissible,
            "rejected_count": total_candidates - total_admissible,
        },
    }
