# `tools/deception_kb` — construction OFFLINE de la KB déception

Ce dossier contient une chaîne **hors runtime**, séparée de `src/`, qui
transforme des sources documentaires officielles en STAGING intermédiaire
pour la future base de connaissances cyberdéception du PFE.

```text
RAW (fichiers officiels tels que téléchargés)
  ↓
D3FEND STAGING (tools/deception_kb/d3fend_seed_builder.py)
ENGAGE STAGING (tools/deception_kb/engage_seed_builder.py)
  ↓
future enrichment (littérature scientifique, normalisation D3FEND↔Engage,
LLM/RAG contrôlé)
  ↓
FINAL CATALOG (data/deception/deception_catalog.json, chargé par
src/knowledge_deception.py)
```

Points essentiels :

- **D3FEND et MITRE Engage sont deux sources parmi d'autres**, pas le
  catalogue final. Elles restent des staging **distincts et non fusionnés**
  (`engage_activity_seed_*.json`/`engage_attack_mapping_seed_*.json` d'un
  côté, `d3fend_deception_seed_*.json`/`d3fend_attack_mapping_seed_*.json`
  de l'autre) — aucun rapprochement automatique D3FEND↔Engage n'est
  effectué ici (OPEN_DECISION 2 ci-dessous).
- **Le staging n'est pas le catalogue final** `deception_catalog.json` : il
  n'est ni chargé, ni lu par `src/knowledge_deception.py`.
- **Le staging n'est pas SP1** : côté D3FEND, `parent_ids`/`child_ids`/
  `is_leaf` sont conservés tels quels ; côté Engage, une activité
  (EACxxxx/SACxxxx) reste une entité documentaire source — dans les deux
  cas, sans décider quels concepts deviennent des mécanismes déployables
  `d ∈ D` (voir OPEN_DECISION 1 ci-dessous).
- **Les mappings D3FEND↔ATT&CK (`origin: "d3fend_inferred"`) et
  Engage↔ATT&CK (`origin: "mitre_engage_v1.0"`) extraits ici ne sont pas
  encore `M_{i,d}`** utilisables par SP1/`admissibility.py`.
- **Aucun LLM n'intervient dans cette phase.** Elle est 100 % déterministe :
  mêmes fichiers sources → mêmes fichiers de staging, bit à bit.

## Pourquoi une couche séparée de `src/knowledge_deception.py`

`src/knowledge_deception.py` a une seule responsabilité : charger et
valider le catalogue normalisé **final** (`catalog_version` + liste de
`DeceptionMechanism`). Construire ce catalogue à partir de sources brutes
(D3FEND, puis Engage, puis littérature) est un problème différent :
acquisition réseau versionnée, inspection de format, extraction
déterministe, provenance fine. Cette responsabilité vit ici, dans
`tools/`, explicitly hors du runtime SP1/SP2/SP3.

## Champs D3FEND 1.5.0 réellement observés et utilisés

L'ontologie officielle (`d3fend.json`) est un document **JSON-LD** :
`{"@context": {...}, "@graph": [...]}`. Chaque classe pertinente porte
(champs constatés par inspection directe du fichier téléchargé, pas
supposés à l'avance) :

| Champ D3FEND (JSON-LD) | Usage dans le staging |
|---|---|
| `@id` | résolu en IRI complète via `@context` → `source_uri` |
| `d3f:d3fend-id` | identifiant canonique (ex. `D3-DO`) → `source_technique_id` |
| `rdfs:label` | → `name` |
| `d3f:definition` | → `definition` |
| `d3f:kb-article` | texte markdown (`## How it works`, `## Considerations`, ou `## Technique Overview` pour les techniques racines) → `kb_article`, conservé verbatim |
| `d3f:kb-reference` | référence(s) (objet unique ou liste) vers des nœuds `d3f:Reference-*` → `references` (titre, lien, auteur, organisation) |
| `d3f:synonym` | chaîne unique ou liste → `synonyms` |
| `d3f:spoofs` | artefact imité par un leurre → contribue à `artifacts` |
| `d3f:manages` | artefact géré par un environnement de leurre → contribue à `artifacts` |
| `d3f:enables` (+ motif OWL `owl:Restriction` équivalent) | identifie les techniques qui appartiennent directement à une tactique (ex. `Deceive`) |
| `rdfs:subClassOf` | hiérarchie de classes ; les nœuds blancs `owl:Restriction` (`@id` commençant par `_:`) sont exclus des parents réels |

Le fichier de mappings inférés (`d3fend-full-mappings.json`) est un
**résultat de requête SPARQL** standard :
`{"head": {"vars": [...]}, "results": {"bindings": [...]}}`. Chaque
`binding` relie une technique D3FEND (`def_tech`) à une technique
offensive (`off_tech`, `off_tech_id`) via une chaîne d'artefacts partagés.

**Constat important (inspection réelle du fichier 1.5.0) :** ce fichier
mélange plusieurs frameworks offensifs distincts, identifiables par le
champ `framework_key` : `"enterprise"` (ATT&CK Enterprise), `"ics"` (ATT&CK
ICS), et `"sparta"` (MITRE SPARTA — un référentiel distinct pour les
systèmes spatiaux, avec des identifiants qui ne suivent pas le format
`Txxxx`, ex. `"PER-0005"`). CLAUDE.md §8 restreint explicitement la base de
connaissances offensive à `enterprise-attack.json` : le builder ne retient
donc que `framework_key == "enterprise"`, et valide en plus que chaque
`attack_id` conservé respecte le format `Txxxx` / `Txxxx.xxx`.

## Comment la branche "Deceive" est identifiée

Aucune liste d'identifiants D3FEND n'est codée en dur. Le builder :

1. cherche les classes portant une propriété directe
   `d3f:enables → d3f:Deceive` (vérifié par recoupement avec le motif
   `owl:Restriction` équivalent — les deux méthodes donnent exactement le
   même résultat sur D3FEND 1.5.0) ;
2. reconstruit la carte parent → enfants à partir de `rdfs:subClassOf` sur
   l'ensemble du graphe ;
3. parcourt récursivement, depuis ces racines, tous les descendants.

Sur D3FEND 1.5.0, cela identifie exactement 2 racines (`Decoy Object`,
`Decoy Environment`) et 11 concepts au total — nombre confirmé identique à
la page officielle `https://d3fend.mitre.org/tactic/d3f:Deceive/`
(« The Deceive tactic contains 11 techniques »).

## Bindings bruts, relations uniques, couples uniques (durcissement)

`d3fend-full-mappings.json` contient des lignes (« bindings ») SPARQL qui
peuvent représenter **exactement** la même relation plusieurs fois. Trois
notions distinctes sont donc explicitement séparées, dans `mapping_seed`
comme dans le rapport :

| Métrique | Dans `mapping_seed` | Dans le rapport | Signification |
|---|---|---|---|
| Bindings bruts retenus | `raw_binding_count` | `raw_attack_binding_count` | nombre de bindings SPARQL après filtrage branche Deceive + `framework_key == "enterprise"`, **avant** déduplication |
| Relations documentaires uniques | `unique_relation_count` | `unique_attack_relation_count` | nombre d'entrées après déduplication **exacte** ; c'est la taille de `mapping_seed["mappings"]` |
| Couples D3FEND↔ATT&CK uniques | `unique_d3fend_attack_pair_count` | `unique_d3fend_attack_pair_count` | nombre de couples `(d3fend_id, attack_id)` distincts, tous chemins d'artefacts confondus |

**Clé de déduplication** (`_mapping_dedup_key`, voir
`d3fend_seed_builder.py`) — deux relations ne sont fusionnées que si elles
coïncident **exactement** sur les sept champs :

```text
(d3fend_id, attack_id,
 relation_path.def_artifact_relation,
 relation_path.shared_artifact,
 relation_path.off_artifact_relation,
 framework, origin)
```

La déduplication ne supprime donc que les bindings strictement identiques.
Un même couple D3FEND↔ATT&CK justifié par **plusieurs chemins d'artefacts
différents** (`relation_path` différent) est conservé comme autant de
preuves documentaires distinctes — jamais fusionné, jamais pondéré, jamais
associé à une confiance inventée. La première occurrence est conservée,
dans l'ordre déterministe du fichier source.

`validate_attack_mapping_seed` rejette explicitement (`D3fendSeedBuilderError`)
toute relation strictement dupliquée qui subsisterait dans un
`mapping_seed` chargé ou corrompu, mais n'a jamais rejeté deux relations ne
partageant qu'un même `(d3fend_id, attack_id)` avec un `relation_path`
différent.

## MITRE Engage v1.0 — sources, champs réellement observés, conventions

Source officielle unique, dépôt `https://github.com/mitre/engage`, **pinné**
au commit `5ae09f6f7511ebb6d35d70a9107490900380d3d8` (jamais `main`/`latest`).
`framework_version = "1.0"` (version déclarée du jeu de données) et
`source_revision` (le commit exact) sont deux notions **distinctes**,
conservées séparément partout dans le staging et le manifest — jamais
conflées.

Sept fichiers officiels `Data/json/*.json` sont utilisés (inspection directe
avant tout code, aucun champ supposé à l'avance) :

| Fichier | Forme réelle | Champs conservés |
|---|---|---|
| `activities.json` | liste plate | `id`, `name`, `description`, `long_description` |
| `activity_details.json` | **dict indexé par id d'activité** | `type`, `goals` (ids), `vulnerabilities` (liste `{id, eav}`), `attack_techniques` (liste `{id, name, attack_tactics: [libellés kebab-case]}`), `attack_tactics` (liste `{id: TAxxxx, name}`), `approaches` (ids, copie dénormalisée), `references` (liste `{id, title, url}`) |
| `approaches.json` | liste plate | `id`, `name`, `description`, `long_description` |
| `approach_details.json` | dict indexé par id d'approche | `type`, `goals`, `activities` (ids, copie dénormalisée) |
| `approach_activity_mappings.json` | liste plate `{approach_id, activity_id}` | table de jointure **canonique**, utilisée à la place des copies dénormalisées ci-dessus |
| `attack_mapping.json` | liste plate | `attack_id`, `attack_technique`, `eav_id`, `eav`, `eac_id`, `eac` |
| `references.json` | liste plate | `id`, `title`, `url`, `activity_id` |

**Point d'attention constaté par inspection, pas supposé** : dans
`activity_details.json`, le champ `attack_tactics` existe à **deux niveaux
distincts** avec une forme différente — la liste de libellés kebab-case
(ex. `"discovery"`) nichée dans chaque élément de `attack_techniques[]`, et
la liste d'objets `{id: TAxxxx, name}` au niveau racine de l'activité. Le
staging les conserve séparément (`attack_tactic_labels` pour la première,
`attack_tactics` pour la seconde) — aucune fusion, aucune conversion de
l'une vers l'autre.

### Convention de préfixe EAC/SAC/EAP/SAP

Aucune liste ni règle n'est codée en dur : la famille d'une entité
(`activity_family`/`approach_family`) est dérivée du **préfixe de son
identifiant**, démontré par inspection sur les deux familles d'entités
(activités et approches) du jeu de données réel — `EAC`/`SAC` pour les
activités (23 EAC, 8 SAC sur 31), `EAP`/`SAP` pour les approches. Un préfixe
non reconnu lève `EngageSeedBuilderError` plutôt que d'être deviné.

Interprétation humaine/documentaire de chaque préfixe, telle que
**réellement supportée** par `activity_details[id]["type"]` et
`approach_details[id]["type"]` (valeurs observées : `"Engagement"` ou
`"Strategic"` — jamais `"Support"`) :

| Préfixe | Signification | Valeur `type` observée |
|---|---|---|
| `EAC` | Engagement Activity | `"Engagement"` |
| `SAC` | **Strategic** Activity | `"Strategic"` |
| `EAP` | Engagement Approach | `"Engagement"` |
| `SAP` | **Strategic** Approach | `"Strategic"` |

`SAC`/`SAP` ne doivent jamais être présentés comme « Support Activity »/
« Support Approach » — cette lecture n'est pas supportée par les données
officielles. Le champ brut `type` est conservé séparément sous
`detail_type` (activités) ou dans `source_evidence` (approches), sans être
fusionné avec `activity_family`/`approach_family` ni traduit.

### Le champ `activity_id` de `references.json` peut désigner une approche

Constat empirique : sur les 67 références du jeu de données réel, 4
pointent vers `SAP0001`/`SAP0002` — des identifiants d'**approche**, pas
d'activité, bien que le champ s'appelle `activity_id`. Le builder ne
suppose donc jamais que ce champ désigne une activité : les références
d'activité proviennent de la copie déjà dénormalisée dans
`activity_details.json`, et les références d'approche sont obtenues en
filtrant `references.json` par correspondance directe avec un
`approach_id` connu.

### Bindings bruts, relations uniques, couples uniques (Engage↔ATT&CK)

Même principe que pour D3FEND, avec une clé de déduplication adaptée à la
forme réelle d'`attack_mapping.json` :

| Métrique | Dans `mapping_seed` | Dans le rapport | Signification |
|---|---|---|---|
| Bindings bruts | `raw_mapping_count` | `raw_attack_mapping_count` | nombre de lignes retenues après filtrage du format `Txxxx`/`Txxxx.xxx`, **avant** déduplication |
| Relations uniques | `unique_mapping_count` | `unique_attack_mapping_count` | après déduplication **exacte** |
| Couples uniques | `unique_attack_activity_pair_count` | `unique_attack_activity_pair_count` | couples `(attack_id, engage_activity_id)` distincts, toutes vulnérabilités adverses (EAV) confondues |

**Clé de déduplication** (`_engage_mapping_dedup_key`) :
`(attack_id, adversary_vulnerability_id, engage_activity_id)`. Cette clé a
été confirmée **suffisante** par inspection réelle du jeu de données
officiel 1.0 : le seul doublon exact constaté (`T1040`/`EAV0007`/`EAC0023`)
partage aussi tout le contenu de la relation ; aucune paire distincte
n'observée avec un contenu différent sous le même triplet. Deux relations
qui partagent `(attack_id, engage_activity_id)` mais diffèrent par
`adversary_vulnerability_id` (EAV) sont **toutes deux conservées** — c'est
le comportement attendu de cette clé, testé explicitement
(`tests/test_engage_seed_builder.py::TestAttackMappingSeed::
test_same_attack_id_and_activity_different_eav_both_kept`).

**Important (réf. tâche §12) :** une relation `(attack_id, EAV, EAC)` n'est
**pas** `M_{i,d}` — `engage_activity_id` n'est pas nécessairement un
mécanisme final `d` du catalogue `D`, et un futur mécanisme peut agréger
D3FEND + Engage + littérature. Ces relations restent du staging
documentaire (`origin: "mitre_engage_v1.0"`).

### `git_blob_sha` — champ optionnel non peuplé par la CLI

`build_manifest_entry` accepte un paramètre `git_blob_sha` optionnel
(destiné à un usage futur/manuel : SHA de blob Git du fichier dans le dépôt
`mitre/engage`, distinct du SHA-256 calculé sur les octets bruts). La CLI
`engage_seed_builder` ne le renseigne **pas automatiquement** — aucun
argument `--git-blob-sha-*` n'était demandé, et le SHA-256 sur les octets
réellement téléchargés reste la preuve de provenance faisant foi. Ce champ
reste disponible pour un enrichissement manuel ultérieur si nécessaire.

## OPEN_DECISION préservées (non résolues par cette phase)

1. Quels concepts D3FEND (et quelles activités/approches Engage) deviennent
   les mécanismes déployables `d ∈ D` ?
2. Comment relier précisément D3FEND ↔ Engage sans fusion arbitraire ?
   (Les deux staging restent strictement séparés dans cette phase — aucun
   rapprochement, même sémantiquement évident, ex. D3FEND « Decoy File »
   vs Engage « Lures ».)
3. Comment transformer les preuves D3FEND/Engage/littérature vers les
   champs finaux `interaction_mechanism`, `realism_factors`,
   `progression_effects`, `admissibility_profile` ?
4. Quelle sémantique SP1 donner aux listes vides de
   `DeceptionAdmissibilityProfile` ?
5. Comment valider les mappings ATT&CK↔déception (D3FEND et Engage) avant
   de les utiliser comme `M_{i,d}` ?

## Utilisation

La CLI régénère de façon cohérente et reproductible le staging, le rapport
**et** le manifest de provenance (`source_manifest.json`) :

```bash
python -m tools.deception_kb.d3fend_seed_builder \
  --ontology data/deception/raw/d3fend/1.5.0/d3fend.json \
  --mappings data/deception/raw/d3fend/1.5.0/d3fend-full-mappings.json \
  --release-version 1.5.0 \
  --ontology-url https://d3fend.mitre.org/ontologies/d3fend/1.5.0/d3fend.json \
  --mappings-url https://d3fend.mitre.org/ontologies/d3fend/1.5.0/d3fend-full-mappings.json \
  --retrieval-date 2026-08-22 \
  --out-dir data/deception/staging \
  --manifest-out data/deception/source_manifest.json
```

(Les URLs ci-dessus sont documentées ici comme exemples — la CLI ne les
utilise jamais comme valeur par défaut silencieuse : `--ontology-url` et
`--mappings-url` sont obligatoires.)

Arguments de provenance requis (aucune valeur devinée ou codée en dur) :

| Argument | Rôle |
|---|---|
| `--ontology` / `--mappings` | chemins locaux vers les fichiers officiels déjà téléchargés |
| `--release-version` | version D3FEND pinnée (ex. `1.5.0`) |
| `--ontology-url` / `--mappings-url` | URL officielle MITRE de chaque fichier (provenance) |
| `--retrieval-date` | date d'acquisition, format `YYYY-MM-DD`, validée par la CLI |
| `--out-dir` | répertoire de sortie du seed/mapping seed/rapport |
| `--manifest-out` | chemin de sortie de `source_manifest.json` |
| `--d3fend-iri-base` | (optionnel) préfixe IRI `d3f:` pour résoudre les identifiants du fichier de mappings |

Les SHA-256 inscrits dans le manifest sont **réutilisés** depuis ceux déjà
calculés par `build_d3fend_deception_seed`/`build_d3fend_attack_mapping_seed`
(pas de seconde lecture des fichiers), avec une vérification de cohérence
explicite (`D3fendSeedBuilderError` en cas de divergence). Le rapport
généré porte donc toujours `report["sources"] == manifest["sources"]` —
jamais une liste vide.

Tous les chemins, URLs et dates sont fournis explicitement en argument ;
rien n'est codé en dur ni deviné dans le module.

### CLI MITRE Engage

```bash
python -m tools.deception_kb.engage_seed_builder \
  --activities data/deception/raw/engage/1.0/activities.json \
  --activity-details data/deception/raw/engage/1.0/activity_details.json \
  --approaches data/deception/raw/engage/1.0/approaches.json \
  --approach-details data/deception/raw/engage/1.0/approach_details.json \
  --approach-activity-mappings data/deception/raw/engage/1.0/approach_activity_mappings.json \
  --attack-mapping data/deception/raw/engage/1.0/attack_mapping.json \
  --references data/deception/raw/engage/1.0/references.json \
  --engage-version 1.0 \
  --source-revision 5ae09f6f7511ebb6d35d70a9107490900380d3d8 \
  --retrieval-date 2026-08-22 \
  --out-dir data/deception/staging \
  --manifest data/deception/source_manifest.json
```

| Argument | Rôle |
|---|---|
| `--activities` / `--activity-details` / `--approaches` / `--approach-details` / `--approach-activity-mappings` / `--attack-mapping` / `--references` | chemins locaux vers les 7 fichiers officiels déjà téléchargés |
| `--engage-version` | version déclarée du jeu de données Engage (ex. `1.0`), distincte de `--source-revision` |
| `--source-revision` | commit Git exact du dépôt `mitre/engage` pinné (jamais `main`/`latest`) |
| `--retrieval-date` | date d'acquisition, format `YYYY-MM-DD`, validée par la CLI |
| `--out-dir` | répertoire de sortie du seed d'activités/approches, du mapping seed et du rapport |
| `--manifest` | chemin de `source_manifest.json` à étendre (créé si absent ; entrées existantes d'autres frameworks, ex. D3FEND, préservées) |

Les URLs officielles (`https://raw.githubusercontent.com/mitre/engage/<source_revision>/Data/json/<fichier>`)
sont dérivées mécaniquement du dépôt officiel mandaté et de
`--source-revision` — jamais devinées, jamais un argument séparé requis. Le
manifest étendu par cette CLI porte, pour chaque source Engage,
`framework: "MITRE Engage"` et `source_revision` en plus de
`release_version` (voir extension additive et rétrocompatible de
`build_manifest_entry` dans `d3fend_seed_builder.py`, réutilisée sans
duplication).
