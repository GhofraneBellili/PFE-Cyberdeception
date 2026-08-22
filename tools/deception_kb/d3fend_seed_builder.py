"""
Réf. architecture : "9. Base de connaissances cyberdéception" / "9.1
Pipeline de construction de la KB déception" — contrat technique du PFE
Cyberdéception (CLAUDE.md).

Couche OFFLINE de construction de données (phase 4B.1) : transforme les
fichiers officiels MITRE D3FEND (ontologie JSON-LD + mappings inférés) en
un STAGING documentaire fidèle à D3FEND, limité à la branche "Deceive".

Ce module NE fait PAS partie du runtime SP1/SP2/SP3 : il ne construit PAS
le catalogue final data/deception/deception_catalog.json (chargé par
src/knowledge_deception.py), ne calcule ni D_i, ni C_{i,h}, ni Allowed, ni
RequirementsSatisfied, ni Relevant, n'effectue aucun RAG ni appel LLM, et ne
produit aucun M_{i,d} exploitable directement par SP1. Les mappings D3FEND
↔ ATT&CK extraits ici sont du staging documentaire ("origin":
"d3fend_inferred"), pas des décisions d'admissibilité.

Format réellement observé dans D3FEND 1.5.0 (voir tools/deception_kb/README.md
pour le détail complet de l'inspection) :

- l'ontologie (d3fend.json) est un document JSON-LD {"@context": {...},
  "@graph": [...]} ; chaque classe porte notamment d3f:d3fend-id,
  d3f:definition, d3f:kb-article, d3f:kb-reference, d3f:synonym, d3f:spoofs,
  d3f:manages, d3f:enables, rdfs:label, rdfs:subClassOf ;
- la tactique "Deceive" est une d3f:DefensiveTactic ; les techniques qui lui
  appartiennent portent une propriété directe d3f:enables -> d3f:Deceive
  (vérifié par recoupement avec le motif OWL owl:Restriction équivalent) ;
- les mappings inférés (d3fend-full-mappings.json) sont un résultat de
  requête SPARQL {"head": {...}, "results": {"bindings": [...]}} ; chaque
  binding relie une technique D3FEND (def_tech) à une technique offensive
  (off_tech, off_tech_id) via une chaîne d'artefacts partagés, et précise
  framework_key ("enterprise", "ics", "sparta", ...) — seul "enterprise"
  correspond au périmètre ATT&CK Enterprise retenu par CLAUDE.md §8.

Convention : identifiants de code en anglais, commentaires et docstrings en
français (§25.1).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from src.schemas import ATTACK_TECHNIQUE_ID_PATTERN

# ---------------------------------------------------------------------------
# Constantes de format — réf. inspection réelle de D3FEND 1.5.0 (voir README)
# ---------------------------------------------------------------------------

# Réf. tâche §7 : concept racine ciblé explicitement (périmètre scientifique
# de cette extraction), pas une liste de techniques codée en dur.
DECEIVE_TACTIC_ID = "d3f:Deceive"

_ENABLES_PROPERTY = "d3f:enables"
_SUBCLASS_OF_PROPERTY = "rdfs:subClassOf"
_BLANK_NODE_PREFIX = "_:"

# Seul le framework "enterprise" correspond au périmètre ATT&CK retenu par
# CLAUDE.md §8 (enterprise-attack.json) ; d3fend-full-mappings.json mélange
# aussi "ics" (ATT&CK ICS) et "sparta" (MITRE SPARTA, IDs non-ATT&CK du
# type "PER-0005") — constaté lors de l'inspection réelle du fichier 1.5.0.
_ATTACK_FRAMEWORK_KEY = "enterprise"

_ATTACK_ID_RE = re.compile(ATTACK_TECHNIQUE_ID_PATTERN)


class D3fendSeedBuilderError(Exception):
    """Erreur de construction ou de validation du staging D3FEND."""


# ---------------------------------------------------------------------------
# Utilitaires génériques
# ---------------------------------------------------------------------------


def read_json_with_sha256(path: str | Path) -> tuple[Any, str]:
    """Réf. tâche §5 : lit un fichier JSON et calcule le SHA-256 sur les
    octets exacts du fichier, avant tout décodage/parsing (provenance)."""
    file_path = Path(path)
    raw_bytes = file_path.read_bytes()
    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    parsed = json.loads(raw_bytes.decode("utf-8"))
    return parsed, sha256


def _as_list(value: Any) -> list[Any]:
    """Les propriétés JSON-LD D3FEND sont tantôt un objet unique, tantôt une
    liste, selon la cardinalité réelle observée dans le fichier. Normalise
    sans changer le contenu."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _resolve_iri(context: dict, prefixed_id: str) -> str:
    """Résout un identifiant préfixé (ex. 'd3f:DecoyObject') en IRI complète
    à partir du @context réellement déclaré dans le fichier — jamais un
    préfixe supposé/codé en dur."""
    if ":" not in prefixed_id:
        return prefixed_id
    prefix, local = prefixed_id.split(":", 1)
    base = context.get(prefix)
    if not isinstance(base, str):
        return prefixed_id
    return base + local


