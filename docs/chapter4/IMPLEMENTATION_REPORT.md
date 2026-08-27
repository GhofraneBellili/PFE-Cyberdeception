# Rapport technique d'implémentation — Chapitre 4

> Ce document est la matière technique directement exploitable pour
> rédiger le chapitre 4 du mémoire. Il diffère de `CLAUDE.md` (contrat
> scientifique / architecture de référence) : ici, seule l'implémentation
> **réellement présente et fonctionnelle** dans le dépôt est décrite.
> Aucune section n'est marquée « implémenté » sans code + tests qui
> passent. Une section absente ou bloquée est marquée `Status : NON
> IMPLEMENTE` ou `Status : NON DISPONIBLE` et rien de plus n'est affirmé
> à son sujet.
>
> Structure alignée sur le plan retenu pour le chapitre 4 du mémoire
> (4.1 Environnement technique → 4.6 Conclusion). Une annexe de
> correspondance chapitre 3 → implémentation suit la conclusion. La
> section finale « Synthèse directement exploitable pour le chapitre 4
> final » fournit, pour chaque sous-section, la matière technique brute
> (objectif/fichiers/entrée/traitement/sortie/limite/capture) — pas le
> texte académique lui-même.

## Invariant central du projet — le LLM hors du chemin d'exécution

**Le LLM (réel ou son repli déterministe) n'intervient jamais dans le
calcul du risque ni dans l'optimisation.** Il annote hors ligne (SP2,
section 4.4.2) ; ses sorties sont validées puis figées (section 4.5.2) ;
l'optimisation (SP3 + `(P)`, sections 4.4.3/4.4.4) lit ensuite
exclusivement la table figée, sans jamais rappeler le LLM. Cet invariant
est vérifié par un test dédié (analyse `ast` de l'arbre syntaxique, pas
une recherche de sous-chaîne) sur **chaque** module du chemin
d'exécution : `src/risk_engine.py`, `src/optimizer.py`,
`src/reporter.py`, `src/annotator_llm.py`, `src/annotation_validator.py`
— tous vérifient qu'ils n'importent jamais `src/annotator_llm.py` (ou,
pour `annotator_llm.py` lui-même, `src/risk_engine.py`/`src/optimizer.py`)
ni `src/rag_indexer.py`/`src/rag_retriever.py`. **Tous ces tests sont
verts.** L'ajout d'un provider LLM réel (`RealLlmAnnotator`,
`src/llm_provider.py`, section 4.4.2) ne change rien à cet invariant :
c'est toujours `AnnotationProvider.annotate()` qui est appelé, une seule
fois par candidat, avant le gel — jamais pendant le coût, le risque,
`(P)` ou le rapport (vérifié dynamiquement par
`tests/test_orchestrator.py::TestLlmOutOfExecutionPath`, comptage
explicite des appels).

---

## 4.1 Environnement technique

### 4.1.1 Technologies utilisées

Voir `TECHNOLOGIES.md` pour le tableau complet et à jour. Résumé :
Python ≥ 3.11, Pydantic 2.x, NetworkX 3.x, pytest ≥ 8.0 — seules
dépendances runtime/dev réelles. Aucune bibliothèque cliente HTTP tierce
(`requests`) : l'appel au provider LLM réel (`src/llm_provider.py`)
utilise `urllib.request` de la bibliothèque standard. Aucune base
vectorielle externe : le RAG (`src/rag_indexer.py`) utilise un index en
mémoire et une vectorisation TF-IDF hachée (choix technique documenté,
section 4.4.2). Aucun frontend, dashboard, API REST métier, Docker, ni
base SQL — conformément à la consigne de ne pas ajouter de complexité
artificielle.

### 4.1.2 Organisation du projet

```text
src/                    modules du modèle (schemas, graph_builder,
                         knowledge_attack, knowledge_deception,
                         admissibility, rag_indexer, rag_retriever,
                         annotator_llm, llm_provider, annotation_validator,
                         cost_engine, risk_engine, optimizer, reporter,
                         orchestrator)
tools/deception_kb/     couche OFFLINE de construction de la KB
                         déception (staging D3FEND/Engage/littérature,
                         catalog_builder.py, mapping_builder.py) —
                         jamais appelée par le runtime SP1-SP3/optimizer
data/deception/         staging versionné + catalogue et mapping réels
                         (deception_catalog.json,
                         attack_deception_mapping.json)
data/attack/            documentation MITRE ATT&CK (README, pas de
                         données brutes versionnées)
examples/                scripts exécutables produisant les sorties
                         réelles de docs/chapter4/outputs/
tests/                  583 tests (pytest), un fichier par module
docs/chapter4/          matière du chapitre 4 (ce document,
                         TECHNOLOGIES.md, SCREENSHOT_MANIFEST.md,
                         outputs/, screenshots/)
runs/                   sorties d'exécution de l'orchestrateur
                         (régénérables, non versionnées — .gitignore)
```

Arborescence réelle complète : `docs/chapter4/outputs/architecture_tree.txt`
(Capture C1, `SCREENSHOT_MANIFEST.md`).

---

## 4.2 Architecture logicielle du système

### 4.2.1 Vue d'ensemble de l'architecture

```text
Knowledge layer (schemas, graph_builder, knowledge_attack,
knowledge_deception + tools/deception_kb/* + catalogue/mapping réels)
  ↓
SP1 (admissibility.py)                         ← IMPLEMENTE
  ↓
RAG (rag_indexer.py / rag_retriever.py)        ← IMPLEMENTE
  ↓
LLM structured annotation (annotator_llm.py)   ← IMPLEMENTE
  (repli déterministe rule_based_stub + provider réel RealLlmAnnotator,
  code testé, non exécuté contre un service réel dans cet environnement)
  ↓
validation + agrégation déterministe SP2       ← IMPLEMENTE
(annotation_validator.py : Realisme/P_interaction/P_engagement/
Effet_prog/DE, §12.3-§12.7)
  ↓
gel de la table d'annotations                  ← IMPLEMENTE
(FrozenAnnotationTable, versionnée, immuable)
  ↓
Coût (cost_engine.py)                          ← IMPLEMENTE
SP3 (risk_engine.py)                           ← IMPLEMENTE (test_reference_example vert)
  ↓
optimizer.py (unicité, budget, Pareto, y*)     ← IMPLEMENTE
  ↓
reporter.py (y* -> Y*, risque avant/après)     ← IMPLEMENTE
  ↓
orchestrator.py (point d'entrée unique)        ← IMPLEMENTE
  (SP1 -> RAG -> annotation -> gel -> coût -> (P) -> risque avant/après
  -> reporter, runs/<run_id>/*.json)
```

Tous les blocs de la chaîne conceptuelle (CLAUDE.md §2) sont désormais
implémentés et testés. Ce qui reste hors périmètre n'est pas un module
manquant mais une **donnée** : un catalogue de déception plus large
(actuellement 3 mécanismes réels, section 4.3.3) et une exécution LLM
réelle (code prêt, non exécutée dans cet environnement, section 4.4.2).

### 4.2.2 Répartition des responsabilités entre les modules

