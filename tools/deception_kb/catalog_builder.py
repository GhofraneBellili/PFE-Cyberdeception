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


# ===========================================================================
# Extension >= 25 mécanismes — réf. tâche « éliminer la limitation : le
# catalogue réel ne contient que 3 mécanismes »
# ===========================================================================
#
# `build_catalog()` ci-dessus (périmètre v1, strict, D3FEND uniquement avec
# relation ATT&CK directement tracée) reste INCHANGÉ : c'est une base de
# référence auditée et testée, pas un choix erroné à corriger. Cette
# extension applique une politique DIFFÉRENTE et plus large :
# `interaction_mechanism` peut désormais être construit à partir du texte
# documentaire réel (kb-article D3FEND « How it works », description/
# long_description MITRE Engage, passage de littérature) plutôt que
# seulement des relations ATT&CK tracées — mais JAMAIS par paraphrase
# libre : chaque valeur ci-dessous est justifiée par une citation exacte de
# la source (voir docs/chapter4/CATALOG_AUDIT.md pour la décision et la
# justification mécanisme par mécanisme).
#
# Composition du catalogue étendu (26 mécanismes) :
#   - 3 D3FEND « v1 » (D3-DF, D3-DUC, D3-DNR, inchangés) ;
#   - 6 D3FEND supplémentaires, feuilles réelles sans relation ATT&CK
#     tracée dans ce staging (D3-DP, D3-DST, D3-DPR, D3-CHN, D3-SHN,
#     D3-IHN) — leur fiche documentaire (definition + kb-article) EXISTE
#     réellement, seule la relation ATT&CK tracée manque : aucun M_{i,d}
#     ne sera donc généré pour eux (mapping_builder.py), mais ce sont des
#     mécanismes catalogués valides (critères §6 : description précise,
#     preuve documentaire, target_artifact/interaction_mechanism) ;
#   - 15 MITRE Engage (activités de type « Engagement », jamais
#     « Strategic » — les 8 activités Strategic sont toutes de la
#     planification/du process, jamais un mécanisme déployable, §6) ;
#   - 2 génériques de littérature (Honeypot, Honeytoken) — concepts
#     largement établis dans la littérature scientifique, distincts des
#     concepts D3FEND de granularité différente (voir audit : Honeypot =
#     hôte/service leurre unique, D3-DNR = ressource leurre greffée sur un
#     actif réel existant, D3-CHN/SHN/IHN = honeynet au niveau réseau).
#
# EAC0012 (Personas) est FUSIONNÉ dans D3-DP (Decoy Persona) comme preuve
# supplémentaire plutôt que catalogué séparément : les deux fiches
# décrivent le même mécanisme (fausse identité utilisateur), réf. §8
# (audit de déduplication) — ne jamais dupliquer une fiche pour gonfler le
# compte.
#
# Convention : identifiants de code en anglais, commentaires et docstrings
# en français (§25.1).

ENGAGE_ACTIVITY_SEED_PATH = STAGING_DIR / "engage_activity_seed_1.0.json"
LITERATURE_EVIDENCE_PATH = STAGING_DIR / "literature_evidence_seed_1.2.json"
LITERATURE_DOCUMENT_PATH = STAGING_DIR / "literature_document_seed_1.2.json"

EXPANDED_CATALOG_VERSION = "pfe-deception-catalog-2.0"

# ---------------------------------------------------------------------------
# D3FEND étendu — 6 feuilles réelles sans relation ATT&CK tracée
# ---------------------------------------------------------------------------

D3FEND_EXTENDED_IDS = ("D3-DP", "D3-DST", "D3-DPR", "D3-CHN", "D3-SHN", "D3-IHN")

# Chaque valeur cite la phrase exacte du kb-article D3FEND (jamais une
# paraphrase libre) — voir docs/chapter4/CATALOG_AUDIT.md pour la citation
# complète par mécanisme.
D3FEND_EXTENDED_INTERACTION_MECHANISM: dict[str, str] = {
    # "A false online identity is created for the purposes of interacting
    # with adversaries in a direct or indirect manner."
    "D3-DP": "interacts with adversaries (directly or indirectly) via a false online identity",
    # "Usage of decoy session tokens may be monitored to track attacker
    # behavior or otherwise control the beliefs of the attacker."
    "D3-DST": "uses (authenticates with) the decoy session token; usage is monitored",
    # "The media may include URLs, points of contact, or other identifiers
    # to entice interaction from adversaries."
    "D3-DPR": "interacts with URLs/points of contact embedded in publicly released decoy media",
    # "Decoy honeypots are deployed within the enterprise environment that
    # emulate certain services or portions of an OS to attract attackers."
    "D3-CHN": "connects to / interacts with emulated services on a network-connected honeynet",
    # "A standalone honeynet does not directly interact with the real
    # enterprise environment" (definition: "attracting attackers and
    # eliciting their behaviors").
    "D3-SHN": "interacts with the standalone honeynet, isolated from production enterprise systems",
    # "Integrated honeynets use full production environments [...] that
    # utilize computing resources or software that attract attackers, and
    # allow full interaction."
    "D3-IHN": "full interaction with production-integrated decoy computing resources/software",
}

D3FEND_EXTENDED_ARTIFACT_TO_LOCATION_TYPE: dict[str, str] = {
    "d3f:User": "account",
    "d3f:SessionToken": "session_store",
    "d3f:LocalAreaNetwork": "network_segment",
    "d3f:IntranetNetwork": "network_segment",
}


