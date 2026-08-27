# Audit du catalogue de déception étendu (≥ 25 mécanismes)

> Réf. tâche « éliminer la limitation : le catalogue réel ne contient que 3 mécanismes ».
> Réf. architecture : CLAUDE.md §7, §9, §10.2 (source de vérité : `docs/architecture_complete_cyberdeception_PFE.pdf`).
>
> Ce document justifie, mécanisme par mécanisme, la décision **INCLUDE / MERGE / EXCLUDE**
> appliquée par `tools/deception_kb/catalog_builder.py::build_expanded_catalog()`.
> Construit **après** le codage du builder, en relisant sa sortie réelle — jamais l'inverse.

## 1. Portée et invariant

`tools/deception_kb/catalog_builder.py::build_catalog()` (périmètre v1 : 3 mécanismes D3FEND
avec relation ATT&CK directement tracée dans `d3fend_attack_mapping_seed_1.5.0.json`) **reste
inchangé** — voir sa docstring de module. `build_expanded_catalog()` l'étend avec 23 mécanismes
supplémentaires, sourcés exclusivement dans les stagings déjà versionnés
(`data/deception/staging/*.json`, produits par `tools/deception_kb/{d3fend,engage,literature}_seed_builder.py`) :
**aucune nouvelle source documentaire n'a été nécessaire** pour atteindre le seuil de 25.