État réel des modules `src/` (source de vérité : `wc -l`, pas une
déclaration d'intention) :

| Module | Lignes | Responsabilité | Statut |
|---|---|---|---|
| `src/schemas.py` | 651 | Contrats de données Pydantic (§26) | IMPLEMENTE |
| `src/graph_builder.py` | 201 | Graphe d'attaque, Entry/Terminal | IMPLEMENTE |
| `src/knowledge_attack.py` | 385 | KB MITRE ATT&CK | IMPLEMENTE |
| `src/knowledge_deception.py` | ~330 | Catalogue D + mapping M_{i,d} (chargement) | IMPLEMENTE |
| `src/admissibility.py` | ~250 | SP1 — `D_i`, `L_{i,h,d}`, `C_{i,h}` | IMPLEMENTE |
| `src/rag_indexer.py` | ~250 | Chunks tracés + vecteurs TF-IDF hachés | IMPLEMENTE |
| `src/rag_retriever.py` | ~70 | Similarité cosinus, top-k | IMPLEMENTE |
| `src/llm_provider.py` | ~180 | Transport HTTP vers un provider LLM réel | IMPLEMENTE (code testé, non exécuté ici) |
| `src/annotator_llm.py` | ~470 | 11 sous-métriques (stub + provider réel + détection) | IMPLEMENTE |
| `src/annotation_validator.py` | ~225 | Validation, agrégats §12.3-§12.7, gel §13 | IMPLEMENTE |
| `src/cost_engine.py` | ~140 | `Cost(d;H)` | IMPLEMENTE |
| `src/risk_engine.py` | ~150 | SP3 — `Gamma`/`A`/`P`/`R` | IMPLEMENTE (`test_reference_example` vert) |
| `src/optimizer.py` | ~270 | Résolution de `(P)` (unicité, budget, Pareto) | IMPLEMENTE |
| `src/reporter.py` | ~90 | Transformation `y*` → `Y*` | IMPLEMENTE |
| `src/orchestrator.py` | ~250 | Point d'entrée unique du pipeline | IMPLEMENTE (hors liste §26 de CLAUDE.md — ajout spécifique chapitre 4) |

En complément, une couche **hors runtime** (`tools/deception_kb/`)
construit, hors ligne et de façon déterministe, le staging documentaire
(D3FEND, MITRE Engage, littérature scientifique) et, désormais, le
catalogue et le mapping finaux (`catalog_builder.py`,
`mapping_builder.py`) — voir section 4.3.3.

---

## 4.3 Préparation des données et des connaissances

### 4.3.1 Représentation de l'instance et du graphe d'attaque

**Objectif.** Fournir les contrats de données typés et validés
représentant `G=(V,E)`, une occurrence `T_{i,h}`, et une instance de
système d'information (graphe + inventaire + emplacements + topologie).

**Fichiers.** `src/schemas.py`, `src/graph_builder.py`.

**Classes/fonctions principales.** `NodeAttributes`,
`TechniqueOccurrence` (identifiant canonique calculé `occurrence_id`),
`AttackGraph`/`AttackGraphEdge` (invariants de divergence `π` validés à
la construction), `SystemInstance`/`SIInventory`/`Asset`/`Location`/
`SITopologyEdge` ; `build_attack_graph`, `to_networkx`, `get_parent_ids`/
`get_child_ids`, `identify_entry_nodes`/`identify_terminal_nodes`.

**Traitement.** Validation Pydantic stricte (`extra="forbid"`) ; aucune
valeur par défaut non prévue par l'architecture ; cohérence croisée
stricte `Critical(h)`/`Accessible(h)` entre les nœuds et l'inventaire.

**Technologie.** Pydantic v2, NetworkX.

**Tests.** `tests/test_schemas.py` (36 tests), `tests/test_graph_builder.py`
(32 tests). Tous verts.

**Limites.** Génération automatique du graphe hors périmètre (CLAUDE.md
§4) — construction manuelle/explicite dans tous les exemples.

### 4.3.2 Base de connaissances MITRE ATT&CK

**Objectif.** Accès structuré à `enterprise-attack.json` (identifiant,
nom, description, tactiques, plateformes).

**Fichiers.** `src/knowledge_attack.py`.

**Classes/fonctions principales.** `load_attack_knowledge`,
`AttackKnowledgeBase`, `AttackTechniqueRecord`, `get_technique`,
`get_tactics`, `get_platforms`, `validate_graph_techniques`.

**Technologie.** Python pur (parseur STIX).

**Tests.** `tests/test_knowledge_attack.py` (47 tests). Tous verts.

### 4.3.3 Base de connaissances de cyberdéception

**Status : IMPLEMENTE — catalogue et mapping réels construits et
chargés (v1, périmètre volontairement restreint, voir Limites).**

**Objectif.** Charger le catalogue fermé `\mathcal D` et le mapping
`M_{i,d}` (technique ATT&CK → mécanismes de déception), déjà normalisés
et versionnés, sans jamais réinterpréter leur contenu (rôle de
`src/knowledge_deception.py`) ; les CONSTRUIRE hors ligne à partir des
sources déjà versionnées (rôle de `tools/deception_kb/`).

**Pipeline réel (§9.1) :**

```text
sources officielles (D3FEND 1.5.0, MITRE Engage 1.0, littérature)
  ↓ (déjà réalisé, phase antérieure)
staging documentaire tracé (data/deception/staging/*.json)
  d3fend_deception_seed, d3fend_attack_mapping_seed,
  engage_activity_seed, engage_attack_mapping_seed,
  literature_document_seed, literature_evidence_seed
  ↓ tools/deception_kb/catalog_builder.py   [NOUVEAU]
data/deception/deception_catalog.json (catalogue fermé D, 3 mécanismes)
  ↓ tools/deception_kb/mapping_builder.py   [NOUVEAU]
data/deception/attack_deception_mapping.json (M_{i,d}, 127 relations)
  ↓ src/knowledge_deception.py (chargement runtime)
DeceptionKnowledgeBase + AttackDeceptionMapping → dict[str, list[str]]
  (format attendu par src.admissibility.build_admissibility_report)
```

**Périmètre v1 du catalogue — décision technique explicite, documentée,
pas une invention.** Un concept D3FEND devient un mécanisme du catalogue
SEULEMENT s'il réunit deux conditions : (1) `is_leaf=True` (un concept
parent/catégorie comme D3-DO « Decoy Object » n'est jamais lui-même
déployable) ; (2) au moins une relation directe avec ATT&CK dans le
staging (nécessaire pour renseigner `interaction_mechanism`, champ requis
du schéma, sans l'inventer). Sur D3FEND 1.5.0, exactement **3 des 9
concepts-feuilles** satisfont ces deux conditions :

| Mécanisme | Nom | Artefact cible | `interaction_mechanism` (dérivé des relations ATT&CK réelles) | `allowed_location_types` |
|---|---|---|---|---|
| `D3-DF` | Decoy File | `d3f:File` | 18 relations distinctes (deletes, produces, reads, executes, ...) | `filesystem` |
| `D3-DUC` | Decoy User Credential | `d3f:Credential` | accesses, adds, copies, creates, forges, may-access, may-create, uses | `credential_store` |
| `D3-DNR` | Decoy Network Resource | `d3f:NetworkResource` | accesses, modifies, unmounts | `network_resource` |

Les 6 autres feuilles (D3-DP, D3-DST, D3-DPR, D3-CHN, D3-SHN, D3-IHN)
possèdent une fiche D3FEND réelle (définition, kb-article) mais **aucune
relation ATT&CK directement tracée** dans ce staging précis : faute de
preuve permettant de renseigner `interaction_mechanism` sans l'inventer,
elles sont explicitement **exclues** (`excluded_concepts` dans le fichier
catalogue, avec raison). Ce n'est pas un défaut de D3FEND — c'est une
limite de couverture de ce staging précis, documentée comme telle.

**Champs volontairement laissés vides, faute de preuve documentaire :**
`requirements`, `realism_factors`, `progression_effects`,
`maintenance_requirements`, `resource_requirements`, et
`admissibility_profile.required_asset_types`/`required_services`/
`required_artifacts`. En particulier, `progression_effects`
(stop/redirect/contain/delay) appartient au modèle du chapitre 3, pas à
l'ontologie D3FEND — ce n'est pas un oubli, c'est la raison d'être de SP2
(section 4.4.2). **Conséquence directe pour SP1** (section 4.4.1) :
`RequirementsSatisfied` évalue « undetermined » pour tout candidat basé
sur ce catalogue — `C_{i,h}` est vide, un résultat honnête, pas un bug.

**Mapping `M_{i,d}` réel.** 127 relations `(attack_id, mechanism_id)`
uniques, filtrées sur les seuls mécanismes du catalogue final (aucun
mécanisme n'est jamais deviné), réduites à 125 techniques ATT&CK
distinctes. Chaque relation conserve sa provenance complète
(`relation_path`, `source`, `source_sha256`) ; les relations dupliquées
dans le staging brut (12 cas, ex. `D3-DUC`↔`T1558`) conservent
plusieurs preuves, jamais fusionnées silencieusement. **Engage
volontairement hors périmètre v1** : les 792 relations Engage↔ATT&CK du
staging ne sont pas matérialisées ici — accepter chaque activité Engage
comme un mécanisme déployable nécessiterait un jugement sémantique non
trivial, déjà signalé comme `OPEN_DECISION` non résolue
(`tools/deception_kb/README.md`, rapprochement D3FEND/Engage interdit
sans décision explicite).

**Fichiers.** `tools/deception_kb/catalog_builder.py`,
`tools/deception_kb/mapping_builder.py` (offline, hors runtime),
`src/knowledge_deception.py` (chargement runtime :
`load_deception_catalog`, `load_attack_deception_mapping`,
`to_sp1_mapping`), `data/deception/deception_catalog.json`,
`data/deception/attack_deception_mapping.json`.

**Technologie.** Python pur.

**Commande réelle d'exécution.**
```bash
python -m tools.deception_kb.catalog_builder
python -m tools.deception_kb.mapping_builder
```

**Tests.** `tests/test_catalog_builder.py` (12 tests, sur le staging réel
— pas une fixture synthétique), `tests/test_mapping_builder.py` (10
tests, idem), `tests/test_knowledge_deception.py` (58 tests, dont 9
nouveaux pour `load_attack_deception_mapping`/`to_sp1_mapping`,
synthétiques par choix — le chargement réel est couvert par les deux
fichiers précédents). Tous verts.

**Capture associée.** C2 — voir `SCREENSHOT_MANIFEST.md`
(`READY_FOR_SCREENSHOT`).

**Limites.** Catalogue volontairement restreint à 3 mécanismes (pas
exhaustif, réf. tâche — « n'a pas besoin d'être exhaustif ») ; Engage
hors périmètre v1 ; `RequirementsSatisfied` toujours « undetermined »
avec ce catalogue (voir section 4.4.1) ; composition finale de
`\mathcal D` au-delà de ce v1 reste une `OPEN_DECISION` non résolue.

---

## 4.4 Mise en œuvre des modules du modèle

### 4.4.1 Construction du domaine admissible — SP1

**Status : IMPLEMENTE (périmètre « petite instance » + catalogue réel).**

**Objectif.** Déterminer, pour chaque occurrence non terminale,
l'ensemble des couples (mécanisme, emplacement) admissibles `C_{i,h}`, à
partir de `D_i`, `Allowed`, `RequirementsSatisfied`, `Relevant` (notation
verrouillée : `Autorise`, `PrerequisSatisfaits`, `Pertinent`).

**Correspondance avec le chapitre 3.** `D_i` (§10.2), `L_{i,h,d}`
(§10.4), `C_{i,h}` (§10.5).

**Fichiers.** `src/admissibility.py`, `tests/test_admissibility.py`,
`examples/sp1_example.py` (catalogue synthétique, pour tests), et
**`examples/sp1_real_example.py` (catalogue et mapping RÉELS, section
4.3.3)**.

**Classes/fonctions principales.** `evaluate_allowed`,
`evaluate_requirements_satisfied`, `evaluate_relevant`,
`build_admissibility_report`.

**Entrées.** Une `SystemInstance` validée, un catalogue
`dict[str, DeceptionMechanism]`, un mapping M_{i,d}
`dict[str, list[str]]`, les seuils `theta_c`/`theta_i`/`theta_a`.

**Traitement.** Pour chaque occurrence non terminale : diagnostic complet
par couple (mécanisme × emplacement) — `mapping`, puis `Autorise`,
`PrerequisSatisfaits`, `Pertinent` (chacun `pass`/`fail`/`undetermined`).
OPEN_DECISION 4 en politique prudente : listes vides →
`undetermined` → exclusion (jamais d'admission devinée). Terminal ⇒
`C_{i,h}=∅` par construction.

**Sorties.** Rapport structuré : par occurrence, `D_i`, `candidates`
(diagnostic complet), `C_{i,h}`, plus un résumé.

**Technologie.** Python pur.

**Commande réelle d'exécution.**
```bash
python -m examples.sp1_example        # catalogue synthétique
python -m examples.sp1_real_example   # catalogue et mapping réels
```

**Tests.** `tests/test_admissibility.py` (21 tests). Tous verts.

**Exemple réel disponible.** `docs/chapter4/outputs/sp1_real_example.json`
/ `.txt`, généré par `examples/sp1_real_example.py` sur deux occurrences
réelles (`T1110.001@DC01`, `T1039@FS01`) : `D_i` correctement peuplé
(`['D3-DUC']`, `['D3-DNR']` — issu du mapping réel), `Autorise`/`Pertinent`
passent au bon emplacement, mais **`PrerequisSatisfaits="undetermined"`
pour les 12 candidats bruts** → `C_{i,h}=∅`, `admissible_count=0`. Un
résultat honnête (section 4.3.3), qui démontre la profondeur diagnostique
de SP1 plutôt que de la masquer.

**Capture associée.** C3 — voir `SCREENSHOT_MANIFEST.md`.

**Limites.** `Pertinent` simplifié à une relation topologique directe
(pas une analyse complète des chemins vers les nœuds terminaux) ; `D_i`
reçu en paramètre, pas construit par ce module ; avec le catalogue réel
v1, `C_{i,h}` est systématiquement vide (section 4.3.3) — un futur
enrichissement du catalogue (`required_asset_types`/`services`/
`artifacts` justifiés par preuve) est nécessaire pour obtenir des
candidats réellement admissibles.

### 4.4.2 Évaluation contextuelle par RAG et LLM — SP2

**Status : IMPLEMENTE — RAG et repli déterministe opérationnels ;
provider LLM réel implémenté et testé, non exécuté dans cet
environnement (aucun service disponible).**

#### RAG (récupération documentaire)

**Fichiers.** `src/rag_indexer.py`, `src/rag_retriever.py`.

**Traitement.** Ingestion réelle des documents D3FEND/Engage/littérature
déjà versionnés → chunks tracés (`chunk_id`, `source_id`, `source_type`,
`document_id`, `locator`, `text`, `text_hash`, `metadata`) → vecteur
TF-IDF haché (256 dimensions, mots-outils exclus, normalisation L2 —
choix technique documenté, pas un embedding sémantique de modèle de
langage, faute de bibliothèque choisie) → similarité cosinus, top-k.

**Tests.** `tests/test_rag_indexer.py` (22 tests, dont ingestion réelle
des 3 fichiers de staging), `tests/test_rag_retriever.py` (13 tests).
Tous verts.

**Exemple réel.** `docs/chapter4/outputs/rag_retrieval_example.txt` /
`rag_chunks_example.json`, générés par `python -m examples.rag_example`
sur un index réel de 124 chunks (44 D3FEND, 62 Engage, 18 littérature) :
requête *"decoy credential store to deceive an adversary on a domain
controller"* → premier résultat `d3fend:D3-DUC:0` (Decoy User Credential),
pertinent.

**Capture associée.** C4 — voir `SCREENSHOT_MANIFEST.md`.

#### Annotation des 11 sous-métriques

**Fichiers.** `src/annotator_llm.py`, `src/llm_provider.py`.

**Classes/fonctions principales.** `AnnotationProvider` (interface),
`RuleBasedStubAnnotator` (repli déterministe), `RealLlmAnnotator`
(provider réel), `detect_provider` (sélection automatique CAS A/B/C),
`AnnotationCache`, `LlmProviderConfig`/`config_from_env`
(`src/llm_provider.py`).

**Repli déterministe `RuleBasedStubAnnotator`.** Score UNIQUE de
chevauchement lexical (contexte ↔ preuves RAG) appliqué identiquement
aux 11 sous-métriques — ne peut PAS les distinguer sémantiquement sans
modèle de langage réel ; `model_version="rule_based_stub"`, jamais
présenté comme un résultat LLM réel.

**Provider réel `RealLlmAnnotator`.** Configuré par variables
d'environnement (`LLM_PROVIDER`=`ollama`|`openai_compatible`,
`LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY`) — aucun modèle ni URL codés
en dur. Appelle réellement `POST {base_url}/api/chat` (Ollama,
`format=json`) ou `POST {base_url}/chat/completions` (OpenAI-compatible,
`response_format=json_object`) via `urllib.request` (bibliothèque
standard), `temperature=0`, timeout et retries limités (2 par défaut).
Le prompt exclut explicitement `system_context` de l'`AnnotationContext`
(protection supplémentaire anti-budget, au-delà de la validation
Pydantic déjà en place, §11.2).

**Validation stricte de la sortie — jamais de valeur inventée en
remplacement.** La réponse doit être un objet JSON `{"annotations": [...]}`
avec exactement les 11 sous-métriques, chacune avec `score`/`confidence`
dans `[0,1]`, `justification` non vide, et `evidence_ids` **référençant
réellement** des preuves présentes dans `context.retrieved_evidence` —
toute sous-métrique manquante/dupliquée, tout score hors bornes, tout
`evidence_id` inexistant lève `LlmOutputValidationError` (héritée
d'`AnnotatorLlmError`), jamais remplacé silencieusement.

**`detect_provider` — sélection automatique, jamais de résultat
fabriqué :**
- **CAS A (Ollama local)** : sonde `GET {base_url}/api/tags` ; si
  `LLM_MODEL` est fourni, vérifie sa disponibilité locale ; sinon utilise
  le premier modèle trouvé (aucun modèle imposé dans le code) ;
  injoignable ou aucun modèle → repli.
- **CAS B (endpoint OpenAI-compatible)** : `LLM_MODEL`+`LLM_BASE_URL`
  fournis → provider réel, sans sondage réseau (pas de quota consommé
  pendant la détection).
- **CAS C (rien de configuré)** : repli `RuleBasedStubAnnotator`, avec la
  raison exacte du repli.

**Cache/reproductibilité.** `AnnotationCache` : clé déterministe
= hash(contexte candidat, y compris les preuves récupérées) +
`model_version` + `prompt_version` → rejoue un résultat identique sans
ré-appeler le provider (testé par comptage d'appels).

**Technologie.** Python pur (`urllib.request`, bibliothèque standard —
pas de nouvelle dépendance).

**Commande réelle d'exécution — repli déterministe (toujours
disponible) :**
```bash
python -m examples.annotator_llm_example
```

**Commande réelle d'exécution — provider réel (nécessite un service
local ou distant configuré par l'utilisateur) :**
```bash
# Option A — Ollama local
LLM_PROVIDER=ollama LLM_MODEL=<votre_modele_local> \
  python -m examples.annotator_llm_real_example

# Option B — endpoint OpenAI-compatible
LLM_PROVIDER=openai_compatible LLM_MODEL=<modele> \
  LLM_BASE_URL=<https://.../v1> LLM_API_KEY=<votre_cle> \
  python -m examples.annotator_llm_real_example
```

**Résultat réel dans cet environnement.** `examples.annotator_llm_real_example`
exécuté ici détecte `annotation_type=rule_based_stub` (« LLM_PROVIDER/
LLM_MODEL/LLM_BASE_URL non configurés » — ni Ollama ni endpoint
OpenAI-compatible disponibles) et **n'écrit aucun fichier
`llm_annotation_real.json`** (anti-fabrication) : il affiche les deux
commandes ci-dessus.

**Tests.** `tests/test_annotator_llm.py` (34 tests : stub, cache,
`RealLlmAnnotator` — 12 tests dédiés couvrant réponse valide, métrique
manquante/dupliquée, score hors bornes, `evidence_id` inconnu, JSON
malformé, retries transitoires puis succès, épuisement des retries,
provider OpenAI-compatible, garde-fou « aucun appel réseau réel » —, et
`detect_provider` — 7 tests couvrant les CAS A/B/C), `tests/test_llm_provider.py`
(15 tests : configuration, appels Ollama/OpenAI-compatible, sondage des
modèles Ollama). **Aucun test n'effectue d'appel réseau réel** (transport
HTTP toujours mocké). Tous verts.

**Exemple réel disponible (repli déterministe).**
`docs/chapter4/outputs/llm_annotation_example.json` — chaîne réelle RAG →
contexte → 11 `Annotation` réelles pour `(T1078@DC01, D3-DUC, auth-store)`.
Le fichier porte explicitement la mention *"PAS un resultat LLM reel"*.

**Capture associée.** C5 (annotation LLM réelle) — `NOT_AVAILABLE` (voir
`SCREENSHOT_MANIFEST.md`) : aucun provider réel exploitable dans cet
environnement.

**Limites.** Aucune annotation sémantique réelle produite dans cet
environnement (CAS C partout) ; le repli déterministe produit un score
identique pour les 11 sous-métriques (chevauchement lexical, pas une
distinction Realism/InteractionLikelihood/Effectiveness) ; le provider
réel n'a jamais été exercé contre un vrai service (seulement contre des
mocks HTTP déterministes en test).

### 4.4.3 Moteur de propagation et de calcul du risque — SP3

**Status : IMPLEMENTE. Ancre de validation `test_reference_example`
VERTE.**

**Objectif.** Propager `Gamma → P^e → A → P → I → R` sur le graphe
d'attaque, en gérant convergence (noisy-OR) et divergence (`π`).

**Correspondance avec le chapitre 3.** CLAUDE.md §14 intégralement.

**Fichiers.** `src/risk_engine.py`, `tests/test_risk_engine.py`,
`examples/sp3_example.py`.

**Classes/fonctions principales.** `compute_gamma`,
`compute_transmitted_edge_probability`, `compute_reachability`
(noisy-OR), `compute_propagated_success_probability`,
`compute_aggregated_impact`, `compute_risk`, `propagate_risk`.

**Ancre de validation — `test_reference_example`.** Scénario
T1566/T1190 → T1003 → T1078 → (T1059/T1057/T1082, `π=1/3`) → T1041,
`DE=0.429` sur T1003 uniquement :

| Grandeur | Calculée | Cible |
|---|---|---|
| `Gamma_1003` | 0.571 | 0.571 |
| `R_avec_deception` (T1041) | 0.0208 | 0.0208 |
| `R_sans_deception` (T1041) | 0.0365 | 0.0365 |
| Réduction relative | 42.9 % | ≈ 42.9 % |

Tolérance `1e-3` (`5e-3` pour la réduction relative).

**Technologie.** Python pur + NetworkX.

**Commande réelle d'exécution.**
```bash
python -m examples.sp3_example
```

**Tests.** `tests/test_risk_engine.py` (23 tests, dont
`test_reference_example` et l'invariant LLM hors chemin d'exécution).
Tous verts.

**Exemple réel disponible.** `docs/chapter4/outputs/risk_example.csv` /
`.txt` (table complète, deux scénarios).

**Limites.** `propagate_risk` ne lit pas encore directement une table
d'annotations figée dans cet exemple isolé (`de_by_occurrence` fourni par
l'appelant) — l'intégration complète existe dans `src/orchestrator.py`
(section 4.5.1), qui lit `FrozenAnnotationTable.de_by_candidate()`.

### 4.4.4 Résolution du problème d'optimisation

**Status : IMPLEMENTE (coût, optimiseur, transformation `y*` → `Y*`).**

#### Coût

**Fichiers.** `src/cost_engine.py`. **Fonctions.**
`compute_deployment_cost`, `compute_resource_cost`,
`compute_maintenance_cost`, `compute_mechanism_cost`,
`compute_cost_by_mechanism`. **Formule.** `Cost(d;H) = C_deploy(d) +
C_resource(d;H) + C_maintenance(d;H)` (§15), indépendant de
l'emplacement par construction (aucune fonction ne prend `l` en
paramètre). **Limite** : `DeceptionMechanism.resource_requirements` reste
du texte libre, non parsé — paramètres numériques attendus déjà
explicites en entrée. **Tests** : `tests/test_cost_engine.py` (13 tests).

#### Optimiseur

**Objectif.** Résoudre `(P)` : minimisation multiobjectif des risques
terminaux sous unicité locale (§16.1) et budget (§16.2).

**Fichiers.** `src/optimizer.py`.

**Classes/fonctions principales.** `Candidate`, `Configuration`,
`build_candidates_from_admissibility`, `enumerate_configurations`,
`filter_by_budget`, `evaluate_configuration`, `dominates`,
`pareto_front`, `select_by_sum_aggregation`, `solve`.

**Traitement.** Énumération exhaustive des configurations (§23, aucune
réduction arbitraire, §24 — garde-fou explicite `max_configurations`) ;
filtrage budgétaire ; évaluation SP3 des risques terminaux ; front de
Pareto par non-dominance ; sélection illustrative `y*` par somme des
risques terminaux sur le front (politique explicite, pas une règle du
chapitre 3).

**Technologie.** Python pur — pas de solveur externe.

**Tests.** `tests/test_optimizer.py` (22 tests, dont la validation
exhaustive sur petite instance conforme à §23).

**Exemple réel.** `docs/chapter4/outputs/optimizer_example.txt`.

#### Reporter — transformation `y*` en `Y*`

**Objectif.** Produire un rapport interprétable par placement :
occurrence protégée, mécanisme, emplacement, coût, effet attendu, risque
avant, risque après, variation, preuves (§17.6).

**Fichiers.** `src/reporter.py`.

**Fonctions.** `build_deployment_report`, `render_text_report`.

**Traitement.** Assemble des valeurs déjà calculées (jamais recalculées) :
`risk_before`/`risk_after` portent sur le risque PROPRE de l'occurrence
protégée — `Gamma_{i,h}` agit sur la transmission vers ses enfants
(§14.3), jamais sur `R_{i,h}` lui-même. Une ligne non terminale affiche
donc normalement `risk_variation=0` (comportement documenté et testé,
pas un bug) ; le risque terminal en aval, lui, diminue réellement
(visible séparément dans `risks.json`, section 4.5.1).

**Tests.** `tests/test_reporter.py` (10 tests).

**Capture associée.** Aucune capture dédiée dans C1–C7 : Pareto/`Y*`
détaillé restent réservés au chapitre 5 (`SCREENSHOT_MANIFEST.md`).

**Limites (coût + optimiseur + reporter).** Exploration exhaustive
uniquement, réservée aux petites instances ; politique de sélection
`y*` illustrative, pas une règle du chapitre 3 ; `reporter.py` ne rédige
aucune justification textuelle narrative, et n'attribue pas la variation
d'un risque terminal à un placement particulier (problème d'attribution
non trivial en cas de placements multiples sur un même chemin).

