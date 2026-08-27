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
Status: AVAILABLE
Module: (aucun module de code — structure du dépôt)
Fichier de sortie: docs/chapter4/outputs/architecture_tree.txt
Générateur: tools/chapter4_figures/c1_architecture.py (python -m tools.chapter4_figures.c1_architecture)
Capture: docs/chapter4/screenshots/01_architecture/architecture_tree.png (1900×2475 px, fond blanc)
Ce qui est visible: src/ (15 modules), tools/deception_kb/ (couche offline, catalog_builder.py/mapping_builder.py), data/deception/ (catalogue + mapping réels + staging résumé), examples/ (16 scripts), tests/ (21 fichiers, résumé), docs/chapter4/ (rapports + outputs résumé).
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

## Capture C3 — Résultat SP1 réel

```
Status: AVAILABLE
Module: src/admissibility.py
Fichier de sortie: docs/chapter4/outputs/sp1_real_example.txt (résumé) + sp1_real_example.json (complet) — catalogue et mapping RÉELS, après audit des prérequis
Générateur: tools/chapter4_figures/c3_sp1.py (python -m tools.chapter4_figures.c3_sp1)
Capture: docs/chapter4/screenshots/03_sp1/sp1_real_result.png (1960×1602 px, fond blanc)
Ce qui est visible: tableau des 12 candidats (Occurrence/Mécanisme/Emplacement/Autorise/PrerequisSatisfaits/Pertinent/Décision), la ligne ADMISSIBLE réelle surlignée (T1039@FS01 / D3-DNR / shared-drive), et la synthèse (12 candidats bruts, 1 admissible, 11 rejetés).
Rôle dans le chapitre 4: Section 4.4.1 — Construction du domaine admissible (SP1).
Note pédagogique: pour D3-DUC et D3-DF, RequirementsSatisfied="undetermined" (aucune preuve documentaire suffisante) — C_{i,h} vide pour ces deux mécanismes ; pour D3-DNR, RequirementsSatisfied s'évalue réellement pass/fail grâce à l'audit documentaire (required_asset_types renseigné). La figure montre ce contraste ligne par ligne, pas seulement le résultat admissible isolé.
```

## Capture C4 — Récupération documentaire RAG

```
Status: AVAILABLE
Module: src/rag_indexer.py / src/rag_retriever.py
Fichier de sortie: docs/chapter4/outputs/rag_retrieval_example.txt (résultat de récupération)
Générateur: tools/chapter4_figures/c4_rag.py (python -m tools.chapter4_figures.c4_rag)
Capture: docs/chapter4/screenshots/04_rag/rag_retrieval.png (2050×1084 px, fond blanc)
Ce qui est visible: la requête, un index réel de 124 chunks (44 D3FEND, 62 Engage, 18 littérature), le classement des 5 premiers résultats (Rang/Score/Type/chunk_id/Extrait) — premier résultat "d3fend:D3-DUC:0" (Decoy User Credential), pertinent pour la requête.
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
Status: AVAILABLE
Module: src/orchestrator.py
Fichier de sortie: docs/chapter4/outputs/pipeline_example.txt + runs/chapter4-example/*.json (régénérable, non versionné)
Générateur: tools/chapter4_figures/c7_pipeline.py (python -m tools.chapter4_figures.c7_pipeline)
Capture: docs/chapter4/screenshots/09_pipeline/pipeline_result.png (2067×1654 px, fond blanc)
Ce qui est visible: run_id, candidats évalués/admissibles, la liste des 8 étapes exécutées (Candidats, Retrieval, Annotations, Table figée, Coûts, Plan, Risques, Manifest) sous forme de coches, et la liste des 11 fichiers réellement produits (input_manifest.json, candidates.json, retrieval.json, annotations_raw.json, annotations_frozen.json, costs.json, pareto.json, deployment_plan.json, deployment_report.json, risks.json, run_manifest.json).
Rôle dans le chapitre 4: Section 4.5.1 — Enchaînement des traitements.
Note: cette exécution utilise le repli déterministe rule_based_stub (aucun provider LLM réel disponible) — sert à démontrer l'intégration technique bout-en-bout. Les valeurs numériques de risque et le front de Pareto (réservés au chapitre 5) ne sont volontairement PAS mis en avant dans cette figure — seule l'étape "Risques" est cochée comme complétée.
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
- **C1, C2, C3, C4, C7 sont désormais `AVAILABLE`** : les 5 PNG existent
  réellement dans `docs/chapter4/screenshots/`, générés de façon
  reproductible par `tools/chapter4_figures/` (`python -m
  tools.chapter4_figures.generate_all` régénère les 5 en une commande) —
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
