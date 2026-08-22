# `tools/deception_kb` — construction OFFLINE de la KB déception

Ce dossier contient une chaîne **hors runtime**, séparée de `src/`, qui
transforme des sources documentaires officielles en STAGING intermédiaire
pour la future base de connaissances cyberdéception du PFE.

```text
RAW (fichiers officiels tels que téléchargés)
  ↓
D3FEND STAGING (ce module — tools/deception_kb/d3fend_seed_builder.py)
  ↓
future enrichment (MITRE Engage, littérature scientifique, LLM/RAG contrôlé)
  ↓
FINAL CATALOG (data/deception/deception_catalog.json, chargé par
src/knowledge_deception.py)
```

Points essentiels :

- **D3FEND est une source parmi d'autres**, pas le catalogue final.
- **Le staging n'est pas le catalogue final** `deception_catalog.json` : il
  n'est ni chargé, ni lu par `src/knowledge_deception.py`.
- **Le staging n'est pas SP1** : `parent_ids`/`child_ids`/`is_leaf` sont
  conservés tels quels, sans décider quels concepts D3FEND deviennent des
  mécanismes déployables `d ∈ D` (voir OPEN_DECISION 1 ci-dessous).
- **Les mappings D3FEND↔ATT&CK extraits ici (`origin: "d3fend_inferred"`)
  ne sont pas encore `M_{i,d}`** utilisables par SP1/`admissibility.py`.
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

## OPEN_DECISION préservées (non résolues par cette phase)

1. Quels niveaux de la hiérarchie D3FEND Deceive deviennent des mécanismes
   déployables `d ∈ D` ? (`parent_ids`/`child_ids`/`is_leaf` sont conservés
   sans trancher.)
2. Comment transformer les informations D3FEND/Engage/littérature vers les
   champs finaux `interaction_mechanism`, `realism_factors`,
   `progression_effects`, `admissibility_profile` ?
3. Quelle sémantique SP1 donner aux listes vides de
   `DeceptionAdmissibilityProfile` ?
4. Comment valider les mappings ATT&CK↔déception inférés par D3FEND avant
   de les utiliser comme `M_{i,d}` ?

## Utilisation

```bash
python -m tools.deception_kb.d3fend_seed_builder \
  --ontology data/deception/raw/d3fend/1.5.0/d3fend.json \
  --mappings data/deception/raw/d3fend/1.5.0/d3fend-full-mappings.json \
  --release-version 1.5.0 \
  --out-dir data/deception/staging
```

Tous les chemins sont fournis explicitement en argument ; aucun chemin
absolu local n'est codé en dur dans le module.
