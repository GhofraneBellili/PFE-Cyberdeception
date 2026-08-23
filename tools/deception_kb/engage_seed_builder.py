"""
Réf. architecture : "9. Base de connaissances cyberdéception" / "9.1
Pipeline de construction de la KB déception" — contrat technique du PFE
Cyberdéception (CLAUDE.md).

Couche OFFLINE de construction de données (phase 4B.2) : transforme les
fichiers officiels MITRE Engage v1.0 (activités, approches, mappings
ATT&CK) en un STAGING documentaire fidèle à Engage — DEUXIÈME source
structurée de la future KB cyberdéception, en complément de D3FEND
(tools/deception_kb/d3fend_seed_builder.py).

Ce module NE fait PAS partie du runtime SP1/SP2/SP3 : il ne construit PAS
le catalogue final data/deception/deception_catalog.json, ne calcule ni
D_i, ni C_{i,h}, ni Allowed, ni RequirementsSatisfied, ni Relevant,
n'effectue aucun RAG ni appel LLM, et ne produit aucun M_{i,d}. Une
activité Engage (EACxxxx/SACxxxx) est une entité documentaire source, PAS
un mécanisme final `d` du catalogue D — la sélection/normalisation future
décidera comment elle y contribue (OPEN_DECISION 1/2/3).

Format réellement observé dans MITRE Engage v1.0, commit
5ae09f6f7511ebb6d35d70a9107490900380d3d8 (voir tools/deception_kb/README.md
pour le détail complet de l'inspection) :

- `activities.json` : liste plate de {id, name, description, long_description}
  — id préfixé EAC (Engagement Activity) ou SAC (Strategic Activity) ;
  constaté par inspection directe : `activity_details[id]["type"]` vaut
  respectivement "Engagement" ou "Strategic" (jamais "Support") — la
  famille SAC est donc documentée comme "Strategic Activity", jamais comme
  "Support Activity" ;
- `activity_details.json` : dict indexé par id d'activité, portant
  notamment type, goals, vulnerabilities (liste de {id, eav}),
  attack_techniques (liste de {id, name, attack_tactics: [libellés
  kebab-case, ex. "discovery"]}), attack_tactics (liste de {id, name} de
  tactiques TAxxxx — distinct des libellés kebab-case ci-dessus),
  approaches (ids), references (liste de {id, title, url}) ;
- `approaches.json` / `approach_details.json` /
  `approach_activity_mappings.json` : même schéma relationnel qu'activités,
  avec id préfixé EAP (Engagement Approach) ou SAP (Strategic Approach) ;
  constaté de même sur `approach_details[id]["type"]` ("Engagement" ou
  "Strategic") ;
- `attack_mapping.json` : liste plate de relations {attack_id,
  attack_technique, eav_id, eav, eac_id, eac} — tous les attack_id
  observés respectent Txxxx/Txxxx.xxx (aucune anomalie de framework
  constatée, contrairement à D3FEND/SPARTA) ;
- `references.json` : liste plate {id, title, url, activity_id} — le champ
  "activity_id" référence en réalité soit une activité, soit une approche
  (constaté : 4 références sur 67 pointent vers SAP0001/SAP0002).

Convention : identifiants de code en anglais, commentaires et docstrings en
français (§25.1).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.schemas import ATTACK_TECHNIQUE_ID_PATTERN
from tools.deception_kb.d3fend_seed_builder import (
    build_manifest_entry,
    build_source_manifest,
    read_json_with_sha256,
)

# ---------------------------------------------------------------------------
# Constantes de format — réf. inspection réelle d'Engage v1.0
# ---------------------------------------------------------------------------

# Réf. tâche §1 : dépôt officiel explicitement mandaté ; aucun mirroir tiers.
_ENGAGE_OFFICIAL_REPO = "mitre/engage"
_ENGAGE_DATA_PATH_PREFIX = "Data/json"

# Réf. tâche §9 : convention de préfixe démontrée par inspection réelle sur
# deux familles d'entités (activités ET approches) — jamais inventée.
_ACTIVITY_FAMILY_PREFIXES = ("EAC", "SAC")
_APPROACH_FAMILY_PREFIXES = ("EAP", "SAP")

_ATTACK_ID_RE = re.compile(ATTACK_TECHNIQUE_ID_PATTERN)


class EngageSeedBuilderError(Exception):
    """Erreur de construction ou de validation du staging MITRE Engage."""


def _engage_official_url(source_revision: str, filename: str) -> str:
    """Réf. tâche §1/§19 : URL officielle dérivée mécaniquement du dépôt
    MITRE Engage mandaté et de source_revision (toujours fourni
    explicitement, jamais 'main'/'latest') — jamais une URL inventée."""
    return (
        f"https://raw.githubusercontent.com/{_ENGAGE_OFFICIAL_REPO}/"
        f"{source_revision}/{_ENGAGE_DATA_PATH_PREFIX}/{filename}"
    )


def _family_from_prefix(entity_id: str, known_prefixes: tuple[str, ...], entity_kind: str) -> str:
    """Réf. tâche §9 : dérive la famille d'une entité Engage depuis son
    préfixe d'identifiant réellement observé, sans jamais l'inventer. Un
    préfixe non reconnu lève une erreur explicite plutôt que d'être deviné."""
    for prefix in known_prefixes:
        if entity_id.startswith(prefix):
            return prefix
    raise EngageSeedBuilderError(
        f"Préfixe d'identifiant {entity_kind} non reconnu (attendu parmi "
        f"{known_prefixes}) : '{entity_id}'."
    )


