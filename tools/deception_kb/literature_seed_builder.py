"""
Réf. architecture : "9. Base de connaissances cyberdéception" / "9.1
Pipeline de construction de la KB déception" — contrat technique du PFE
Cyberdéception (CLAUDE.md).

Couche OFFLINE de construction de données (phase 4B.3) : transforme un
registre bibliographique versionné (data/deception/literature/
literature_sources.json), vérifié manuellement contre des sources stables
(DOI/Crossref, dépôts institutionnels, pages officielles d'éditeur), en un
STAGING documentaire — TROISIÈME source structurée de la future KB
cyberdéception, en complément de D3FEND (d3fend_seed_builder.py) et MITRE
Engage (engage_seed_builder.py).

Ce module NE fait PAS partie du runtime SP1/SP2/SP3 : il ne construit PAS
le catalogue final data/deception/deception_catalog.json, ne calcule ni
D_i, ni C_{i,h}, ni Allowed, ni RequirementsSatisfied, ni Relevant,
n'effectue aucun RAG ni appel LLM, et ne produit aucun M_{i,d}. Un passage
scientifique conservé ici est une preuve documentaire vérifiable, PAS une
propriété finale de DeceptionMechanism (interaction_mechanism,
realism_factors, progression_effects, etc.) — cette transformation
sémantique appartient à une phase future non commencée ici (OPEN_DECISION
3 du rapport de tâche).

Différence structurelle avec D3FEND/Engage : il n'existe pas d'API/dump
officiel unique fournissant toutes les publications scientifiques sur la
cyberdéception. Le registre bibliographique (literature_sources.json) est
donc une entrée CURÉE : chaque champ a été vérifié individuellement avant
d'être écrit (DOI vérifié via l'API Crossref, URL d'accès ouvert vérifiée
par requête HTTP réelle) — voir data/deception/literature/
search_protocol.md pour la méthode complète, reproductible. Ce module ne
télécharge rien lui-même : il consomme des fichiers déjà acquis
localement (PDF + extraction texte .txt produite hors-ligne par
`pdftotext`, sans dépendance Python supplémentaire) et le registre, de
façon purement déterministe.

Convention : identifiants de code en anglais, commentaires et docstrings en
français (§25.1).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

# Réf. tâche §12 : taxonomie documentaire minimale (thèmes de couverture du
# corpus), explicitement PAS les métriques finales SP2 (Realism,
# InteractionLikelihood, Effectiveness_prog, DE).
DOCUMENTARY_THEMES = (
    "deception_mechanism", "honeypot", "honeynet", "honeytoken",
    "decoy_asset", "decoy_credential", "decoy_document", "decoy_service",
    "decoy_network", "realism", "attacker_interaction", "engagement",
    "redirection", "delay", "containment", "detection",
    "intelligence_collection", "deployment", "resource_requirements",
    "maintenance", "evaluation",
)

_ACCESS_STATUS_VALUES = ("open_fulltext", "metadata_only", "abstract_only", "unavailable")
_PUBLICATION_TYPE_VALUES = ("journal-article", "conference-paper", "preprint", "thesis")
_MAX_EVIDENCE_TEXT_LENGTH = 500

_REQUIRED_SOURCE_FIELDS = (
    "source_id", "title", "authors", "year", "publication_type", "venue",
    "doi", "official_url", "open_access_url", "retrieval_date",
    "access_status", "relevance_summary", "search_queries",
    "inclusion_reasons", "exclusion_notes", "themes", "raw_file", "sha256",
)


class LiteratureSeedBuilderError(Exception):
    """Erreur de construction ou de validation du staging littérature."""


# ---------------------------------------------------------------------------
# Identifiants stables — réf. tâche §11
# ---------------------------------------------------------------------------


def compute_doi_based_source_id(doi: str) -> str:
    """Réf. tâche §11 : règle déterministe préférée — dérivée du DOI, stable
    tant que le DOI ne change pas. Ne dépend d'aucun métadonnée mutable
    (titre, auteurs)."""
    return "doi_" + doi.strip().lower().replace("/", "_")


_FALLBACK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.]*$")


def is_valid_fallback_source_id(source_id: str) -> bool:
    """Réf. tâche §11 : à défaut de DOI, aucune règle de recomposition
    stricte n'est imposée (les métadonnées disponibles varient trop d'une
    source à l'autre), mais la convention documentée est vérifiée :
    identifiant ASCII, minuscules, sans espace ni caractère spécial —
    jamais un identifiant arbitraire du type PAPER1/PAPER2 (§11)."""
    return bool(_FALLBACK_ID_RE.match(source_id)) and not re.match(r"^paper\d+$", source_id)


# ---------------------------------------------------------------------------
# Utilitaires génériques
# ---------------------------------------------------------------------------


def _sha256_of_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def read_literature_sources_registry(path: str | Path) -> dict:
    """Réf. tâche §10 : charge le registre bibliographique versionné."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != "deception_literature_sources":
        raise LiteratureSeedBuilderError(
            f"Schéma de registre inattendu : '{data.get('schema')}' (attendu "
            "'deception_literature_sources')."
        )
    if not isinstance(data.get("sources"), list):
        raise LiteratureSeedBuilderError("Le registre doit contenir une liste 'sources'.")
    return data