def _build_extended_d3fend_mechanism(concept: dict, *, release_version: str, extra_evidence: list[dict]) -> dict:
    concept_id = concept["source_technique_id"]
    artifacts = list(concept.get("artifacts", []))
    location_types = sorted(
        {D3FEND_EXTENDED_ARTIFACT_TO_LOCATION_TYPE[a] for a in artifacts if a in D3FEND_EXTENDED_ARTIFACT_TO_LOCATION_TYPE}
    )
    evidence = _build_evidence(concept, concept_id) + extra_evidence

    return {
        "id": concept_id,
        "name": concept["name"],
        "description": concept["definition"],
        "target_artifacts": artifacts,
        "requirements": [],
        "possible_placements": location_types,
        "interaction_mechanism": D3FEND_EXTENDED_INTERACTION_MECHANISM[concept_id],
        "realism_factors": [],
        "progression_effects": [],
        "resource_requirements": {},
        "maintenance_requirements": [],
        "evidence": evidence,
        "version": release_version,
        "admissibility_profile": {
            "allowed_location_types": location_types,
            "required_asset_types": [],
            "required_services": [],
            "required_artifacts": [],
            "exposure_mode": None,
            "metadata": {},
        },
        "metadata": {
            "d3fend_source_uri": concept.get("source_uri"),
            "d3fend_off_artifact_relations": [],
            "d3fend_attack_technique_count": 0,
            "inclusion_policy": "extended_v2_no_direct_attack_relation_in_staging",
        },
    }


# ---------------------------------------------------------------------------
# MITRE Engage — 15 activités « Engagement » retenues comme mécanismes
# déployables (réf. §6 : critères d'inclusion, jamais automatique)
# ---------------------------------------------------------------------------

# EAC0012 (Personas) fusionné dans D3-DP — pas un id de catalogue séparé.
ENGAGE_MERGED_INTO_D3FEND: dict[str, str] = {"EAC0012": "D3-DP"}

# Justification EXCLUE par activité (réf. docs/chapter4/CATALOG_AUDIT.md
# pour le raisonnement complet) — jamais silencieux.
ENGAGE_EXCLUDED_REASONS: dict[str, str] = {
    "EAC0001": "activite de MONITORING (API Monitoring) : observation, pas un mecanisme deployable percu par l'attaquant",
    "EAC0002": "activite de MONITORING (Network Monitoring)",
    "EAC0003": "activite de MONITORING (System Activity Monitoring)",
    "EAC0004": "activite d'ANALYSE (Network Analysis), pas un artefact deployable",
    "EAC0013": "activite d'ANALYSE (Malware Detonation / sandboxing) : technique d'investigation, pas un mecanisme de tromperie deploye contre l'attaquant",
    "EAC0017": "controle de SECURITE OPERATIONNELLE (Hardware Manipulation) : retrait de micro/camera pour la securite de l'operation elle-meme, pas percu comme un leurre par l'attaquant (source : 'often required to maintain operational safety')",
    "EAC0019": "activite de gestion INTERNE (Baseline) : definir/reinitialiser un etat de reference, aucun placement ni artefact concret percu par l'attaquant",
    "SAC0001": "activite STRATEGIQUE (Operational Objective) : planification, pas un mecanisme deployable",
    "SAC0002": "activite STRATEGIQUE (Persona Creation) : planification amont de EAC0012/D3-DP, pas elle-meme un mecanisme distinct",
    "SAC0003": "activite STRATEGIQUE (Storyboarding) : planification narrative",
    "SAC0004": "activite STRATEGIQUE (Cyber Threat Intelligence) : analyse, pas un mecanisme deployable",
    "SAC0005": "activite STRATEGIQUE (Gating Criteria) : criteres d'arret operationnel, pas un mecanisme deployable",
    "SAC0006": "activite STRATEGIQUE (After-Action Review) : retour d'experience post-operation",
    "SAC0009": "activite STRATEGIQUE (Threat Model) : evaluation de risque organisationnel",
    "SAC0012": "activite STRATEGIQUE (Engagement Environment) : conception amont de l'environnement, categorie/processus (memes motifs que D3-DE/D3-DO), pas elle-meme un mecanisme instancie",
}

