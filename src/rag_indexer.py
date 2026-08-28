"""
Réf. architecture : "9.1 Pipeline de construction de la KB déception"
(étapes 2-4-7) et "26. Modules recommandés — rag_indexer.py" (CLAUDE.md
§9.1, §26).

Ingestion des documents déjà versionnés hors ligne
(`tools/deception_kb/*`, `data/deception/staging/*.json`), découpage en
chunks tracés (chunk_id, source_id, source_type, document_id,
page/locator, text, hash, metadata), calcul de vecteurs et construction
d'un index (§9.1 étapes 2, 3, 7).

**Deux moteurs de vectorisation, réf. tâche « remplacer le TF-IDF par un
vrai RAG sémantique » :**

1. **`RagIndex` / `embed_text` / `build_index` (TF-IDF haché, ce
   module)** — désormais une **baseline lexicale expérimentale**
   (§9.1), comparée explicitement au retrieval sémantique
   (`docs/chapter4/outputs/rag_semantic_evaluation.*`). Reste
   entièrement fonctionnelle et testée : déterministe, sans dépendance,
   utile en test unitaire et comme point de comparaison quantitatif.
   Ce n'est PAS un embedding sémantique au sens d'un modèle de langage.
2. **`SemanticRagIndex` / `build_semantic_index` (ce module) — moteur
   PRINCIPAL** du RAG à partir de cette tâche : vecteurs produits par un
   modèle `sentence-transformers` réel (`src/semantic_embedder.py`,
   configurable via `RAG_EMBEDDING_MODEL`), indexés par
   `src/vector_index.py` (FAISS si disponible, repli NumPy sinon).

Les deux index restent compatibles avec les mêmes `Chunk` et le même
`RetrievalResult`/`DeceptionEvidence` en aval (`src/rag_retriever.py`).

Ce module n'appelle jamais de LLM. Le chargement d'un modèle sémantique
(`build_semantic_index`) nécessite le modèle déjà téléchargé/en cache
localement — jamais appelé pendant `pytest` (tests unitaires mockés, voir
`tests/test_rag_indexer.py`).

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Literal

SourceType = Literal["attack", "d3fend", "engage", "literature"]

EMBEDDING_DIMENSION = 256

_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")

# Réf. choix technique simple (voir docstring de module) : liste fermée et
# standard de mots-outils anglais très fréquents, sans charge sémantique
# distinctive pour la recherche documentaire — leur exclusion évite qu'ils
# ne diluent le signal des vecteurs hachés sur un petit corpus.
_STOPWORDS = frozenset(
    {
        "a", "an", "the", "to", "of", "in", "on", "and", "or", "is", "are",
        "be", "this", "that", "for", "with", "as", "by", "it", "its", "from",
        "at", "was", "were", "has", "have", "had", "not", "but", "if", "than",
        "then", "so", "such", "these", "those", "their", "which", "who",
        "whom", "will", "would", "can", "could", "should", "must", "may",
        "might", "do", "does", "did", "into", "about", "when", "while",
        "any", "all", "each", "other", "more", "most", "some", "no", "also",
    }
)


class RagIndexerError(Exception):
    """Erreur de construction des chunks ou de l'index RAG."""


