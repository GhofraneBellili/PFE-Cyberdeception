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

Depuis la branche `implementation/chapter4`, un dossier
`docs/chapter4/` complète ce README pour la rédaction du chapitre 4 du
mémoire : `docs/chapter4/IMPLEMENTATION_REPORT.md` (matière technique
détaillée par module, avec matrice de correspondance chapitre 3 →
implémentation), `docs/chapter4/TECHNOLOGIES.md` (technologies
réellement utilisées) et `docs/chapter4/SCREENSHOT_MANIFEST.md`
(captures prévues pour le chapitre 4, avec leur statut réel). Ce README
reste le journal cumulatif complet ; `docs/chapter4/` n'en est pas un
doublon mais une matière de rédaction ciblée.

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
- **Déduplication documentaire (durcissement)** : un « binding » SPARQL
  brut n'est pas une relation unique, qui n'est pas non plus un couple
  D3FEND↔ATT&CK unique — trois métriques explicites sont donc distinguées
  (`raw_attack_binding_count`, `unique_attack_relation_count`,
  `unique_d3fend_attack_pair_count`). La déduplication ne supprime que les
  bindings **strictement identiques** (même `d3fend_id`, `attack_id`,
  chemin d'artefacts `relation_path`, `framework` et `origin`) ; deux
  chemins d'artefacts différents entre un même couple D3FEND↔ATT&CK sont
  conservés comme preuves distinctes, jamais fusionnés.
- Validation déterministe : pas de `source_technique_id` dupliqué, pas de
  parent/enfant orphelin, pas de mapping référençant une technique absente
  du seed, format `Txxxx`/`Txxxx.xxx` des identifiants ATT&CK conservés, et
  désormais pas de relation strictement dupliquée.
- La CLI régénère également `data/deception/source_manifest.json` à partir
  de paramètres de provenance explicites (URLs officielles, date
  d'acquisition) et injecte exactement ses sources dans le rapport
  (`report["sources"] == manifest["sources"]`, jamais une liste vide).

#### Sorties

- `data/deception/staging/d3fend_deception_seed_1.5.0.json` (11 concepts) ;
- `data/deception/staging/d3fend_attack_mapping_seed_1.5.0.json` — sur
  D3FEND 1.5.0 (périmètre ATT&CK Enterprise) : **406 bindings SPARQL
  bruts** retenus après filtrage, **140 relations documentaires uniques**
  après déduplication exacte (c'est la taille de `mappings[]`), et **128
  couples D3FEND↔ATT&CK uniques** (12 couples sont donc justifiés par
  plusieurs chemins d'artefacts distincts, conservés séparément) ;
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
`build_d3fend_attack_mapping_seed` (dédupliqué), `validate_deception_seed`,
`validate_attack_mapping_seed` (rejette les doublons exacts),
`build_seed_report`, `build_manifest_entry`, `build_source_manifest`.

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
mappings ATT&CK, filtrage hors branche/hors périmètre, **déduplication
documentaire** (bindings strictement identiques, chemins d'artefacts
distincts conservés, rejet de doublon exact par validation), validation,
déterminisme, rapport/manifest **reproductible** (cohérence des hashes
manifest ↔ seed), CLI offline de bout en bout, généralité (fixtures STIX
synthétiques uniquement, aucune dépendance réseau en CI). 31 tests au
moment de la validation. CI verte.

#### Traçabilité

- Source : MITRE D3FEND, version **1.5.0** (release identifiée comme
  courante sur `https://d3fend.mitre.org/resources/ontology/`).
- `d3fend.json` — `https://d3fend.mitre.org/ontologies/d3fend/1.5.0/d3fend.json`
  — SHA-256 `db82077fffb3897387fde29006b140b1401cb6df4b5729c0496c830e099114b9`.
- `d3fend-full-mappings.json` — `https://d3fend.mitre.org/ontologies/d3fend/1.5.0/d3fend-full-mappings.json`
  — SHA-256 `684f0a1872868a64b9046e66111e28cb9f0dc46c08e8f044b803fd8b493260ba`.
- Nombre de concepts extraits (11) vérifié identique à la page officielle
  `https://d3fend.mitre.org/tactic/d3f:Deceive/` (« The Deceive tactic
  contains 11 techniques ») — inchangé par ce durcissement (fichier de seed
  regénéré strictement identique, octet pour octet).
- Commit de validation initiale (extraction du staging) :
  `94ff9c72fbe5cab9f26d470b8e25da13b2e836dd`.
- Commit de durcissement (déduplication documentaire + reproductibilité de
  la CLI) : `3205fa82ff09fb99013af0147a562308ae4eb339`.

#### Limites actuelles

D3FEND et MITRE Engage (étape 6) sont désormais traités ; la littérature
scientifique et les agents LLM/RAG restent explicitement non commencés.
Aucune décision sur quels concepts D3FEND (ni quelles activités/approches
Engage) deviennent des mécanismes déployables. Les mappings ATT&CK ne sont
pas encore validés comme \(M_{i,d}\). Ce staging n'est consommé par aucun
autre module à ce stade.

#### Lien avec l'étape suivante

Un futur enrichissement (littérature scientifique sélectionnée,
normalisation D3FEND↔Engage, transformation contrôlée) consommera ces
staging pour produire `data/deception/deception_catalog.json`, chargé par
`knowledge_deception.py` (étape 4).

---

### Étape 6 — Construction offline MITRE Engage (staging documentaire)

#### Objectif

Construire une chaîne **offline, déterministe et traçable** transformant
les données officielles MITRE Engage v1.0 en un staging documentaire —
**deuxième source structurée** de la future KB cyberdéception, en
complément de D3FEND (étape 5). Cette étape ne construit **pas** le
catalogue final, n'implémente aucune règle SP1, et n'utilise aucun LLM/RAG.

#### Position dans l'architecture

```text
MITRE Engage v1.0 (fichiers officiels, hors runtime SP1/SP2/SP3)
  → tools/deception_kb/engage_seed_builder.py
  → staging documentaire (activités + approches) + mappings ATT&CK
    + rapport d'extraction
```

Ce module vit dans `tools/`, explicitement hors du runtime chargé par
`src/knowledge_deception.py`. Il ne fusionne à aucun moment ses résultats
avec le staging D3FEND (OPEN_DECISION 2).

#### Entrées

Sept fichiers officiels MITRE Engage v1.0, téléchargés depuis le dépôt
officiel `https://github.com/mitre/engage`, **pinné** au commit
`5ae09f6f7511ebb6d35d70a9107490900380d3d8` (jamais `main`/`latest`) :
`activities.json`, `activity_details.json`, `approaches.json`,
`approach_details.json`, `approach_activity_mappings.json`,
`attack_mapping.json`, `references.json`. `framework_version = "1.0"`
(version déclarée du jeu de données) et `source_revision` (le commit exact)
sont conservés comme deux notions distinctes, jamais conflées.

#### Traitement réalisé

- Acquisition versionnée : téléchargement depuis les URLs officielles
  dérivées mécaniquement du dépôt pinné, calcul du SHA-256 sur les octets
  réellement téléchargés, enregistrement dans
  `data/deception/source_manifest.json` (étendu, pas remplacé — les
  entrées D3FEND existantes sont préservées à l'identique).
- Conservation de la sémantique native d'Engage : les activités
  (EACxxxx/SACxxxx) et approches (EAPxxxx/SAPxxxx) restent des entités
  documentaires sources, jamais présentées comme des mécanismes finaux
  `d \in \mathcal D`. La famille (`activity_family`/`approach_family`) est
  dérivée du préfixe d'identifiant réellement observé (jamais d'une liste
  codée en dur) ; un préfixe non reconnu lève une erreur explicite.
  Interprétation retenue, conforme à `activity_details[id]["type"]`/
  `approach_details[id]["type"]` (`"Engagement"` ou `"Strategic"`, jamais
  `"Support"`) : EAC = Engagement Activity, SAC = Strategic Activity,
  EAP = Engagement Approach, SAP = Strategic Approach.
- Jointure activité ↔ approche à partir de la table de correspondance
  canonique `approach_activity_mappings.json` (pas des copies dénormalisées
  embarquées dans `activity_details.json`/`approach_details.json`).
- Distinction explicite, à l'intérieur d'une activité, entre les libellés
  de tactique kebab-case nichés par technique ATT&CK
  (`attack_tactic_labels`, ex. `"discovery"`) et la liste d'objets
  `{id: TAxxxx, name}` au niveau racine de l'activité (`attack_tactics`) —
  deux champs distincts jamais fusionnés, malgré un nom de clé source
  identique aux deux niveaux.
- Traitement du champ `activity_id` de `references.json`, constaté par
  inspection comme pouvant désigner soit une activité, soit une approche
  (4 références sur 67 pointent vers `SAP0001`/`SAP0002`) — aucune
  hypothèse a priori, résolution par correspondance directe des deux cas.
- Extraction séparée des mappings Engage↔ATT&CK (`attack_mapping.json`),
  filtrés au format ATT&CK `Txxxx`/`Txxxx.xxx` (réutilisation de
  `ATTACK_TECHNIQUE_ID_PATTERN` de `src/schemas.py`, sans duplication du
  motif) ; **aucune de ces relations n'est `M_{i,d}`** — une relation
  `(attack_id, EAV, EAC)` documente une vulnérabilité adverse potentielle,
  pas une décision d'admissibilité SP1.
- Déduplication documentaire : trois métriques distinctes (bindings bruts,
  relations uniques après déduplication exacte, couples `(attack_id,
  engage_activity_id)` uniques), clé de déduplication `(attack_id,
  adversary_vulnerability_id, engage_activity_id)` confirmée suffisante par
  inspection réelle du jeu de données (le seul doublon exact constaté
  partage aussi tout le contenu de la relation).
- Validation déterministe : pas d'identifiant d'activité/approche dupliqué,
  pas de référence croisée orpheline (activité ↔ approche, mapping ↔
  activité), format ATT&CK conservé, provenance obligatoire sur chaque
  entité, rejet de toute relation strictement dupliquée.
- La CLI régénère `data/deception/staging/engage_activity_seed_1.0.json`,
  `data/deception/staging/engage_attack_mapping_seed_1.0.json`,
  `data/deception/staging/engage_seed_report_1.0.json`, et étend
  `data/deception/source_manifest.json` par fusion idempotente (remplace
  uniquement les entrées `engage-*`, préserve les entrées `d3fend-*`).

#### Sorties

- `data/deception/staging/engage_activity_seed_1.0.json` — **31 activités** :
  **23 Engagement Activities (EAC)** et **8 Strategic Activities (SAC)**
  (jamais « Support Activities » — non supporté par les données officielles,
  `activity_details[id]["type"] == "Strategic"`), et **9 approches**
  (**Engagement Approaches, EAP** / **Strategic Approaches, SAP**) ;
- `data/deception/staging/engage_attack_mapping_seed_1.0.json` — **793
  bindings bruts**, **792 relations documentaires uniques** après
  déduplication exacte (1 doublon exact retiré), **596 couples
  `(attack_id, engage_activity_id)` uniques** (145 de ces couples sont
  justifiés par plusieurs vulnérabilités adverses (EAV) distinctes,
  totalisant 196 relations supplémentaires, toutes conservées séparément),
  **175 identifiants ATT&CK distincts**, **29 vulnérabilités adverses
  (EAV) distinctes** ;
- `data/deception/staging/engage_seed_report_1.0.json` ;
- `data/deception/source_manifest.json` (étendu : 9 sources au total, 2
  D3FEND + 7 Engage).

#### Fichiers concernés

- `tools/deception_kb/engage_seed_builder.py`
- `tools/deception_kb/README.md`
- `tests/test_engage_seed_builder.py`
- `data/deception/source_manifest.json`
- `data/deception/staging/engage_*.json`
- `data/deception/raw/engage/1.0/` (fichiers officiels bruts, non versionnés — voir `.gitignore`)

#### Fonctions principales

`build_engage_activity_seed`, `build_engage_attack_mapping_seed`
(dédupliqué), `validate_engage_activity_seed`,
`validate_engage_attack_mapping_seed` (rejette les doublons exacts),
`build_engage_seed_report`, `merge_source_manifest` (fusion idempotente,
réutilise `build_manifest_entry`/`build_source_manifest` de
`d3fend_seed_builder.py` sans duplication).

#### Invariants et règles respectées

- aucune convention de préfixe codée en dur sans être démontrée par
  inspection réelle des deux familles d'entités (activités et approches) ;
- une activité/approche Engage n'est jamais assimilée à un mécanisme final
  `d \in \mathcal D` ;
- un mapping Engage↔ATT&CK n'est jamais assimilé à \(M_{i,d}\) ;
- le staging n'est pas chargé par `src/knowledge_deception.py` ;
- 100 % déterministe, aucun appel LLM, aucun appel réseau pendant les tests ;
- SHA-256 calculé sur les octets réellement téléchargés, jamais inventé ;
- le staging D3FEND existant n'est ni modifié ni fusionné avec le staging
  Engage.

#### Tests et validation

`tests/test_engage_seed_builder.py` — construction du seed
activités/approches, conservation verbatim des champs, jointure via la
table canonique, activité à approches multiples, distinction EAC/SAC et
EAP/SAP, rejets (référence croisée orpheline, identifiant ATT&CK mal
formé, préfixe non reconnu), mapping Engage↔ATT&CK valide, EAV conservée,
déduplication exacte, cas `attack_id`+activité identiques mais EAV
différente (comportement explicite de la clé), ordre déterministe,
provenance SHA-256, `source_revision` conservé, CLI de bout en bout
(staging + rapport + fusion de manifest), même entrée → même sortie,
absence de toute logique spécifique au cas de référence PFE (T1003/T1078/
etc., vérifiée par inspection statique du module), et régression
terminologique SAC/SAP (`activity_family`/`approach_family` cohérents avec
`type == "Strategic"`). **35 tests** dans ce fichier, **230 tests** au
total au moment de la validation. CI verte.

#### Traçabilité

- Source : MITRE Engage, dépôt officiel `https://github.com/mitre/engage`,
  version déclarée **1.0**, commit pinné
  `5ae09f6f7511ebb6d35d70a9107490900380d3d8`.
- `activities.json` — SHA-256 `19c8788bdd8615a0d5dddf8046c902c00b453c1b0247e35c9ca610a99ad98e07`.
- `activity_details.json` — SHA-256 `4e47d11af0428ad1d3b1782c367a3e4a0abf850e6809fd838e350d31886a1abf`.
- `approaches.json` — SHA-256 `da2e09ad8c93f4aa463afaa9c5b1ef27eae91b444b580c4af432ae4ba05dadb7`.
- `approach_details.json` — SHA-256 `cff1b915f0fbba99373bb2322a1b1c4abccb300bada6cd8eefb482caec97d5db`.
- `approach_activity_mappings.json` — SHA-256 `604f9e9e38431ec83a0fdcaa0c7d2f88c4b5d20a4f2ff4c94e497a78c6ccbe06`.
- `attack_mapping.json` — SHA-256 `8004901aa219813a4b7105665aa5e9cd2128beeccc818b2c3e42324f1ad609bf`.
- `references.json` — SHA-256 `6598c1c3cad875b33586b88732ac1c27faa9d376529db8730e56889ccd1e316a`.
- Toutes les URLs officielles sont dérivées de
  `https://raw.githubusercontent.com/mitre/engage/5ae09f6f7511ebb6d35d70a9107490900380d3d8/Data/json/<fichier>`.
- Le champ optionnel `git_blob_sha` de `build_manifest_entry` n'est pas
  peuplé automatiquement par la CLI (aucun argument dédié demandé) —
  documenté dans `tools/deception_kb/README.md`.
- Commit de validation initiale (extraction du staging) :
  `233351cb5bc168e571371babca9bfbf7c3c6683e`.
- Commit de correctif (alignement de la nomenclature SAC/SAP sur
  « Strategic », conformément à `activity_details[id]["type"]`/
  `approach_details[id]["type"]`) :
  `d1c00a041017b73be5b1f6a9402e469a8108e9ef`.

#### Limites actuelles

Les activités et approches Engage sont conservées comme entités
documentaires sources, sans normalisation vers le catalogue final ni
rapprochement avec D3FEND. Les mappings Engage↔ATT&CK ne sont pas encore
validés comme \(M_{i,d}\). Ce staging n'est consommé par aucun autre module
à ce stade.

#### Lien avec l'étape suivante

Un futur enrichissement (littérature scientifique sélectionnée,
normalisation contrôlée D3FEND↔Engage, transformation vers les champs
finaux de `DeceptionMechanism`) consommera conjointement les deux staging
(D3FEND et Engage) pour produire `data/deception/deception_catalog.json`,
chargé par `knowledge_deception.py` (étape 4).

---

### Étape 7 — Construction du corpus scientifique de cyberdéception

#### Objectif

Construire un **corpus scientifique versionné et traçable**, complémentaire
à D3FEND et MITRE Engage, destiné à documenter — à terme — des propriétés
difficiles à obtenir des seules bases D3FEND/Engage (réalisme, interaction
attaquant, déploiement, ressources, maintenance, évaluation). Cette étape
constitue un STAGING documentaire ; elle ne construit ni le catalogue
final, ni aucune propriété de `DeceptionMechanism`. Durcie une première
fois (phase 4B.3-H) : provenance bibliographique renforcée, distinction
DOI de publication / DOI de dépôt, dates de publication explicites, statut
d'évaluation par les pairs explicite, vérification page par page des
passages, et complément empirique ciblé. Durcie une seconde fois (phase
4B.3-H2, schéma de staging 1.2) : invariant strict de pagination (une
extraction sans séparateur de page n'est plus jamais assimilée à une page
1 vérifiée), provenance structurée pour la date d'Early Access de
Beltrán-López et al., et distinction documentaire enticingness/realism
pour Honeyquest.

#### Position dans l'architecture

```text
littérature scientifique (DOI vérifiés Crossref/DataCite/OpenAlex, dépôts
institutionnels, DBLP)
  → data/deception/literature/literature_sources.json (registre curé, schéma 1.1)
  → tools/deception_kb/literature_seed_builder.py
  → staging documentaire (documents + passages courts vérifiés page par
    page, schéma 1.2) + rapport
```

Ce module vit dans `tools/`, hors du runtime chargé par
`src/knowledge_deception.py`. Il ne fusionne à aucun moment ses résultats
avec les staging D3FEND ou Engage (OPEN_DECISION 2).

#### Entrées

- registre bibliographique curé et vérifié individuellement (chaque
  `publication_doi` confirmé via l'API Crossref, chaque `repository_doi`
  via l'API DataCite, dates croisées via DBLP lorsque nécessaire, chaque
  URL d'accès ouvert vérifiée par requête HTTP réelle) :
  `data/deception/literature/literature_sources.json` ;
- fichiers PDF déjà acquis localement pour les sources en accès ouvert
  (`data/deception/raw/literature/`, non versionnés) et leur extraction
  texte déjà produite hors ligne par `pdftotext`, séparateurs de page
  (`\f`) conservés (`.txt` à côté de chaque `.pdf`) ;
- passages candidats courts avec page déclarée : `data/deception/literature/evidence_candidates.json`.

#### Méthode de recherche documentaire

Recherche manuelle assistée d'axes conceptuels généraux (cyber deception,
honeypot, honeynet, honeytoken, decoy documents, deception placement,
attacker engagement, deception optimization, ...) — jamais restreinte aux
techniques ATT&CK ou actifs du scénario expérimental du PFE (T1003, T1078,
`DC`/`WS`/`DB` explicitement exclus des requêtes). Chaque source candidate
est vérifiée individuellement via l'API Crossref/DataCite (titre, auteurs,
dates, venue) avant inclusion. Complément ciblé lors du durcissement sur
la couverture empirique (réalisme/enticingness, comportement de
l'attaquant, efficacité observée). Méthode complète, 21 requêtes
réellement exécutées et candidats examinés/rejetés documentés dans
`data/deception/literature/search_protocol.md`.

#### Critères d'inclusion/exclusion

**Inclusion** : pertinence directe pour la cyberdéception, nature
académique (revue, conférence évaluée par les pairs, ou preprint retenu
seulement si l'information est absente ailleurs), métadonnées vérifiables
via une source stable, couverture thématique non redondante (aucun ajout
pour atteindre un nombre arbitraire).

**Exclusion** : blogs marketing/commerciaux, documentation fournisseur,
sources non vérifiées indépendamment, contournement de paywall, doublons
(même DOI, ou même travail décliné preprint + version publiée — traité
comme une seule entité scientifique, jamais fusionné par similarité de
titre seule), publications redondantes avec une source déjà retenue
couvrant le même jeu de données empirique (ex. deux candidats liés à
l'étude « Tularosa » explicitement écartés, voir Traçabilité).

#### Traitement réalisé

- Validation du registre durci : aucun champ obligatoire manquant, aucun
  `source_id`/`publication_doi`/`repository_doi` dupliqué (chacun dans sa
  propre catégorie), `publication_doi` jamais égal à `repository_doi`,
  cohérence stricte `source_id` ↔ `publication_doi`
  (`source_id = "doi_" + publication_doi.lower().replace("/", "_")`,
  vérifiée automatiquement), `bibliographic_year` obligatoire,
  `peer_review_status`/`peer_review_basis` obligatoires et jamais déduits
  de `publication_type`, `metadata_provenance` non vide et structurée,
  `access_status` cohérent avec la présence ou l'absence d'un fichier
  local.
- Construction du staging document : pour chaque source en accès ouvert,
  vérification que le SHA-256 du fichier local correspond exactement à
  celui déclaré dans le registre, que son extraction texte (`.txt`)
  existe réellement, et découpage de ce texte par page (séparateurs `\f`
  natifs de `pdftotext`) — sinon rejet explicite, jamais une substitution
  silencieuse. **Invariant durci (4B.3-H2)** : une extraction sans aucun
  séparateur `\f` obtient `pagination_available: false` et `page_count:
  null` — elle n'est plus jamais assimilée à un document d'une seule page
  vérifiée.
- Construction du staging de passages courts (`≤ 500` caractères) :
  **chaque passage est revérifié par le programme**, pas seulement par la
  personne qui l'a proposé, comme sous-chaîne littérale (après
  normalisation des espaces/retours à la ligne) **sur la page précisément
  déclarée** — un passage présent ailleurs dans le document mais pas sur
  cette page est explicitement rejeté (pas seulement un passage
  introuvable partout). Si `pagination_available` est faux pour la
  source, **tout** passage candidat est rejeté d'emblée, y compris pour
  une page 1 déclarée. Tout passage conservé porte `page_verified: true`,
  et l'invariant `page_verified ⇒ pagination_available` est revérifié
  explicitement à la validation du staging evidence.
- Calcul d'un rapport de couverture thématique sur une taxonomie
  documentaire (jamais les métriques SP2) ; les thèmes non couverts sont
  rapportés explicitement (`coverage_gaps`), jamais comblés par une source
  inventée ; compteurs peer review et access_status calculés depuis des
  champs explicites, jamais déduits implicitement.

#### Sorties

- `data/deception/staging/literature_document_seed_1.2.json` — **14
  sources** (13 en accès ouvert, 1 en métadonnées seules), dont
  **13 documents avec pagination réellement vérifiée** (`pagination_available: true`),
  **0 sans pagination vérifiable** ;
- `data/deception/staging/literature_evidence_seed_1.2.json` — **18
  passages courts**, tous `page_verified: true`, répartis sur 13 sources ;
- `data/deception/staging/literature_seed_report_1.2.json` — 13 sources
  `peer_reviewed`, 1 `not_peer_reviewed` (Fraunholz et al. 2018, retenu
  pour sa couverture unique d'aspects légaux/éthiques/psychologiques),
  0 `unknown`, 11 sources avec `publication_doi`, 1 avec `repository_doi`
  uniquement (Fraunholz et al.), 13 avec SHA-256 local, période
  bibliographique couverte 2003–2026, 3 lacunes de couverture identifiées
  (`decoy_asset`, `decoy_network`, `decoy_service`). Les fichiers
  `literature_*_1.0.json` et `literature_*_1.1.json` (schémas antérieurs)
  ont été retirés du dépôt au fil des deux durcissements successifs.

#### Fichiers concernés

- `tools/deception_kb/literature_seed_builder.py`
- `tools/deception_kb/README.md`
- `tests/test_literature_seed_builder.py`
- `data/deception/literature/literature_sources.json`
- `data/deception/literature/search_protocol.md`
- `data/deception/literature/evidence_candidates.json`
- `data/deception/staging/literature_*.json`
- `data/deception/raw/literature/` (PDF et extractions texte non versionnés — voir `.gitignore`)

#### Fonctions principales

`compute_doi_based_source_id`, `is_valid_fallback_source_id`,
`extract_page_structure` (distingue `pagination_available`),
`validate_literature_sources_registry`, `build_literature_document_seed`,
`validate_literature_document_seed`, `build_literature_evidence_seed`
(vérification verbatim page par page contre le texte extrait, rejet
d'emblée si pagination non observable), `validate_literature_evidence_seed`,
`build_literature_seed_report`.

#### Invariants

- un passage scientifique n'est jamais assimilé à une propriété finale de
  `DeceptionMechanism` ;
- aucun `deception_catalog.json` n'est créé ni modifié ;
- aucune source, aucun DOI, aucune métadonnée, aucune date, aucune page,
  aucun passage n'est inventé — toute donnée non vérifiable reste
  `null`/absente ;
- un DOI de dépôt/preprint (`repository_doi`) n'est jamais assimilé à un
  DOI de publication finale (`publication_doi`) ;
- un `peer_review_status` n'est jamais déduit implicitement du type de
  publication ;
- une extraction sans séparateur de page observable
  (`pagination_available: false`) ne peut produire aucun passage
  `page_verified: true`, y compris pour une page 1 déclarée ;
- un passage n'est conservé que si sa page déclarée est réellement
  vérifiée (`page_verified: true`), jamais sur la seule confiance de la
  personne qui l'a proposé, et cet invariant implique structurellement
  `pagination_available: true` sur sa source (vérifié à la construction
  et à la validation) ;
- aucun appel LLM, aucun RAG, aucun embedding, aucune base vectorielle ;
- 100 % déterministe et hors ligne (le builder ne télécharge rien) ;
- aucun texte intégral protégé par le droit d'auteur n'est versionné dans
  Git (seuls les passages courts vérifiés, ≤ 500 caractères, le sont).

#### Tests et validation

`tests/test_literature_seed_builder.py` — identifiants stables
déterministes, découpage par page (séparateurs `\f` présents →
`pagination_available: true` ; absents → `pagination_available: false`,
**jamais** assimilé à une page 1 vérifiée), validation du registre durci
(`publication_doi`/`repository_doi` dupliqués rejetés séparément,
`publication_doi == repository_doi` rejeté, année bibliographique
obligatoire, `peer_review_status` invalide rejeté, provenance
vide/incomplète rejetée, thème inconnu, `access_status` incohérent avec
la présence d'un fichier local), construction et validation du staging
document (SHA-256 non concordant rejeté, extraction texte absente
rejetée, champs bibliographiques propagés), construction et validation du
staging de passages **avec vérification de page stricte** (passage
présent sur la bonne page accepté, passage présent ailleurs mais pas sur
la page déclarée rejeté, page inexistante rejetée, page = 0 rejetée,
**page 1 ET page 2 rejetées lorsque la pagination n'est pas observable**,
même passage répété sur deux pages correctement distingué par page,
invariant `page_verified ⇒ pagination_available` revérifié même sur une
evidence falsifiée a posteriori), déterminisme (même entrée → même
sortie, ordre stable), rapport de couverture durci (compteurs peer review
et access_status indépendants et explicites, DOI de publication compté
séparément du DOI de dépôt, nouveaux compteurs
`documents_with_verified_pagination_count`/`documents_without_verified_pagination_count`),
CLI de bout en bout, absence de toute logique spécifique au cas de
référence PFE et absence de dépendance LLM/RAG/réseau (vérifiées par
inspection statique du module). **77 tests** dans ce fichier (4 de plus
que la version précédente), **307 tests** au total au moment de la
validation. CI verte.

#### Traçabilité

Voir `data/deception/literature/literature_sources.json` (métadonnées et
SHA-256 complets par source, `metadata_provenance` par source) et
`data/deception/literature/search_protocol.md` (21 requêtes exécutées,
méthode de vérification Crossref/DataCite/DBLP/OpenAlex, cas détaillé
Beltrán-López (Early Access 2025 confirmée par OpenAlex, IEEE Xplore
inaccessible depuis cet environnement, vs. volume final 2026), analyse
textuelle Honeyquest (enticingness ≠ realism), gestion des versions
arXiv/éditeur, journal des corrections de métadonnées des deux
durcissements, candidats examinés et rejetés avec justification). 14
sources retenues : les 12 du corpus initial (Han, Kheir & Balzarotti 2018 ;
Pawlick, Colbert & Zhu 2019 ; Almeshekah & Spafford 2014 ; Fraunholz et
al. 2018, preprint arXiv:1804.06196 ; Bowen, Hershkop, Keromytis & Stolfo
2009 ; Zhang & Thing 2021 ; Provos 2004 ; Spitzner 2003 ; Yuill, Zappe,
Denning & Feer 2004 ; Milani et al. 2020 ; Beltrán-López, Gil Pérez &
Nespoli, `bibliographic_year` 2026 ; Urias et al. 2017, métadonnées
seules) plus 2 nouvelles sources empiriques ajoutées lors du premier
durcissement : Kahlhofer, Achleitner, Rass & Mayrhofer (« Honeyquest »,
RAID 2024, DOI 10.1145/3678890.3678897, thème `realism` retiré lors du
second durcissement) et Ferguson-Walter, Major, Johnson & Muhleman
(« Examining the Efficacy of Decoy-based and Psychological Cyber
Deception », USENIX Security 2021, sans DOI). Aucune nouvelle publication
n'a été ajoutée lors du second durcissement.

- Commit de construction initiale du corpus :
  `8d5b7a9efd761697ced7fb557e25851eace08b27`.
- Commit de premier durcissement (schéma bibliographique 1.1, vérification
  page par page, complément empirique) :
  `d9ee1df3f887103391aa0eeba17df8f3367694aa`.
- Commit de second durcissement (invariant strict de pagination, schéma de
  staging 1.2, provenance OpenAlex, distinction enticingness/realism) :
  *à renseigner lors de la prochaine mise à jour naturelle de ce README*,
  pour éviter une boucle de commits d'auto-référencement.

#### Couverture

Thèmes couverts (source_count > 0) : `deception_mechanism`, `honeypot`,
`honeynet`, `honeytoken`, `decoy_credential`, `decoy_document`, `realism`,
`attacker_interaction`, `engagement`, `redirection`, `delay`,
`containment`, `detection`, `intelligence_collection`, `deployment`,
`resource_requirements`, `maintenance`, `evaluation`. Lacunes identifiées
et non comblées, malgré une recherche complémentaire dédiée lors du
durcissement : `decoy_asset`, `decoy_network`, `decoy_service` — aucune
publication scientifique solide couvrant spécifiquement ces artefacts
n'a été identifiée.

#### Limites actuelles

Corpus représentatif, pas exhaustif (recherche via moteur généraliste,
pas d'interrogation systématique de chaque base bibliographique
spécialisée via ses API propres). Un seul preprint non évalué par les
pairs est inclus, explicitement signalé comme tel
(`peer_review_status = "not_peer_reviewed"`). Une source (Urias et al.
2017) reste en métadonnées seules, aucun mirroir en accès ouvert n'ayant
pu être vérifié depuis cet environnement. Pour deux sources anciennes
(Spitzner 2003, Yuill et al. 2004), Crossref ne fournit aucune date de
publication fiable ; l'année a été reconstruite à partir du
`container-title` et de la venue officielle, documenté explicitement.
IEEE Xplore n'a pas pu être consulté directement depuis cet environnement
lors de la vérification de l'Early Access de Beltrán-López et al. ; la
corroboration retenue (OpenAlex) est une base bibliographique tierce, pas
la source primaire de l'éditeur. Un thème documentaire `enticingness`
distinct de `realism` n'a volontairement pas été créé (OPEN_DECISION 7).
Aucun passage n'est encore relié à un mécanisme D3FEND/Engage ni à une
propriété finale de `DeceptionMechanism`.

#### Lien avec l'étape suivante

Une future étape de normalisation contrôlée (hors périmètre de cette
phase) devra décider comment les preuves D3FEND, Engage et littérature
convergent vers le catalogue fermé `data/deception/deception_catalog.json`
(OPEN_DECISION 1, 2, 3, 6 ci-dessous).

---

### Étape 8 — Implémentation de SP1 (`src/admissibility.py`)

*(branche `implementation/chapter4`)*

#### Objectif

Construire l'espace admissible `C_i_h` pour chaque occurrence non
terminale d'une instance de système d'information, à partir d'un mapping
M_{i,d} déjà fourni et des règles déterministes `Allowed`,
`RequirementsSatisfied`, `Relevant` (notation verrouillée du chapitre 4 :
`Autorise`, `PrerequisSatisfaits`, `Pertinent`).

#### Traitement réalisé

Pour chaque occurrence non Terminal : diagnostic complet par couple
(mécanisme du catalogue × emplacement du SI), avec court-circuit explicite
si le mécanisme n'appartient pas à `D_i` (`mapping="fail"` →
`not_evaluated` pour les trois critères). `Relevant` est simplifié à une
relation topologique directe (même actif, ou arête `SITopologyEdge` à un
saut) — limite documentée, pas une omission silencieuse. Politique
prudente pour l'OPEN_DECISION 4 (listes vides de
`DeceptionAdmissibilityProfile`) : un critère dont les listes pertinentes
sont toutes vides est `undetermined`, jamais admis par défaut.

#### Sorties

`docs/chapter4/outputs/sp1_candidates.json` / `sp1_example.txt`, générés
par `python -m examples.sp1_example` sur une petite instance explicite :
4 candidats bruts, 1 admissible.

#### Fichiers concernés

`src/admissibility.py`, `tests/test_admissibility.py`,
`examples/sp1_example.py`.

#### Tests et validation

`tests/test_admissibility.py` — 21 tests (pass/fail/undetermined pour
chacun des trois critères, occurrence Terminal sans candidat, mapping
absent, déterminisme, cohérence des compteurs). **368 tests** au total au
moment de la validation. Détail complet (correspondance chapitre 3,
limites, invariant LLM hors chemin d'exécution) :
`docs/chapter4/IMPLEMENTATION_REPORT.md`, section 4.

#### Limites actuelles

`Pertinent` ne couvre pas encore les chemins complets vers les nœuds
terminaux ni les voisins du graphe d'attaque (relation topologique directe
uniquement). M_{i,d} reste un paramètre d'entrée, pas construit par SP1
lui-même (OPEN_DECISION 5).

#### Lien avec l'étape suivante

SP3 (moteur de risque déterministe, `src/risk_engine.py`), avec pour
critère de correction le test de régression `test_reference_example` sur
l'exemple numérique de référence du chapitre 3.

---

### Étape 9 — Implémentation de SP3 (`src/risk_engine.py`)

*(branche `implementation/chapter4`)*

#### Objectif

Propager `Gamma → P^e → A → P → I → R` sur le graphe d'attaque
(convergence noisy-OR, divergence par probabilité de branche `pi`), et
faire passer le test de régression `test_reference_example` — ancre de
validation du projet : aucun module de risque ou d'optimisation n'est
considéré correct tant que ce test ne passe pas.

#### Traitement réalisé

Tri topologique du graphe (NetworkX) ; `Gamma = 1 - DE` par occurrence ;
noeuds d'entrée : `A=1` ; sinon noisy-OR sur les probabilités transmises
de chaque parent (`P^e = P_parent × Gamma_parent × pi`, `pi` uniquement en
divergence — valeur explicite de l'arête ou `1/|enfants|` par défaut) ;
`P = A×q` ; `R = P×I`. Aucune valeur manquante n'est devinée (q et I
obligatoires pour chaque occurrence, erreur explicite sinon).

#### Ancre de validation — résultat réel

Scénario T1566/T1190 → T1003 → T1078 → (T1059/T1057/T1082, divergence
`pi=1/3`) → T1041, déception `DE=0.429` sur T1003 uniquement :

| Grandeur | Calculé | Cible |
|---|---|---|
| `Gamma_1003` | 0.571 | 0.571 |
| `R_avec_deception` | 0.0208 | 0.0208 |
| `R_sans_deception` | 0.0365 | 0.0365 |
| Réduction relative | 42.9 % | ≈ 42.9 % |

#### Sorties

`docs/chapter4/outputs/risk_example.csv` / `risk_example.txt`, générés
par `python -m examples.sp3_example`.

#### Fichiers concernés

`src/risk_engine.py`, `tests/test_risk_engine.py`,
`examples/sp3_example.py`.

#### Tests et validation

`tests/test_risk_engine.py` — 23 tests (formules élémentaires,
propagation linéaire, convergence, divergence par défaut et explicite,
valeurs manquantes rejetées, bornes `[0,1]`, **`test_reference_example`**,
et un test d'invariant vérifiant par analyse `ast` que `risk_engine.py`
n'importe jamais `annotator_llm.py`/`rag_indexer.py`/`rag_retriever.py`).
**391 tests** au total au moment de la validation. Détail complet :
`docs/chapter4/IMPLEMENTATION_REPORT.md`, section 9.

#### Limites actuelles

`DE` par occurrence est fourni directement par l'appelant (pas encore lu
depuis une table d'annotations figée réelle, sections SP2/freeze non
implémentées). Intégration avec `cost_engine.py`/`optimizer.py` à venir.

#### Lien avec l'étape suivante

`cost_engine.py` (`Cout(d;H)`), puis `optimizer.py` (unicité, budget,
dominance, front de Pareto, `Y*`).

---

### Étape 10 — Implémentation du coût (`src/cost_engine.py`)

*(branche `implementation/chapter4`)*

#### Objectif

Calculer `Cost(d;H) = C_deploy(d) + C_resource(d;H) + C_maintenance(d;H)`
(§15), en amont de la contrainte budgétaire de l'optimiseur.

#### Traitement réalisé

Trois fonctions déterministes pour les trois composantes (`C_deploy`,
`C_resource`, `C_maintenance`), sommées par `compute_mechanism_cost`.
Toute valeur négative (paramètre ou horizon `H`) est rejetée
explicitement. Hypothèse gelée du §15 respectée par construction : aucune
fonction ne prend d'emplacement `l` en paramètre, donc `Cost(d,l;H) =
Cost(d;H)` structurellement.

#### Sorties

`docs/chapter4/outputs/cost_example.txt`, généré par
`python -m examples.cost_example` (deux mécanismes, `H=720`) :

```
Mecanisme   C_deploy    C_resource  C_maintenance   Cost
D3-DUC      270.00      21.60       3747.60         4039.20
D3-DF       130.00      22.68       1879.20         2031.88
```

#### Fichiers concernés

`src/cost_engine.py`, `tests/test_cost_engine.py`,
`examples/cost_example.py`.

#### Tests et validation

`tests/test_cost_engine.py` — 13 tests (formules des trois composantes,
rejet des valeurs négatives, somme totale, indépendance vis-à-vis de
l'emplacement par construction, déterminisme). **404 tests** au total au
moment de la validation. Détail complet :
`docs/chapter4/IMPLEMENTATION_REPORT.md`, section 8.

#### Limites actuelles

`DeceptionMechanism.resource_requirements` reste du texte libre non
parsé (ex. "2 vCPU") : ce module attend des paramètres numériques déjà
explicites, fournis par l'appelant — la conversion texte→numérique reste
une OPEN_DECISION non résolue.

#### Lien avec l'étape suivante

`optimizer.py` (unicité, budget, dominance, front de Pareto, `Y*`).

---

### Étape 11 — Implémentation de l'optimiseur (`src/optimizer.py`)

*(branche `implementation/chapter4`)*

#### Objectif

Résoudre `(P)` : minimisation multiobjectif des risques terminaux sous
contrainte d'unicité locale (§16.1) et de budget (§16.2), produire le
front de Pareto et un `y*` illustratif.

#### Traitement réalisé

Construction des candidats à partir de `C_i_h` (SP1) enrichis de `DE` et
`Cost` déjà calculés ; énumération exhaustive des configurations
(« aucune déception » + chaque candidat par occurrence, unicité garantie
par construction, garde-fou explicite contre l'explosion combinatoire —
pas une réduction arbitraire, §24) ; filtrage budgétaire ; évaluation SP3
de chaque configuration faisable (risques terminaux uniquement) ; front
de Pareto par non-dominance ; sélection illustrative par somme des
risques terminaux sur le front (politique explicite, autorisée par §16
mais pas imposée par le chapitre 3).

#### Sorties

`docs/chapter4/outputs/optimizer_example.txt`, généré par
`python -m examples.optimizer_example` (T1078@DC01 → T1003@DC01
Terminal, `B_total=5000`) : 2 configurations énumérées, 2 faisables, la
configuration avec déception domine (risque terminal réduit de 0.297 à
0.172). `DE` y est une valeur illustrative (SP2 non implémenté) — pas un
résultat expérimental du chapitre 5.

#### Fichiers concernés

`src/optimizer.py`, `tests/test_optimizer.py`,
`examples/optimizer_example.py`.

#### Tests et validation

`tests/test_optimizer.py` — 22 tests (construction des candidats,
énumération/unicité, budget, dominance, front de Pareto, agrégation,
résolution de bout en bout, **validation exhaustive sur petite instance**
conforme à CLAUDE.md §23, invariant LLM hors du chemin d'exécution).
**426 tests** au total au moment de la validation. Détail complet :
`docs/chapter4/IMPLEMENTATION_REPORT.md`, section 10.

#### Limites actuelles

Exploration exhaustive uniquement (réservé aux petites instances de
validation, §23) ; la politique de sélection par somme des risques est
illustrative, pas une règle imposée ; pas de `reporter.py` dédié pour un
rapport explicatif complet (preuves, justification par placement) — seule
une matérialisation minimale de `Y*` existe (`to_deployment_plan`).

#### Lien avec l'étape suivante

RAG (`src/rag_indexer.py` / `src/rag_retriever.py`), puis annotation LLM
(`src/annotator_llm.py`) avec repli déterministe `rule_based_stub`
explicitement marqué comme tel si aucune API LLM réelle n'est disponible.

---

### Étape 12 — Implémentation du RAG (`src/rag_indexer.py` / `src/rag_retriever.py`)

*(branche `implementation/chapter4`)*

#### Objectif

Ingérer les documents déjà versionnés hors ligne (D3FEND, Engage,
littérature), les découper en chunks tracés, construire un index et
récupérer les passages pertinents pour une requête contextuelle (§9.1
étapes 2, 3, 7).

#### Traitement réalisé

Un chunk par entrée `source_evidence` (D3FEND), par
`description`/`long_description` distincte (Engage), par passage
scientifique déjà vérifié (littérature) — texte vide jamais indexé.
Chaque chunk : `chunk_id`, `source_id`, `source_type`, `document_id`,
`locator`, `text`, `text_hash` (SHA-256), `metadata`. Vecteur déterministe
TF-IDF avec « hashing trick » (256 dimensions, mots-outils exclus,
normalisation L2) — **choix technique explicite**, pas un embedding
sémantique de modèle de langage, documenté comme tel faute de
bibliothèque d'embeddings choisie à ce stade. La requête est encodée avec
les mêmes poids IDF que le corpus indexé pour rester comparable.

#### Sorties

`docs/chapter4/outputs/rag_chunks_example.json` (échantillon réel de 6
chunks) et `docs/chapter4/outputs/rag_retrieval_example.txt` (résultat
réel de récupération sur un index de 124 chunks réels — 44 D3FEND, 62
Engage, 18 littérature), générés par `python -m examples.rag_example` :
le premier résultat pour la requête *"decoy credential store to deceive
an adversary on a domain controller"* est `d3fend:D3-DUC:0` (« Decoy
User Credential »).

#### Fichiers concernés

`src/rag_indexer.py`, `src/rag_retriever.py`, `tests/test_rag_indexer.py`,
`tests/test_rag_retriever.py`, `examples/rag_example.py`.

#### Tests et validation

`tests/test_rag_indexer.py` (22 tests) + `tests/test_rag_retriever.py`
(13 tests) — tokenisation, exclusion des mots-outils, vecteurs
déterministes, IDF, ingestion synthétique et **ingestion réelle des trois
fichiers de staging**, index sans collision, similarité cosinus,
classement, `top_k`, filtre par source, invariant LLM hors du chemin
d'exécution. **461 tests** au total au moment de la validation. Détail
complet : `docs/chapter4/IMPLEMENTATION_REPORT.md`, section 5.

#### Limites actuelles

Vecteur TF-IDF haché déterministe, pas un embedding sémantique ; index en
mémoire, pas de magasin vectoriel persistant ; liste de mots-outils fixe
et anglaise uniquement ; aucune intégration avec `annotator_llm.py` (non
implémenté) pour convertir les `RetrievalResult` en
`DeceptionEvidence`/`AnnotationContext.retrieved_evidence`.

#### Lien avec l'étape suivante

Annotation LLM (`src/annotator_llm.py`), avec repli déterministe
`rule_based_stub` explicitement marqué comme tel si aucune API LLM réelle
n'est disponible.

## OPEN_DECISION en cours

Ces points sont volontairement non résolus et ne doivent pas l'être
implicitement par une étape future sans décision explicite :

1. Quels concepts D3FEND deviennent réellement des mécanismes déployables
   \(d \in \mathcal D\) ?
2. Comment aligner D3FEND et Engage sans fusion arbitraire ? (Les trois
   staging — D3FEND, Engage, littérature — restent strictement séparés
   dans cette phase — aucun rapprochement automatique, même
   sémantiquement évident, ex. D3FEND « Decoy File » vs Engage « Lures »
   vs les decoy documents de la littérature.)
3. Comment les passages scientifiques (et les preuves D3FEND/Engage)
   seront-ils transformés vers les champs finaux `target_artifacts`,
   `requirements`, `possible_placements`, `interaction_mechanism`,
   `realism_factors`, `progression_effects`, `resource_requirements`,
   `maintenance_requirements`, `admissibility_profile` ?
4. Quelle sémantique SP1 donner aux listes vides de
   `DeceptionAdmissibilityProfile` ?
5. Comment agréger/valider les associations ATT&CK↔déception (D3FEND et
   Engage) avant de produire \(M_{i,d}\) ?
6. Quels mécanismes constituent finalement le catalogue fermé \(\mathcal D\) ?
7. Un thème documentaire `enticingness`, distinct de `realism`, doit-il
   être ajouté à la taxonomie documentaire de la littérature si le corpus
   s'enrichit d'autres travaux empiriques sur l'attractivité des leurres ?