# ---------------------------------------------------------------------------
# Hiérarchie de la branche Deceive (ontologie d3fend.json)
# ---------------------------------------------------------------------------


def _index_graph_by_id(graph: list[dict]) -> dict[str, dict]:
    """Indexe les nœuds du @graph JSON-LD par @id, en conservant l'ordre
    d'apparition du fichier source (déterminisme, réf. tâche §16)."""
    return {node["@id"]: node for node in graph if isinstance(node, dict) and "@id" in node}


def _direct_parent_ids(node: dict) -> list[str]:
    """Extrait les parents directs via rdfs:subClassOf, en excluant les
    nœuds blancs owl:Restriction (motif OWL utilisé par D3FEND pour exprimer
    les mêmes relations sous une autre forme, sans identité propre)."""
    parents = []
    for item in _as_list(node.get(_SUBCLASS_OF_PROPERTY)):
        if isinstance(item, dict) and "@id" in item and not item["@id"].startswith(_BLANK_NODE_PREFIX):
            parents.append(item["@id"])
    return parents


def find_deceive_root_ids(nodes_by_id: dict[str, dict]) -> list[str]:
    """Réf. tâche §7 : identifie les classes qui portent une propriété
    directe d3f:enables -> d3f:Deceive (racines réelles de la branche),
    sans jamais coder en dur une liste d'identifiants D3FEND."""
    roots = []
    for node_id, node in nodes_by_id.items():
        for enabled in _as_list(node.get(_ENABLES_PROPERTY)):
            if isinstance(enabled, dict) and enabled.get("@id") == DECEIVE_TACTIC_ID:
                roots.append(node_id)
                break
    return roots


def _build_children_map(nodes_by_id: dict[str, dict]) -> dict[str, list[str]]:
    """Construit la carte parent_id -> [child_id] à partir de la hiérarchie
    rdfs:subClassOf de tout le graphe, dans l'ordre du fichier source."""
    children: dict[str, list[str]] = {}
    for node_id, node in nodes_by_id.items():
        for parent_id in _direct_parent_ids(node):
            children.setdefault(parent_id, []).append(node_id)
    return children


def collect_branch_ids(root_ids: list[str], children_map: dict[str, list[str]]) -> list[str]:
    """Réf. tâche §7 : parcours déterministe (DFS, ordre du fichier source)
    de tous les descendants des racines de la branche Deceive."""
    seen: list[str] = []
    seen_set: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in seen_set:
            return
        seen_set.add(node_id)
        seen.append(node_id)
        for child_id in children_map.get(node_id, []):
            visit(child_id)

    for root_id in root_ids:
        visit(root_id)
    return seen


# ---------------------------------------------------------------------------
# Extraction des champs d'un concept (§9 et §10 de la tâche)
# ---------------------------------------------------------------------------


def _extract_synonyms(node: dict) -> list[str]:
    """d3f:synonym, réellement observé sous forme de chaîne unique ou de
    liste selon les concepts (§2 : lecture défensive, jamais d'invention)."""
    return [s for s in _as_list(node.get("d3f:synonym")) if isinstance(s, str)]