# target_artifacts/possible_placements/interaction_mechanism dérivés d'une
# lecture directe de description/long_description (jamais inventés) — voir
# docs/chapter4/CATALOG_AUDIT.md pour la citation source de chaque champ.
ENGAGE_MECHANISM_SPECS: dict[str, dict] = {
    "EAC0005": {
        "target_artifacts": ["credential", "account", "file", "directory", "process"],
        "possible_placements": ["credential_store", "account", "filesystem"],
        "interaction_mechanism": "adversary encounters decoy credentials, accounts, files/directories, or system processes (Lures) intended to elicit, enable, block, encourage, or discourage a specific adversary action",
    },
    "EAC0006": {
        "target_artifacts": ["application", "service"],
        "possible_placements": ["host"],
        "interaction_mechanism": "adversary engages with a diverse set of installed applications/services (varied types and patch levels) configured on the target system",
    },
    "EAC0007": {
        "target_artifacts": ["network_device", "firewall", "printer", "phone"],
        "possible_placements": ["network_segment"],
        "interaction_mechanism": "adversary engages with an assorted collection of deployed network devices establishing the legitimacy of a deceptive network",
    },
    "EAC0008": {
        "target_artifacts": ["browsing_history", "filesystem_usage_history", "session_cookie", "decoy_account"],
        "possible_placements": ["host", "account"],
        "interaction_mechanism": "adversary observes system artifacts (browsing history, file usage, session cookies) generated by defender-driven exercising of a decoy account/system to reinforce believability",
    },
    "EAC0009": {
        "target_artifacts": ["email", "mailbox"],
        "possible_placements": ["mailbox"],
        "interaction_mechanism": "adversary's suspicious email/attachment is redirected into a monitored engagement-environment mailbox for detonation/analysis",
    },
    "EAC0010": {
        "target_artifacts": ["peripheral_device", "usb_device", "wifi_adapter"],
        "possible_placements": ["host"],
        "interaction_mechanism": "adversary interacts with introduced peripheral devices (e.g., external Wi-Fi adapters, USB devices) carrying additional deceptive information",
    },
    "EAC0011": {
        "target_artifacts": ["document", "picture", "registry_entry", "browsing_history", "connection_history"],
        "possible_placements": ["filesystem", "host"],
        "interaction_mechanism": "adversary encounters planted user data (documents, pictures, registry entries, browsing/connection history) supporting the credibility of the engagement narrative",
    },
    "EAC0014": {
        "target_artifacts": ["os_component", "filesystem", "discovery_command_output", "password_policy"],
        "possible_placements": ["host"],
        "interaction_mechanism": "adversary receives altered software outputs (discovery command results, password policy description, archival/encryption behavior) that hide real artifacts and/or reveal decoy artifacts",
    },
    "EAC0015": {
        "target_artifacts": ["os_version_info", "hardware_info", "account_info", "credential_info", "decoy_file", "decoy_email"],
        "possible_placements": [],
        "interaction_mechanism": "adversary is exposed to revealed or concealed facts/fictions (OS/hardware/account/credential info, decoy file/email content) engineered to adjust trust and uncertainty in the environment",
    },
    "EAC0016": {
        "target_artifacts": ["network_topology", "ip_addressing_scheme", "c2_channel"],
        "possible_placements": ["network_segment"],
        "interaction_mechanism": "adversary's network operations (C2/exfiltration channels, port/service reachability) are throttled, segmented, or redirected via manipulated network properties",
    },
    "EAC0018": {
        "target_artifacts": ["security_configuration", "group_policy", "firewall_rule"],
        "possible_placements": ["host", "network_share"],
        "interaction_mechanism": "adversary encounters selectively weakened or tightened security controls (e.g., a single disabled control on one specific share) that encourage or discourage activity in predetermined locations",
    },
    "EAC0020": {
        "target_artifacts": ["isolated_system", "isolated_network"],
        "possible_placements": ["network_segment", "host"],
        "interaction_mechanism": "adversary's lateral movement and activity are contained within an isolated decoy system/network with limited or no path to production resources",
    },
    "EAC0021": {
        "target_artifacts": ["malicious_email", "malicious_attachment", "malicious_usb"],
        "possible_placements": ["mailbox", "host", "network_segment"],
        "interaction_mechanism": "adversary's malicious link/file/device is intercepted and moved to a decoy system within a decoy network for continued engagement/analysis",
    },
    "EAC0022": {
        "target_artifacts": ["account", "file", "directory", "credential", "log", "browsing_history", "cookie"],
        "possible_placements": ["host", "account", "filesystem", "credential_store"],
        "interaction_mechanism": "adversary is presented with multiple diverse network/system artifacts (accounts, files, credentials, logs, browsing history, cookies) broadening the attack surface and revealing targeting preferences",
    },
    "EAC0023": {
        "target_artifacts": ["vulnerability"],
        "possible_placements": ["host", "network_resource"],
        "interaction_mechanism": "adversary exploits an intentionally introduced vulnerability in the engagement environment, steering targeting toward or away from specific resources",
    },
}


# Réf. ADMISSIBILITY_EVIDENCE_AUDIT.md (même discipline que
# REQUIRED_ASSET_TYPES/D3-DNR ci-dessus) : deux enrichissements
# ponctuels, chacun cité à une phrase factuelle exacte du long_description
# Engage (jamais une recommandation « should »/« may »), justifiant que le
# mécanisme opère spécifiquement sur une infrastructure de messagerie.
ENGAGE_REQUIRED_SERVICES: dict[str, list[str]] = {
    # "Email Manipulation can affect which mail appliances process mail
    # flows, where mail is forwarded, or what mail is present in an
    # inbox. [...] Suspicious emails may be removed from production
    # mailbox and placed into an inbox in an engagement environment."
    "EAC0009": ["email"],
    # "a defender might move a suspicious attachment from a corporate
    # inbox to an inbox on a system that, while in the corporate IP
    # space, is completely segmented from the enterprise network."
    "EAC0021": ["email"],
}


def _build_engage_evidence(activity: dict) -> list[dict]:
    activity_id = activity["activity_id"]
    evidence = []
    description = (activity.get("description") or "").strip()
    long_description = (activity.get("long_description") or "").strip()
    if description:
        evidence.append({"source": f"engage:{activity_id}:description", "passage": description})
    if long_description and long_description != description:
        evidence.append({"source": f"engage:{activity_id}:long_description", "passage": long_description})
    return evidence


