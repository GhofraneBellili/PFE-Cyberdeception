"""
Réf. architecture : CLAUDE.md §11 (annotation LLM+RAG) — tests de
src/llm_provider.py (§25.4 : pytest obligatoire).

Aucun test ici n'effectue d'appel réseau réel (§ tâche 12) : le
`transport`/`list_ollama_models` sont toujours des fonctions mock
injectées, jamais `default_http_transport` en conditions réelles.
"""

import pytest

from src.llm_provider import (
    DEFAULT_OLLAMA_BASE_URL,
    LlmProviderConfig,
    LlmProviderError,
    call_ollama,
    call_openai_compatible,
    config_from_env,
    default_list_ollama_models,
)


class TestConfigFromEnv:
    def test_ollama_with_defaults(self):
        config = config_from_env({"LLM_PROVIDER": "ollama", "LLM_MODEL": "llama3"})
        assert config.provider == "ollama"
        assert config.model == "llama3"
        assert config.base_url == DEFAULT_OLLAMA_BASE_URL

    def test_ollama_without_model_still_returns_config(self):
        """LLM_MODEL peut être absent pour ollama : detect_provider choisit
        alors le premier modèle localement disponible (réf. § tâche 1 :
        "ne pas imposer un modèle particulier dans le code métier")."""
        config = config_from_env({"LLM_PROVIDER": "ollama"})
        assert config.provider == "ollama"
        assert config.model == ""

    def test_ollama_custom_base_url(self):
        config = config_from_env({"LLM_PROVIDER": "ollama", "LLM_MODEL": "llama3", "LLM_BASE_URL": "http://gpu-box:11434"})
        assert config.base_url == "http://gpu-box:11434"

    def test_openai_compatible_requires_model_and_base_url(self):
        assert config_from_env({"LLM_PROVIDER": "openai_compatible", "LLM_MODEL": "gpt-x"}) is None
        assert config_from_env({"LLM_PROVIDER": "openai_compatible", "LLM_BASE_URL": "https://api.example.com"}) is None

    def test_openai_compatible_complete(self):
        config = config_from_env(
            {"LLM_PROVIDER": "openai_compatible", "LLM_MODEL": "gpt-x", "LLM_BASE_URL": "https://api.example.com", "LLM_API_KEY": "secret"}
        )
        assert config.provider == "openai_compatible"
        assert config.api_key == "secret"

    def test_no_provider_returns_none(self):
        assert config_from_env({}) is None

    def test_unknown_provider_returns_none(self):
        assert config_from_env({"LLM_PROVIDER": "carrier_pigeon", "LLM_MODEL": "x"}) is None

    def test_never_reads_real_os_environ_unless_asked(self, monkeypatch):
        """Par défaut (env=None), lit os.environ — vérifié explicitement
        pour ne pas dépendre silencieusement d'un état non maîtrisé."""
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        assert config_from_env(None) is None


class TestCallOllama:
    def test_extracts_message_content(self):
        config = LlmProviderConfig(provider="ollama", model="llama3", base_url="http://localhost:11434")

        def fake_transport(url, payload, headers, timeout):
            assert url == "http://localhost:11434/api/chat"
            assert payload["model"] == "llama3"
            assert payload["options"]["temperature"] == 0.0
            return {"message": {"content": '{"annotations": []}'}}

        result = call_ollama(config, "prompt", fake_transport)
        assert result == '{"annotations": []}'

    def test_unexpected_response_structure_raises(self):
        config = LlmProviderConfig(provider="ollama", model="llama3", base_url="http://localhost:11434")

        def fake_transport(url, payload, headers, timeout):
            return {"unexpected": "shape"}

        with pytest.raises(LlmProviderError):
            call_ollama(config, "prompt", fake_transport)


class TestCallOpenAiCompatible:
    def test_extracts_choice_content_and_sets_auth_header(self):
        config = LlmProviderConfig(
            provider="openai_compatible", model="gpt-x", base_url="https://api.example.com", api_key="secret"
        )
        captured = {}

        def fake_transport(url, payload, headers, timeout):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = payload
            return {"choices": [{"message": {"content": '{"annotations": []}'}}]}

        result = call_openai_compatible(config, "prompt", fake_transport)
        assert result == '{"annotations": []}'
        assert captured["url"] == "https://api.example.com/chat/completions"
        assert captured["headers"]["Authorization"] == "Bearer secret"
        assert captured["payload"]["response_format"] == {"type": "json_object"}

    def test_no_api_key_omits_auth_header(self):
        config = LlmProviderConfig(provider="openai_compatible", model="gpt-x", base_url="https://api.example.com")
        captured = {}

        def fake_transport(url, payload, headers, timeout):
            captured["headers"] = headers
            return {"choices": [{"message": {"content": "{}"}}]}

        call_openai_compatible(config, "prompt", fake_transport)
        assert "Authorization" not in captured["headers"]

    def test_unexpected_response_structure_raises(self):
        config = LlmProviderConfig(provider="openai_compatible", model="gpt-x", base_url="https://api.example.com")

        def fake_transport(url, payload, headers, timeout):
            return {"choices": []}

        with pytest.raises(LlmProviderError):
            call_openai_compatible(config, "prompt", fake_transport)


class TestDefaultListOllamaModels:
    def test_connection_error_raises_llm_provider_error(self, monkeypatch):
        """Aucun appel réseau réel pendant pytest (§ tâche 12) :
        urllib.request.urlopen est mocké pour simuler un service
        injoignable, sans jamais ouvrir de socket réelle."""
        import urllib.error
        import urllib.request

        def fake_urlopen(request, timeout):
            raise urllib.error.URLError("connection refused (mock)")

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(LlmProviderError):
            default_list_ollama_models("http://localhost:11434", 1.0)

    def test_parses_model_names_from_response(self, monkeypatch):
        import io
        import urllib.request

        class FakeResponse(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fake_urlopen(request, timeout):
            return FakeResponse(b'{"models": [{"name": "llama3"}, {"name": "mistral"}]}')

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        models = default_list_ollama_models("http://localhost:11434", 1.0)
        assert models == ["llama3", "mistral"]
