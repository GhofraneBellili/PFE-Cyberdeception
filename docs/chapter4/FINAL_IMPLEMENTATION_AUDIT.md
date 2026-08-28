# Audit final de l'implémentation — Chapitre 4

Réf. tâche « dernière passe de finition technique du chapitre 4 », §25.
Ce document est l'audit final, item par item, de l'architecture décrite
dans `docs/chapter4/FINAL_TECHNICAL_REPORT.md`. Chaque ligne cite une
preuve VÉRIFIABLE dans le dépôt (fichier, test, ou sortie réelle) — aucun
`PASS` n'est donné sans preuve. Statuts autorisés : `PASS` (vérifié
réellement, preuve reproductible), `LIMITATION` (comportement correct
mais volontairement restreint, documenté comme tel), `NOT_APPLICABLE`
(hors périmètre de cette tâche).

Vérifié à jour au commit list au bas de ce document — `pytest -v` vert
(voir §23 de la tâche), aucun appel réseau/LLM/téléchargement dans la
suite standard.

| # | Item | Expected | Observed | Status | Evidence |
|---|---|---|---|---|---|
| 1 | SP1 runtime | `build_admissibility_report` reçoit le graphe/SI/catalogues COURANTS à chaque appel, jamais pré-calculé | Vérifié : même `D_org`+`M_{i,d}`, deux graphes différents ⇒ `C_i,h` différents | PASS | `src/admissibility.py::build_admissibility_report` ; `tests/test_admissibility.py::TestAdmissibilityReport::test_criterion_j_same_organization_different_graph_different_c_i_h` |
| 2 | Séparation catalogue de connaissances / catalogue organisationnel | `Autorise`/`PrerequisSatisfaits` viennent EXCLUSIVEMENT du catalogue OPÉRATIONNEL, jamais de `DeceptionMechanism.admissibility_profile` | Vérifié : `admissibility_profile` n'est lu nulle part dans `src/admissibility.py` (champ hérité documenté) | PASS | `src/organization_catalog.py`, `src/schemas.py::OrganizationDeceptionCapability`, `tests/test_admissibility.py` (critères A-L) |
| 3 | 51 mécanismes au catalogue de connaissances | 9 D3FEND + 15 MITRE Engage + 27 littérature = 51 | Confirmé par inspection directe du catalogue réel | PASS | `data/deception/deception_catalog.json` (51 entrées, 27 `LIT-*`, 9 `D3-*`, 15 `EAC*`) ; `docs/chapter4/outputs/catalog_statistics.json` |
| 4 | 18/51 mécanismes mappés | 18 mécanismes ont ≥ 1 relation `M_{i,d}` tracée, 33 n'en ont aucune | Confirmé | PASS | `docs/chapter4/outputs/catalog_statistics.json` (`mechanisms_with_attack_mapping: 18`, `mechanisms_without_attack_mapping: 33`) |
| 5 | Corpus RAG à 4 sources | ATT&CK + D3FEND + Engage + littérature combinées dans le même index | Confirmé, 4 `source_type` distincts présents | PASS | `docs/chapter4/outputs/rag_index_manifest.json` (`chunk_count_by_source`) |
| 6 | 1306 chunks au total | 1157 ATT&CK + 44 D3FEND + 62 Engage + 43 littérature = 1306 | Confirmé arithmétiquement et par inspection du manifest persisté | PASS | `docs/chapter4/outputs/rag_index_manifest.json` |
| 7 | Index sémantique persisté OFFLINE, rechargé ONLINE sans ré-encodage | `save_rag_index`/`load_rag_index`, round-trip retrieval identique, `FakeEmbedder.encode` jamais rappelé au chargement | Vérifié par test (monkeypatch faisant échouer l'encodeur si appelé pendant `load_rag_index`) | PASS | `src/rag_index_store.py` ; `tests/test_rag_index_store.py::TestLoadRagIndexRoundTrip` |
| 8 | Connaissance ATT&CK runtime indépendante du fichier brut | `RagCandidateContext.technique_name` renseigné SANS `enterprise-attack.json` présent sur disque | Vérifié empiriquement : fichier brut renommé/absent, `examples/orchestrator_example.py` ET la suite complète `pytest` (817 tests) restent verts, `technique_name` toujours renseigné (271 techniques chargées depuis le staging) | PASS | `src/attack_runtime_knowledge.py` ; `tests/test_attack_runtime_knowledge.py` ; `tests/test_rag_candidate_context.py::test_technique_name_populated_from_attack_staging_without_raw_file` ; `tests/test_rag_sp2_separation.py::TestAttackRuntimeKnowledgeIndependentOfRawStixParsing` |
| 9 | 3 requêtes SP2 (Q_realism/Q_interaction/Q_effect) | `build_rag_queries` retourne exactement 3 clés, textes distincts | Confirmé | PASS | `src/rag_query_builder.py` ; `tests/test_rag_query_builder.py` ; `docs/chapter4/outputs/rag_queries_example.json` |
| 10 | Cross-encoder reranker réel | Modèle `sentence-transformers.CrossEncoder` réellement téléchargé et exécuté, jamais le LLM principal | Confirmé : score correct sur une paire pertinente/non pertinente, chargé une seule fois par run | PASS | `src/reranker.py` ; `tests/test_reranker.py::TestCrossEncoderRerankerReal` (`pytest -m real_reranker`) ; `docs/chapter4/outputs/rag_evidence_bundle_example.json` |
| 11 | `CandidateEvidenceBundle` structuré et tracé | `{candidate_id, realism, interaction, effect}`, chaque preuve avec scores intermédiaires + provenance | Confirmé | PASS | `src/rag_evidence.py` ; `docs/chapter4/outputs/rag_evidence_bundle_example.json` ; `runs/chapter4-example/evidence_bundles.json` |
| 12 | Preuves regroupées par famille transmises à l'annotateur | `AnnotationContext.evidence_by_family` non `None`, 3 familles avec des ensembles de sources distincts | Vérifié : `run_pipeline` transmet des jeux de sources réellement différents par famille (pas un bloc générique dupliqué) | PASS | `tests/test_orchestrator.py::TestThreeFamiliesGenuinelyUsed` |
| 13 | `DE` gelé par code, jamais par le LLM | `annotation_validator.py` calcule Realisme/P_interaction/P_engagement/Effet_prog/DE ; le LLM ne produit que les 11 scores bruts | Confirmé | PASS | `src/annotation_validator.py` ; `runs/chapter4-example/annotations_frozen.json` |
| 14 | SP3 — propagation déterministe | Reproduit exactement l'ancre analytique du chapitre 3 (§20 CLAUDE.md) | Vert, tolérance `1e-4` | PASS | `src/risk_engine.py` ; `tests/test_risk_engine.py::test_reference_example` |
| 15 | Optimiseur — énumération exhaustive | Résout `(P)` par énumération, jamais un solveur externe, jamais de Top-K arbitraire | Confirmé sur l'exemple réel (6 configurations énumérées, 4 faisables) | PASS | `src/optimizer.py` ; `runs/chapter4-example/pareto.json` |
| 16 | Reporter — transformation `y*` → `Y*` | Reprend les valeurs déjà calculées, ne recalcule rien | Confirmé | PASS | `src/reporter.py` ; `runs/chapter4-example/deployment_report.json` |
| 17 | Orchestrateur — pipeline contextuel unique | `run_pipeline` n'utilise plus l'ancien chemin à requête unique ; RAG contextuel = seul chemin de référence | Confirmé par analyse statique des imports (aucun `retrieve`/`retrieve_semantic`/`retrieve_hybrid` importé) | PASS | `src/orchestrator.py` ; `tests/test_orchestrator.py::TestRunPipelineContextualRag` |
| 18 | Traçabilité complète du run | `run_manifest.json` porte RAG/LLM/catalogues ; 13 fichiers par run, tous indexés/audités | Confirmé, liste de fichiers correspond exactement à la documentation | PASS | `runs/chapter4-example/run_manifest.json` ; `tests/test_orchestrator.py::TestRunManifestTraceability` |
| 19 | Provider LLM réel techniquement exécutable | `detect_provider()` détecte un endpoint OpenAI-compatible réellement configuré et joignable, `RealLlmAnnotator` produit les 11 sous-métriques valides sur un candidat SP2 contextuel réel | Confirmé : `LLM_PROVIDER=openai_compatible`, `LLM_MODEL=openai/gpt-oss-120b` (Groq) — smoke test contrôlé exécuté avec succès (`RagCandidateContext` → 3 requêtes → retrieval → reranking → `CandidateEvidenceBundle` → `RealLlmAnnotator` → 11 annotations), scores/confidences dans [0,1], `evidence_ids` tous traçables au bundle réellement récupéré, aucune métrique dérivée (Realisme/P_interaction/P_engagement/Effet_prog/DE/Gamma/risque/coût/budget) produite par le LLM. Ceci est une preuve d'intégration technique, **pas** une validation expérimentale quantitative (réservée au chapitre 5) | PASS | `src/llm_provider.py` (correctif `User-Agent`, requis face au WAF Cloudflare de l'endpoint Groq) ; `tests/test_annotator_llm_real_integration.py` (`pytest -m real_llm`) ; `docs/chapter4/outputs/groq_real_llm_smoke_test.json` |