---

## 4.5 Orchestration et traçabilité

### 4.5.1 Enchaînement des traitements

**Status : IMPLEMENTE.**

**Objectif.** Fournir un point d'entrée unique enchaînant SP1 → RAG →
annotation → validation/agrégation/gel → coût → résolution de `(P)` →
reporting avant/après (§19).

**Fichiers.** `src/orchestrator.py`, `tests/test_orchestrator.py`,
`examples/orchestrator_example.py`.

**Fonction principale.** `run_pipeline`.

**Traitement.** SP1 (`build_admissibility_report`) → pour chaque
candidat admissible : RAG (`retrieve`) puis annotation
(`annotator.annotate`, **une seule fois par candidat**) → gel
(`freeze_table`) → coût (`compute_cost_by_mechanism`) → résolution de
`(P)` (`optimizer.solve`, lit exclusivement la table figée) →
propagation du risque avant/après (`risk_engine.propagate_risk`) →
transformation en `Y*` (`reporter.build_deployment_report`). Chaque
étape est sérialisée dans `runs/<run_id>/` (non versionné, régénérable).

**Sorties.** `runs/<run_id>/{input_manifest,candidates,retrieval,
annotations_raw,annotations_frozen,costs,pareto,deployment_plan,
deployment_report,risks,run_manifest}.json`.

