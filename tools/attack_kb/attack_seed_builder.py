"""
Réf. architecture : "8. Base de connaissances ATT&CK" (CLAUDE.md §8) —
réf. tâche « renforcer le RAG utilisé par SP2 », §3 « Ajouter MITRE ATT&CK
au corpus RAG ».

Couche OFFLINE de construction de données (mirroir du pattern déjà établi
par `tools/deception_kb/d3fend_seed_builder.py`) : transforme le bundle
STIX officiel `enterprise-attack.json` (jamais versionné, voir
`data/attack/README.md` et `.gitignore`) en un STAGING documentaire RAG
tracé, limité aux techniques ATT&CK réellement RÉFÉRENCÉES par le mapping
attaque-déception déjà versionné (`data/deception/attack_deception_mapping.json`)
— pas les ~700 techniques de la base complète, qui dépasseraient largement
le périmètre utile au RAG de SP2.

Ce module ne fait PAS partie du runtime SP1/SP2/SP3 : il ne calcule ni
D_i, ni C_{i,h}, ni aucune sous-métrique. Il réutilise
`src/knowledge_attack.py::load_attack_knowledge` (déjà testé) pour le
parsing STIX — jamais de second parseur — et les utilitaires génériques de
provenance déjà écrits pour D3FEND (`read_json_with_sha256`,
`build_manifest_entry`, `build_source_manifest`), pour éviter toute
duplication de code déjà testé.

**Techniques revoked/deprecated** : la base ATT&CK réellement téléchargée
évolue dans le temps (renumérotation, dépréciation, révocation) alors que
`attack_deception_mapping.json` a été construit à partir d'une donnée
MITRE Engage figée à une version antérieure. Constat réel (vérifié) : sur
les 271 identifiants ATT&CK référencés par le mapping, 264 sont
"courants" dans le bundle STIX actuellement épinglé, et 7
(`T1053.004`, `T1070.002`, `T1142`, `T1547.011`, `T1562`, `T1562.003`,
`T1574.002`) y sont toujours présents mais désormais marqués
`revoked`/`x_mitre_deprecated` par MITRE. Ce module charge donc la base
avec `include_revoked=True, include_deprecated=True` (texte MITRE réel
dans les deux cas, jamais inventé) et conserve `revoked`/`deprecated`
explicitement dans chaque entrée du seed, pour une traçabilité honnête —
plutôt que de silencieusement amputer le corpus RAG de 7 techniques
réellement référencées par M_{i,d}. Un identifiant du mapping qui resterait
malgré tout absent de la base (ex. renumérotation totale, pas seulement
dépréciation) est reporté explicitement dans `missing_technique_ids` du
rapport — jamais silencieusement ignoré (§25.3).

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

import json
from pathlib import Path

from src.knowledge_attack import AttackKnowledgeBase, AttackTechniqueRecord, load_attack_knowledge
from tools.deception_kb.d3fend_seed_builder import (
    build_manifest_entry,
    build_source_manifest,
    read_json_with_sha256,
)


class AttackSeedBuilderError(Exception):
    """Erreur de construction ou de validation du staging RAG ATT&CK."""


# ---------------------------------------------------------------------------
# Périmètre : techniques réellement référencées par M_{i,d}
# ---------------------------------------------------------------------------


def relevant_technique_ids(mapping: dict) -> list[str]:
    """Réf. tâche §3 : périmètre du corpus RAG ATT&CK = les identifiants
    `attack_id` réellement présents dans les relations M_{i,d} déjà
    versionnées (`data/deception/attack_deception_mapping.json`) — jamais
    la base ATT&CK complète (~700 techniques), dont l'immense majorité
    n'a aucun lien avec le catalogue de cyberdéception."""
    relations = mapping.get("relations")
    if not isinstance(relations, list):
        raise AttackSeedBuilderError("Le mapping doit contenir une liste 'relations'.")
    return sorted({relation["attack_id"] for relation in relations if isinstance(relation, dict) and "attack_id" in relation})


# ---------------------------------------------------------------------------
# Construction des chunks source par technique (§3/§4)
# ---------------------------------------------------------------------------


def _field_evidence(source_property: str, value: str) -> dict:
    """Une entrée de provenance par champ ATT&CK réellement présent —
    `evidence_text` est recopié verbatim depuis le bundle STIX MITRE,
    jamais reformulé (réf. tâche §3 : « ne jamais inventer de texte
    ATT&CK »)."""
    return {"source_property": source_property, "evidence_text": value}


