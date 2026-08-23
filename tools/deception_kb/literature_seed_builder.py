"""
Réf. architecture : "9. Base de connaissances cyberdéception" / "9.1
Pipeline de construction de la KB déception" — contrat technique du PFE
Cyberdéception (CLAUDE.md).

Couche OFFLINE de construction de données (phase 4B.3, durcie en 4B.3-H) :
transforme un registre bibliographique versionné (data/deception/
literature/literature_sources.json), vérifié manuellement contre des
sources stables (Crossref, DataCite, DBLP, dépôts institutionnels, pages
officielles d'éditeur/conférence), en un STAGING documentaire —
TROISIÈME source structurée de la future KB cyberdéception, en complément
de D3FEND (d3fend_seed_builder.py) et MITRE Engage (engage_seed_builder.py).

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
d'être écrit — voir data/deception/literature/search_protocol.md pour la
méthode complète, reproductible. Ce module ne télécharge rien lui-même :
il consomme des fichiers déjà acquis localement (PDF + extraction texte
.txt produite hors-ligne par `pdftotext`, séparateurs de page `\\f`
conservés, sans dépendance Python supplémentaire) et le registre, de façon
purement déterministe.

Durcissement (phase 4B.3-H) — réf. tâche :
- distinction explicite publication_doi (DOI de la publication finale) /
  repository_doi (DOI attribué au dépôt/preprint, ex. DataCite arXiv) /
  repository_identifier (ex. "arXiv:1804.06196") — jamais confondus ;
- dates de publication explicites : bibliographic_year (année de
  citation), published_online_year, published_print_year — jamais réduites
  silencieusement à une seule valeur `year` ;
- peer_review_status explicite (peer_reviewed/not_peer_reviewed/unknown),
  jamais déduit implicitement de publication_type ;
- vérification de la PAGE déclarée d'un passage : le texte extrait est
  découpé par page (séparateurs `\\f` de pdftotext) et un passage n'est
  accepté que s'il apparaît sur la page précisément déclarée, pas
  seulement quelque part dans le document.

Durcissement 4B.3-H2 (schéma de staging 1.2) — réf. tâche :
- `extract_page_structure` distingue explicitement une pagination
  **réellement observable** (`pagination_available: true`, séparateurs
  `\\f` présents) d'une pagination **absente** (`pagination_available:
  false`) : un texte sans aucun séparateur de page n'est plus jamais
  assimilé à un document PDF d'une seule page vérifiée — invariant
  structurel : `page_verified: true` implique toujours
  `pagination_available: true` sur sa source (vérifié à la fois à la
  construction et à la validation du staging evidence).

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
_PEER_REVIEW_STATUS_VALUES = ("peer_reviewed", "not_peer_reviewed", "unknown")
_MAX_EVIDENCE_TEXT_LENGTH = 500

_REQUIRED_SOURCE_FIELDS = (
    "source_id", "title", "authors", "bibliographic_year",
    "published_online_year", "published_print_year", "publication_type",
    "venue", "publication_doi", "repository_doi", "repository_identifier",
    "official_url", "open_access_url", "retrieval_date", "access_status",
    "peer_review_status", "peer_review_basis", "relevance_summary",
    "search_queries", "inclusion_reasons", "exclusion_notes",
    "metadata_notes", "metadata_provenance", "themes", "raw_file", "sha256",
)

_REQUIRED_PROVENANCE_FIELDS = ("provider", "url", "retrieval_date", "verified_fields")


class LiteratureSeedBuilderError(Exception):
    """Erreur de construction ou de validation du staging littérature."""


# ---------------------------------------------------------------------------
# Identifiants stables — réf. tâche §6/§11 (phase initiale) durci en §6 (4B.3-H)
# ---------------------------------------------------------------------------


def compute_doi_based_source_id(doi: str) -> str:
    """Réf. tâche §6/§11 : règle déterministe préférée — dérivée du
    **publication_doi** (jamais du repository_doi), stable tant que ce DOI
    ne change pas."""
    return "doi_" + doi.strip().lower().replace("/", "_")


_FALLBACK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.]*$")


def is_valid_fallback_source_id(source_id: str) -> bool:
    """Réf. tâche §11 : à défaut de publication_doi (y compris lorsqu'un
    repository_doi existe — réf. tâche §6, un preprint garde son
    source_id `arxiv_...`, jamais dérivé du repository_doi), la convention
    documentée est vérifiée : identifiant ASCII, minuscules, sans espace ni
    caractère spécial — jamais un identifiant arbitraire du type
    PAPER1/PAPER2 (§11)."""
    return bool(_FALLBACK_ID_RE.match(source_id)) and not re.match(r"^paper\d+$", source_id)


# ---------------------------------------------------------------------------
# Utilitaires génériques
# ---------------------------------------------------------------------------


def _sha256_of_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_page_structure(text: str) -> dict:
    """Réf. tâche §4/§5 (durcissement 4B.3-H2) : reconstruit la structure de
    pages d'un texte extrait par `pdftotext` à partir des séparateurs de
    page `\\f` (form feed) qu'il insère nativement entre chaque page.

    Distingue explicitement une pagination réellement observable d'une
    pagination absente : un texte sans aucun séparateur `\\f` ne doit
    JAMAIS être assimilé à un document PDF d'une seule page vérifiée — un
    document de 20 pages dont les séparateurs ont été perdus à
    l'extraction ne devient pas artificiellement une « page 1 ». Dans ce
    cas, `pagination_available` est `False` et `pages` est vide : aucune
    page ne peut être affirmée, ni vérifiée, à partir de ce texte.

    Réf. correctif micro-durcissement : `pdftotext` termine chaque page,
    y compris la dernière, par un `\\f` — un texte à deux pages produit
    donc littéralement `"P1\\fP2\\f"`. Un split naïf sur `\\f` produirait
    alors un troisième segment vide fantôme (`["P1", "P2", ""]`), qui
    n'est PAS une page réelle. Seul ce segment vide **terminal**, causé
    par le séparateur de fin de document, est retiré ; un segment vide
    **interne** (page réellement vide entre deux séparateurs) est
    conservé tel quel — il n'est jamais supprimé silencieusement.
    """
    if "\x0c" not in text:
        return {"pagination_available": False, "pages": []}
    pages = text.split("\x0c")
    if text.endswith("\x0c"):
        pages = pages[:-1]
    return {"pagination_available": True, "pages": pages}


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
    manuellement comme réellement présents sur la page déclarée du texte
    extrait avant d'être proposés au builder — la validation finale est
    refaite ici, déterministiquement, par `build_literature_evidence_seed`)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    candidates = data.get("evidence_candidates")
    if not isinstance(candidates, list):
        raise LiteratureSeedBuilderError("Le fichier de passages candidats doit contenir une liste 'evidence_candidates'.")
    return candidates


# ---------------------------------------------------------------------------
# Validation du registre — réf. tâche §9/§10/§19/§28
# ---------------------------------------------------------------------------


def _validate_year_field(value: Any, field_name: str, source_id: str) -> None:
    if value is not None and not isinstance(value, int):
        raise LiteratureSeedBuilderError(
            f"Source '{source_id}' : '{field_name}' doit être un entier ou null (reçu : {value!r})."
        )


def _validate_metadata_provenance(entries: Any, source_id: str) -> None:
    if not isinstance(entries, list) or not entries:
        raise LiteratureSeedBuilderError(
            f"Source '{source_id}' : 'metadata_provenance' doit être une liste non vide "
            "(au moins un fournisseur réellement consulté, réf. tâche §7)."
        )
    for prov in entries:
        missing = [f for f in _REQUIRED_PROVENANCE_FIELDS if f not in prov]
        if missing:
            raise LiteratureSeedBuilderError(
                f"Source '{source_id}' : entrée metadata_provenance incomplète, champs "
                f"manquants : {missing}."
            )
        if not isinstance(prov["verified_fields"], list) or not prov["verified_fields"]:
            raise LiteratureSeedBuilderError(
                f"Source '{source_id}' : 'verified_fields' de metadata_provenance doit être "
                "une liste non vide."
            )


def validate_literature_sources_registry(registry: dict) -> None:
    """Réf. tâche §9/§19/§28 : vérifie l'intégrité minimale du registre
    durci — champs obligatoires présents, source_id stable et cohérent
    avec publication_doi, aucun publication_doi ni repository_doi dupliqué
    (chacun dans sa propre catégorie), access_status/publication_type/
    peer_review_status dans les valeurs documentées, provenance des
    métadonnées structurée et non vide, aucune donnée de fichier local
    incohérente avec access_status."""
    sources = registry["sources"]
    seen_ids: set[str] = set()
    seen_publication_dois: set[str] = set()
    seen_repository_dois: set[str] = set()

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

        publication_doi = entry.get("publication_doi")
        repository_doi = entry.get("repository_doi")

        if publication_doi is not None and repository_doi is not None:
            if publication_doi.strip().lower() == repository_doi.strip().lower():
                raise LiteratureSeedBuilderError(
                    f"Source '{source_id}' : publication_doi et repository_doi identiques — "
                    "un DOI de dépôt/preprint ne doit jamais être assimilé à un DOI de "
                    "publication finale sans preuve explicite (réf. tâche §4/§5)."
                )

        if publication_doi is not None:
            doi_norm = publication_doi.strip().lower()
            if doi_norm in seen_publication_dois:
                raise LiteratureSeedBuilderError(
                    f"publication_doi dupliqué dans le registre : '{publication_doi}' — deux "
                    "entrées distinctes ne doivent jamais partager le même publication_doi."
                )
            seen_publication_dois.add(doi_norm)
            expected_id = compute_doi_based_source_id(publication_doi)
            if source_id != expected_id:
                raise LiteratureSeedBuilderError(
                    f"source_id '{source_id}' incohérent avec la règle dérivée du "
                    f"publication_doi '{publication_doi}' (attendu '{expected_id}', réf. "
                    "tâche §6/§11)."
                )
        else:
            if not is_valid_fallback_source_id(source_id):
                raise LiteratureSeedBuilderError(
                    f"source_id de repli invalide (pas de publication_doi) : '{source_id}' — "
                    "doit être ASCII minuscule, sans espace, et ne jamais suivre le motif "
                    "interdit PAPER<n> (réf. tâche §11)."
                )

        if repository_doi is not None:
            repo_doi_norm = repository_doi.strip().lower()
            if repo_doi_norm in seen_repository_dois:
                raise LiteratureSeedBuilderError(
                    f"repository_doi dupliqué dans le registre : '{repository_doi}'."
                )
            seen_repository_dois.add(repo_doi_norm)

        for field_name in ("bibliographic_year", "published_online_year", "published_print_year"):
            _validate_year_field(entry.get(field_name), field_name, source_id)
        if entry.get("bibliographic_year") is None:
            raise LiteratureSeedBuilderError(
                f"Source '{source_id}' : 'bibliographic_year' est obligatoire (jamais null, "
                "réf. tâche §9)."
            )

        peer_review_status = entry["peer_review_status"]
        if peer_review_status not in _PEER_REVIEW_STATUS_VALUES:
            raise LiteratureSeedBuilderError(
                f"Source '{source_id}' : peer_review_status invalide '{peer_review_status}' "
                f"(attendu parmi {_PEER_REVIEW_STATUS_VALUES})."
            )
        if not entry.get("peer_review_basis"):
            raise LiteratureSeedBuilderError(
                f"Source '{source_id}' : 'peer_review_basis' est obligatoire et ne doit pas "
                "être vide (réf. tâche §19)."
            )

        _validate_metadata_provenance(entry.get("metadata_provenance"), source_id)

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
    celui déclaré dans le registre (aucune substitution silencieuse). Le
    texte extrait est également découpé par page (réf. §13) pour permettre
    la vérification page par page des passages courts."""
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
            page_structure = extract_page_structure(extracted_text)
            extraction = {
                "extracted_text_file": str(text_path),
                "extracted_text_sha256": hashlib.sha256(extracted_text.encode("utf-8")).hexdigest(),
                "character_count": len(extracted_text),
                "word_count": len(extracted_text.split()),
                "pagination_available": page_structure["pagination_available"],
                "page_count": len(page_structure["pages"]) if page_structure["pagination_available"] else None,
            }

        documents.append(
            {
                "source_id": source_id,
                "title": entry["title"],
                "authors": entry["authors"],
                "bibliographic_year": entry["bibliographic_year"],
                "published_online_year": entry["published_online_year"],
                "published_print_year": entry["published_print_year"],
                "publication_type": entry["publication_type"],
                "venue": entry["venue"],
                "publication_doi": entry["publication_doi"],
                "repository_doi": entry["repository_doi"],
                "repository_identifier": entry["repository_identifier"],
                "official_url": entry["official_url"],
                "open_access_url": entry["open_access_url"],
                "retrieval_date": entry["retrieval_date"],
                "access_status": access_status,
                "sha256": entry["sha256"],
                "peer_review_status": entry["peer_review_status"],
                "peer_review_basis": entry["peer_review_basis"],
                "themes": list(entry["themes"]),
                "relevance_summary": entry["relevance_summary"],
                "search_queries": list(entry["search_queries"]),
                "inclusion_reasons": list(entry["inclusion_reasons"]),
                "exclusion_notes": entry["exclusion_notes"],
                "metadata_notes": entry["metadata_notes"],
                "metadata_provenance": list(entry["metadata_provenance"]),
                "extraction": extraction,
            }
        )

    return {
        "schema": "literature_document_seed",
        "schema_version": "1.2",
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
# Staging des passages courts — réf. tâche §12/§13/§14/§15/§16
# ---------------------------------------------------------------------------


def build_literature_evidence_seed(document_seed: dict, evidence_candidates: list[dict]) -> dict:
    """Réf. tâche §14/§29 (durcie en 4B.3-H2 §4/§7) : ne conserve un passage
    que si (a) sa source est 'open_fulltext' avec une extraction de texte
    disponible, (b) sa longueur respecte la limite documentée, (c) la
    **pagination de cette extraction est réellement observable**
    (`extraction["pagination_available"] is True` — sinon rejet explicite,
    jamais un repli silencieux sur une « page 1 » non vérifiée), (d) la
    page déclarée existe réellement dans le découpage par page du texte
    extrait, et (e) le passage est retrouvé littéralement (après
    normalisation des espaces/retours à la ligne) **sur cette page
    précise** — pas seulement quelque part dans le document entier. Un
    passage présent ailleurs dans le document mais pas sur la page
    déclarée est rejeté. Tout passage conservé porte donc
    `page_verified: true`, ce qui implique désormais structurellement que
    sa source avait `pagination_available: true` — aucun passage à page
    non vérifiée n'atteint le
    staging final (réf. tâche §16).
    """
    documents_by_id = {d["source_id"]: d for d in document_seed["documents"]}
    pages_cache: dict[str, list[str]] = {}

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

        if not document["extraction"]["pagination_available"]:
            raise LiteratureSeedBuilderError(
                f"Passage de la source '{source_id}' : pagination impossible à vérifier pour "
                "cette extraction (aucun séparateur de page détecté) — aucune page ne peut "
                "être affirmée, réf. tâche §4."
            )

        if source_id not in pages_cache:
            extracted_text = Path(document["extraction"]["extracted_text_file"]).read_text(
                encoding="utf-8", errors="replace"
            )
            pages_cache[source_id] = extract_page_structure(extracted_text)["pages"]
        pages = pages_cache[source_id]

        if page > len(pages):
            raise LiteratureSeedBuilderError(
                f"Passage de la source '{source_id}' : page {page} déclarée mais le document "
                f"extrait n'en compte que {len(pages)}."
            )

        text_normalized = _normalize_whitespace(text)
        declared_page_normalized = _normalize_whitespace(pages[page - 1])
        if text_normalized not in declared_page_normalized:
            full_text_normalized = _normalize_whitespace(" ".join(pages))
            if text_normalized in full_text_normalized:
                raise LiteratureSeedBuilderError(
                    f"Passage de la source '{source_id}' trouvé ailleurs dans le document mais "
                    f"pas sur la page déclarée ({page}) : '{text[:80]}...'."
                )
            raise LiteratureSeedBuilderError(
                f"Passage introuvable verbatim dans le texte extrait de la source "
                f"'{source_id}' (page {page}) : '{text[:80]}...'."
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
                "page_verified": True,
            }
        )

    return {
        "schema": "literature_evidence_seed",
        "schema_version": "1.2",
        "selection_method_version": document_seed["selection_method_version"],
        "evidence": evidence,
    }


