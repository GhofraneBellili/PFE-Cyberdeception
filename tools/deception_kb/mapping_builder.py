"""
Réf. architecture : "10.2 Étape 1 — Mapping attaque ↔ déception" (M_{i,d})
et "9.1 Pipeline de construction de la KB déception" — contrat technique
du PFE Cyberdéception (CLAUDE.md).

Construit `data/deception/attack_deception_mapping.json` (matérialisation
versionnée de `M_{i,d}`) à partir du staging D3FEND↔ATT&CK déjà versé
(`d3fend_attack_mapping_seed_1.5.0.json`) et du catalogue final déjà
construit (`deception_catalog.json`, `tools/deception_kb/
catalog_builder.py`) : seules les relations dont `mechanism_id`
appartient réellement au catalogue final sont retenues (réf. tâche §4 :
« Ne pas considérer automatiquement toute activité Engage ou tout concept
D3FEND comme un mécanisme déployable »).

Chaque relation `(attack_id, mechanism_id)` unique regroupe TOUTES les
preuves (`evidence`) des lignes brutes qui la justifient (réf. tâche §4 :
« Si plusieurs sources justifient la même relation, conserver les
différentes preuves »), sans déduplication de contenu.

**Périmètre v1** : seules les relations D3FEND -> ATT&CK sont
matérialisées ici. Les relations Engage -> ATT&CK (792 lignes dans
`engage_attack_mapping_seed`) ne sont PAS incluses : accepter chaque
activité Engage comme un mécanisme déployable nécessiterait un jugement
sémantique non trivial, déjà signalé comme OPEN_DECISION non résolue
(`tools/deception_kb/README.md` — rapprochement D3FEND/Engage interdit
sans décision explicite). Ce périmètre pourra être étendu par une
décision explicite ultérieure, pas silencieusement ici.

Ce module ne fait ni SP1, ni RAG, ni appel LLM : c'est une couche OFFLINE
(comme `catalog_builder.py`), pas une partie du runtime. Il ne calcule
aucune pondération ni probabilité de mapping (réf. tâche §4 : « Ne créer
aucune pondération ou probabilité de mapping non définie dans le
modèle »).

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

STAGING_DIR = Path("data/deception/staging")
ATTACK_MAPPING_PATH = STAGING_DIR / "d3fend_attack_mapping_seed_1.5.0.json"
CATALOG_PATH = Path("data/deception/deception_catalog.json")
MAPPING_PATH = Path("data/deception/attack_deception_mapping.json")

MAPPING_VERSION = "pfe-attack-deception-mapping-1.0"


class MappingBuilderError(Exception):
    """Erreur de construction du mapping M_{i,d}."""


def _read_json_with_sha256(path: Path) -> tuple[Any, str]:
    raw_bytes = path.read_bytes()
    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    return json.loads(raw_bytes.decode("utf-8")), sha256


def build_mapping(
    *,
    attack_mapping_path: Path = ATTACK_MAPPING_PATH,
    catalog_path: Path = CATALOG_PATH,
) -> dict:
    """Réf. §10.2 : construit M_{i,d} en filtrant le staging D3FEND↔ATT&CK
    sur les seuls `mechanism_id` réellement présents dans le catalogue
    final déjà construit (aucun mécanisme n'est jamais inventé ici)."""
    attack_mapping, attack_mapping_sha256 = _read_json_with_sha256(attack_mapping_path)
    catalog, catalog_sha256 = _read_json_with_sha256(catalog_path)
    catalog_mechanism_ids = {mechanism["id"] for mechanism in catalog["mechanisms"]}

    if not catalog_mechanism_ids:
        raise MappingBuilderError(f"Le catalogue '{catalog_path}' ne contient aucun mécanisme.")

    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in attack_mapping["mappings"]:
        mechanism_id = row["d3fend_id"]
        if mechanism_id not in catalog_mechanism_ids:
            continue
        key = (row["attack_id"], mechanism_id)
        grouped.setdefault(key, []).append(row)

    if not grouped:
        raise MappingBuilderError(
            "Aucune relation retenue : aucun mechanism_id du staging ATT&CK "
            "ne correspond à un mécanisme du catalogue fourni."
        )

    relations = []
    for (attack_id, mechanism_id) in sorted(grouped):
        rows = grouped[(attack_id, mechanism_id)]
        evidence = [
            {
                "relation_path": row["relation_path"],
                "source": row.get("source"),
                "source_sha256": row.get("source_sha256"),
            }
            for row in rows
        ]
        relations.append(
            {
                "attack_id": attack_id,
                "mechanism_id": mechanism_id,
                "evidence": evidence,
                "origin": rows[0].get("origin", "d3fend_inferred"),
            }
        )

    return {
        "schema": "pfe_attack_deception_mapping",
        "schema_version": "1.0",
        "mapping_version": MAPPING_VERSION,
        "generated_from": {
            "d3fend_attack_mapping_seed": {
                "path": str(attack_mapping_path),
                "sha256": attack_mapping_sha256,
                "release_version": attack_mapping["release_version"],
            },
            "deception_catalog": {
                "path": str(catalog_path),
                "sha256": catalog_sha256,
                "catalog_version": catalog["catalog_version"],
            },
        },
        "relation_count": len(relations),
        "relations": relations,
    }


def write_mapping(mapping: dict, path: Path = MAPPING_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping, indent=2, ensure_ascii=False), encoding="utf-8")