def _extract_artifacts(node: dict) -> list[str]:
    """Réf. tâche §9 (artifacts) : dérivé des propriétés réellement
    observées d3f:spoofs (artefact imité par un leurre) et d3f:manages
    (artefact géré par un environnement de leurre) — noms locaux tels
    qu'apparaissant dans le fichier, sans reformulation."""
    artifacts: list[str] = []
    for prop in ("d3f:spoofs", "d3f:manages"):
        for value in _as_list(node.get(prop)):
            if isinstance(value, dict) and isinstance(value.get("@id"), str):
                artifacts.append(value["@id"])
    return artifacts


def _extract_references(nodes_by_id: dict[str, dict], node: dict) -> list[dict[str, str | None]]:
    """d3f:kb-reference pointe vers des nœuds Reference réellement présents
    dans le graphe, portant d3f:kb-reference-title, d3f:has-link,
    d3f:kb-author, d3f:kb-organization. Aucune reformulation."""
    references = []
    for ref in _as_list(node.get("d3f:kb-reference")):
        if not isinstance(ref, dict) or "@id" not in ref:
            continue
        ref_node = nodes_by_id.get(ref["@id"])
        if ref_node is None:
            continue
        link = ref_node.get("d3f:has-link")
        url = link.get("@value") if isinstance(link, dict) else None
        references.append(
            {
                "title": ref_node.get("d3f:kb-reference-title"),
                "url": url,
                "author": ref_node.get("d3f:kb-author"),
                "organization": ref_node.get("d3f:kb-organization"),
            }
        )
    return references


def _field_evidence(source_file: str, source_sha256: str, entity_id: str, source_property: str, value: str) -> dict:
    """Réf. tâche §10 : structure légère de provenance au niveau du champ —
    evidence_text est recopié verbatim depuis la source, jamais reformulé."""
    return {
        "source_file": source_file,
        "source_sha256": source_sha256,
        "source_entity": entity_id,
        "source_property": source_property,
        "evidence_text": value,
    }


def _build_source_evidence(node: dict, entity_id: str, source_file: str, source_sha256: str) -> list[dict]:
    """Une entrée de provenance par propriété réellement présente et
    porteuse d'information sur le concept (réf. tâche §10)."""
    evidence = []
    label = node.get("rdfs:label")
    if isinstance(label, str):
        evidence.append(_field_evidence(source_file, source_sha256, entity_id, "rdfs:label", label))
    definition = node.get("d3f:definition")
    if isinstance(definition, str):
        evidence.append(_field_evidence(source_file, source_sha256, entity_id, "d3f:definition", definition))
    kb_article = node.get("d3f:kb-article")
    if isinstance(kb_article, str):
        evidence.append(_field_evidence(source_file, source_sha256, entity_id, "d3f:kb-article", kb_article))
    for prop in ("d3f:synonym", "d3f:spoofs", "d3f:manages"):
        for value in _as_list(node.get(prop)):
            text = value.get("@id") if isinstance(value, dict) else value
            if isinstance(text, str):
                evidence.append(_field_evidence(source_file, source_sha256, entity_id, prop, text))
    return evidence


def _short_ids(node_ids: list[str], nodes_by_id: dict[str, dict]) -> list[str]:
    """Convertit une liste d'@id JSON-LD (ex. 'd3f:DecoyObject') vers les
    source_technique_id (d3f:d3fend-id, ex. 'D3-DO') utilisés comme
    identifiant canonique du staging — évite de mélanger deux schémas
    d'identifiants entre source_technique_id et parent_ids/child_ids."""
    return [
        nodes_by_id[node_id]["d3f:d3fend-id"]
        for node_id in node_ids
        if node_id in nodes_by_id and nodes_by_id[node_id].get("d3f:d3fend-id")
    ]