**Commande réelle d'exécution.**
```bash
python -m examples.orchestrator_example
```

**Tests.** `tests/test_orchestrator.py` (11 tests, dont l'intégration
avec le catalogue et le mapping RÉELS — `TestPipelineWithRealCatalogAndMapping`
— qui vérifie que le pipeline complet reste robuste même quand
`C_{i,h}=∅`, cf. section 4.4.1 : `deployment_plan == []`, `status ==
"completed"`, aucun plantage). Tous verts.

**Exemple réel disponible.** `docs/chapter4/outputs/pipeline_example.txt` :
2 candidats évalués, 1 admissible (catalogue synthétique de démonstration
utilisé ici, distinct du catalogue réel de la section 4.3.3), risque
terminal réduit de 0.2974 à 0.2864. `DE` provient du repli déterministe
`rule_based_stub`.

**Capture associée.** C7 — voir `SCREENSHOT_MANIFEST.md`.

**Limites.** Hérite des limites de chaque module (exploration exhaustive,
repli LLM déterministe dans cet environnement). Pas de rapport
explicatif narratif dédié au-delà de `reporter.py`.

### 4.5.2 Conservation des annotations et des preuves

**Status : IMPLEMENTE.**

**Objectif.** Calculer PAR CODE — jamais par le LLM (§11.5) — les
agrégats déterministes `Realisme`/`P_interaction`/`P_engagement`/
`Effet_prog`/`DE` à partir des 11 sous-métriques validées, puis geler le
résultat dans une table versionnée et immuable, réutilisable par
l'optimisation sans jamais rappeler le LLM (§13) : `LLM+RAG → Annotation
→ Validation → Table figée → Optimisation`.

**Fichiers.** `src/annotation_validator.py`, `tests/test_annotation_validator.py`,
`examples/freeze_example.py`.

**Classes/fonctions principales.** `validate_candidate_annotations`,
`compute_realisme`, `compute_p_interaction`, `compute_effet_prog`,
`compute_p_engagement`, `compute_de`, `freeze_candidate`, `freeze_table`,
`FrozenAnnotation`, `FrozenAnnotationTable` (`de_by_candidate()`, pont
direct vers `src.optimizer.build_candidates_from_admissibility`).

**Chaîne de traçabilité des preuves (bout en bout, réellement câblée) :**

```text
chunk RAG (chunk_id, source_type, text, text_hash)
  ↓ src.rag_retriever.to_deception_evidence