def _build_source_evidence(record: AttackTechniqueRecord) -> list[dict]:
    """Réf. tâche §3 : une technique ATT&CK pertinente peut générer
    PLUSIEURS chunks structurés — un par champ porteur d'information
    (nom, description, une entrée par tactique, plateformes), jamais un
    unique bloc de texte agrégé qui perdrait la granularité par champ."""
    evidence: list[dict] = []
    evidence.append(_field_evidence("name", record.name))
    if record.description:
        evidence.append(_field_evidence("description", record.description))
    for tactic in record.tactics:
        evidence.append(_field_evidence("tactic", tactic))
    if record.platforms:
        evidence.append(_field_evidence("platforms", ", ".join(record.platforms)))
    return evidence


def build_technique_entry(record: AttackTechniqueRecord) -> dict:
    """Réf. tâche §3/§4 : une entrée de staging par technique ATT&CK
    pertinente, avec son statut de cycle de vie MITRE conservé
    explicitement (revoked/deprecated) — jamais masqué (voir docstring de
    module)."""
    return {
        "technique_id": record.technique_id,
        "stix_id": record.stix_id,
        "name": record.name,
        "tactics": list(record.tactics),
        "platforms": list(record.platforms),
        "is_subtechnique": record.is_subtechnique,
        "revoked": record.revoked,
        "deprecated": record.deprecated,
        "version": record.version,
        "external_url": record.external_url,
        "source_evidence": _build_source_evidence(record),
    }


def build_attack_rag_seed(
    kb: AttackKnowledgeBase,
    mapping: dict,
    *,
    release_version: str,
    source_file_label: str = "enterprise-attack.json",
) -> dict:
    """Réf. tâche §3 : construit le staging RAG ATT&CK, limité aux
    techniques référencées par le mapping attaque-déception (§ périmètre
    ci-dessus). `kb` doit avoir été chargée avec
    `include_revoked=True, include_deprecated=True` par l'appelant (voir
    docstring de module) — ce module ne recharge jamais le bundle
    lui-même, pour rester cohérent avec le principe « un seul parseur
    STIX » (`src/knowledge_attack.py`).
    """
    relevant_ids = relevant_technique_ids(mapping)

    techniques: list[dict] = []
    missing_technique_ids: list[str] = []
    for technique_id in relevant_ids:
        record = kb.techniques_by_id.get(technique_id)
        if record is None:
            missing_technique_ids.append(technique_id)
            continue
        techniques.append(build_technique_entry(record))

    return {
        "schema": "attack_rag_seed",
        "schema_version": "1.0",
        "release_version": release_version,
        "source_file": source_file_label,
        "source_sha256": None,  # renseigné par le CLI (réf. read_json_with_sha256, calcul unique)
        "relevance_scope": {
            "criterion": "attack_id present in data/deception/attack_deception_mapping.json relations",
            "relevant_technique_count": len(relevant_ids),
        },
        "missing_technique_ids": missing_technique_ids,
        "techniques": techniques,
    }


# ---------------------------------------------------------------------------
# Validation déterministe du staging (mirroir §16 D3FEND)
# ---------------------------------------------------------------------------


def validate_attack_seed(seed: dict) -> None:
    """Réf. tâche §3 : intégrité minimale du seed ATT&CK — aucun
    technique_id dupliqué, chaque technique porte au moins une preuve de
    provenance."""
    seen_ids: set[str] = set()
    for entry in seed["techniques"]:
        technique_id = entry.get("technique_id")
        if not technique_id:
            raise AttackSeedBuilderError("Entrée de staging ATT&CK sans technique_id.")
        if technique_id in seen_ids:
            raise AttackSeedBuilderError(f"technique_id dupliqué dans le staging ATT&CK : '{technique_id}'.")
        seen_ids.add(technique_id)
        if not entry.get("source_evidence"):
            raise AttackSeedBuilderError(f"Technique '{technique_id}' sans provenance (source_evidence) associée.")


# ---------------------------------------------------------------------------
# Rapport d'extraction (mirroir §17 D3FEND)
# ---------------------------------------------------------------------------


