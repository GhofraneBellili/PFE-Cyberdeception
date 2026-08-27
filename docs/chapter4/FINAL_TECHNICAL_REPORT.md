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
> État au moment de la rédaction : 588 tests verts, catalogue réel de 3
> mécanismes, mapping réel de 127 relations, **1 candidat réellement
> admissible** (`T1039@FS01`/`D3-DNR`/`shared-drive`, obtenu après audit
> documentaire des prérequis — voir
> `docs/chapter4/ADMISSIBILITY_EVIDENCE_AUDIT.md`), aucune exécution LLM
> réelle dans cet environnement (code prêt et testé).

---

## 4.1 Environnement technique

### 4.1.1 Technologies utilisées

**A. Objectif.** Documenter les technologies réellement présentes dans
le dépôt.

**B. Réellement implémenté.** Python ≥ 3.11, Pydantic 2.x, NetworkX 3.x,
pytest ≥ 8.0 (dépendances déclarées) ; `urllib.request` (bibliothèque
standard) pour l'appel HTTP au provider LLM réel.

**C. Fichiers.** `pyproject.toml`, `docs/chapter4/TECHNOLOGIES.md`.

**D. Entrées.** N/A.

**E. Traitement.** N/A (inventaire, pas un calcul).

**F. Sorties.** Tableau de dépendances.

**G. Technologies.** Voir B.

**H. Décisions techniques importantes.** Choix explicite de ne PAS
ajouter `requests` (bibliothèque tierce) pour l'appel HTTP LLM —
`urllib.request` suffit ; choix explicite de ne PAS utiliser de base
vectorielle externe (FAISS/Chroma) pour le RAG — un index en mémoire et
une vectorisation TF-IDF hachée suffisent à l'échelle du prototype.

**I. Écart modèle↔implémentation.** N/A — pas de formalisation
mathématique associée à cette sous-section.

**J. Limites réelles.** Aucune bibliothèque d'embeddings sémantiques ;
aucun solveur d'optimisation externe.

**K. Artefact/capture.** Aucun (tableau textuel dans
`docs/chapter4/TECHNOLOGIES.md`).

**L. Formulation à ne pas utiliser.** Ne pas écrire « le système utilise
une architecture microservices » ou « une base de données vectorielle »
— faux, aucun des deux n'est présent.

### 4.1.2 Organisation du projet

**A. Objectif.** Présenter la structure réelle du dépôt.

