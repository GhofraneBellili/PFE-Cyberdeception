# Audit du catalogue de déception étendu (≥ 50 mécanismes)

> Réf. tâche « éliminer la limitation : le catalogue réel ne contient que 3 mécanismes » (26
> mécanismes) puis réf. tâche « |D_knowledge| >= 50 mécanismes de cyberdéception distincts » (51
> mécanismes, section 8 ci-dessous).
> Réf. architecture : CLAUDE.md §7, §9, §10.2 (source de vérité : `docs/architecture_complete_cyberdeception_PFE.pdf`).
>
> Ce document justifie, mécanisme par mécanisme, la décision **INCLUDE / MERGE / EXCLUDE**
> appliquée par `tools/deception_kb/catalog_builder.py::build_expanded_catalog()`.
> Construit **après** le codage du builder, en relisant sa sortie réelle — jamais l'inverse.

## 1. Portée et invariant

`tools/deception_kb/catalog_builder.py::build_catalog()` (périmètre v1 : 3 mécanismes D3FEND
avec relation ATT&CK directement tracée dans `d3fend_attack_mapping_seed_1.5.0.json`) **reste
inchangé** — voir sa docstring de module. `build_expanded_catalog()` l'étend avec 48 mécanismes
supplémentaires (23 D3FEND/Engage + 25 littérature, section 8), sourcés exclusivement dans les
stagings déjà versionnés
(`data/deception/staging/*.json`, produits par `tools/deception_kb/{d3fend,engage,literature}_seed_builder.py`).
Les 23 premiers (D3FEND/Engage) ne nécessitaient aucune nouvelle source ; les 25 mécanismes de la
section 8 ont nécessité l'extraction de nouveaux passages de deux documents déjà présents dans le
registre bibliographique (`data/deception/literature/literature_sources.json`) mais jusqu'ici sous-
exploités, jamais une nouvelle source non vérifiée (détail section 8.1).

Total : **51 mécanismes** (marge de 1 par rapport au seuil ≥ 50, en cas de retrait ultérieur d'un
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

## 6bis. Prérequis d'admissibilité (`required_*`) — devenus une donnée ORGANISATIONNELLE

**Mise à jour (réf. tâche « separate knowledge and organization capabilities ») :** la note
ci-dessous décrivait la situation *avant* la séparation connaissance/capacité organisationnelle.
Depuis cette séparation, `DeceptionMechanism.admissibility_profile` (y compris
`required_asset_types`/`required_services`/`required_artifacts`) est un champ **hérité**,
documentaire, **plus jamais consulté par `src/admissibility.py`** pour évaluer
Autorise/PrerequisSatisfaits — voir `docs/chapter4/FINAL_TECHNICAL_REPORT.md`, section « Préparation
hors ligne vs exécution en ligne ». Les prérequis d'admissibilité viennent désormais
EXCLUSIVEMENT du catalogue OPÉRATIONNEL fourni par l'organisation
(`OrganizationDeceptionCapability`, `examples/data/organization_deception_catalog.json`) — jamais
de D3FEND/Engage/littérature. Ce n'est donc plus « D3FEND ne documente pas assez de prérequis »
mais « l'organisation n'a pas encore configuré ce mécanisme » — distinction explicite portée par
`rejection_reason` (`"...undetermined (missing organization configuration)"`).

Pour mémoire, l'historique ci-dessous reste correct pour la période où il a été écrit (avant cette
séparation) — conservé pour traçabilité du raisonnement, pas comme description de l'état actuel :

> `src/admissibility.py::evaluate_requirements_satisfied` retournait `"undetermined"` (jamais
> `"pass"`) tant que les `required_*` du **catalogue de connaissances** étaient tous vides. Avant la
> présente extension, seul `D3-DNR` avait un `required_asset_types` documenté par D3FEND ; une
> relecture ciblée des `long_description` MITRE Engage avait alors permis de documenter
> `required_services=["email"]` pour `EAC0009`/`EAC0021` (citations exactes sur l'infrastructure de
> messagerie). Ces trois enrichissements ont depuis été reportés dans le catalogue OPÉRATIONNEL
> d'exemple (`examples/data/organization_deception_catalog.json`), qui reste libre de les reprendre,
> les modifier ou les ignorer — ce ne sont plus des faits scientifiques figés dans le catalogue de
> connaissances.