def _field_evidence(source_file: str, source_sha256: str, entity_id: str, source_property: str, value: str) -> dict:
    """Réf. tâche §15 : structure légère de provenance au niveau du champ —
    evidence_text est recopié verbatim depuis la source, jamais reformulé."""
    return {
        "source_file": source_file,
        "source_sha256": source_sha256,
        "source_entity": entity_id,
        "source_property": source_property,
        "evidence_text": value,
    }


def _build_field_evidence_entries(entity_id: str, fields: list[tuple[str, Any, str, str]]) -> list[dict]:
    """fields : liste de (source_property, valeur, source_file, source_sha256).
    N'émet une entrée que pour les valeurs textuelles réellement présentes."""
    return [
        _field_evidence(source_file, source_sha256, entity_id, prop, value)
        for prop, value, source_file, source_sha256 in fields
        if isinstance(value, str)
    ]


# ---------------------------------------------------------------------------
# Extraction des activités et approches (réf. tâche §8/§9/§10)
# ---------------------------------------------------------------------------


def _index_by_id(items: list[dict], id_key: str = "id") -> dict[str, dict]:
    return {item[id_key]: item for item in items if isinstance(item, dict) and id_key in item}


def _extract_attack_techniques(details: dict) -> list[dict]:
    """Réf. tâche §14 : ne conserve que les attack_id conformes à
    Txxxx/Txxxx.xxx (réutilise ATTACK_TECHNIQUE_ID_PATTERN de schemas.py,
    aucune duplication du motif) ; un identifiant hors périmètre serait
    filtré et non propagé comme ATT&CK Enterprise valide (aucun cas réel
    constaté dans Engage v1.0). attack_tactics ici est la liste de libellés
    kebab-case propre à CHAQUE technique (ex. "discovery"), distincte du
    champ attack_tactics de l'activité (objets {id, name} de tactiques
    TAxxxx)."""
    techniques = []
    for item in details.get("attack_techniques", []) or []:
        if not isinstance(item, dict):
            continue
        attack_id = item.get("id")
        if not isinstance(attack_id, str) or not _ATTACK_ID_RE.match(attack_id):
            continue
        techniques.append(
            {
                "attack_id": attack_id,
                "attack_technique_name": item.get("name"),
                "attack_tactic_labels": [
                    label for label in item.get("attack_tactics", []) or [] if isinstance(label, str)
                ],
            }
        )
    return techniques


