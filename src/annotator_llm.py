"""
Réf. architecture : "11. SP2 — Annotation contextuelle LLM+RAG" (CLAUDE.md
§11, §26 — module `annotator_llm.py`).

Produit les 11 `Annotation` brutes (`src/schemas.py`) — Realism
(`R_tech`, `R_context`, `R_perception`, `R_behavior`),
InteractionLikelihood (`A_object`, `A_action`, `A_source`), Effectiveness
sur la progression (`S_stop`, `S_redirect`, `S_contain`, `S_delay`) — pour
un candidat `(T_{i,h}, d, l)` déjà décrit par un `AnnotationContext` (RAG
déjà exécuté, §11.2, `src/rag_retriever.py`).

**Ce module ne calcule JAMAIS** Realisme, P_interaction, P_engagement,
Effet_prog, DE ni le risque (§11.5) : seule la sortie brute des 11
sous-métriques est produite ici. L'agrégation déterministe (§12) et le
gel de la table (§13, `annotation_validator.py`, non implémenté à ce
stade) restent hors de ce module.

**Repli déterministe `rule_based_stub`** — aucune clé d'API LLM réelle
n'est disponible dans cet environnement. `RuleBasedStubAnnotator` calcule
un score UNIQUE de chevauchement lexical (proportion de tokens du
contexte — technique, tactiques, mécanisme, emplacement — retrouvés dans
les preuves RAG récupérées) et l'applique identiquement aux 11
sous-métriques : ce stub ne peut PAS distinguer sémantiquement Realism
d'InteractionLikelihood ou d'Effectiveness sans modèle de langage réel —
prétendre le contraire serait une fabrication (§20, §25.3). Chaque
annotation produite porte `model_version="rule_based_stub"` et n'est
**jamais présentée comme un résultat LLM réel ni comme un résultat
expérimental du chapitre 5** (voir
`docs/chapter4/IMPLEMENTATION_REPORT.md`, section 6).

**Déterminisme/reproductibilité** : `AnnotationCache` associe une clé
déterministe (hash du contexte + `model_version` + `prompt_version`) à la
liste d'`Annotation` déjà produite, pour rejouer un résultat identique
sans ré-appeler le provider (API réelle ou stub) — la clé dépend du
contexte candidat (donc des preuves récupérées, incluses dans
`AnnotationContext`), de `model_version` et de `prompt_version`.

**Provider LLM réel (`RealLlmAnnotator`)** — réf. tâche « intégrer un
véritable provider LLM ». Configuré par variables d'environnement
(`LLM_PROVIDER`/`LLM_MODEL`/`LLM_BASE_URL`/`LLM_API_KEY`,
`src/llm_provider.py`), appelle réellement un service Ollama local ou un
endpoint OpenAI-compatible, `temperature=0`, sortie JSON structurée,
timeout et retries limités. **Toute sortie malformée, incomplète, hors
`[0,1]`, ou citant un `evidence_id` absent des preuves réellement
récupérées est REJETÉE** (`LlmOutputValidationError`) — jamais remplacée
silencieusement par une valeur inventée (§20, §25.3).
`RuleBasedStubAnnotator` reste le repli explicite : utilisé pour les
tests unitaires, et comme repli documenté quand aucun provider réel n'est
disponible dans l'environnement — jamais présenté comme un résultat LLM
réel. `detect_provider` choisit automatiquement entre les deux selon ce
qui est réellement exploitable (CAS A : Ollama local disponible ; CAS B :
endpoint OpenAI-compatible configuré ; CAS C : repli déterministe).

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from pydantic import ValidationError

from src.llm_provider import (
    LlmProviderConfig,
    LlmProviderError,
    Transport,
    call_ollama,
    call_openai_compatible,
    config_from_env,
    default_http_transport,
    default_list_ollama_models,
)
from src.schemas import Annotation, AnnotationContext, AnnotationMetricName

ELEVEN_METRICS: tuple[AnnotationMetricName, ...] = (
    "R_tech",
    "R_context",
    "R_perception",
    "R_behavior",
    "A_object",
    "A_action",
    "A_source",
    "S_stop",
    "S_redirect",
    "S_contain",
    "S_delay",
)

RULE_BASED_STUB_MODEL_VERSION = "rule_based_stub"
DEFAULT_PROMPT_VERSION = "rule_based_stub-v1"

_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")


class AnnotatorLlmError(Exception):
    """Erreur de production d'une annotation SP2."""


