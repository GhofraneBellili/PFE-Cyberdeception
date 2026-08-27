# Rapport technique d'implémentation — Chapitre 4

> Ce document est la matière technique directement exploitable pour
> rédiger le chapitre 4 du mémoire. Il diffère de `CLAUDE.md` (contrat
> scientifique / architecture de référence) : ici, seule l'implémentation
> **réellement présente et fonctionnelle** dans le dépôt est décrite.
> Aucune section n'est marquée « implémenté » sans code + tests qui
> passent. Une section absente est marquée `Status : NON IMPLEMENTE` et
> rien de plus n'est affirmé à son sujet.

## Invariant central du projet — le LLM hors du chemin d'exécution

**Le LLM n'intervient jamais dans le calcul du risque ni dans
l'optimisation.** Il annote hors ligne (SP2, section 6/7) ; ses sorties
sont validées puis figées (`freeze`) ; l'optimisation et le moteur de
risque (SP3) lisent ensuite exclusivement la table figée, sans jamais
rappeler le LLM. Cet invariant est vérifié par un test dédié pour chaque
module qui existe réellement (section 12) : ce test contrôle qu'il
n'importe jamais `src/annotator_llm.py` ni `src/rag_indexer.py`/
`src/rag_retriever.py`. **Tous les modules du chemin d'exécution
(`src/risk_engine.py`, `src/optimizer.py`, `src/annotator_llm.py`,
`src/annotation_validator.py`, `src/reporter.py`) sont désormais
implémentés et ce test est vert sur chacun d'eux**
(vérification par analyse `ast` de l'arbre syntaxique, jamais une
recherche de sous-chaîne). Au niveau de l'orchestrateur
(`src/orchestrator.py`), l'invariant est en outre vérifié dynamiquement :
l'annotateur n'est appelé qu'une seule fois par candidat admissible,
jamais pendant le coût/le risque/`(P)`/le rapport.

---

## 1. Architecture logicielle