def _build_activity_evidence(
    raw_activity: dict, details: dict, activity_id: str, activities_sha256: str, details_sha256: str
) -> list[dict]:
    return _build_field_evidence_entries(
        activity_id,
        [
            ("name", raw_activity.get("name"), "activities.json", activities_sha256),
            ("description", raw_activity.get("description"), "activities.json", activities_sha256),
            (
                "long_description",
                raw_activity.get("long_description"),
                "activities.json",
                activities_sha256,
            ),
            ("type", details.get("type"), "activity_details.json", details_sha256),
        ],
    )


def _build_approach_evidence(
    raw_approach: dict, details: dict, approach_id: str, approaches_sha256: str, approach_details_sha256: str
) -> list[dict]:
    return _build_field_evidence_entries(
        approach_id,
        [
            ("name", raw_approach.get("name"), "approaches.json", approaches_sha256),
            ("description", raw_approach.get("description"), "approaches.json", approaches_sha256),
            (
                "long_description",
                raw_approach.get("long_description"),
                "approaches.json",
                approaches_sha256,
            ),
            ("type", details.get("type"), "approach_details.json", approach_details_sha256),
        ],
    )


def build_engage_activity_seed(
    *,
    activities_path: str | Path,
    activity_details_path: str | Path,
    approaches_path: str | Path,
    approach_details_path: str | Path,
    approach_activity_mappings_path: str | Path,
    references_path: str | Path,
    engage_version: str,
    source_revision: str,
) -> dict:
    """Réf. architecture : "9.1 Pipeline de construction de la KB
    déception" — construit le staging documentaire des activités et
    approches MITRE Engage (chemins fournis explicitement, jamais codés en
    dur).

    Conserve la sémantique native d'Engage : EAC/SAC et EAP/SAP restent
    distincts (activity_family/approach_family, réf. tâche §9), aucune
    activité n'est présentée comme un mécanisme final `d` du catalogue D
    (OPEN_DECISION 1/2, non résolues ici).
    """
    raw_activities, activities_sha256 = read_json_with_sha256(activities_path)
    raw_details, details_sha256 = read_json_with_sha256(activity_details_path)
    raw_approaches, approaches_sha256 = read_json_with_sha256(approaches_path)
    raw_approach_details, approach_details_sha256 = read_json_with_sha256(approach_details_path)
    raw_aam, aam_sha256 = read_json_with_sha256(approach_activity_mappings_path)
    raw_references, references_sha256 = read_json_with_sha256(references_path)

    if not isinstance(raw_activities, list):
        raise EngageSeedBuilderError("activities.json doit être une liste.")
    if not isinstance(raw_details, dict):
        raise EngageSeedBuilderError("activity_details.json doit être un objet indexé par identifiant.")
    if not isinstance(raw_approaches, list):
        raise EngageSeedBuilderError("approaches.json doit être une liste.")
    if not isinstance(raw_approach_details, dict):
        raise EngageSeedBuilderError("approach_details.json doit être un objet indexé par identifiant.")
    if not isinstance(raw_aam, list):
        raise EngageSeedBuilderError("approach_activity_mappings.json doit être une liste.")
    if not isinstance(raw_references, list):
        raise EngageSeedBuilderError("references.json doit être une liste.")

    approaches_by_id = _index_by_id(raw_approaches)

    # Réf. tâche §8/§10 : jointure canonique activité <-> approche à partir
    # de la table de correspondance officielle (pas de la copie dénormalisée
    # embarquée dans activity_details.json/approach_details.json).
    activity_to_approach_ids: dict[str, list[str]] = {}
    approach_to_activity_ids: dict[str, list[str]] = {}
    for entry in raw_aam:
        if not isinstance(entry, dict):
            continue
        approach_id = entry.get("approach_id")
        activity_id = entry.get("activity_id")
        if not isinstance(approach_id, str) or not isinstance(activity_id, str):
            continue
        activity_to_approach_ids.setdefault(activity_id, []).append(approach_id)
        approach_to_activity_ids.setdefault(approach_id, []).append(activity_id)

    activities_seed = []
    for raw_activity in raw_activities:
        activity_id = raw_activity.get("id") if isinstance(raw_activity, dict) else None
        if not isinstance(activity_id, str):
            raise EngageSeedBuilderError("Une entrée d'activities.json est dépourvue d'identifiant valide.")

        details = raw_details.get(activity_id, {})
        approach_ids = activity_to_approach_ids.get(activity_id, [])

        activities_seed.append(
            {
                "activity_id": activity_id,
                "activity_family": _family_from_prefix(
                    activity_id, _ACTIVITY_FAMILY_PREFIXES, "d'activité"
                ),
                "name": raw_activity.get("name"),
                "description": raw_activity.get("description"),
                "long_description": raw_activity.get("long_description"),
                "detail_type": details.get("type"),
                "goal_ids": [g for g in details.get("goals", []) or [] if isinstance(g, str)],
                "vulnerabilities": [
                    {"vulnerability_id": v.get("id"), "vulnerability_text": v.get("eav")}
                    for v in details.get("vulnerabilities", []) or []
                    if isinstance(v, dict)
                ],
                "attack_techniques": _extract_attack_techniques(details),
                "attack_tactics": [
                    {"attack_tactic_id": t.get("id"), "attack_tactic_name": t.get("name")}
                    for t in details.get("attack_tactics", []) or []
                    if isinstance(t, dict)
                ],
                "approach_ids": approach_ids,
                "approach_names": [
                    approaches_by_id[aid]["name"]
                    for aid in approach_ids
                    if aid in approaches_by_id and isinstance(approaches_by_id[aid].get("name"), str)
                ],
                "references": [
                    {"reference_id": r.get("id"), "title": r.get("title"), "url": r.get("url")}
                    for r in details.get("references", []) or []
                    if isinstance(r, dict)
                ],
                "source_evidence": _build_activity_evidence(
                    raw_activity, details, activity_id, activities_sha256, details_sha256
                ),
            }
        )

    approaches_seed = []
    for raw_approach in raw_approaches:
        approach_id = raw_approach.get("id") if isinstance(raw_approach, dict) else None
        if not isinstance(approach_id, str):
            raise EngageSeedBuilderError("Une entrée d'approaches.json est dépourvue d'identifiant valide.")

        approach_details = raw_approach_details.get(approach_id, {})
        # Réf. constat d'inspection (docstring de module) : le champ
        # "activity_id" de references.json référence parfois en réalité un
        # approach_id (SAP0001/SAP0002) — motif observé, pas une hypothèse.
        approach_references = [
            {"reference_id": r.get("id"), "title": r.get("title"), "url": r.get("url")}
            for r in raw_references
            if isinstance(r, dict) and r.get("activity_id") == approach_id
        ]

        approaches_seed.append(
            {
                "approach_id": approach_id,
                "approach_family": _family_from_prefix(
                    approach_id, _APPROACH_FAMILY_PREFIXES, "d'approche"
                ),
                "name": raw_approach.get("name"),
                "description": raw_approach.get("description"),
                "long_description": raw_approach.get("long_description"),
                "activity_ids": approach_to_activity_ids.get(approach_id, []),
                "references": approach_references,
                "source_evidence": _build_approach_evidence(
                    raw_approach, approach_details, approach_id, approaches_sha256, approach_details_sha256
                ),
            }
        )

    return {
        "schema": "engage_activity_seed",
        "schema_version": "1.0",
        "engage_version": engage_version,
        "source_revision": source_revision,
        "source_files": {
            "activities": {"file": "activities.json", "sha256": activities_sha256},
            "activity_details": {"file": "activity_details.json", "sha256": details_sha256},
            "approaches": {"file": "approaches.json", "sha256": approaches_sha256},
            "approach_details": {"file": "approach_details.json", "sha256": approach_details_sha256},
            "approach_activity_mappings": {
                "file": "approach_activity_mappings.json",
                "sha256": aam_sha256,
            },
            "references": {"file": "references.json", "sha256": references_sha256},
        },
        "activities": activities_seed,
        "approaches": approaches_seed,
    }