def _build_engage_mechanism(activity: dict, *, release_version: str) -> dict:
    activity_id = activity["activity_id"]
    spec = ENGAGE_MECHANISM_SPECS[activity_id]
    location_types = list(spec["possible_placements"])
    required_services = sorted(ENGAGE_REQUIRED_SERVICES.get(activity_id, []))
    return {
        "id": activity_id,
        "name": activity["name"],
        "description": activity["description"],
        "target_artifacts": list(spec["target_artifacts"]),
        "requirements": [],
        "possible_placements": location_types,
        "interaction_mechanism": spec["interaction_mechanism"],
        "realism_factors": [],
        "progression_effects": [],
        "resource_requirements": {},
        "maintenance_requirements": [],
        "evidence": _build_engage_evidence(activity),
        "version": release_version,
        "admissibility_profile": {
            "allowed_location_types": location_types,
            "required_asset_types": [],
            "required_services": required_services,
            "required_artifacts": [],
            "exposure_mode": None,
            "metadata": {},
        },
        "metadata": {
            "engage_detail_type": activity.get("detail_type"),
            "inclusion_policy": "engage_activity_direct_engagement_technique",
        },
    }


def _build_persona_merge_evidence(engage_activities_by_id: dict) -> list[dict]:
    """Réf. §8 (déduplication) : EAC0012 (Personas) fusionné comme preuve
    supplémentaire de D3-DP plutôt que catalogué séparément."""
    activity = engage_activities_by_id["EAC0012"]
    return _build_engage_evidence(activity)


# ---------------------------------------------------------------------------
# Littérature — mécanismes génériques établis, distincts par granularité
# des concepts D3FEND/Engage déjà catalogués (voir docs/chapter4/CATALOG_AUDIT.md
# pour la justification complète, mécanisme par mécanisme, y compris les
# relations de granularité avec les mécanismes D3FEND/Engage existants) —
# réf. tâche « |D_knowledge| >= 50 mécanismes ».
#
# `evidence_selectors` identifie chaque preuve par (source_id, locator)
# EXACT (pas par source_id seul) : plusieurs mécanismes distincts peuvent
# désormais citer le même document (ex. doi_10.1145_3214305, 22 passages
# après l'extension de `data/deception/literature/evidence_candidates.json`)
# — filtrer par source_id seul agrégerait alors des preuves d'autres
# mécanismes sans rapport.
# ---------------------------------------------------------------------------