def build_concept_entry(
    node_id: str,
    nodes_by_id: dict[str, dict],
    context: dict,
    branch_id_set: set[str],
    children_map: dict[str, list[str]],
    source_file: str,
    source_sha256: str,
) -> dict:
    """Réf. tâche §8/§9 : construit une entrée de staging pour un concept de
    la branche Deceive. Conserve parent_ids/child_ids/is_leaf sans décider
    quels concepts deviennent des mécanismes déployables d ∈ D
    (OPEN_DECISION 1, non résolue ici)."""
    node = nodes_by_id[node_id]

    # Réf. tâche §8 : la hiérarchie conservée est celle interne à la branche
    # extraite — un parent réel hors branche (ex. d3f:DefensiveTechnique,
    # supertype commun à toutes les techniques D3FEND) n'est pas un
    # descendant de Deceive et n'est donc pas répété comme parent_id ici.
    parent_ids = _short_ids([p for p in _direct_parent_ids(node) if p in branch_id_set], nodes_by_id)
    child_ids = _short_ids(
        [c for c in children_map.get(node_id, []) if c in branch_id_set], nodes_by_id
    )

    return {
        "source_technique_id": node.get("d3f:d3fend-id"),
        "source_uri": _resolve_iri(context, node_id),
        "name": node.get("rdfs:label"),
        "definition": node.get("d3f:definition"),
        "synonyms": _extract_synonyms(node),
        "parent_ids": parent_ids,
        "child_ids": child_ids,
        "is_leaf": len(child_ids) == 0,
        "artifacts": _extract_artifacts(node),
        "kb_article": node.get("d3f:kb-article"),
        "references": _extract_references(nodes_by_id, node),
        "source_evidence": _build_source_evidence(node, node_id, source_file, source_sha256),
    }


# ---------------------------------------------------------------------------
# Construction du seed de concepts (fonction principale, réf. tâche §15)
# ---------------------------------------------------------------------------


def build_d3fend_deception_seed(
    ontology_path: str | Path,
    *,
    release_version: str,
    source_file_label: str = "d3fend.json",
) -> dict:
    """Réf. architecture : "9.1 Pipeline de construction de la KB
    déception" — construit le staging hiérarchique de la branche Deceive à
    partir de l'ontologie D3FEND officielle (chemin fourni explicitement,
    jamais codé en dur).
    """
    ontology_path = Path(ontology_path)
    raw_ontology, source_sha256 = read_json_with_sha256(ontology_path)

    if not isinstance(raw_ontology, dict) or "@graph" not in raw_ontology:
        raise D3fendSeedBuilderError(
            "Le fichier ontologie D3FEND doit être un document JSON-LD avec une clé '@graph'."
        )

    context = raw_ontology.get("@context", {})
    graph = raw_ontology["@graph"]
    if not isinstance(graph, list):
        raise D3fendSeedBuilderError("'@graph' doit être une liste.")

    nodes_by_id = _index_graph_by_id(graph)
    children_map = _build_children_map(nodes_by_id)
    root_ids = find_deceive_root_ids(nodes_by_id)
    branch_ids = collect_branch_ids(root_ids, children_map)
    branch_id_set = set(branch_ids)

    concepts = [
        build_concept_entry(
            node_id, nodes_by_id, context, branch_id_set, children_map, source_file_label, source_sha256
        )
        for node_id in branch_ids
    ]

    return {
        "schema": "d3fend_deception_seed",
        "schema_version": "1.0",
        "release_version": release_version,
        "root_concept": DECEIVE_TACTIC_ID,
        "source_file": source_file_label,
        "source_sha256": source_sha256,
        "concepts": concepts,
    }


# ---------------------------------------------------------------------------
# Mappings D3FEND -> ATT&CK (fonction principale, réf. tâche §11)
# ---------------------------------------------------------------------------


def _local_name_from_iri(context_iri_base: str, full_iri: str) -> str | None:
    """Retrouve le nom local D3FEND (ex. 'DecoyObject') depuis une IRI
    complète du fichier de mappings, à partir du préfixe d3f: réellement
    déclaré dans l'ontologie."""
    if full_iri.startswith(context_iri_base):
        return full_iri[len(context_iri_base):]
    return None


def _mapping_dedup_key(mapping: dict) -> tuple:
    """Réf. durcissement §3 : clé déterministe de déduplication d'une
    relation D3FEND -> ATT&CK. Deux relations ne sont considérées comme le
    même binding QUE si elles coïncident exactement sur ces sept champs —
    un relation_path différent (chemin d'artefacts différent) reste une
    preuve documentaire distincte, jamais fusionnée. Accès défensif
    (`.get`) : utilisable aussi bien sur des mappings construits en interne
    que sur un mapping_seed chargé/corrompu passé à la validation."""
    relation_path = mapping.get("relation_path") or {}
    return (
        mapping.get("d3fend_id"),
        mapping.get("attack_id"),
        relation_path.get("def_artifact_relation"),
        relation_path.get("shared_artifact"),
        relation_path.get("off_artifact_relation"),
        mapping.get("framework"),
        mapping.get("origin"),
    )