class AnnotationProvider(Protocol):
    """Interface commune à tout annotateur (repli déterministe ou futur
    provider LLM réel) — réf. §11.3/§11.4."""

    def annotate(self, context: AnnotationContext, *, now: datetime | None = None) -> list[Annotation]: ...


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_PATTERN.findall(text.lower()))


def _context_signature(context: AnnotationContext) -> str:
    """Réf. §27 : signal de contexte minimal, construit uniquement à
    partir de champs déjà présents dans `AnnotationContext` (jamais du
    budget, §11.2)."""
    tactics = " ".join(context.attack_occurrence.attributes.tactics)
    return f"{context.attack_occurrence.technique_id} {tactics} {context.deception.name} {context.placement}"


def _evidence_text(context: AnnotationContext) -> str:
    return " ".join(item.passage for item in context.retrieved_evidence)


def _lexical_overlap_score(context: AnnotationContext) -> float:
    """Score déterministe [0,1] : proportion des tokens du signal de
    contexte retrouvés dans le texte des preuves RAG récupérées. Mesure
    purement lexicale (pas sémantique) — voir docstring de module."""
    context_tokens = _tokens(_context_signature(context))
    evidence_tokens = _tokens(_evidence_text(context))
    if not context_tokens or not evidence_tokens:
        return 0.0
    return len(context_tokens & evidence_tokens) / len(context_tokens)


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, value))


