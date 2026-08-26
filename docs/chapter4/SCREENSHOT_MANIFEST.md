# Manifeste des captures — Chapitre 4

Aucune capture n'est fabriquée pour un module absent. Le statut
`READY_FOR_SCREENSHOT` signifie qu'un fichier de sortie réel existe et
qu'une commande précise permet de reproduire la capture ; aucun outil de
capture d'écran automatisé n'est disponible dans cet environnement, donc
aucun statut `AVAILABLE` (PNG déjà produit) n'est déclaré tant qu'une
capture n'a pas été prise manuellement par l'utilisateur.

## Capture C1 — Architecture / arborescence simplifiée du projet

```
Status: READY_FOR_SCREENSHOT
Module: (aucun module de code — structure du dépôt)
Fichier de sortie: docs/chapter4/outputs/architecture_tree.txt
Commande: voir docs/chapter4/outputs/architecture_tree.txt (généré depuis un script Python ponctuel listant récursivement le dépôt, répertoires .git/.venv/__pycache__ exclus, répertoires de données volumineuses résumés par un nombre de fichiers)
Capture: docs/chapter4/screenshots/01_architecture/architecture_tree.png (à produire manuellement à partir du fichier texte)
Ce qui doit être visible: src/ (modules implémentés vs stubs), tools/deception_kb/ (couche offline), data/deception/ (staging + registre littérature), tests/.
Rôle dans le chapitre 4: Section 4.2 — Architecture logicielle.
```

## Capture C2 — Exemple d'une fiche réelle de mécanisme de cyberdéception

```
Status: NOT_IMPLEMENTED
Module: src/knowledge_deception.py (chargeur implémenté et testé, mais aucun catalogue réel à charger)
Fichier de sortie: (absent)
Commande: (absente)
Capture: (absente)
Ce qui doit être visible: un DeceptionMechanism réel (name, description, target_artifacts, ...).
Rôle dans le chapitre 4: Section 4.3 — Préparation des données et connaissances.
Raison du blocage: data/deception/deception_catalog.json n'existe pas encore — sa composition dépend d'une OPEN_DECISION non résolue (voir tools/deception_kb/README.md). Ne pas fabriquer un exemple synthétique présenté comme réel (règle anti-fabrication).
```

## Capture C3 — Résultat réel de SP1

```
Status: NOT_IMPLEMENTED
Module: src/admissibility.py (stub, non implémenté)
Fichier de sortie: (absent)
Commande: (absente)
Capture: (absente)
Ce qui doit être visible (une fois implémenté): Occurrence ; Mecanisme ; Emplacement ; Decision (admissible/rejeté), avec Autorise/PrerequisSatisfaits/Pertinent.
Rôle dans le chapitre 4: Section 4.4 — Implémentation de SP1.
```

## Capture C4 — Exemple de chunks / preuves disponibles pour le RAG

```
Status: NOT_IMPLEMENTED
Module: src/rag_indexer.py (stub, non implémenté)
Raison: RAG non implémenté. Note : les preuves documentaires versionnées existent déjà côté offline (data/deception/staging/literature_evidence_seed_1.2.json, 18 passages page_verified ; D3FEND source_evidence), mais elles ne sont pas encore chunkées/indexées pour un RAG runtime.
Rôle dans le chapitre 4: Section 4.5 — Implémentation du LLM et du RAG.
```

## Capture C5 — Résultat réel du retrieval

```
Status: NOT_IMPLEMENTED
Module: src/rag_retriever.py (stub, non implémenté)
Rôle dans le chapitre 4: Section 4.5 — Implémentation du LLM et du RAG.
```

## Capture C6 — Exemple réel d'annotation structurée du LLM

```
Status: NOT_IMPLEMENTED
Module: src/annotator_llm.py (stub, non implémenté)
Rôle dans le chapitre 4: Section 4.5 — Implémentation du LLM et du RAG.
```

## Capture C7 — Table réelle des annotations figées / DE

```
Status: NOT_IMPLEMENTED
Module: src/annotation_validator.py (stub, non implémenté) ; calcul déterministe SP2 (non implémenté)
Rôle dans le chapitre 4: Section 4.6 — Moteurs déterministes et optimisation.
```

## Capture C8 — Sortie simple du moteur SP3 ou du pipeline complet

```
Status: NOT_IMPLEMENTED
Module: src/risk_engine.py (stub, non implémenté)
Rôle dans le chapitre 4: Section 4.6 — Moteurs déterministes et optimisation.
Condition de déblocage: test_reference_example (ancre §11) doit passer avant toute capture de ce module.
```

## Notes de suivi

- Ce manifeste est mis à jour à chaque module réellement livré (code +
  tests + sortie réelle), jamais en anticipation.
- Le front de Pareto et le plan de déploiement `Y*` final sont
  volontairement réservés au chapitre 5 (résultats/validation), même une
  fois l'optimiseur implémenté, sauf besoin ponctuel de illustrer un
  mécanisme technique au chapitre 4.