# ===========================================================================
# Extension M_{i,d} — réf. tâche §9 « reconstruire M_{i,d} pour le nouveau
# catalogue, en distinguant relation DIRECTE et relation DÉRIVÉE »
# ===========================================================================
#
# `build_mapping()` ci-dessus (périmètre v1, D3FEND uniquement) reste
# INCHANGÉ — c'est la base auditée existante, réutilisée telle quelle
# ci-dessous. Cette extension ajoute :
#
# 1. `mapping_type: "derived"` sur les relations D3FEND->ATT&CK
#    existantes : le staging `d3fend_attack_mapping_seed` est lui-même le
#    résultat d'une requête SPARQL qui relie une technique D3FEND à une
#    technique offensive via une CHAÎNE D'ARTEFACTS PARTAGÉS (réf.
#    docstring de `d3fend_seed_builder.py`) — ce n'est jamais une relation
#    directement affirmée par une source (D3FEND ne dit pas explicitement
#    « D3-DUC contre T1078 »), c'est une inférence déterministe et
#    documentée : DÉRIVÉE, jamais présentée comme une relation officielle.
#
# 2. De NOUVELLES relations Engage->ATT&CK DIRECTES, à partir du staging
#    déjà versionné mais jusqu'ici volontairement inutilisé
#    `engage_attack_mapping_seed_1.0.json` (792 lignes, origin
#    "mitre_engage_v1.0") : chaque ligne relie explicitement une activité
#    MITRE Engage à une technique ATT&CK via une « adversary vulnerability »
#    officiellement documentée par MITRE Engage lui-même (pas une
#    inférence que nous avons construite) — DIRECTE.
#
# Les 6 mécanismes D3FEND étendus (D3-DP, D3-DST, D3-DPR, D3-CHN, D3-SHN,
# D3-IHN) et les 2 mécanismes de littérature (LIT-HONEYPOT, LIT-HONEYTOKEN)
# n'ont AUCUNE relation ATT&CK tracée dans les stagings disponibles :
# aucune relation n'est fabriquée pour eux (§25.3) — limite documentée
# explicitement dans docs/chapter4/outputs/catalog_statistics.*.
#
# Convention : identifiants de code en anglais, commentaires et docstrings
# en français (§25.1).

ENGAGE_ATTACK_MAPPING_PATH = STAGING_DIR / "engage_attack_mapping_seed_1.0.json"
EXPANDED_MAPPING_VERSION = "pfe-attack-deception-mapping-2.0"

D3FEND_DERIVATION_RULE = (
    "d3fend_attack_mapping_seed (d3fend-full-mappings.json) : requête SPARQL reliant une "
    "technique D3FEND à une technique offensive (off_tech) via une chaîne d'artefacts "
    "partagés (relation_path.off_artifact_relation) — inférence déterministe et documentée, "
    "jamais une relation officiellement affirmée par une source."
)


