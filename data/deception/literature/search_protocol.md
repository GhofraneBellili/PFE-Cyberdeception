# Protocole de recherche documentaire — corpus scientifique de cyberdéception

> Réf. architecture : CLAUDE.md §9 « Base de connaissances cyberdéception »
> / §9.1 « Pipeline de construction de la KB déception ». Ce document
> décrit la méthode réellement suivie pour construire
> `data/deception/literature/literature_sources.json` — reproductible,
> mais non automatisée (aucun script ne « re-fait » cette recherche ; ce
> protocole documente une démarche manuelle assistée d'outils
> déterministes de vérification).

## 1. Date de recherche

Recherche effectuée le **2026-08-23**.

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
   réelle, réponse JSON horodatée) ;
3. comparaison du `title`, des `author`, du `container-title` et du champ
   `issued` retournés par Crossref avec les informations trouvées par la
   recherche web ;
4. en cas de divergence de date entre `issued`, `published-print` et
   `published-online` (observé pour les deux articles ACM Computing
   Surveys — Han et al. et Pawlick et al.), la règle retenue est
   d'utiliser le champ **`issued`** de Crossref (date de première mise en
   ligne / publication effective), qui correspond à l'année communément
   citée dans la littérature, et non `published-print` (date de
   l'assignation à un numéro imprimé, parfois postérieure d'un an).

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

Réf. tâche §11. Règle déterministe, implémentée dans
`tools/deception_kb/literature_seed_builder.py` :

- **si un DOI est disponible** : `source_id = "doi_" + doi.lower().replace("/", "_")`
  (fonction `compute_doi_based_source_id`), vérifié automatiquement par
  `validate_literature_sources_registry` — toute incohérence entre
  `source_id` et le DOI déclaré est rejetée ;
- **sinon** (aucun DOI officiel identifié — un seul cas dans ce corpus,
  Provos 2004, USENIX Security, antérieur à l'attribution systématique de
  DOI par USENIX) : identifiant dérivé manuellement de métadonnées
  vérifiées, selon la convention `<acronyme_venue><année>_<famille_premier_auteur>_<mots_clés_titre>`,
  entièrement en minuscules ASCII, jamais `PAPER1`/`PAPER2` — vérifié par
  `is_valid_fallback_source_id` (rejette explicitement le motif
  `paper<n>`) ;
- cas particulier du preprint arXiv sans DOI (Fraunholz et al. 2018) :
  `source_id = "arxiv_" + <identifiant arXiv>` (ex. `arxiv_1804.06196`),
  également couvert par la règle de repli.

## 12. Limites de la recherche

- La recherche s'appuie sur un moteur de recherche web généraliste, pas
  sur une interrogation systématique et exhaustive de chaque base
  bibliographique spécialisée (IEEE Xplore, ACM DL, Scopus, Web of
  Science) via leurs API propres — ce corpus est donc **représentatif**,
  pas **exhaustif**, du domaine.
- Un seul preprint non évalué par les pairs a été retenu (Fraunholz et
  al. 2018), pour sa couverture unique d'aspects (légaux, éthiques,
  psychologiques) absents des autres sources — explicitement signalé
  comme tel dans le registre (`publication_type = "preprint"`), jamais
  compté comme source évaluée par les pairs dans le rapport de
  couverture.
- Une source (Urias et al. 2017) n'a pu être obtenue en texte intégral
  malgré une tentative d'accès via un miroir institutionnel public
  (OSTI.GOV) — conservée en `access_status = "metadata_only"`, sans aucun
  passage documentaire associé.
- Les lacunes de couverture thématique identifiées (`coverage_gaps` du
  rapport) ne sont comblées par aucune source ajoutée artificiellement ;
  elles restent des lacunes réelles de ce corpus à cette date.