## 7. Résumé chiffré (réf. `docs/chapter4/outputs/catalog_statistics.json`)

- 51 mécanismes catalogués (9 D3FEND, 15 MITRE Engage, 25 littérature — dont 2 génériques déjà
  présents avant cette passe et 23 nouveaux, section 8) ;
- 18 mécanismes disposent d'au moins une relation M_{i,d} (591 relations au total : 464 directes
  MITRE Engage + 127 dérivées D3FEND) — inchangé par l'extension littérature : aucune relation
  ATT&CK n'a été fabriquée pour les 25 nouveaux mécanismes, faute de staging le permettant ;
- 271 techniques ATT&CK Enterprise distinctes couvertes (vs. ~125 techniques → 3 mécanismes avant
  la première extension) ;
- 33 mécanismes n'ont encore aucune relation ATT&CK tracée (les 6 D3FEND étendus, les 25 mécanismes
  littérature de la section 8, D3-DPR et D3-DP en étant déjà 2) — limite documentée, pas comblée
  artificiellement (§9 de la tâche).

## 8. Extension vers ≥ 50 mécanismes — 25 mécanismes littérature supplémentaires

Réf. tâche « |D_knowledge| >= 50 mécanismes de cyberdéception distincts ». Le catalogue D3FEND
(branche « Deceive », 11 concepts) et MITRE Engage (23 activités « Engagement ») étaient déjà
épuisés par l'extension à 26 mécanismes (sections 3-4) — aucun concept/activité supplémentaire
n'existe dans ces deux staging pour aller plus loin sans inventer. L'extension vers 50+ mécanismes
s'appuie donc sur la littérature scientifique déjà présente dans le registre bibliographique
(`data/deception/literature/literature_sources.json`), en extrayant de nouveaux passages
vérifiables de documents déjà versionnés mais jusque-là sous-exploités.

### 8.1 Nouvelle preuve documentaire — méthode

