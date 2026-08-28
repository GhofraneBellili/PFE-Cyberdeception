# Manifeste des captures — Chapitre 4

Aucune capture n'est fabriquée pour un module absent. Le statut
`AVAILABLE` signifie que le fichier PNG existe réellement dans
`docs/chapter4/screenshots/`, généré de façon reproductible par
`tools/chapter4_figures/` à partir des sorties réelles du dépôt (jamais
une valeur inventée) ; `READY_FOR_SCREENSHOT` signifie qu'un fichier de
sortie réel existe et qu'une commande précise permet de produire la
figure, mais que le PNG n'a pas encore été généré ;
`NOT_AVAILABLE` signifie que la donnée source elle-même n'existe pas
encore (aucune figure ne peut en être tirée sans fabrication).

**Renumérotation (réf. tâche « captures utiles au chapitre 4 »)** : la
liste avait été réduite à **C1–C7** (auparavant C1–C8), puis une capture
**C8** a été réintroduite (réf. tâche « separate knowledge and
organization capabilities » §18) pour représenter explicitement la
distinction OFFLINE/ONLINE — sans lien avec l'ancienne C8 (SP3), qui reste
hors périmètre. SP3 détaillé, front de Pareto, réduction de risque et
`Y*` restent prioritairement pour le chapitre 5 — aucune capture dédiée
ne leur est réservée ici, même si les modules correspondants
(`risk_engine.py`, `optimizer.py`) sont implémentés et testés (voir
`FINAL_TECHNICAL_REPORT.md`, section 4.4.3 et 4.4.4).

**Source de vérité technique désormais `FINAL_TECHNICAL_REPORT.md`**
(structure A–L par sous-section, table de traçabilité). Voir aussi
`ADMISSIBILITY_EVIDENCE_AUDIT.md` pour l'audit documentaire complet ayant
permis d'obtenir le candidat admissible réel de C3.

## Capture C1 — Organisation réelle du projet

```
Status: AVAILABLE
Module: (aucun module de code — structure du dépôt)
Fichier de sortie: docs/chapter4/outputs/architecture_tree.txt
Générateur: tools/chapter4_figures/c1_architecture.py (python -m tools.chapter4_figures.c1_architecture)
Capture: docs/chapter4/screenshots/01_architecture/architecture_tree.png (1900×3420 px, fond blanc)
Ce qui est visible: src/ (24 modules), tools/deception_kb/ (couche offline KB déception), tools/attack_kb/ (couche offline corpus RAG ATT&CK), tools/rag/ (builder offline de l'index RAG persisté), data/deception/ (catalogue + mapping réels + staging résumé), examples/ (17 scripts), tests/ (résumé), docs/chapter4/ (rapports + outputs résumé). Compteurs RECALCULÉS automatiquement à chaque génération (réf. tâche « maturation technique finale » §29, docs/chapter4/outputs/module_counts.json) — jamais retapés à la main.
Rôle dans le chapitre 4: Section 4.1.2 — Organisation du projet.
```

## Capture C2 — Fiche d'un mécanisme réel du catalogue

```
Status: AVAILABLE
Module: data/deception/deception_catalog.json (tools/deception_kb/catalog_builder.py)
Fichier de sortie: data/deception/deception_catalog.json (mécanisme "D3-DNR")
Générateur: tools/chapter4_figures/c2_mechanism.py (python -m tools.chapter4_figures.c2_mechanism)
Capture: docs/chapter4/screenshots/02_knowledge/deception_mechanism.png (1946×1450 px, fond blanc)
Ce qui est visible: id, name, description, target_artifacts, possible_placements, required_asset_types (D3-DNR : file_server, web_application_server — renseigné après audit), interaction_mechanism (dérivé des relations ATT&CK réelles), version, un extrait de preuve documentaire (source + passage du kb-article D3FEND).
Rôle dans le chapitre 4: Section 4.3.3 — Base de connaissances de cyberdéception.
Note: D3-DNR choisi de préférence (plutôt que D3-DUC/D3-DF) car il possède des propriétés d'admissibilité réellement renseignées après l'audit documentaire (docs/chapter4/ADMISSIBILITY_EVIDENCE_AUDIT.md) — required_asset_types traçable à une phrase précise du kb-article D3FEND, jamais inventé.
```