def validate_literature_evidence_seed(evidence_seed: dict, document_seed: dict) -> None:
    """Réf. tâche §20/§9 (durcie en 4B.3-H2) : chaque passage référence une
    source existante et 'open_fulltext', porte page_verified=true, aucun
    doublon exact ne subsiste, et — invariant central du durcissement —
    tout passage `page_verified=true` référence obligatoirement un
    document dont `pagination_available=true` : un passage ne peut jamais
    être marqué vérifié si sa source n'a pas de pagination réellement
    observable (réf. tâche §9)."""
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
        if item.get("page_verified") is not True:
            raise LiteratureSeedBuilderError(
                f"Passage '{evidence_id}' : page_verified doit être true (réf. tâche §16)."
            )
        if not documents_by_id[source_id]["extraction"]["pagination_available"]:
            raise LiteratureSeedBuilderError(
                f"Passage '{evidence_id}' : page_verified=true mais la source '{source_id}' "
                "n'a pas de pagination_available=true — invariant violé (réf. tâche §9)."
            )


# ---------------------------------------------------------------------------
# Rapport de couverture — réf. tâche §17/§18/§20/§33
# ---------------------------------------------------------------------------


def build_literature_seed_report(document_seed: dict, evidence_seed: dict) -> dict:
    """Réf. tâche §17/§33 : rapport de couverture calculé uniquement à
    partir du staging déjà construit — aucune valeur n'est devinée, les
    lacunes de couverture thématique sont rapportées explicitement
    (coverage_gaps), jamais comblées par une source inventée. Les
    compteurs peer review et access_status sont calculés depuis des
    champs explicites du registre, jamais déduits implicitement du type de
    publication (réf. tâche §19/§20)."""
    documents = document_seed["documents"]

    peer_reviewed_count = sum(1 for d in documents if d["peer_review_status"] == "peer_reviewed")
    not_peer_reviewed_count = sum(1 for d in documents if d["peer_review_status"] == "not_peer_reviewed")
    unknown_peer_review_count = sum(1 for d in documents if d["peer_review_status"] == "unknown")

    access_status_counts: dict[str, int] = {status: 0 for status in _ACCESS_STATUS_VALUES}
    for d in documents:
        access_status_counts[d["access_status"]] += 1

    sources_with_publication_doi = sum(1 for d in documents if d["publication_doi"])
    sources_with_repository_doi = sum(1 for d in documents if d["repository_doi"])
    sources_with_local_sha256 = sum(1 for d in documents if d["sha256"])

    theme_coverage: dict[str, int] = {theme: 0 for theme in DOCUMENTARY_THEMES}
    for d in documents:
        for theme in d["themes"]:
            theme_coverage[theme] += 1
    coverage_gaps = sorted(theme for theme, count in theme_coverage.items() if count == 0)

    publication_type_counts: dict[str, int] = {}
    for d in documents:
        publication_type_counts[d["publication_type"]] = publication_type_counts.get(d["publication_type"], 0) + 1

    years = [d["bibliographic_year"] for d in documents]
    year_range = {"min": min(years), "max": max(years)} if years else {"min": None, "max": None}

    verified_page_evidence_count = sum(1 for e in evidence_seed["evidence"] if e.get("page_verified") is True)

    open_fulltext_documents = [d for d in documents if d["access_status"] == "open_fulltext"]
    documents_with_verified_pagination_count = sum(
        1 for d in open_fulltext_documents if d["extraction"]["pagination_available"]
    )
    documents_without_verified_pagination_count = sum(
        1 for d in open_fulltext_documents if not d["extraction"]["pagination_available"]
    )

    return {
        "schema": "literature_seed_report",
        "schema_version": "1.2",
        "selection_method_version": document_seed["selection_method_version"],
        "source_count": len(documents),
        "peer_reviewed_count": peer_reviewed_count,
        "not_peer_reviewed_count": not_peer_reviewed_count,
        "unknown_peer_review_count": unknown_peer_review_count,
        "open_fulltext_count": access_status_counts["open_fulltext"],
        "metadata_only_count": access_status_counts["metadata_only"],
        "abstract_only_count": access_status_counts["abstract_only"],
        "unavailable_count": access_status_counts["unavailable"],
        "access_status_counts": access_status_counts,
        "sources_with_publication_doi": sources_with_publication_doi,
        "sources_with_repository_doi": sources_with_repository_doi,
        "sources_with_local_sha256": sources_with_local_sha256,
        "evidence_count": len(evidence_seed["evidence"]),
        "verified_page_evidence_count": verified_page_evidence_count,
        "documents_with_verified_pagination_count": documents_with_verified_pagination_count,
        "documents_without_verified_pagination_count": documents_without_verified_pagination_count,
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
        default="1.2",
        help="Version du staging littérature (suffixe des fichiers de sortie, défaut '1.2').",
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