# ---------------------------------------------------------------------------
# Mappings Engage -> ATT&CK, déduplication (réf. tâche §11/§13)
# ---------------------------------------------------------------------------


def _engage_mapping_dedup_key(mapping: dict) -> tuple:
    """Réf. tâche §13 : clé de déduplication (attack_id,
    adversary_vulnerability_id, engage_activity_id) — confirmée SUFFISANTE
    par inspection réelle d'attack_mapping.json (le seul doublon exact
    constaté, T1040/EAV0007/EAC0023, partage aussi le contenu complet de la
    relation ; aucune paire distincte ne partage ce triplet avec un contenu
    différent)."""
    return (
        mapping.get("attack_id"),
        mapping.get("adversary_vulnerability_id"),
        mapping.get("engage_activity_id"),
    )


def _deduplicate_engage_mappings(mappings: list[dict]) -> list[dict]:
    """Réf. tâche §13 : supprime les doublons EXACTS, conserve la première
    occurrence et l'ordre déterministe du fichier source."""
    seen: set[tuple] = set()
    deduplicated: list[dict] = []
    for mapping in mappings:
        key = _engage_mapping_dedup_key(mapping)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(mapping)
    return deduplicated


def build_engage_attack_mapping_seed(
    attack_mapping_path: str | Path,
    activity_seed: dict,
    *,
    engage_version: str,
    source_revision: str,
    source_file_label: str = "attack_mapping.json",
) -> dict:
    """Réf. architecture : "9.1 Pipeline de construction de la KB
    déception" — extrait les relations ATT&CK <-> Engage documentées dans
    attack_mapping.json.

    Réf. tâche §12 (CRITIQUE) : une relation (attack_id, EAV, EAC) n'est
    PAS M_{i,d} — EAC n'est pas nécessairement un mécanisme final `d`, et le
    futur mécanisme peut agréger D3FEND + Engage + littérature. Ces
    relations restent du STAGING ("origin": "mitre_engage_v1.0").

    Réf. tâche §13 : trois métriques distinguent bindings bruts, relations
    uniques (après déduplication exacte) et couples (attack_id,
    engage_activity_id) uniques — même principe que le durcissement D3FEND.
    """
    raw_mappings, source_sha256 = read_json_with_sha256(attack_mapping_path)

    if not isinstance(raw_mappings, list):
        raise EngageSeedBuilderError("attack_mapping.json doit être une liste.")

    filtered_mappings = []
    for entry in raw_mappings:
        if not isinstance(entry, dict):
            continue
        attack_id = entry.get("attack_id")
        eac_id = entry.get("eac_id")
        if not isinstance(attack_id, str) or not _ATTACK_ID_RE.match(attack_id):
            # Réf. tâche §14 : hors périmètre Txxxx/Txxxx.xxx, filtré —
            # jamais propagé silencieusement comme ATT&CK Enterprise valide
            # (aucun cas réel constaté dans Engage v1.0).
            continue

        filtered_mappings.append(
            {
                "attack_id": attack_id,
                "attack_technique_name": entry.get("attack_technique"),
                "adversary_vulnerability_id": entry.get("eav_id"),
                "adversary_vulnerability_text": entry.get("eav"),
                "engage_activity_id": eac_id,
                "engage_activity_name": entry.get("eac"),
                "source_file": source_file_label,
                "source_sha256": source_sha256,
                "source_revision": source_revision,
                "origin": "mitre_engage_v1.0",
            }
        )

    raw_mapping_count = len(filtered_mappings)
    deduplicated_mappings = _deduplicate_engage_mappings(filtered_mappings)
    unique_pairs = {
        (m["attack_id"], m["engage_activity_id"]) for m in deduplicated_mappings
    }

    return {
        "schema": "engage_attack_mapping_seed",
        "schema_version": "1.0",
        "engage_version": engage_version,
        "source_revision": source_revision,
        "source_file": source_file_label,
        "source_sha256": source_sha256,
        "raw_mapping_count": raw_mapping_count,
        "unique_mapping_count": len(deduplicated_mappings),
        "unique_attack_activity_pair_count": len(unique_pairs),
        "mappings": deduplicated_mappings,
    }


