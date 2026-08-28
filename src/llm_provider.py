"""
Réf. architecture : "11. SP2 — Annotation contextuelle LLM+RAG" (§11) —
couche de transport HTTP vers un vrai service LLM, séparée de
`src/annotator_llm.py` pour garder ce dernier centré sur le CONTENU de
l'annotation (interface, validation, cache) plutôt que sur la mécanique
réseau.

**Deux providers supportés, choisis par variables d'environnement — pas
de modèle imposé dans le code métier (§ tâche 1) :**

    LLM_PROVIDER   "ollama" ou "openai_compatible"
    LLM_MODEL      nom du modèle (obligatoire)
    LLM_BASE_URL   URL de base (optionnelle pour ollama, "http://localhost:11434"
                   par défaut ; obligatoire pour openai_compatible)
    LLM_API_KEY    clé d'API (optionnelle — jamais versionnée dans le dépôt)

Aucune clé API ni URL privée n'est codée en dur ici. `urllib.request`
(bibliothèque standard) est utilisé pour l'appel HTTP — pas de nouvelle
dépendance (§ tâche 13, ne pas surdévelopper).

Le `transport` (fonction d'envoi HTTP) et `list_models` (sondage Ollama)
sont injectables : les tests peuvent les remplacer par un mock déterministe
sans jamais appeler un service réel (§ tâche 12).

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_PROMPT_VERSION = "real-llm-v1"

# Réf. incompatibilité réelle constatée (endpoint OpenAI-compatible Groq,
# https://api.groq.com/openai/v1/chat/completions) : le User-Agent par
# défaut d'urllib ("Python-urllib/x.y") est bloqué par le WAF Cloudflare
# placé devant l'API (HTTP 403, corps "error code: 1010" — signature de
# bot). Reproduit et confirmé : un appel curl identique (User-Agent
# différent) et un appel urllib avec ce User-Agent explicite réussissent
# tous deux (HTTP 200) avec exactement la même clé/URL/charge utile.
# Un User-Agent explicite et identifiable est donc nécessaire — jamais
# une valeur imitant un navigateur pour contourner un blocage légitime.
DEFAULT_USER_AGENT = "pfe-cyberdeception-sp2-annotator/1.0"

Transport = Callable[[str, dict, dict, float], dict]


class LlmProviderError(Exception):
    """Erreur de configuration, de connexion ou de réponse du provider LLM réel."""


@dataclass(frozen=True)
class LlmProviderConfig:
    """Réf. § tâche 1 : configuration d'un provider LLM réel, entièrement
    dérivée de variables d'environnement — jamais d'URL ni de clé
    codée en dur."""

    provider: str
    model: str
    base_url: str
    api_key: str | None = None
    temperature: float = 0.0
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_retries: int = DEFAULT_MAX_RETRIES
    prompt_version: str = DEFAULT_PROMPT_VERSION


def config_from_env(env: Mapping[str, str] | None = None) -> LlmProviderConfig | None:
    """Réf. § tâche 2 : lit LLM_PROVIDER/LLM_MODEL/LLM_BASE_URL/LLM_API_KEY.
    Retourne `None` si la configuration est absente ou incomplète — ne
    devine jamais une valeur manquante (§25.3)."""
    env = env if env is not None else os.environ
    provider = env.get("LLM_PROVIDER")
    model = env.get("LLM_MODEL")
    base_url = env.get("LLM_BASE_URL")
    api_key = env.get("LLM_API_KEY")

    if provider == "ollama":
        return LlmProviderConfig(
            provider="ollama", model=model or "", base_url=base_url or DEFAULT_OLLAMA_BASE_URL, api_key=api_key
        )
    if provider == "openai_compatible":
        if not model or not base_url:
            return None
        return LlmProviderConfig(provider="openai_compatible", model=model, base_url=base_url, api_key=api_key)
    return None


# ---------------------------------------------------------------------------
# Transport HTTP par défaut — urllib (bibliothèque standard)
# ---------------------------------------------------------------------------


def default_http_transport(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    """Réf. § tâche 1 : envoie `payload` en JSON via POST, retourne la
    réponse déjà décodée en JSON. Toute erreur réseau ou de décodage lève
    `LlmProviderError` — jamais de valeur de repli inventée.

    `User-Agent` explicite (`DEFAULT_USER_AGENT`) : requis en pratique
    contre le WAF Cloudflare de l'endpoint Groq réel, qui bloque (HTTP
    403) le User-Agent par défaut d'urllib — voir la constante ci-dessus.
    Un `headers` appelant qui fixerait son propre `User-Agent` resterait
    prioritaire (fusion avec `headers` en second)."""
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": DEFAULT_USER_AGENT, **headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise LlmProviderError(f"Échec de connexion au provider LLM ({url}) : {exc}") from exc
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise LlmProviderError(f"Réponse du provider LLM non-JSON ({url}) : {exc}") from exc


def default_list_ollama_models(base_url: str, timeout: float) -> list[str]:
    """Réf. § tâche 2, CAS A : sonde `GET /api/tags` pour lister les
    modèles réellement disponibles localement."""
    url = base_url.rstrip("/") + "/api/tags"
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise LlmProviderError(f"Ollama injoignable ({url}) : {exc}") from exc
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise LlmProviderError(f"Réponse Ollama non-JSON ({url}) : {exc}") from exc
    return [model.get("name") for model in parsed.get("models", []) if model.get("name")]


# ---------------------------------------------------------------------------
# Appels spécifiques par provider — réf. § tâche 1
# ---------------------------------------------------------------------------


def call_ollama(config: LlmProviderConfig, prompt: str, transport: Transport = default_http_transport) -> str:
    """Réf. § tâche 1 : `POST {base_url}/api/chat`, `format=json`,
    `temperature` fixée par `config`. Retourne le contenu texte brut
    produit par le modèle (à parser/valider séparément, réf.
    `src/annotator_llm.py`)."""
    url = config.base_url.rstrip("/") + "/api/chat"
    payload = {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
        "options": {"temperature": config.temperature},
    }
    response = transport(url, payload, {}, config.timeout_seconds)
    try:
        return response["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise LlmProviderError(f"Réponse Ollama inattendue (structure) : {response!r}") from exc


def call_openai_compatible(config: LlmProviderConfig, prompt: str, transport: Transport = default_http_transport) -> str:
    """Réf. § tâche 1 : `POST {base_url}/chat/completions`,
    `response_format={"type":"json_object"}`, `temperature` fixée par
    `config`. Retourne le contenu texte brut produit par le modèle."""
    url = config.base_url.rstrip("/") + "/chat/completions"
    headers = {}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    payload = {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": config.temperature,
        "response_format": {"type": "json_object"},
    }
    response = transport(url, payload, headers, config.timeout_seconds)
    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmProviderError(f"Réponse OpenAI-compatible inattendue (structure) : {response!r}") from exc