## Capture C3 — Réduction runtime de SP1 (D_knowledge → D_org → D_i → C_i_h)

```
Status: AVAILABLE
Module: src/admissibility.py, src/organization_catalog.py
Fichier de sortie: docs/chapter4/outputs/sp1_runtime_statistics.json (chiffres de réduction) + sp1_extended_real_example.json (candidats) — catalogue de connaissances réel (51 mécanismes), catalogue OPÉRATIONNEL d'une organisation d'exemple (examples/data/organization_deception_catalog.json, 42 référencés/30 activés), mapping réel (591 relations)
Générateur: tools/chapter4_figures/c3_sp1.py (python -m tools.chapter4_figures.c3_sp1)
Capture: docs/chapter4/screenshots/03_sp1/sp1_real_result.png (fond blanc)
Ce qui est visible: un entonnoir de réduction séquentielle réel (couples évalués → après mapping → après organization → après Autorise → après PrerequisSatisfaits → C_i_h final), puis le tableau des 46 candidats réellement admissibles (Occurrence/Mécanisme/Emplacement), et la liste des 9 mécanismes admissibles distincts sur 9 occurrences non terminales couvertes.
Rôle dans le chapitre 4: Section 4.4.1 — Construction du domaine admissible (SP1, module runtime).
Note pédagogique (réf. tâche « separate knowledge and organization capabilities ») : la figure ne montre plus « seuls les mécanismes suffisamment documentés par D3FEND sont utilisables » — elle montre au contraire que l'admissibilité dépend exclusivement du profil OPÉRATIONNEL fourni par l'organisation (examples/build_organization_catalog_example.py), appliqué au runtime sur le graphe/SI courants, jamais pré-calculé hors ligne.
```

## Capture C8 — Architecture OFFLINE / ONLINE

```
Status: AVAILABLE
Module: (diagramme d'architecture — src/organization_catalog.py, src/admissibility.py, src/orchestrator.py)
Fichier de sortie: docs/chapter4/outputs/catalog_statistics.json + sp1_runtime_statistics.json (compteurs réels affichés dans les blocs)
Générateur: tools/chapter4_figures/c8_offline_online.py (python -m tools.chapter4_figures.c8_offline_online)
Capture: docs/chapter4/screenshots/01_architecture/offline_online_architecture.png (fond blanc)
Ce qui est visible: bloc OFFLINE (ATT&CK/D3FEND/Engage/littérature → Knowledge Base : catalogue de connaissances 51 mécanismes, M_i,d 591 relations, index RAG) et bloc ONLINE (catalogue opérationnel de l'organisation + inventaire SI/topologie + graphe d'attaque courant → SP1 → C_i_h → SP2 → SP3 → optimizer → Y*), avec la note explicite qu'aucun appel LLM n'a lieu pendant l'optimisation et que le budget n'intervient jamais dans SP1.
Rôle dans le chapitre 4: nouvelle section « Préparation hors ligne vs exécution en ligne » de FINAL_TECHNICAL_REPORT.md.
```

## Capture C4 — Architecture RAG contextuelle (SP2)

