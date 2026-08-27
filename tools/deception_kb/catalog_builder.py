"""
Réf. architecture : "9. Base de connaissances cyberdéception" / "9.1
Pipeline de construction de la KB déception" (étapes 4 à 8) — contrat
technique du PFE Cyberdéception (CLAUDE.md).

Construit `data/deception/deception_catalog.json` (catalogue fermé D,
format interne PFE chargé par `src/knowledge_deception.py`) à partir du
staging D3FEND déjà versionné et testé
(`tools/deception_kb/d3fend_seed_builder.py`,
`data/deception/staging/d3fend_deception_seed_1.5.0.json`,
`d3fend_attack_mapping_seed_1.5.0.json`).

**Périmètre volontairement restreint (v1) — un concept D3FEND devient un
mécanisme du catalogue SEULEMENT s'il réunit les DEUX conditions
suivantes :**

1. `is_leaf = True` — un concept parent/catégorie (ex. D3-DO « Decoy
   Object », D3-DE « Decoy Environment ») n'est jamais lui-même un
   mécanisme déployable, seuls ses enfants le sont ;
2. au moins une relation directe avec ATT&CK dans
   `d3fend_attack_mapping_seed` — nécessaire pour renseigner
   `interaction_mechanism` (champ obligatoire du schéma, non vide) sans
   l'inventer.

Sur D3FEND 1.5.0, exactement 3 des 9 concepts-feuilles satisfont ces deux
conditions : **D3-DF (Decoy File), D3-DNR (Decoy Network Resource),
D3-DUC (Decoy User Credential)**. Les 6 autres feuilles (D3-DP, D3-DST,
D3-DPR, D3-CHN, D3-SHN, D3-IHN) possèdent une fiche D3FEND réelle
(définition, kb-article) mais AUCUNE relation ATT&CK directement tracée
dans ce staging précis : faute de preuve permettant de renseigner
`interaction_mechanism` sans l'inventer, elles sont explicitement
EXCLUES de ce catalogue v1 (§25.3 : « ne jamais inventer silencieusement
une valeur manquante » ; tâche §3 : « soit la laisser explicitement non
renseignée si le schéma le permet, soit exclure ce mécanisme »). Ce
n'est PAS un défaut de D3FEND : c'est une limite de couverture de ce
staging précis, documentée comme telle dans `excluded_concepts`.

**Audit documentaire des prérequis d'admissibilité** (réf.
`docs/chapter4/ADMISSIBILITY_EVIDENCE_AUDIT.md`, dernière passe avant gel
de l'implémentation) : `definition`/`kb-article`/`artifacts` de chacun
des 3 mécanismes, ainsi que MITRE Engage et la littérature déjà versés,
ont été relus systématiquement à la recherche d'affirmations
documentaires (jamais de simples recommandations « should »/« may »)
justifiant `required_asset_types`/`required_services`/
`required_artifacts`/`possible_placements`. Deux enrichissements
ponctuels en sont ressortis, chacun cité à une phrase précise du
kb-article D3FEND (`ADDITIONAL_LOCATION_TYPES`, `REQUIRED_ASSET_TYPES`
ci-dessous) — tout le reste (`requirements`, `realism_factors`,
`progression_effects`, `maintenance_requirements`,
`resource_requirements`, et le reste de `admissibility_profile.required_*`)
demeure à sa valeur par défaut (liste vide), faute de preuve
documentaire suffisamment directe. En particulier, `progression_effects`
(stop/redirect/contain/delay) appartient au modèle de cyberdéception du
PFE (chapitre 3), pas à l'ontologie D3FEND elle-même : ce n'est pas une
omission, c'est la raison d'être de SP2 (annotation contextuelle) — le
catalogue statique ne peut pas répondre à cette question
dynamique/contextuelle, seule une annotation (LLM ou repli déterministe)
le peut.

**Conséquence pour SP1** : `RequirementsSatisfied(d,ℓ)` reste
« undetermined » (politique prudente OPEN_DECISION 4) pour tout candidat
dont le mécanisme n'a pas de `required_*` non vide — c'est-à-dire tous
sauf `D3-DNR` après cette passe. `D3-DNR` peut désormais évaluer
« pass »/« fail » réellement, selon l'`asset_type` de l'emplacement
candidat (voir `docs/chapter4/outputs/sp1_real_example.json`).

**Distinction « aucun prérequis » (`known_none`) vs « prérequis
inconnu » (`unknown`)** : analysée explicitement dans l'audit — aucun
des 3 mécanismes ne possède de preuve documentaire d'une absence
CONFIRMÉE de prérequis (`known_none`) ; chaque liste vide reflète une
absence réelle d'information (`unknown`), déjà correctement représentée
par la sémantique actuelle de `DeceptionAdmissibilityProfile` (liste vide
→ `undetermined`). Aucun nouveau champ de statut n'a donc été introduit
dans le schéma — voir l'audit pour le raisonnement complet.

**Champs dérivés d'une transformation déterministe, uniforme et
documentée (pas une valeur inventée par mécanisme) :**
- `admissibility_profile.allowed_location_types` / `possible_placements` :
  dérivés de l'artefact cible D3FEND (`artifacts`) via une table de
  correspondance fixe `ARTIFACT_TO_LOCATION_TYPE` (ex. `d3f:File` ->
  `"filesystem"`), complétés le cas échéant par `ADDITIONAL_LOCATION_TYPES`
  (un seul cas : `D3-DF` -> `+"network_share"`, kb-article) ;
- `interaction_mechanism` : liste triée des `off_artifact_relation`
  observés dans `d3fend_attack_mapping_seed` pour ce concept (ex.
  `"accesses, creates, forges"`) — une lecture directe de la donnée
  D3FEND, pas une interprétation libre ;
- `admissibility_profile.required_asset_types` : vide par défaut,
  complété par `REQUIRED_ASSET_TYPES` (un seul cas : `D3-DNR` ->
  `["web_application_server", "file_server"]`, kb-article, avec réserve
  documentée sur la clause ouverte « or other », voir l'audit).

Ce module ne fait ni SP1, ni RAG, ni appel LLM : c'est une couche
OFFLINE (comme `d3fend_seed_builder.py`), pas une partie du runtime.

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

STAGING_DIR = Path("data/deception/staging")
DECEPTION_SEED_PATH = STAGING_DIR / "d3fend_deception_seed_1.5.0.json"
ATTACK_MAPPING_PATH = STAGING_DIR / "d3fend_attack_mapping_seed_1.5.0.json"
CATALOG_PATH = Path("data/deception/deception_catalog.json")

CATALOG_VERSION = "pfe-deception-catalog-1.0"

# Réf. docstring de module : transformation déterministe et uniforme,
# jamais une valeur inventée par mécanisme. Un seul artefact D3FEND par
# concept dans ce staging (source_technique_id -> artifacts), donc une
# correspondance directe suffit.
ARTIFACT_TO_LOCATION_TYPE: dict[str, str] = {
    "d3f:File": "filesystem",
    "d3f:NetworkResource": "network_resource",
    "d3f:Credential": "credential_store",
}

# Réf. docs/chapter4/ADMISSIBILITY_EVIDENCE_AUDIT.md — deux enrichissements
# ponctuels, chacun directement cité à une phrase précise du kb-article
# D3FEND (section « How it works », factuelle — jamais une recommandation
# « should »/« may » de la section « Considerations »), jamais inventés.
# Ne pas ajouter d'entrée ici sans un passage correspondant dans l'audit.

# D3-DF : "The decoy file is made available as a local or network
# resource." -> un second type d'emplacement possible, en complément de
# celui dérivé de target_artifacts (filesystem, via ARTIFACT_TO_LOCATION_TYPE).
ADDITIONAL_LOCATION_TYPES: dict[str, list[str]] = {
    "D3-DF": ["network_share"],
}

# D3-DNR : "Decoy network resources are deployed to web application
# servers, network file shares, or other network based sharing
# services." -> deux categories d'actifs de deploiement explicitement
# nommees (la clause ouverte "or other" n'est PAS encodee — rien de
# concret a y inventer, voir audit).
REQUIRED_ASSET_TYPES: dict[str, list[str]] = {
    "D3-DNR": ["web_application_server", "file_server"],
}


class CatalogBuilderError(Exception):
    """Erreur de construction du catalogue de déception."""


def _read_json_with_sha256(path: Path) -> tuple[Any, str]:
    raw_bytes = path.read_bytes()
    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    return json.loads(raw_bytes.decode("utf-8")), sha256


def _off_artifact_relations(concept_id: str, mapping_rows: list[dict]) -> list[str]:
    """Réf. docstring de module : ensemble trié des relations off_artifact
    réellement observées pour ce concept dans le staging ATT&CK."""
    return sorted(
        {row["relation_path"]["off_artifact_relation"] for row in mapping_rows if row["d3fend_id"] == concept_id}
    )


def _build_evidence(concept: dict, concept_id: str) -> list[dict]:
    evidence = []
    for item in concept.get("source_evidence", []):
        text = (item.get("evidence_text") or "").strip()
        if not text:
            continue
        evidence.append(
            {
                "source": f"d3fend:{concept_id}:{item.get('source_property', 'unknown')}",
                "passage": text,
            }
        )
    return evidence


def _build_mechanism(concept: dict, *, mapping_rows: list[dict], release_version: str) -> dict | None:
    """Retourne le mécanisme construit, ou None si le concept doit être
    exclu (voir docstring de module)."""
    concept_id = concept["source_technique_id"]
    relations = _off_artifact_relations(concept_id, mapping_rows)
    if not relations:
        return None

    artifacts = list(concept.get("artifacts", []))
    location_types = sorted(
        {ARTIFACT_TO_LOCATION_TYPE[a] for a in artifacts if a in ARTIFACT_TO_LOCATION_TYPE}
        | set(ADDITIONAL_LOCATION_TYPES.get(concept_id, []))
    )
    required_asset_types = sorted(REQUIRED_ASSET_TYPES.get(concept_id, []))
    evidence = _build_evidence(concept, concept_id)
    attack_technique_count = len({row["attack_id"] for row in mapping_rows if row["d3fend_id"] == concept_id})

    return {
        "id": concept_id,
        "name": concept["name"],
        "description": concept["definition"],
        "target_artifacts": artifacts,
        "requirements": [],
        "possible_placements": location_types,
        "interaction_mechanism": ", ".join(relations),
        "realism_factors": [],
        "progression_effects": [],
        "resource_requirements": {},
        "maintenance_requirements": [],
        "evidence": evidence,
        "version": release_version,
        "admissibility_profile": {
            "allowed_location_types": location_types,
            "required_asset_types": required_asset_types,
            "required_services": [],
            "required_artifacts": [],
            "exposure_mode": None,
            "metadata": {},
        },
        "metadata": {
            "d3fend_source_uri": concept.get("source_uri"),
            "d3fend_off_artifact_relations": relations,
            "d3fend_attack_technique_count": attack_technique_count,
        },
    }


def build_catalog(
    *,
    deception_seed_path: Path = DECEPTION_SEED_PATH,
    attack_mapping_path: Path = ATTACK_MAPPING_PATH,
) -> dict:
    """Réf. §9.1 (pipeline de construction de la KB déception, étapes
    4-8) : construit le catalogue fermé D (format interne PFE) à partir
    du staging D3FEND déjà versionné. Ne modifie ni le staging ni les
    fichiers officiels bruts."""
    deception_seed, deception_seed_sha256 = _read_json_with_sha256(deception_seed_path)
    attack_mapping, attack_mapping_sha256 = _read_json_with_sha256(attack_mapping_path)
    mapping_rows = attack_mapping["mappings"]
    release_version = deception_seed["release_version"]

    mechanisms: list[dict] = []
    excluded: list[dict] = []

    for concept in deception_seed["concepts"]:
        concept_id = concept["source_technique_id"]
        if not concept["is_leaf"]:
            excluded.append(
                {
                    "id": concept_id,
                    "name": concept["name"],
                    "reason": "concept parent/categorie (is_leaf=false) : jamais un mecanisme deployable, seuls ses enfants le sont",
                }
            )
            continue

        mechanism = _build_mechanism(concept, mapping_rows=mapping_rows, release_version=release_version)
        if mechanism is None:
            excluded.append(
                {
                    "id": concept_id,
                    "name": concept["name"],
                    "reason": "aucune relation ATT&CK directe dans ce staging : interaction_mechanism non justifiable sans l'inventer",
                }
            )
            continue

        mechanisms.append(mechanism)

    if not mechanisms:
        raise CatalogBuilderError(
            "Aucun mecanisme construit : le staging D3FEND fourni ne contient aucun "
            "concept-feuille avec une relation ATT&CK directe."
        )

    return {
        "schema": "pfe_deception_catalog",
        "schema_version": "1.0",
        "catalog_version": CATALOG_VERSION,
        "generated_from": {
            "d3fend_deception_seed": {
                "path": str(deception_seed_path),
                "sha256": deception_seed_sha256,
                "release_version": release_version,
            },
            "d3fend_attack_mapping_seed": {
                "path": str(attack_mapping_path),
                "sha256": attack_mapping_sha256,
                "release_version": attack_mapping["release_version"],
            },
        },
        "excluded_concepts": excluded,
        "mechanisms": mechanisms,
    }


def write_catalog(catalog: dict, path: Path = CATALOG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    write_catalog(build_catalog())