LITERATURE_MECHANISM_SPECS: dict[str, dict] = {
    "LIT-HONEYPOT": {
        "name": "Honeypot",
        "description": (
            "A closely monitored network decoy host or service used to distract adversaries from more "
            "valuable machines, provide early warning of new attacks, and allow in-depth examination of "
            "adversaries during and after exploitation."
        ),
        "target_artifacts": ["decoy_host"],
        "possible_placements": ["network_segment", "host"],
        "interaction_mechanism": "adversary scans, connects to, and attempts to exploit or log on to the monitored decoy host, diverting them from production systems",
        "evidence_selectors": (
            ("usenixsec2004_provos_virtual_honeypot_framework", "abstract"),
            ("doi_10.1109_csac.2003.1254322", "abstract"),
            ("usenixsec2021_fergusonwalter_decoy_psychological_deception_efficacy", "abstract"),
            ("usenixsec2021_fergusonwalter_decoy_psychological_deception_efficacy", "body_text_results"),
        ),
    },
    "LIT-HONEYTOKEN": {
        "name": "Honeytoken",
        "description": (
            "A fake but plausible-looking piece of data or resource (e.g., a database record, configuration "
            "entry, or API key) planted to detect unauthorized access; interacting with it creates a strong "
            "indicator of compromise. Generalizes beyond a single credential/session token (already covered "
            "by D3-DUC/D3-DST) to arbitrary non-credential decoy data."
        ),
        "target_artifacts": ["decoy_data", "decoy_record"],
        "possible_placements": ["database", "filesystem", "configuration_store"],
        "interaction_mechanism": "adversary accesses or exfiltrates the honeytoken (fake data/record), triggering a monitored indicator of compromise",
        "evidence_selectors": (("doi_10.1145_3678890.3678897", "abstract"),),
    },
    "LIT-TARPIT": {
        "name": "Network Tarpit",
        "description": (
            "A decoy machine that creates sticky, slow-responding network connections to stall automated "
            "scanning and confuse human adversaries during reconnaissance."
        ),
        "target_artifacts": ["decoy_host", "tcp_connection"],
        "possible_placements": ["network_segment"],
        "interaction_mechanism": "adversary's scanning tool or session opens a connection to the tarpit and is deliberately kept open/slowed, stalling reconnaissance",
        "evidence_selectors": (("doi_10.1145_3214305", "body_text_network_tarpit"),),
    },
    "LIT-DECEPTIVE-TOPOLOGY": {
        "name": "Deceptive Network Topology",
        "description": (
            "Skews the topology observed by an attacker's reconnaissance (e.g., traceroute, scanning) through "
            "random connection dropping and traffic forging, revealing a false network topology."
        ),
        "target_artifacts": ["network_topology"],
        "possible_placements": ["network_segment"],
        "interaction_mechanism": "adversary's scanning/traceroute probes are answered with forged responses that skew the perceived network topology",
        "evidence_selectors": (("doi_10.1145_3214305", "body_text_deceptive_topology"),),
    },
    "LIT-OS-FINGERPRINT": {
        "name": "Deceptive OS Fingerprint",
        "description": (
            "Mimics the network-stack behavior of a fake operating system to mislead OS fingerprinting tools "
            "used during reconnaissance. Distinct from EAC0014 (Software Manipulation, a broad MITRE Engage "
            "activity covering many output-manipulation cases) by its specific, network-stack-level technical "
            "implementation documented in the academic literature."
        ),
        "target_artifacts": ["os_fingerprint_response"],
        "possible_placements": ["host", "network_segment"],
        "interaction_mechanism": "adversary's OS fingerprinting tool (e.g., Nmap-style probes) receives responses mimicking a fake operating system",
        "evidence_selectors": (("doi_10.1145_3214305", "body_text_os_obfuscation"),),
    },
    "LIT-DECEPTIVE-ATTACK-GRAPH": {
        "name": "Deceptive Attack Graph",
        "description": (
            "Leverages a structured attack graph representation to drive attackers into following fake attack "
            "paths that distract them from real targets."
        ),
        "target_artifacts": ["attack_path", "decoy_vulnerability_chain"],
        "possible_placements": ["network_segment", "host"],
        "interaction_mechanism": "adversary follows a fake attack path/vulnerability chain constructed to distract from the real target",
        "evidence_selectors": (("doi_10.1145_3214305", "body_text_deceptive_attack_graph"),),
    },
    "LIT-ICS-DECOY": {
        "name": "Decoy ICS/OT Asset",
        "description": (
            "A deceptive simulation of an industrial control system (ICS) target that monitors network "
            "topology and creates fake but indistinguishable attack targets for adversaries targeting "
            "operational technology environments."
        ),
        "target_artifacts": ["decoy_ics_endpoint"],
        "possible_placements": ["network_segment", "host"],
        "interaction_mechanism": "adversary targeting an industrial control system interacts with a fake but indistinguishable ICS/OT attack target",
        "evidence_selectors": (("doi_10.1145_3214305", "body_text_decoy_ics_asset"),),
    },
    "LIT-DECOY-NIC": {
        "name": "Decoy Network Interface",
        "description": (
            "A decoy Network Interface Controller (NIC) intentionally set up so that only malicious software "
            "would use it, since benign software is not expected to interact with it."
        ),
        "target_artifacts": ["decoy_network_interface"],
        "possible_placements": ["host"],
        "interaction_mechanism": "malicious software running on the host uses the decoy network interface, which benign software never does, revealing its presence",
        "evidence_selectors": (("doi_10.1145_3214305", "body_text_decoy_network_interface"),),
    },
    "LIT-FAKE-HONEYPOT": {
        "name": "Fake Honeypot Camouflage",
        "description": (
            "Makes an ordinary but critical production system appear to be a honeypot, in order to confuse an "
            "attacker and turn them away from the real, compromised-worthy system — the inverse of a real "
            "honeypot."
        ),
        "target_artifacts": ["production_asset_disguise"],
        "possible_placements": ["host"],
        "interaction_mechanism": "adversary who has gained access believes the real critical system is a honeypot and disengages to avoid detection",
        "evidence_selectors": (("doi_10.1145_3214305", "body_text_fake_honeypot_camouflage"),),
    },
    "LIT-DECOY-COMPUTE": {
        "name": "Decoy Computation",
        "description": (
            "Duplicates an application server multiple times to generate decoy computation activity, "
            "concealing real processing among fake workload instances."
        ),
        "target_artifacts": ["decoy_compute_workload"],
        "possible_placements": ["host"],
        "interaction_mechanism": "adversary targets a duplicated decoy compute instance instead of the real application server",
        "evidence_selectors": (("doi_10.1145_3214305", "body_text_decoy_computation"),),
    },
    "LIT-HONEY-PERMISSION": {
        "name": "Honey Permission",
        "description": (
            "Extends role-based access control with fake permissions that assign unintended access to fake "
            "versions of sensitive system assets, detecting insiders/attackers who attempt to use them."
        ),
        "target_artifacts": ["decoy_rbac_permission"],
        "possible_placements": ["account"],
        "interaction_mechanism": "adversary or insider attempts to exercise a fake permission granting access to a decoy asset, triggering detection",
        "evidence_selectors": (("doi_10.1145_3214305", "body_text_honey_permission"),),
    },
    "LIT-SOFTWARE-DECOY": {
        "name": "Intelligent Software Decoy",
        "description": (
            "A decoy software component that detects and responds to patterns of suspicious behavior, "
            "maintaining a repository of behavior patterns and decoying actions."
        ),
        "target_artifacts": ["decoy_software_component"],
        "possible_placements": ["host"],
        "interaction_mechanism": "adversary's tool interacts with the software component, whose behavior-pattern detection recognizes and responds to the suspicious interaction",
        "evidence_selectors": (("doi_10.1145_3214305", "body_text_intelligent_software_decoy"),),
    },
    "LIT-HONEYPATCH": {
        "name": "Honey-patch",
        "description": (
            "Converts a software patch into a fake but valid-looking vulnerability; upon detecting exploitation "
            "of the fake vulnerability, the system seamlessly forwards the attacker to a vulnerable decoy "
            "version of the software. Distinct from EAC0023 (Introduced Vulnerabilities, a broad MITRE Engage "
            "activity) by this specific patch-masquerading-plus-redirect implementation."
        ),
        "target_artifacts": ["decoy_vulnerability", "decoy_software_version"],
        "possible_placements": ["host"],
        "interaction_mechanism": "adversary exploits what appears to be an unpatched vulnerability and is seamlessly redirected to a vulnerable decoy version of the software",
        "evidence_selectors": (("doi_10.1145_3214305", "body_text_honey_patch"),),
    },
    "LIT-SHADOW-HONEYPOT": {
        "name": "Shadow Honeypot",
        "description": (
            "Extends a honeypot with anomaly-based detection: an instance of the target application that "
            "shares its real context and internal state, used to process anomalous traffic. Distinct from the "
            "generic Honeypot (LIT-HONEYPOT) by sharing live application state rather than being an isolated "
            "decoy."
        ),
        "target_artifacts": ["decoy_application_instance"],
        "possible_placements": ["host"],
        "interaction_mechanism": "traffic flagged as anomalous is processed by the shadow instance, which shares the real application's context/state to validate the attack without risking production data",
        "evidence_selectors": (("doi_10.1145_3214305", "body_text_shadow_honeypot"),),
    },
    "LIT-SOFTWARE-TRAP": {
        "name": "Software Trap",
        "description": (
            "A trap dissimulated in application code as a gadget that detects return-oriented programming "
            "(ROP) exploitation attempts."
        ),
        "target_artifacts": ["code_gadget_trap"],
        "possible_placements": ["host"],
        "interaction_mechanism": "adversary's ROP exploit manipulates the planted code gadget, which detects and notifies the ongoing attack",
        "evidence_selectors": (("doi_10.1145_3214305", "body_text_software_trap"),),
    },
    "LIT-DECOY-HYPERLINK": {
        "name": "Decoy Hyperlink",
        "description": (
            "Embeds decoy links in a web application that are invisible to normal human users but are "
            "triggered by automated crawlers and web bots, revealing their presence."
        ),
        "target_artifacts": ["decoy_hyperlink"],
        "possible_placements": ["network_resource"],
        "interaction_mechanism": "an automated crawler/bot follows the invisible decoy link, revealing itself as non-human traffic",
        "evidence_selectors": (("doi_10.1145_3214305", "body_text_decoy_hyperlink"),),
    },
    "LIT-HONEY-CONFIG": {
        "name": "Honey Configuration File",
        "description": (
            "A web-facing configuration file (e.g., robots.txt) seeded with fake entries and invisible links to "
            "detect scanners and attackers who inspect it."
        ),
        "target_artifacts": ["decoy_configuration_file"],
        "possible_placements": ["network_resource"],
        "interaction_mechanism": "adversary's scanner inspects the configuration file and follows a fake entry/invisible link that only an automated or malicious actor would use",
        "evidence_selectors": (("doi_10.1145_3214305", "body_text_honey_configuration_file"),),
    },
    "LIT-DECOY-FORM": {
        "name": "Decoy Web Form/Parameter",
        "description": (
            "Decoy form fields and honey URL parameters embedded in a web application that display fake "
            "configuration errors, misleading attackers probing the application."
        ),
        "target_artifacts": ["decoy_form_field", "decoy_url_parameter"],
        "possible_placements": ["network_resource"],
        "interaction_mechanism": "adversary probing the web application interacts with a decoy form field or URL parameter, exposing a fake configuration error",
        "evidence_selectors": (("doi_10.1145_3214305", "body_text_decoy_form_field"),),
    },
    "LIT-HONEYWORD": {
        "name": "Honeyword",
        "description": (
            "Multiple false candidate passwords stored alongside the real (hashed) password for an account; "
            "any login attempt using a honeyword sets off an alarm, concealing which password is authentic even "
            "if the password file is stolen."
        ),
        "target_artifacts": ["decoy_password"],
        "possible_placements": ["credential_store"],
        "interaction_mechanism": "adversary who stole the password file attempts to log in with a honeyword instead of the real password, triggering an alarm",
        "evidence_selectors": (("doi_10.1145_3214305", "body_text_honeyword"),),
    },
    "LIT-HONEY-ENCRYPTION": {
        "name": "Honey Encryption",
        "description": (
            "Produces a ciphertext that, when decrypted with an incorrect key or password, yields a plausible-"
            "looking but bogus plaintext instead of an obvious failure, confusing an adversary attempting "
            "brute-force decryption."
        ),
        "target_artifacts": ["decoy_ciphertext"],
        "possible_placements": ["filesystem", "configuration_store"],
        "interaction_mechanism": "adversary brute-forcing the encryption key obtains a plausible-looking decoy plaintext instead of a clear failure signal, unable to tell the correct key from a wrong one",
        "evidence_selectors": (("doi_10.1145_3214305", "body_text_honey_encryption"),),
    },
    "LIT-DECOY-SOURCECODE": {
        "name": "Decoy Source Code",
        "description": (
            "Fake but believable source code files planted to detect the exfiltration of proprietary source "
            "code by insiders or attackers."
        ),
        "target_artifacts": ["decoy_source_file"],
        "possible_placements": ["filesystem"],
        "interaction_mechanism": "adversary or insider exfiltrates the decoy source code file believing it to be proprietary, revealing the exfiltration attempt",
        "evidence_selectors": (("doi_10.1145_3214305", "body_text_decoy_source_code"),),
    },
    "LIT-DECOY-TRAFFIC": {
        "name": "Decoy Network Traffic",
        "description": (
            "Generates decoy network traffic (chaff) to dissimulate sensitive real network connections, making "
            "them less likely to be identified and targeted by an adversary observing the network."
        ),
        "target_artifacts": ["decoy_traffic_flow"],
        "possible_placements": ["network_segment"],
        "interaction_mechanism": "adversary eavesdropping on the network observes decoy traffic flows mixed with real connections, reducing the chance of identifying the real one",
        "evidence_selectors": (("doi_10.1145_3214305", "body_text_decoy_network_traffic"),),
    },
    "LIT-IP-ROTATION": {
        "name": "Dynamic IP Address Rotation",
        "description": (
            "Periodically rotates which virtual machine host is mapped to an externally visible IP address; the "
            "VM host previously in use is analyzed for evidence of intrusion and removed from rotation if "
            "compromised — a moving-target-defense form of deception that prevents an adversary from reliably "
            "targeting a fixed address."
        ),
        "target_artifacts": ["ip_address_mapping"],
        "possible_placements": ["network_segment"],
        "interaction_mechanism": "adversary targeting a specific external IP address is unknowingly redirected to a periodically rotated VM host, exposing prior intrusion attempts to analysis",
        "evidence_selectors": (("doi_10.1016_j.cose.2021.102288", "body_text_ip_address_rotation"),),
    },
    "LIT-DYNAMIC-IDS": {
        "name": "Dynamic IDS Placement",
        "description": (
            "Dynamically and continuously changes the network placement of intrusion detection sensors over "
            "time, creating uncertainty about their location and increasing the likelihood that adversary "
            "actions are detected."
        ),
        "target_artifacts": ["ids_sensor_placement"],
        "possible_placements": ["network_segment"],
        "interaction_mechanism": "adversary cannot reliably predict or avoid the current location of detection sensors, increasing the chance their activity is observed",
        "evidence_selectors": (("doi_10.1016_j.cose.2021.102288", "body_text_dynamic_ids_placement"),),
    },
    "LIT-PLATFORM-MIGRATION": {
        "name": "Cross-Platform Application Migration",
        "description": (
            "Migrates a running application between virtual machines with different platforms (OS/architecture) "
            "while preserving execution state, increasing uncertainty for an adversary who must re-target a "
            "changing platform."
        ),
        "target_artifacts": ["application_runtime_platform"],
        "possible_placements": ["host"],
        "interaction_mechanism": "adversary who has profiled the application's platform finds it has migrated to a different OS/architecture, invalidating platform-specific exploits",
        "evidence_selectors": (("doi_10.1016_j.cose.2021.102288", "body_text_cross_platform_migration"),),
    },
    "LIT-SOFTWARE-DIVERSITY": {
        "name": "Software Diversity Randomization",
        "description": (
            "Breaks a software binary into function blocks and randomly shuffles their order at load time, so "
            "every execution instance is unique, hindering code-reuse (e.g., ROP) exploitation."
        ),
        "target_artifacts": ["binary_layout"],
        "possible_placements": ["host"],
        "interaction_mechanism": "adversary's exploit relies on a known binary layout that has been randomized for this execution instance, causing the exploit to fail unpredictably",
        "evidence_selectors": (("doi_10.1016_j.cose.2021.102288", "body_text_software_diversity"),),
    },
    "LIT-MULTIPATH-ROUTING": {
        "name": "Dynamic Multipath Routing",
        "description": (
            "Uses SDN features to frequently modify communication routes between devices so that any single "
            "vantage point only observes a portion of the exchanged traffic, preventing an eavesdropper from "
            "reconstructing a full communication."
        ),
        "target_artifacts": ["network_route"],
        "possible_placements": ["network_segment"],
        "interaction_mechanism": "adversary eavesdropping from a fixed network vantage point only intercepts a portion of the communication, unable to reconstruct the full exchange",
        "evidence_selectors": (("doi_10.1016_j.cose.2021.102288", "body_text_dynamic_multipath_routing"),),
    },
}