def read_evidence_candidates(path: str | Path) -> list[dict]:
    """Réf. tâche §15 : charge les passages candidats (courts, vérifiés
    manuellement comme réellement présents dans le texte extrait avant
    d'être proposés au builder — la validation finale est refaite ici,
    déterministiquement, par `build_literature_evidence_seed`)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    candidates = data.get("evidence_candidates")
    if not isinstance(candidates, list):
        raise LiteratureSeedBuilderError("Le fichier de passages candidats doit contenir une liste 'evidence_candidates'.")
    return candidates


# ---------------------------------------------------------------------------
# Validation du registre — réf. tâche §9/§10/§19
# ---------------------------------------------------------------------------


def validate_literature_sources_registry(registry: dict) -> None:
    """Réf. tâche §9/§19 : vérifie l'intégrité minimale du registre —
    champs obligatoires présents, source_id/DOI uniques et cohérents,
    access_status/publication_type dans les valeurs documentées, aucune
    donnée de fichier local incohérente avec access_status."""
    sources = registry["sources"]
    seen_ids: set[str] = set()
    seen_dois: set[str] = set()

    for entry in sources:
        missing = [f for f in _REQUIRED_SOURCE_FIELDS if f not in entry]
        if missing:
            raise LiteratureSeedBuilderError(
                f"Source '{entry.get('source_id', '?')}' : champs obligatoires absents : {missing}."
            )

        source_id = entry["source_id"]
        if not source_id:
            raise LiteratureSeedBuilderError("Une source du registre a un source_id vide.")
        if source_id in seen_ids:
            raise LiteratureSeedBuilderError(f"source_id dupliqué : '{source_id}'.")
        seen_ids.add(source_id)

        doi = entry.get("doi")
        if doi is not None:
            doi_norm = doi.strip().lower()
            if doi_norm in seen_dois:
                raise LiteratureSeedBuilderError(
                    f"DOI dupliqué dans le registre : '{doi}' — deux entrées distinctes ne "
                    "doivent jamais partager le même DOI (fusionner manuellement si c'est la "
                    "même publication, réf. tâche §19)."
                )
            seen_dois.add(doi_norm)
            expected_id = compute_doi_based_source_id(doi)
            if source_id != expected_id:
                raise LiteratureSeedBuilderError(
                    f"source_id '{source_id}' incohérent avec la règle dérivée du DOI "
                    f"'{doi}' (attendu '{expected_id}', réf. tâche §11)."
                )
        else:
            if not is_valid_fallback_source_id(source_id):
                raise LiteratureSeedBuilderError(
                    f"source_id de repli invalide (pas de DOI) : '{source_id}' — doit être "
                    "ASCII minuscule, sans espace, et ne jamais suivre le motif interdit "
                    "PAPER<n> (réf. tâche §11)."
                )

        access_status = entry["access_status"]
        if access_status not in _ACCESS_STATUS_VALUES:
            raise LiteratureSeedBuilderError(
                f"Source '{source_id}' : access_status invalide '{access_status}' "
                f"(attendu parmi {_ACCESS_STATUS_VALUES})."
            )

        publication_type = entry["publication_type"]
        if publication_type not in _PUBLICATION_TYPE_VALUES:
            raise LiteratureSeedBuilderError(
                f"Source '{source_id}' : publication_type invalide '{publication_type}' "
                f"(attendu parmi {_PUBLICATION_TYPE_VALUES})."
            )

        raw_file = entry["raw_file"]
        sha256 = entry["sha256"]
        if access_status == "open_fulltext":
            if not raw_file or not sha256:
                raise LiteratureSeedBuilderError(
                    f"Source '{source_id}' : access_status='open_fulltext' exige raw_file "
                    "et sha256 renseignés."
                )
        else:
            if raw_file or sha256:
                raise LiteratureSeedBuilderError(
                    f"Source '{source_id}' : access_status='{access_status}' ne doit pas "
                    "porter de raw_file/sha256 (aucun fichier local associé)."
                )

        unknown_themes = set(entry.get("themes", [])) - set(DOCUMENTARY_THEMES)
        if unknown_themes:
            raise LiteratureSeedBuilderError(
                f"Source '{source_id}' : thèmes inconnus (hors taxonomie documentaire) : "
                f"{sorted(unknown_themes)}."
            )


# ---------------------------------------------------------------------------
# Staging des documents — réf. tâche §14/§15
# ---------------------------------------------------------------------------


def build_literature_document_seed(registry: dict) -> dict:
    """Réf. tâche §14 : transforme le registre validé en staging documentaire,
    en vérifiant pour chaque source à texte ouvert que le fichier local
    déclaré existe réellement et que son SHA-256 correspond exactement à
    celui déclaré dans le registre (aucune substitution silencieuse)."""
    documents = []
    for entry in registry["sources"]:
        source_id = entry["source_id"]
        access_status = entry["access_status"]

        extraction: dict[str, Any] | None = None
        if access_status == "open_fulltext":
            raw_path = Path(entry["raw_file"])
            if not raw_path.exists():
                raise LiteratureSeedBuilderError(
                    f"Source '{source_id}' : access_status='open_fulltext' mais le fichier "
                    f"local déclaré est introuvable : '{raw_path}'."
                )
            actual_sha256 = _sha256_of_file(raw_path)
            if actual_sha256 != entry["sha256"]:
                raise LiteratureSeedBuilderError(
                    f"Source '{source_id}' : SHA-256 du fichier local ('{actual_sha256}') "
                    f"ne correspond pas au SHA-256 déclaré dans le registre "
                    f"('{entry['sha256']}')."
                )

            text_path = raw_path.with_suffix(".txt")
            if not text_path.exists():
                raise LiteratureSeedBuilderError(
                    f"Source '{source_id}' : extraction texte absente ('{text_path}') — "
                    "requise pour toute source déclarée 'open_fulltext'."
                )
            extracted_text = text_path.read_text(encoding="utf-8", errors="replace")
            extraction = {
                "extracted_text_file": str(text_path),
                "extracted_text_sha256": hashlib.sha256(extracted_text.encode("utf-8")).hexdigest(),
                "character_count": len(extracted_text),
                "word_count": len(extracted_text.split()),
            }

        documents.append(
            {
                "source_id": source_id,
                "title": entry["title"],
                "authors": entry["authors"],
                "year": entry["year"],
                "publication_type": entry["publication_type"],
                "venue": entry["venue"],
                "doi": entry["doi"],
                "official_url": entry["official_url"],
                "open_access_url": entry["open_access_url"],
                "retrieval_date": entry["retrieval_date"],
                "access_status": access_status,
                "sha256": entry["sha256"],
                "themes": list(entry["themes"]),
                "relevance_summary": entry["relevance_summary"],
                "search_queries": list(entry["search_queries"]),
                "inclusion_reasons": list(entry["inclusion_reasons"]),
                "exclusion_notes": entry["exclusion_notes"],
                "extraction": extraction,
            }
        )

    return {
        "schema": "literature_document_seed",
        "schema_version": "1.0",
        "selection_method_version": registry["selection_method_version"],
        "documents": documents,
    }


def validate_literature_document_seed(document_seed: dict) -> None:
    """Réf. tâche §20 : intégrité minimale du staging documents — aucun
    doublon de source_id, extraction cohérente avec access_status."""
    seen: set[str] = set()
    for doc in document_seed["documents"]:
        source_id = doc["source_id"]
        if source_id in seen:
            raise LiteratureSeedBuilderError(f"source_id dupliqué dans le staging document : '{source_id}'.")
        seen.add(source_id)
        if doc["access_status"] == "open_fulltext" and doc["extraction"] is None:
            raise LiteratureSeedBuilderError(
                f"Document '{source_id}' : access_status='open_fulltext' sans extraction associée."
            )
        if doc["access_status"] != "open_fulltext" and doc["extraction"] is not None:
            raise LiteratureSeedBuilderError(
                f"Document '{source_id}' : access_status='{doc['access_status']}' ne devrait "
                "porter aucune extraction de texte."
            )


# ---------------------------------------------------------------------------
# Staging des passages courts — réf. tâche §15/§16
# ---------------------------------------------------------------------------


def build_literature_evidence_seed(document_seed: dict, evidence_candidates: list[dict]) -> dict:
    """Réf. tâche §15/§29 : ne conserve un passage que si (a) sa source est
    'open_fulltext' avec une extraction de texte disponible, (b) sa longueur
    respecte la limite documentée, et (c) le passage est retrouvé
    littéralement (après normalisation des espaces/retours à la ligne) dans
    le texte extrait de cette source. Aucun passage n'est jamais accepté
    sur la seule confiance du registre : la preuve est revérifiée ici,
    déterministiquement, contre le texte réellement extrait localement.
    """
    documents_by_id = {d["source_id"]: d for d in document_seed["documents"]}
    text_cache: dict[str, str] = {}

    evidence: list[dict] = []
    seen_keys: set[tuple] = set()
    per_source_counter: dict[str, int] = {}

    for candidate in evidence_candidates:
        source_id = candidate.get("source_id")
        text = candidate.get("text")
        page = candidate.get("page")
        locator = candidate.get("locator")

        if not isinstance(page, int) or page <= 0:
            raise LiteratureSeedBuilderError(
                f"Passage de la source '{source_id}' : 'page' doit être un entier positif."
            )
        if not locator:
            raise LiteratureSeedBuilderError(
                f"Passage de la source '{source_id}' : 'locator' est obligatoire."
            )

        if source_id not in documents_by_id:
            raise LiteratureSeedBuilderError(
                f"Passage référencé pour une source absente du staging document : '{source_id}'."
            )
        document = documents_by_id[source_id]
        if document["access_status"] != "open_fulltext" or document["extraction"] is None:
            raise LiteratureSeedBuilderError(
                f"Passage référencé pour la source '{source_id}', dont l'accès n'est pas "
                "'open_fulltext' — aucun passage ne peut être vérifié sans texte extrait."
            )

        if not isinstance(text, str) or not text.strip():
            raise LiteratureSeedBuilderError(f"Passage vide ou invalide pour la source '{source_id}'.")
        if len(text) > _MAX_EVIDENCE_TEXT_LENGTH:
            raise LiteratureSeedBuilderError(
                f"Passage de la source '{source_id}' dépasse la longueur maximale autorisée "
                f"({len(text)} > {_MAX_EVIDENCE_TEXT_LENGTH} caractères)."
            )

        if source_id not in text_cache:
            text_cache[source_id] = _normalize_whitespace(
                Path(document["extraction"]["extracted_text_file"]).read_text(
                    encoding="utf-8", errors="replace"
                )
            )
        full_text_normalized = text_cache[source_id]
        text_normalized = _normalize_whitespace(text)
        if text_normalized not in full_text_normalized:
            raise LiteratureSeedBuilderError(
                f"Passage introuvable verbatim dans le texte extrait de la source "
                f"'{source_id}' : '{text[:80]}...'."
            )

        key = (source_id, text_normalized)
        if key in seen_keys:
            raise LiteratureSeedBuilderError(
                f"Passage strictement dupliqué pour la source '{source_id}'."
            )
        seen_keys.add(key)

        per_source_counter[source_id] = per_source_counter.get(source_id, 0) + 1
        evidence_id = f"{source_id}__ev{per_source_counter[source_id]:03d}"

        evidence.append(
            {
                "evidence_id": evidence_id,
                "source_id": source_id,
                "page": page,
                "locator": locator,
                "text": text,
                "source_sha256": document["sha256"],
            }
        )

    return {
        "schema": "literature_evidence_seed",
        "schema_version": "1.0",
        "selection_method_version": document_seed["selection_method_version"],
        "evidence": evidence,
    }


def validate_literature_evidence_seed(evidence_seed: dict, document_seed: dict) -> None:
    """Réf. tâche §20 : chaque passage référence une source existante et
    'open_fulltext', et aucun doublon exact ne subsiste."""
    documents_by_id = {d["source_id"]: d for d in document_seed["documents"]}
    seen_ids: set[str] = set()
    for item in evidence_seed["evidence"]:
        evidence_id = item["evidence_id"]
        if evidence_id in seen_ids:
            raise LiteratureSeedBuilderError(f"evidence_id dupliqué : '{evidence_id}'.")
        seen_ids.add(evidence_id)

        source_id = item["source_id"]
        if source_id not in documents_by_id or documents_by_id[source_id]["access_status"] != "open_fulltext":
            raise LiteratureSeedBuilderError(
                f"Passage '{evidence_id}' référence une source invalide ou non 'open_fulltext' : '{source_id}'."
            )
        if len(item["text"]) > _MAX_EVIDENCE_TEXT_LENGTH:
            raise LiteratureSeedBuilderError(f"Passage '{evidence_id}' dépasse la longueur maximale autorisée.")


# ---------------------------------------------------------------------------
# Rapport de couverture — réf. tâche §17
# ---------------------------------------------------------------------------


def build_literature_seed_report(document_seed: dict, evidence_seed: dict) -> dict:
    """Réf. tâche §17 : rapport de couverture calculé uniquement à partir du
    staging déjà construit — aucune valeur n'est devinée, les lacunes de
    couverture thématique sont rapportées explicitement (coverage_gaps),
    jamais comblées par une source inventée."""
    documents = document_seed["documents"]

    peer_reviewed_types = {"journal-article", "conference-paper"}
    peer_reviewed_count = sum(1 for d in documents if d["publication_type"] in peer_reviewed_types)
    open_fulltext_count = sum(1 for d in documents if d["access_status"] == "open_fulltext")
    metadata_only_count = sum(1 for d in documents if d["access_status"] != "open_fulltext")
    sources_with_doi = sum(1 for d in documents if d["doi"])
    sources_with_local_sha256 = sum(1 for d in documents if d["sha256"])

    theme_coverage: dict[str, int] = {theme: 0 for theme in DOCUMENTARY_THEMES}
    for d in documents:
        for theme in d["themes"]:
            theme_coverage[theme] += 1
    coverage_gaps = sorted(theme for theme, count in theme_coverage.items() if count == 0)

    publication_type_counts: dict[str, int] = {}
    for d in documents:
        publication_type_counts[d["publication_type"]] = publication_type_counts.get(d["publication_type"], 0) + 1

    years = [d["year"] for d in documents]
    year_range = {"min": min(years), "max": max(years)} if years else {"min": None, "max": None}

    return {
        "schema": "literature_seed_report",
        "schema_version": "1.0",
        "selection_method_version": document_seed["selection_method_version"],
        "source_count": len(documents),
        "peer_reviewed_count": peer_reviewed_count,
        "open_fulltext_count": open_fulltext_count,
        "metadata_only_count": metadata_only_count,
        "sources_with_doi": sources_with_doi,
        "sources_with_local_sha256": sources_with_local_sha256,
        "evidence_count": len(evidence_seed["evidence"]),
        "theme_coverage": theme_coverage,
        "coverage_gaps": coverage_gaps,
        "year_range": year_range,
        "publication_type_counts": publication_type_counts,
        "warnings": [],
    }


# ---------------------------------------------------------------------------
# CLI offline (réf. tâche §14/§19-analogue) — aucune valeur codée en dur
# ---------------------------------------------------------------------------


def _run_cli(argv: list[str] | None = None) -> None:
    """Point d'entrée `python -m tools.deception_kb.literature_seed_builder`.

    Ne télécharge rien : consomme un registre déjà curé et vérifié
    (literature_sources.json), les fichiers PDF déjà acquis localement, et
    leurs extractions texte déjà produites hors ligne (pdftotext), pour
    produire de façon déterministe le staging document/evidence/rapport.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Construit le staging documentaire de la littérature scientifique de "
            "cyberdéception à partir d'un registre bibliographique déjà vérifié."
        )
    )
    parser.add_argument("--registry", required=True, help="Chemin vers literature_sources.json.")
    parser.add_argument(
        "--evidence-candidates",
        required=True,
        help="Chemin vers le fichier JSON des passages candidats (evidence_candidates).",
    )
    parser.add_argument("--out-dir", required=True, help="Répertoire de sortie du staging.")
    parser.add_argument(
        "--version",
        default="1.0",
        help="Version du staging littérature (suffixe des fichiers de sortie, défaut '1.0').",
    )
    args = parser.parse_args(argv)

    registry = read_literature_sources_registry(args.registry)
    validate_literature_sources_registry(registry)

    document_seed = build_literature_document_seed(registry)
    validate_literature_document_seed(document_seed)

    evidence_candidates = read_evidence_candidates(args.evidence_candidates)
    evidence_seed = build_literature_evidence_seed(document_seed, evidence_candidates)
    validate_literature_evidence_seed(evidence_seed, document_seed)

    report = build_literature_seed_report(document_seed, evidence_seed)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    version = args.version

    document_seed_path = out_dir / f"literature_document_seed_{version}.json"
    evidence_seed_path = out_dir / f"literature_evidence_seed_{version}.json"
    report_path = out_dir / f"literature_seed_report_{version}.json"

    document_seed_path.write_text(json.dumps(document_seed, indent=2, ensure_ascii=False), encoding="utf-8")
    evidence_seed_path.write_text(json.dumps(evidence_seed, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Document seed: {document_seed_path}")
    print(f"Evidence seed: {evidence_seed_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    _run_cli()
