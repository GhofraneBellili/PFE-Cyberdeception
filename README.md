# PFE — Système de cyberdéception

Ce fichier est le **journal technique cumulatif** de l'implémentation du
PFE. Il documente uniquement ce qui est réellement implémenté, testé et
présent dans le dépôt à la date de la dernière mise à jour. Les travaux
prévus mais non réalisés sont explicitement marqués **« Non implémenté à ce
stade »** ou **« À venir »**.

Le contrat scientifique et architectural complet du projet est
`CLAUDE.md` (et le document de référence `docs/architecture_complete_cyberdeception_PFE.pdf`
qu'il synthétise). Ce README n'en est pas une copie : il en documente la
**traduction logicielle réellement construite**.

## 1. Objectif du projet

Le système vise à déterminer quelle technique de cyberdéception déployer,
contre quelle occurrence d'attaque, et à quel emplacement du système
d'information, sous contraintes opérationnelles et budgétaires, afin de
réduire le risque résiduel sur les objectifs critiques. La chaîne
conceptuelle complète est :

```text
Graphe d'attaque
  → KB ATT&CK
  → KB cyberdéception
  → SP1 (admissibilité)
  → SP2 (annotation LLM+RAG)
  → SP3 (propagation du risque)
  → optimisation sous budget
  → plan de déploiement Y*
```

**Tous les blocs de cette chaîne ne sont pas encore implémentés.** À la
date de ce document, seules les fondations (schémas de données, graphe
d'attaque, deux bases de connaissances structurées, et une première couche
de construction de données offline pour la KB déception) existent.

## 2. Architecture logicielle

| Module | Responsabilité | État |
|---|---|---|
| `src/schemas.py` | Modèles Pydantic (contrats de données) | Validé |
| `src/graph_builder.py` | Construction/navigation du graphe d'attaque | Validé |
| `src/knowledge_attack.py` | KB structurée MITRE ATT&CK | Validé |
| `src/knowledge_deception.py` | Moteur du catalogue cyberdéception normalisé | Validé |
| `tools/deception_kb/d3fend_seed_builder.py` | Staging offline D3FEND (branche Deceive) | Validé (staging uniquement, pas le catalogue final) |
| `src/admissibility.py` | SP1 — espace admissible \(C_{i,h}\) | Non implémenté à ce stade |
| `src/rag_indexer.py` / `src/rag_retriever.py` | RAG | Non implémenté à ce stade |
| `src/annotator_llm.py` / `src/annotation_validator.py` | SP2 — annotation LLM | Non implémenté à ce stade |
| `src/risk_engine.py` | SP3 — propagation du risque | Non implémenté à ce stade |
| `src/cost_engine.py` | Calcul du coût | Non implémenté à ce stade |
| `src/optimizer.py` | Résolution du problème global \((P)\) | Non implémenté à ce stade |
| `src/reporter.py` | Production du rapport \(Y^*\) | Non implémenté à ce stade |

CI GitHub Actions : verte sur `master` à chaque commit documenté ci-dessous
(`.github/workflows/tests.yml`, déclenchée sur `push`/`pull_request`).

## 3. Étapes techniques validées

### Étape 1 — Fondations et schémas de données

#### Objectif

Fournir les contrats de données typés et validés (Pydantic v2) qui
représentent les objets mathématiques du modèle : occurrence d'attaque
\(T_{i,h}\), graphe d'attaque \(G=(V,E)\), fiche de mécanisme de
cyberdéception, annotation LLM auditable, contexte remis à l'annotateur, et
instance de système d'information (graphe + inventaire + emplacements +
topologie).

#### Position dans l'architecture

```text
(aucune entrée — module fondation)
  → src/schemas.py
  → objets validés consommés par tous les autres modules
```

#### Entrées

Dictionnaires/JSON bruts fournis par l'appelant à la construction de chaque
modèle (aucune source de données propre à ce module).