# ---------------------------------------------------------------------------
# Validation déterministe du staging (réf. tâche §20)
# ---------------------------------------------------------------------------


def validate_engage_activity_seed(activity_seed: dict) -> None:
    """Réf. tâche §20 : intégrité minimale du staging activités/approches —
    aucun doublon d'identifiant, aucune référence croisée orpheline,
    provenance obligatoire."""
    seen_activity_ids: set[str] = set()
    for activity in activity_seed["activities"]:
        activity_id = activity.get("activity_id")
        if not activity_id:
            raise EngageSeedBuilderError("Une activité du seed est dépourvue d'activity_id.")
        if activity_id in seen_activity_ids:
            raise EngageSeedBuilderError(f"activity_id dupliqué : '{activity_id}'.")
        seen_activity_ids.add(activity_id)
        if not activity.get("source_evidence"):
            raise EngageSeedBuilderError(f"Activité '{activity_id}' sans provenance associée.")

    seen_approach_ids: set[str] = set()
    for approach in activity_seed["approaches"]:
        approach_id = approach.get("approach_id")
        if not approach_id:
            raise EngageSeedBuilderError("Une approche du seed est dépourvue d'approach_id.")
        if approach_id in seen_approach_ids:
            raise EngageSeedBuilderError(f"approach_id dupliqué : '{approach_id}'.")
        seen_approach_ids.add(approach_id)
        if not approach.get("source_evidence"):
            raise EngageSeedBuilderError(f"Approche '{approach_id}' sans provenance associée.")
        for activity_id in approach.get("activity_ids", []):
            if activity_id not in seen_activity_ids:
                raise EngageSeedBuilderError(
                    f"L'approche '{approach_id}' référence une activité absente du seed : '{activity_id}'."
                )

    for activity in activity_seed["activities"]:
        for approach_id in activity.get("approach_ids", []):
            if approach_id not in seen_approach_ids:
                raise EngageSeedBuilderError(
                    f"L'activité '{activity['activity_id']}' référence une "
                    f"approche absente du seed : '{approach_id}'."
                )