```
Status: AVAILABLE
Module: src/rag_candidate_context.py / src/rag_query_builder.py / src/rag_evidence.py / src/reranker.py / src/rag_indexer.py
Fichiers de sortie: docs/chapter4/outputs/rag_candidate_context_example.json, rag_queries_example.json, rag_evidence_bundle_example.json (produits par python -m examples.rag_sp2_context_example, candidat réel admissible T1566@WS01/EAC0009/mailbox-ws01)
Générateur: tools/chapter4_figures/c4_rag.py (python -m tools.chapter4_figures.c4_rag)
Capture: docs/chapter4/screenshots/04_rag/rag_architecture.png (fond blanc)
Ce qui est visible: diagramme d'architecture OFFLINE (ATT&CK/D3FEND/Engage/littérature -> chunking+métadonnées -> embeddings sémantiques -> index vectoriel FAISS, 1306 chunks réels, BAAI/bge-small-en-v1.5) / ONLINE (candidat SP1 -> RagCandidateContext -> Q_realism/Q_interaction/Q_effect -> retrieval large -> reranking contextuel [cross-encoder/ms-marco-MiniLM-L-6-v2, réellement exécuté] -> diversification -> CandidateEvidenceBundle -> LLM), avec la requête Q_realism réellement construite pour le candidat et les compteurs réels de preuves par famille (realism=5, interaction=5, effect=5).
Rôle dans le chapitre 4: Section 4.4.2 — SP2 : RAG contextuel + LLM.
Remplace: l'ancienne capture C4 (tableau plat de retrieval TF-IDF seul, docs/chapter4/screenshots/04_rag/rag_retrieval.png), qui ne représentait plus l'architecture réellement implémentée depuis l'introduction du RAG sémantique puis du RAG contextuel par famille — fichier retiré du dépôt.
```

## Capture C5 — Annotation structurée provenant du vrai LLM

```
Status: NOT_AVAILABLE
Module: src/annotator_llm.py (RealLlmAnnotator — code implémenté et testé par mocks HTTP, tests/test_annotator_llm.py::TestRealLlmAnnotator, jamais exécuté contre un service réel)
Fichier de sortie attendu: docs/chapter4/outputs/llm_annotation_real.json (NON généré dans cet environnement)
Commande pour produire cette capture: LLM_PROVIDER=ollama LLM_MODEL=<modele_local> python -m examples.annotator_llm_real_example (ou LLM_PROVIDER=openai_compatible LLM_MODEL=<modele> LLM_BASE_URL=<url> LLM_API_KEY=<cle>) — voir FINAL_TECHNICAL_REPORT.md section 4.4.2.
Rôle dans le chapitre 4: Section 4.4.2 — Évaluation contextuelle par RAG et LLM (SP2).
Raison du blocage: aucun provider LLM réel n'est exploitable dans cet environnement (ni Ollama local, ni endpoint OpenAI-compatible configuré — voir TECHNOLOGIES.md). examples/annotator_llm_real_example.py récupère désormais le candidat DIRECTEMENT depuis la sortie réelle de SP1 (T1039@FS01/D3-DNR/shared-drive, C3) — plus aucun candidat codé manuellement — mais détecte l'absence de provider et n'écrit AUCUN fichier (anti-fabrication, §20).
Repli documenté (PAS cette capture) : docs/chapter4/outputs/llm_annotation_example.json, produit par le repli déterministe rule_based_stub (examples/annotator_llm_example.py) — explicitement marqué comme tel, jamais présenté comme cette capture C5.
```

## Capture C6 — Table figée résultant de cette annotation

```
Status: NOT_AVAILABLE
Module: src/annotation_validator.py (freeze_candidate — code réel, non exécuté avec une annotation LLM réelle)
Fichier de sortie attendu: docs/chapter4/outputs/frozen_annotations_real.csv / .json (NON générés dans cet environnement)
Commande pour produire cette capture (commande unique, une fois C5 obtenue): python -m examples.freeze_real_example — lit llm_annotation_real.json, calcule Realisme/P_interaction/P_engagement/Effet_prog/DE PAR CODE (jamais par le LLM), écrit frozen_annotations_real.json/.csv. Refuse explicitement si llm_annotation_real.json est absent (testé, tests/test_freeze_real_example.py).
Rôle dans le chapitre 4: Section 4.5.2 — Conservation des annotations et des preuves.
Raison du blocage: dépend directement de C5 (aucune annotation LLM réelle disponible dans cet environnement).
Repli documenté (PAS cette capture) : docs/chapter4/outputs/frozen_annotations_example.csv, qui gèle des annotations produites par le repli déterministe rule_based_stub — les FORMULES d'agrégation (Realisme/P_interaction/P_engagement/Effet_prog/DE) y sont réelles, mais pas les scores sémantiques sous-jacents.
```