DeceptionEvidence (source, passage) — AnnotationContext.retrieved_evidence
  ↓ annotator_llm (stub ou provider réel)
Annotation.evidence (liste d'evidence_ids cités, vérifiés contre les
  preuves réellement récupérées pour le provider réel — jamais un id
  inventé, §4.4.2)
  ↓ annotation_validator.freeze_candidate
FrozenAnnotation.evidence_ids (union triée et dédupliquée des 11
  Annotation.evidence)
  ↓ reporter.build_deployment_report
DeploymentReportRow.evidence_ids (jointes depuis la table figée pour
  chaque placement sélectionné)
```

**Validation de complétude.** Exactement les 11 sous-métriques, sans
doublon, `model_version`/`prompt_version` cohérents entre elles pour un
même candidat — le bornage `[0,1]` et les champs obligatoires sont déjà
garantis par `Annotation` (Pydantic).

**Agrégations (moyenne simple, poids égaux par défaut §12.3/§12.4/§12.6,
pondération explicite acceptée si elle somme à 1) :**
`Realisme = moyenne(R_tech, R_context, R_perception, R_behavior)`,
`P_interaction = moyenne(A_object, A_action, A_source)`,
`Effet_prog = moyenne(S_stop, S_redirect, S_contain, S_delay)`,
`P_engagement = Realisme × P_interaction`, `DE = P_engagement ×
Effet_prog`.

**Gel.** `FrozenAnnotationTable` immuable (`entries` en tuple, dataclass
`frozen=True`), versionnée (`annotation_set_version`, `frozen_at`),
rejetant tout candidat en double.

**Reproductibilité/déterminisme (LLM).** `AnnotationCache`
(`src/annotator_llm.py`, section 4.4.2) : clé = hash(contexte candidat +
preuves récupérées + `model_version` + `prompt_version`) → rejoue un
résultat identique sans ré-appeler le provider (réel ou stub) — testé
par comptage d'appels.

**Technologie.** Python pur.

**Commande réelle d'exécution.**
```bash
python -m examples.freeze_example
```

**Tests.** `tests/test_annotation_validator.py` (21 tests). Tous verts.

**Exemple réel disponible.** `docs/chapter4/outputs/frozen_annotations_example.csv` —
chaîne réelle SP1 → RAG → annotation (stub) → validation/agrégation/gel
pour `(T1078@DC01, D3-DUC, auth-store)` : `Realisme=0.333`,
`P_interaction=0.333`, `P_engagement=0.111`, `Effet_prog=0.333`,
`DE=0.037`.

**Capture associée.** C6 (table figée résultant d'une annotation LLM
réelle) — `NOT_AVAILABLE` (dépend de C5, section 4.4.2). Le fichier
ci-dessus (repli déterministe) reste disponible comme preuve technique
distincte, jamais présentée comme C6.

**Limites.** Les valeurs agrégées de l'exemple réel dépendent du repli
déterministe (section 4.4.2) — identiques entre les 11 sous-métriques,
pas une distinction sémantique réelle. Les FORMULES d'agrégation
elles-mêmes sont réelles et indépendantes de la source des scores bruts.

---

## 4.6 Conclusion

Synthèse technique (pas la conclusion rédigée du mémoire) :

- **Tous les modules de l'architecture (CLAUDE.md §26 + orchestrateur)
  sont implémentés et testés** : 583 tests, tous verts, sur
  `implementation/chapter4`.
- **Deux lacunes documentées, pas masquées :**
  1. Le catalogue de déception réel est volontairement restreint à 3
     mécanismes (D3-DF, D3-DNR, D3-DUC), et ne renseigne aucun
     `required_asset_types`/`services`/`artifacts` faute de preuve — SP1
     produit donc `C_{i,h}=∅` avec ce catalogue (section 4.3.3/4.4.1).
  2. Aucun provider LLM réel n'est exploitable dans cet environnement —
     le code (`RealLlmAnnotator`, `detect_provider`) est implémenté et
     testé par mocks HTTP, mais jamais exécuté contre un vrai service
     (section 4.4.2). Les commandes exactes pour le faire localement sont
     documentées.
- **Ce que ces deux lacunes n'empêchent pas de démontrer** : la chaîne
  complète SP1 → RAG → annotation → gel → coût → SP3 → optimisation →
  reporter → orchestrateur s'exécute de bout en bout sur des données
  réelles (catalogue, mapping, corpus RAG, graphe) à chaque étape, y
  compris dans le cas dégénéré `C_{i,h}=∅` (testé explicitement).
- **Réservé au chapitre 5** : SP3 détaillé sur un cas d'étude complet,
  front de Pareto, réduction de risque quantifiée, plan `Y*` final,
  comparaison avec/sans déception — tous les modules nécessaires existent
  déjà, seule l'analyse expérimentale reste à mener.

---

## Annexe — Matrice de correspondance chapitre 3 → implémentation

| Élément chapitre 3 | Module | Fonction | Test | État |
|---|---|---|---|---|
| `G=(V,E)` | `src/graph_builder.py` | `build_attack_graph` | `test_graph_builder.py` | IMPLEMENTE |
| Attributs de nœud | `src/schemas.py` | `NodeAttributes` | `test_schemas.py` | IMPLEMENTE |
| KB ATT&CK | `src/knowledge_attack.py` | `load_attack_knowledge` | `test_knowledge_attack.py` | IMPLEMENTE |
| Catalogue `D` | `src/knowledge_deception.py` + `tools/deception_kb/catalog_builder.py` | `load_deception_catalog` | `test_knowledge_deception.py`, `test_catalog_builder.py` | IMPLEMENTE (3 mécanismes réels) |
| `M_{i,d}` | `src/knowledge_deception.py` + `tools/deception_kb/mapping_builder.py` | `load_attack_deception_mapping`/`to_sp1_mapping` | `test_knowledge_deception.py`, `test_mapping_builder.py` | IMPLEMENTE (127 relations réelles) |
| `D_i`, `L_{i,h,d}`, `C_{i,h}` | `src/admissibility.py` | `build_admissibility_report` | `test_admissibility.py` | IMPLEMENTE |
| 11 sous-métriques | `src/annotator_llm.py` | `RuleBasedStubAnnotator`/`RealLlmAnnotator` | `test_annotator_llm.py` | IMPLEMENTE (stub réel ; provider réel testé, non exécuté) |
| `Realisme`/`P_interaction`/`P_engagement`/`Effet_prog`/`DE` | `src/annotation_validator.py` | `compute_realisme` etc. | `test_annotation_validator.py` | IMPLEMENTE |
| `Cout(d;H)` | `src/cost_engine.py` | `compute_cost_by_mechanism` | `test_cost_engine.py` | IMPLEMENTE |
| `Gamma`, `A`, `P`, `R` | `src/risk_engine.py` | `propagate_risk` | `test_reference_example` | IMPLEMENTE |
| unicité + budget + Pareto | `src/optimizer.py` | `solve` | `test_optimizer.py` | IMPLEMENTE |
| `y*` / `Y*` | `src/optimizer.py` + `src/reporter.py` | `solve`/`build_deployment_report` | `test_optimizer.py`, `test_reporter.py` | IMPLEMENTE |

---

# Synthèse directement exploitable pour le chapitre 4 final

> Matière technique brute par sous-section, pour rédaction académique
> ultérieure — pas le texte du chapitre lui-même.

## 4.1.1 Technologies utilisées
- **Objectif** : documenter les technologies réellement utilisées.
- **Fichiers/modules** : `docs/chapter4/TECHNOLOGIES.md` (source de vérité), `pyproject.toml`.
- **Technologie** : Python ≥ 3.11, Pydantic 2.x, NetworkX 3.x, pytest ≥ 8.0, `urllib.request` (stdlib).
- **Entrée** : n/a (méta-documentation).
- **Traitement** : n/a.
- **Sortie** : tableau technologies.
- **Détail important** : aucune dépendance HTTP tierce (`requests`) — choix technique délibéré, stdlib suffisante.
- **Limite** : aucune.
- **Capture recommandée** : aucune (tableau textuel suffisant).

## 4.1.2 Organisation du projet
- **Objectif** : montrer la structure réelle du dépôt.
- **Fichiers/modules** : arborescence complète (`src/`, `tools/deception_kb/`, `data/deception/`, `examples/`, `tests/`, `docs/chapter4/`, `runs/`).
- **Technologie** : n/a.
- **Entrée** : dépôt Git.
- **Traitement** : script Python ponctuel de listage récursif.
- **Sortie** : `docs/chapter4/outputs/architecture_tree.txt`.
- **Détail important** : `runs/` n'est pas versionné (régénérable, `.gitignore`) — seule la preuve d'exécution `docs/chapter4/outputs/pipeline_example.txt` est retenue.
- **Limite** : aucune.
- **Capture recommandée** : C1.

## 4.2.1 Vue d'ensemble de l'architecture
- **Objectif** : montrer la chaîne complète SP1→RAG→SP2→SP3→optimisation→reporter→orchestrateur.
- **Fichiers/modules** : tous les modules `src/`.
- **Technologie** : n/a (diagramme).
- **Entrée** : n/a.
- **Traitement** : n/a.
- **Sortie** : diagramme textuel (section 4.2.1 ci-dessus).
- **Détail important** : tous les blocs sont IMPLEMENTE ; ce qui manque est une donnée (catalogue plus large, exécution LLM réelle), pas un module.
- **Limite** : aucune.
- **Capture recommandée** : aucune (diagramme reproductible dans le texte).

## 4.2.2 Répartition des responsabilités entre les modules
- **Objectif** : cartographier responsabilité ↔ module.
- **Fichiers/modules** : tableau de la section 4.2.2.
- **Technologie** : n/a.
- **Entrée** : `wc -l` sur `src/*.py`.
- **Traitement** : n/a.
- **Sortie** : tableau modules/lignes/statut.
- **Détail important** : `src/orchestrator.py` n'appartient pas à la liste `§26` de CLAUDE.md — ajout spécifique à la tâche chapitre 4.
- **Limite** : aucune.
- **Capture recommandée** : aucune.

## 4.3.1 Représentation de l'instance et du graphe d'attaque
- **Objectif** : formaliser `T_{i,h}`, `G=(V,E)`, l'instance SI.
- **Fichiers/modules** : `src/schemas.py`, `src/graph_builder.py`.
- **Technologie** : Pydantic v2, NetworkX.
- **Entrée** : dictionnaires/JSON fournis par l'appelant.
- **Traitement** : validation stricte, invariants de divergence `π`, cohérence Critical/Accessible.
- **Sortie** : objets `AttackGraph`/`SystemInstance` validés.
- **Détail important** : `occurrence_id` calculé automatiquement (`technique_id@asset_id`) — jamais désynchronisé.
- **Limite** : génération automatique du graphe hors périmètre.
- **Capture recommandée** : aucune (déjà couvert par C3).

## 4.3.2 Base de connaissances MITRE ATT&CK
- **Objectif** : accès structuré à ATT&CK Enterprise.
- **Fichiers/modules** : `src/knowledge_attack.py`.
- **Technologie** : Python pur (parseur STIX).
- **Entrée** : `enterprise-attack.json`.
- **Traitement** : indexation par identifiant, extraction tactiques/plateformes.
- **Sortie** : `AttackKnowledgeBase`.
- **Détail important** : aucun mapping ATT&CK↔déception ici (rôle de `knowledge_deception.py`).
- **Limite** : aucune.
- **Capture recommandée** : aucune.

## 4.3.3 Base de connaissances de cyberdéception
- **Objectif** : catalogue fermé `D` + mapping `M_{i,d}` réels et tracés.
- **Fichiers/modules** : `tools/deception_kb/catalog_builder.py`, `mapping_builder.py`, `src/knowledge_deception.py`, `data/deception/deception_catalog.json`, `data/deception/attack_deception_mapping.json`.
- **Technologie** : Python pur.
- **Entrée** : staging D3FEND déjà versionné (`d3fend_deception_seed_1.5.0.json`, `d3fend_attack_mapping_seed_1.5.0.json`).
- **Traitement** : filtrage is_leaf + relation ATT&CK directe → 3 mécanismes ; dérivation déterministe de `interaction_mechanism`/`allowed_location_types` depuis les données D3FEND réelles.
- **Sortie** : catalogue (3 mécanismes) + mapping (127 relations).
- **Détail important** : les 6 autres feuilles D3FEND et les 792 relations Engage sont explicitement EXCLUES avec raison tracée — c'est le point le plus riche à expliquer dans le mémoire (anti-fabrication appliquée concrètement).
- **Limite** : catalogue non exhaustif ; `required_asset_types`/`services`/`artifacts` vides partout (conséquence en 4.4.1).
- **Capture recommandée** : C2.

## 4.4.1 Construction du domaine admissible — SP1
- **Objectif** : `D_i`→`L_{i,h,d}`→`C_{i,h}`.
- **Fichiers/modules** : `src/admissibility.py`, `examples/sp1_real_example.py`.
- **Technologie** : Python pur.
- **Entrée** : `SystemInstance`, catalogue réel, mapping réel, seuils `theta`.
- **Traitement** : diagnostic `Autorise`/`PrerequisSatisfaits`/`Pertinent` par candidat.
- **Sortie** : `sp1_real_example.json`/`.txt`.
- **Détail important** : avec le catalogue réel, `C_{i,h}=∅` systématiquement (`RequirementsSatisfied="undetermined"`) — un résultat honnête à expliquer explicitement, pas à cacher.
- **Limite** : `Pertinent` simplifié (topologie directe uniquement).
- **Capture recommandée** : C3.

## 4.4.2 Évaluation contextuelle par RAG et LLM — SP2
- **Objectif** : RAG (récupération) + 11 sous-métriques annotées.
- **Fichiers/modules** : `src/rag_indexer.py`, `src/rag_retriever.py`, `src/annotator_llm.py`, `src/llm_provider.py`.
- **Technologie** : TF-IDF haché (choix technique, `hashlib.blake2b`) ; `urllib.request` pour le provider LLM réel.
- **Entrée** : documents staging (RAG) ; `AnnotationContext` (annotation).
- **Traitement** : chunking → vecteurs → similarité cosinus (RAG) ; prompt structuré → appel HTTP → validation stricte de la sortie JSON (LLM).
- **Sortie** : `RetrievalResult` (RAG) ; 11 `Annotation` (LLM).
- **Détail important** : le provider réel est entièrement implémenté et testé (mocks HTTP), mais AUCUNE exécution réelle n'a eu lieu dans cet environnement — à énoncer explicitement dans le mémoire, avec la commande de reproduction locale.
- **Limite** : repli déterministe = score identique sur les 11 sous-métriques (pas une annotation sémantique réelle).
- **Capture recommandée** : C4 (RAG) ; C5 (LLM réel) `NOT_AVAILABLE`.

## 4.4.3 Moteur de propagation et de calcul du risque — SP3
- **Objectif** : `Gamma→P^e→A→P→I→R`.
- **Fichiers/modules** : `src/risk_engine.py`.
- **Technologie** : Python pur + NetworkX.
- **Entrée** : `AttackGraph`, `q`/`I`/`DE` par occurrence.
- **Traitement** : tri topologique, noisy-OR en convergence, `π` en divergence uniquement.
- **Sortie** : `R_{i,h}` par occurrence.
- **Détail important** : `test_reference_example` reproduit exactement l'ancre de validation du chapitre 3 (`DE=0.429`, réduction 42.9 %) — argument central de correction du moteur.
- **Limite** : aucune (module considéré complet).
- **Capture recommandée** : aucune dans C1–C7 (réservé au chapitre 5).

## 4.4.4 Résolution du problème d'optimisation
- **Objectif** : `Cost(d;H)` → `(P)` → `y*` → `Y*`.
- **Fichiers/modules** : `src/cost_engine.py`, `src/optimizer.py`, `src/reporter.py`.
- **Technologie** : Python pur, énumération exhaustive.
- **Entrée** : `C_{i,h}`, `DE` figé, `Cost(d;H)`, `B_total`.
- **Traitement** : configurations → filtrage budget → SP3 → front de Pareto → sélection illustrative → rapport `Y*`.
- **Sortie** : `pareto.json`, `deployment_plan.json`, `deployment_report.json`.
- **Détail important** : `risk_before`/`risk_after` d'une ligne `Y*` portent sur le risque PROPRE de l'occurrence protégée (souvent `variation=0`), pas le risque terminal en aval — nuance à expliciter pour ne pas laisser croire à un défaut.
- **Limite** : politique de sélection `y*` illustrative, pas une règle du chapitre 3 ; pas d'attribution causale par placement d'une baisse de risque terminal.
- **Capture recommandée** : aucune dans C1–C7 (Pareto/`Y*` réservés au chapitre 5).

## 4.5.1 Enchaînement des traitements
- **Objectif** : point d'entrée unique bout-en-bout.
- **Fichiers/modules** : `src/orchestrator.py`.
- **Technologie** : Python pur (`json`, `pathlib`, `dataclasses`).
- **Entrée** : instance, catalogue, mapping, index RAG, provider, paramètres de coût/budget.
- **Traitement** : SP1→RAG→annotation (1x/candidat)→gel→coût→`(P)`→risque avant/après→rapport.
- **Sortie** : `runs/<run_id>/*.json` (10 fichiers).
- **Détail important** : testé explicitement avec le catalogue et le mapping RÉELS (`C_{i,h}=∅`) — le pipeline reste robuste, pas de plantage sur le cas dégénéré.
- **Limite** : hérite des limites de chaque module amont.
- **Capture recommandée** : C7.

## 4.5.2 Conservation des annotations et des preuves
- **Objectif** : agrégation déterministe SP2 + gel + traçabilité des preuves.
- **Fichiers/modules** : `src/annotation_validator.py`.
- **Technologie** : Python pur.
- **Entrée** : 11 `Annotation` validées par candidat.
- **Traitement** : `Realisme`/`P_interaction`/`P_engagement`/`Effet_prog`/`DE` (moyennes, produits) → `FrozenAnnotation` immuable.
- **Sortie** : `FrozenAnnotationTable` (`de_by_candidate()` → pont direct vers l'optimiseur).
- **Détail important** : chaîne de traçabilité complète chunk RAG → `DeceptionEvidence` → `Annotation.evidence` → `FrozenAnnotation.evidence_ids` → `DeploymentReportRow.evidence_ids`, entièrement réelle et testée.
- **Limite** : les scores agrégés de l'exemple réel dépendent du repli déterministe (section 4.4.2).
- **Capture recommandée** : C6 (`NOT_AVAILABLE`, dépend de C5).
