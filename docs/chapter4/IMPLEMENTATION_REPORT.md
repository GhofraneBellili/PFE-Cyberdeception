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
`src/rag_retriever.py`. **`src/risk_engine.py` (SP3) est désormais
implémenté et ce test est vert**
(`tests/test_risk_engine.py::TestLlmOutOfExecutionPath`, vérification par
analyse `ast` de l'arbre syntaxique). Le volet symétrique pour
`src/optimizer.py` sera ajouté dès que ce module existera ; jusque-là,
l'invariant y reste vrai par absence de code, mais pas encore *testé* —
ce document ne prétend pas le contraire.

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
| `src/rag_indexer.py` | 7 (stub) | NON IMPLEMENTE |
| `src/rag_retriever.py` | 7 (stub) | NON IMPLEMENTE |
| `src/annotator_llm.py` | 8 (stub) | NON IMPLEMENTE |
| `src/annotation_validator.py` | 8 (stub) | NON IMPLEMENTE |
| `src/risk_engine.py` | ~150 | **IMPLEMENTE** (SP3, `test_reference_example` vert) |
| `src/cost_engine.py` | ~140 | **IMPLEMENTE** (Cost(d;H)) |
| `src/optimizer.py` | 7 (stub) | NON IMPLEMENTE |
| `src/reporter.py` | 8 (stub) | NON IMPLEMENTE |

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
RAG (rag_indexer.py / rag_retriever.py)   ← NON IMPLEMENTE
  ↓
LLM structured annotation (annotator_llm.py)  ← NON IMPLEMENTE
  ↓
validation (annotation_validator.py)  ← NON IMPLEMENTE
  ↓
deterministic SP2 aggregation         ← NON IMPLEMENTE
  ↓
frozen annotations                    ← NON IMPLEMENTE
  ↓
Cost (cost_engine.py)                ← IMPLEMENTE (Cost(d;H))
SP3 (risk_engine.py)                 ← IMPLEMENTE (test_reference_example vert)
  ↓
optimizer.py                          ← NON IMPLEMENTE
  ↓
Pareto                                ← NON IMPLEMENTE
  ↓
Y* (reporter.py)                      ← NON IMPLEMENTE
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

**Status : NON IMPLEMENTE.**

`src/rag_indexer.py` et `src/rag_retriever.py` sont des stubs de 7 lignes
chacun.

---

## 6. Implémentation de l'annotation LLM

**Status : NON IMPLEMENTE.**

`src/annotator_llm.py` est un stub de 8 lignes.

---

## 7. Calcul déterministe de SP2

**Status : NON IMPLEMENTE.**

Aucun module ne calcule encore `Realisme`, `P_interaction`,
`P_engagement`, `Effet_prog`, `DE` à partir d'annotations réelles.

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

**Status : NON IMPLEMENTE.**

`src/optimizer.py` est un stub de 7 lignes.

---

## 11. Orchestration du pipeline

**Status : NON IMPLEMENTE.**

Aucun point d'entrée `runs/<run_id>/...` n'existe encore.

---

## 12. Traçabilité et reproductibilité

### Invariant testé — LLM hors du chemin d'exécution

**Status : PARTIELLEMENT TESTÉ.** `tests/test_risk_engine.py::TestLlmOutOfExecutionPath::test_risk_engine_does_not_import_llm_or_rag`
vérifie, par analyse de l'arbre syntaxique (`ast`, pas une recherche de
sous-chaîne), que `src/risk_engine.py` n'importe jamais
`src/annotator_llm.py`, `src/rag_indexer.py` ni `src/rag_retriever.py` —
**ce test est vert**. Le volet symétrique pour `src/optimizer.py` sera
ajouté dès que ce module existera (section 10) ; à ce stade, l'invariant
y est vrai par absence totale de code, mais pas encore testé.

### Déterminisme du LLM

**Status : NON APPLICABLE ENCORE.** Aucun appel LLM n'existe dans le
dépôt à ce stade — la politique de reproductibilité (température 0,
cache par `model`/`prompt_version`/`temperature`/`timestamp`, repli
`rule_based_stub` explicitement marqué comme tel) sera documentée ici
lorsque `src/annotator_llm.py` sera implémenté.

---

## 13. Limites de l'implémentation

- Seule la couche de préparation des connaissances est fonctionnelle à ce
  stade (schémas, graphe, KB ATT&CK, KB déception + staging offline
  D3FEND/Engage/littérature/normalisation). Aucun des modules SP1 → Y*
  n'est encore implémenté.
- Aucun `deception_catalog.json` n'existe : sa composition dépend d'une
  OPEN_DECISION non résolue (quels concepts D3FEND/Engage/littérature
  deviennent des mécanismes finaux de `\mathcal D`) — voir
  `tools/deception_kb/README.md`, section OPEN_DECISION.
- Le test de régression `test_reference_example` (ancre de validation du
  cœur du système) n'existe pas encore : aucun module de risque ou
  d'optimisation ne peut donc être considéré comme correct à ce stade.

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
| 11 sous-métriques | `src/annotator_llm.py` | — | — | — | C6 | NON IMPLEMENTE |
| `Realisme` | (calcul déterministe SP2) | — | — | — | C7 | NON IMPLEMENTE |
| `P_interaction` | (calcul déterministe SP2) | — | — | — | C7 | NON IMPLEMENTE |
| `P_engagement` | (calcul déterministe SP2) | — | — | — | C7 | NON IMPLEMENTE |
| `Effet_prog` | (calcul déterministe SP2) | — | — | — | C7 | NON IMPLEMENTE |
| `DE` | (calcul déterministe SP2) | — | — | — | C7 | NON IMPLEMENTE |
| `Cout(d;H)` | `src/cost_engine.py` | `compute_cost_by_mechanism` | `test_cost_engine.py` | `cost_example.txt` | — | IMPLEMENTE |
| `Gamma`, `A`, `P`, `R` | `src/risk_engine.py` | `propagate_risk` | `test_reference_example` | `risk_example.csv` | C8 | IMPLEMENTE |
| budget | `src/optimizer.py` | — | — | — | — | NON IMPLEMENTE |
| Pareto | `src/optimizer.py` | — | — | — | (chapitre 5) | NON IMPLEMENTE |
| `y*` / `Y*` | `src/optimizer.py` / `src/reporter.py` | — | — | — | (chapitre 5) | NON IMPLEMENTE |