def validate_engage_attack_mapping_seed(mapping_seed: dict, activity_seed: dict) -> None:
    """Réf. tâche §20 : un mapping ne doit jamais référencer une activité
    Engage absente du seed, chaque attack_id doit respecter le format
    ATT&CK Txxxx/Txxxx.xxx, et aucune relation strictement dupliquée (même
    clé _engage_mapping_dedup_key) ne doit subsister."""
    known_activity_ids = {a["activity_id"] for a in activity_seed["activities"]}
    seen_relation_keys: set[tuple] = set()

    for mapping in mapping_seed["mappings"]:
        activity_id = mapping.get("engage_activity_id")
        if activity_id not in known_activity_ids:
            raise EngageSeedBuilderError(
                f"Le mapping référence une activité Engage absente du seed : '{activity_id}'."
            )

        attack_id = mapping.get("attack_id")
        if not isinstance(attack_id, str) or not _ATTACK_ID_RE.match(attack_id):
            raise EngageSeedBuilderError(
                f"Identifiant ATT&CK mal formé dans un mapping Engage : '{attack_id}'."
            )

        if not mapping.get("source_sha256"):
            raise EngageSeedBuilderError("Un mapping Engage doit conserver source_sha256.")

        relation_key = _engage_mapping_dedup_key(mapping)
        if relation_key in seen_relation_keys:
            raise EngageSeedBuilderError(
                f"Relation Engage<->ATT&CK strictement dupliquée : attack_id='{attack_id}', "
                f"engage_activity_id='{activity_id}'."
            )
        seen_relation_keys.add(relation_key)


# ---------------------------------------------------------------------------
# Rapport d'extraction (réf. tâche §18)
# ---------------------------------------------------------------------------


