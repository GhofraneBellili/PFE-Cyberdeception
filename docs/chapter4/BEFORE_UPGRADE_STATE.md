# État de référence AVANT amélioration substantielle (Phase 0)

> Réf. tâche « amélioration substantielle de l'implémentation ».
> Ce document fige l'état RÉEL du dépôt immédiatement avant les
> modifications des phases 1 à 25 (branche `implementation/chapter4`,
> dernier commit avant cette tâche : `cfe03c3`). Il sert de point de
> comparaison objectif pour mesurer les gains réels obtenus — pas une
> déclaration d'intention.

## Documents relus (Phase 0.1)

`CLAUDE.md`, `README.md`, `docs/chapter4/FINAL_TECHNICAL_REPORT.md`,
`docs/chapter4/ADMISSIBILITY_EVIDENCE_AUDIT.md`,
`docs/chapter4/TECHNOLOGIES.md`, `docs/chapter4/SCREENSHOT_MANIFEST.md`.

## Tests (Phase 0.3)

```
pytest -v
============================ 588 passed in 10.64s =============================
```

## État chiffré (Phase 0.4)

| Indicateur | Valeur AVANT |
|---|---|
| Tests totaux | 588, tous verts |
| RAG — moteur de vectorisation | TF-IDF haché (`hashlib.blake2b`, `src/rag_indexer.py`) — **aucun embedding sémantique** |
| RAG — nombre de chunks indexés | 124 (44 D3FEND, 62 Engage, 18 littérature) |
| Catalogue — mécanismes réels | **3** (`D3-DF`, `D3-DUC`, `D3-DNR`) |
| Mapping `M_{i,d}` — relations | 127 (→ 125 techniques ATT&CK distinctes), toutes `d3fend_inferred`, aucune distinction `direct`/`derived` |
| SP1 réel (`sp1_real_example.py`) — candidats bruts | 12 |
| SP1 réel — candidats admissibles | **1** (`T1039@FS01` / `D3-DNR` / `shared-drive`) |
| Provider LLM réel | Implémenté et testé par mocks HTTP (`RealLlmAnnotator`, `src/llm_provider.py`) — **jamais exécuté contre un service réel** (aucun Ollama local, aucune variable `LLM_*` configurée dans cet environnement, revérifié à l'instant : `ollama` absent du PATH, aucun service sur `localhost:11434`) |
| Annotations LLM réelles figées | 0 (`docs/chapter4/outputs/llm_annotation_real.json` n'existe pas) |
| Figures PNG chapitre 4 | C1, C2, C3, C4, C7 `AVAILABLE` ; C5, C6 `NOT_AVAILABLE` |

## Les 4 limites ciblées par cette tâche

1. **RAG lexical, pas sémantique** — `src/rag_indexer.py` vectorise par
   fréquence de termes hachée (TF-IDF + hashing trick), pas par un
   modèle de langage. Choix technique documenté (`TECHNOLOGIES.md`),
   jamais présenté comme une représentation sémantique.
2. **Catalogue restreint à 3 mécanismes** — périmètre v1 volontairement
   étroit (`tools/deception_kb/catalog_builder.py`) : seuls les concepts
   D3FEND feuilles avec une relation ATT&CK directement tracée.
3. **LLM réel jamais exécuté** — code complet et testé par mocks
   (`tests/test_annotator_llm.py::TestRealLlmAnnotator`, 12 tests),
   aucune exécution réelle faute de service disponible.
4. **Un seul candidat SP1 admissible** — l'instance d'exemple
   (`examples/sp1_real_example.py`) est volontairement minimale (2
   occurrences, 2 emplacements), insuffisante pour illustrer la
   diversité de comportement de SP1.

## Environnement vérifié pour cette passe

- Accès réseau : `https://pypi.org` joignable (code 200).
- Espace disque libre : ~63 Go sur `C:`.
- `ollama` : absent du PATH, aucun service sur `http://localhost:11434`.
- Variables `LLM_PROVIDER`/`LLM_MODEL`/`LLM_BASE_URL`/`LLM_API_KEY` :
  aucune définie.

Ce dernier point signifie que la Phase 12 (exécution LLM réelle)
rencontrera très probablement le blocage documenté par la tâche elle-même
(« BLOCKER — REAL LLM NOT EXECUTED ») — noté ici par avance, pour
transparence, pas comme un renoncement anticipé : les phases 1 à 11 et
18-19 (RAG sémantique, catalogue étendu, SP1 enrichi, tests) ne dépendent
pas d'un LLM réel et seront menées à terme indépendamment de ce blocage.
