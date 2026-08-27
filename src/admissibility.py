"""
Réf. architecture : "10. SP1 — Construction de l'espace admissible"
(CLAUDE.md §10, §26 — module `admissibility.py`) — réf. tâche « separate
knowledge and organization capabilities » (refonte de l'admissibilité
runtime).

Construction de D_i, Allowed, RequirementsSatisfied, Relevant, L_{i,h,d}
et C_{i,h} pour une instance de système d'information déjà validée
(`SystemInstance`), un catalogue de CONNAISSANCES déjà chargé
(`dict[str, DeceptionMechanism]`) et le catalogue OPÉRATIONNEL d'une
organisation (`dict[str, OrganizationDeceptionCapability]`,
réf. `src/organization_catalog.py`).

SP1 ne calcule ni P_engagement, ni Effet_prog, ni DE, ni le risque (§10.1) :
il détermine uniquement quels couples (mécanisme, emplacement) sont
ADMISSIBLES pour chaque occurrence d'attaque — pas encore lesquels seront
sélectionnés (cela appartient à l'optimiseur, §10.5).

**SP1 est un module RUNTIME** (réf. tâche) : il ne pré-calcule jamais
`C_{i,h}` hors ligne. Il reçoit à chaque appel le graphe courant `G`,
l'inventaire/topologie SI courants, le catalogue de connaissances, le
catalogue opérationnel de l'organisation, et `M_{i,d}` — rien de ceci
n'est mis en cache d'un appel à l'autre.

**Séparation connaissance / capacité organisationnelle** (réf. tâche
§1-§2) : une source scientifique (D3FEND/Engage/littérature) décrit CE
QU'EST un mécanisme et dans quels contextes GÉNÉRAUX il peut être
utilisé — elle ne peut jamais décider qu'une organisation PARTICULIÈRE
l'autorise sur un emplacement précis de SON système d'information. Ce
module ne lit donc plus `DeceptionMechanism.admissibility_profile`
(champ hérité, documentaire) pour évaluer Autorise/PrerequisSatisfaits :
ces deux critères viennent exclusivement d'`OrganizationDeceptionCapability`
(`src/schemas.py`) — le profil opérationnel fourni par l'organisation.

- **D_org** (réf. tâche §5) : ensemble des `mechanism_id` activés
  (`enabled=True`) par l'organisation.
- **D_i** (réf. tâche §5) : `D_i = {d ∈ D_org | M_{i,d}(T_i, d) = 1}` —
  le mapping réduit D'ABORD le catalogue organisationnel selon la
  technique ; SP1 poursuit ensuite la réduction selon le contexte de
  l'occurrence et du SI (Autorise/PrerequisSatisfaits/Pertinent).
- **Autorise(d, l)** (réf. tâche §7) : `d` est activé et référencé par
  l'organisation (vérifié en amont, tier `organization` du diagnostic) ;
  `l` n'est pas explicitement interdit (`forbidden_locations`) ;
  `l.location_type ∈ capability.allowed_location_types`.
- **PrerequisSatisfaits(d, l)** (réf. tâche §8) : compare les exigences
  opérationnelles du mécanisme (`allowed_asset_types`/`forbidden_asset_types`/
  `required_services`/`required_artifacts`, tous fournis par
  l'organisation) aux propriétés réelles de l'actif associé à `l` dans
  l'inventaire SI (`asset_type`, `properties["services"]`/`properties["artifacts"]`).
  Règle générique — aucun `mechanism_id`/`asset_id`/`location_id` codé en
  dur (réf. tâche §12).
- **Relevant(T_{i,h}, d, l)** : inchangé — relation topologique directe
  (même actif, ou arête `SITopologyEdge` à un saut entre
  `T_{i,h}.asset_id` et `l.asset_id`). Choix opérationnel simple,
  documenté comme tel (réf. tâche §9) — PAS une analyse complète des
  chemins vers les nœuds terminaux, et ne calcule JAMAIS
  Realisme/InteractionLikelihood/P_engagement/Effet_prog/DE (rôle
  réservé à SP2).

**Distinction « configuration organisationnelle manquante » vs « prérequis
inconnu au sens scientifique »** (réf. tâche §10) : lorsque
`PrerequisSatisfaits`/`Autorise` restent `"undetermined"`, la cause
identifiée est TOUJOURS une configuration organisationnelle insuffisante
(l'organisation n'a pas renseigné `allowed_location_types`/
`allowed_asset_types`/`required_services`/`required_artifacts` pour un
mécanisme qu'elle a pourtant activé) — jamais une absence de preuve
scientifique D3FEND, puisque ce module ne consulte plus D3FEND du tout
pour ces critères. `rejection_reason` le précise explicitement
(`"undetermined (missing organization configuration)"`).

Réf. §6 (nœuds terminaux) : aucune variable de déploiement n'est créée
sur une occurrence Terminal — `C_{i,h} = ∅` par construction pour ces
occurrences, jamais calculé puis filtré après coup.

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

from typing import Literal

from src.graph_builder import is_terminal_node
from src.schemas import Asset, DeceptionMechanism, Location, OrganizationDeceptionCapability, SystemInstance, TechniqueOccurrence

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


def enabled_mechanism_ids(organization_catalog: dict[str, OrganizationDeceptionCapability]) -> frozenset[str]:
    """Réf. tâche §5 : D_org — ensemble des `mechanism_id` activés
    (`enabled=True`) par l'organisation. Fonction pure, aucune dépendance
    au catalogue de connaissances ni au graphe courant."""
    return frozenset(
        mechanism_id for mechanism_id, capability in organization_catalog.items() if capability.enabled
    )


def evaluate_allowed(capability: OrganizationDeceptionCapability | None, location: Location) -> CheckOutcome:
    """Réf. tâche §7 « Redéfinir proprement Autorise ». Suppose que `d` est
    déjà connu comme activé et référencé par l'organisation (vérifié en
    amont par le tier `organization` du diagnostic, réf.
    `_organization_status`) — ce critère se concentre donc sur la
    politique d'emplacement : `l` n'est pas explicitement interdit, et son
    `location_type` figure dans `allowed_location_types`.

    `capability=None` ne devrait normalement pas atteindre cette fonction
    (le tier `organization` filtre déjà ce cas) — retourne `"fail"` par
    prudence si cela arrive quand même (jamais un `pass` implicite)."""
    if capability is None:
        return "fail"
    if location.location_id in capability.forbidden_locations:
        return "fail"
    if not capability.allowed_location_types:
        return "undetermined"
    if location.location_type is None:
        return "fail"
    return "pass" if location.location_type in capability.allowed_location_types else "fail"


def evaluate_requirements_satisfied(
    capability: OrganizationDeceptionCapability | None, location: Location, asset_by_id: dict[str, Asset]
) -> CheckOutcome:
    """Réf. tâche §8 « Redéfinir proprement PrerequisSatisfaits ». Compare
    les exigences opérationnelles déclarées par l'organisation
    (`allowed_asset_types`/`forbidden_asset_types`/`required_services`/
    `required_artifacts`) aux propriétés réelles de l'actif associé à `l`
    dans l'inventaire SI — règle générique, aucun identifiant codé en dur
    (réf. tâche §12)."""
    if capability is None:
        return "fail"

    asset = asset_by_id.get(location.asset_id) if location.asset_id else None

    if capability.forbidden_asset_types and asset is not None and asset.asset_type in capability.forbidden_asset_types:
        return "fail"

    if not (capability.allowed_asset_types or capability.required_services or capability.required_artifacts):
        return "undetermined"

    if asset is None:
        return "fail"

    if capability.allowed_asset_types and asset.asset_type not in capability.allowed_asset_types:
        return "fail"

    available_services = set(asset.properties.get("services", []) or [])
    if capability.required_services and not set(capability.required_services).issubset(available_services):
        return "fail"

    available_artifacts = set(asset.properties.get("artifacts", []) or [])
    if capability.required_artifacts and not set(capability.required_artifacts).issubset(available_artifacts):
        return "fail"

    return "pass"


def evaluate_relevant(occurrence: TechniqueOccurrence, location: Location, instance: SystemInstance) -> CheckOutcome:
    """Réf. §10.4 « Relevant(T_{i,h}, d, l) » — réf. tâche §9 : choix
    opérationnel simple documenté comme tel (relation topologique directe
    entre `h` et `l`), jamais une analyse complète des chemins vers les
    nœuds terminaux ni un calcul de grandeurs réservées à SP2
    (Realisme/InteractionLikelihood/P_engagement/Effet_prog/DE)."""
    if location.asset_id is None:
        return "undetermined"
    if location.asset_id == occurrence.asset_id:
        return "pass"
    adjacent = _adjacent_asset_ids(instance, occurrence.asset_id)
    return "pass" if location.asset_id in adjacent else "fail"


def _organization_status(mechanism_id: str, organization_catalog: dict[str, OrganizationDeceptionCapability]) -> tuple[bool, str | None]:
    """Réf. tâche §5/§6 : un mécanisme n'est utilisable par SP1 que s'il
    est référencé ET activé par l'organisation — distingue explicitement
    les deux causes de rejet (réf. tâche §15, critères A/B)."""
    capability = organization_catalog.get(mechanism_id)
    if capability is None:
        return False, "mecanisme absent du catalogue operationnel de l'organisation"
    if not capability.enabled:
        return False, "mecanisme desactive par l'organisation (enabled=false)"
    return True, None


def _build_candidate_diagnostic(
    occurrence: TechniqueOccurrence,
    mechanism: DeceptionMechanism,
    capability: OrganizationDeceptionCapability | None,
    location: Location,
    *,
    in_mapping: bool,
    org_enabled: bool,
    org_reason: str | None,
    asset_by_id: dict[str, Asset],
    instance: SystemInstance,
) -> dict:
    diagnostic = {
        "occurrence_id": occurrence.occurrence_id,
        "mechanism_id": mechanism.id,
        "location_id": location.location_id,
        "mapping": "pass" if in_mapping else "fail",
        "organization": "pass" if org_enabled else "fail",
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

    if not org_enabled:
        diagnostic.update(
            {
                "Autorise": "not_evaluated",
                "PrerequisSatisfaits": "not_evaluated",
                "Pertinent": "not_evaluated",
                "admissible": False,
                "rejection_reason": f"organization=faux ({org_reason})",
            }
        )
        return diagnostic

    autorise = evaluate_allowed(capability, location)
    prerequis = evaluate_requirements_satisfied(capability, location, asset_by_id)
    pertinent = evaluate_relevant(occurrence, location, instance)

    admissible = autorise == "pass" and prerequis == "pass" and pertinent == "pass"
    rejection_reason = None
    if not admissible:
        failing = []
        for name, value in (("Autorise", autorise), ("PrerequisSatisfaits", prerequis), ("Pertinent", pertinent)):
            if value == "undetermined":
                failing.append(f"{name}=undetermined (missing organization configuration)")
            elif value != "pass":
                failing.append(f"{name}={value}")
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
    organization_catalog: dict[str, OrganizationDeceptionCapability],
    mapping: dict[str, list[str]],
    *,
    theta_c: float,
    theta_i: float,
    theta_a: float,
) -> dict:
    """Réf. §10.6 (pseudo-algorithme SP1) — réf. tâche « SP1 is a RUNTIME
    module ». Construit, pour chaque occurrence non terminale du graphe
    COURANT, le diagnostic complet mapping/organization/Autorise/
    PrerequisSatisfaits/Pertinent pour tous les couples (mécanisme du
    catalogue de connaissances, emplacement du SI courant), puis en
    dérive `D_i`, `L_i_h_d` et `C_i_h`.

    `catalog` : catalogue de CONNAISSANCES (§2 de la tâche) — décrit CE
    QUE SONT les mécanismes, jamais consulté ici pour Autorise/
    PrerequisSatisfaits.
    `organization_catalog` : catalogue OPÉRATIONNEL de l'organisation
    (§3 de la tâche, réf. `src/organization_catalog.py::capabilities_by_id`)
    — seule source des décisions Autorise/PrerequisSatisfaits.
    `mapping` représente M_{i,d} : technique_id -> liste d'identifiants de
    mécanismes applicables (réf. connaissance, fourni explicitement par
    l'appelant, jamais reconstruit ici).

    `D_i` reporté = `{d ∈ D_org | M_{i,d}(technique_id, d) = 1}` (réf.
    tâche §5) — pas la liste brute de `mapping`, qui n'est qu'une étape
    intermédiaire.

    Réf. §6 : aucune occurrence Terminal ne reçoit de candidats — C_i_h
    reste vide par construction pour ces occurrences.

    Aucun `mechanism_id`/`asset_id`/`location_id` n'est codé en dur dans
    cette fonction (réf. tâche §12) : le comportement est entièrement
    déterminé par les données passées en paramètre.
    """
    asset_by_id = _asset_by_id(instance)
    locations = instance.si_inventory.locations
    d_org = enabled_mechanism_ids(organization_catalog)

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

        mapped_mechanism_ids = set(mapping.get(occurrence.technique_id, []))
        d_i = sorted(mapped_mechanism_ids & d_org)
        candidates = []
        c_i_h = []
        for mechanism_id, mechanism in sorted(catalog.items()):
            in_mapping = mechanism_id in mapped_mechanism_ids
            capability = organization_catalog.get(mechanism_id)
            org_enabled, org_reason = _organization_status(mechanism_id, organization_catalog)
            for location in locations:
                diagnostic = _build_candidate_diagnostic(
                    occurrence,
                    mechanism,
                    capability,
                    location,
                    in_mapping=in_mapping,
                    org_enabled=org_enabled,
                    org_reason=org_reason,
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
        "schema_version": "2.0",
        "occurrences": occurrences_report,
        "summary": {
            "d_org_size": len(d_org),
            "occurrence_count": len(occurrences_report),
            "terminal_occurrence_count": sum(1 for o in occurrences_report.values() if o["is_terminal"]),
            "candidate_count": total_candidates,
            "admissible_count": total_admissible,
            "rejected_count": total_candidates - total_admissible,
        },
    }