def build_engage_seed_report(activity_seed: dict, mapping_seed: dict, manifest_entries: list[dict]) -> dict:
    """Réf. tâche §18 : petit rapport local sur l'extraction Engage
    réalisée. warnings reste vide tant qu'aucune divergence n'est
    constatée — jamais ajusté artificiellement.

    Réf. correctif de nomenclature : la famille SAC correspond, dans les
    données réelles (`activity_details[id]["type"] == "Strategic"`), à
    "Strategic Activity" — jamais "Support Activity". La clé de rapport
    reflète donc `strategic_activity_count`, pas `support_activity_count`.
    """
    activities = activity_seed["activities"]
    engagement_activity_count = sum(1 for a in activities if a["activity_family"] == "EAC")
    strategic_activity_count = sum(1 for a in activities if a["activity_family"] == "SAC")
    distinct_attack_ids = {m["attack_id"] for m in mapping_seed["mappings"]}
    distinct_eav_ids = {
        m["adversary_vulnerability_id"] for m in mapping_seed["mappings"] if m.get("adversary_vulnerability_id")
    }
    return {
        "schema": "engage_seed_report",
        "schema_version": "1.0",
        "engage_version": activity_seed["engage_version"],
        "source_revision": activity_seed["source_revision"],
        "sources": manifest_entries,
        "activity_count": len(activities),
        "engagement_activity_count": engagement_activity_count,
        "strategic_activity_count": strategic_activity_count,
        "approach_count": len(activity_seed["approaches"]),
        "raw_attack_mapping_count": mapping_seed["raw_mapping_count"],
        "unique_attack_mapping_count": mapping_seed["unique_mapping_count"],
        "unique_attack_activity_pair_count": mapping_seed["unique_attack_activity_pair_count"],
        "number_of_attack_ids": len(distinct_attack_ids),
        "number_of_adversary_vulnerabilities": len(distinct_eav_ids),
        "warnings": [],
    }


# ---------------------------------------------------------------------------
# Manifest de provenance partagé (réf. tâche §7)
# ---------------------------------------------------------------------------


def merge_source_manifest(existing_manifest_path: str | Path, new_entries: list[dict]) -> dict:
    """Réf. tâche §7 : étend le manifest existant (ex. sources D3FEND) sans
    supprimer ni modifier sémantiquement les entrées déjà présentes. Un
    ré-exécution avec le même source_id remplace uniquement cette entrée
    (idempotence), jamais les autres."""
    path = Path(existing_manifest_path)
    existing_sources: list[dict] = []
    if path.exists():
        existing_data = json.loads(path.read_text(encoding="utf-8"))
        existing_sources = list(existing_data.get("sources", []))

    new_ids = {entry.get("source_id") for entry in new_entries}
    kept_existing = [entry for entry in existing_sources if entry.get("source_id") not in new_ids]
    return build_source_manifest(kept_existing + new_entries)


# ---------------------------------------------------------------------------
# CLI offline (réf. tâche §19) — aucun chemin, URL ou date codé en dur
# ---------------------------------------------------------------------------


