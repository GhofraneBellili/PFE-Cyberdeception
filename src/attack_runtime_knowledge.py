"""
Réf. architecture : "8. Base de connaissances ATT&CK" (CLAUDE.md §8) —
réf. tâche « dernière passe de finition technique du chapitre 4 »,
§6-§10 « Supprimer la dépendance runtime au fichier brut ATT&CK ».

Chargeur LÉGER de métadonnées ATT&CK pour le runtime ONLINE, à partir du
staging RAG déjà versionné (`data/attack/staging/attack_rag_seed_*.json`,
`tools/attack_kb/attack_seed_builder.py`) — PAS depuis le bundle STIX brut
`enterprise-attack.json` (~51 Mo, jamais versionné, réf.
`data/attack/README.md`).

**Séparation de responsabilité (réf. tâche §8)** :
- `src/knowledge_attack.py::load_attack_knowledge` reste le SEUL parseur
  STIX du projet — il sert exclusivement à la préparation OFFLINE
  (`tools/attack_kb/attack_seed_builder.py`, construction du staging RAG
  ATT&CK). Il continue de nécessiter le bundle STIX brut, ce qui est
  attendu : le fichier brut ne doit plus être nécessaire qu'à la
  RECONSTRUCTION offline de la base de connaissances, jamais à
  l'exécution du pipeline runtime.
- CE module (`load_attack_runtime_knowledge`) est le SEUL point d'entrée
  ATT&CK utilisé au RUNTIME (`src/rag_candidate_context.py`,
  `src/orchestrator.py`) — il ne lit jamais le bundle STIX brut, il lit
  uniquement le staging déjà versionné. Ne recrée PAS la structure
  complète `AttackKnowledgeBase`/`AttackTechniqueRecord` (description
  complète, stix_id, external_url, ...) : seuls les champs réellement
  utilisés par `RagCandidateContext` sont exposés (technique_id, name,
  tactics, platforms, version, revoked, deprecated) — réf. tâche §7,
  « ne pas recréer toute la structure complète ATT&CK si elle n'est pas
  nécessaire ».

**Aucune invention** (réf. tâche §10) : si une technique du graphe
n'existe pas dans ce staging, `has_technique` renvoie `False` — les
champs `technique_name`/`tactics`/`platforms` de `RagCandidateContext`
restent alors `None`/`[]` (jamais un nom deviné) — voir
`src/rag_candidate_context.py`.

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType


class AttackRuntimeKnowledgeError(Exception):
    """Erreur de chargement du staging RAG ATT&CK pour le runtime."""


@dataclass(frozen=True, slots=True)
class AttackRuntimeTechnique:
    """Réf. tâche §7 : métadonnées minimales d'une technique ATT&CK
    nécessaires au runtime — pas la fiche complète (pas de description,
    pas de stix_id, pas d'external_url : ceux-ci restent réservés au
    corpus RAG lui-même, `src/rag_indexer.py::load_attack_chunks`)."""

    technique_id: str
    name: str | None
    tactics: tuple[str, ...]
    platforms: tuple[str, ...]
    version: str | None
    revoked: bool
    deprecated: bool


@dataclass(frozen=True, slots=True)
class AttackRuntimeKnowledge:
    """Réf. tâche §7/§8 : index déterministe, léger, des techniques ATT&CK
    disponibles au runtime — construit exclusivement depuis le staging RAG
    déjà versionné, jamais depuis le bundle STIX brut."""

    source_path: Path
    techniques_by_id: Mapping[str, AttackRuntimeTechnique]

    def __len__(self) -> int:
        return len(self.techniques_by_id)


def find_latest_attack_staging_file(staging_dir: str | Path) -> Path:
    """Réf. tâche §7 : localise le staging RAG ATT&CK le plus récent dans
    `staging_dir` (`data/attack/staging/` par défaut) — factorise la
    règle déjà durcie dans `tools/rag/build_index.py`/
    `examples/rag_sp2_context_example.py` : le glob
    `attack_rag_seed_*.json` capte AUSSI le rapport d'extraction
    `attack_rag_seed_report_*.json` (même préfixe, schéma différent, sans
    clé 'techniques') — explicitement exclu, sous peine de charger
    silencieusement 0 technique."""
    directory = Path(staging_dir)
    candidates = sorted(f for f in directory.glob("attack_rag_seed_*.json") if "_report_" not in f.name)
    if not candidates:
        raise AttackRuntimeKnowledgeError(
            f"Aucun staging RAG ATT&CK trouvé dans '{directory}' — générer d'abord via "
            "'python -m tools.attack_kb.attack_seed_builder'."
        )
    return candidates[-1]


def load_attack_runtime_knowledge(staging_path: str | Path) -> AttackRuntimeKnowledge:
    """Réf. tâche §7 : charge `attack_rag_seed_<version>.json` (produit
    par `tools/attack_kb/attack_seed_builder.py`) et construit
    `AttackRuntimeKnowledge` — un `AttackRuntimeTechnique` par entrée
    `techniques` du staging, à partir des champs déjà structurés (jamais
    reparsé depuis `source_evidence`, qui reste un texte fragmenté par
    champ pour l'indexation RAG, pas une source de métadonnées
    structurées).

    Lève `AttackRuntimeKnowledgeError` si le fichier est absent ou
    structurellement invalide (clé `techniques` absente) — jamais un
    index vide silencieux."""
    path = Path(staging_path)
    if not path.exists():
        raise AttackRuntimeKnowledgeError(
            f"Staging RAG ATT&CK introuvable : '{path}'. Générer d'abord via "
            "'python -m tools.attack_kb.attack_seed_builder' (réf. data/attack/README.md)."
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "techniques" not in raw:
        raise AttackRuntimeKnowledgeError(
            f"'{path}' n'a pas la forme attendue d'un staging attack_rag_seed (clé 'techniques' absente)."
        )

    techniques_by_id: dict[str, AttackRuntimeTechnique] = {}
    for entry in raw["techniques"]:
        technique_id = entry["technique_id"]
        techniques_by_id[technique_id] = AttackRuntimeTechnique(
            technique_id=technique_id,
            name=entry.get("name"),
            tactics=tuple(entry.get("tactics", [])),
            platforms=tuple(entry.get("platforms", [])),
            version=entry.get("version"),
            revoked=bool(entry.get("revoked", False)),
            deprecated=bool(entry.get("deprecated", False)),
        )

    return AttackRuntimeKnowledge(source_path=path, techniques_by_id=MappingProxyType(techniques_by_id))


def has_technique(kb: AttackRuntimeKnowledge, technique_id: str) -> bool:
    """Réf. tâche §10 : teste l'appartenance sans jamais inventer une
    correspondance approximative."""
    return technique_id in kb.techniques_by_id


def get_technique(kb: AttackRuntimeKnowledge, technique_id: str) -> AttackRuntimeTechnique:
    """Accès direct ; lève `KeyError` si absent (l'appelant doit tester
    `has_technique` au préalable pour un accès défensif, réf.
    `src/rag_candidate_context.py`)."""
    return kb.techniques_by_id[technique_id]
