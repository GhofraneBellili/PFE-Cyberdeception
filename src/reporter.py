"""
Réf. architecture : "17.6 Reporter" (CLAUDE.md §17.6, §26 — module
`reporter.py`).

Transforme `y*` en `Y*` : produit, pour chaque placement sélectionné par
l'optimiseur (`src/optimizer.py`), un rapport interprétable — occurrence
protégée, mécanisme, emplacement, coût, effet attendu, risque avant,
risque après, variation du risque, preuves/justification associées.

**Ce module n'assemble et ne présente que des valeurs déjà calculées
ailleurs** : il ne recalcule jamais le risque (`risk_engine.py`), le
coût (`cost_engine.py`) ni `DE` (`annotation_validator.py`) — cohérent
avec §17.6 (« transformer y* en Y* et produire un rapport », pas un rôle
de calcul).

**Lecture importante de `risk_before`/`risk_after`** : ces deux valeurs
sont le risque `R_{i,h}` de l'occurrence PROTÉGÉE elle-même (celle où le
placement est déployé), pas le risque terminal en aval. Or `Gamma_{i,h}`
(§14.3) agit sur la transmission de `i,h` vers SES ENFANTS, jamais sur
`R_{i,h}` lui-même (§14.6/§14.7 : `P_{i,h}=A_{i,h} q_{i,h}`, `R_{i,h}=
P_{i,h} I_{i,h}`, ni l'un ni l'autre ne dépend du `DE` DÉPLOYÉ À `i,h`).
**Il est donc normal et attendu qu'une ligne de rapport affiche
`risk_variation=0`** pour une occurrence non terminale : l'effet réel de
la déception se lit sur le risque des occurrences terminales en aval
(disponible séparément, `risks_payload`/`risks.json` produit par
`src/orchestrator.py`), pas sur la ligne de l'occurrence protégée. Ce
module n'attribue PAS la variation d'un risque terminal à un placement
particulier — un problème d'attribution non trivial dès que plusieurs
placements interagissent sur un même chemin — et ne doit jamais être lu
comme prétendant que la déception n'a aucun effet.

**Invariant central du projet (LLM hors du chemin d'exécution)** : ce
module n'importe jamais `src/annotator_llm.py`, `src/rag_indexer.py` ni
`src/rag_retriever.py` — il lit uniquement des structures déjà figées
(plan de déploiement, risques avant/après, table figée pour les preuves).

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.annotation_validator import FrozenAnnotationTable


class ReporterError(Exception):
    """Erreur de construction du rapport de déploiement Y*."""


@dataclass(frozen=True)
class DeploymentReportRow:
    """Réf. §17.6 : une ligne de Y*, entièrement interprétable."""

    occurrence_id: str
    mechanism_id: str
    location_id: str
    cost: float
    de: float
    risk_before: float
    risk_after: float
    risk_variation: float
    risk_variation_relative: float | None
    evidence_ids: tuple[str, ...]


def build_deployment_report(
    deployment_plan: list[dict],
    *,
    risks_before: dict[str, float],
    risks_after: dict[str, float],
    frozen_table: "FrozenAnnotationTable | None" = None,
) -> list[DeploymentReportRow]:
    """Réf. §17.6 : construit une ligne de rapport par placement de `Y*`.

    `risks_before`/`risks_after` (déjà calculés par
    `risk_engine.propagate_risk`, réf. `src/orchestrator.py`) doivent
    couvrir l'occurrence de chaque placement — sinon `ReporterError`
    explicite (§25.3, aucune valeur devinée). `frozen_table` est optionnel
    : s'il est fourni, les `evidence_ids` de la table figée sont joints
    pour la traçabilité (§28).
    """
    rows: list[DeploymentReportRow] = []
    for placement in deployment_plan:
        occurrence_id = placement["occurrence_id"]
        mechanism_id = placement["mechanism_id"]
        location_id = placement["location_id"]

        if occurrence_id not in risks_before:
            raise ReporterError(f"Risque AVANT deception manquant pour l'occurrence '{occurrence_id}'.")
        if occurrence_id not in risks_after:
            raise ReporterError(f"Risque APRES deception manquant pour l'occurrence '{occurrence_id}'.")

        risk_before = risks_before[occurrence_id]
        risk_after = risks_after[occurrence_id]
        variation = risk_after - risk_before
        relative = (variation / risk_before) if risk_before > 0 else None

        evidence_ids: tuple[str, ...] = ()
        if frozen_table is not None:
            entry = frozen_table.get(occurrence_id, mechanism_id, location_id)
            if entry is not None:
                evidence_ids = entry.evidence_ids

        rows.append(
            DeploymentReportRow(
                occurrence_id=occurrence_id,
                mechanism_id=mechanism_id,
                location_id=location_id,
                cost=placement["Cost"],
                de=placement["DE"],
                risk_before=risk_before,
                risk_after=risk_after,
                risk_variation=variation,
                risk_variation_relative=relative,
                evidence_ids=evidence_ids,
            )
        )
    return rows


def render_text_report(rows: list[DeploymentReportRow]) -> str:
    """Réf. §17.6 : rendu texte lisible du rapport de déploiement Y*."""
    if not rows:
        return "Y* est vide : aucun placement selectionne.\n"

    header = f"{'Occurrence':<14}{'Mecanisme':<10}{'Emplacement':<14}{'Cout':<10}{'DE':<8}{'R avant':<10}{'R apres':<10}Variation"
    lines = [header, "-" * len(header)]
    for row in rows:
        relative = f" ({row.risk_variation_relative:+.1%})" if row.risk_variation_relative is not None else ""
        lines.append(
            f"{row.occurrence_id:<14}{row.mechanism_id:<10}{row.location_id:<14}"
            f"{row.cost:<10.2f}{row.de:<8.3f}{row.risk_before:<10.4f}{row.risk_after:<10.4f}"
            f"{row.risk_variation:+.4f}{relative}"
        )
    return "\n".join(lines) + "\n"