Deux documents déjà enregistrés dans le registre bibliographique (titre/auteurs/année/DOI/URL/
sha256 déjà vérifiés lors d'une passe antérieure) n'avaient que 2 et 1 passage(s) extrait(s)
respectivement : `doi_10.1145_3214305` (Han, Kheir, Balzarotti — *Deception Techniques in
Computer Security: A Research Perspective*, ACM Computing Surveys 2018) et
`doi_10.1016_j.cose.2021.102288` (Zhang, Thing — *Three Decades of Deception Techniques in Active
Cyber Defense*, Computers & Security 2021). Les deux sont des **surveys** dédiés à l'énumération de
techniques de déception nommées et distinctes.

Méthode reproductible et vérifiée par code (pas une lecture non tracée) :
1. Relecture intégrale des deux PDF déjà acquis localement
   (`data/deception/raw/literature/{doi_10.1145_3214305,doi_10.1016_j.cose.2021.102288}.{pdf,txt}`,
   sha256 déjà vérifiés contre le registre) ;
2. identification de 25 techniques nommées, distinctes, et suffisamment décrites (jamais une simple
   entrée de taxonomie isolée) ;
3. pour chacune, un passage exact (`data/deception/literature/evidence_candidates.json`) avec sa
   page précise ;
4. **revalidation automatique et déterministe** par `tools/deception_kb/literature_seed_builder.py::build_literature_evidence_seed`
   — chaque passage doit être retrouvé verbatim (après normalisation des espaces) sur la page
   déclarée exacte du texte extrait, sinon le builder lève une erreur explicite (aucun passage
   n'est jamais accepté sans cette vérification programmatique) ;
5. régénération de `data/deception/staging/literature_{document,evidence}_seed_1.2.json` par la
   commande officielle (`python -m tools.deception_kb.literature_seed_builder ...`), jamais par
   édition manuelle du JSON de staging.

Résultat : `literature_evidence_seed_1.2.json` passe de 18 à 43 passages (25 nouveaux), tous avec
`page_verified: true`.

### 8.2 Les 25 mécanismes retenus

| id | nom | source | citation (extrait) |
|---|---|---|---|
| LIT-TARPIT | Network Tarpit | Han et al. 2018, p.8 | *"decoy machines are commonly known as network tarpits... create sticky connections with the aim to slow or stall automated scanning"* |
| LIT-DECEPTIVE-TOPOLOGY | Deceptive Network Topology | Han et al. 2018, p.10 | *"a technique to skew the topology of the target network through random connection dropping and traffic forging"* |
| LIT-OS-FINGERPRINT | Deceptive OS Fingerprint | Han et al. 2018, p.10 | *"multiple deception techniques...offer to mimic the network behavior of fake operating systems"* |
| LIT-DECEPTIVE-ATTACK-GRAPH | Deceptive Attack Graph | Han et al. 2018, p.10 | *"leveraging structured attack graph representations, in order to drive attackers into following fake attack paths"* |
| LIT-ICS-DECOY | Decoy ICS/OT Asset | Han et al. 2018, p.10 | *"deceptive simulation techniques...applied in the context of industrial control systems...create fake but indistinguishable attack targets"* |
| LIT-DECOY-NIC | Decoy Network Interface | Han et al. 2018, p.10 | *"a decoy Network Interface Controller (NIC)...intentionally set in order to lure and detect malicious software"* |
| LIT-FAKE-HONEYPOT | Fake Honeypot Camouflage | Han et al. 2018, p.10 | *"fake honeypots that make ordinary but critical systems appear as real honeypots...turn him away"* |
| LIT-DECOY-COMPUTE | Decoy Computation | Han et al. 2018, p.11 | *"duplicate multiple times the entire application server to generate decoy computation activities"* |
| LIT-HONEY-PERMISSION | Honey Permission | Han et al. 2018, p.11 | *"extend role-based access control mechanisms with honey permissions...assign unintended access permissions to only fake versions of sensitive system assets"* |
| LIT-SOFTWARE-DECOY | Intelligent Software Decoy | Han et al. 2018, p.11 | *"intelligent software decoys that detect and respond to patterns of suspicious behavior"* |
| LIT-HONEYPATCH | Honey-patch | Han et al. 2018, p.11 | *"converted software patches into fake but valid-looking vulnerabilities...forwards the attacker to a vulnerable decoy version"* |
| LIT-SHADOW-HONEYPOT | Shadow Honeypot | Han et al. 2018, p.11 | *"shadow honeypots that extend honeypots with anomaly-based buffer overflow detection...shares its context and internal state"* |
| LIT-SOFTWARE-TRAP | Software Trap | Han et al. 2018, p.11 | *"software traps that are dissimulated in the code as gadgets, and detect return-oriented programming attacks"* |
| LIT-DECOY-HYPERLINK | Decoy Hyperlink | Han et al. 2018, p.11 | *"decoy links...invisible to normal users, but are expected to be triggered by crawlers and web bots"* |
| LIT-HONEY-CONFIG | Honey Configuration File | Han et al. 2018, p.11 | *"honey configuration files, such as robots.txt, including fake entries, invisible links"* |
| LIT-DECOY-FORM | Decoy Web Form/Parameter | Han et al. 2018, p.12 | *"decoy forms...and honey URL parameters...that display fake configuration errors"* |
| LIT-HONEYWORD | Honeyword | Han et al. 2018, p.12 | *"honeywords (false passwords) in order to conceal true authentic passwords"* |
| LIT-HONEY-ENCRYPTION | Honey Encryption | Han et al. 2018, p.12 | *"'honey encryption', which creates a ciphertext that, when decrypted with an incorrect key or password, results in a valid-looking decoy message"* |
| LIT-DECOY-SOURCECODE | Decoy Source Code | Han et al. 2018, p.12 | *"generated fake but believable Java source code to detect the exfiltration of proprietary source code"* |
| LIT-DECOY-TRAFFIC | Decoy Network Traffic | Han et al. 2018, p.17 | *"Rrushi et al. generated decoy network traffic...to dissimulate sensitive...network connections"* |
| LIT-IP-ROTATION | Dynamic IP Address Rotation | Zhang & Thing 2021, p.9 | *"periodic rotation of VM hosts...the VM host that was previously in use is analyzed for evidence of intrusion and will be removed"* |
| LIT-DYNAMIC-IDS | Dynamic IDS Placement | Zhang & Thing 2021, p.9 | *"dynamically and continuously changing the placement of IDS over time"* |
| LIT-PLATFORM-MIGRATION | Cross-Platform Application Migration | Zhang & Thing 2021, p.9 | *"a running application can be migrated between VMs with different platforms while preserving the state"* |
| LIT-SOFTWARE-DIVERSITY | Software Diversity Randomization | Zhang & Thing 2021, p.10 | *"Marlin breaks a software binary into function blocks and randomly shuffles the order"* |
| LIT-MULTIPATH-ROUTING | Dynamic Multipath Routing | Zhang & Thing 2021, p.10 | *"a multipath routing strategy, which relies on SDN features to frequently modify communication routes"* |

### 8.3 Points de vigilance dédup (granularité, pas duplication)

- **LIT-OS-FINGERPRINT vs EAC0014** (Software Manipulation) : EAC0014 est une activité MITRE Engage
  large (toute manipulation de sortie logicielle) ; LIT-OS-FINGERPRINT est une technique
  académique spécifique au niveau de la pile réseau/TCP contre le fingerprinting d'OS —
  complémentaires par granularité, même motif que Honeypot/D3-DNR (§6).
- **LIT-HONEYPATCH vs EAC0023** (Introduced Vulnerabilities) : EAC0023 est une activité large
  d'introduction de vulnérabilités ; LIT-HONEYPATCH est une implémentation technique précise
  (patch masquerading + redirection vers une version leurre) — complémentaires.
- **LIT-SHADOW-HONEYPOT / LIT-FAKE-HONEYPOT vs LIT-HONEYPOT** : variantes techniques distinctes du
  honeypot générique (partage d'état réel pour l'une, camouflage inverse pour l'autre) — jamais de
  fusion, chacune a sa propre mécanique documentée.
- **LIT-DECOY-SOURCECODE vs D3-DF** (Decoy File) : décision volontairement **distincte** (pas
  fusionnée comme les honeyfiles/decoy documents, §5) car la mécanique diffère techniquement
  (détection d'exfiltration de code source, pas un simple accès fichier surveillé) — jugement
  documenté ici pour audit futur, pas une règle automatique.
- **LIT-DECEPTIVE-TOPOLOGY vs EAC0016** (Network Manipulation) : EAC0016 est un levier opérationnel
  défensif (throttle/segment/kill-switch) ; LIT-DECEPTIVE-TOPOLOGY trompe activement la
  reconnaissance de l'attaquant (topologie perçue fausse) — angle différent, complémentaires.

Les 5 mécanismes « Moving Target Defense » (LIT-IP-ROTATION, LIT-DYNAMIC-IDS,
LIT-PLATFORM-MIGRATION, LIT-SOFTWARE-DIVERSITY, LIT-MULTIPATH-ROUTING) sont explicitement
qualifiés de déception par la littérature déjà présente dans le corpus : `doi_10.1145_3337772`
(*"we propose a taxonomy that defines six types of deception: perturbation, moving target
defense, obfuscation, mixing, honey-x, and attacker engagement"*) classe le MTD comme l'une des
six catégories reconnues de cyberdéception — fondement documentaire de leur inclusion, pas une
extrapolation.

### 8.4 Aucune relation M_{i,d} pour ces 25 mécanismes

Comme pour les 6 mécanismes D3FEND étendus (§6bis), aucun staging ne relie ces 25 mécanismes à des
techniques ATT&CK spécifiques : aucune relation `M_{i,d}` n'a été fabriquée pour eux. Ils sont
catalogués (répondent aux critères §6 de la tâche : mécanisme déployable, description précise,
preuve documentaire, target_artifact/interaction_mechanism) mais resteront `D_i = ∅` pour toute
technique tant qu'aucune preuve de relation n'est trouvée — limite honnête, documentée dans
`docs/chapter4/outputs/catalog_statistics.json`.

## 9. Ce que cet audit ne prouve pas

Comme le test analytique de référence (CLAUDE.md §21), cet audit prouve la cohérence et la
traçabilité du catalogue étendu et de son mapping ATT&CK — il ne prouve pas la qualité
opérationnelle de chaque mécanisme en déploiement réel, ni l'exhaustivité du catalogue par
rapport à l'univers complet de la cyberdéception (hors périmètre de cette tâche, §23).
