# Protocole de recherche documentaire — corpus scientifique de cyberdéception

> Réf. architecture : CLAUDE.md §9 « Base de connaissances cyberdéception »
> / §9.1 « Pipeline de construction de la KB déception ». Ce document
> décrit la méthode réellement suivie pour construire
> `data/deception/literature/literature_sources.json` — reproductible,
> mais non automatisée (aucun script ne « re-fait » cette recherche ; ce
> protocole documente une démarche manuelle assistée d'outils
> déterministes de vérification).

## 1. Dates de recherche

- Construction initiale du corpus : **2026-08-23**.
- Session de durcissement (phase 4B.3-H — provenance bibliographique,
  distinction DOI publication/repository, dates explicites, peer review
  explicite, vérification page par page, complément empirique) :
  **2026-08-23** (même journée, session distincte).

## 2. Portée

Le corpus vise à couvrir la cyberdéception comme domaine scientifique
général (mécanismes, artefacts, réalisme, interaction attaquant,
déploiement, ressources, évaluation), **pas** le cas d'usage expérimental
du PFE. Aucune requête n'a ciblé T1003, T1078, ou les actifs `DC`/`WS`/`DB`
du scénario de référence.

## 3. Bases et sites consultés

- Moteur de recherche web généraliste (accès aux pages d'éditeurs,
  dépôts institutionnels et agrégateurs académiques) ;
- **Crossref REST API** (`https://api.crossref.org/works/<DOI>`) — vérification
  déterministe et scriptable des métadonnées (titre, auteurs, année,
  venue, type) de chaque DOI retenu, avant toute inclusion dans le
  registre ;
- pages officielles des éditeurs/organisateurs de conférence consultées
  individuellement pour confirmer chaque référence : `dl.acm.org`,
  `ieeexplore.ieee.org`, `link.springer.com`, `sciencedirect.com`,
  `usenix.org`, `acsac.org` ;
- dépôts d'accès ouvert utilisés pour le texte intégral lorsque la version
  d'édition est payante : `arxiv.org`, dépôt institutionnel CERIAS (Purdue
  University), dépôt institutionnel EURECOM, page officielle de conférence
  (USENIX, ACSAC), page faculté officielle (.edu), page personnelle
  académique d'auteur (auto-archivage), miroir académique SoS-VO
  (Science of Security Virtual Organization, communauté NSA/NSF).

## 4. Axes conceptuels de recherche

Axes conceptuels utilisés comme point de départ (non exhaustifs, non
imposés comme liste de résultats) :

```text
cyber deception
cyberdeception
deception technology cybersecurity
honeypot
honeynet
honeytoken
decoy system cybersecurity
decoy credentials
decoy documents
deception defense
attacker engagement deception
cyber deception realism
deception environment realism
attacker interaction honeypot
deception attack graph
deception placement cybersecurity
adaptive cyber deception
cyber deception optimization
```

## 5. Requêtes réellement exécutées

