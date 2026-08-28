"""
Réf. tâche « renforcer l'architecture et l'implémentation du module RAG
utilisé par SP2 », §8/§9 « Configuration centralisée du retrieval
contextuel » — évite que des constantes numériques (nombre de candidats
récupérés en première phase, modèle de reranking, quotas de diversité,
taille finale du top-k) ne soient dispersées et codées en dur à plusieurs
endroits du code, à l'image du précédent déjà établi par
`RAG_EMBEDDING_MODEL` (`src/semantic_embedder.py`).

Chaque constante est résolue dans cet ordre : valeur explicite passée en
paramètre par l'appelant > variable d'environnement > valeur par défaut
documentée ci-dessous. Aucune de ces valeurs par défaut n'est une donnée
scientifique du chapitre 3 : ce sont des choix d'implémentation du
pipeline de retrieval (§8), documentés comme tels.

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

import os

# Réf. §8 « RETRIEVAL LARGE » : nombre de candidats récupérés PAR MOTEUR
# (lexical et sémantique) avant fusion, pour chacune des trois requêtes
# (Q_realism/Q_interaction/Q_effect) — volontairement plus large que le
# top-k final, pour laisser au reranker un pool suffisant pour réordonner.
ENV_RETRIEVAL_CANDIDATES = "RAG_RETRIEVAL_CANDIDATES"
DEFAULT_RETRIEVAL_CANDIDATES = 20

# Réf. §9 : modèle de reranking contextuel — jamais codé en dur dans
# `src/reranker.py`. Cross-encoder `sentence-transformers` léger,
# compatible CPU, public et reproductible (voir comparatif documenté dans
# `docs/chapter4/FINAL_TECHNICAL_REPORT.md`, section RAG contextuel).
ENV_RERANKER_MODEL = "RAG_RERANKER_MODEL"
DEFAULT_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Réf. §12 « Diversité des preuves » : nombre maximal de chunks retenus
# pour un même document source (document_id) dans le top-k final d'une
# famille — évite un top-k saturé par un seul document quand une preuve
# complémentaire existe ailleurs, sans jamais devenir un quota rigide par
# type de source (§12 : « ne jamais forcer un quota artificiel »).
ENV_DIVERSITY_MAX_PER_DOCUMENT = "RAG_DIVERSITY_MAX_PER_DOCUMENT"
DEFAULT_DIVERSITY_MAX_PER_DOCUMENT = 2

# Réf. §13 : taille finale du top-k de preuves conservées PAR FAMILLE dans
# le `CandidateEvidenceBundle`, après retrieval large + reranking +
# diversification.
ENV_FINAL_TOP_K = "RAG_FINAL_TOP_K"
DEFAULT_FINAL_TOP_K = 5


def _resolve_int(explicit: int | None, env_var: str, default: int, *, env: dict[str, str] | None = None) -> int:
    if explicit is not None:
        return explicit
    env = env if env is not None else os.environ
    raw = env.get(env_var)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{env_var} doit être un entier (valeur reçue : '{raw}').") from exc


def resolve_retrieval_candidates(explicit: int | None = None, *, env: dict[str, str] | None = None) -> int:
    """Réf. §8 : résout `RAG_RETRIEVAL_CANDIDATES` (paramètre explicite >
    variable d'environnement > défaut documenté)."""
    return _resolve_int(explicit, ENV_RETRIEVAL_CANDIDATES, DEFAULT_RETRIEVAL_CANDIDATES, env=env)


def resolve_diversity_max_per_document(explicit: int | None = None, *, env: dict[str, str] | None = None) -> int:
    """Réf. §12 : résout `RAG_DIVERSITY_MAX_PER_DOCUMENT`."""
    return _resolve_int(explicit, ENV_DIVERSITY_MAX_PER_DOCUMENT, DEFAULT_DIVERSITY_MAX_PER_DOCUMENT, env=env)


def resolve_final_top_k(explicit: int | None = None, *, env: dict[str, str] | None = None) -> int:
    """Réf. §13 : résout `RAG_FINAL_TOP_K`."""
    return _resolve_int(explicit, ENV_FINAL_TOP_K, DEFAULT_FINAL_TOP_K, env=env)


def resolve_reranker_model(explicit: str | None = None, *, env: dict[str, str] | None = None) -> str:
    """Réf. §9 : résout `RAG_RERANKER_MODEL` (paramètre explicite >
    variable d'environnement > défaut documenté)."""
    if explicit is not None:
        return explicit
    env = env if env is not None else os.environ
    return env.get(ENV_RERANKER_MODEL) or DEFAULT_RERANKER_MODEL
