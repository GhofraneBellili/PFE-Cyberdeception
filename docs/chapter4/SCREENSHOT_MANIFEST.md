# Manifeste des captures — Chapitre 4

Aucune capture n'est fabriquée pour un module absent. Le statut
`READY_FOR_SCREENSHOT` signifie qu'un fichier de sortie réel existe et
qu'une commande précise permet de reproduire la capture ; aucun outil de
capture d'écran automatisé n'est disponible dans cet environnement, donc
aucun statut `AVAILABLE` (PNG déjà produit) n'est déclaré tant qu'une
capture n'a pas été prise manuellement par l'utilisateur.

**Renumérotation (réf. tâche « captures utiles au chapitre 4 »)** : la
liste est désormais **C1–C7** (auparavant C1–C8). SP3 détaillé, front de
Pareto, réduction de risque et `Y*` restent prioritairement pour le
chapitre 5 — aucune capture dédiée ne leur est réservée ici, même si les
modules correspondants (`risk_engine.py`, `optimizer.py`) sont
implémentés et testés (voir `FINAL_TECHNICAL_REPORT.md`, section 4.4.3 et
4.4.4).

**Source de vérité technique désormais `FINAL_TECHNICAL_REPORT.md`**
(structure A–L par sous-section, table de traçabilité). Voir aussi
`ADMISSIBILITY_EVIDENCE_AUDIT.md` pour l'audit documentaire complet ayant
permis d'obtenir le candidat admissible réel de C3.

## Capture C1 — Organisation réelle du projet

```
Status: READY_FOR_SCREENSHOT
Module: (aucun module de code — structure du dépôt)
Fichier de sortie: docs/chapter4/outputs/architecture_tree.txt
Commande: voir docs/chapter4/outputs/architecture_tree.txt (généré depuis un script Python ponctuel listant récursivement le dépôt, répertoires .git/.venv/.claude/__pycache__ exclus, répertoires de données volumineuses résumés par un nombre de fichiers)
Capture: docs/chapter4/screenshots/01_architecture/architecture_tree.png (à produire manuellement à partir du fichier texte)
Ce qui doit être visible: src/ (tous modules implémentés), tools/deception_kb/ (couche offline, y compris catalog_builder.py/mapping_builder.py), data/deception/ (staging + catalogue + mapping réels), examples/, tests/.
Rôle dans le chapitre 4: Section 4.1.2 — Organisation du projet.
```

## Capture C2 — Fiche d'un mécanisme réel du catalogue

```
Status: READY_FOR_SCREENSHOT
Module: data/deception/deception_catalog.json (tools/deception_kb/catalog_builder.py)
Fichier de sortie: data/deception/deception_catalog.json (mécanisme "D3-DUC")
Commande: python -m tools.deception_kb.catalog_builder
Capture: docs/chapter4/screenshots/02_knowledge/deception_mechanism.png (à produire manuellement — se limiter à un seul mécanisme, ex. D3-DUC, pas les 3 ni les preuves complètes)
Ce qui doit être visible: id, name, description, target_artifacts, interaction_mechanism (dérivé des relations ATT&CK réelles), admissibility_profile.allowed_location_types (D3-DUC : credential_store ; suggestion : montrer plutôt D3-DNR pour illustrer aussi required_asset_types, réellement renseigné après audit), un extrait d'evidence (source + passage), version.
Rôle dans le chapitre 4: Section 4.3.3 — Base de connaissances de cyberdéception.
Note: catalogue v1 volontairement restreint à 3 mécanismes (D3-DF, D3-DNR, D3-DUC) — seuls les concepts-feuilles D3FEND avec une relation ATT&CK directement tracée dans le staging. Après audit documentaire des prérequis (docs/chapter4/ADMISSIBILITY_EVIDENCE_AUDIT.md), D3-DF gagne "network_share" (allowed_location_types) et D3-DNR gagne required_asset_types=["web_application_server","file_server"] — les deux traçables à une phrase précise du kb-article D3FEND, jamais inventés.
```