def _deduplicate_mappings(mappings: list[dict]) -> list[dict]:
    """Réf. durcissement §4 : supprime les doublons EXACTS (même clé de
    relation), en conservant la première occurrence et l'ordre déterministe
    du fichier source. Ne fusionne jamais deux relation_path différents,
    n'invente aucune relation, n'attribue ni poids ni confidence."""
    seen: set[tuple] = set()
    deduplicated: list[dict] = []
    for mapping in mappings:
        key = _mapping_dedup_key(mapping)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(mapping)
    return deduplicated


def build_d3fend_attack_mapping_seed(
    mappings_path: str | Path,
    deception_seed: dict,
    *,
    release_version: str,
    d3fend_iri_base: str,
    source_file_label: str = "d3fend-full-mappings.json",
) -> dict:
    """Réf. architecture : "9.1 Pipeline de construction de la KB
    déception" — extrait, depuis le fichier officiel de mappings inférés,
    les seules relations dont la technique D3FEND appartient à la branche
    Deceive du seed fourni, et dont le framework offensif est "enterprise"
    (ATT&CK Enterprise, seul périmètre couvert par CLAUDE.md §8 — le fichier
    officiel mélange aussi ATT&CK ICS et MITRE SPARTA, dont les identifiants
    ne suivent pas le format Txxxx).

    Réf. durcissement §2/§3/§4 : un binding SPARQL brut n'est pas une
    relation documentaire unique, qui n'est pas non plus un couple
    D3FEND<->ATT&CK unique (plusieurs chemins d'artefacts peuvent justifier
    le même couple). Trois métriques explicites sont donc conservées :
    raw_binding_count (bindings retenus après filtrage branche/framework),
    unique_relation_count (après déduplication EXACTE, clé
    _mapping_dedup_key), unique_d3fend_attack_pair_count (couples
    (d3fend_id, attack_id) distincts). `mappings` ne contient que les
    relations dédupliquées ; len(mappings) == unique_relation_count.

    Ces relations restent du STAGING ("origin": "d3fend_inferred") : elles
    ne deviennent pas M_{i,d} ici (OPEN_DECISION 4, non résolue).
    """
    mappings_path = Path(mappings_path)
    raw_mappings, source_sha256 = read_json_with_sha256(mappings_path)

    bindings = raw_mappings.get("results", {}).get("bindings")
    if not isinstance(bindings, list):
        raise D3fendSeedBuilderError(
            "Le fichier de mappings D3FEND doit être un résultat SPARQL avec results.bindings."
        )

    known_local_names = {entry["source_uri"].split("#")[-1] for entry in deception_seed["concepts"]}

    filtered_mappings = []
    for binding in bindings:
        def_tech_iri = binding.get("def_tech", {}).get("value", "")
        local_name = _local_name_from_iri(d3fend_iri_base, def_tech_iri)
        if local_name is None or local_name not in known_local_names:
            continue
        if binding.get("framework_key", {}).get("value") != _ATTACK_FRAMEWORK_KEY:
            continue

        attack_id = binding.get("off_tech_id", {}).get("value")
        d3fend_short_id = next(
            (
                entry["source_technique_id"]
                for entry in deception_seed["concepts"]
                if entry["source_uri"].split("#")[-1] == local_name
            ),
            None,
        )

        filtered_mappings.append(
            {
                "d3fend_id": d3fend_short_id,
                "d3fend_local_name": local_name,
                "attack_id": attack_id,
                "attack_technique_label": binding.get("off_tech_label", {}).get("value"),
                "relation_path": {
                    "def_artifact_relation": binding.get("def_artifact_rel_label", {}).get("value"),
                    "shared_artifact": binding.get("def_artifact_label", {}).get("value"),
                    "off_artifact_relation": binding.get("off_artifact_rel_label", {}).get("value"),
                },
                "framework": binding.get("framework_key", {}).get("value"),
                "source": source_file_label,
                "source_sha256": source_sha256,
                "origin": "d3fend_inferred",
            }
        )

    raw_binding_count = len(filtered_mappings)
    deduplicated_mappings = _deduplicate_mappings(filtered_mappings)
    unique_pairs = {(m["d3fend_id"], m["attack_id"]) for m in deduplicated_mappings}

    return {
        "schema": "d3fend_attack_mapping_seed",
        "schema_version": "1.0",
        "release_version": release_version,
        "attack_framework_scope": _ATTACK_FRAMEWORK_KEY,
        "source_file": source_file_label,
        "source_sha256": source_sha256,
        "raw_binding_count": raw_binding_count,
        "unique_relation_count": len(deduplicated_mappings),
        "unique_d3fend_attack_pair_count": len(unique_pairs),
        "mappings": deduplicated_mappings,
    }