@dataclass(frozen=True)
class Chunk:
    """Réf. §9.1/§26 — un passage documentaire tracé, prêt à être indexé.

    `text_hash` permet de détecter une divergence entre le chunk et le
    document source (intégrité), à l'image de `source_sha256` déjà utilisé
    par `tools/deception_kb/*`.
    """

    chunk_id: str
    source_id: str
    source_type: SourceType
    document_id: str
    locator: str
    text: str
    text_hash: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RagIndex:
    """Réf. §9.1 étape 7 — index en mémoire : chunks, vecteurs et
    statistiques du corpus (document_frequencies/num_documents) nécessaires
    pour encoder une requête avec les mêmes poids IDF (`embed_query`)."""

    chunks: tuple[Chunk, ...]
    embeddings: dict[str, tuple[float, ...]]
    dimension: int
    document_frequencies: dict[str, int]
    num_documents: int

    def __len__(self) -> int:
        return len(self.chunks)


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _make_chunk(*, chunk_id, source_id, source_type, document_id, locator, text, metadata) -> Chunk | None:
    """Réf. §25.3 : un texte vide n'est jamais indexé comme un chunk
    silencieusement fabriqué — il est simplement omis (pas d'exception,
    car un champ optionnel vide côté source documentaire est légitime)."""
    normalized = text.strip() if text else ""
    if not normalized:
        return None
    return Chunk(
        chunk_id=chunk_id,
        source_id=source_id,
        source_type=source_type,
        document_id=document_id,
        locator=locator,
        text=normalized,
        text_hash=_text_hash(normalized),
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Ingestion par source — réf. §9.1 étape 1/2 (D3FEND / Engage / littérature)
# ---------------------------------------------------------------------------


def load_d3fend_chunks(seed: dict) -> list[Chunk]:
    """Réf. §9.1 : un chunk par entrée `source_evidence` d'un concept
    D3FEND déjà tracé (`tools/deception_kb/d3fend_seed_builder.py`,
    `data/deception/staging/d3fend_deception_seed_*.json`).

    `mechanism_ids`/`artifact_types` (réf. tâche RAG contextuel SP2, §4) :
    `concept_id` (`d3f:d3fend-id`, ex. "D3-DUC") EST l'identifiant utilisé
    tel quel comme `mechanism_id` par `tools/deception_kb/catalog_builder.py`
    pour les mécanismes d'origine D3FEND — association source-native,
    jamais dérivée par une règle heuristique."""
    chunks: list[Chunk] = []
    for concept in seed.get("concepts", []):
        concept_id = concept["source_technique_id"]
        for index, evidence in enumerate(concept.get("source_evidence", [])):
            chunk = _make_chunk(
                chunk_id=f"d3fend:{concept_id}:{index}",
                source_id=evidence.get("source_file", concept_id),
                source_type="d3fend",
                document_id=concept_id,
                locator=evidence.get("source_property", "unknown"),
                text=evidence.get("evidence_text", ""),
                metadata={
                    "concept_name": concept.get("name"),
                    "source_entity": evidence.get("source_entity"),
                    "source_sha256": evidence.get("source_sha256"),
                    "mechanism_ids": [concept_id],
                    "artifact_types": concept.get("artifacts", []),
                },
            )
            if chunk is not None:
                chunks.append(chunk)
    return chunks


def load_engage_chunks(seed: dict) -> list[Chunk]:
    """Réf. §9.1 : un chunk par `description`/`long_description` d'une
    activité MITRE Engage déjà tracée
    (`tools/deception_kb/engage_seed_builder.py`,
    `data/deception/staging/engage_activity_seed_*.json`).

    `mechanism_ids` (réf. tâche RAG contextuel SP2, §4) : `activity_id`
    (ex. "EAC0014") EST l'identifiant utilisé tel quel comme `mechanism_id`
    par `tools/deception_kb/catalog_builder.py` pour les mécanismes
    d'origine Engage — association source-native."""
    chunks: list[Chunk] = []
    for activity in seed.get("activities", []):
        activity_id = activity["activity_id"]
        for locator in ("description", "long_description"):
            text = activity.get(locator, "")
            if locator == "long_description" and text == activity.get("description"):
                continue
            chunk = _make_chunk(
                chunk_id=f"engage:{activity_id}:{locator}",
                source_id=activity_id,
                source_type="engage",
                document_id=activity_id,
                locator=locator,
                text=text,
                metadata={
                    "name": activity.get("name"),
                    "detail_type": activity.get("detail_type"),
                    "mechanism_ids": [activity_id],
                },
            )
            if chunk is not None:
                chunks.append(chunk)
    return chunks


def load_attack_chunks(seed: dict) -> list[Chunk]:
    """Réf. tâche « renforcer le RAG utilisé par SP2 », §3/§4 : un chunk
    par entrée `source_evidence` d'une technique ATT&CK déjà tracée
    (`tools/attack_kb/attack_seed_builder.py`,
    `data/attack/staging/attack_rag_seed_*.json`) — texte MITRE ATT&CK
    verbatim (name/description/tactic/platforms), jamais reformulé.

    Le seed est déjà limité aux techniques réellement référencées par
    M_{i,d} (réf. `tools.attack_kb.attack_seed_builder.relevant_technique_ids`) :
    ce chargeur ne refiltre rien, il se contente de traduire le staging en
    `Chunk` indexables. `revoked`/`deprecated` sont conservés explicitement
    dans les métadonnées — jamais masqués (voir docstring de module de
    `tools/attack_kb/attack_seed_builder.py`)."""
    chunks: list[Chunk] = []
    for technique in seed.get("techniques", []):
        technique_id = technique["technique_id"]
        for index, evidence in enumerate(technique.get("source_evidence", [])):
            chunk = _make_chunk(
                chunk_id=f"attack:{technique_id}:{index}",
                source_id=technique_id,
                source_type="attack",
                document_id=technique_id,
                locator=evidence.get("source_property", "unknown"),
                text=evidence.get("evidence_text", ""),
                metadata={
                    "attack_technique_ids": [technique_id],
                    "tactics": technique.get("tactics", []),
                    "platforms": technique.get("platforms", []),
                    "version": technique.get("version"),
                    "revoked": technique.get("revoked", False),
                    "deprecated": technique.get("deprecated", False),
                    "external_url": technique.get("external_url"),
                    "source_sha256": seed.get("source_sha256"),
                },
            )
            if chunk is not None:
                chunks.append(chunk)
    return chunks


def load_literature_chunks(seed: dict) -> list[Chunk]:
    """Réf. §9.1 : un chunk par passage scientifique déjà vérifié page par
    page (`tools/deception_kb/literature_seed_builder.py`,
    `data/deception/staging/literature_evidence_seed_*.json`) — le
    schéma source porte déjà `evidence_id`/`source_id`/`page`/`locator`/
    `text`, directement réutilisables."""
    chunks: list[Chunk] = []
    for evidence in seed.get("evidence", []):
        chunk = _make_chunk(
            chunk_id=evidence["evidence_id"],
            source_id=evidence["source_id"],
            source_type="literature",
            document_id=evidence["source_id"],
            locator=f"page_{evidence.get('page')}_{evidence.get('locator')}",
            text=evidence.get("text", ""),
            metadata={
                "source_sha256": evidence.get("source_sha256"),
                "page_verified": evidence.get("page_verified"),
            },
        )
        if chunk is not None:
            chunks.append(chunk)
    return chunks


# ---------------------------------------------------------------------------
# Vecteurs déterministes TF-IDF + hashing trick — réf. §9.1 étape 7
# ---------------------------------------------------------------------------


def tokenize(text: str) -> list[str]:
    """Découpage simple en tokens alphanumériques, minuscules, mots-outils
    anglais exclus (`_STOPWORDS`, liste fermée standard)."""
    return [token for token in _TOKEN_PATTERN.findall(text.lower()) if token not in _STOPWORDS]


def _hash_bucket(token: str, dimension: int) -> int:
    return int(hashlib.blake2b(token.encode("utf-8"), digest_size=8).hexdigest(), 16) % dimension


def compute_document_frequencies(chunks: list[Chunk]) -> dict[str, int]:
    """Réf. §9.1 : nombre de chunks du corpus dans lesquels chaque token
    apparaît au moins une fois (df), base du poids IDF."""
    document_frequencies: dict[str, int] = {}
    for chunk in chunks:
        for token in set(tokenize(chunk.text)):
            document_frequencies[token] = document_frequencies.get(token, 0) + 1
    return document_frequencies


def _idf(token: str, document_frequencies: dict[str, int], num_documents: int) -> float:
    """IDF lissé (`+1` évite toute division par zéro, y compris pour un
    corpus vide). Un token jamais vu dans le corpus (absent de
    `document_frequencies`, ex. terme d'une requête hors vocabulaire) est
    traité comme maximalement rare (df=0) — repli standard en recherche
    d'information, pas une valeur inventée arbitrairement."""
    df = document_frequencies.get(token, 0)
    return math.log((1 + num_documents) / (1 + df)) + 1.0


def embed_text(
    text: str,
    *,
    document_frequencies: dict[str, int],
    num_documents: int,
    dimension: int = EMBEDDING_DIMENSION,
) -> tuple[float, ...]:
    """Vecteur déterministe TF-IDF avec « hashing trick » : chaque token
    est haché (blake2b) vers un indice de `[0, dimension)`, pondéré par son
    IDF sur le corpus indexé, puis le vecteur est normalisé (norme L2 = 1)
    pour une similarité cosinus stable."""
    if dimension <= 0:
        raise RagIndexerError(f"dimension doit être positive (valeur reçue : {dimension}).")
    vector = [0.0] * dimension
    for token in tokenize(text):
        weight = _idf(token, document_frequencies, num_documents)
        vector[_hash_bucket(token, dimension)] += weight
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return tuple(vector)
    return tuple(value / norm for value in vector)


def build_index(chunks: list[Chunk], *, dimension: int = EMBEDDING_DIMENSION) -> RagIndex:
    """Réf. §9.1 étape 7 : construit l'index en mémoire (chunks, vecteurs
    TF-IDF hachés, statistiques du corpus). Lève une erreur explicite en
    cas de `chunk_id` dupliqué (aucune collision silencieuse acceptée)."""
    seen_ids: set[str] = set()
    for chunk in chunks:
        if chunk.chunk_id in seen_ids:
            raise RagIndexerError(f"chunk_id dupliqué : '{chunk.chunk_id}'.")
        seen_ids.add(chunk.chunk_id)

    document_frequencies = compute_document_frequencies(chunks)
    num_documents = len(chunks)
    embeddings = {
        chunk.chunk_id: embed_text(
            chunk.text, document_frequencies=document_frequencies, num_documents=num_documents, dimension=dimension
        )
        for chunk in chunks
    }
    return RagIndex(
        chunks=tuple(chunks),
        embeddings=embeddings,
        dimension=dimension,
        document_frequencies=document_frequencies,
        num_documents=num_documents,
    )


def embed_query(index: RagIndex, text: str) -> tuple[float, ...]:
    """Réf. §9.1 : encode une requête avec les MÊMES poids IDF que le
    corpus indexé (`index.document_frequencies`/`index.num_documents`),
    condition nécessaire pour que la similarité cosinus avec les vecteurs
    de chunks soit comparable."""
    return embed_text(
        text,
        document_frequencies=index.document_frequencies,
        num_documents=index.num_documents,
        dimension=index.dimension,
    )


# ---------------------------------------------------------------------------
# Index sémantique — moteur RAG principal, réf. tâche « RAG sémantique »
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SemanticRagIndex:
    """Réf. §9.1 étape 7 — index sémantique : chunks + vecteurs
    `sentence-transformers` (normalisés L2) + index vectoriel
    (`src/vector_index.py`, FAISS ou repli NumPy). `embedding_model`
    reflète le modèle RÉELLEMENT utilisé (préféré ou repli, jamais
    supposé) — traçabilité de la requête (§28) : `embed_query` doit
    utiliser le même modèle."""

    chunks: tuple[Chunk, ...]
    vectors: "object"  # numpy.ndarray (n, d) — typé Any pour ne pas imposer numpy en import top-niveau des consommateurs légers
    vector_index: object
    backend: str  # "faiss" ou "numpy"
    embedding_model: str
    dimension: int

    def __len__(self) -> int:
        return len(self.chunks)


def build_semantic_index(chunks: list[Chunk], *, embedder: "EmbeddingBackend | None" = None) -> SemanticRagIndex:
    """Réf. tâche « nouvelle chaîne : documents -> chunks tracés ->
    embeddings sémantiques -> normalisation -> index vectoriel ». Encode
    tous les chunks avec `embedder` (`src.semantic_embedder.load_embedder`
    par défaut si non fourni — un modèle réel, jamais un faux vecteur),
    construit l'index vectoriel (`src.vector_index.build_vector_index`).

    `embedder` est injectable : les tests unitaires passent un embedder
    déterministe factice (dimension fixe, pas de téléchargement de
    modèle) — jamais `sentence-transformers` pendant `pytest` (réf. tâche
    §18, « aucune dépendance ne doit télécharger un modèle pendant la
    CI »)."""
    import numpy as np

    from src.semantic_embedder import load_embedder
    from src.vector_index import build_vector_index

    seen_ids: set[str] = set()
    for chunk in chunks:
        if chunk.chunk_id in seen_ids:
            raise RagIndexerError(f"chunk_id dupliqué : '{chunk.chunk_id}'.")
        seen_ids.add(chunk.chunk_id)

    if embedder is None:
        embedder = load_embedder()

    if not chunks:
        vectors = np.zeros((0, embedder.dimension), dtype=np.float32)
    else:
        vectors = embedder.encode([chunk.text for chunk in chunks])
        if vectors.shape[1] != embedder.dimension:
            raise RagIndexerError(
                f"Dimension d'embedding incohérente : embedder.dimension={embedder.dimension}, "
                f"vecteurs produits de dimension {vectors.shape[1]}."
            )

    vector_index, backend = build_vector_index(vectors)
    return SemanticRagIndex(
        chunks=tuple(chunks),
        vectors=vectors,
        vector_index=vector_index,
        backend=backend,
        embedding_model=embedder.model_name,
        dimension=embedder.dimension,
    )


def embed_query_semantic(index: SemanticRagIndex, text: str, *, embedder: "EmbeddingBackend | None" = None):
    """Réf. §28 (traçabilité) : encode une requête avec le MÊME modèle que
    celui utilisé pour construire l'index (`index.embedding_model`) — un
    `embedder` explicite doit porter le même `model_name`, sinon
    `RagIndexerError` (jamais une comparaison silencieusement incohérente
    entre deux espaces vectoriels différents)."""
    from src.semantic_embedder import load_embedder

    if embedder is None:
        embedder = load_embedder(index.embedding_model)
    if embedder.model_name != index.embedding_model:
        raise RagIndexerError(
            f"Modèle d'embedding incohérent : index construit avec '{index.embedding_model}', "
            f"requête encodée avec '{embedder.model_name}'."
        )
    return embedder.encode([text])[0]
