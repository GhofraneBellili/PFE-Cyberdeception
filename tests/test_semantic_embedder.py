"""
Réf. architecture : CLAUDE.md §9.1/§26 — contrat technique du PFE
Cyberdéception, réf. tâche « remplacer le TF-IDF par un vrai RAG
sémantique ».

Tests unitaires de src/semantic_embedder.py (§25.4 : pytest obligatoire).

Aucun test ici ne télécharge ni ne charge un vrai modèle
`sentence-transformers` (réf. tâche §18 : « les tests ne doivent pas
télécharger un modèle depuis Internet pendant la CI ») : `_try_load` est
systématiquement simulé (monkeypatch) avec un faux modèle déterministe.
Le smoke test d'exécution réelle est fait hors pytest par
`examples/rag_example.py` / `examples/rag_semantic_evaluation.py`.
"""

from __future__ import annotations

import numpy as np
import pytest

from src import semantic_embedder as se


class FakeSentenceTransformer:
    """Simule l'API minimale de `SentenceTransformer` utilisée par
    `SentenceTransformerEmbedder.encode`."""

    def __init__(self, dimension: int = 4):
        self._dimension = dimension

    def get_sentence_embedding_dimension(self) -> int:
        return self._dimension

    def encode(self, texts, normalize_embeddings=True, show_progress_bar=False):
        vectors = []
        for text in texts:
            seed = sum(ord(c) for c in text) or 1
            rng = np.random.default_rng(seed)
            vector = rng.normal(size=self._dimension)
            if normalize_embeddings:
                norm = np.linalg.norm(vector)
                vector = vector / norm if norm > 0 else vector
            vectors.append(vector)
        return np.asarray(vectors, dtype=np.float32)


class TestLoadEmbedderResolutionOrder:
    def test_explicit_param_wins_over_env_and_default(self, monkeypatch):
        loaded_with = []

        def fake_try_load(model_name):
            loaded_with.append(model_name)
            return FakeSentenceTransformer()

        monkeypatch.setattr(se, "_try_load", fake_try_load)
        embedder = se.load_embedder("explicit-model", env={se.ENV_VAR_NAME: "env-model"})
        assert loaded_with == ["explicit-model"]
        assert embedder.model_name == "explicit-model"

    def test_env_var_wins_over_default_when_no_explicit_param(self, monkeypatch):
        loaded_with = []

        def fake_try_load(model_name):
            loaded_with.append(model_name)
            return FakeSentenceTransformer()

        monkeypatch.setattr(se, "_try_load", fake_try_load)
        embedder = se.load_embedder(env={se.ENV_VAR_NAME: "env-model"})
        assert loaded_with == ["env-model"]
        assert embedder.model_name == "env-model"

    def test_default_model_used_when_no_param_and_no_env(self, monkeypatch):
        loaded_with = []

        def fake_try_load(model_name):
            loaded_with.append(model_name)
            return FakeSentenceTransformer()

        monkeypatch.setattr(se, "_try_load", fake_try_load)
        embedder = se.load_embedder(env={})
        assert loaded_with == [se.DEFAULT_EMBEDDING_MODEL]
        assert embedder.model_name == se.DEFAULT_EMBEDDING_MODEL


class TestLoadEmbedderFallback:
    def test_falls_back_when_preferred_model_fails(self, monkeypatch):
        loaded_with = []

        def fake_try_load(model_name):
            loaded_with.append(model_name)
            if model_name == se.DEFAULT_EMBEDDING_MODEL:
                raise se.SemanticEmbedderError("modèle préféré indisponible (simulé)")
            return FakeSentenceTransformer()

        monkeypatch.setattr(se, "_try_load", fake_try_load)
        embedder = se.load_embedder(env={})
        assert loaded_with == [se.DEFAULT_EMBEDDING_MODEL, se.FALLBACK_EMBEDDING_MODEL]
        assert embedder.model_name == se.FALLBACK_EMBEDDING_MODEL

    def test_raises_combined_error_when_both_preferred_and_fallback_fail(self, monkeypatch):
        def fake_try_load(model_name):
            raise se.SemanticEmbedderError(f"'{model_name}' indisponible (simulé)")

        monkeypatch.setattr(se, "_try_load", fake_try_load)
        with pytest.raises(se.SemanticEmbedderError) as excinfo:
            se.load_embedder(env={})
        message = str(excinfo.value)
        assert se.DEFAULT_EMBEDDING_MODEL in message
        assert se.FALLBACK_EMBEDDING_MODEL in message

    def test_reports_dimension_from_model_actually_loaded(self, monkeypatch):
        monkeypatch.setattr(se, "_try_load", lambda model_name: FakeSentenceTransformer(dimension=17))
        embedder = se.load_embedder(env={})
        assert embedder.dimension == 17


class TestSentenceTransformerEmbedderEncode:
    def test_encode_returns_float32_array_with_expected_shape(self, monkeypatch):
        monkeypatch.setattr(se, "_try_load", lambda model_name: FakeSentenceTransformer(dimension=4))
        embedder = se.load_embedder(env={})
        vectors = embedder.encode(["a decoy credential", "a decoy file"])
        assert vectors.shape == (2, 4)
        assert vectors.dtype == np.float32

    def test_encode_is_deterministic_for_same_text(self, monkeypatch):
        monkeypatch.setattr(se, "_try_load", lambda model_name: FakeSentenceTransformer(dimension=4))
        embedder = se.load_embedder(env={})
        vector_1 = embedder.encode(["decoy credential store"])[0]
        vector_2 = embedder.encode(["decoy credential store"])[0]
        assert np.array_equal(vector_1, vector_2)


class TestTryLoadWithoutSentenceTransformersInstalled:
    def test_import_error_wrapped_as_semantic_embedder_error(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def blocking_import(name, *args, **kwargs):
            if name == "sentence_transformers":
                raise ImportError("simulated missing dependency")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocking_import)
        with pytest.raises(se.SemanticEmbedderError):
            se._try_load("any-model")