# ---------------------------------------------------------------------------
# Validation déterministe du staging (réf. tâche §16)
# ---------------------------------------------------------------------------


def validate_deception_seed(seed: dict) -> None:
    """Réf. tâche §16 : intégrité minimale du seed de concepts."""
    seen_ids: set[str] = set()

    for concept in seed["concepts"]:
        technique_id = concept.get("source_technique_id")
        if not technique_id:
            raise D3fendSeedBuilderError(
                f"Concept sans source_technique_id : '{concept.get('source_uri')}'."
            )
        if technique_id in seen_ids:
            raise D3fendSeedBuilderError(f"source_technique_id dupliqué : '{technique_id}'.")
        seen_ids.add(technique_id)

        if not concept.get("source_evidence"):
            raise D3fendSeedBuilderError(
                f"Concept '{technique_id}' sans provenance (source_evidence) associée."
            )

    # parent_ids/child_ids sont déjà exprimés en source_technique_id (voir
    # _short_ids) : la cohérence se vérifie donc directement contre seen_ids.
    for concept in seed["concepts"]:
        for related_id in concept.get("parent_ids", []) + concept.get("child_ids", []):
            if related_id not in seen_ids:
                raise D3fendSeedBuilderError(
                    f"Concept '{concept['source_technique_id']}' référence un "
                    f"parent/enfant '{related_id}' absent du seed."
                )


def validate_attack_mapping_seed(mapping_seed: dict, deception_seed: dict) -> None:
    """Réf. tâche §16 (phase initiale) / §5 (durcissement) : un mapping ne
    doit jamais référencer une technique D3FEND absente du seed de
    concepts, chaque attack_id doit respecter le format ATT&CK
    Txxxx / Txxxx.xxx, et aucune relation strictement dupliquée (même clé
    _mapping_dedup_key) ne doit subsister — deux relations partageant
    seulement (d3fend_id, attack_id) mais un relation_path différent ne
    sont jamais rejetées."""
    known_ids = {c["source_technique_id"] for c in deception_seed["concepts"]}
    seen_relation_keys: set[tuple] = set()

    for mapping in mapping_seed["mappings"]:
        d3fend_id = mapping.get("d3fend_id")
        if d3fend_id not in known_ids:
            raise D3fendSeedBuilderError(
                f"Le mapping référence une technique D3FEND absente du seed : '{d3fend_id}'."
            )

        attack_id = mapping.get("attack_id")
        if not isinstance(attack_id, str) or not _ATTACK_ID_RE.match(attack_id):
            raise D3fendSeedBuilderError(
                f"Identifiant ATT&CK mal formé dans un mapping D3FEND : '{attack_id}'."
            )

        if not mapping.get("source_sha256"):
            raise D3fendSeedBuilderError("Un mapping D3FEND doit conserver source_sha256.")

        relation_key = _mapping_dedup_key(mapping)
        if relation_key in seen_relation_keys:
            raise D3fendSeedBuilderError(
                f"Relation D3FEND<->ATT&CK strictement dupliquée dans le mapping seed : "
                f"d3fend_id='{d3fend_id}', attack_id='{attack_id}'."
            )
        seen_relation_keys.add(relation_key)


