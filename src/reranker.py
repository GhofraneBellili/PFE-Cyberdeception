"""
Réf. tâche « renforcer l'architecture et l'implémentation du module RAG
utilisé par SP2 », §9/§10 « Reranking contextuel » — module de reranking
des passages récupérés en première phase (retrieval large,
`src/rag_retriever.py`), avant sélection du top-k final de preuves
(`src/rag_evidence.py`).

**Choix technique (§9)** : un cross-encoder `sentence-transformers`
(`sentence_transformers.CrossEncoder`) — même famille de bibliothèque déjà
utilisée pour les embeddings sémantiques (`src/semantic_embedder.py`),
donc AUCUNE nouvelle dépendance (`sentence-transformers>=3,<4` couvre déjà
`CrossEncoder`). Alternatives comparées avant ce choix : un second appel
au modèle bi-encodeur d'embeddings (`BAAI/bge-small-en-v1.5`) réutilisé en
« similarité contextuelle » — écarté car un bi-encodeur encode requête et
passage INDÉPENDAMMENT (mêmes vecteurs déjà utilisés par le retrieval
sémantique, réf. `src/rag_indexer.py::embed_query_semantic`) : il
n'apporterait aucun signal de reranking réellement nouveau. Un
cross-encoder encode la PAIRE (requête, passage) conjointement, produisant
un score de pertinence dédié — c'est le rôle attendu d'un reranker. Le
LLM d'annotation N'EST JAMAIS utilisé comme reranker (interdiction
explicite §9).

**Modèle par défaut** (`src/rag_config.py::DEFAULT_RERANKER_MODEL`,
`cross-encoder/ms-marco-MiniLM-L-6-v2`) : léger (~80 Mo), compatible CPU,
public, reproductible, entraîné spécifiquement pour le classement
requête/passage (MS MARCO passage ranking) — choix documenté, jamais codé
en dur dans la logique métier : configurable via `RAG_RERANKER_MODEL`.

**Jamais de simulation** (§9) : `CrossEncoderReranker` échoue explicitement
(`RerankerError`) si le modèle ne peut pas être chargé/téléchargé — il ne
retombe JAMAIS silencieusement sur un score inventé. `DeterministicFakeReranker`
existe UNIQUEMENT pour les tests unitaires (déterministe, sans
téléchargement, jamais utilisé dans un chemin d'exécution réel) — voir
`tests/test_reranker.py`.

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.rag_config import resolve_reranker_model
from src.rag_retriever import RetrievalResult


class RerankerError(Exception):
    """Erreur de chargement ou d'exécution du reranker contextuel."""


@dataclass(frozen=True)
class RerankResult:
    """Réf. §10 : un résultat de reranking conservant TOUS les scores
    intermédiaires pour une traçabilité complète (§10, §13) — jamais
    seulement le score final."""

    retrieval_result: RetrievalResult
    reranker_score: float
    final_rank: int


class Reranker(Protocol):
    """Réf. §10 : interface commune à tout reranker (réel ou factice de
    test)."""

    model_name: str

    def rerank(self, query: str, candidates: list[RetrievalResult], *, top_k: int) -> list[RerankResult]: ...


def _rank_by_score(candidates: list[RetrievalResult], scores: list[float], *, top_k: int) -> list[RerankResult]:
    paired = list(zip(candidates, scores))
    paired.sort(key=lambda pair: pair[1], reverse=True)
    return [
        RerankResult(retrieval_result=result, reranker_score=score, final_rank=rank)
        for rank, (result, score) in enumerate(paired[:top_k], start=1)
    ]


@dataclass
class CrossEncoderReranker:
    """Réf. §9/§10 : reranker RÉEL, basé sur un cross-encoder
    `sentence-transformers`. Le modèle est chargé PARESSEUSEMENT (au
    premier `rerank`, jamais à l'import du module) — jamais téléchargé
    pendant `pytest` par défaut (voir `tests/test_reranker.py`, mocks)."""

    model_name: str
    _model: object = None

    @classmethod
    def load(cls, model_name: str | None = None, *, env: dict[str, str] | None = None) -> "CrossEncoderReranker":
        """Réf. §9 : résout le modèle via `RAG_RERANKER_MODEL` (même
        ordre de résolution que `src/semantic_embedder.py::load_embedder`),
        puis le charge réellement — lève `RerankerError` explicite en cas
        d'échec (jamais un repli silencieux vers un score inventé)."""
        resolved_name = resolve_reranker_model(model_name, env=env)
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RerankerError(
                "Le paquet 'sentence-transformers' n'est pas installé "
                "(dépendance optionnelle du groupe 'rag' de pyproject.toml) : "
                "impossible de charger un cross-encoder réel."
            ) from exc
        try:
            model = CrossEncoder(resolved_name)
        except Exception as exc:  # modèle introuvable / pas de réseau / etc.
            raise RerankerError(f"Impossible de charger le reranker '{resolved_name}' : {exc}") from exc
        return cls(model_name=resolved_name, _model=model)

    def rerank(self, query: str, candidates: list[RetrievalResult], *, top_k: int) -> list[RerankResult]:
        if not candidates:
            return []
        if self._model is None:
            raise RerankerError(
                "CrossEncoderReranker n'a pas de modèle chargé : utiliser "
                "CrossEncoderReranker.load(...) plutôt que le constructeur direct."
            )
        pairs = [(query, candidate.chunk.text) for candidate in candidates]
        raw_scores = self._model.predict(pairs)
        scores = [float(score) for score in raw_scores]
        return _rank_by_score(candidates, scores, top_k=top_k)


@dataclass(frozen=True)
class DeterministicFakeReranker:
    """Réf. §9/§28 : double de test déterministe — AUCUN modèle réel,
    AUCUN téléchargement. Score = chevauchement lexical (tokens communs
    requête/passage), suffisant pour tester le CONTRAT du pipeline
    (préservation des chunk_id, des scores intermédiaires, ordre par
    score) sans jamais prétendre reproduire un vrai jugement sémantique de
    cross-encoder. `model_name` porte explicitement le suffixe
    'fake-test-double' pour ne jamais être confondu avec un modèle réel
    dans une sortie/rapport."""

    model_name: str = "deterministic-fake-reranker-test-double"

    @staticmethod
    def _tokens(text: str) -> set[str]:
        import re

        return set(re.findall(r"[a-zA-Z0-9]+", text.lower()))

    def rerank(self, query: str, candidates: list[RetrievalResult], *, top_k: int) -> list[RerankResult]:
        if not candidates:
            return []
        query_tokens = self._tokens(query)
        scores = []
        for candidate in candidates:
            chunk_tokens = self._tokens(candidate.chunk.text)
            overlap = len(query_tokens & chunk_tokens)
            scores.append(float(overlap) / (len(query_tokens) + 1))
        return _rank_by_score(candidates, scores, top_k=top_k)