def _build_literature_evidence(selectors: tuple[tuple[str, str], ...], literature_evidence: list[dict]) -> list[dict]:
    return [
        {"source": item["evidence_id"], "passage": item["text"]}
        for item in literature_evidence
        if (item["source_id"], item["locator"]) in selectors
    ]


def _build_literature_mechanism(mechanism_id: str, *, literature_evidence: list[dict], release_version: str) -> dict:
    spec = LITERATURE_MECHANISM_SPECS[mechanism_id]
    evidence = _build_literature_evidence(spec["evidence_selectors"], literature_evidence)
    if not evidence:
        raise CatalogBuilderError(
            f"Aucune preuve littérature trouvée pour '{mechanism_id}' parmi {spec['evidence_selectors']} : "
            "un mécanisme catalogué doit toujours avoir au moins une preuve réelle."
        )
    location_types = list(spec["possible_placements"])
    return {
        "id": mechanism_id,
        "name": spec["name"],
        "description": spec["description"],
        "target_artifacts": list(spec["target_artifacts"]),
        "requirements": [],
        "possible_placements": location_types,
        "interaction_mechanism": spec["interaction_mechanism"],
        "realism_factors": [],
        "progression_effects": [],
        "resource_requirements": {},
        "maintenance_requirements": [],
        "evidence": evidence,
        "version": release_version,
        "admissibility_profile": {
            "allowed_location_types": location_types,
            "required_asset_types": [],
            "required_services": [],
            "required_artifacts": [],
            "exposure_mode": None,
            "metadata": {},
        },
        "metadata": {
            "literature_source_ids": sorted({source_id for source_id, _ in spec["evidence_selectors"]}),
            "inclusion_policy": "literature_generic_established_mechanism",
        },
    }