## Capture C3 — Résultat SP1 réel

```
Status: READY_FOR_SCREENSHOT
Module: src/admissibility.py
Fichier de sortie: docs/chapter4/outputs/sp1_real_example.txt (résumé) + sp1_real_example.json (complet) — catalogue et mapping RÉELS, après audit des prérequis
Commande: python -m examples.sp1_real_example
Capture: docs/chapter4/screenshots/03_sp1/sp1_real_result.png (à produire manuellement depuis sp1_real_example.txt)
Ce qui doit être visible: D_i réellement peuplé depuis le mapping M_{i,d} matérialisé, décision par candidat (Autorise/PrerequisSatisfaits/Pertinent), la synthèse (12 candidats bruts, 1 admissible, 11 rejetés), ET la ligne ADMISSIBLE réelle : T1039@FS01 / D3-DNR / shared-drive.
Rôle dans le chapitre 4: Section 4.4.1 — Construction du domaine admissible (SP1).
Note pédagogique: pour D3-DUC et D3-DF, RequirementsSatisfied="undetermined" (aucune preuve documentaire suffisante) — C_{i,h} vide pour ces deux mécanismes ; pour D3-DNR, RequirementsSatisfied s'évalue réellement pass/fail grâce à l'audit documentaire (required_asset_types renseigné). La capture doit montrer ce contraste, pas seulement le résultat admissible isolé.
```

## Capture C4 — Récupération documentaire RAG

```
Status: READY_FOR_SCREENSHOT
Module: src/rag_indexer.py / src/rag_retriever.py
Fichier de sortie: docs/chapter4/outputs/rag_retrieval_example.txt (résultat de récupération) + rag_chunks_example.json (structure des chunks)
Commande: python -m examples.rag_example
Capture: docs/chapter4/screenshots/04_rag/rag_retrieval.png (à produire manuellement depuis rag_retrieval_example.txt)
Ce qui doit être visible: la requête, un index réel de 124 chunks (44 D3FEND, 62 Engage, 18 littérature), le classement Rang/Score/Type/chunk_id/Extrait — premier résultat "d3fend:D3-DUC:0" (Decoy User Credential), pertinent pour la requête.
Rôle dans le chapitre 4: Section 4.4.2 — Évaluation contextuelle par RAG et LLM (SP2).
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
Status: READY_FOR_SCREENSHOT
Module: src/orchestrator.py
Fichier de sortie: docs/chapter4/outputs/pipeline_example.txt + runs/chapter4-example/*.json (régénérable, non versionné)
Commande: python -m examples.orchestrator_example
Capture: docs/chapter4/screenshots/09_pipeline/pipeline_result.png (à produire manuellement depuis pipeline_example.txt)
Ce qui doit être visible: run_id, liste des fichiers écrits (input_manifest, candidates, retrieval, annotations_raw/frozen, costs, pareto, deployment_plan, deployment_report, risks, run_manifest), et le rapport Y* (occurrence/mécanisme/emplacement/coût/DE/risque avant-après).
Rôle dans le chapitre 4: Section 4.5.1 — Enchaînement des traitements.
Note: cette exécution utilise le repli déterministe rule_based_stub (aucun provider LLM réel disponible) — sert à démontrer l'intégration technique bout-en-bout, pas un résultat expérimental du chapitre 5.
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
  (`IMPLEMENTATION_REPORT.md`, section 4.4.2) ; seule l'exécution manque.
- Historique : l'ancienne numérotation (C1–C8, avec C4=chunks/C5=retrieval
  séparées, C6=annotation stub, C7=table figée stub, C8=SP3) est
  remplacée par celle ci-dessus. Les sorties de l'ancienne C6/C7 restent
  documentées dans le corps du rapport (repli `rule_based_stub`,
  explicitement non présentées comme C5/C6 réelles).