# ---------------------------------------------------------------------------
# Rapport d'extraction (réf. tâche §17)
# ---------------------------------------------------------------------------


def build_seed_report(deception_seed: dict, mapping_seed: dict, manifest_entries: list[dict]) -> dict:
    """Réf. tâche §17 (phase initiale) / §6 (durcissement) : petit rapport
    local sur l'extraction réalisée, pour comparaison ultérieure avec la
    taxonomie officielle MITRE.

    Expose explicitement trois métriques distinctes plutôt qu'un
    "attack_mapping_count" ambigu : un binding SPARQL brut retenu
    (raw_attack_binding_count) n'est pas une relation documentaire unique
    (unique_attack_relation_count), qui n'est pas non plus un couple
    D3FEND<->ATT&CK unique (unique_d3fend_attack_pair_count) — un même
    couple peut être justifié par plusieurs chemins d'artefacts différents,
    donc par plusieurs relations uniques distinctes.
    """
    concepts = deception_seed["concepts"]
    leaves = [c for c in concepts if c["is_leaf"]]
    parents = [c for c in concepts if not c["is_leaf"]]
    return {
        "schema": "d3fend_seed_report",
        "schema_version": "1.0",
        "release_version": deception_seed["release_version"],
        "sources": manifest_entries,
        "concept_count": len(concepts),
        "leaf_count": len(leaves),
        "parent_count": len(parents),
        "raw_attack_binding_count": mapping_seed["raw_binding_count"],
        "unique_attack_relation_count": mapping_seed["unique_relation_count"],
        "unique_d3fend_attack_pair_count": mapping_seed["unique_d3fend_attack_pair_count"],
        "extracted_ids": sorted(c["source_technique_id"] for c in concepts),
        "warnings": [],
    }


# ---------------------------------------------------------------------------
# Manifest de provenance (réf. tâche §5)
# ---------------------------------------------------------------------------


def build_manifest_entry(
    *,
    source_id: str,
    source_name: str,
    release_version: str,
    official_url: str,
    local_filename: str,
    sha256: str,
    source_type: str,
    retrieval_date: str,
    role: str,
) -> dict:
    """Réf. tâche §5 (phase initiale) / §10 (durcissement) : une entrée de
    manifest de provenance, construite uniquement à partir de paramètres
    explicites — aucune URL ni date n'est devinée ou codée en dur ici."""
    return {
        "source_id": source_id,
        "source_name": source_name,
        "provider": "MITRE",
        "release_version": release_version,
        "official_url": official_url,
        "local_filename": local_filename,
        "sha256": sha256,
        "source_type": source_type,
        "retrieval_date": retrieval_date,
        "role": role,
    }


def build_source_manifest(entries: list[dict]) -> dict:
    """Réf. tâche §5 : assemble le manifest versionné des sources
    officielles réellement utilisées."""
    return {"schema": "deception_source_manifest", "schema_version": "1.0", "sources": entries}


# ---------------------------------------------------------------------------
# CLI offline (réf. tâche §15 phase initiale / §7-§12 durcissement) —
# aucun chemin, URL ou date codé en dur
# ---------------------------------------------------------------------------