## Limites finales du chapitre 4 (réf. tâche §26)

Après cette passe, les limites principales restantes sont :

1. **18/51 mécanismes** du catalogue de connaissances ont actuellement une relation `M_{i,d}` tracée (33 n'en ont aucune) — non comblé artificiellement (réf. tâche §18).
2. Le catalogue organisationnel (`examples/data/organization_deception_catalog.json`) reste une **configuration d'étude de cas**, pas des données fournies par une organisation réelle.
3. `Pertinent` reste opérationnalisé par une **relation topologique directe** (même actif, ou adjacence SI à un saut) — extension multi-hop hors périmètre (réf. tâche §19).
4. L'optimiseur reste une **énumération exhaustive**, exacte sur petites instances, non dimensionnée pour un grand espace combinatoire (réf. tâche §20).
5. Un **smoke test technique contrôlé** du provider LLM réel (Groq, `openai/gpt-oss-120b`) a été exécuté avec succès sur un unique candidat SP2 contextuel (`docs/chapter4/outputs/groq_real_llm_smoke_test.json`) — cela démontre que l'intégration fonctionne réellement, mais **aucune campagne expérimentale** (plusieurs candidats, comparaison de modèles, mesure de qualité d'annotation) n'a été menée : cela reste réservé au chapitre 5.
6. La **validation quantitative comparative du RAG** (Recall@5/MRR@5/nDCG@5 contre le corpus élargi et le pipeline reranké) est reportée au chapitre 5.

Aucune autre limitation n'est ajoutée : les points déjà résolus par les passes précédentes (RAG à requête unique, dépendance runtime au fichier brut ATT&CK, persistance de l'index sémantique, ambiguïté du statut de l'index lexical, absence de preuve d'exécution du provider LLM réel) ne sont plus des limites.

## CHAPTER 4 IMPLEMENTATION FROZEN

**YES** — aucun bug bloquant découvert durant cette passe. L'architecture et le code du chapitre 4 sont considérés stables. Les développements suivants (validation, expérimentation, chapitre 5) sont hors périmètre de ce document.