Liste exacte et complète des requêtes de recherche web effectivement
soumises lors de cette session (chaque requête a mené à la vérification
d'au moins une source retenue ou explicitement écartée) :

1. `"Deception Techniques in Computer Security: A Research Perspective" ACM Computing Surveys Han Kheir Balzarotti DOI`
2. `"A Game-Theoretic Taxonomy and Survey of Defensive Deception" Pawlick Colbert Zhu ACM Computing Surveys DOI`
3. `"Planning and Integrating Deception into Computer Security Defenses" Almeshekah Spafford NSPW DOI`
4. `"Demystifying Deception Technology: A Survey" Fraunholz arxiv`
5. `"Baiting Inside Attackers Using Decoy Documents" Bowen Hershkop Keromytis Stolfo SecureComm DOI`
6. `"Three decades of deception techniques in active cyber defense" Zhang Thing Computers Security DOI`
7. `Provos "A Virtual Honeypot Framework" USENIX Security 2004`
8. `Spitzner "Honeytokens: The Other Honeypot" 2003`
9. `"Urias" "Technologies to Enable Cyber Deception" ICCST 2017 DOI`
10. `cyber deception attack graph placement optimization defensive deception scientific paper DOI`
11. `Spitzner "Honeypots: Catching the Insider Threat" ACSAC 2003 IEEE DOI`
12. `"Harnessing the Power of Deception in Attack Graph-Based Security Games" authors Springer DOI`
13. `Yuill Zappe Denning "Honeyfiles: deceptive files for intrusion detection" IEEE DOI`
14. `"Cyber Deception: State of the art, Trends, and Open challenges" arxiv 2409.07194 authors`
15. `Almeshekah Spafford "Planning and Integrating Deception" CERIAS Purdue pdf site:cerias.purdue.edu OR site:docs.lib.purdue.edu`
16. `Fraunholz "Demystifying Deception Technology" published journal conference peer-reviewed venue 2018 2019`

La requête n°8 (« Honeytokens: The Other Honeypot ») a été explicitement
**écartée** du corpus : il s'agit d'un billet SecurityFocus de 2003, non
évalué par les pairs, sans venue académique identifiable ni DOI. Le
mécanisme des honeytokens est couvert dans le corpus retenu par des
sources évaluées par les pairs (Han et al. 2018 ; Yuill et al. 2004 pour
les honeyfiles, une forme de honeytoken).

### 5.1 Requêtes de la session de durcissement (2026-08-23)

Recherche complémentaire ciblée sur la couverture empirique (réalisme,
attractivité/enticingness, interaction attaquant, comportement de
l'attaquant, efficacité observée — réf. tâche §21/§23) :

17. `"Honeyquest" "Enticingness" Cyber Deception Techniques Code-based Questionnaires authors venue DOI`
18. `"Tularosa Study" cyber deception human behavior Ferguson-Walter Fugate Mauger Major`
19. `"Examining the Efficacy of Decoy-based and Psychological Cyber Deception" authors venue DOI`
20. `"The Tularosa Study: An Experimental Design and Implementation to Quantify the Effectiveness of Cyber Deception" HICSS 2019 authors DOI`
21. `Beltrán-López Gil Pérez Nespoli "Cyber Deception" IEEE Communications Surveys Tutorials 2026 volume 28 early access 2025`

Requêtes des axes complémentaires suggérés par la tâche (§23) qui ont été
**effectivement soumises** mais n'ont produit aucune source retenue
au-delà de ce qui précède (résultats déjà couverts par le corpus existant
ou non concluants lors de cette session) : `cyber deception attacker
behavior empirical study`, `attacker engagement empirical cyber
deception`. Les autres axes listés à titre indicatif dans la tâche §23
(`cyber deception enticingness experiment`, `honeypot attacker
interaction experiment`, `decoy attractiveness cybersecurity study`,
`cyber deception realism experiment`, `cyber deception user study`,
`cyber deception field experiment`, `decoy service cybersecurity
deception`, `decoy network empirical study`, `decoy asset
cybersecurity`, `honeypot realism attacker behavior`) n'ont **pas** été
exécutés littéralement lors de cette session — les requêtes 17 à 19
ci-dessus, plus larges, ont suffi à identifier les deux candidats retenus
sans dupliquer inutilement les appels de recherche. Ceci est documenté
explicitement pour ne jamais prétendre avoir exécuté une requête qui ne
l'a pas été (réf. tâche §31).

### 5.2 Candidats examinés lors du durcissement

| Candidat | Statut | Raison |
|---|---|---|
| Kahlhofer, Achleitner, Rass, Mayrhofer — « Honeyquest: Rapidly Measuring the Enticingness of Cyber Deception Techniques with Code-based Questionnaires », RAID 2024, DOI 10.1145/3678890.3678897 | **Retenu** | Étude empirique (47 participants) mesurant l'attractivité de 25 techniques de déception ; comble un manque explicite (réalisme/enticingness empirique) du corpus initial. |
| Ferguson-Walter, Major, Johnson, Muhleman — « Examining the Efficacy of Decoy-based and Psychological Cyber Deception », USENIX Security 2021, pp. 1127-1144 | **Retenu** | Publication évaluée par les pairs rapportant les résultats d'efficacité de l'étude dite « Tularosa » (>130 red teamers professionnels) ; comble un manque explicite (comportement empirique de l'attaquant). |
| Ferguson-Walter et al. — « The Tularosa Study: An Experimental Design and Implementation to Quantify the Effectiveness of Cyber Deception », HICSS 2019, DOI 10.24251/hicss.2019.874 | **Écarté** | Article de conception expérimentale sur le **même jeu de données** que la publication ci-dessus retenue ; les résultats d'efficacité qu'il annonce sont précisément ceux publiés en détail par l'article USENIX Security 2021 retenu — inclusion jugée redondante (réf. tâche §22 point 10 : non-redondance). |
| « The Tularosa Experiment: A Foundational Study for Cyber Deception », chapitre de l'ouvrage *Foundations of Cyber Deception* (Advances in Information Security), DOI 10.1007/978-3-031-93867-2_6, 2026 | **Écarté** | Synthèse tertiaire (chapitre d'ouvrage) du même travail Tularosa, sans nouvelle contribution empirique identifiée par rapport à la publication USENIX Security 2021 déjà retenue. |

## 6. Critères d'inclusion

Une source n'est retenue que si **toutes** les conditions suivantes sont
vérifiées :

1. pertinence directe pour la cyberdéception (mécanismes, déploiement,
   interaction attaquant, réalisme, évaluation) — pas seulement une
   mention incidente ;
2. nature académique : article de revue, article de conférence/atelier
   évalué par les pairs, ou — à défaut, et seulement si l'information
   n'est disponible nulle part ailleurs dans le corpus — preprint
   académique clairement identifié comme tel ;
3. métadonnées vérifiables via au moins une source stable (DOI résolu via
   Crossref, ou page officielle d'éditeur/conférence) ;
4. couverture thématique non redondante avec une source déjà retenue (pas
   d'ajout uniquement pour atteindre un nombre, réf. tâche §7).

## 7. Critères d'exclusion

- blogs marketing, pages commerciales, documentation fournisseur (source
  potentielle d'un futur corpus technique séparé, hors périmètre de cette
  phase) ;
- articles dont le titre seul a été retourné par la recherche, sans
  vérification indépendante des métadonnées ;
- toute source nécessitant de contourner un paywall pour en obtenir le
  texte intégral (dans ce cas : conserver uniquement les métadonnées,
  `access_status = "metadata_only"`) ;
- doublons manifestes (même DOI, ou même travail décliné en version
  preprint + version publiée — traité comme une seule entité
  scientifique, cf. §9).

## 8. Méthode de vérification des DOI et métadonnées

Pour chaque candidat retenu :

1. identification d'un DOI plausible via la recherche web (page
   d'éditeur, DBLP, ResearchGate, Semantic Scholar — jamais retenu comme
   preuve finale) ;
2. interrogation de `https://api.crossref.org/works/<DOI>` (requête HTTP
   réelle, réponse JSON horodatée) — pour un DOI de dépôt/preprint arXiv
   (préfixe `10.48550/`), interrogation de **DataCite**
   (`https://api.datacite.org/dois/<doi>`) à la place, Crossref
   n'indexant pas ces DOI ;
3. comparaison du `title`, des `author`, du `container-title` et des
   champs de date retournés avec les informations trouvées par la
   recherche web ;
4. vérification croisée via **DBLP** (`https://dblp.org/search/publ/api`)
   lorsque nécessaire pour trancher une ambiguïté de date (cas
   Beltrán-López et al., §8.2).

### 8.1 publication_doi vs repository_doi (durcissement)

Distinction obligatoire, jamais confondue :

- **`publication_doi`** : DOI de la publication scientifique finale
  (revue, actes de conférence), enregistré auprès de **Crossref**.
- **`repository_doi`** : DOI attribué à un dépôt/preprint (ex. arXiv),
  enregistré auprès de **DataCite**, distinct de l'agence Crossref.
  Vérifié explicitement pour Fraunholz et al. (2018) :
  `10.48550/arXiv.1804.06196`, interrogé via l'API DataCite le
  2026-08-23, confirmé `publisher: "arXiv"`,
  `resourceTypeGeneral: "Preprint"`, auteurs et titre identiques au
  registre. Ce DOI n'est **jamais** traité comme `publication_doi` : le
  champ reste `null` pour cette source, faute de publication finale
  identifiée (recherche dédiée, requête n°16, sans résultat concluant).
- Lorsqu'un DOI Crossref existe pour la publication finale
  (`publication_doi`) ET qu'une version preprint distincte existe (arXiv),
  seul `publication_doi` est renseigné et `open_access_url` pointe vers le
  preprint pour l'accès au texte intégral (cf. §9 — identité de l'entité
  scientifique confirmée par correspondance des auteurs, jamais par
  ressemblance de titre seule).
- Un même enregistrement ne doit jamais porter `publication_doi ==
  repository_doi` (vérifié automatiquement par
  `validate_literature_sources_registry`).

### 8.2 Dates de publication explicites (durcissement)

Trois champs distincts remplacent l'ancien champ unique `year` :
`bibliographic_year` (année de citation formelle — obligatoire),
`published_online_year` (première mise en ligne officielle, si
identifiable avec certitude), `published_print_year` (édition/volume
imprimé, si applicable). Règle appliquée systématiquement : ne jamais
recopier aveuglément `Crossref["issued"]` dans `bibliographic_year` sans
examiner `published-print`, `published-online` et `created` en parallèle.

**Cas particulier vérifié en détail — Beltrán-López, Gil Pérez & Nespoli,
DOI 10.1109/COMST.2025.3594788 :**

| Champ Crossref | Valeur observée (interrogé le 2026-08-23) |
|---|---|
| `created` (premier enregistrement du DOI) | 2025-08-01 |
| `issued` | 2026 (année seule) |
| `published-print` | 2026 (année seule) |
| `published-online` | absent |
| `deposited` | 2026-01-02 |
| volume / pages | 28 / 1520-1556 |

DBLP (`https://dblp.org/rec/journals/comsur/LopezPN26`, interrogé le
2026-08-23) confirme `year: 2026`. Une recherche web indépendante
corrobore explicitement une mise en Early Access en 2025, antérieure à
l'assignation au volume 2026. **Décision documentée** :
`bibliographic_year = 2026` (citation formelle, confirmée par deux
sources indépendantes Crossref + DBLP) ; `published_online_year = 2025`
(Early Access, dérivé de `created` + corroboration externe explicite —
PAS d'un champ Crossref `published-online` formellement présent, cette
nuance étant documentée pour ne pas être confondue avec un cas où
`published-online` existe réellement, ex. Han et al. ou Pawlick et al.
ci-dessous) ; `published_print_year = 2026`.

**Autres cas non ambigus, pour référence :**

| Source | `issued`/`published-online` | `published-print` | Décision |
|---|---|---|---|
| Han et al. 2018 (10.1145/3214305) | 2018-07-25 | 2019-07-31 | bibliographic_year=2018 (citation usuelle), published_online_year=2018, published_print_year=2019 |
| Pawlick et al. 2019 (10.1145/3337772) | 2019-08-30 | 2020-07-31 | bibliographic_year=2019, published_online_year=2019, published_print_year=2020 |
| Zhang & Thing 2021 (10.1016/j.cose.2021.102288) | absent (`published-online` non fourni par Crossref) | 2021-07 | bibliographic_year=2021, published_online_year=**null** (le champ `created`, 2021-04-18, n'est PAS utilisé comme proxy faute de corroboration externe équivalente au cas Beltrán-López — décision volontairement différente pour ne pas inventer une date) |
| Spitzner 2003 (10.1109/CSAC.2003.1254322) | vide (`issued: [[None]]`) | absent | bibliographic_year=2003, dérivée du `container-title` Crossref lui-même (« 19th Annual Computer Security Applications Conference, 2003 ») et de la page officielle ACSAC — `created` (2004-07-08) explicitement **non retenu**, n'étant qu'une date de dépôt tardive du DOI |
| Yuill et al. 2004 (10.1109/IAW.2004.1437806) | vide (`issued: [[None]]`) | absent | bibliographic_year=2004, même motif que Spitzner ; `created` (2005-06-07) explicitement **non retenu** (postdate d'un an la tenue réelle de l'atelier, confirmée par le `container-title` et la page officielle de l'autrice) |

## 9. Gestion des versions arXiv / éditeur

Lorsqu'une version arXiv et une version publiée correspondent
manifestement au même travail (même titre ou titre very proche, mêmes
auteurs confirmés via Crossref sur la version publiée), une seule entité
scientifique est conservée dans le registre : les métadonnées
bibliographiques (titre exact, DOI, venue) proviennent de la version
publiée (faisant foi), et `open_access_url` pointe vers la version arXiv
pour l'accès au texte intégral. Cette identité n'est **jamais** inférée
par simple ressemblance de titre (fuzzy matching) : elle est confirmée par
correspondance exacte des auteurs entre les deux versions. Deux cas
traités ainsi dans ce corpus :

- Pawlick, Colbert & Zhu — arXiv:1712.05441 ≡ DOI 10.1145/3337772 ;
- Zhang & Thing — arXiv:2104.03594 ≡ DOI 10.1016/j.cose.2021.102288 ;
- Beltrán-López, Gil Pérez & Nespoli — arXiv:2409.07194 (titre légèrement
  différent : « ... State of the art, Trends and Open challenges ») ≡ DOI
  10.1109/COMST.2025.3594788 (titre final : « ... Taxonomy, State of the
  Art, Frameworks, Trends, and Open Challenges »).

## 10. Gestion des doublons

Priorité de détection (réf. tâche §19) :

1. DOI identique (rejeté par `validate_literature_sources_registry`,
   `tools/deception_kb/literature_seed_builder.py`) ;
2. URL canonique identique ;
3. combinaison titre normalisé + année + auteurs lorsque le DOI est
   absent.

Aucune fusion automatique par similarité de titre n'a été effectuée à
aucun moment de cette recherche.

## 11. Identifiants stables des sources

Réf. tâche §6/§11 (durcie en 4B.3-H). Règle déterministe, implémentée dans
`tools/deception_kb/literature_seed_builder.py` :

- **si un `publication_doi` est disponible** : `source_id = "doi_" + publication_doi.lower().replace("/", "_")`
  (fonction `compute_doi_based_source_id`), vérifié automatiquement par
  `validate_literature_sources_registry` — toute incohérence entre
  `source_id` et le `publication_doi` déclaré est rejetée. **Jamais**
  dérivé d'un `repository_doi` (réf. tâche §6) ;
- **sinon** (aucun `publication_doi` — trois cas dans ce corpus : Provos
  2004 et Ferguson-Walter et al. 2021, actes USENIX Security sans DOI
  Crossref ; Fraunholz et al. 2018, preprint arXiv sans publication
  finale) : identifiant dérivé manuellement de métadonnées vérifiées,
  selon la convention `<acronyme_venue><année>_<famille_premier_auteur>_<mots_clés_titre>`
  (ex. `usenixsec2021_fergusonwalter_decoy_psychological_deception_efficacy`),
  entièrement en minuscules ASCII, jamais `PAPER1`/`PAPER2` — vérifié par
  `is_valid_fallback_source_id` (rejette explicitement le motif
  `paper<n>`) ;
- cas particulier du preprint arXiv sans `publication_doi` mais avec
  `repository_doi` (Fraunholz et al. 2018) : `source_id = "arxiv_" +
  <identifiant arXiv>` (`arxiv_1804.06196`), **conservé tel quel même en
  présence d'un `repository_doi`** (réf. tâche §6 : le `repository_doi`
  identifie le dépôt, le `source_id` identifie l'entité scientifique déjà
  versionnée — les deux notions ne doivent pas être mélangées).

Stabilité : aucun des 12 `source_id` du corpus initial n'a été modifié
lors de ce durcissement, conformément à la consigne de ne pas casser
inutilement les identifiants déjà versionnés (réf. tâche §6).

## 11bis. Statut d'évaluation par les pairs (peer_review_status)

Réf. tâche §19. Champ explicite `peer_review_status`
(`peer_reviewed`/`not_peer_reviewed`/`unknown`) et `peer_review_basis`
(justification textuelle), jamais déduits automatiquement de
`publication_type`. Base de vérification pour chaque source : venue
officielle confirmée (actes de conférence avec comité de programme,
revue avec comité de lecture) via Crossref `container-title` et/ou la
page officielle de l'éditeur/organisateur. Dans ce corpus, seule une
source est `not_peer_reviewed` : Fraunholz et al. 2018 (preprint arXiv,
absence confirmée de publication évaluée par les pairs après recherche
dédiée). Toutes les autres sont `peer_reviewed`, chacune avec sa
justification propre consignée dans `peer_review_basis` (voir
`literature_sources.json`).

## 11ter. Vérification page par page des passages (durcissement)

Réf. tâche §12/§13/§14. Le texte extrait par `pdftotext` conserve
nativement un séparateur de page (`\f`, form feed) entre chaque page du
PDF source. `split_extracted_text_pages` (module builder) découpe le
texte extrait sur ce séparateur ; si aucun séparateur n'est présent
(extraction sans structure de page reconstruable), le texte entier est
traité comme une unique page 1 — jamais une page inventée au-delà de ce
qui est structurellement observable.

Pour chaque passage candidat (`page`, `text`), le builder vérifie
désormais que le texte normalisé (espaces/retours à la ligne réduits à un
espace unique) apparaît **sur la page précisément déclarée**, et non plus
seulement quelque part dans le document entier. Un passage trouvé
ailleurs dans le document mais pas sur la page annoncée est rejeté
explicitement (message distinct d'un passage introuvable partout). Tout
passage conservé dans `literature_evidence_seed_1.1.json` porte
`page_verified: true` — aucun passage à page non vérifiée n'atteint le
staging final.

Les 14 passages du corpus initial ont été reconstruits et revérifiés avec
cette méthode stricte : les 14 pages précédemment enregistrées (déjà
calculées par comptage de séparateurs de page lors de la phase initiale)
se sont toutes confirmées exactes sous ce contrôle plus strict, sans
qu'aucune ne doive être corrigée. 4 nouveaux passages (2 par nouvelle
source empirique) ont été ajoutés et vérifiés selon la même méthode,
portant le total à 18 passages, tous `page_verified: true`.

## 12. Limites de la recherche

- La recherche s'appuie sur un moteur de recherche web généraliste, pas
  sur une interrogation systématique et exhaustive de chaque base
  bibliographique spécialisée (IEEE Xplore, ACM DL, Scopus, Web of
  Science) via leurs API propres — ce corpus est donc **représentatif**,
  pas **exhaustif**, du domaine.
- Un seul preprint non évalué par les pairs a été retenu (Fraunholz et
  al. 2018), pour sa couverture unique d'aspects (légaux, éthiques,
  psychologiques) absents des autres sources — explicitement signalé
  comme tel dans le registre (`peer_review_status = "not_peer_reviewed"`),
  jamais compté comme source évaluée par les pairs dans le rapport de
  couverture.
- Une source (Urias et al. 2017) n'a pu être obtenue en texte intégral
  malgré une tentative d'accès via un miroir institutionnel public
  (OSTI.GOV) — conservée en `access_status = "metadata_only"`, sans aucun
  passage documentaire associé.
- Les lacunes de couverture thématique identifiées (`coverage_gaps` du
  rapport) ne sont comblées par aucune source ajoutée artificiellement ;
  après la recherche complémentaire du durcissement, `decoy_asset`,
  `decoy_network` et `decoy_service` restent des lacunes réelles du
  corpus à cette date — aucune publication scientifique solide couvrant
  spécifiquement ces trois artefacts n'a été identifiée lors de cette
  session.
- Pour deux sources anciennes (Spitzner 2003, Yuill et al. 2004), le
  champ Crossref `issued` est vide et `created` s'est révélé peu fiable
  (postérieur d'un à deux ans à la tenue réelle de la conférence) — année
  reconstruite à partir du `container-title` Crossref et de la page
  officielle de la venue, documenté explicitement dans `metadata_notes`
  (§8.2) plutôt que masqué.

## 13. Journal des corrections de métadonnées lors du hardening

Aucune métadonnée de titre, auteur, DOI ou venue n'a été modifiée pour les
12 sources existantes lors de ce durcissement — seules des précisions
(distinction DOI, dates explicites, provenance) ont été ajoutées.
Corrections réelles apportées :

| source_id | Champ | Ancienne représentation | Nouvelle représentation | Raison | Preuve |
|---|---|---|---|---|---|
| `doi_10.1109_comst.2025.3594788` | année | `year: 2025` (unique) | `bibliographic_year: 2026`, `published_online_year: 2025`, `published_print_year: 2026` | L'ancienne valeur unique (2025) correspondait à une lecture partielle ; la vérification croisée Crossref+DBLP confirme que la citation formelle (volume 28, pagination définitive) relève de 2026, avec 2025 comme seule date d'Early Access. | Crossref `issued`/`published-print`=2026, `created`=2025-08-01 ; DBLP `year`=2026 (interrogés le 2026-08-23). |
| `arxiv_1804.06196` | DOI | `doi: null` (aucune distinction) | `publication_doi: null`, `repository_doi: "10.48550/arXiv.1804.06196"`, `repository_identifier: "arXiv:1804.06196"` | Le registre initial ne distinguait pas DOI de publication et DOI de dépôt ; le DOI DataCite du dépôt arXiv est désormais explicitement enregistré comme `repository_doi`, jamais comme `publication_doi`. | API DataCite, `https://api.datacite.org/dois/10.48550/arxiv.1804.06196`, interrogée le 2026-08-23. |
| `doi_10.1109_csac.2003.1254322` / `doi_10.1109_iaw.2004.1437806` | année | `year: 2003` / `year: 2004` (sans note) | `bibliographic_year` identique, mais `metadata_notes` documente désormais explicitement que le champ Crossref `issued` est vide pour ces deux DOI et que `created` (dates tardives, 2004 et 2005) n'est pas fiable comme année de publication | Aucune correction de valeur, mais absence de traçabilité corrigée : la source de l'année (container-title Crossref + page officielle) est maintenant documentée explicitement. | Crossref (`issued: [[None]]` pour les deux DOI, interrogés le 2026-08-23). |

Toutes les autres sources conservent leurs métadonnées de titre, auteurs,
année et DOI inchangées ; seuls les nouveaux champs structurés
(`metadata_provenance`, `peer_review_status`, dates explicites) ont été
ajoutés. Deux nouvelles sources empiriques ont été ajoutées (§5.2) sans
modifier aucune des 12 sources préexistantes au-delà des précisions
ci-dessus.