def _run_cli(argv: list[str] | None = None) -> None:
    """Point d'entrée `python -m tools.deception_kb.engage_seed_builder`.

    Régénère, à partir de paramètres explicites uniquement, le staging
    activités/approches, le staging de mappings ATT&CK (déjà dédupliqué),
    le rapport, et étend le manifest de provenance partagé — sans jamais
    supprimer les entrées D3FEND existantes.
    """
    import argparse
    from datetime import date

    parser = argparse.ArgumentParser(
        description=(
            "Construit le staging MITRE Engage (activités, approches, mappings "
            "ATT&CK) à partir des fichiers officiels pinnés à un commit précis."
        )
    )
    parser.add_argument("--activities", required=True, help="Chemin vers activities.json (officiel).")
    parser.add_argument(
        "--activity-details", required=True, help="Chemin vers activity_details.json (officiel)."
    )
    parser.add_argument("--approaches", required=True, help="Chemin vers approaches.json (officiel).")
    parser.add_argument(
        "--approach-details", required=True, help="Chemin vers approach_details.json (officiel)."
    )
    parser.add_argument(
        "--approach-activity-mappings",
        required=True,
        help="Chemin vers approach_activity_mappings.json (officiel).",
    )
    parser.add_argument(
        "--attack-mapping", required=True, help="Chemin vers attack_mapping.json (officiel)."
    )
    parser.add_argument("--references", required=True, help="Chemin vers references.json (officiel).")
    parser.add_argument(
        "--engage-version", required=True, help="Version déclarée du jeu de données Engage (ex. 1.0)."
    )
    parser.add_argument(
        "--source-revision",
        required=True,
        help="Commit Git exact du dépôt mitre/engage pinné (jamais 'main'/'latest').",
    )
    parser.add_argument(
        "--retrieval-date", required=True, help="Date d'acquisition des fichiers officiels, format YYYY-MM-DD."
    )
    parser.add_argument("--out-dir", required=True, help="Répertoire de sortie du staging.")
    parser.add_argument(
        "--manifest",
        required=True,
        help="Chemin de source_manifest.json à étendre (créé si absent, entrées existantes préservées).",
    )
    args = parser.parse_args(argv)

    try:
        date.fromisoformat(args.retrieval_date)
    except ValueError as exc:
        raise EngageSeedBuilderError(
            f"--retrieval-date doit être au format YYYY-MM-DD (reçu : '{args.retrieval_date}')."
        ) from exc

    activity_seed = build_engage_activity_seed(
        activities_path=args.activities,
        activity_details_path=args.activity_details,
        approaches_path=args.approaches,
        approach_details_path=args.approach_details,
        approach_activity_mappings_path=args.approach_activity_mappings,
        references_path=args.references,
        engage_version=args.engage_version,
        source_revision=args.source_revision,
    )
    validate_engage_activity_seed(activity_seed)

    mapping_seed = build_engage_attack_mapping_seed(
        args.attack_mapping,
        activity_seed,
        engage_version=args.engage_version,
        source_revision=args.source_revision,
    )
    validate_engage_attack_mapping_seed(mapping_seed, activity_seed)

    source_files = activity_seed["source_files"]
    file_entries = [
        ("activities", args.activities, "activities.json", source_files["activities"]["sha256"]),
        (
            "activity_details",
            args.activity_details,
            "activity_details.json",
            source_files["activity_details"]["sha256"],
        ),
        ("approaches", args.approaches, "approaches.json", source_files["approaches"]["sha256"]),
        (
            "approach_details",
            args.approach_details,
            "approach_details.json",
            source_files["approach_details"]["sha256"],
        ),
        (
            "approach_activity_mappings",
            args.approach_activity_mappings,
            "approach_activity_mappings.json",
            source_files["approach_activity_mappings"]["sha256"],
        ),
        ("attack_mapping", args.attack_mapping, "attack_mapping.json", mapping_seed["source_sha256"]),
        ("references", args.references, "references.json", source_files["references"]["sha256"]),
    ]

    new_manifest_entries = [
        build_manifest_entry(
            source_id=f"engage-{role}-{args.engage_version}",
            source_name=f"MITRE Engage {role.replace('_', ' ').title()}",
            release_version=args.engage_version,
            official_url=_engage_official_url(args.source_revision, filename),
            local_filename=str(path),
            sha256=sha256_value,
            source_type="json",
            retrieval_date=args.retrieval_date,
            role=role,
            framework="MITRE Engage",
            source_revision=args.source_revision,
        )
        for role, path, filename, sha256_value in file_entries
    ]

    manifest = merge_source_manifest(args.manifest, new_manifest_entries)
    # Réf. §18 : le rapport Engage décrit ses propres sources (les 7
    # fichiers Engage), pas l'intégralité du manifest partagé qui peut
    # contenir d'autres frameworks (D3FEND).
    report = build_engage_seed_report(activity_seed, mapping_seed, manifest_entries=new_manifest_entries)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    version = args.engage_version

    activity_seed_path = out_dir / f"engage_activity_seed_{version}.json"
    mapping_seed_path = out_dir / f"engage_attack_mapping_seed_{version}.json"
    report_path = out_dir / f"engage_seed_report_{version}.json"
    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    activity_seed_path.write_text(
        json.dumps(activity_seed, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    mapping_seed_path.write_text(json.dumps(mapping_seed, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Activity seed: {activity_seed_path}")
    print(f"Attack mapping seed: {mapping_seed_path}")
    print(f"Report: {report_path}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    _run_cli()