def build_attack_seed_report(seed: dict, manifest_entries: list[dict]) -> dict:
    """Réf. tâche §3 : petit rapport d'extraction, exposant explicitement
    la distinction entre techniques pertinentes (référencées par M_{i,d}),
    techniques effectivement incluses, et techniques manquantes — jamais
    un total ambigu unique."""
    techniques = seed["techniques"]
    revoked = [t for t in techniques if t["revoked"]]
    deprecated = [t for t in techniques if t["deprecated"]]
    return {
        "schema": "attack_rag_seed_report",
        "schema_version": "1.0",
        "release_version": seed["release_version"],
        "sources": manifest_entries,
        "relevant_technique_count": seed["relevance_scope"]["relevant_technique_count"],
        "included_technique_count": len(techniques),
        "missing_technique_count": len(seed["missing_technique_ids"]),
        "missing_technique_ids": seed["missing_technique_ids"],
        "revoked_included_count": len(revoked),
        "deprecated_included_count": len(deprecated),
        "chunk_count": sum(len(t["source_evidence"]) for t in techniques),
        "extracted_ids": sorted(t["technique_id"] for t in techniques),
    }


# ---------------------------------------------------------------------------
# CLI offline — aucun chemin, URL ou date codé en dur
# ---------------------------------------------------------------------------


def _run_cli(argv: list[str] | None = None) -> None:
    """Point d'entrée `python -m tools.attack_kb.attack_seed_builder`.

    Régénère de façon reproductible le staging RAG ATT&CK et le manifest
    de provenance, à partir de paramètres explicites uniquement (aucune
    URL/date codée en dur, mêmes conventions que
    `tools/deception_kb/d3fend_seed_builder.py`)."""
    import argparse
    from datetime import date

    parser = argparse.ArgumentParser(
        description=(
            "Construit le staging RAG ATT&CK (techniques référencées par "
            "M_{i,d}) et le manifest de provenance depuis le bundle STIX officiel."
        )
    )
    parser.add_argument("--raw-bundle", required=True, help="Chemin vers enterprise-attack.json (officiel).")
    parser.add_argument(
        "--mapping-file",
        required=True,
        help="Chemin vers data/deception/attack_deception_mapping.json déjà versionné.",
    )
    parser.add_argument("--release-version", required=True, help="Version ATT&CK Enterprise pinnée (ex. 19.2).")
    parser.add_argument(
        "--source-url",
        required=True,
        help="URL officielle MITRE du bundle STIX (provenance ; jamais devinée).",
    )
    parser.add_argument(
        "--retrieval-date", required=True, help="Date d'acquisition du bundle, format YYYY-MM-DD."
    )
    parser.add_argument("--out-dir", required=True, help="Répertoire de sortie du staging.")
    parser.add_argument("--manifest-out", required=True, help="Chemin de sortie de attack_source_manifest.json.")
    args = parser.parse_args(argv)

    try:
        date.fromisoformat(args.retrieval_date)
    except ValueError as exc:
        raise AttackSeedBuilderError(
            f"--retrieval-date doit être au format YYYY-MM-DD (reçu : '{args.retrieval_date}')."
        ) from exc

    _, source_sha256 = read_json_with_sha256(args.raw_bundle)
    kb = load_attack_knowledge(args.raw_bundle, include_revoked=True, include_deprecated=True)

    with open(args.mapping_file, "r", encoding="utf-8") as file:
        mapping = json.load(file)

    seed = build_attack_rag_seed(kb, mapping, release_version=args.release_version)
    seed["source_sha256"] = source_sha256
    validate_attack_seed(seed)

    manifest_entry = build_manifest_entry(
        source_id=f"enterprise-attack-{args.release_version}",
        source_name="MITRE ATT&CK Enterprise (STIX bundle)",
        release_version=args.release_version,
        official_url=args.source_url,
        local_filename=str(args.raw_bundle),
        sha256=source_sha256,
        source_type="stix-bundle-json",
        retrieval_date=args.retrieval_date,
        role="offensive_knowledge_base",
    )
    manifest = build_source_manifest([manifest_entry])
    report = build_attack_seed_report(seed, manifest_entries=manifest["sources"])

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(args.manifest_out)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    version = args.release_version
    seed_path = out_dir / f"attack_rag_seed_{version}.json"
    report_path = out_dir / f"attack_rag_seed_report_{version}.json"

    seed_path.write_text(json.dumps(seed, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Seed: {seed_path}")
    print(f"Report: {report_path}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    _run_cli()