def _d3fend_relations_as_derived(base_relations: list[dict]) -> list[dict]:
    """Réf. docstring de section : ajoute `mapping_type`/`derivation_rule`
    aux relations D3FEND déjà construites par `build_mapping()`, sans
    modifier `origin`/`evidence` (traçabilité conservée intacte)."""
    return [
        {**relation, "mapping_type": "derived", "derivation_rule": D3FEND_DERIVATION_RULE}
        for relation in base_relations
    ]


def _engage_direct_relations(
    *, engage_attack_mapping_path: Path, catalog_mechanism_ids: set[str]
) -> tuple[list[dict], str]:
    """Réf. tâche §9 (relation DIRECTE) : filtre `engage_attack_mapping_seed`
    sur les seuls `engage_activity_id` réellement présents dans le
    catalogue fourni (jamais un mécanisme inventé), regroupe les preuves
    par (attack_id, mechanism_id)."""
    raw, sha256 = _read_json_with_sha256(engage_attack_mapping_path)

    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in raw["mappings"]:
        mechanism_id = row["engage_activity_id"]
        if mechanism_id not in catalog_mechanism_ids:
            continue
        key = (row["attack_id"], mechanism_id)
        grouped.setdefault(key, []).append(row)

    relations = []
    for (attack_id, mechanism_id) in sorted(grouped):
        rows = grouped[(attack_id, mechanism_id)]
        evidence = [
            {
                "adversary_vulnerability_id": row.get("adversary_vulnerability_id"),
                "adversary_vulnerability_text": row.get("adversary_vulnerability_text"),
                "source": row.get("source_file"),
                "source_sha256": row.get("source_sha256"),
            }
            for row in rows
        ]
        relations.append(
            {
                "attack_id": attack_id,
                "mechanism_id": mechanism_id,
                "evidence": evidence,
                "origin": rows[0].get("origin", "mitre_engage_v1.0"),
                "mapping_type": "direct",
                "derivation_rule": None,
            }
        )
    return relations, sha256


def build_expanded_mapping(
    *,
    attack_mapping_path: Path = ATTACK_MAPPING_PATH,
    engage_attack_mapping_path: Path = ENGAGE_ATTACK_MAPPING_PATH,
    catalog_path: Path = CATALOG_PATH,
) -> dict:
    """Réf. §9 : combine les relations D3FEND (dérivées, `build_mapping()`)
    et les relations Engage (directes, `engage_attack_mapping_seed`),
    filtrées sur le catalogue étendu fourni. Lève `MappingBuilderError` si
    aucune relation ne survit, comme `build_mapping()`."""
    base_mapping = build_mapping(attack_mapping_path=attack_mapping_path, catalog_path=catalog_path)
    _, catalog_sha256 = _read_json_with_sha256(catalog_path)
    catalog = json.loads(catalog_path.read_bytes().decode("utf-8"))
    catalog_mechanism_ids = {mechanism["id"] for mechanism in catalog["mechanisms"]}

    d3fend_relations = _d3fend_relations_as_derived(base_mapping["relations"])
    engage_relations, engage_mapping_sha256 = _engage_direct_relations(
        engage_attack_mapping_path=engage_attack_mapping_path, catalog_mechanism_ids=catalog_mechanism_ids
    )

    relations = sorted(d3fend_relations + engage_relations, key=lambda r: (r["attack_id"], r["mechanism_id"]))

    if not relations:
        raise MappingBuilderError(
            "Aucune relation retenue (D3FEND dérivées + Engage directes) pour le catalogue fourni."
        )

    return {
        "schema": "pfe_attack_deception_mapping",
        "schema_version": "2.0",
        "mapping_version": EXPANDED_MAPPING_VERSION,
        "generated_from": {
            "d3fend_attack_mapping_seed": base_mapping["generated_from"]["d3fend_attack_mapping_seed"],
            "engage_attack_mapping_seed": {
                "path": str(engage_attack_mapping_path),
                "sha256": engage_mapping_sha256,
            },
            "deception_catalog": {
                "path": str(catalog_path),
                "sha256": catalog_sha256,
                "catalog_version": catalog["catalog_version"],
            },
        },
        "relation_count": len(relations),
        "direct_relation_count": sum(1 for r in relations if r["mapping_type"] == "direct"),
        "derived_relation_count": sum(1 for r in relations if r["mapping_type"] == "derived"),
        "relations": relations,
    }


if __name__ == "__main__":
    write_mapping(build_expanded_mapping())