Total : **26 mécanismes** (marge de 1 par rapport au seuil ≥ 25, en cas de retrait ultérieur d'un
mécanisme lors d'une revue future).

## 2. Critères d'inclusion appliqués (réf. §6 de la tâche)

Un élément devient un mécanisme du catalogue seulement s'il réunit :

1. c'est une action ou une ressource de cyberdéception réellement déployable ;
2. sa description est suffisamment précise (jamais une phrase de taxonomie isolée) ;
3. il a au moins une preuve documentaire vérifiable (`evidence`, citée exactement) ;
4. il a au moins un `target_artifact`, OU un `possible_placement`, OU un `interaction_mechanism` ;
5. ce n'est pas un simple objectif stratégique abstrait.

Aucun élément n'a été inclus uniquement parce qu'il figure dans la liste illustrative de familles
du prompt (honeytokens, tarpits, etc.) — chaque inclusion est justifiée par une source réelle
ci-dessous.

## 3. D3FEND — 11 concepts réels de la branche « Deceive » (D3FEND 1.5.0)

| id | nom | décision | famille | justification |
|---|---|---|---|---|
| D3-DF | Decoy File | **INCLUDE** (v1, inchangé) | filesystem/network_share | relation ATT&CK directe tracée (`d3fend_attack_mapping_seed`) |
| D3-DUC | Decoy User Credential | **INCLUDE** (v1, inchangé) | credential_store | idem |
| D3-DNR | Decoy Network Resource | **INCLUDE** (v1, inchangé) | network_resource | idem |
| D3-DP | Decoy Persona | **INCLUDE** (étendu) | account | fiche réelle (definition + kb-article : *"A false online identity is created for the purposes of interacting with adversaries..."*) ; aucune relation ATT&CK tracée dans ce staging → aucun M_{i,d} généré (limite documentée) |
| D3-DST | Decoy Session Token | **INCLUDE** (étendu) | session_store | *"Usage of decoy session tokens may be monitored to track attacker behavior..."* ; idem, aucun M_{i,d} |
| D3-DPR | Decoy Public Release | **INCLUDE** (étendu) | (aucun placement dérivable — `artifacts: []` dans le staging) | *"The media may include URLs, points of contact, or other identifiers to entice interaction..."* ; idem, aucun M_{i,d} |
| D3-CHN | Connected Honeynet | **INCLUDE** (étendu) | network_segment | *"Decoy honeypots are deployed within the enterprise environment that emulate certain services..."* ; idem, aucun M_{i,d} |
| D3-SHN | Standalone Honeynet | **INCLUDE** (étendu) | network_segment | *"An environment created for the purpose of attracting attackers and eliciting their behaviors that is not connected to any production enterprise systems."* ; idem, aucun M_{i,d} |
| D3-IHN | Integrated Honeynet | **INCLUDE** (étendu) | network_segment | *"Integrated honeynets use full production environments [...] that utilize computing resources or software that attract attackers, and allow full interaction."* ; idem, aucun M_{i,d} |
| D3-DO | Decoy Object | **EXCLUDE** | — | concept parent/catégorie (`is_leaf=false`) : jamais lui-même un mécanisme déployable |
| D3-DE | Decoy Environment | **EXCLUDE** | — | idem, catégorie parente de D3-CHN/D3-SHN/D3-IHN |

**Politique différente entre v1 (build_catalog) et étendu (build_expanded_catalog) :**
la v1 exige une relation ATT&CK directement tracée pour renseigner `interaction_mechanism` (le
plus conservateur). L'extension autorise `interaction_mechanism` construit à partir d'une citation
exacte du kb-article D3FEND (« How it works ») lorsque le concept est une feuille réelle
(`is_leaf=true`), suffisamment décrite, avec au moins un `target_artifact` ou `interaction_mechanism`
— jamais une paraphrase libre, toujours une citation directe (voir tableau ci-dessus).

## 4. MITRE Engage — 31 activités réelles (23 EAC « Engagement » + 8 SAC « Strategic »)

### 4.1 Retenues comme mécanismes déployables (15)

Chacune dispose d'une relation ATT&CK **directe** et officielle dans
`engage_attack_mapping_seed_1.0.json` (matrice MITRE Engage, `origin: "mitre_engage_v1.0"`,
792 lignes déjà versionnées mais jusqu'ici inutilisées) — voir §5.

| id | nom | placement principal | citation source (extrait) |
|---|---|---|---|
| EAC0005 | Lures | credential_store / account / filesystem | *"Lures can take a variety of forms including credentials, accounts, files/directories..."* |
| EAC0006 | Application Diversity | host | *"presents an array of software targets to the adversary"* |
| EAC0007 | Network Diversity | network_segment | *"use of an assorted collection of network resources... to help establish the legitimacy of a deceptive network"* |
| EAC0008 | Burn-In | host / account | *"exercising the system to create desirable system artifacts... logs into a decoy account..."* |
| EAC0009 | Email Manipulation | mailbox | *"Suspicious emails may be removed from production mailbox and placed into an inbox in an engagement environment"* |
| EAC0010 | Peripheral Management | host | *"introduce peripherals to an adversary-controlled system... to present new or additional information"* |
| EAC0011 | Pocket Litter | filesystem / host | *"data placed on a system to help tell the engagement narrative"* |
| EAC0014 | Software Manipulation | host | *"alter or replace elements of the OS, file system, or other software... to hide legitimate systems... reveal deceptive artifacts"* |
| EAC0015 | Information Manipulation | (non dérivable) | *"Conceal and reveal both facts and fictions to support a deception story"* |
| EAC0016 | Network Manipulation | network_segment | *"throttle network speeds, segment the network, maintain a unique IP addressing scheme..."* |
| EAC0018 | Security Controls | host / network_share | *"turn off Windows Defender in a single directory or share [to] encourage adversary activity in predetermined locations"* |
| EAC0020 | Isolation | network_segment / host | *"observe adversary behaviors or tools with limited, or no, lateral movement allowed"* — correspond à l'effet de progression **contain** (§12.6 CLAUDE.md) |
| EAC0021 | Attack Vector Migration | mailbox / host / network_segment | *"intercepts a malicious element and moves it to a safe environment, such as a decoy system within a decoy network"* — correspond à **redirect** |
| EAC0022 | Artifact Diversity | host / account / filesystem / credential_store | *"presenting multiple network and system artifacts to the adversary including accounts, files/directories, credentials, logs..."* |
| EAC0023 | Introduced Vulnerabilities | host / network_resource | *"intentionally introduce vulnerabilities into the environment for the adversary to exploit"* |

### 4.2 Fusionnée (1)

| id | nom | décision | justification |
|---|---|---|---|
| EAC0012 | Personas | **MERGE → D3-DP** | même mécanisme (fausse identité utilisateur) que D3-DP « Decoy Persona » : description/long_description ajoutées comme preuve supplémentaire de D3-DP, pas un id de catalogue séparé (§8, anti-duplication) |

### 4.3 Exclues (15)

| id | nom | catégorie | justification |
|---|---|---|---|
| EAC0001 | API Monitoring | monitoring | observation, pas un mécanisme déployable perçu par l'attaquant |
| EAC0002 | Network Monitoring | monitoring | idem |
| EAC0003 | System Activity Monitoring | monitoring | idem |
| EAC0004 | Network Analysis | analyse | analyse de trafic, pas un artefact déployable |
| EAC0013 | Malware Detonation | analyse | technique d'investigation (sandboxing), pas un mécanisme de tromperie déployé contre l'attaquant |
| EAC0017 | Hardware Manipulation | sécurité opérationnelle | retrait de micro/caméra pour la sécurité de l'opération elle-même (*"often required to maintain operational safety"*) — pas perçu comme un leurre par l'attaquant |
| EAC0019 | Baseline | gestion interne | définir/réinitialiser un état de référence, aucun placement ni artefact concret perçu par l'attaquant |
| SAC0001 | Operational Objective | stratégique | planification |
| SAC0002 | Persona Creation | stratégique | planification amont de EAC0012/D3-DP |
| SAC0003 | Storyboarding | stratégique | planification narrative |
| SAC0004 | Cyber Threat Intelligence | stratégique | analyse |
| SAC0005 | Gating Criteria | stratégique | critères d'arrêt opérationnel |
| SAC0006 | After-Action Review | stratégique | retour d'expérience post-opération |
| SAC0009 | Threat Model | stratégique | évaluation de risque organisationnel |
| SAC0012 | Engagement Environment | stratégique / catégorie | conception amont de l'environnement — mêmes motifs que D3-DE/D3-DO, pas elle-même un mécanisme instancié |

**Règle globale, auditable en un coup d'œil :** toute activité **Strategic** (SAC*) est exclue par
construction (planification, jamais un mécanisme déployé) ; parmi les activités **Engagement**
(EAC*), seules celles décrivant explicitement une action/ressource perçue ou rencontrée par
l'attaquant sont retenues.

## 5. Littérature scientifique — 2 mécanismes génériques établis

| id | nom | sources | justification |
|---|---|---|---|
| LIT-HONEYPOT | Honeypot | Provos 2004 (*A Virtual Honeypot Framework*), Spitzner 2003 (*Honeypots: Catching the Insider Threat*), Ferguson-Walter et al. 2021 (efficacité psychologique) | définition établie et largement citée : *"A honeypot is a closely monitored network decoy... it can distract adversaries from more valuable machines... provide early warning..."* |
| LIT-HONEYTOKEN | Honeytoken | Kahlhofer et al. 2024 (*Honeyquest*) | *"Fooling adversaries with traps such as honeytokens can slow down cyber attacks and create strong indicators of compromise."* |

Le passage *"Decoy Documents are automatically generated and stored on a file system... to
entice a malicious user"* (Bowen et al., `doi_10.1007_978-3-642-05284-2_4`) ainsi que la
définition des honeyfiles (`doi_10.1109_iaw.2004.1437806`, *"bait files... reside on a file
server"*) **ne créent pas de mécanisme séparé** : ce sont des variantes de D3-DF (Decoy File),
dont le kb-article couvre déjà explicitement les documents (*"The files may be configurations,
documents, executables..."*) — évitent une scission artificielle d'une même fiche (§8).

## 6. Distinction de granularité Honeypot / D3-DNR / D3-CHN-SHN-IHN

Point de vigilance dédup explicite : le kb-article D3-DNR mentionne *"A 'honeypot' may serve a
variety of decoy network resources"* — un lien réel entre les deux concepts. Décision retenue
(pas une fusion) : les trois niveaux de granularité sont **complémentaires**, pas synonymes :

- **LIT-HONEYPOT** = un hôte/service leurre autonome (l'actif lui-même) ;
- **D3-DNR** = une ressource leurre greffée sur un actif réel existant (serveur web/fichiers) ;
- **D3-CHN / D3-SHN / D3-IHN** = un environnement/réseau de leurres (plusieurs hôtes), différencié
  par son degré de connexion à l'environnement de production.

Cette hiérarchie de granularité est utile à SP1 pour modéliser des emplacements de nature
différente (un honeypot dédié vs. une ressource déployée sur un serveur réel vs. un honeynet
entier) — ce n'est pas une duplication du même mécanisme.

## 7. Résumé chiffré (réf. `docs/chapter4/outputs/catalog_statistics.json`)

- 26 mécanismes catalogués (9 D3FEND, 15 MITRE Engage, 2 littérature) ;
- 18 mécanismes disposent d'au moins une relation M_{i,d} (591 relations au total : 464 directes
  MITRE Engage + 127 dérivées D3FEND) ;
- 271 techniques ATT&CK Enterprise distinctes couvertes (vs. ~125 techniques → 3 mécanismes avant
  cette extension) ;
- 8 mécanismes n'ont encore aucune relation ATT&CK tracée (D3-DP, D3-DST, D3-DPR, D3-CHN, D3-SHN,
  D3-IHN, LIT-HONEYPOT, LIT-HONEYTOKEN) — limite documentée, pas comblée artificiellement (§9).

## 8. Ce que cet audit ne prouve pas

Comme le test analytique de référence (CLAUDE.md §21), cet audit prouve la cohérence et la
traçabilité du catalogue étendu et de son mapping ATT&CK — il ne prouve pas la qualité
opérationnelle de chaque mécanisme en déploiement réel, ni l'exhaustivité du catalogue par
rapport à l'univers complet de la cyberdéception (hors périmètre de cette tâche, §23).
