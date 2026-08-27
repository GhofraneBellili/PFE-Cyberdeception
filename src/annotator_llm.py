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
sans ré-appeler le provider (API réelle ou stub) — toute future
implémentation d'un provider LLM réel doit respecter la même interface
(`AnnotationProvider.annotate`) et température fixe (0), conformément à
la politique de reproductibilité demandée.

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

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
