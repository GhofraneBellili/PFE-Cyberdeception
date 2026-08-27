# Rapport technique final — Chapitre 4

> Source de vérité définitive pour la rédaction du chapitre 4. Ce
> document ne recopie ni `CLAUDE.md` (contrat scientifique) ni
> `README.md` (journal cumulatif) : c'est une synthèse technique propre à
> chaque sous-section, structurée pour l'écriture académique. Pour
> chaque sous-section : (A) objectif, (B) ce qui est réellement
> implémenté, (C) fichiers/classes/fonctions, (D) entrées, (E) traitement
> algorithmique exact, (F) sorties, (G) technologies réellement
> utilisées, (H) décisions techniques importantes, (I) écart
> modèle↔implémentation si applicable, (J) limites réelles, (K)
> artefact/capture disponible, (L) formulation à NE PAS utiliser dans le
> mémoire.
>
> État au moment de la rédaction (mise à jour post-upgrade RAG sémantique +
> catalogue étendu, voir `docs/chapter4/BEFORE_UPGRADE_STATE.md` pour
> l'état AVANT cette passe) : **664 tests verts** (+ 2 tests d'intégration
> optionnels `pytest -m real_llm`), **RAG sémantique** (`sentence-transformers`
> + FAISS) devenu le **moteur principal** — le TF-IDF haché
> (`src/rag_indexer.py::RagIndex`/`retrieve`) reste disponible comme
> **baseline lexicale expérimentale**, comparée quantitativement
> (`docs/chapter4/outputs/rag_semantic_evaluation.*` : Recall@5 sémantique
> 0.396 > lexical 0.331 ; mode hybride retenu, alpha=0.8, Recall@5=0.470,
> gain mesuré, pas supposé). Catalogue réel de **26 mécanismes** (9
> D3FEND, 15 MITRE Engage, 2 littérature — `docs/chapter4/CATALOG_AUDIT.md`),
> mapping réel de **591 relations** (464 directes MITRE Engage + 127
> dérivées D3FEND, 271 techniques ATT&CK couvertes —
> `docs/chapter4/outputs/catalog_statistics.*`). Instance SP1 étendue :
> **4 candidats réellement admissibles** sur 3042 candidats bruts, couvrant
> 3 mécanismes distincts (`D3-DNR`, `EAC0009`, `EAC0021`) sur 2 occurrences
> (`docs/chapter4/outputs/sp1_extended_real_example.*`) — voir section
> 4.4.1 pour l'analyse de la cause structurelle (pas un manque de richesse
> d'instance). État de l'exécution LLM réelle et des figures C5/C6/C7 :
> voir la note de clôture, mise à jour séparément une fois cette phase
> tranchée.

---

## 4.1 Environnement technique

### 4.1.1 Technologies utilisées

**A. Objectif.** Documenter les technologies réellement présentes dans
le dépôt.

**B. Réellement implémenté.** Python ≥ 3.11, Pydantic 2.x, NetworkX 3.x,
pytest ≥ 8.0 (dépendances déclarées) ; `urllib.request` (bibliothèque
standard) pour l'appel HTTP au provider LLM réel ; groupe optionnel
`rag` (`sentence-transformers>=3,<4`, `faiss-cpu>=1.8,<2`, `numpy`) pour
le RAG sémantique — moteur principal du RAG depuis cette passe (section
4.4.2), le TF-IDF haché restant une baseline expérimentale sans
dépendance.

**C. Fichiers.** `pyproject.toml`, `docs/chapter4/TECHNOLOGIES.md`.

**D. Entrées.** N/A.

**E. Traitement.** N/A (inventaire, pas un calcul).

**F. Sorties.** Tableau de dépendances.

**G. Technologies.** Voir B.

