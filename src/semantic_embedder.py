"""
Réf. architecture : "9.1 Pipeline de construction de la KB déception"
(étape 7, vectorisation) — module de vectorisation SÉMANTIQUE du RAG,
réf. tâche « remplacer le TF-IDF par un vrai RAG sémantique ».

Encapsule un modèle `sentence-transformers` réel — jamais codé en dur
dans la logique métier : le modèle est choisi par la variable
d'environnement `RAG_EMBEDDING_MODEL`, avec un repli documenté si le
modèle préféré n'est pas disponible localement/téléchargeable.

**Ceci ne remplace PAS le RAG lexical existant** (`src/rag_indexer.py`,
TF-IDF haché) : celui-ci reste disponible comme baseline expérimentale,
comparée explicitement au retrieval sémantique
(`docs/chapter4/outputs/rag_semantic_evaluation.*`).

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
FALLBACK_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
ENV_VAR_NAME = "RAG_EMBEDDING_MODEL"


class SemanticEmbedderError(Exception):
    """Erreur de chargement ou d'exécution du modèle d'embeddings sémantiques."""


class EmbeddingBackend(Protocol):
    """Interface minimale requise par `src.rag_indexer.build_semantic_index`
    et `src.rag_retriever.retrieve_semantic` — permet d'injecter un faux
    embedder déterministe dans les tests, sans jamais appeler
    `sentence-transformers` ni télécharger un modèle pendant `pytest`."""

    model_name: str
    dimension: int

    def encode(self, texts: Sequence[str]) -> np.ndarray: ...


@dataclass
class SentenceTransformerEmbedder:
    """Réf. tâche « choix technique recommandé » : encapsule un modèle
    `sentence-transformers` réel. `model_name` reflète le modèle
    RÉELLEMENT chargé (préféré ou repli) — jamais une valeur supposée."""

    model_name: str
    _model: object
    dimension: int

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        vectors = self._model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vectors, dtype=np.float32)


def _try_load(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise SemanticEmbedderError(
            "Le paquet 'sentence-transformers' n'est pas installé "
            "(dépendance optionnelle du groupe 'rag' de pyproject.toml)."
        ) from exc
    try:
        return SentenceTransformer(model_name)
    except Exception as exc:  # modèle introuvable/pas de réseau/etc.
        raise SemanticEmbedderError(f"Impossible de charger le modèle '{model_name}' : {exc}") from exc


def load_embedder(
    model_name: str | None = None,
    *,
    env: dict[str, str] | None = None,
    fallback_model: str = FALLBACK_EMBEDDING_MODEL,
) -> SentenceTransformerEmbedder:
    """Réf. tâche « configuration RAG_EMBEDDING_MODEL, valeur par défaut
    documentée ». Ordre de résolution :
    1. `model_name` explicite (paramètre) ;
    2. variable d'environnement `RAG_EMBEDDING_MODEL` ;
    3. `DEFAULT_EMBEDDING_MODEL` (`BAAI/bge-small-en-v1.5`) ;
    4. si (3) échoue (indisponible/pas de réseau), repli explicite sur
       `fallback_model` (`sentence-transformers/all-MiniLM-L6-v2`) —
       jamais un modèle arbitraire non documenté.

    Lève `SemanticEmbedderError` si NI le modèle préféré NI le repli ne
    peuvent être chargés — ne fabrique jamais un embedder factice.
    """
    env = env if env is not None else os.environ
    preferred = model_name or env.get(ENV_VAR_NAME) or DEFAULT_EMBEDDING_MODEL

    try:
        model = _try_load(preferred)
        used_model = preferred
    except SemanticEmbedderError as primary_error:
        if preferred == fallback_model:
            raise
        try:
            model = _try_load(fallback_model)
            used_model = fallback_model
        except SemanticEmbedderError as fallback_error:
            raise SemanticEmbedderError(
                f"Ni '{preferred}' ni le repli '{fallback_model}' n'ont pu être chargés. "
                f"Erreur modèle préféré : {primary_error}. Erreur repli : {fallback_error}."
            ) from fallback_error

    dimension = model.get_sentence_embedding_dimension()
    return SentenceTransformerEmbedder(model_name=used_model, _model=model, dimension=dimension)
