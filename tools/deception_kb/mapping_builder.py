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


if __name__ == "__main__":
    write_mapping(build_mapping())