## Capture C7 — Orchestration / artefacts d'un run complet

```
Status: AVAILABLE
Module: src/orchestrator.py (RAG contextuel désormais chemin de référence unique, réf. tâche « maturation technique finale du chapitre 4 »)
Fichier de sortie: docs/chapter4/outputs/pipeline_example.txt + runs/chapter4-example/*.json (régénérable, non versionné)
Générateur: tools/chapter4_figures/c7_pipeline.py (python -m tools.chapter4_figures.c7_pipeline)
Capture: docs/chapter4/screenshots/09_pipeline/pipeline_result.png (2410×1858 px, fond blanc)
Ce qui est visible: run_id, candidats évalués/admissibles, la liste des 11 étapes exécutées (Candidats [SP1], Contexte RAG [RagCandidateContext], Requêtes Q_realism/Q_interaction/Q_effect, Retrieval+reranking+diversification, CandidateEvidenceBundle, Annotations [SP2], Table figée, Coûts, Plan, Risques, Manifest) sous forme de coches — MÊME pipeline que C4, jamais une architecture différente — et la liste des fichiers réellement produits (input_manifest.json, candidates.json, candidate_contexts.json, rag_queries.json, evidence_bundles.json, annotations_raw.json, annotations_frozen.json, costs.json, pareto.json, deployment_plan.json, deployment_report.json, risks.json, run_manifest.json).
Rôle dans le chapitre 4: Section 4.5.1 — Enchaînement des traitements.
Note: exécuté sur les DONNÉES RÉELLES du projet (catalogue 51 mécanismes, mapping 591 relations, catalogue opérationnel réel, index RAG persisté 1306 chunks, reranker cross-encoder réel) et une instance volontairement petite (réf. tâche §25/§26). Le repli déterministe rule_based_stub (aucun provider LLM réel disponible, explicitement labellisé technical integration fallback) sert à démontrer l'intégration technique bout-en-bout. Les valeurs numériques de risque et le front de Pareto (réservés au chapitre 5) ne sont volontairement PAS mis en avant dans cette figure — seule l'étape "Risques" est cochée comme complétée.
```

## Notes de suivi

- Ce manifeste est mis à jour à chaque module réellement livré (code +
  tests + sortie réelle), jamais en anticipation.
- Le front de Pareto et le plan de déploiement `Y*` détaillé (analyse
  quantitative), la réduction de risque et SP3 détaillé restent
  volontairement réservés au chapitre 5 (résultats/validation) — non
  couverts par C1–C7, même si les modules correspondants sont
  implémentés et testés.
- C5 et C6 resteront `NOT_AVAILABLE` tant qu'une exécution locale avec un
  vrai provider LLM (Ollama ou endpoint OpenAI-compatible) n'aura pas été
  effectuée par l'utilisateur — le code est prêt, testé, et documenté
  (`FINAL_TECHNICAL_REPORT.md`, section 4.4.2) ; seule l'exécution manque.
- **C1, C2, C3, C4, C7, C8 sont désormais `AVAILABLE`** : les 6 PNG
  existent réellement dans `docs/chapter4/screenshots/`, générés de façon
  reproductible par `tools/chapter4_figures/` (`python -m
  tools.chapter4_figures.generate_all` régénère les 6 en une commande) —
  fond blanc, texte noir/gris, aucune capture de terminal brute, aucune
  valeur inventée (chaque figure lit un fichier de sortie réel du dépôt).
  Dépendance `matplotlib` (groupe optionnel `docs` de `pyproject.toml`),
  utilisée uniquement par cet outil de documentation — jamais importée
  par `src/`.
- Historique : l'ancienne numérotation (C1–C8, avec C4=chunks/C5=retrieval
  séparées, C6=annotation stub, C7=table figée stub, C8=SP3) est
  remplacée par celle ci-dessus. Les sorties de l'ancienne C6/C7 restent
  documentées dans le corps du rapport (repli `rule_based_stub`,
  explicitement non présentées comme C5/C6 réelles).