État réel des modules `src/` (source de vérité : `wc -l`, pas une
déclaration d'intention) :

| Module | Lignes | Statut |
|---|---|---|
| `src/schemas.py` | 651 | **IMPLEMENTE** |
| `src/graph_builder.py` | 201 | **IMPLEMENTE** |
| `src/knowledge_attack.py` | 385 | **IMPLEMENTE** |
| `src/knowledge_deception.py` | 239 | **IMPLEMENTE** |
| `src/admissibility.py` | ~250 | **IMPLEMENTE** (SP1, périmètre petite instance) |
| `src/rag_indexer.py` | ~250 | **IMPLEMENTE** (chunks tracés + vecteurs TF-IDF hachés) |
| `src/rag_retriever.py` | ~70 | **IMPLEMENTE** (similarité cosinus, top-k) |
| `src/annotator_llm.py` | ~215 | **IMPLEMENTE** (11 sous-métriques, repli déterministe `rule_based_stub`, cache) |
| `src/annotation_validator.py` | ~225 | **IMPLEMENTE** (validation, agrégats §12.3-§12.7, gel §13) |
| `src/risk_engine.py` | ~150 | **IMPLEMENTE** (SP3, `test_reference_example` vert) |
| `src/cost_engine.py` | ~140 | **IMPLEMENTE** (Cost(d;H)) |
| `src/optimizer.py` | ~270 | **IMPLEMENTE** (unicité, budget, Pareto, `test_reference_example`-style validation exhaustive) |
| `src/reporter.py` | ~90 | **IMPLEMENTE** (transformation y* -> Y*, §17.6) |
| `src/orchestrator.py` | ~250 | **IMPLEMENTE** (point d'entrée unique, hors liste §26 — ajout spécifique à la tâche chapitre 4) |

En complément, une couche **hors runtime** (`tools/deception_kb/`)
construit, hors ligne et de façon déterministe, les sources documentaires
qui alimenteront à terme la KB déception (D3FEND, MITRE Engage,
littérature scientifique, normalisation contrôlée inter-sources) — voir
section 3.

```
Knowledge layer (schemas, graph_builder, knowledge_attack,
knowledge_deception + tools/deception_kb/*)
  ↓
SP1 (admissibility.py)               ← IMPLEMENTE (petite instance)
  ↓
RAG (rag_indexer.py / rag_retriever.py)   ← IMPLEMENTE (chunks reels D3FEND/Engage/litterature, TF-IDF hache)
  ↓
LLM structured annotation (annotator_llm.py)  ← IMPLEMENTE (repli deterministe rule_based_stub, cache)
  ↓
validation (annotation_validator.py)  ← IMPLEMENTE (completude des 11 sous-metriques)
  ↓
deterministic SP2 aggregation         ← IMPLEMENTE (Realisme/P_interaction/P_engagement/Effet_prog/DE)
  ↓
frozen annotations                    ← IMPLEMENTE (FrozenAnnotationTable, versionnee, immuable)
  ↓
Cost (cost_engine.py)                ← IMPLEMENTE (Cost(d;H))
SP3 (risk_engine.py)                 ← IMPLEMENTE (test_reference_example vert)
  ↓
optimizer.py                          ← IMPLEMENTE (unicité, budget, Pareto, y*)
  ↓
Pareto                                ← IMPLEMENTE (dans optimizer.py)
  ↓
Y* (reporter.py)                      ← IMPLEMENTE (build_deployment_report,
                                         risque avant/après, preuves)
  ↓
orchestrator.py (point d'entrée unique) ← IMPLEMENTE
                                           (SP1 -> RAG -> annotation -> gel
                                           -> cout -> (P) -> risque avant/après
                                           -> reporter, runs/<run_id>/*.json)
```

### Capture associée

**CAPTURE 1 — Architecture / arborescence simplifiée.**
Voir `SCREENSHOT_MANIFEST.md`.

---

## 2. Environnement et technologies

Voir `TECHNOLOGIES.md` pour le tableau complet. Résumé : Python ≥ 3.11,
Pydantic 2.x, NetworkX 3.x, pytest ≥ 8.0. Aucune autre dépendance runtime
à ce stade.

---

## 3. Préparation des connaissances

### Objectif

Fournir les briques de données validées (schémas, graphe d'attaque, KB
ATT&CK, KB déception) sur lesquelles s'appuieront SP1/SP2/SP3, ainsi que
les couches offline de construction de la future KB déception à partir de
sources externes (D3FEND, MITRE Engage, littérature scientifique).

### Correspondance avec le chapitre 3

- `G=(V,E)` (§3.1) → `src/graph_builder.py` ;
- attributs de nœud `Attr(T_{i,h})` (§3.3) → `NodeAttributes` dans `src/schemas.py` ;
- catalogue `\mathcal D` (§7) → `src/knowledge_deception.py` (chargeur du
  futur `deception_catalog.json`, pas encore construit — voir section 13) ;
- KB ATT&CK (§8) → `src/knowledge_attack.py`.

### Fichiers concernés

`src/schemas.py`, `src/graph_builder.py`, `src/knowledge_attack.py`,
`src/knowledge_deception.py`, `tools/deception_kb/d3fend_seed_builder.py`,
`tools/deception_kb/engage_seed_builder.py`,
`tools/deception_kb/literature_seed_builder.py`,
`tools/deception_kb/normalization_builder.py`.

### Classes / fonctions principales

**`src/schemas.py`** (19 modèles Pydantic v2, `extra="forbid"`) :
`TechniqueOccurrence`, `NodeAttributes`, `AttackGraph`, `AttackGraphEdge`,
`DeceptionMechanism`, `DeceptionEvidence`, `DeceptionAdmissibilityProfile`,
`Annotation`, `AnnotationContext`, `SystemInstance`, `SIInventory`,
`Asset`, `Location`.

**`src/graph_builder.py`** : `build_attack_graph`,
`load_attack_graph_json`, `to_networkx` (conversion vers `networkx.DiGraph`),
`get_parent_ids`, `get_child_ids`, `identify_entry_nodes`,
`identify_terminal_nodes`, `is_entry_node`, `is_terminal_node`.

**`src/knowledge_attack.py`** : `load_attack_knowledge` (parseur
`enterprise-attack.json` STIX), `AttackKnowledgeBase`,
`AttackTechniqueRecord`, `get_technique`, `get_tactics`, `get_platforms`,
`validate_graph_techniques`.

**`src/knowledge_deception.py`** : `load_deception_catalog`,
`DeceptionKnowledgeBase`, `get_deception`, `get_admissibility_profile`,
`validate_deception_ids`. **Ce chargeur n'a pas encore de fichier réel à
charger** : `data/deception/deception_catalog.json` n'existe pas encore
(voir section 13 — dépend d'une OPEN_DECISION de composition finale de
`\mathcal D`, non résolue).

**`tools/deception_kb/*`** (hors runtime, offline) : construction
déterministe et tracée du staging D3FEND (11 concepts, branche Deceive),
MITRE Engage (31 activités, 9 approches), corpus scientifique (14 sources,
18 passages vérifiés page par page), et couche de normalisation
inter-sources (candidats de mécanismes issus des feuilles D3FEND).
Détail complet : `README.md` (étapes 5 à 8) et `tools/deception_kb/README.md`.

### Entrées

`enterprise-attack.json` (KB ATT&CK), fichiers JSON de graphe d'attaque,
staging D3FEND/Engage/littérature déjà versionnés dans
`data/deception/staging/`.

### Traitement

Validation Pydantic stricte à la construction ; construction du graphe et
conversion vers `networkx.DiGraph` pour les utilitaires de parcours ;
identification des nœuds d'entrée/terminaux selon `Entry`/`Terminal`
(CLAUDE.md §5/§6).

### Sorties

Objets Python validés (`AttackGraph`, `AttackKnowledgeBase`,
`DeceptionKnowledgeBase`) ; côté offline, fichiers JSON de staging déjà
présents dans `data/deception/staging/`.

### Technologie utilisée

Pydantic v2, NetworkX.

### Commande réelle d'exécution

```bash
pytest tests/test_schemas.py tests/test_graph_builder.py \
       tests/test_knowledge_attack.py tests/test_knowledge_deception.py -v
```

### Tests

`tests/test_schemas.py` (36 tests), `tests/test_graph_builder.py`
(32 tests), `tests/test_knowledge_attack.py` (47 tests),
`tests/test_knowledge_deception.py` (49 tests) — 164 tests, tous verts.
Côté offline : `tests/test_d3fend_seed_builder.py`,
`tests/test_engage_seed_builder.py`,
`tests/test_literature_seed_builder.py`,
`tests/test_normalization_builder.py`.

### Exemple réel disponible

`docs/chapter4/outputs/architecture_tree.txt` (arborescence réelle du
dépôt). Un exemple réel de **fiche de mécanisme de cyberdéception**
(Capture 2) n'est **pas encore disponible** : `DeceptionMechanism` est
défini et testé (`src/schemas.py`), mais aucun `deception_catalog.json`
réel n'existe encore pour être chargé par `knowledge_deception.py` — voir
section 13.

### Capture associée

CAPTURE 1 disponible (voir `SCREENSHOT_MANIFEST.md`). CAPTURE 2
`NOT_IMPLEMENTED` (catalogue final absent).

### Limites

`knowledge_deception.py` est un chargeur/validateur générique, testé
contre des fixtures synthétiques (`tests/test_knowledge_deception.py`) —
il n'a jamais encore chargé un vrai catalogue, faute de
`deception_catalog.json` réel.

---

## 4. Implémentation de SP1

**Status : IMPLEMENTE (périmètre « petite instance », voir Limites).**

### Objectif

Déterminer, pour chaque occurrence non terminale du graphe d'attaque,
l'ensemble des couples (mécanisme, emplacement) admissibles `C_i_h`, à
partir de `D_i` (mapping M_{i,d} fourni), `Allowed`, `PrerequisSatisfaits`
et `Pertinent`.

### Correspondance avec le chapitre 3

`D_i` (§10.2), `L_i_h_d` (§10.4), `C_i_h` (§10.5) — notation verrouillée
(section 0 de ce document) : `Autorise`, `PrerequisSatisfaits`,
`Pertinent`.

### Fichiers concernés

`src/admissibility.py`, `tests/test_admissibility.py`,
`examples/sp1_example.py`.

### Classes / fonctions principales

`evaluate_allowed`, `evaluate_requirements_satisfied`, `evaluate_relevant`,
`build_admissibility_report`.

### Entrées

Une `SystemInstance` déjà validée (graphe + inventaire SI), un catalogue
`dict[str, DeceptionMechanism]`, un mapping M_{i,d}
`dict[str, list[str]]` (technique_id → identifiants de mécanismes
applicables, **fourni par l'appelant** — sa construction depuis
D3FEND/Engage/littérature reste une OPEN_DECISION non résolue, réf.
`tools/deception_kb/README.md`), et les seuils `theta_c`/`theta_i`/
`theta_a` (§6, jamais par défaut).

### Traitement

Pour chaque occurrence : si Terminal (§6), aucun candidat n'est généré
(`C_i_h = ∅` par construction). Sinon, pour chaque mécanisme du
catalogue × chaque emplacement du SI, un diagnostic complet est produit :
`mapping` (d ∈ D_i ?), puis si `mapping="pass"`, `Autorise`,
`PrerequisSatisfaits`, `Pertinent` (chacun `pass`/`fail`/`undetermined`).
**OPEN_DECISION 4 appliquée en politique prudente** : lorsque les listes
pertinentes de `DeceptionAdmissibilityProfile` sont toutes vides, le
critère est `undetermined` et le candidat est exclu de `C_i_h` (jamais
d'admission devinée).

### Sorties

Un rapport structuré : par occurrence, `is_terminal`, `D_i`, la liste
complète des diagnostics `candidates`, et `C_i_h` ; plus un résumé
(`occurrence_count`, `candidate_count`, `admissible_count`,
`rejected_count`).

### Technologie utilisée

Python pur (pas de dépendance supplémentaire).

### Commande réelle d'exécution

```bash
python -m examples.sp1_example
```

### Tests

`tests/test_admissibility.py` — 21 tests : `Allowed`/
`PrerequisSatisfaits`/`Pertinent` chacun en pass/fail/undetermined,
mapping absent (rejet sans évaluation), occurrence Terminal (aucun
candidat), déterminisme, cohérence des compteurs de synthèse, contenu de
`rejection_reason`. Tous verts.

### Exemple réel disponible

`docs/chapter4/outputs/sp1_candidates.json` (rapport complet) et
`docs/chapter4/outputs/sp1_example.txt` (résumé), générés par
`examples/sp1_example.py` sur une petite instance explicite (T1078 sur un
contrôleur de domaine DC01, deux mécanismes candidats D3-DUC/D3-DF, deux
emplacements) : 4 candidats bruts, 1 admissible.

### Capture associée

CAPTURE 3 — voir `SCREENSHOT_MANIFEST.md` (`READY_FOR_SCREENSHOT`).

### Limites

- `Pertinent` est simplifié à une relation topologique **directe** (même
  actif, ou arête `SITopologyEdge` à un saut) — pas une analyse complète
  des voisins du graphe d'attaque ni des chemins vers les nœuds
  terminaux (§10.4 le permet en principe, mais ce niveau de détail est
  hors périmètre d'une première « petite instance », pour éviter la
  sur-ingénierie).
- M_{i,d} est un paramètre d'entrée, pas construit par ce module.
- Aucun catalogue réel n'existe encore (section 3) : les tests et
  l'exemple utilisent des mécanismes synthétiques mais structurellement
  valides (mêmes champs qu'un `DeceptionMechanism` réel issu de D3FEND).

---

## 5. Implémentation du RAG

**Status : IMPLEMENTE (indexation + récupération, périmètre décrit
ci-dessous).**

### Objectif

Ingérer les documents déjà versionnés hors ligne (D3FEND, Engage,
littérature), les découper en chunks tracés, construire un index et
récupérer les passages pertinents pour une requête contextuelle (§9.1
étapes 2, 3, 7).

### Correspondance avec le chapitre 3

CLAUDE.md §9.1 (pipeline de construction de la KB déception, étapes 2/3/7
en particulier), §26 (`rag_indexer.py`, `rag_retriever.py`).

### Fichiers concernés

`src/rag_indexer.py`, `src/rag_retriever.py`, `tests/test_rag_indexer.py`,
`tests/test_rag_retriever.py`, `examples/rag_example.py`.

### Classes / fonctions principales

**`rag_indexer.py`** : `Chunk`, `RagIndex`, `load_d3fend_chunks`,
`load_engage_chunks`, `load_literature_chunks`, `tokenize`,
`compute_document_frequencies`, `embed_text`, `embed_query`,
`build_index`.

**`rag_retriever.py`** : `RetrievalResult`, `cosine_similarity`,
`retrieve`.

### Entrées

Les fichiers de staging déjà versionnés et testés (§3) :
`data/deception/staging/d3fend_deception_seed_1.5.0.json` (concepts +
`source_evidence`), `data/deception/staging/engage_activity_seed_1.0.json`
(activités, `description`/`long_description`),
`data/deception/staging/literature_evidence_seed_1.2.json` (18 passages
`page_verified`).

### Traitement

Un chunk par entrée `source_evidence` (D3FEND), par
`description`/`long_description` distincte (Engage), par passage
scientifique déjà vérifié (littérature) — texte vide jamais indexé
(§25.3, omis silencieusement, pas une erreur). Chaque chunk porte
`chunk_id`, `source_id`, `source_type`, `document_id`, `locator`
(page/propriété source), `text`, `text_hash` (SHA-256, intégrité),
`metadata`. Vecteur déterministe par chunk : fréquence de terme pondérée
par IDF (fréquence documentaire inverse, calculée sur le corpus indexé)
avec « hashing trick » (256 dimensions par défaut), mots-outils anglais
exclus, puis normalisation L2. La requête est encodée avec les **mêmes**
poids IDF que le corpus (`embed_query`), condition nécessaire à une
similarité cosinus comparable. `retrieve` trie par similarité
décroissante et retourne les `top_k` chunks (filtre optionnel par
`source_type`).

### Sorties

`RagIndex` (chunks + vecteurs + statistiques du corpus) ; côté
`retrieve` : liste de `RetrievalResult` (chunk + score).

### Technologie utilisée

Python pur (`hashlib.blake2b`/`sha256`, `re`, `math`) — **aucune**
bibliothèque d'embeddings ni service externe (voir Limites).

### Commande réelle d'exécution

```bash
python -m examples.rag_example
```

### Tests

`tests/test_rag_indexer.py` — 22 tests (tokenisation, exclusion des
mots-outils, vecteurs déterministes/normalisés, IDF plus élevé pour un
terme rare que pour un terme fréquent, ingestion synthétique par source,
texte vide omis, index sans collision de `chunk_id`, **ingestion réelle
des trois fichiers de staging** avec assertions sur les comptes réels,
invariant LLM hors du chemin d'exécution). `tests/test_rag_retriever.py`
— 13 tests (similarité cosinus, classement par score, `top_k`, filtre par
`source_type`, index vide, invariant LLM hors du chemin d'exécution). 35
tests au total, tous verts.

### Exemple réel disponible

`docs/chapter4/outputs/rag_chunks_example.json` (échantillon réel de 6
chunks, 2 par source) et `docs/chapter4/outputs/rag_retrieval_example.txt`
(résultat réel de récupération, requête *"decoy credential store to
deceive an adversary on a domain controller"* sur un index réel de 124
chunks — 44 D3FEND, 62 Engage, 18 littérature) : le premier résultat est
`d3fend:D3-DUC:0` (« Decoy User Credential »), directement pertinent pour
la requête.

### Capture associée

CAPTURE 4 (chunks) et CAPTURE 5 (retrieval) — voir
`SCREENSHOT_MANIFEST.md` (`READY_FOR_SCREENSHOT`).

### Limites

- Le vecteur par chunk est un TF-IDF haché **déterministe**, pas un
  embedding sémantique de modèle de langage — un choix technique
  documenté (pas une décision scientifique), cohérent avec l'absence de
  bibliothèque d'embeddings choisie à ce stade (`TECHNOLOGIES.md`). Il
  peut être remplacé plus tard sans changer la forme de
  `Chunk`/`RagIndex`/`RetrievalResult`.
- Index en mémoire (`dict` Python), pas de magasin vectoriel persistant.
- La liste de mots-outils exclus est fixe et anglaise uniquement (pas de
  détection de langue).
- Aucune intégration avec `annotator_llm.py` (non implémenté) : les
  `RetrievalResult` ne sont pas encore convertis en
  `DeceptionEvidence`/`AnnotationContext.retrieved_evidence`.

---

## 6. Implémentation de l'annotation LLM

**Status : IMPLEMENTE — repli déterministe `rule_based_stub` (aucune API
LLM réelle disponible dans cet environnement). Voir Limites : ceci n'est
PAS une annotation sémantique réelle.**

### Objectif

Produire les 11 `Annotation` brutes (§11.3) pour un candidat `(T_{i,h},
d, l)` déjà décrit par un `AnnotationContext`, sans jamais calculer les
agrégats SP2 (§11.5).

### Correspondance avec le chapitre 3

CLAUDE.md §11.2 (entrées, interdiction du budget — déjà garantie par le
validateur Pydantic d'`AnnotationContext`), §11.3 (11 sous-métriques),
§11.4 (format minimum de sortie), §11.5 (ce que le LLM ne calcule
jamais). Politique de déterminisme/reproductibilité de la tâche
d'implémentation (cache par contexte/modèle/version de prompt).

### Fichiers concernés

`src/annotator_llm.py`, `src/rag_retriever.py` (fonction
`to_deception_evidence`, pont RAG → contexte d'annotation),
`tests/test_annotator_llm.py`, `examples/annotator_llm_example.py`.

### Classes / fonctions principales

`AnnotationProvider` (interface), `RuleBasedStubAnnotator` (repli
déterministe), `AnnotationCache`, `annotate_with_cache`,
`deterministic_annotation_id`.

### Entrées

Un `AnnotationContext` déjà construit (occurrence, référence de
mécanisme, emplacement, contexte graphe, `retrieved_evidence` — non vide,
sinon `AnnotatorLlmError` explicite, aucune preuve n'est jamais
fabriquée).

### Traitement

`RuleBasedStubAnnotator` calcule un score **unique** de chevauchement
lexical (proportion des tokens du signal de contexte — technique,
tactiques, nom du mécanisme, emplacement — retrouvés dans le texte des
preuves RAG récupérées) et l'applique identiquement aux 11 sous-métriques
: ce stub ne peut pas distinguer sémantiquement Realism
d'InteractionLikelihood ou d'Effectiveness sans modèle de langage réel —
le prétendre serait une fabrication. La confiance croît avec le nombre de
preuves récupérées (saturée). Chaque `Annotation` (validée par Pydantic,
`src/schemas.py`) porte `model_version="rule_based_stub"` et un
`annotation_id` déterministe (hash du contexte). `AnnotationCache`
permet de rejouer un résultat identique pour un contexte identique sans
ré-appeler le provider (testé par comptage d'appels).

### Sorties

`list[Annotation]` (11 éléments, un par sous-métrique), chacune avec
`score`, `justification`, `evidence`, `confidence`, `model_version`,
`prompt_version`, `annotated_at`, `annotation_id`.

### Technologie utilisée

Python pur (`hashlib`, `re`, `json`) + Pydantic (validation de sortie via
`Annotation`, déjà présente dans `src/schemas.py`).

### Commande réelle d'exécution

```bash
python -m examples.annotator_llm_example
```

### Tests

`tests/test_annotator_llm.py` — 13 tests : exactement 11 métriques
produites, marquage `rule_based_stub`, refus explicite sans preuve,
déterminisme (contexte identique → sortie identique), score plus élevé
pour un contexte pertinent que pour un contexte non pertinent (variation
réelle mesurée, pas une constante arbitraire), confiance croissante avec
le nombre de preuves, bornes `[0,1]`, identifiant déterministe, cache
(rejeu sans second appel au provider, vérifié par comptage), invariant :
`annotator_llm.py` n'importe jamais `risk_engine`/`optimizer`. Tous
verts.

### Exemple réel disponible

`docs/chapter4/outputs/llm_annotation_example.json` — chaîne réelle
complète RAG (124 chunks réels) → contexte d'annotation → 11
`Annotation` réelles pour le candidat `(T1078@DC01, D3-DUC, auth-store)`,
générée par `examples/annotator_llm_example.py`. Le fichier porte
explicitement la mention *"PAS un resultat LLM reel ni un resultat
experimental du chapitre 5"*.

### Capture associée

CAPTURE 6 — voir `SCREENSHOT_MANIFEST.md` (`READY_FOR_SCREENSHOT`).

### Limites

- **Ce n'est pas une annotation sémantique réelle** : faute d'API LLM
  disponible dans cet environnement, le score des 11 sous-métriques est
  identique (chevauchement lexical unique), pas différencié entre
  Realism/InteractionLikelihood/Effectiveness — une vraie annotation LLM
  produirait des scores distincts par sous-métrique, avec une
  justification sémantique réelle.
- Pas d'`annotation_validator.py` dédié : le bornage/format sont déjà
  garantis par la validation Pydantic d'`Annotation` (§11.4), mais la
  logique de gel de table (§13, module 9 « freeze ») reste à implémenter.
- Aucune intégration avec `admissibility.py` (SP1) : ce module consomme
  un `AnnotationContext` déjà construit ; l'assemblage automatique
  occurrence SP1 → contexte → annotation reste à faire dans un futur
  orchestrateur.

---

## 7. Calcul déterministe de SP2

**Status : IMPLEMENTE (avec le repli déterministe `rule_based_stub` de
la section 6 — voir Limites).**

### Objectif

Calculer PAR CODE — jamais par le LLM (§11.5) — `Realisme`,
`P_interaction`, `P_engagement`, `Effet_prog`, `DE` à partir des 11
`Annotation` brutes validées d'un candidat, puis geler le résultat.

### Correspondance avec le chapitre 3

CLAUDE.md §12.3 (`Realisme`), §12.4 (`P_interaction`), §12.5
(`P_engagement`), §12.6 (`Effet_prog`), §12.7 (`DE`) ; §13 (validation et
gel).

### Fichiers concernés

`src/annotation_validator.py`, `tests/test_annotation_validator.py`,
`examples/freeze_example.py`.

### Classes / fonctions principales

`validate_candidate_annotations`, `compute_realisme`,
`compute_p_interaction`, `compute_effet_prog`, `compute_p_engagement`,
`compute_de`, `freeze_candidate`, `freeze_table`, `FrozenAnnotation`,
`FrozenAnnotationTable` (avec `de_by_candidate()`, pont direct vers
`src.optimizer.build_candidates_from_admissibility`).

### Entrées

Les 11 `Annotation` brutes d'un candidat `(occurrence_id, mechanism_id,
location_id)` (produites par `src/annotator_llm.py`).

### Traitement

Validation de complétude (exactement 11 sous-métriques, sans doublon,
`model_version`/`prompt_version` cohérents) — le bornage `[0,1]` et les
champs obligatoires sont déjà garantis par `Annotation` (Pydantic).
Agrégations par moyenne simple (poids égaux par défaut, §12.3/§12.4/§12.6,
pondération explicite acceptée en option si elle somme à 1) :
`Realisme = moyenne(R_tech, R_context, R_perception, R_behavior)`,
`P_interaction = moyenne(A_object, A_action, A_source)`,
`Effet_prog = moyenne(S_stop, S_redirect, S_contain, S_delay)`,
`P_engagement = Realisme × P_interaction`, `DE = P_engagement ×
Effet_prog`. Gel dans une `FrozenAnnotationTable` immuable et versionnée
(`annotation_set_version`, `frozen_at`), rejetant tout candidat en
double.

### Sorties

`FrozenAnnotation` par candidat (11 scores bruts + 5 agrégats + preuves +
confiance) ; `FrozenAnnotationTable.de_by_candidate()` ->
`dict[(occurrence_id, mechanism_id, location_id), float]`, directement
consommable par `src/optimizer.py`.

### Technologie utilisée

Python pur.

### Commande réelle d'exécution

```bash
python -m examples.freeze_example
```

### Tests

`tests/test_annotation_validator.py` — 21 tests : complétude (métrique
manquante/dupliquée/`model_version` incohérent rejetés), formules
d'agrégation (poids égaux par défaut, poids personnalisés validés),
chaîne complète `P_engagement`/`DE` reproduisant l'ordre de grandeur de
l'ancre de référence (§20.4 : `P_engage=0.70`, `Effectiveness_prog=0.60`
→ `DE=0.42`), gel d'un candidat et d'une table multi-candidats,
identifiant déterministe, doublon rejeté, `de_by_candidate()` conforme au
format attendu par l'optimiseur, table immuable, invariant
d'importation. Tous verts.

### Exemple réel disponible

`docs/chapter4/outputs/frozen_annotations_example.csv` — chaîne réelle
complète SP1 → RAG → annotation (stub) → validation/agrégation/gel pour
le candidat `(T1078@DC01, D3-DUC, auth-store)`, générée par
`examples/freeze_example.py`.

### Capture associée

CAPTURE 7 — voir `SCREENSHOT_MANIFEST.md` (`READY_FOR_SCREENSHOT`).

### Limites

Les valeurs `Realisme`/`P_interaction`/`P_engagement`/`Effet_prog`/`DE`
de l'exemple réel dépendent des scores bruts du repli déterministe
`rule_based_stub` (section 6) — donc identiques entre les 11
sous-métriques, pas une distinction sémantique réelle. Les FORMULES
d'agrégation elles-mêmes sont réelles et indépendantes de la source des
scores bruts (elles fonctionneraient identiquement avec de vraies
annotations LLM).

---

## 8. Calcul du coût

**Status : IMPLEMENTE.**

### Objectif

Calculer `Cost(d;H) = C_deploy(d) + C_resource(d;H) + C_maintenance(d;H)` (§15).

### Correspondance avec le chapitre 3

CLAUDE.md §15.1 (`C_deploy`), §15.2 (`C_resource`), §15.3 (`C_maintenance`).
Hypothèse de référence gelée (§15) : coût indépendant de l'emplacement —
`Cost(d,l;H) = Cost(d;H)` (le module ne prend structurellement jamais `l`
en paramètre).

### Fichiers concernés

`src/cost_engine.py`, `tests/test_cost_engine.py`,
`examples/cost_example.py`.

### Classes / fonctions principales

`compute_deployment_cost`, `compute_resource_cost`,
`compute_maintenance_cost`, `compute_mechanism_cost`,
`compute_cost_by_mechanism`.

### Entrées

Paramètres numériques explicites par mécanisme (`t_setup`, `w_eng`,
`L_data`, `w_data`, `C_integration` ; `r_CPU`/`r_RAM`/`r_disk`/
`r_network` et coûts unitaires associés ; `t_monitoring`, `S_logs`,
`w_storage`, `C_updates`) et un horizon `H`.

### Traitement

Somme pondérée déterministe des trois composantes ; rejet explicite de
toute valeur négative ou d'un horizon négatif (aucune valeur devinée).

### Sorties

`dict` par mécanisme : `{C_deploy, C_resource, C_maintenance, Cost}`.

### Technologie utilisée

Python pur.

### Commande réelle d'exécution

```bash
python -m examples.cost_example
```

### Tests

`tests/test_cost_engine.py` — 13 tests (formules des trois composantes,
rejet des valeurs négatives, somme totale, indépendance vis-à-vis de
l'emplacement par construction, déterminisme). Tous verts.

### Exemple réel disponible

`docs/chapter4/outputs/cost_example.txt`, généré par
`examples/cost_example.py` (deux mécanismes, `H=720`).

### Limites

`DeceptionMechanism.resource_requirements` (`src/schemas.py`) reste du
texte libre (`cpu`, `ram`, ... ex. "2 vCPU") : ce module n'essaie pas de
le parser en valeurs numériques — il attend des paramètres numériques
déjà explicites, quelle qu'en soit l'origine. La conversion texte→numérique
reste une OPEN_DECISION non résolue.

---

## 9. Moteur SP3

**Status : IMPLEMENTE. Ancre de validation `test_reference_example` VERTE.**

### Objectif

Propager Gamma → P^e → A → P → I → R sur le graphe d'attaque, dans
l'ordre topologique, en gérant convergence (noisy-OR) et divergence (π).

### Correspondance avec le chapitre 3

CLAUDE.md §14 intégralement : `Gamma_{i,h}(y)` (§14.3), `P^e` (§14.4, cas
non divergent et divergent), `A_{i,h}(y)` noisy-OR (§14.5), `P_{i,h}(y)`
(§14.6), `R_{i,h}(y)` (§14.7). Notation verrouillée : `Gamma`, `A`, `P`,
`I`, `R`, `q`, `DE` (inchangés de CLAUDE.md, seuls les concepts SP2 sont
renommés en français).

### Fichiers concernés

`src/risk_engine.py`, `tests/test_risk_engine.py`,
`examples/sp3_example.py`.

### Classes / fonctions principales

`compute_gamma`, `compute_transmitted_edge_probability`,
`compute_reachability` (noisy-OR), `compute_propagated_success_probability`,
`compute_aggregated_impact`, `compute_risk`, `propagate_risk` (orchestration
complète sur le graphe, ordre topologique via NetworkX).

### Entrées

Un `AttackGraph` déjà validé, `q_by_occurrence` (obligatoire pour toutes
les occurrences — aucune valeur devinée, §25.3), `impact_by_occurrence`
(idem), `de_by_occurrence` (optionnel par occurrence — absence = DE=0,
aucune déception déployée à cette occurrence).

### Traitement

Tri topologique du graphe (NetworkX) ; pour chaque occurrence : Gamma =
1-DE ; si nœud d'entrée, A=1 ; sinon, pour chaque parent, calcul de P^e
(avec π = valeur explicite de l'arête si divergence, sinon 1/|enfants| —
jamais si non divergent, §14.4 « règle gelée ») puis agrégation noisy-OR ;
P = A×q ; R = P×I.

### Sorties

`dict[occurrence_id, {Gamma, A, P, I, R, DE, q}]`.

### Technologie utilisée

Python pur + NetworkX (tri topologique).

### Commande réelle d'exécution

```bash
python -m examples.sp3_example
```

### Tests

`tests/test_risk_engine.py` — 23 tests : formules élémentaires isolées,
propagation linéaire, convergence à deux entrées, divergence (répartition
égale par défaut et probabilités explicites), valeurs manquantes rejetées
(q/I), bornes `[0,1]` sur A/P/Gamma/R, **`test_reference_example`**
(ancre de validation — voir ci-dessous), et un test dédié vérifiant que
`src/risk_engine.py` n'importe jamais `src/annotator_llm.py` ni
`src/rag_indexer.py`/`src/rag_retriever.py` (invariant « LLM hors du
chemin d'exécution », analysé par `ast`, pas une recherche de
sous-chaîne). Tous verts.

### Ancre de validation — `test_reference_example`

Scénario : T1566/T1190 → T1003 → T1078 → T1059/T1057/T1082 (divergence à
trois enfants, π=1/3) → T1041. Déception DE=0.429 sur T1003 uniquement.
Résultats **réellement calculés par `propagate_risk`** (aucune valeur
recopiée à la main) :

| Grandeur | Valeur calculée | Valeur cible (prompt §0bis) |
|---|---|---|
| `DE_1003` | 0.429 | 0.429 |
| `Gamma_1003` | 0.571 | 0.571 |
| `R_avec_deception` (T1041) | 0.0208 | 0.0208 |
| `R_sans_deception` (T1041) | 0.0365 | 0.0365 |
| Réduction relative | 42.9 % | ≈ 42.9 % |

Toutes les égalités sont vérifiées à une tolérance de `1e-3` (`5e-3` pour
la réduction relative dérivée, valeur donnée avec « ≈ » dans la cible).

### Exemple réel disponible

`docs/chapter4/outputs/risk_example.csv` (table complète des 8 occurrences,
scénarios avec/sans déception) et `docs/chapter4/outputs/risk_example.txt`
(résumé lisible), générés par `examples/sp3_example.py`.

### Capture associée

CAPTURE 8 — voir `SCREENSHOT_MANIFEST.md` (`READY_FOR_SCREENSHOT`).

### Limites

`propagate_risk` ne lit pas encore une table d'annotations figée réelle
(section 7/13, non implémentées) : `de_by_occurrence` est fourni
directement par l'appelant pour l'instant (comme dans l'exemple et les
tests). L'intégration avec `cost_engine.py`/`optimizer.py` (sélection de
`y`) reste à faire.

---

## 10. Optimisation et Pareto

**Status : IMPLEMENTE (périmètre « petite instance », voir Limites).**

### Objectif

Résoudre le problème global `(P)` : minimisation multiobjectif des
risques terminaux, sous contrainte d'unicité locale et de budget, en
produisant le front de Pareto puis un `y*` illustratif.

### Correspondance avec le chapitre 3

CLAUDE.md §16 intégralement : §16.1 (unicité), §16.2 (budget), §16.3
(domaine binaire, `y` n'existe que pour `(d,l) ∈ C_{i,h}`). §23
(validation exhaustive sur petite instance) et §24 (interdiction de toute
réduction arbitraire de l'espace de décision, respectée par le garde-fou
explicite `max_configurations`, qui refuse d'énumérer plutôt que
d'omettre silencieusement).

### Fichiers concernés

`src/optimizer.py`, `tests/test_optimizer.py`,
`examples/optimizer_example.py`.

### Classes / fonctions principales

`Candidate`, `Configuration` (`total_cost`, `de_by_occurrence`,
`to_deployment_plan`), `build_candidates_from_admissibility`,
`enumerate_configurations`, `filter_by_budget`, `evaluate_configuration`,
`dominates`, `pareto_front`, `select_by_sum_aggregation`, `solve`
(orchestration complète).

### Entrées

Le rapport SP1 (`C_{i,h}` via `build_admissibility_report`), `DE`
déjà figé par candidat `(occurrence_id, mechanism_id, location_id)`,
`Cost(d;H)` déjà calculé par mécanisme (`cost_engine`), `q`/`I` par
occurrence, `B_total`, et les seuils `theta_c`/`theta_i`/`theta_a`
(pour identifier les occurrences Terminal, objectifs de `(P)`).

### Traitement

Construction des candidats à partir de `C_{i,h}` ; énumération
exhaustive des configurations (« aucune déception » + chaque candidat,
par occurrence, unicité garantie par construction) ; filtrage budgétaire
(§16.2) ; évaluation SP3 (`propagate_risk`) de chaque configuration
faisable, restreinte au vecteur des risques terminaux ; front de Pareto
(non-dominance, minimisation) ; sélection illustrative d'un `y*` par
somme des risques terminaux sur le front (politique explicite, pas une
règle imposée par le chapitre 3 — §16 l'autorise explicitement si
justifiée).

### Sorties

`configurations_enumerated`, `configurations_feasible`, `pareto_front`
(liste d'`EvaluatedConfiguration`), `selected` (`y*` illustratif), chaque
configuration exposant `to_deployment_plan()` (matérialisation minimale
de `Y*` : liste de `{occurrence_id, mechanism_id, location_id, DE, Cost}`).

### Technologie utilisée

Python pur (énumération exhaustive, pas de solveur externe).

### Commande réelle d'exécution

```bash
python -m examples.optimizer_example
```

### Tests

`tests/test_optimizer.py` — 22 tests : construction des candidats,
énumération (unicité, garde-fou de taille), filtrage budgétaire,
dominance, front de Pareto, sélection par agrégation, résolution de bout
en bout, **validation exhaustive sur petite instance** (§23 : toutes les
configurations faisables sont énumérées « à la main » indépendamment de
`enumerate_configurations`, leur objectif recalculé directement via
`propagate_risk`, et la meilleure solution exacte comparée à celle de
`solve()`), et invariant LLM hors du chemin d'exécution (analyse `ast`).
Tous verts.

### Exemple réel disponible

`docs/chapter4/outputs/optimizer_example.txt`, généré par
`examples/optimizer_example.py` (T1078@DC01 → T1003@DC01 Terminal, 1
candidat admissible D3-DUC après application des règles SP1, `B_total=5000`) :
2 configurations énumérées, 2 faisables, la configuration avec déception
domine (risque terminal réduit de 0.297 à 0.172).

**`DE` y est une valeur illustrative fournie directement en entrée** (SP2
non implémenté, §5/§6/§7 non implémentées) — ce script démontre
uniquement que `(P)` s'exécute de bout en bout sur des sorties réelles de
SP1/coût, ce n'est pas un résultat expérimental du chapitre 5.

### Capture associée

Aucune. Réf. tâche §8 : le front de Pareto et le plan `Y*` final sont
réservés au chapitre 5. La sortie ci-dessus sert de preuve d'exécution
interne pour ce document, pas de capture de chapitre 4.

### Limites

- Exploration exhaustive uniquement (§23) : aucune réduction ni
  heuristique (§24 l'interdit avant validation du modèle) — le module
  refuse explicitement d'énumérer au-delà de `max_configurations` plutôt
  que d'omettre silencieusement des configurations.
- La politique de décision `select_by_sum_aggregation` est illustrative,
  pas une règle du chapitre 3 ; seuls l'énumération et le front de Pareto
  sont la sortie de référence de `(P)`.
- `DE` et `Cost` sont reçus déjà calculés (SP2/coût) : ce module ne les
  recalcule jamais.
- `Configuration.to_deployment_plan()` fournit une matérialisation
  minimale de `Y*` ; le rapport interprétable (risque avant/après,
  preuves) est produit séparément par `src/reporter.py` (section 11), pas
  par `optimizer.py` lui-même.

---

## 11. Orchestration du pipeline

**Status : IMPLEMENTE.**

### Objectif

Fournir un point d'entrée unique enchaînant SP1 → RAG → annotation →
validation/agrégation/gel → coût → résolution de `(P)` → reporting
avant/après, sur une instance déjà validée (§19).

### Correspondance avec le chapitre 3

CLAUDE.md §19 (« Workflow complet d'exécution ») ; §18.3 (« aucun appel
LLM pendant l'optimisation », vérifié ici par construction : l'annotateur
n'est appelé qu'une seule fois par candidat, avant le gel).

### Fichiers concernés

`src/orchestrator.py`, `src/reporter.py`, `tests/test_orchestrator.py`,
`tests/test_reporter.py`, `examples/orchestrator_example.py`.
**`orchestrator.py` n'appartient pas à la liste `§26` de CLAUDE.md**
(`schemas`…`reporter`) : c'est un ajout spécifique à la tâche
d'implémentation du chapitre 4, qui demande explicitement un point
d'entrée unique. `reporter.py`, lui, appartient bien à `§26`/`§17.6` :
transformation de `y*` en `Y*`, avec occurrence protégée, mécanisme,
emplacement, coût, effet attendu, risque avant/après, variation,
preuves — assemblé à partir des sorties déjà calculées par `optimizer.py`,
`risk_engine.py` et `annotation_validator.py` (`reporter.py` ne recalcule
jamais rien).

### Classes / fonctions principales

`run_pipeline` (orchestration complète), `OrchestratorError` ;
`build_deployment_report`, `render_text_report`, `DeploymentReportRow`,
`ReporterError` (`src/reporter.py`).

### Entrées

Une `SystemInstance` déjà validée, un catalogue, un mapping `D_i`, un
`RagIndex` déjà construit, un `AnnotationProvider` (le repli déterministe
`RuleBasedStubAnnotator` dans les exemples), les paramètres de coût par
mécanisme, l'horizon, le budget, les seuils `theta_*`, `q`/`I` par
occurrence, une version d'ensemble d'annotations.

### Traitement

SP1 (`build_admissibility_report`) → pour chaque candidat admissible :
RAG (`retrieve`) puis annotation (`annotator.annotate`, **une seule fois
par candidat**) → gel (`freeze_table`) → coût
(`compute_cost_by_mechanism`) → résolution de `(P)` (`optimizer.solve`,
lit exclusivement `frozen_table.de_by_candidate()`, plus aucun appel à
l'annotateur à partir d'ici) → propagation du risque avant/après pour la
configuration sélectionnée (`risk_engine.propagate_risk`) →
transformation en `Y*` (`reporter.build_deployment_report`, §17.6).
Chaque étape est sérialisée en JSON dans `runs/<run_id>/` (non
versionné, régénérable — voir `.gitignore`).

**Lecture importante (documentée dans `src/reporter.py`)** :
`risk_before`/`risk_after` d'une ligne de `Y*` portent sur le risque
PROPRE de l'occurrence protégée, pas sur le risque terminal en aval.
`Gamma_{i,h}` (§14.3) agit sur la transmission de `i,h` vers SES ENFANTS,
jamais sur `R_{i,h}` lui-même : une ligne non terminale affiche donc
normalement `risk_variation=0` (vérifié explicitement,
`tests/test_orchestrator.py::test_report_row_variation_is_zero_while_terminal_risk_differs`)
alors que le risque de l'occurrence terminale en aval diminue réellement
(`risks_payload`/`risks.json`, exemple ci-dessous). `reporter.py`
n'attribue pas la variation d'un risque terminal à un placement
particulier — attribution non triviale dès que plusieurs placements
interagissent sur un même chemin, non implémentée.

### Sorties

`runs/<run_id>/{input_manifest,candidates,retrieval,annotations_raw,
annotations_frozen,costs,pareto,deployment_plan,risks,deployment_report,
run_manifest}.json` et un résumé en mémoire pour usage programmatique
immédiat.

### Technologie utilisée

Python pur (`json`, `pathlib`, `dataclasses`).

### Commande réelle d'exécution

```bash
python -m examples.orchestrator_example
```

### Tests

`tests/test_orchestrator.py` — 10 tests : tous les fichiers attendus sont
créés (y compris `deployment_report.json`), le plan de déploiement
correspond exactement à la sélection de l'optimiseur, le rapport `Y*`
reprend exactement le plan et les risques déjà calculés, le risque
avec/sans déception est présent, le `DE` gelé utilisé dans le plan
correspond à celui de la table figée, le manifeste de run est lisible et
cohérent, un budget invalide lève `OrchestratorError`,
**l'annotateur n'est appelé qu'une seule fois par candidat admissible**
(compté explicitement, invariant central du projet), et la variation nulle
d'une ligne non terminale est explicitement documentée comme un
comportement attendu (pas un bug). `tests/test_reporter.py` — 10 tests
(champs du rapport, plan vide, risque avant/après manquant rejeté,
variation relative non définie si risque avant nul, jointure des preuves
depuis la table figée, rendu texte, invariant d'importation). Tous verts.

### Exemple réel disponible

`docs/chapter4/outputs/pipeline_example.txt` — exécution réelle complète
sur l'instance `(T1078@DC01 → T1003@DC01)` avec un index RAG réel (124
chunks D3FEND/Engage/littérature) : 2 candidats évalués, 1 admissible, 2
configurations énumérées et faisables, front de Pareto de taille 1,
rapport `Y*` avec une ligne (`T1078@DC01`/`D3-DUC`/`auth-store`,
`risk_variation=+0.0000` — comportement attendu, voir ci-dessus), risque
terminal (`T1003@DC01`) réduit de 0.2974 à 0.2864 avec la déception
sélectionnée. `DE` provient du repli déterministe `rule_based_stub` — pas
un résultat expérimental du chapitre 5.

### Capture associée

Aucune capture dédiée : la liste fixe C1-C8 (§4/§5 de la tâche) réserve
déjà C8 à « SP3 ou pipeline complet », et C8 est déjà attribuée à SP3
(section 9). Cette sortie sert de preuve d'exécution bout-en-bout, pas de
capture supplémentaire.

### Limites

- Pas de réduction ni de sélection Top-K de l'espace de décision (§24) :
  hérite directement des limites d'`optimizer.py` (exploration
  exhaustive, réservée aux petites instances).
- `reporter.py` ne produit pas de justification textuelle rédigée par
  placement (uniquement des identifiants de preuve, `evidence_ids`) et
  n'attribue pas la variation d'un risque terminal à un placement
  particulier (voir « Lecture importante » ci-dessus).
- `runs/<run_id>/` n'est pas versionné (régénérable) — seule
  `docs/chapter4/outputs/pipeline_example.txt` est retenue comme preuve
  d'exécution pour le chapitre 4.

---

## 12. Traçabilité et reproductibilité

### Invariant testé — LLM hors du chemin d'exécution

**Status : TESTÉ sur les deux modules d'exécution existants.**
`tests/test_risk_engine.py::TestLlmOutOfExecutionPath::test_risk_engine_does_not_import_llm_or_rag`
et
`tests/test_optimizer.py::TestLlmOutOfExecutionPath::test_optimizer_does_not_import_llm_or_rag`
vérifient, par analyse de l'arbre syntaxique (`ast`, pas une recherche de
sous-chaîne), que `src/risk_engine.py` et `src/optimizer.py` n'importent
jamais `src/annotator_llm.py`, `src/rag_indexer.py` ni
`src/rag_retriever.py` — **les deux tests sont verts**. Symétriquement,
`tests/test_annotator_llm.py::TestNeverComputesAggregates` et
`tests/test_annotation_validator.py::TestLlmOutOfExecutionPath` vérifient
que `src/annotator_llm.py` et `src/annotation_validator.py` n'importent
jamais `src/risk_engine.py` ni `src/optimizer.py` — **les deux sont
verts**. `tests/test_reporter.py::TestLlmOutOfExecutionPath` vérifie de
même que `src/reporter.py` n'importe jamais `src/annotator_llm.py`,
`src/rag_indexer.py` ni `src/rag_retriever.py` — **vert**. Au niveau de
l'orchestrateur (`src/orchestrator.py`), l'invariant est en outre vérifié
dynamiquement : l'annotateur n'est appelé **exactement une fois par
candidat admissible**, jamais pendant le coût, le risque, `(P)` ou le
rapport (`tests/test_orchestrator.py::TestLlmOutOfExecutionPath`,
comptage explicite des appels) — **vert**. Tous les modules du chemin
d'exécution testent désormais cet invariant ; seul un futur
enrichissement de `reporter.py` (justification textuelle par placement)
resterait à re-vérifier s'il venait à importer de nouvelles dépendances.

### Déterminisme du LLM

**Status : IMPLEMENTE côté repli déterministe.** Aucune API LLM réelle
n'est appelée dans ce dépôt à ce stade : `src/annotator_llm.py` fournit
`RuleBasedStubAnnotator`, marqué `model_version="rule_based_stub"`
partout où une annotation est produite — jamais présenté comme un
résultat LLM réel (§20). `AnnotationCache` associe une clé déterministe
(hash du contexte + `model_version` + `prompt_version`) à la liste
d'`Annotation` déjà produite, pour rejouer un résultat identique sans
ré-appeler le provider — testé par comptage d'appels
(`tests/test_annotator_llm.py::TestAnnotationCache`). Un futur provider
LLM réel devra respecter la même interface (`AnnotationProvider`) et une
température fixe (0) pour préserver cette reproductibilité.

---

## 13. Limites de l'implémentation

Tous les modules de l'ordre imposé (schémas → graphe → SP1 → SP3 → coût →
optimiseur → RAG → annotation LLM → gel → orchestrateur) sont implémentés
et testés (503 tests verts). Limites qui subsistent :

- Aucun `deception_catalog.json` réel n'existe : sa composition dépend
  d'une OPEN_DECISION non résolue (quels concepts D3FEND/Engage/
  littérature deviennent des mécanismes finaux de `\mathcal D`) — voir
  `tools/deception_kb/README.md`, section OPEN_DECISION. Tous les
  exemples réels de ce document utilisent des mécanismes synthétiques
  mais structurellement valides (mêmes champs qu'un `DeceptionMechanism`
  réel issu de D3FEND).
- **Aucune API LLM réelle n'est disponible dans cet environnement** :
  `src/annotator_llm.py` utilise le repli déterministe
  `RuleBasedStubAnnotator` (`model_version="rule_based_stub"`), qui
  produit un score unique de chevauchement lexical appliqué
  identiquement aux 11 sous-métriques — jamais une distinction sémantique
  réelle. Toutes les valeurs `DE`/`Realisme`/`P_interaction`/
  `P_engagement`/`Effet_prog` des exemples de ce document en dépendent
  directement et ne doivent jamais être présentées comme un résultat
  expérimental du chapitre 5.
- Le vecteur RAG (`src/rag_indexer.py`) est un TF-IDF haché déterministe,
  pas un embedding sémantique de modèle de langage (choix technique
  documenté, pas une bibliothèque d'embeddings choisie).
- L'optimiseur (`src/optimizer.py`) explore exhaustivement l'espace des
  configurations (§23), sans réduction ni heuristique (§24) : réservé aux
  petites instances de validation, pas dimensionné pour un SI de grande
  taille.
- `src/reporter.py` assemble un rapport structuré (`deployment_report.json`)
  avec `evidence_ids` par ligne, mais ne rédige pas de justification
  textuelle narrative par placement ; il n'attribue pas non plus la
  variation d'un risque terminal à un placement particulier (voir section
  11, « Lecture importante »).
- `Pertinent` (SP1) reste simplifié à une relation topologique directe
  (même actif ou arête à un saut), pas une analyse complète des chemins
  vers les nœuds terminaux.

## 14. Matrice de correspondance chapitre 3 → implémentation

| Élément chapitre 3 | Module | Fonction | Test | Output | Capture | État |
|---|---|---|---|---|---|---|
| `G=(V,E)` | `src/graph_builder.py` | `build_attack_graph` | `test_graph_builder.py` | objet `AttackGraph` | C1 | IMPLEMENTE |
| Attributs de nœud | `src/schemas.py` | `NodeAttributes` | `test_schemas.py` | — | — | IMPLEMENTE |
| KB ATT&CK | `src/knowledge_attack.py` | `load_attack_knowledge` | `test_knowledge_attack.py` | — | — | IMPLEMENTE |
| Catalogue `D` (chargeur) | `src/knowledge_deception.py` | `load_deception_catalog` | `test_knowledge_deception.py` | — | — | IMPLEMENTE (chargeur) ; catalogue réel absent |
| `D_i` | `src/admissibility.py` | `build_admissibility_report` | `test_admissibility.py` | `sp1_candidates.json` | C3 | IMPLEMENTE |
| `L_{i,h,d}` | `src/admissibility.py` | `evaluate_allowed`/`evaluate_requirements_satisfied`/`evaluate_relevant` | `test_admissibility.py` | `sp1_candidates.json` | C3 | IMPLEMENTE |
| `C_{i,h}` | `src/admissibility.py` | `build_admissibility_report` | `test_admissibility.py` | `sp1_candidates.json` | C3 | IMPLEMENTE |
| 11 sous-métriques | `src/annotator_llm.py` | `RuleBasedStubAnnotator.annotate` | `test_annotator_llm.py` | `llm_annotation_example.json` | C6 | IMPLEMENTE (repli `rule_based_stub`, pas une annotation sémantique réelle) |
| `Realisme` | `src/annotation_validator.py` | `compute_realisme` | `test_annotation_validator.py` | `frozen_annotations_example.csv` | C7 | IMPLEMENTE |
| `P_interaction` | `src/annotation_validator.py` | `compute_p_interaction` | `test_annotation_validator.py` | `frozen_annotations_example.csv` | C7 | IMPLEMENTE |
| `P_engagement` | `src/annotation_validator.py` | `compute_p_engagement` | `test_annotation_validator.py` | `frozen_annotations_example.csv` | C7 | IMPLEMENTE |
| `Effet_prog` | `src/annotation_validator.py` | `compute_effet_prog` | `test_annotation_validator.py` | `frozen_annotations_example.csv` | C7 | IMPLEMENTE |
| `DE` | `src/annotation_validator.py` | `compute_de` | `test_annotation_validator.py` | `frozen_annotations_example.csv` | C7 | IMPLEMENTE |
| `Cout(d;H)` | `src/cost_engine.py` | `compute_cost_by_mechanism` | `test_cost_engine.py` | `cost_example.txt` | — | IMPLEMENTE |
| `Gamma`, `A`, `P`, `R` | `src/risk_engine.py` | `propagate_risk` | `test_reference_example` | `risk_example.csv` | C8 | IMPLEMENTE |
| unicité + budget | `src/optimizer.py` | `enumerate_configurations` / `filter_by_budget` | `test_optimizer.py` | `optimizer_example.txt` | (chapitre 5) | IMPLEMENTE |
| Pareto | `src/optimizer.py` | `pareto_front` | `test_optimizer.py` | `optimizer_example.txt` | (chapitre 5) | IMPLEMENTE |
| `y*` / `Y*` | `src/optimizer.py` (`select_by_sum_aggregation`, `to_deployment_plan`) + `src/reporter.py` (`build_deployment_report`) | `solve` / `build_deployment_report` | `test_optimizer.py` / `test_reporter.py` / `test_orchestrator.py` | `optimizer_example.txt` / `pipeline_example.txt` | (chapitre 5) | IMPLEMENTE |