#### Traitement réalisé

- `NodeAttributes` porte les attributs minimaux \(Attr(T_{i,h})\) : tactiques,
  outcomes (uniquement en tant qu'attribut, jamais un sommet indépendant),
  \(q_{i,h}\), impacts \(I^C, I^I, I^A\), `Critical(h)`, `Accessible(h)`.
- `TechniqueOccurrence` valide `technique_id` contre le format ATT&CK
  (`T\d{4}` avec sous-technique optionnelle) et expose un identifiant
  canonique calculé `occurrence_id` (`technique_id@asset_id`).
- `AttackGraph` valide que \(V\) ne contient pas d'occurrences dupliquées,
  que chaque arête référence des nœuds existants, qu'aucune arête n'est
  dupliquée (E est un ensemble), et que \(\pi\) n'apparaît que sur les
  parents divergents, avec somme des branches égale à 1 quand \(\pi\) est
  explicite.
- `DeceptionMechanism` et ses sous-modèles (`DeceptionEvidence`,
  `DeceptionResourceRequirements`, `DeceptionAdmissibilityProfile`)
  reprennent exactement le schéma de fiche de déception (§9.2 CLAUDE.md),
  avec un identifiant libre (pas de contrainte `DTxx`).
- `Annotation` porte les 11 sous-métriques (Realism/InteractionLikelihood/
  Effectiveness) avec score, justification, preuve et confiance bornés
  \([0,1]\). `AnnotationContext` interdit récursivement toute clé évoquant
  un budget, y compris imbriquée.
- `Asset`, `Location`, `SITopologyEdge`, `SIInventory`, `SystemInstance`
  représentent l'instance du SI, avec vérification croisée stricte entre
  les attributs `Critical`/`Accessible` d'un nœud et l'inventaire.

#### Sorties

L'ensemble des classes Pydantic ci-dessus, importées par les autres
modules (`from src.schemas import ...`).

#### Fichiers concernés

- `src/schemas.py`
- `tests/test_schemas.py`

#### Fonctions principales

`StrictModel` (base commune `extra="forbid"`), `NodeAttributes`,
`TechniqueOccurrence`, `AttackGraphEdge`, `AttackGraph`, `DeceptionMechanism`
(+ sous-modèles), `Annotation`, `AnnotationContext`, `Asset`, `Location`,
`SITopologyEdge`, `SIInventory`, `SystemInstance`, `build_occurrence_id`.

#### Invariants et règles respectées

- les outcomes ne sont jamais des sommets indépendants (§3.2) ;
- \(\pi\) intervient uniquement en divergence, jamais ailleurs (§14.4) ;
- \(E\) est un ensemble : aucune arête dupliquée ;
- aucune valeur manquante n'est inventée silencieusement (§25.3) ;
- toute grandeur probabiliste/score est bornée \([0,1]\) (§25.2) ;
- le budget \(B_{total}\) ne peut jamais apparaître dans le contexte
  d'annotation (§11.2) ;
- aucune mutation implicite : les mappings d'index sont en lecture seule
  là où c'est pertinent.

#### Tests et validation

`tests/test_schemas.py` — cas valides et cas rejetés (bornes, champs
obligatoires, doublons, incohérences graphe/inventaire). 36 tests au moment
de la validation. CI verte.

#### Traçabilité

Commits de validation : `107f502` (création initiale), `c8a0ca7` (topologie
SI + invariants), `3ca63c4` (interdiction des arêtes dupliquées).

#### Limites actuelles

Ce module ne calcule aucune propagation (\(A, P, \Gamma, R, DE\)), ne
réalise aucune admissibilité, aucun mapping ATT&CK↔déception, aucune
annotation LLM. Ce sont uniquement des structures de données validées.

#### Lien avec l'étape suivante

`graph_builder.py`, `knowledge_attack.py` et `knowledge_deception.py`
importent et réutilisent directement ces modèles sans les redéfinir.

---

### Étape 2 — Construction et manipulation du graphe d'attaque

#### Objectif

Fournir un module générique (aucune règle propre à un cas d'usage) capable
de construire, charger, représenter et naviguer le graphe d'attaque
\(G=(V,E)\), et d'y identifier les nœuds Entry et Terminal selon les règles
exactes de l'architecture.

#### Position dans l'architecture

```text
TechniqueOccurrence[] + AttackGraphEdge[] (ou fichier JSON)
  → src/graph_builder.py
  → AttackGraph + représentation NetworkX + navigation parents/enfants
    + identifiants des nœuds Entry/Terminal
```

#### Entrées

Séquences de `TechniqueOccurrence`/`AttackGraphEdge` déjà valides, ou
chemin explicite vers un fichier JSON conforme au schéma `AttackGraph`.

#### Traitement réalisé

- `build_attack_graph` délègue toute la validation à `AttackGraph`
  (schemas.py) sans dupliquer de logique.
- `load_attack_graph_json` lit un fichier UTF-8, parse le JSON, et le
  transmet à `AttackGraph.model_validate` ; aucune valeur manquante n'est
  complétée automatiquement.
- `to_networkx` construit une copie fidèle en `nx.DiGraph` : clé de nœud =
  `occurrence_id`, objet `TechniqueOccurrence` conservé sous la clé
  `"occurrence"`, `branch_probability` conservé tel quel (y compris
  `None`) — aucun recalcul.
- `get_parent_ids`/`get_child_ids` naviguent via cette représentation
  NetworkX, en conservant l'ordre d'insertion des arêtes.
- `is_entry_node`/`identify_entry_nodes` appliquent exactement :
  \(Entry(T_{i,h}) = 1 \iff \text{"initial-access"} \in Tactics(T_i) \text{ ET } Accessible(h) = 1\).
- `is_terminal_node`/`identify_terminal_nodes` appliquent exactement :
  \(Terminal(T_{i,h}) = 1\) si \(Critical(h)=1\) OU \(I^C \ge \theta_C\) OU
  \(I^I \ge \theta_I\) OU \(I^A \ge \theta_A\), avec les trois seuils
  **obligatoirement fournis par l'appelant** (aucune valeur par défaut).

#### Sorties

`AttackGraph`, `nx.DiGraph`, listes d'`occurrence_id` (parents, enfants,
nœuds Entry, nœuds Terminal).

#### Fichiers concernés

- `src/graph_builder.py`
- `tests/test_graph_builder.py`

#### Fonctions principales

`build_attack_graph`, `load_attack_graph_json`, `to_networkx`,
`get_parent_ids`, `get_child_ids`, `is_entry_node`, `identify_entry_nodes`,
`is_terminal_node`, `identify_terminal_nodes`.

#### Invariants et règles respectées

- un nœud feuille (`out-degree == 0`) n'est **pas** terminal par
  définition — seuls les critères Critical/impact comptent ;
- aucune valeur de seuil \(\theta\) par défaut n'est inventée ;
- le module ne calcule ni \(A\), ni \(P\), ni \(\Gamma\), ni \(R\), ni
  \(DE\) — ces calculs appartiennent au futur `risk_engine.py` ;
- aucun identifiant de technique ATT&CK ni d'actif n'est codé en dur dans
  le code de production (démontré par un test dédié avec des identifiants
  fictifs) ;
- les cycles ne sont ni imposés absents, ni rejetés (décision différée).

#### Tests et validation

`tests/test_graph_builder.py` — construction, JSON, NetworkX, navigation,
Entry, Terminal, généralité, cycles. 32 tests au moment de la validation.
CI verte.

#### Traçabilité

Commit de validation : `28aa428`.

#### Limites actuelles

Aucune construction automatique du graphe depuis des logs, vulnérabilités
ou renseignement ; aucune gestion de cycle pour la propagation du risque
(différée) ; aucun calcul de risque.

#### Lien avec l'étape suivante

`knowledge_attack.py` peut valider que chaque `technique_id` d'un
`AttackGraph` existe réellement dans la base de connaissances ATT&CK
chargée, sans modifier le graphe.

---

### Étape 3 — Base de connaissances MITRE ATT&CK

#### Objectif

Charger, valider et indexer de manière déterministe les techniques
offensives MITRE ATT&CK Enterprise à partir d'un bundle STIX officiel, et
fournir un accès en lecture pour les futurs modules.

#### Position dans l'architecture

```text
enterprise-attack.json (chemin fourni explicitement)
  → src/knowledge_attack.py
  → AttackKnowledgeBase (index technique_id -> AttackTechniqueRecord)
```

#### Entrées

Fichier JSON conforme à un bundle STIX (`{"type": "bundle", "objects": [...]}`).

#### Traitement réalisé

- `load_attack_knowledge` vérifie que la racine est un objet JSON, que
  `type == "bundle"`, que `objects` est une liste ; ne retient que les
  objets `"attack-pattern"`.
- L'identifiant ATT&CK humain (`Txxxx`/`Txxxx.xxx`) est lu **uniquement**
  dans `external_references` (jamais déduit du nom ou du `stix_id`) ; un
  objet sans identifiant exploitable est ignoré, jamais indexé sous un
  identifiant inventé.
- Les champs optionnels (`revoked`, `x_mitre_deprecated`,
  `x_mitre_is_subtechnique`, `x_mitre_platforms`, `kill_chain_phases`,
  `description`, `x_mitre_version`, `external_references`) distinguent
  explicitement l'absence (défaut autorisé) de la présence avec un type
  incompatible (erreur explicite `AttackKnowledgeError`, jamais traitée
  silencieusement comme une absence).
- Les techniques `revoked`/`deprecated` sont exclues par défaut
  (indépendamment l'une de l'autre), avec options `include_revoked`/
  `include_deprecated`.
- Un identifiant ATT&CK dupliqué parmi les techniques effectivement
  retenues (après filtrage revoked/deprecated) lève une erreur explicite.
- `validate_graph_techniques` vérifie que chaque `technique_id` d'un
  `AttackGraph` existe dans la KB chargée, sans jamais modifier le graphe.

#### Sorties

`AttackKnowledgeBase` (`source_path`, `techniques_by_id` en lecture seule).

#### Fichiers concernés

- `src/knowledge_attack.py`
- `tests/test_knowledge_attack.py`
- `data/attack/README.md` (emplacement attendu du vrai `enterprise-attack.json`, non inclus dans le dépôt)

#### Fonctions principales

`load_attack_knowledge`, `get_technique`, `has_technique`,
`list_technique_ids`, `get_tactics`, `get_platforms`,
`validate_graph_techniques`.

#### Invariants et règles respectées

- aucune correspondance approximative, aucune correction automatique ;
- `revoked` et `deprecated` ne sont jamais confondus ;
- aucun appel réseau, aucun LLM ;
- `mechanisms_by_id`/`techniques_by_id` non ambigu (doublon détecté, jamais
  arbitré silencieusement) ;
- aucune technique ATT&CK codée en dur dans le code de production.

#### Tests et validation

`tests/test_knowledge_attack.py` — chargement, extraction, identifiants,
revoked/deprecated, accès, validation de graphe, durcissement des types,
généralité. 47 tests au moment de la validation (36 initiaux + 11 de
durcissement). CI verte.

#### Traçabilité

Commits de validation : `ffb359d` (implémentation initiale), `221450c`
(durcissement : vérification explicite `type == "bundle"`, distinction
absence/mauvais type sur les champs optionnels).

#### Limites actuelles

`enterprise-attack.json` n'est pas présent dans le dépôt (le chemin est
toujours fourni explicitement par l'appelant). Aucun mapping vers des
mécanismes de déception. Aucune reconstruction des relations
technique/sous-technique.

#### Lien avec l'étape suivante

Fournit, en parallèle de `knowledge_deception.py`, l'une des deux bases de
connaissances indépendantes (ATT&CK et cyberdéception) nécessaires à la
future construction de SP1 (mapping \(M_{i,d}\), \(D_i\)).

---

### Étape 4 — Moteur du catalogue structuré de cyberdéception

#### Objectif

Charger et valider de manière stricte le **catalogue normalisé final** de
mécanismes de cyberdéception (format interne PFE), et fournir un accès en
lecture déterministe pour les futurs SP1/SP2. Ce module réutilise
strictement les modèles `DeceptionMechanism` et associés de
`src/schemas.py`, sans les redéfinir.

#### Position dans l'architecture

```text
catalogue JSON normalisé PFE ({"catalog_version": ..., "mechanisms": [...]})
  → src/knowledge_deception.py
  → DeceptionKnowledgeBase (mechanisms_by_id, provenance SHA-256)
```

#### Entrées

Fichier JSON `{"catalog_version": "...", "mechanisms": [...]}`, chaque
élément de `mechanisms` conforme au schéma `DeceptionMechanism`.

#### Traitement réalisé

- `load_deception_catalog` calcule le SHA-256 sur les octets exacts du
  fichier, vérifie que la racine est un objet JSON, que `catalog_version`
  est une chaîne non vide (jamais complétée par un défaut du type `"1.0"`),
  que `mechanisms` est une liste.
- Chaque élément est validé via `DeceptionMechanism.model_validate` (aucune
  revalidation manuelle) ; une erreur Pydantic remonte telle quelle.
- Règle propre à cette couche, plus stricte que le schéma seul : un
  mécanisme validé **sans aucune** `DeceptionEvidence` est rejeté.
- Un `id` de mécanisme dupliqué lève une erreur explicite (jamais de fusion
  ni de conservation silencieuse du premier/dernier).
- `admissibility_profile` est chargé et conservé tel quel, sans aucune
  interprétation SP1 (y compris pour des listes vides).

#### Sorties

`DeceptionKnowledgeBase` (`source_path`, `catalog_version`,
`mechanisms_by_id` en lecture seule, `source_sha256`).

#### Fichiers concernés

- `src/knowledge_deception.py`
- `tests/test_knowledge_deception.py`
- `data/deception/README.md` (emplacement attendu du catalogue final `deception_catalog.json`, non créé à ce stade)

#### Fonctions principales

`load_deception_catalog`, `get_deception`, `has_deception`,
`list_deception_ids`, `get_evidence`, `get_admissibility_profile`,
`validate_deception_ids`.

#### Invariants et règles respectées

- le catalogue \(\mathcal D\) est fermé : `validate_deception_ids` ne fait
  aucun mapping ATT&CK, elle vérifie seulement l'appartenance ;
- aucun format d'identifiant n'est imposé (pas de contrainte `DTxx`) ;
- aucune donnée manquante inventée (`catalog_version` sans défaut) ;
- `mechanisms_by_id` est en lecture seule après chargement.

#### Tests et validation

`tests/test_knowledge_deception.py` — chargement, validation de fiche,
identifiants, preuves documentaires, accès, catalogue fermé,
provenance/hash, généralité, non-interprétation SP1, immutabilité. 49 tests
au moment de la validation. CI verte.

#### Traçabilité

Commit de validation : `9569ee0`.

#### Limites actuelles

Ne construit pas le catalogue final lui-même (`deception_catalog.json`
n'existe pas encore) ; ne parse ni D3FEND, ni Engage, ni aucun document
brut (responsabilité de la couche offline séparée, voir étape 5) ; aucune
sémantique SP1 n'est attribuée à `admissibility_profile`.

#### Lien avec l'étape suivante

Le staging D3FEND (étape 5), après un enrichissement futur non encore
réalisé (Engage, littérature, transformation contrôlée), alimentera le
catalogue normalisé final que ce module charge.

---

### Étape 5 — Construction offline D3FEND (staging documentaire)

#### Objectif

Construire une chaîne **offline, déterministe et traçable** transformant
les données officielles MITRE D3FEND 1.5.0 en un staging documentaire
limité à la branche « Deceive », en amont de tout enrichissement futur.
Cette étape ne construit **pas** le catalogue final, n'implémente aucune
règle SP1, et n'utilise aucun LLM/RAG.

#### Position dans l'architecture

```text
MITRE D3FEND 1.5.0 (fichiers officiels, hors runtime SP1/SP2/SP3)
  → tools/deception_kb/d3fend_seed_builder.py
  → staging hiérarchique (branche Deceive) + mappings ATT&CK inférés
    + rapport d'extraction
```

Ce module vit dans `tools/`, explicitement hors du runtime chargé par
`src/knowledge_deception.py`.

#### Entrées

Fichiers officiels MITRE D3FEND 1.5.0, téléchargés depuis le domaine
officiel `d3fend.mitre.org` :

- `d3fend.json` — ontologie complète, format **JSON-LD**
  (`{"@context": {...}, "@graph": [...]}`) ;
- `d3fend-full-mappings.json` — relations inférées vers des techniques
  offensives, format **résultat de requête SPARQL**
  (`{"head": {...}, "results": {"bindings": [...]}}`).

#### Traitement réalisé

- Acquisition versionnée : téléchargement depuis les URLs officielles,
  calcul du SHA-256 sur les octets réellement téléchargés, enregistrement
  dans `data/deception/source_manifest.json`.
- Identification de la branche « Deceive » **sans liste codée en dur** :
  recherche des classes portant une propriété directe
  `d3f:enables -> d3f:Deceive` (recoupée avec le motif OWL
  `owl:Restriction` équivalent — les deux méthodes convergent
  exactement), puis parcours récursif de la hiérarchie `rdfs:subClassOf`
  (en excluant les nœuds blancs de restriction).
- Pour chaque concept de la branche : conservation de `parent_ids`/
  `child_ids`/`is_leaf` **sans décider** lesquels deviennent des mécanismes
  déployables \(d \in \mathcal D\) ; extraction de la définition, de
  l'article de connaissance (`kb_article`, texte markdown conservé
  verbatim), des synonymes, des artefacts imités/gérés (`d3f:spoofs`,
  `d3f:manages`), des références documentaires résolues, et d'une
  provenance fine par propriété (fichier source, SHA-256, entité,
  propriété, texte verbatim).
- Extraction séparée des mappings D3FEND↔ATT&CK inférés, restreinte au
  framework `"enterprise"` (le fichier officiel mélange aussi ATT&CK ICS et
  MITRE SPARTA, dont les identifiants ne suivent pas le format `Txxxx` —
  constat fait par inspection réelle du fichier) ; aucune confiance n'est
  inventée, seule la provenance (`origin: "d3fend_inferred"`) est conservée.
- Validation déterministe : pas de `source_technique_id` dupliqué, pas de
  parent/enfant orphelin, pas de mapping référençant une technique absente
  du seed, format `Txxxx`/`Txxxx.xxx` des identifiants ATT&CK conservés.

#### Sorties

- `data/deception/staging/d3fend_deception_seed_1.5.0.json` (11 concepts) ;
- `data/deception/staging/d3fend_attack_mapping_seed_1.5.0.json` (406
  relations inférées, périmètre ATT&CK Enterprise) ;
- `data/deception/staging/d3fend_seed_report_1.5.0.json` ;
- `data/deception/source_manifest.json`.

#### Fichiers concernés

- `tools/deception_kb/d3fend_seed_builder.py`
- `tools/deception_kb/README.md`
- `tests/test_d3fend_seed_builder.py`
- `data/deception/source_manifest.json`
- `data/deception/staging/*.json`
- `data/deception/raw/d3fend/1.5.0/` (fichiers officiels bruts, volumineux, non versionnés — voir `.gitignore`)

#### Fonctions principales

`build_d3fend_deception_seed`, `find_deceive_root_ids`,
`collect_branch_ids`, `build_concept_entry`,
`build_d3fend_attack_mapping_seed`, `validate_deception_seed`,
`validate_attack_mapping_seed`, `build_seed_report`,
`build_source_manifest`.

#### Invariants et règles respectées

- aucune liste `DECEPTION_IDS` codée en dur : la branche est découverte
  dynamiquement (vérifié par test dédié) ;
- aucune confiance numérique inventée pour un mapping inféré ;
- le staging n'est pas chargé par `src/knowledge_deception.py` ;
- les mappings extraits ne sont pas \(M_{i,d}\) ;
- 100 % déterministe, aucun appel LLM ;
- SHA-256 calculé sur les octets réellement téléchargés, jamais inventé.

#### Tests et validation

`tests/test_d3fend_seed_builder.py` — construction du seed, hiérarchie,
mappings ATT&CK, filtrage hors branche/hors périmètre, validation,
déterminisme, rapport/manifest, généralité (fixtures STIX synthétiques
uniquement, aucune dépendance réseau en CI). 22 tests au moment de la
validation. CI verte.

#### Traçabilité

- Source : MITRE D3FEND, version **1.5.0** (release identifiée comme
  courante sur `https://d3fend.mitre.org/resources/ontology/`).
- `d3fend.json` — `https://d3fend.mitre.org/ontologies/d3fend/1.5.0/d3fend.json`
  — SHA-256 `db82077fffb3897387fde29006b140b1401cb6df4b5729c0496c830e099114b9`.
- `d3fend-full-mappings.json` — `https://d3fend.mitre.org/ontologies/d3fend/1.5.0/d3fend-full-mappings.json`
  — SHA-256 `684f0a1872868a64b9046e66111e28cb9f0dc46c08e8f044b803fd8b493260ba`.
- Nombre de concepts extraits (11) vérifié identique à la page officielle
  `https://d3fend.mitre.org/tactic/d3f:Deceive/` (« The Deceive tactic
  contains 11 techniques »).
- Commit de validation : *à renseigner lors de la prochaine mise à jour
  naturelle de ce README* (hash communiqué dans le rapport de session
  ayant validé cette étape, pour éviter une boucle de commits
  d'auto-référencement).

#### Limites actuelles

Seul D3FEND est traité (MITRE Engage, littérature scientifique, agents
LLM/RAG explicitement non commencés). Aucune décision sur quels concepts
D3FEND deviennent des mécanismes déployables. Les mappings ATT&CK ne sont
pas encore validés comme \(M_{i,d}\). Ce staging n'est consommé par aucun
autre module à ce stade.

#### Lien avec l'étape suivante

Un futur enrichissement (MITRE Engage, littérature scientifique
sélectionnée, transformation contrôlée) consommera ce staging pour produire
`data/deception/deception_catalog.json`, chargé par `knowledge_deception.py`
(étape 4).

## OPEN_DECISION en cours

Ces points sont volontairement non résolus et ne doivent pas l'être
implicitement par une étape future sans décision explicite :

1. Quels niveaux de la hiérarchie D3FEND « Deceive » deviennent des
   mécanismes déployables \(d \in \mathcal D\) ?
2. Comment transformer les informations D3FEND/Engage/littérature vers les
   champs finaux `interaction_mechanism`, `realism_factors`,
   `progression_effects`, `admissibility_profile` ?
3. Quelle sémantique SP1 donner aux listes vides de
   `DeceptionAdmissibilityProfile` ?
4. Comment valider les mappings ATT&CK↔déception inférés par D3FEND avant
   de les utiliser comme \(M_{i,d}\) ?