def deterministic_annotation_id(
    context: AnnotationContext, *, metric: str, model_version: str, prompt_version: str
) -> str:
    """Identifiant reproductible : même contexte + même métrique + même
    (model_version, prompt_version) -> même `annotation_id` (§ déterminisme)."""
    canonical = json.dumps(context.model_dump(mode="json"), sort_keys=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{model_version}:{prompt_version}:{metric}:{digest}"


@dataclass(frozen=True)
class RuleBasedStubAnnotator:
    """Réf. « repli déterministe » — implémentation de secours utilisée en
    l'absence d'API LLM réelle. Voir docstring de module pour les
    limites : score de chevauchement lexical UNIQUE appliqué identiquement
    aux 11 sous-métriques, jamais une annotation sémantique réelle."""

    prompt_version: str = DEFAULT_PROMPT_VERSION
    evidence_saturation: int = 3

    def annotate(self, context: AnnotationContext, *, now: datetime | None = None) -> list[Annotation]:
        if not context.retrieved_evidence:
            raise AnnotatorLlmError(
                "Aucune preuve RAG recuperee dans le contexte : le stub deterministe "
                "refuse de fabriquer une justification ou une preuve (§20, §25.3)."
            )
        timestamp = now if now is not None else datetime.now(timezone.utc)
        score = _clamp_unit(_lexical_overlap_score(context))
        confidence = _clamp_unit(len(context.retrieved_evidence) / self.evidence_saturation)
        evidence_ids = [item.source for item in context.retrieved_evidence]
        justification = (
            "Stub deterministe (rule_based_stub) : chevauchement lexical entre le "
            f"contexte ('{context.attack_occurrence.technique_id}', '{context.deception.name}', "
            f"'{context.placement}') et {len(context.retrieved_evidence)} preuve(s) RAG "
            f"recuperee(s) -> score={score:.3f}. Ceci n'est PAS une annotation semantique "
            "LLM reelle (score identique applique aux 11 sous-metriques, faute de modele "
            "de langage disponible dans cet environnement)."
        )

        annotations = []
        for metric in ELEVEN_METRICS:
            annotations.append(
                Annotation(
                    metric=metric,
                    score=score,
                    justification=justification,
                    evidence=evidence_ids,
                    confidence=confidence,
                    model_version=RULE_BASED_STUB_MODEL_VERSION,
                    prompt_version=self.prompt_version,
                    annotated_at=timestamp,
                    annotation_id=deterministic_annotation_id(
                        context,
                        metric=metric,
                        model_version=RULE_BASED_STUB_MODEL_VERSION,
                        prompt_version=self.prompt_version,
                    ),
                )
            )
        return annotations


@dataclass
class AnnotationCache:
    """Réf. § reproductibilité LLM : cache déterministe
    contexte+modèle+prompt -> annotations déjà produites, pour rejouer un
    résultat identique sans ré-appeler le provider."""

    _entries: dict[str, list[Annotation]] = field(default_factory=dict)
    calls: int = 0

    @staticmethod
    def make_key(context: AnnotationContext, *, model_version: str, prompt_version: str) -> str:
        canonical = json.dumps(context.model_dump(mode="json"), sort_keys=True)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"{model_version}:{prompt_version}:{digest}"

    def get(self, key: str) -> list[Annotation] | None:
        return self._entries.get(key)

    def put(self, key: str, annotations: list[Annotation]) -> None:
        self._entries[key] = annotations

    def __len__(self) -> int:
        return len(self._entries)


def annotate_with_cache(
    provider: AnnotationProvider,
    context: AnnotationContext,
    cache: AnnotationCache,
    *,
    model_version: str,
    prompt_version: str,
    now: datetime | None = None,
) -> list[Annotation]:
    """Réf. § reproductibilité LLM : rejoue une annotation déjà en cache
    pour un contexte identique, sinon appelle `provider.annotate` une
    seule fois et met en cache le résultat."""
    key = cache.make_key(context, model_version=model_version, prompt_version=prompt_version)
    cached = cache.get(key)
    if cached is not None:
        return cached
    cache.calls += 1
    annotations = provider.annotate(context, now=now)
    cache.put(key, annotations)
    return annotations


# ---------------------------------------------------------------------------
# Provider LLM réel — réf. tâche « intégrer un véritable provider LLM »
# ---------------------------------------------------------------------------


class LlmOutputValidationError(AnnotatorLlmError):
    """Sortie du provider LLM réel structurellement invalide, hors bornes,
    incomplète, ou citant un `evidence_id` absent des preuves réellement
    récupérées. Jamais remplacée silencieusement par une valeur inventée
    (§20, §25.3) : cette exception doit systématiquement remonter."""


def _build_prompt(context: AnnotationContext) -> str:
    """Réf. §11.2 : construit le prompt à partir des seuls champs déjà
    présents dans `AnnotationContext` — occurrence, mécanisme,
    emplacement, contexte graphe, preuves RAG. `system_context` n'est
    JAMAIS inclus ici (protection supplémentaire, au-delà de
    l'interdiction déjà appliquée par le validateur Pydantic
    d'`AnnotationContext`) : le budget B_total ne doit jamais atteindre le
    LLM (§11.2)."""
    payload = {
        "attack_occurrence": {
            "technique_id": context.attack_occurrence.technique_id,
            "asset_id": context.attack_occurrence.asset_id,
            "tactics": context.attack_occurrence.attributes.tactics,
            "outcomes": context.attack_occurrence.attributes.outcomes,
        },
        "deception": {"id": context.deception.id, "name": context.deception.name},
        "placement": context.placement,
        "graph_context": {
            "parents": context.graph_context.parents,
            "children": context.graph_context.children,
            "terminal_paths": context.graph_context.terminal_paths,
        },
    }
    evidence_ids = [item.source for item in context.retrieved_evidence]
    evidence_block = "\n".join(f"- [{item.source}] {item.passage}" for item in context.retrieved_evidence)
    instructions = (
        "You are annotating a single cyberdeception placement candidate for a "
        "security research pipeline. Score EXACTLY these 11 sub-metrics, each in "
        "[0,1], each citing at least one evidence_id taken ONLY from the list "
        "below (never invent an evidence_id): "
        "R_tech, R_context, R_perception, R_behavior, A_object, A_action, "
        "A_source, S_stop, S_redirect, S_contain, S_delay.\n"
        'Return ONLY a JSON object of the exact form: {"annotations": '
        '[{"metric": "...", "score": 0.0, "confidence": 0.0, "justification": '
        '"...", "evidence_ids": ["..."]}, ...11 items total...]}.\n'
        "Do not compute or mention any aggregate: Realism, InteractionLikelihood, "
        "P_engage, Effectiveness_prog, DE, cost, Gamma, risk, budget, or an "
        "optimal configuration — these are computed elsewhere, never by you."
    )
    return (
        f"{instructions}\n\n"
        f"Context:\n{json.dumps(payload, ensure_ascii=False)}\n\n"
        f"Evidence (cite ONLY these evidence_ids: {evidence_ids}):\n{evidence_block}\n"
    )


def _parse_and_validate_llm_output(
    raw_content: str,
    *,
    context: AnnotationContext,
    model: str,
    prompt_version: str,
    timestamp: datetime,
) -> list[Annotation]:
    """Réf. § tâche « intégrer un véritable provider LLM » : valide
    strictement la sortie brute du LLM. Toute non-conformité lève
    `LlmOutputValidationError` — jamais une correction silencieuse."""
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise LlmOutputValidationError(f"Sortie LLM non-JSON : {exc}. Contenu brut : {raw_content!r}") from exc

    if not isinstance(parsed, dict) or "annotations" not in parsed:
        raise LlmOutputValidationError(f"Sortie LLM mal formée : clé 'annotations' absente. Contenu : {parsed!r}")

    raw_annotations = parsed["annotations"]
    if not isinstance(raw_annotations, list):
        raise LlmOutputValidationError("'annotations' doit être une liste.")

    valid_evidence_ids = {item.source for item in context.retrieved_evidence}
    seen_metrics: set[str] = set()
    annotations: list[Annotation] = []

    for raw in raw_annotations:
        if not isinstance(raw, dict):
            raise LlmOutputValidationError(f"Élément d'annotation non-objet : {raw!r}")

        metric = raw.get("metric")
        if metric not in ELEVEN_METRICS:
            raise LlmOutputValidationError(f"Sous-métrique inconnue ou absente : {metric!r}")
        if metric in seen_metrics:
            raise LlmOutputValidationError(f"Sous-métrique dupliquée dans la sortie LLM : {metric}")
        seen_metrics.add(metric)

        evidence_ids = raw.get("evidence_ids")
        if not isinstance(evidence_ids, list) or not evidence_ids:
            raise LlmOutputValidationError(f"'{metric}' : evidence_ids manquant ou vide.")
        unknown_evidence = [e for e in evidence_ids if e not in valid_evidence_ids]
        if unknown_evidence:
            raise LlmOutputValidationError(
                f"'{metric}' cite des evidence_ids absents des preuves réellement récupérées : {unknown_evidence}."
            )

        try:
            annotation = Annotation(
                metric=metric,
                score=raw.get("score"),
                justification=raw.get("justification") or "",
                evidence=evidence_ids,
                confidence=raw.get("confidence"),
                model_version=model,
                prompt_version=prompt_version,
                annotated_at=timestamp,
                annotation_id=deterministic_annotation_id(
                    context, metric=metric, model_version=model, prompt_version=prompt_version
                ),
            )
        except ValidationError as exc:
            raise LlmOutputValidationError(f"'{metric}' : sortie LLM hors bornes ou incomplète : {exc}") from exc
        annotations.append(annotation)

    missing_metrics = set(ELEVEN_METRICS) - seen_metrics
    if missing_metrics:
        raise LlmOutputValidationError(f"Sous-métriques manquantes dans la sortie LLM : {sorted(missing_metrics)}.")

    return annotations


@dataclass(frozen=True)
class RealLlmAnnotator:
    """Réf. § tâche « intégrer un véritable provider LLM » — provider LLM
    réel (Ollama local ou endpoint OpenAI-compatible), configuré par
    `LlmProviderConfig` (`src/llm_provider.py`, dérivée de variables
    d'environnement — jamais d'URL ni de clé codée en dur).

    Ne calcule JAMAIS Realisme/P_interaction/P_engagement/Effet_prog/DE
    ni le risque, la configuration optimale ou le budget (§11.5) — le
    prompt ne les mentionne que comme des calculs INTERDITS au LLM.

    `transport` est injectable : les tests remplacent l'appel réseau réel
    par un mock déterministe (§ tâche 12), jamais un appel à un service
    payant pendant `pytest`.
    """

    config: LlmProviderConfig
    transport: Transport = default_http_transport

    def _call_raw(self, prompt: str) -> str:
        if self.config.provider == "ollama":
            return call_ollama(self.config, prompt, self.transport)
        if self.config.provider == "openai_compatible":
            return call_openai_compatible(self.config, prompt, self.transport)
        raise LlmProviderError(f"Provider LLM inconnu : '{self.config.provider}'.")

    def annotate(self, context: AnnotationContext, *, now: datetime | None = None) -> list[Annotation]:
        if not context.retrieved_evidence:
            raise AnnotatorLlmError(
                "Aucune preuve RAG recuperee dans le contexte : le provider LLM reel "
                "refuse d'annoter sans preuve (§20, §25.3)."
            )
        timestamp = now if now is not None else datetime.now(timezone.utc)
        prompt = _build_prompt(context)

        last_error: Exception | None = None
        for _ in range(self.config.max_retries + 1):
            try:
                raw_content = self._call_raw(prompt)
                return _parse_and_validate_llm_output(
                    raw_content,
                    context=context,
                    model=self.config.model,
                    prompt_version=self.config.prompt_version,
                    timestamp=timestamp,
                )
            except (LlmProviderError, LlmOutputValidationError) as exc:
                last_error = exc
                continue
        raise LlmProviderError(
            f"Échec du provider LLM réel après {self.config.max_retries + 1} tentative(s) : {last_error}"
        ) from last_error


# ---------------------------------------------------------------------------
# Détection du provider réellement exploitable — réf. § tâche 2
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderDetectionResult:
    """Réf. § tâche 2 : provider réellement sélectionné + description
    honnête du choix fait (jamais une affirmation non vérifiée)."""

    provider: AnnotationProvider
    annotation_type: str  # "real_llm" ou "rule_based_stub"
    reason: str
    details: dict


def detect_provider(
    env: Mapping[str, str] | None = None,
    *,
    transport: Transport = default_http_transport,
    list_ollama_models: Callable[[str, float], list[str]] = default_list_ollama_models,
    probe_timeout: float = 5.0,
) -> ProviderDetectionResult:
    """Réf. § tâche 2 : détecte si un provider LLM réel est réellement
    exploitable dans l'environnement — ne fabrique jamais un résultat si
    ce n'est pas le cas (CAS C : repli déterministe, avec la raison
    exacte du repli).

    CAS A — `LLM_PROVIDER=ollama` : sonde `GET /api/tags` ; si
    `LLM_MODEL` est fourni, vérifie qu'il est bien disponible localement ;
    sinon, utilise le premier modèle disponible (pas de modèle imposé
    dans le code, réf. § tâche 1).
    CAS B — `LLM_PROVIDER=openai_compatible` avec `LLM_MODEL`/
    `LLM_BASE_URL` : considéré disponible sans sondage réseau (pas de
    quota consommé pendant la détection).
    CAS C — configuration absente/incomplète/provider inconnu : repli
    `RuleBasedStubAnnotator`.
    """
    config = config_from_env(env)
    if config is None:
        return ProviderDetectionResult(
            provider=RuleBasedStubAnnotator(),
            annotation_type="rule_based_stub",
            reason="LLM_PROVIDER/LLM_MODEL/LLM_BASE_URL non configurés (ou LLM_PROVIDER inconnu).",
            details={},
        )

    if config.provider == "ollama":
        try:
            available_models = list_ollama_models(config.base_url, probe_timeout)
        except LlmProviderError as exc:
            return ProviderDetectionResult(
                provider=RuleBasedStubAnnotator(),
                annotation_type="rule_based_stub",
                reason=f"LLM_PROVIDER=ollama configuré mais injoignable ({config.base_url}) : {exc}",
                details={"base_url": config.base_url},
            )
        if not available_models:
            return ProviderDetectionResult(
                provider=RuleBasedStubAnnotator(),
                annotation_type="rule_based_stub",
                reason=f"Ollama joignable ({config.base_url}) mais aucun modèle local disponible.",
                details={"base_url": config.base_url},
            )
        model = config.model or available_models[0]
        if config.model and config.model not in available_models:
            return ProviderDetectionResult(
                provider=RuleBasedStubAnnotator(),
                annotation_type="rule_based_stub",
                reason=(
                    f"LLM_MODEL='{config.model}' non disponible localement "
                    f"(modèles trouvés : {available_models})."
                ),
                details={"base_url": config.base_url, "available_models": available_models},
            )
        real_config = LlmProviderConfig(
            provider="ollama",
            model=model,
            base_url=config.base_url,
            api_key=config.api_key,
            temperature=config.temperature,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
            prompt_version=config.prompt_version,
        )
        return ProviderDetectionResult(
            provider=RealLlmAnnotator(config=real_config, transport=transport),
            annotation_type="real_llm",
            reason=f"Ollama local disponible, modèle '{model}' trouvé.",
            details={"provider": "ollama", "model": model, "base_url": config.base_url},
        )

    if config.provider == "openai_compatible":
        return ProviderDetectionResult(
            provider=RealLlmAnnotator(config=config, transport=transport),
            annotation_type="real_llm",
            reason=f"Endpoint OpenAI-compatible configuré ({config.base_url}).",
            details={"provider": "openai_compatible", "model": config.model, "base_url": config.base_url},
        )

    return ProviderDetectionResult(
        provider=RuleBasedStubAnnotator(),
        annotation_type="rule_based_stub",
        reason=f"LLM_PROVIDER inconnu : '{config.provider}'.",
        details={},
    )