# ---------------------------------------------------------------------------
# Assemblage du catalogue étendu
# ---------------------------------------------------------------------------


def build_expanded_catalog(
    *,
    deception_seed_path: Path = DECEPTION_SEED_PATH,
    attack_mapping_path: Path = ATTACK_MAPPING_PATH,
    engage_activity_seed_path: Path = ENGAGE_ACTIVITY_SEED_PATH,
    literature_evidence_path: Path = LITERATURE_EVIDENCE_PATH,
) -> dict:
    """Réf. tâche « étendre le catalogue à >= 25 mécanismes réels » :
    combine le périmètre v1 (`build_catalog`, 3 mécanismes D3FEND avec
    relation ATT&CK tracée) avec l'extension D3FEND (6), MITRE Engage (15)
    et littérature (2) — 26 mécanismes au total. Chaque exclusion reste
    documentée (`excluded_concepts`), jamais silencieuse."""
    base_catalog = build_catalog(deception_seed_path=deception_seed_path, attack_mapping_path=attack_mapping_path)

    deception_seed, deception_seed_sha256 = _read_json_with_sha256(deception_seed_path)
    engage_seed, engage_seed_sha256 = _read_json_with_sha256(engage_activity_seed_path)
    literature_seed, literature_seed_sha256 = _read_json_with_sha256(literature_evidence_path)

    release_version = deception_seed["release_version"]
    engage_version = engage_seed.get("engage_version") or engage_seed.get("schema_version")
    literature_version = literature_seed.get("schema_version")

    concepts_by_id = {c["source_technique_id"]: c for c in deception_seed["concepts"]}
    engage_activities_by_id = {a["activity_id"]: a for a in engage_seed["activities"]}
    literature_evidence = literature_seed["evidence"]

    mechanisms = list(base_catalog["mechanisms"])
    excluded = [e for e in base_catalog["excluded_concepts"] if e["id"] not in D3FEND_EXTENDED_IDS]

    # --- D3FEND étendu (6) ---
    persona_extra_evidence = _build_persona_merge_evidence(engage_activities_by_id)
    for concept_id in D3FEND_EXTENDED_IDS:
        concept = concepts_by_id[concept_id]
        extra_evidence = persona_extra_evidence if concept_id == "D3-DP" else []
        mechanisms.append(
            _build_extended_d3fend_mechanism(concept, release_version=release_version, extra_evidence=extra_evidence)
        )

    # --- MITRE Engage (15) ---
    for activity_id, activity in sorted(engage_activities_by_id.items()):
        if activity_id in ENGAGE_MECHANISM_SPECS:
            mechanisms.append(_build_engage_mechanism(activity, release_version=str(engage_version)))
        elif activity_id in ENGAGE_MERGED_INTO_D3FEND:
            excluded.append(
                {
                    "id": activity_id,
                    "name": activity["name"],
                    "reason": f"fusionne dans {ENGAGE_MERGED_INTO_D3FEND[activity_id]} (meme mecanisme, réf. §8 deduplication) : preuve ajoutee en evidence supplementaire, pas un id de catalogue separe",
                }
            )
        else:
            reason = ENGAGE_EXCLUDED_REASONS.get(activity_id)
            if reason is None:
                raise CatalogBuilderError(
                    f"Activite Engage '{activity_id}' ni incluse, ni fusionnee, ni justifiee comme exclue : "
                    "toute activite doit relever explicitement d'un de ces trois cas (jamais silencieux)."
                )
            excluded.append({"id": activity_id, "name": activity["name"], "reason": reason})

    # --- Littérature (2) ---
    for mechanism_id in sorted(LITERATURE_MECHANISM_SPECS):
        mechanisms.append(
            _build_literature_mechanism(mechanism_id, literature_evidence=literature_evidence, release_version=str(literature_version))
        )

    return {
        "schema": "pfe_deception_catalog",
        "schema_version": "1.0",
        "catalog_version": EXPANDED_CATALOG_VERSION,
        "generated_from": {
            "d3fend_deception_seed": base_catalog["generated_from"]["d3fend_deception_seed"],
            "d3fend_attack_mapping_seed": base_catalog["generated_from"]["d3fend_attack_mapping_seed"],
            "engage_activity_seed": {
                "path": str(engage_activity_seed_path),
                "sha256": engage_seed_sha256,
                "engage_version": engage_version,
            },
            "literature_evidence_seed": {
                "path": str(literature_evidence_path),
                "sha256": literature_seed_sha256,
                "schema_version": literature_version,
            },
        },
        "excluded_concepts": excluded,
        "mechanisms": mechanisms,
    }


if __name__ == "__main__":
    write_catalog(build_expanded_catalog())