**H. Décisions techniques importantes.** Choix explicite de ne PAS
ajouter `requests` (bibliothèque tierce) pour l'appel HTTP LLM —
`urllib.request` suffit. Pour le RAG : choix explicite de ne PAS utiliser
de base vectorielle EXTERNE (service Chroma/Pinecone/Weaviate) — l'index
vectoriel reste local et reproductible (FAISS `IndexFlatIP` en mémoire,
repli NumPy pur si FAISS n'est pas installable, `src/vector_index.py`) ;
le modèle d'embeddings n'est jamais codé en dur (`RAG_EMBEDDING_MODEL`,
défaut `BAAI/bge-small-en-v1.5`, repli documenté
`sentence-transformers/all-MiniLM-L6-v2`, `src/semantic_embedder.py`).

**I. Écart modèle↔implémentation.** N/A — pas de formalisation
mathématique associée à cette sous-section.

**J. Limites réelles.** Aucun solveur d'optimisation externe.

**K. Artefact/capture.** Aucun (tableau textuel dans
`docs/chapter4/TECHNOLOGIES.md`).

**L. Formulation à ne pas utiliser.** Ne pas écrire « le système utilise
une architecture microservices » — faux. Ne pas écrire « le système
utilise une base de données vectorielle externe/un service de vector
search managé » — faux : l'index vectoriel (FAISS) est local, en mémoire,
reproductible, jamais un service tiers (Chroma/Pinecone/Weaviate).

### 4.1.2 Organisation du projet

**A. Objectif.** Présenter la structure réelle du dépôt.

**B. Réellement implémenté.** Arborescence complète et stable :
`src/` (18 modules, dont `semantic_embedder.py`/`vector_index.py` ajoutés
pour le RAG sémantique), `tools/deception_kb/` (couche offline, catalogue
étendu à 26 mécanismes), `data/deception/` (staging + catalogue + mapping
réels) + `data/rag/` (jeu de requêtes d'évaluation RAG), `examples/` (15
scripts exécutables), `tests/` (664 tests + 2 optionnels `real_llm`),
`docs/chapter4/` (ce document + IMPLEMENTATION_REPORT.md +
TECHNOLOGIES.md + SCREENSHOT_MANIFEST.md + ADMISSIBILITY_EVIDENCE_AUDIT.md
+ CATALOG_AUDIT.md + BEFORE_UPGRADE_STATE.md + outputs/ + screenshots/),
`runs/` (sorties d'exécution, non versionnées).

**C. Fichiers.** N/A (structure elle-même).

**D. Entrées.** Dépôt Git.

**E. Traitement.** Script Python ponctuel de listage récursif
(répertoires `.git`/`.venv`/`.claude`/`__pycache__` exclus, données
volumineuses résumées par un nombre de fichiers).

**F. Sorties.** `docs/chapter4/outputs/architecture_tree.txt`.

**G. Technologies.** Python pur (script ponctuel, pas un module `src/`).

**H. Décisions techniques importantes.** `runs/` explicitement exclu du
contrôle de version (`.gitignore`) — régénérable, pas une preuve
versionnée ; seule `docs/chapter4/outputs/pipeline_example.txt` est
retenue comme preuve d'exécution du pipeline complet.

**I. Écart modèle↔implémentation.** N/A.

**J. Limites réelles.** Aucune.

**K. Artefact/capture.** C1 (`AVAILABLE`) —
`docs/chapter4/screenshots/01_architecture/architecture_tree.png`
(1900×2475 px, généré par `tools/chapter4_figures/c1_architecture.py`).

**L. Formulation à ne pas utiliser.** Ne pas décrire `runs/` comme une
« base de données de résultats » — c'est un répertoire de sortie de
scripts, régénérable, non versionné.

---

## 4.2 Architecture logicielle du système

### 4.2.1 Vue d'ensemble

**A. Objectif.** Montrer la chaîne complète des traitements.

**B. Réellement implémenté.** Chaîne intégrale : préparation des
connaissances → SP1 → RAG → annotation (11 sous-métriques) → validation
+ agrégation déterministe → gel → coût → SP3 → optimisation → reporter →
orchestrateur. **Tous les blocs sont implémentés et testés.**

**C. Fichiers.** L'ensemble de `src/`.

**D. Entrées.** Instance de système d'information, catalogue de
déception, mapping `M_{i,d}`, corpus documentaire, paramètres de
coût/budget.

**E. Traitement.** Voir sections 4.3 à 4.5 pour le détail par module.

**F. Sorties.** `Y*` (plan de déploiement), risques avant/après, rapport
interprétable.

**G. Technologies.** Python pur + Pydantic + NetworkX.

**H. Décisions techniques importantes.** Un seul point d'entrée
(`src/orchestrator.py`) enchaîne tous les modules, chacun testé
indépendamment ET en intégration.

**I. Écart modèle↔implémentation.** Le modèle du chapitre 3 décrit un
problème global `(P)` unique ; l'implémentation matérialise cette unicité
par un orchestrateur explicite qui appelle chaque sous-problème (SP1,
SP2, SP3) dans l'ordre, mais chaque sous-problème reste un module Python
séparé et testable isolément — pas une fonction monolithique.

**J. Limites réelles.** Le catalogue réel (26 mécanismes, section 4.3.3)
n'a de relation `M_{i,d}` tracée que pour 18 d'entre eux, et un prérequis
d'admissibilité documenté (`required_*`) pour seulement 3 (`D3-DNR`,
`EAC0009`, `EAC0021`, section 4.4.1) — l'espace de décision effectivement
exploré par un exemple de bout en bout reste donc plus restreint que le
catalogue complet ne le suggère, limite documentée plutôt que masquée.

**K. Artefact/capture.** Aucune capture dédiée (diagramme reproductible
dans le texte).

**L. Formulation à ne pas utiliser.** Ne pas écrire « le système a été
validé sur un système d'information réel de grande taille » — seuls des
exemples explicites de petite taille (2 à 3 occurrences) ont été
exécutés.

### 4.2.2 Responsabilités des modules

**A. Objectif.** Cartographier responsabilité ↔ module, en cohérence
avec la séparation des rôles imposée par le chapitre 3 (§17).

**B. Réellement implémenté.** 15 modules `src/`, chacun avec une
responsabilité unique (voir tableau `IMPLEMENTATION_REPORT.md` section
4.2.2 pour le détail ligne par ligne — non recopié ici).

**C. Fichiers.** Tous les fichiers de `src/`.

**D-F.** N/A (méta-organisation).

**G. Technologies.** N/A.

**H. Décisions techniques importantes.** `src/orchestrator.py`
n'appartient pas à la liste des modules recommandés par CLAUDE.md §26 —
ajout spécifique à la tâche d'implémentation du chapitre 4, justifié par
le besoin d'un point d'entrée unique testable.

**I. Écart modèle↔implémentation.** Le chapitre 3 (§17) définit des
rôles conceptuels (« Sources/KB/RAG », « LLM », « Règles déterministes »,
« Moteur probabiliste », « Solveur », « Reporter ») — l'implémentation
matérialise CHACUN de ces rôles par un ou plusieurs modules Python
distincts, avec un test dédié vérifiant qu'aucun module de calcul
(risque, optimisation, rapport) n'importe le module d'annotation LLM ni
le RAG (invariant testé par analyse `ast`, pas une convention non
vérifiée).

**J. Limites réelles.** `src/reporter.py` ne produit pas de justification
textuelle narrative (uniquement des champs structurés).

**K. Artefact/capture.** Aucune.

**L. Formulation à ne pas utiliser.** Ne pas écrire « chaque module
correspond exactement à une section de CLAUDE.md » — `orchestrator.py`
est une exception explicite, documentée comme telle.

---

## 4.3 Préparation des données et connaissances

### 4.3.1 Instance et graphe

**A. Objectif.** Représenter `G=(V,E)`, une occurrence `T_{i,h}`, une
instance de système d'information (SI), de façon strictement validée.

**B. Réellement implémenté.** Modèles Pydantic v2 stricts
(`extra="forbid"`), invariants de divergence `π` validés à la
construction, cohérence croisée `Critical(h)`/`Accessible(h)` entre
nœuds et inventaire SI.

**C. Fichiers/classes/fonctions.** `src/schemas.py`
(`TechniqueOccurrence`, `NodeAttributes`, `AttackGraph`,
`AttackGraphEdge`, `SystemInstance`, `SIInventory`, `Asset`, `Location`,
`SITopologyEdge`) ; `src/graph_builder.py` (`build_attack_graph`,
`to_networkx`, `get_parent_ids`/`get_child_ids`,
`identify_entry_nodes`/`identify_terminal_nodes`).

**D. Entrées.** Dictionnaires/JSON fournis explicitement par l'appelant
(aucune génération automatique de graphe).

**E. Traitement.** Validation stricte à la construction (Pydantic) ;
`occurrence_id` calculé automatiquement (`technique_id@asset_id`, jamais
saisi indépendamment) ; identification `Entry`/`Terminal` par règles
déterministes sur les tactiques/impacts/`Critical(h)`.

**F. Sorties.** Objets `AttackGraph`/`SystemInstance` validés,
`networkx.DiGraph` pour la navigation.

**G. Technologies.** Pydantic v2, NetworkX 3.x.

**H. Décisions techniques importantes.** Aucune valeur par défaut non
prévue par l'architecture (ex. pas de seuil `theta` par défaut — toujours
fourni explicitement par l'appelant).

**I. Écart modèle↔implémentation.** Aucun — cette couche est une
traduction directe et fidèle du formalisme du chapitre 3 (§3, §5, §6),
sans simplification.

**J. Limites réelles.** Génération automatique du graphe hors périmètre
(CLAUDE.md §4) — toute instance de ce dépôt est construite explicitement
dans le code (exemples ou tests), jamais dérivée automatiquement d'un
scan réseau ou d'un inventaire externe.

**K. Artefact/capture.** Aucune capture dédiée (implicite dans C3).

**L. Formulation à ne pas utiliser.** Ne pas écrire « le graphe est
généré automatiquement à partir du système d'information » — faux, il
est toujours construit explicitement dans ce dépôt.

### 4.3.2 KB ATT&CK

**A. Objectif.** Accès structuré à `enterprise-attack.json`.

**B. Réellement implémenté.** Parseur STIX complet, indexation par
identifiant, extraction tactiques/plateformes.

**C. Fichiers/classes/fonctions.** `src/knowledge_attack.py`
(`load_attack_knowledge`, `AttackKnowledgeBase`,
`AttackTechniqueRecord`, `get_technique`, `get_tactics`,
`get_platforms`, `validate_graph_techniques`).

**D. Entrées.** `enterprise-attack.json` (format STIX officiel MITRE).

**E. Traitement.** Parsing STIX, indexation déterministe par
`technique_id`.

**F. Sorties.** `AttackKnowledgeBase` (objet Python indexé).

**G. Technologies.** Python pur.

**H. Décisions techniques importantes.** Aucun mapping ATT&CK↔déception
ici — rôle strictement réservé à `knowledge_deception.py` (section
4.3.3), pour respecter la séparation des responsabilités (§17.1).

**I. Écart modèle↔implémentation.** Aucun.

**J. Limites réelles.** Aucune connue.

**K. Artefact/capture.** Aucune.

**L. Formulation à ne pas utiliser.** Ne pas écrire que ce module
« sélectionne les techniques pertinentes » — il ne fait qu'un accès en
lecture à la base ATT&CK, aucune sélection ni filtrage métier.

### 4.3.3 KB cyberdéception

**A. Objectif.** Charger (runtime) et construire (offline) le catalogue
fermé `D` et le mapping `M_{i,d}`, avec provenance documentaire complète,
sans jamais inventer de propriété manquante.

**B. Réellement implémenté.** Deux politiques de construction du
catalogue coexistent, jamais confondues :
- `build_catalog()` (v1, **inchangée**) : 3 mécanismes D3FEND avec
  relation ATT&CK directement tracée (`D3-DF`, `D3-DUC`, `D3-DNR`), 127
  relations M_{i,d} — conservée telle quelle comme base auditée.
- `build_expanded_catalog()` (extension, réf. tâche « catalogue ≥25
  mécanismes ») : **catalogue réel de 26 mécanismes** — les 3 ci-dessus +
  6 concepts D3FEND supplémentaires (feuilles réelles de la branche
  « Deceive », interaction_mechanism cité du kb-article faute de relation
  ATT&CK tracée) + **15 activités MITRE Engage** (« Engagement », jamais
  « Strategic ») + **2 mécanismes génériques de littérature** (Honeypot,
  Honeytoken). C'est ce catalogue qui alimente
  `data/deception/deception_catalog.json` depuis cette passe. Audit
  mécanisme par mécanisme dans `docs/chapter4/CATALOG_AUDIT.md`.
  Mapping réel étendu : **591 relations** M_{i,d} — 464 **directes**
  (matrice officielle MITRE Engage↔ATT&CK, `engage_attack_mapping_seed_1.0.json`,
  792 lignes déjà versionnées mais jusqu'ici inutilisées) + 127
  **dérivées** (inférence SPARQL D3FEND, inchangées), couvrant **271**
  techniques ATT&CK distinctes (contre 125 avant cette passe) — chaque
  relation porte désormais `mapping_type: "direct"|"derived"` (jamais
  présentée comme une relation officielle si elle est dérivée).

**C. Fichiers/classes/fonctions.**
`tools/deception_kb/catalog_builder.py` (`build_catalog` [v1, inchangée],
`build_expanded_catalog`, `D3FEND_EXTENDED_INTERACTION_MECHANISM`,
`ENGAGE_MECHANISM_SPECS`, `ENGAGE_EXCLUDED_REASONS`,
`ENGAGE_REQUIRED_SERVICES`, `LITERATURE_MECHANISM_SPECS`,
`ARTIFACT_TO_LOCATION_TYPE`, `ADDITIONAL_LOCATION_TYPES`,
`REQUIRED_ASSET_TYPES`), `tools/deception_kb/mapping_builder.py`
(`build_mapping` [v1, inchangée], `build_expanded_mapping`,
`_engage_direct_relations`, `_d3fend_relations_as_derived`),
`src/knowledge_deception.py` (`load_deception_catalog`,
`load_attack_deception_mapping`, `to_sp1_mapping`),
`data/deception/deception_catalog.json`,
`data/deception/attack_deception_mapping.json`.

**D. Entrées.** Staging déjà versionné et testé :
`d3fend_deception_seed_1.5.0.json` (11 concepts D3FEND, dont 9 feuilles),
`d3fend_attack_mapping_seed_1.5.0.json` (140 relations D3FEND↔ATT&CK
brutes), `engage_activity_seed_1.0.json` (31 activités MITRE Engage),
`engage_attack_mapping_seed_1.0.json` (792 relations Engage↔ATT&CK
officielles, `origin: "mitre_engage_v1.0"`), `literature_evidence_seed_1.2.json`
(18 passages, 13 documents).

**E. Traitement algorithmique exact (extension).**
1. D3FEND étendu : pour les 6 feuilles sans relation ATT&CK tracée,
   `interaction_mechanism` est construit par CITATION EXACTE d'une phrase
   du kb-article (« How it works »), jamais une paraphrase libre —
   `possible_placements` dérivé de `target_artifacts` via une table
   étendue (`d3f:User→account`, `d3f:SessionToken→session_store`,
   `d3f:LocalAreaNetwork`/`d3f:IntranetNetwork→network_segment`).
2. MITRE Engage : 15 des 23 activités « Engagement » retenues (celles
   décrivant une action/ressource perçue par l'attaquant, pas du
   monitoring/de l'analyse/un contrôle de sécurité opérationnelle) ; les
   8 activités « Strategic » sont toutes exclues (planification, jamais
   déployable) ; `EAC0012` (Personas) fusionné dans `D3-DP` (§8,
   anti-duplication) plutôt que dupliqué. Décision INCLUDE/MERGE/EXCLUDE
   pour chacune des 31 activités documentée dans `CATALOG_AUDIT.md`.
3. Littérature : `LIT-HONEYPOT` (Provos 2004, Spitzner 2003,
   Ferguson-Walter et al. 2021) et `LIT-HONEYTOKEN` (Kahlhofer et al.
   2024) — deux concepts établis et distincts par granularité des
   mécanismes D3FEND déjà catalogués (§6 de l'audit).
4. `required_services` grounded pour 2 mécanismes Engage (`EAC0009`,
   `EAC0021` → `["email"]`), citation exacte d'une phrase factuelle du
   `long_description` (infrastructure de messagerie), même discipline que
   `D3-DNR.required_asset_types` — les 24 autres mécanismes gardent des
   listes `required_*` vides (`undetermined`, jamais fabriqué).
5. Mapping étendu : relations D3FEND (v1) marquées `mapping_type:
   "derived"` (inférence SPARQL par artefact partagé) ; nouvelles
   relations Engage marquées `mapping_type: "direct"` (matrice MITRE
   Engage officielle, filtrée sur les 15 `mechanism_id` retenus).

**F. Sorties.** `data/deception/deception_catalog.json`,
`data/deception/attack_deception_mapping.json`,
`docs/chapter4/ADMISSIBILITY_EVIDENCE_AUDIT.md`,
`docs/chapter4/CATALOG_AUDIT.md`,
`docs/chapter4/outputs/catalog_statistics.{json,txt}`.

**G. Technologies.** Python pur.

**H. Décisions techniques importantes.**
- `build_catalog()`/`build_mapping()` (v1) restent inchangées et testées
  — l'extension est additive (`build_expanded_catalog()`/
  `build_expanded_mapping()`), jamais une réécriture de la politique v1.
- Distinction « aucun prérequis » (`known_none`) vs « prérequis inconnu »
  (`unknown`) analysée explicitement pour les 26 mécanismes : seuls
  `D3-DNR`/`EAC0009`/`EAC0021` ont un cas `known_none` documenté — les 23
  autres restent `unknown` (liste vide → `undetermined`), jamais inventé.
- Granularité honeypot/honeynet explicitement justifiée (§6 de l'audit) :
  `LIT-HONEYPOT` (hôte/service leurre unique) ≠ `D3-DNR` (ressource
  leurre sur un actif réel) ≠ `D3-CHN`/`D3-SHN`/`D3-IHN` (environnement
  réseau de leurres) — complémentaires, pas des doublons.

**I. Écart modèle↔implémentation.** Le chapitre 3 (§9) décrit la
construction de la KB déception comme un pipeline en 8 étapes génériques
sans préciser de critère de sélection concret. L'implémentation ajoute un
critère opérationnel explicite et documenté (§6 de la tâche : mécanisme
déployable + description précise + preuve + target_artifact/placement/
interaction_mechanism + non abstrait) pour décider QUELS concepts/activités
deviennent des mécanismes — choix technique nécessaire, à assumer
explicitement dans la rédaction.

**J. Limites réelles.** 8 des 26 mécanismes (les 6 D3FEND étendus +
2 littérature) n'ont encore aucune relation `M_{i,d}` tracée — aucun
staging disponible ne l'établit, aucune relation n'a été fabriquée pour
combler ce vide (limite documentée, `catalog_statistics.json`). Seuls 3
mécanismes sur 26 ont un `required_*` documenté (`D3-DNR`, `EAC0009`,
`EAC0021`).

**K. Artefact/capture.** C2 (`AVAILABLE`, à régénérer pour refléter le
catalogue étendu) —
`docs/chapter4/screenshots/02_knowledge/deception_mechanism.png`,
généré par `tools/chapter4_figures/c2_mechanism.py`.

**L. Formulation à ne pas utiliser.** Ne pas écrire « le catalogue de
cyberdéception couvre l'ensemble des mécanismes documentés par D3FEND et
MITRE Engage » — 26 mécanismes réels sur un total bien plus grand
(D3FEND/Engage documentent des dizaines de techniques hors du périmètre
« Deceive »/« Engagement » retenu). Ne pas écrire « les prérequis de
placement ont été extraits automatiquement par NLP/LLM » — extraction par
relecture humaine (assistée) systématique et citation exacte, avec
décision explicite INCLUDE/MERGE/EXCLUDE par mécanisme, jamais une
extraction automatique. Ne pas écrire « toutes les relations M_{i,d} sont
officiellement établies par MITRE » — 127 des 591 relations sont
DÉRIVÉES (inférence SPARQL par artefact partagé), pas des relations
officielles.

---

## 4.4 Mise en œuvre des modules

### 4.4.1 SP1

**A. Objectif.** Construire `D_i` → `L_{i,h,d}` → `C_{i,h}` de façon
déterministe et diagnostique (pas un simple booléen).

**B. Réellement implémenté.** Diagnostic complet par candidat
(`mapping`, `Autorise`, `PrerequisSatisfaits`, `Pertinent`, chacun
`pass`/`fail`/`undetermined`/`not_evaluated`). Deux instances réelles
publiées, sur le catalogue et le mapping étendus (26 mécanismes, 591
relations) :
- `examples/sp1_real_example.py` (petite instance, 2 occurrences, 2
  emplacements, inchangée) : **1 candidat admissible**
  (`T1039@FS01`/`D3-DNR`/`shared-drive`).
- `examples/sp1_extended_real_example.py` (**réf. tâche « SP1 riche »**,
  10 occurrences, 6 actifs, 13 emplacements, scénario cohérent
  hameçonnage/exploitation → compromission d'identifiants → exécution →
  découverte/collecte divergente → exfiltration terminale convergente) :
  **4 candidats réellement admissibles** sur 3042 candidats bruts,
  couvrant **3 mécanismes distincts** (`D3-DNR`, `EAC0009`, `EAC0021`)
  sur **2 occurrences** (`T1566@WS01`, `T1039@FS01`).

**C. Fichiers/classes/fonctions.** `src/admissibility.py`
(`evaluate_allowed`, `evaluate_requirements_satisfied`,
`evaluate_relevant`, `build_admissibility_report`),
`examples/sp1_real_example.py`, `examples/sp1_extended_real_example.py`.

**D. Entrées.** `SystemInstance` validée, catalogue
`dict[str, DeceptionMechanism]` (réel, 26 mécanismes), mapping M_{i,d}
`dict[str, list[str]]` (réel, réduit de 591 relations), seuils
`theta_c`/`theta_i`/`theta_a`.

**E. Traitement algorithmique exact.** Pour chaque occurrence non
terminale × chaque mécanisme du catalogue × chaque emplacement du SI :
1. `mapping` : `mechanism.id ∈ D_i` (issu de `M_{i,d}`) ? Sinon
   court-circuit (`not_evaluated` pour les 3 critères suivants).
2. `Autorise` : `location.location_type ∈ mechanism.admissibility_profile.allowed_location_types` ;
   liste vide → `undetermined`.
3. `PrerequisSatisfaits` : `asset.asset_type ∈ required_asset_types`
   (+ services/artifacts si renseignés) ; si les trois listes requises
   sont vides → `undetermined` (jamais `pass` par défaut) ; sinon évalué
   réellement `pass`/`fail`.
4. `Pertinent` : relation topologique directe (même actif, ou arête à un
   saut).
5. `admissible = (Autorise="pass") ∧ (PrerequisSatisfaits="pass") ∧ (Pertinent="pass")`.

**F. Sorties.** Rapport structuré : par occurrence, `D_i`, `candidates`
(diagnostic complet par couple), `C_{i,h}`, résumé (`candidate_count`,
`admissible_count`, `rejected_count`).

**G. Technologies.** Python pur.

**H. Décisions techniques importantes.** Politique prudente (OPEN_DECISION
4) : une liste de prérequis vide n'est JAMAIS traitée comme « aucun
prérequis » — toujours `undetermined`, exclusion par défaut. **Analyse de
la cause racine (réf. tâche « si un seul candidat admissible, analyser la
cause, ne pas relâcher SP1 »)** : avant cette passe, seul `D3-DNR`
disposait d'un `required_asset_types` documenté — AUCUN autre mécanisme
ne pouvait structurellement jamais devenir admissible, quelle que soit la
richesse de l'instance. Ce n'était donc pas un manque de richesse
d'instance, mais un manque de preuve documentaire de prérequis. Après
relecture ciblée (section 4.3.3), 2 mécanismes supplémentaires
(`EAC0009`, `EAC0021`) ont un `required_services` documenté — portant à 3
sur 26 le nombre de mécanismes pouvant réellement atteindre
`PrerequisSatisfaits = "pass"`. C'est cette limite structurelle,
combinée à l'audit documentaire, qui explique pourquoi 3038 des 3042
candidats bruts de l'instance étendue restent rejetés malgré `Autorise`/
`Pertinent` passant pour beaucoup d'entre eux.

**I. Écart modèle↔implémentation.** Le chapitre 3 (§10.4) laisse
`RequirementsSatisfied(d,ℓ)` comme une fonction booléenne abstraite sans
préciser le traitement d'une information manquante. L'implémentation
comble cet écart par un troisième état explicite (`undetermined`,
OPEN_DECISION 4) — une décision d'implémentation nécessaire, documentée,
pas une invention du modèle.

**J. Limites réelles.** `Pertinent` simplifié à une relation topologique
directe (pas une analyse complète des chemins vers les nœuds terminaux,
que §10.4 permettrait en principe). `C_{i,h}` reste vide pour 23 des 26
mécanismes du catalogue étendu (aucun `required_*` documenté pour eux) —
limite documentée, pas masquée.

**K. Artefact/capture.** C3 (`AVAILABLE`, à régénérer pour l'instance
étendue) — `docs/chapter4/screenshots/03_sp1/sp1_real_result.png`,
généré par `tools/chapter4_figures/c3_sp1.py` depuis
`docs/chapter4/outputs/sp1_extended_real_example.json`/`.txt`.

**L. Formulation à ne pas utiliser.** Ne pas écrire « SP1 sélectionne le
meilleur mécanisme » — SP1 ne classe ni ne sélectionne, il filtre
uniquement l'admissibilité (rôle de l'optimiseur, section 4.4.4). Ne pas
écrire « le catalogue étendu permet de couvrir la majorité des scénarios
d'attaque » — 4 candidats admissibles sur l'instance riche testée, avec
un catalogue de 26 mécanismes dont seulement 3 ont un prérequis
d'admissibilité documenté.

### 4.4.2 SP2 — RAG + LLM

**A. Objectif.** Récupérer des preuves documentaires pertinentes (RAG)
et produire les 11 sous-métriques annotées pour un candidat admissible.

**B. Réellement implémenté.** **RAG à deux moteurs**, réf. tâche
« remplacer le TF-IDF par un vrai RAG sémantique » : `SemanticRagIndex`
(embeddings `sentence-transformers`, index vectoriel FAISS/NumPy) est
désormais le **moteur principal** ; `RagIndex` (TF-IDF haché) reste une
**baseline lexicale expérimentale**, comparée quantitativement (voir E).
`retrieve_hybrid` (fusion alpha-pondérée) existe et est le mode RETENU
pour la relecture finale (alpha=0.8, gain mesuré, réf. tâche §3).
Orchestrateur (`src/orchestrator.py::run_pipeline`) dispatché sur les
trois moteurs sans casser la compatibilité des runs lexicaux existants.
Annotation : repli déterministe `RuleBasedStubAnnotator` (opérationnel,
testé) ET provider LLM réel `RealLlmAnnotator` (Ollama local ou endpoint
OpenAI-compatible — code implémenté et testé par mocks HTTP ; statut
d'exécution réelle : voir note de clôture). Le candidat annoté par
`examples/annotator_llm_real_example.py` est récupéré directement depuis
la sortie réelle de SP1 — plus aucun candidat codé manuellement dans
cette chaîne.

**C. Fichiers/classes/fonctions.** `src/rag_indexer.py`
(`load_d3fend_chunks`/`load_engage_chunks`/`load_literature_chunks`,
`build_index`/`embed_text` [TF-IDF, baseline], `build_semantic_index`/
`embed_query_semantic` [sémantique, principal]), `src/semantic_embedder.py`
(`load_embedder`, `SentenceTransformerEmbedder`), `src/vector_index.py`
(`build_vector_index`, `search_vector_index`, FAISS/NumPy),
`src/rag_retriever.py` (`retrieve` [lexical], `retrieve_semantic`
[sémantique], `retrieve_hybrid` [fusion], `cosine_similarity`,
`to_deception_evidence`), `examples/rag_semantic_evaluation.py`
(évaluation Recall@5/MRR@5/nDCG@5), `src/llm_provider.py`
(`LlmProviderConfig`, `call_ollama`, `call_openai_compatible`),
`src/annotator_llm.py` (`RuleBasedStubAnnotator`, `RealLlmAnnotator`,
`detect_provider`, `AnnotationCache`), `examples/annotator_llm_real_example.py`.

**D. Entrées (RAG).** Documents staging déjà versionnés (D3FEND, Engage,
littérature). **Entrées (LLM).** `AnnotationContext` (occurrence,
mécanisme, emplacement, contexte graphe, preuves RAG — **jamais** le
budget).

**E. Traitement algorithmique exact.**
- RAG lexical (baseline) : chunking tracé → vecteur TF-IDF haché (256
  dimensions, mots-outils exclus, normalisation L2) → similarité cosinus,
  top-k.
- RAG sémantique (principal) : chunking tracé (identique) → embedding
  `sentence-transformers` (modèle configurable `RAG_EMBEDDING_MODEL`,
  défaut `BAAI/bge-small-en-v1.5`, dimension 384, repli documenté
  `all-MiniLM-L6-v2` si le modèle préféré est indisponible) → normalisation
  L2 → index vectoriel FAISS `IndexFlatIP` (produit scalaire normalisé =
  cosinus ; repli NumPy pur si FAISS n'est pas installable) → top-k.
  Évaluation réelle sur 17 requêtes à vérité terrain relue humainement
  (`data/rag/rag_eval_queries.json`) contre les 124 chunks réels : Recall@5
  = 0.396 (sémantique) vs 0.331 (lexical), MRR@5 = 0.578 vs 0.522, nDCG@5 =
  0.400 vs 0.342 — gain mesuré, jamais supposé
  (`docs/chapter4/outputs/rag_semantic_evaluation.json`).
- RAG hybride : `score = alpha·score_sémantique + (1-alpha)·score_lexical`
  — alpha testé parmi {0.5, 0.7, 0.8, 0.9}, retenu à 0.8 (Recall@5=0.470,
  meilleur que le sémantique seul) : implémenté UNIQUEMENT parce que
  l'évaluation démontre ce gain réel (réf. tâche §3), pas un choix
  arbitraire.
- LLM réel : construction du prompt (JSON structuré demandé, 11
  sous-métriques exactement, `evidence_ids` limités aux preuves
  réellement fournies) → `POST {base_url}/api/chat` (Ollama) ou
  `/chat/completions` (OpenAI-compatible), `temperature=0` → parsing
  strict de la réponse → validation (11 métriques exactement, sans
  doublon, scores/confiances `[0,1]`, `evidence_ids` référençant
  réellement les preuves fournies) → `LlmOutputValidationError` sur toute
  non-conformité, jamais une valeur de repli.
- `detect_provider()` : CAS A (Ollama, sondage `/api/tags`) / CAS B
  (endpoint OpenAI-compatible configuré) / CAS C (repli déterministe).

**F. Sorties.** RAG : `RetrievalResult` (chunk + score). LLM : 11
`Annotation` (score, confiance, justification, `evidence_ids`,
`model_version`, `annotation_id`).

**G. Technologies.** `sentence-transformers` + FAISS (moteur RAG
principal, embeddings sémantiques réels) ; TF-IDF haché (`hashlib.blake2b`,
baseline lexicale expérimentale, aucune dépendance) ; `urllib.request`
pour l'appel LLM réel.

**H. Décisions techniques importantes.** Le prompt exclut explicitement
`system_context` (protection anti-budget supplémentaire, au-delà de la
validation Pydantic déjà en place). Aucun modèle LLM n'est imposé dans le
code — sélection entièrement par variables d'environnement.

**I. Écart modèle↔implémentation.** Le chapitre 3 (§11) définit le
LLM+RAG comme une boîte conceptuelle produisant 11 scores annotés, sans
préciser le mécanisme concret de récupération documentaire ni le format
d'échange avec le modèle. L'implémentation matérialise ce vide par un
choix technique explicite (TF-IDF haché, prompt JSON structuré,
validation stricte) — techniquement nécessaire, scientifiquement neutre
(n'affecte aucune formule du chapitre 3), à présenter comme tel.

**J. Limites réelles.** **Aucune annotation sémantique réelle n'a été
produite dans cet environnement** — le repli déterministe produit un
score identique pour les 11 sous-métriques (chevauchement lexical, pas
une distinction Realism/InteractionLikelihood/Effectiveness) ; le
provider réel n'a jamais été exercé contre un vrai service.

**K. Artefact/capture.** C4 (RAG, `AVAILABLE`) —
`docs/chapter4/screenshots/04_rag/rag_retrieval.png` (2050×1084 px,
généré par `tools/chapter4_figures/c4_rag.py`) ; C5 (LLM réel,
`NOT_AVAILABLE`).

**L. Formulation à ne pas utiliser.** Ne pas écrire « le système utilise
un modèle de langage pour analyser sémantiquement les techniques
d'attaque » sans préciser le statut réel de l'exécution LLM (voir note de
clôture). Ne pas écrire « le RAG utilise uniquement du TF-IDF » — c'est
désormais FAUX : le TF-IDF haché est une baseline lexicale expérimentale,
le moteur principal est un RAG sémantique réel (`sentence-transformers` +
FAISS), démontré supérieur par une évaluation quantitative réelle (pas
seulement affirmé). Ne pas présenter les scores du repli déterministe
(`RuleBasedStubAnnotator`) comme le résultat d'une annotation sémantique
LLM réelle.

### 4.4.3 SP3

**A. Objectif.** Propager `Gamma → P^e → A → P → I → R` sur le graphe
d'attaque (convergence noisy-OR, divergence `π`).

**B. Réellement implémenté.** Propagation complète, topologiquement
triée, avec **ancre de validation `test_reference_example` reproduisant
exactement** les valeurs cibles du chapitre 3 (`DE=0.429`,
`Gamma_1003=0.571`, réduction 42.9 %, tolérance `1e-3`).

**C. Fichiers/classes/fonctions.** `src/risk_engine.py`
(`compute_gamma`, `compute_transmitted_edge_probability`,
`compute_reachability`, `compute_propagated_success_probability`,
`compute_aggregated_impact`, `compute_risk`, `propagate_risk`).

**D. Entrées.** `AttackGraph` validé, `q`/`I`/`DE` par occurrence (`DE`
déjà figé, jamais recalculé ici).

**E. Traitement algorithmique exact.** Tri topologique (NetworkX) ; par
occurrence : `Gamma = 1 - DE` ; nœud d'entrée ⇒ `A=1` ; sinon,
agrégation noisy-OR des `P^e` de chaque parent
(`P^e = P_parent × Gamma_parent × π`, `π` uniquement en divergence — issu
de l'arête ou `1/|enfants|` par défaut) ; `P = A×q` ; `R = P×I`.

**F. Sorties.** `dict[occurrence_id, {Gamma, A, P, I, R, DE, q}]`.

**G. Technologies.** Python pur + NetworkX (tri topologique).

**H. Décisions techniques importantes.** Aucune — traduction directe et
fidèle des formules §14.

**I. Écart modèle↔implémentation.** Aucun — c'est le module le plus
strictement fidèle au modèle mathématique, vérifié par un test de
non-régression numérique exact (tolérance `1e-3`).

**J. Limites réelles.** Ce module ne lit pas directement une table
d'annotations figée dans son exemple isolé (`de_by_occurrence` fourni par
l'appelant) — l'intégration complète existe dans l'orchestrateur (section
4.5.1).

**K. Artefact/capture.** Aucune dans C1–C7 (réservé au chapitre 5,
conformément à la consigne).

**L. Formulation à ne pas utiliser.** Ne pas écrire « le moteur de risque
a été validé sur un cas d'étude réel » — seul le scénario analytique de
référence du chapitre 3 (petit graphe synthétique) a été reproduit ; la
validation sur un cas réel complet appartient au chapitre 5.

### 4.4.4 Optimisation

**A. Objectif.** Résoudre `(P)` (unicité, budget, minimisation
multiobjectif des risques terminaux) et transformer `y*` en `Y*`.

**B. Réellement implémenté.** `Cost(d;H)` ; énumération exhaustive des
configurations ; front de Pareto ; sélection illustrative ; transformation
en rapport interprétable (`reporter.py`).

**C. Fichiers/classes/fonctions.** `src/cost_engine.py`
(`compute_cost_by_mechanism`), `src/optimizer.py`
(`enumerate_configurations`, `filter_by_budget`, `pareto_front`, `solve`),
`src/reporter.py` (`build_deployment_report`).

**D. Entrées.** `C_{i,h}` (SP1), `DE` figé (SP2), `Cost(d;H)`,
`B_total`.

**E. Traitement algorithmique exact.** Construction des candidats à
partir de `C_{i,h}` → énumération de toutes les configurations (« aucune
déception » + chaque candidat, par occurrence — unicité locale garantie
par construction) → filtrage budgétaire → évaluation SP3 par
configuration → front de Pareto (non-dominance) → sélection `y*` par
somme des risques terminaux sur le front (politique explicite et
illustrative) → `Y*` = liste de placements avec risque avant/après.

**F. Sorties.** `pareto.json`, `deployment_plan.json`,
`deployment_report.json`.

**G. Technologies.** Python pur — pas de solveur externe, pas
d'heuristique, pas d'algorithme génétique.

**H. Décisions techniques importantes.** Garde-fou explicite
(`max_configurations`) : refuse d'énumérer au-delà d'un seuil plutôt que
d'omettre silencieusement des configurations — pas une réduction
arbitraire de l'espace de décision (§24).

**I. Écart modèle↔implémentation.** Le chapitre 3 (§16) ne prescrit
aucune méthode de résolution particulière pour `(P)` — l'implémentation
choisit l'énumération exhaustive, explicitement justifiée pour les
« petites instances » de validation (§23), pas un solveur industriel. La
politique de sélection `y*` par somme des risques est une addition
explicite et documentée (§16 l'autorise si justifiée), PAS une formule du
chapitre 3.

**J. Limites réelles.** Réservé aux petites instances (pas dimensionné
pour un SI de grande taille) ; `risk_before`/`risk_after` d'une ligne
`Y*` portent sur le risque PROPRE de l'occurrence protégée — souvent
`variation=0` pour une occurrence non terminale, car `Gamma` agit sur la
transmission vers les enfants (§14.3), jamais sur `R` de l'occurrence
elle-même ; le risque terminal réel diminue, mais séparément (visible
dans `risks.json`).

**K. Artefact/capture.** Aucune dans C1–C7 (Pareto/`Y*` détaillé réservés
au chapitre 5).

**L. Formulation à ne pas utiliser.** Ne pas écrire « l'algorithme trouve
la solution optimale garantie » sans préciser « par énumération
exhaustive, sur une petite instance » — la garantie d'optimalité ne
s'étend pas à un espace de décision de grande taille (le module refuse
alors explicitement de s'exécuter). Ne pas écrire « un algorithme
génétique/heuristique a été implémenté » — faux, énumération exhaustive
uniquement. Ne pas écrire qu'une ligne `Y*` à `risk_variation=0` signifie
que le placement est inefficace — c'est un artefact de la définition de
`R_{i,h}` (risque propre de l'occurrence), pas une mesure de l'effet réel
du placement.

---

## 4.5 Orchestration et traçabilité

### 4.5.1 Enchaînement

**A. Objectif.** Point d'entrée unique enchaînant tous les modules.

**B. Réellement implémenté.** `run_pipeline` orchestre SP1 → RAG →
annotation (une seule fois par candidat) → gel → coût → `(P)` → risque
avant/après → rapport, avec sérialisation systématique.

**C. Fichiers/classes/fonctions.** `src/orchestrator.py` (`run_pipeline`),
`examples/orchestrator_example.py`.

**D. Entrées.** Instance, catalogue, mapping, index RAG, provider
d'annotation, paramètres de coût/budget/seuils.

**E. Traitement algorithmique exact.** Voir sections 4.4.1 à 4.4.4,
enchaînées dans cet ordre exact ; l'annotateur n'est jamais rappelé après
le gel (vérifié dynamiquement par comptage d'appels en test).

**F. Sorties.** `runs/<run_id>/{input_manifest,candidates,retrieval,
annotations_raw,annotations_frozen,costs,pareto,deployment_plan,
deployment_report,risks,run_manifest}.json` (10 fichiers).

**G. Technologies.** Python pur (`json`, `pathlib`, `dataclasses`).

**H. Décisions techniques importantes.** `runs/` non versionné
(régénérable) — la preuve d'exécution retenue est
`docs/chapter4/outputs/pipeline_example.txt`.

**I. Écart modèle↔implémentation.** N/A — pure orchestration technique,
aucune formule.

**J. Limites réelles.** Testé explicitement avec le catalogue et le
mapping réels (`C_{i,h}` restreint à 1 candidat) : le pipeline reste
robuste (`deployment_plan` non vide dans ce cas précis grâce à l'audit de
la section 4.3.3), mais l'exemple `orchestrator_example.py` par défaut
utilise encore un catalogue synthétique de démonstration distinct.

**K. Artefact/capture.** C7 (`AVAILABLE`) —
`docs/chapter4/screenshots/09_pipeline/pipeline_result.png` (2067×1654 px,
généré par `tools/chapter4_figures/c7_pipeline.py`).

**L. Formulation à ne pas utiliser.** Ne pas écrire « le pipeline exécute
les annotations en parallèle » — traitement strictement séquentiel, un
candidat à la fois.

### 4.5.2 Conservation des annotations et preuves

**A. Objectif.** Calculer PAR CODE (jamais par le LLM) les agrégats
`Realisme`/`P_interaction`/`P_engagement`/`Effet_prog`/`DE`, geler le
résultat, et conserver la chaîne de preuves.

**B. Réellement implémenté.** Validation de complétude (11 métriques,
sans doublon) ; agrégation par moyennes/produits (§12.3-§12.7) ; gel dans
une `FrozenAnnotationTable` immuable et versionnée ; **commande unique de
gel réel après une vraie exécution LLM**
(`examples/freeze_real_example.py`, produit
`frozen_annotations_real.json`/`.csv` à partir de
`llm_annotation_real.json` — refuse explicitement si ce dernier n'existe
pas).

**C. Fichiers/classes/fonctions.** `src/annotation_validator.py`
(`validate_candidate_annotations`, `compute_realisme`,
`compute_p_interaction`, `compute_effet_prog`, `compute_p_engagement`,
`compute_de`, `freeze_candidate`, `freeze_table`),
`examples/freeze_example.py` (repli déterministe),
`examples/freeze_real_example.py` (provider réel, une fois exécuté).

**D. Entrées.** 11 `Annotation` validées par candidat (repli ou provider
réel).

**E. Traitement algorithmique exact.**
`Realisme = moyenne(R_tech, R_context, R_perception, R_behavior)` ;
`P_interaction = moyenne(A_object, A_action, A_source)` ;
`P_engagement = Realisme × P_interaction` ;
`Effet_prog = moyenne(S_stop, S_redirect, S_contain, S_delay)` ;
`DE = P_engagement × Effet_prog` ; gel dans `FrozenAnnotation`
(`entries` en tuple, dataclass `frozen=True`).

**F. Sorties.** `FrozenAnnotationTable.de_by_candidate()` → pont direct
vers `src.optimizer.build_candidates_from_admissibility`.

**G. Technologies.** Python pur.

**H. Décisions techniques importantes.** Chaîne de traçabilité des
preuves entièrement câblée et testée : chunk RAG → `DeceptionEvidence` →
`Annotation.evidence` (vérifié contre les preuves réellement récupérées
pour le provider réel) → `FrozenAnnotation.evidence_ids` →
`DeploymentReportRow.evidence_ids`.

**I. Écart modèle↔implémentation.** Aucun — traduction directe de §12.3
à §12.7 et §13.

**J. Limites réelles.** L'exemple réel disponible
(`frozen_annotations_example.csv`) dépend du repli déterministe — les
FORMULES d'agrégation sont réelles, pas les scores sémantiques
sous-jacents. `frozen_annotations_real.*` n'existent pas encore (dépend
d'une exécution LLM réelle, non disponible ici).

**K. Artefact/capture.** C6 (`NOT_AVAILABLE`, dépend de C5).

**L. Formulation à ne pas utiliser.** Ne pas écrire « les 5 agrégats sont
calculés par le LLM » — ils sont calculés PAR CODE, exclusivement, à
partir des 11 scores bruts (LLM ou stub). Ne pas présenter
`frozen_annotations_example.csv` comme une table figée issue d'une
annotation LLM réelle.

---

## Table de traçabilité pour le mémoire

| Affirmation possible dans le chapitre 4 | Preuve dans le code | Preuve dans les données | Sortie reproductible | Capture | Statut |
|---|---|---|---|---|---|
| « SP1 construit `C_{i,h}` de manière déterministe » | `src/admissibility.py` | catalogue + mapping réels étendus | `sp1_extended_real_example.json` | C3 | **VALIDÉ** |
| « Le catalogue réel contient 26 mécanismes tracés depuis D3FEND/Engage/littérature » | `tools/deception_kb/catalog_builder.py::build_expanded_catalog` | `deception_catalog.json` | `python -c "from tools.deception_kb.catalog_builder import *; write_catalog(build_expanded_catalog())"` | C2 | **VALIDÉ** |
| « Le mapping `M_{i,d}` réel comporte 591 relations (464 directes + 127 dérivées) tracées » | `tools/deception_kb/mapping_builder.py::build_expanded_mapping` | `attack_deception_mapping.json` | `python -c "from tools.deception_kb.mapping_builder import *; write_mapping(build_expanded_mapping())"` | — | **VALIDÉ** |
| « Un audit documentaire a permis d'enrichir des propriétés d'admissibilité sans en inventer » | `catalog_builder.py` (`ADDITIONAL_LOCATION_TYPES`, `REQUIRED_ASSET_TYPES`, `ENGAGE_REQUIRED_SERVICES`) | `ADMISSIBILITY_EVIDENCE_AUDIT.md`, `CATALOG_AUDIT.md` §6bis | régénération du catalogue | C2 | **VALIDÉ** |
| « Plusieurs candidats sont réellement admissibles sur une instance riche avec le catalogue et le mapping étendus » | `src/admissibility.py` | `sp1_extended_real_example.json` | `python -m examples.sp1_extended_real_example` | C3 | **VALIDÉ** (4 candidats, 3 mécanismes distincts : `D3-DNR`, `EAC0009`, `EAC0021`) |
| « Le RAG sémantique (embeddings) récupère des passages D3FEND/Engage/littérature, avec un Recall@5 supérieur au RAG lexical » | `src/semantic_embedder.py`/`src/vector_index.py`/`src/rag_indexer.py`/`src/rag_retriever.py` | staging (124 chunks), 17 requêtes réelles (`data/rag/rag_eval_queries.json`) | `rag_semantic_evaluation.json` | C4 | **VALIDÉ** (Recall@5 sémantique 0.396 > lexical 0.331 ; hybride alpha=0.8 : 0.470) |
| « Le LLM réel produit les 11 sous-métriques » | `RealLlmAnnotator` | preuves RAG | `llm_annotation_real.json` | C5 | **NON VALIDÉ** — code prêt et testé (mocks), aucune exécution réelle dans cet environnement |
| « Le repli déterministe produit les 11 sous-métriques sans LLM réel » | `RuleBasedStubAnnotator` | preuves RAG | `llm_annotation_example.json` | — | **VALIDÉ** (explicitement marqué `rule_based_stub`) |
| « Les agrégats `Realisme`/`P_interaction`/`P_engagement`/`Effet_prog`/`DE` sont calculés par code, jamais par le LLM » | `src/annotation_validator.py` | 11 `Annotation` (stub ou réel) | `frozen_annotations_example.csv` | C6 (stub) | **VALIDÉ** (formules) ; table figée à partir d'un LLM réel **NON VALIDÉE** |
| « Le moteur SP3 reproduit exactement l'ancre de validation du chapitre 3 » | `src/risk_engine.py` | scénario analytique CLAUDE.md §20 | `test_reference_example` | — (chapitre 5) | **VALIDÉ** (tolérance `1e-3`) |
| « L'optimiseur résout `(P)` par énumération exhaustive avec front de Pareto » | `src/optimizer.py` | `C_{i,h}` + coûts | `optimizer_example.txt` | — (chapitre 5) | **VALIDÉ** |
| « L'orchestrateur exécute le pipeline complet de bout en bout » | `src/orchestrator.py` | catalogue/mapping réels + RAG réel | `pipeline_example.txt` | C7 | **VALIDÉ** (avec repli déterministe, pas de LLM réel) |
| « Aucun appel LLM ni aucune dépendance RAG n'a lieu pendant le calcul du risque ou l'optimisation » | tests `ast` dédiés sur `risk_engine.py`/`optimizer.py`/`reporter.py` (incluant `semantic_embedder.py`/`vector_index.py` depuis cette passe) | — | `pytest -v` (664 tests + 2 optionnels `real_llm`) | — | **VALIDÉ** |

---

## Note de clôture

Cette passe ferme la rupture identifiée dans la chaîne
catalogue→mapping→SP1→candidat admissible→RAG→LLM : un candidat
réellement admissible existe désormais (`T1039@FS01`/`D3-DNR`/`shared-drive`),
obtenu par audit documentaire rigoureux (2 propriétés retenues, une
dizaine rejetées comme non justifiées — voir
`ADMISSIBILITY_EVIDENCE_AUDIT.md`), sans jamais assouplir la politique
d'admissibilité ni inventer de prérequis. La seule rupture restante est
l'absence d'un service LLM réel dans cet environnement d'exécution — le
code, la validation stricte de sortie, et la commande de reproduction
locale sont tous prêts et testés (588 tests verts).