def _run_cli(argv: list[str] | None = None) -> None:
    """Point d'entrée `python -m tools.deception_kb.d3fend_seed_builder`.

    Régénère de façon cohérente et reproductible, à partir de paramètres
    explicites uniquement (aucune URL ni date codée en dur, réf. durcissement
    §7-§12) :
    - le seed de concepts et le seed de mappings (déjà dédupliqué) ;
    - le manifest de provenance `source_manifest.json` ;
    - le rapport d'extraction, dont `sources` provient exactement du
      manifest généré (jamais une liste vide).

    Les SHA-256 du manifest sont réutilisés depuis ceux déjà calculés par
    `build_d3fend_deception_seed`/`build_d3fend_attack_mapping_seed` (pas de
    seconde lecture des fichiers), avec une vérification de cohérence
    explicite.
    """
    import argparse
    from datetime import date

    parser = argparse.ArgumentParser(
        description=(
            "Construit le staging D3FEND (branche Deceive) et le manifest de "
            "provenance à partir des fichiers officiels."
        )
    )
    parser.add_argument("--ontology", required=True, help="Chemin vers d3fend.json (officiel).")
    parser.add_argument(
        "--mappings", required=True, help="Chemin vers d3fend-full-mappings.json (officiel)."
    )
    parser.add_argument("--release-version", required=True, help="Version D3FEND pinnée (ex. 1.5.0).")
    parser.add_argument(
        "--ontology-url",
        required=True,
        help="URL officielle MITRE de l'ontologie (provenance ; jamais devinée).",
    )
    parser.add_argument(
        "--mappings-url",
        required=True,
        help="URL officielle MITRE du fichier de mappings (provenance ; jamais devinée).",
    )
    parser.add_argument(
        "--retrieval-date",
        required=True,
        help="Date d'acquisition des fichiers officiels, format YYYY-MM-DD.",
    )
    parser.add_argument(
        "--d3fend-iri-base",
        default="http://d3fend.mitre.org/ontologies/d3fend.owl#",
        help="Préfixe IRI d3f: utilisé pour résoudre les identifiants du fichier de mappings.",
    )
    parser.add_argument("--out-dir", required=True, help="Répertoire de sortie du staging.")
    parser.add_argument(
        "--manifest-out", required=True, help="Chemin de sortie de source_manifest.json."
    )
    args = parser.parse_args(argv)

    try:
        date.fromisoformat(args.retrieval_date)
    except ValueError as exc:
        raise D3fendSeedBuilderError(
            f"--retrieval-date doit être au format YYYY-MM-DD (reçu : '{args.retrieval_date}')."
        ) from exc

    deception_seed = build_d3fend_deception_seed(
        args.ontology, release_version=args.release_version
    )
    validate_deception_seed(deception_seed)

    mapping_seed = build_d3fend_attack_mapping_seed(
        args.mappings,
        deception_seed,
        release_version=args.release_version,
        d3fend_iri_base=args.d3fend_iri_base,
    )
    validate_attack_mapping_seed(mapping_seed, deception_seed)

    version = args.release_version

    ontology_entry = build_manifest_entry(
        source_id=f"d3fend-ontology-{version}",
        source_name="D3FEND Ontology",
        release_version=version,
        official_url=args.ontology_url,
        local_filename=str(args.ontology),
        sha256=deception_seed["source_sha256"],
        source_type="json-ld",
        retrieval_date=args.retrieval_date,
        role="ontology",
    )
    mappings_entry = build_manifest_entry(
        source_id=f"d3fend-full-mappings-{version}",
        source_name="D3FEND Full Mappings (inferred relationships)",
        release_version=version,
        official_url=args.mappings_url,
        local_filename=str(args.mappings),
        sha256=mapping_seed["source_sha256"],
        source_type="sparql-results-json",
        retrieval_date=args.retrieval_date,
        role="inferred_mappings",
    )

    # Réf. durcissement §11 : les hashes du manifest doivent provenir des
    # mêmes lectures que le seed/mapping_seed (jamais d'un recalcul séparé),
    # vérifié explicitement pour se prémunir d'une régression future.
    if ontology_entry["sha256"] != deception_seed["source_sha256"]:
        raise D3fendSeedBuilderError(
            "Incohérence de hash entre le manifest et le seed de concepts."
        )
    if mappings_entry["sha256"] != mapping_seed["source_sha256"]:
        raise D3fendSeedBuilderError(
            "Incohérence de hash entre le manifest et le seed de mappings."
        )

    manifest = build_source_manifest([ontology_entry, mappings_entry])
    report = build_seed_report(deception_seed, mapping_seed, manifest_entries=manifest["sources"])

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    seed_path = out_dir / f"d3fend_deception_seed_{version}.json"
    mapping_path = out_dir / f"d3fend_attack_mapping_seed_{version}.json"
    report_path = out_dir / f"d3fend_seed_report_{version}.json"
    manifest_path = Path(args.manifest_out)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    seed_path.write_text(json.dumps(deception_seed, indent=2, ensure_ascii=False), encoding="utf-8")
    mapping_path.write_text(json.dumps(mapping_seed, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Seed: {seed_path}")
    print(f"Mapping seed: {mapping_path}")
    print(f"Report: {report_path}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    _run_cli()
