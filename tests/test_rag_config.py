"""
Réf. tâche « renforcer le RAG utilisé par SP2 », §8/§9 « Configuration
centralisée du retrieval contextuel ».

Tests unitaires de `src/rag_config.py` (§25.4 : pytest obligatoire).
"""

from src.rag_config import (
    DEFAULT_DIVERSITY_MAX_PER_DOCUMENT,
    DEFAULT_FINAL_TOP_K,
    DEFAULT_RERANKER_MODEL,
    DEFAULT_RETRIEVAL_CANDIDATES,
    resolve_diversity_max_per_document,
    resolve_final_top_k,
    resolve_reranker_model,
    resolve_retrieval_candidates,
)


class TestResolutionOrder:
    """Ordre de résolution : paramètre explicite > variable d'environnement
    > défaut documenté."""

    def test_explicit_value_wins_over_env(self):
        assert resolve_retrieval_candidates(5, env={"RAG_RETRIEVAL_CANDIDATES": "99"}) == 5

    def test_env_value_wins_over_default(self):
        assert resolve_retrieval_candidates(None, env={"RAG_RETRIEVAL_CANDIDATES": "42"}) == 42

    def test_default_used_when_nothing_provided(self):
        assert resolve_retrieval_candidates(None, env={}) == DEFAULT_RETRIEVAL_CANDIDATES

    def test_diversity_max_per_document_default(self):
        assert resolve_diversity_max_per_document(None, env={}) == DEFAULT_DIVERSITY_MAX_PER_DOCUMENT

    def test_final_top_k_default(self):
        assert resolve_final_top_k(None, env={}) == DEFAULT_FINAL_TOP_K

    def test_reranker_model_default(self):
        assert resolve_reranker_model(None, env={}) == DEFAULT_RERANKER_MODEL

    def test_reranker_model_explicit_wins(self):
        assert resolve_reranker_model("custom/model", env={"RAG_RERANKER_MODEL": "other/model"}) == "custom/model"

    def test_reranker_model_env_wins_over_default(self):
        assert resolve_reranker_model(None, env={"RAG_RERANKER_MODEL": "custom/model"}) == "custom/model"


class TestInvalidEnvValue:
    def test_non_integer_env_value_raises(self):
        import pytest

        with pytest.raises(ValueError):
            resolve_retrieval_candidates(None, env={"RAG_RETRIEVAL_CANDIDATES": "not-a-number"})