**B. Réellement implémenté.** Arborescence complète et stable :
`src/` (15 modules), `tools/deception_kb/` (couche offline), `data/deception/`
(staging + catalogue + mapping réels), `examples/` (16 scripts
exécutables), `tests/` (588 tests), `docs/chapter4/` (ce document +
IMPLEMENTATION_REPORT.md + TECHNOLOGIES.md + SCREENSHOT_MANIFEST.md +
ADMISSIBILITY_EVIDENCE_AUDIT.md + outputs/ + screenshots/), `runs/`
(sorties d'exécution, non versionnées).

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

**K. Artefact/capture.** C1 (`READY_FOR_SCREENSHOT`).

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

**J. Limites réelles.** Le catalogue réel actuel (3 mécanismes) limite la
portée des exemples de bout en bout — la chaîne fonctionne, mais sur un
espace de décision très restreint (voir section 4.3.3/4.4.1).

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

**B. Réellement implémenté.** Catalogue réel de **3 mécanismes**
(`D3-DF`, `D3-DUC`, `D3-DNR`) construit depuis le staging D3FEND 1.5.0
déjà versionné ; mapping réel de **127 relations**
`(attack_id, mechanism_id)` (→ 125 techniques ATT&CK distinctes) ;
**audit documentaire systématique des prérequis d'admissibilité**
(`docs/chapter4/ADMISSIBILITY_EVIDENCE_AUDIT.md`), ayant abouti à deux
enrichissements évidence-based : `D3-DF.allowed_location_types` +=
`"network_share"` et `D3-DNR.required_asset_types` =
`["web_application_server", "file_server"]`.

**C. Fichiers/classes/fonctions.**
`tools/deception_kb/catalog_builder.py` (`build_catalog`,
`ARTIFACT_TO_LOCATION_TYPE`, `ADDITIONAL_LOCATION_TYPES`,
`REQUIRED_ASSET_TYPES`), `tools/deception_kb/mapping_builder.py`
(`build_mapping`), `src/knowledge_deception.py`
(`load_deception_catalog`, `load_attack_deception_mapping`,
`to_sp1_mapping`), `data/deception/deception_catalog.json`,
`data/deception/attack_deception_mapping.json`.

**D. Entrées.** Staging déjà versionné et testé :
`d3fend_deception_seed_1.5.0.json` (11 concepts D3FEND, dont 9 feuilles),
`d3fend_attack_mapping_seed_1.5.0.json` (140 relations D3FEND↔ATT&CK
brutes).

**E. Traitement algorithmique exact.**
1. Filtrage : un concept devient un mécanisme du catalogue SEULEMENT s'il
   est une feuille (`is_leaf=True`) ET possède au moins une relation
   ATT&CK directe dans le staging (nécessaire pour renseigner
   `interaction_mechanism`, champ requis, sans l'inventer) — 3 des 9
   feuilles satisfont ces deux conditions.
2. `interaction_mechanism` = liste triée des `off_artifact_relation`
   observés pour ce concept (lecture directe, pas une interprétation).
3. `admissibility_profile.allowed_location_types` = dérivé de
   `target_artifacts` via une table de correspondance fixe
   (`d3f:File→filesystem`, `d3f:Credential→credential_store`,
   `d3f:NetworkResource→network_resource`), complété pour `D3-DF` par
   `network_share` (preuve : kb-article, « made available as a local or
   network resource »).
4. `admissibility_profile.required_asset_types` = vide par défaut,
   complété pour `D3-DNR` par `["web_application_server", "file_server"]`
   (preuve : kb-article, « deployed to web application servers, network
   file shares... », section factuelle « How it works », pas une
   recommandation).
5. Mapping `M_{i,d}` : filtrage des 140 relations brutes sur les 3
   `mechanism_id` du catalogue final → 127 relations retenues, chacune
   avec sa provenance complète (`relation_path`, `source`,
   `source_sha256`) ; les paires dupliquées dans le staging brut (12 cas)
   conservent toutes leurs preuves, jamais fusionnées.

**F. Sorties.** `data/deception/deception_catalog.json`,
`data/deception/attack_deception_mapping.json`,
`docs/chapter4/ADMISSIBILITY_EVIDENCE_AUDIT.md`.

**G. Technologies.** Python pur.

**H. Décisions techniques importantes.**
- Périmètre v1 volontairement restreint : les 6 autres feuilles D3FEND
  et les 792 relations MITRE Engage↔ATT&CK sont explicitement exclues
  (raison tracée dans `excluded_concepts` du catalogue), faute de preuve
  suffisante ou par cohérence avec l'OPEN_DECISION existante interdisant
  le rapprochement automatique D3FEND/Engage.
- Distinction « aucun prérequis » (`known_none`) vs « prérequis inconnu »
  (`unknown`) analysée explicitement : **aucun cas `known_none` trouvé**
  parmi les 3 mécanismes — la représentation actuelle (liste vide →
  `undetermined`) reste donc sémantiquement correcte pour les données
  disponibles ; aucun nouveau champ de statut introduit (décision
  documentée, pas une omission).
- La valeur retenue pour `D3-DNR.required_asset_types` porte une réserve
  documentée : la phrase source se termine par « or other network based
  sharing services » (clause ouverte, non encodée).

**I. Écart modèle↔implémentation.** Le chapitre 3 (§9) décrit la
construction de la KB déception comme un pipeline en 8 étapes génériques
(collecte, extraction, normalisation, structuration, enrichissement,
traçabilité, indexation RAG, versionnage) sans préciser de critère de
sélection concret. L'implémentation ajoute un critère opérationnel
explicite et documenté (feuille + relation ATT&CK directe) pour décider
QUELS concepts deviennent des mécanismes — un choix technique nécessaire
non spécifié par le modèle, à assumer explicitement dans la rédaction.

**J. Limites réelles.** Catalogue non exhaustif (3 mécanismes sur les 9
feuilles D3FEND, 0 sur Engage) ; `required_services`/`required_artifacts`
vides pour les 3 mécanismes (aucune preuve trouvée) ; `required_asset_types`
vide pour `D3-DF`/`D3-DUC`.

**K. Artefact/capture.** C2 (`READY_FOR_SCREENSHOT`).

**L. Formulation à ne pas utiliser.** Ne pas écrire « le catalogue de
cyberdéception couvre l'ensemble des mécanismes documentés par D3FEND et
MITRE Engage » — faux, 3 mécanismes D3FEND seulement, Engage totalement
exclu. Ne pas écrire « les prérequis de placement ont été extraits
automatiquement par NLP/LLM » — l'audit a été fait par lecture humaine
(assistée) systématique, avec décision explicite RETENUE/REJETÉE par
propriété, pas une extraction automatique.

---

## 4.4 Mise en œuvre des modules

### 4.4.1 SP1

**A. Objectif.** Construire `D_i` → `L_{i,h,d}` → `C_{i,h}` de façon
déterministe et diagnostique (pas un simple booléen).

**B. Réellement implémenté.** Diagnostic complet par candidat
(`mapping`, `Autorise`, `PrerequisSatisfaits`, `Pertinent`, chacun
`pass`/`fail`/`undetermined`/`not_evaluated`) ; **avec le catalogue et le
mapping réels (après audit), exactement 1 candidat est réellement
admissible** sur 12 candidats bruts testés dans l'exemple de référence :
`T1039@FS01` / `D3-DNR` / `shared-drive`.

**C. Fichiers/classes/fonctions.** `src/admissibility.py`
(`evaluate_allowed`, `evaluate_requirements_satisfied`,
`evaluate_relevant`, `build_admissibility_report`),
`examples/sp1_real_example.py`.

**D. Entrées.** `SystemInstance` validée, catalogue
`dict[str, DeceptionMechanism]` (réel, 3 mécanismes), mapping M_{i,d}
`dict[str, list[str]]` (réel, réduit de 127 relations), seuils
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
prérequis » — toujours `undetermined`, exclusion par défaut. C'est cette
politique, combinée à l'audit documentaire (section 4.3.3), qui explique
pourquoi 11 des 12 candidats bruts restent rejetés malgré `Autorise`/
`Pertinent` passant pour certains d'entre eux.

**I. Écart modèle↔implémentation.** Le chapitre 3 (§10.4) laisse
`RequirementsSatisfied(d,ℓ)` comme une fonction booléenne abstraite sans
préciser le traitement d'une information manquante. L'implémentation
comble cet écart par un troisième état explicite (`undetermined`,
OPEN_DECISION 4) — une décision d'implémentation nécessaire, documentée,
pas une invention du modèle.

**J. Limites réelles.** `Pertinent` simplifié à une relation topologique
directe (pas une analyse complète des chemins vers les nœuds terminaux,
que §10.4 permettrait en principe). `C_{i,h}` reste vide pour `D3-DF` et
`D3-DUC` avec le catalogue réel actuel.

**K. Artefact/capture.** C3 (`READY_FOR_SCREENSHOT`) —
`docs/chapter4/outputs/sp1_real_example.json`/`.txt`.

**L. Formulation à ne pas utiliser.** Ne pas écrire « SP1 sélectionne le
meilleur mécanisme » — SP1 ne classe ni ne sélectionne, il filtre
uniquement l'admissibilité (rôle de l'optimiseur, section 4.4.4). Ne pas
écrire « le catalogue réel permet de couvrir la majorité des scénarios
d'attaque » — un seul candidat admissible sur l'exemple testé, avec un
catalogue de 3 mécanismes seulement.

### 4.4.2 SP2 — RAG + LLM

**A. Objectif.** Récupérer des preuves documentaires pertinentes (RAG)
et produire les 11 sous-métriques annotées pour un candidat admissible.

**B. Réellement implémenté.** RAG opérationnel sur un corpus réel de 124
chunks (D3FEND/Engage/littérature). Annotation : repli déterministe
`RuleBasedStubAnnotator` (opérationnel, testé) ET provider LLM réel
`RealLlmAnnotator` (Ollama local ou endpoint OpenAI-compatible — code
implémenté et testé par mocks HTTP, **jamais exécuté contre un service
réel dans cet environnement**, faute de service disponible). Le candidat
annoté par `examples/annotator_llm_real_example.py` est désormais
récupéré directement depuis la sortie réelle de SP1 (section 4.4.1) —
plus aucun candidat codé manuellement dans cette chaîne.

**C. Fichiers/classes/fonctions.** `src/rag_indexer.py`
(`load_d3fend_chunks`/`load_engage_chunks`/`load_literature_chunks`,
`build_index`, `embed_text`), `src/rag_retriever.py` (`retrieve`,
`cosine_similarity`, `to_deception_evidence`), `src/llm_provider.py`
(`LlmProviderConfig`, `call_ollama`, `call_openai_compatible`),
`src/annotator_llm.py` (`RuleBasedStubAnnotator`, `RealLlmAnnotator`,
`detect_provider`, `AnnotationCache`), `examples/annotator_llm_real_example.py`.

**D. Entrées (RAG).** Documents staging déjà versionnés (D3FEND, Engage,
littérature). **Entrées (LLM).** `AnnotationContext` (occurrence,
mécanisme, emplacement, contexte graphe, preuves RAG — **jamais** le
budget).

**E. Traitement algorithmique exact.**
- RAG : chunking tracé → vecteur TF-IDF haché (256 dimensions, mots-outils
  exclus, normalisation L2) → similarité cosinus, top-k.
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

**G. Technologies.** TF-IDF haché (`hashlib.blake2b`) — choix technique,
pas un embedding sémantique de modèle de langage ; `urllib.request` pour
l'appel LLM réel.

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

**K. Artefact/capture.** C4 (RAG, `READY_FOR_SCREENSHOT`) ; C5 (LLM réel,
`NOT_AVAILABLE`).

**L. Formulation à ne pas utiliser.** Ne pas écrire « le système utilise
un modèle de langage pour analyser sémantiquement les techniques
d'attaque » sans préciser qu'aucune exécution réelle n'a eu lieu dans cet
environnement. Ne pas écrire « le RAG utilise des embeddings
sémantiques » — c'est un vecteur TF-IDF haché, une technique de
recherche d'information classique, pas un modèle de langage. Ne pas
présenter les scores du repli déterministe comme le résultat d'une
annotation sémantique réelle.

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

**K. Artefact/capture.** C7 (`READY_FOR_SCREENSHOT`).

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
| « SP1 construit `C_{i,h}` de manière déterministe » | `src/admissibility.py` | catalogue + mapping réels | `sp1_real_example.json` | C3 | **VALIDÉ** |
| « Le catalogue réel contient 3 mécanismes tracés depuis D3FEND » | `tools/deception_kb/catalog_builder.py` | `deception_catalog.json` | `python -m tools.deception_kb.catalog_builder` | C2 | **VALIDÉ** |
| « Le mapping `M_{i,d}` réel comporte 127 relations tracées » | `tools/deception_kb/mapping_builder.py` | `attack_deception_mapping.json` | `python -m tools.deception_kb.mapping_builder` | — | **VALIDÉ** |
| « Un audit documentaire a permis d'enrichir 2 propriétés d'admissibilité sans en inventer » | `catalog_builder.py` (`ADDITIONAL_LOCATION_TYPES`, `REQUIRED_ASSET_TYPES`) | `ADMISSIBILITY_EVIDENCE_AUDIT.md` | régénération du catalogue | C2 | **VALIDÉ** |
| « Au moins un candidat est réellement admissible avec le catalogue et le mapping réels » | `src/admissibility.py` | `sp1_real_example.json` | `python -m examples.sp1_real_example` | C3 | **VALIDÉ** (`T1039@FS01`/`D3-DNR`/`shared-drive`) |
| « Le RAG récupère des passages D3FEND/Engage/littérature » | `rag_indexer.py`/`rag_retriever.py` | staging (124 chunks) | `rag_retrieval_example.txt` | C4 | **VALIDÉ** |
| « Le LLM réel produit les 11 sous-métriques » | `RealLlmAnnotator` | preuves RAG | `llm_annotation_real.json` | C5 | **NON VALIDÉ** — code prêt et testé (mocks), aucune exécution réelle dans cet environnement |
| « Le repli déterministe produit les 11 sous-métriques sans LLM réel » | `RuleBasedStubAnnotator` | preuves RAG | `llm_annotation_example.json` | — | **VALIDÉ** (explicitement marqué `rule_based_stub`) |
| « Les agrégats `Realisme`/`P_interaction`/`P_engagement`/`Effet_prog`/`DE` sont calculés par code, jamais par le LLM » | `src/annotation_validator.py` | 11 `Annotation` (stub ou réel) | `frozen_annotations_example.csv` | C6 (stub) | **VALIDÉ** (formules) ; table figée à partir d'un LLM réel **NON VALIDÉE** |
| « Le moteur SP3 reproduit exactement l'ancre de validation du chapitre 3 » | `src/risk_engine.py` | scénario analytique CLAUDE.md §20 | `test_reference_example` | — (chapitre 5) | **VALIDÉ** (tolérance `1e-3`) |
| « L'optimiseur résout `(P)` par énumération exhaustive avec front de Pareto » | `src/optimizer.py` | `C_{i,h}` + coûts | `optimizer_example.txt` | — (chapitre 5) | **VALIDÉ** |
| « L'orchestrateur exécute le pipeline complet de bout en bout » | `src/orchestrator.py` | catalogue/mapping réels + RAG réel | `pipeline_example.txt` | C7 | **VALIDÉ** (avec repli déterministe, pas de LLM réel) |
| « Aucun appel LLM n'a lieu pendant le calcul du risque ou l'optimisation » | tests `ast` dédiés sur `risk_engine.py`/`optimizer.py`/`reporter.py` | — | `pytest -v` (588 tests) | — | **VALIDÉ** |

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
