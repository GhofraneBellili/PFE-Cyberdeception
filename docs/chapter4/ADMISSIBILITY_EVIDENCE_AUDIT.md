# Audit documentaire des prérequis d'admissibilité SP1

> Objectif : vérifier si les sources déjà versionnées (D3FEND, MITRE
> Engage, littérature) permettent de renseigner
> `required_asset_types`/`required_services`/`required_artifacts`,
> `possible_placements`, ou des contraintes de déploiement explicites
> pour les 3 mécanismes du catalogue réel (`D3-DF`, `D3-DUC`, `D3-DNR`),
> sans jamais transformer une recommandation en prérequis obligatoire ni
> inventer une exigence pour obtenir artificiellement des candidats
> admissibles.
>
> Méthode : lecture intégrale de `definition`, `kb-article` (sections
> « How it works » / « Considerations » / « Examples »), `artifacts` et
> `relation_path` pour chacun des 3 mécanismes dans
> `data/deception/staging/d3fend_deception_seed_1.5.0.json` et
> `d3fend_attack_mapping_seed_1.5.0.json` ; recherche croisée dans
> `data/deception/staging/engage_activity_seed_1.0.json` et
> `literature_evidence_seed_1.2.json` (18 passages).
>
> Règle de décision appliquée systématiquement : une affirmation en
> section « How it works » (factuelle/définitionnelle) est considérée
> comme un candidat sérieux ; une affirmation en section
> « Considerations » utilisant « should »/« may »/« could » est une
> recommandation, jamais un prérequis. Un « Example » isolé n'est jamais
> généralisé en règle.

---

## D3-DF — Decoy File

**Source** : `d3fend:D3-DF` (`data/deception/staging/d3fend_deception_seed_1.5.0.json`).

| Propriété envisagée | Valeur candidate | Source / passage | Locator | Justification | Décision |
|---|---|---|---|---|---|
| `possible_placements` (emplacement) | `"network_share"` (en complément de `"filesystem"` déjà dérivé de `target_artifacts=["d3f:File"]`) | *"The decoy file is made available as a local or network resource."* | `d3f:kb-article`, section « How it works » | Affirmation factuelle et définitionnelle (pas une recommandation) : le fichier leurre est explicitement placé soit en local, soit en ressource réseau — deux catégories de placement distinctes | **RETENUE** — ajoutée à `admissibility_profile.allowed_location_types` et `possible_placements` via `tools/deception_kb/catalog_builder.py` (table `KB_ARTICLE_LOCATION_ADDITIONS`, provenance citée en commentaire) |
| `required_asset_types` | — | *"Properties of the file such as cryptographic checksums, file creation date, file modified date, file size, file owner etc may be modified to improve the credibility of the file."* | `d3f:kb-article`, section « Considerations » | Recommandation de réalisme (« may be modified »), ne décrit aucun type d'actif requis | **REJETÉE** — recommandation, pas un prérequis de placement |
| `required_asset_types` | — | *"A CSV file with decoy user credentials is placed on a system."* | `d3f:kb-article`, section « Examples » | Un seul exemple illustratif, ne généralise à aucun type d'actif requis | **REJETÉE** — exemple isolé, pas une règle |
| `required_services`/`required_artifacts` | — | (aucune mention dans D3FEND) | — | Aucune affirmation trouvée | **REJETÉE** (absence de preuve, pas une conclusion « aucun prérequis ») |

**MITRE Engage / littérature.** Aucune activité Engage ne nomme
« Decoy File » ni ne décrit un mécanisme équivalent avec une précision
suffisante pour en dériver un prérequis (cohérent avec l'OPEN_DECISION
existante interdisant le rapprochement automatique D3FEND/Engage — voir
`tools/deception_kb/README.md`). Aucun passage de littérature
(`literature_evidence_seed_1.2.json`) ne mentionne explicitement les
fichiers leurres ou leurs contraintes de placement.

**Conclusion D3-DF.** `required_asset_types`/`required_services`/
`required_artifacts` restent **vides** (`unknown`, pas `known_none` —
voir section « Distinction aucun/inconnu » ci-dessous).
`allowed_location_types`/`possible_placements` enrichis avec
`network_share`.

---

## D3-DUC — Decoy User Credential

**Source** : `d3fend:D3-DUC`.

| Propriété envisagée | Valeur candidate | Source / passage | Locator | Justification | Décision |
|---|---|---|---|---|---|
| `required_asset_types` | `["domain_controller"]` ou `["workstation"]` (exclusif) | *"A credential may be: Domain username and password / Local system username and password."* | `d3f:kb-article`, section « How it works » | Décrit DEUX catégories possibles (« may be ») sans trancher : choisir l'une des deux reviendrait à inventer une restriction que le texte ne pose pas — le texte affirme au contraire une portée large (domaine OU local) | **REJETÉE** — le texte ne restreint pas à un type d'actif unique ; en choisir un serait une invention |
| `required_asset_types`/`required_services`/`required_artifacts` | — | *"Decoy credentials should be integrated with a larger decoy environment to ensure that when decoy credentials are compromised, the credentials are used to interact with a decoy asset that is being monitored."* | `d3f:kb-article`, section « Considerations » | Recommandation explicite (« should be integrated »), pas une exigence de placement | **REJETÉE** — recommandation, pas un prérequis |
| `maintenance_requirements` (hors admissibilité SP1) | — | *"Continuous maintenance and updates are needed to ensure the legitimacy of the larger decoy environment..."* | `d3f:kb-article`, section « Considerations » | Concerne la maintenance opérationnelle, pas l'admissibilité `Allowed`/`RequirementsSatisfied`/`Pertinent` de SP1 (§10.4) — hors périmètre de cet audit, qui porte uniquement sur les champs consommés par `src/admissibility.py` | **HORS PÉRIMÈTRE** — non traité pour ne pas élargir cette passe au-delà de l'objectif (fermer la rupture SP1) |

**MITRE Engage / littérature.** Aucune activité Engage ne nomme
explicitement les identifiants leurres avec une précision suffisante
(cohérent avec l'OPEN_DECISION D3FEND/Engage). Aucun passage de
littérature ne traite spécifiquement des contraintes de placement des
identifiants leurres.

**Conclusion D3-DUC.** Aucune propriété d'admissibilité ajoutée.
`required_asset_types`/`required_services`/`required_artifacts` restent
**vides** (`unknown`).

---

## D3-DNR — Decoy Network Resource

**Source** : `d3fend:D3-DNR`.

| Propriété envisagée | Valeur candidate | Source / passage | Locator | Justification | Décision |
|---|---|---|---|---|---|
| `required_asset_types` | `["web_application_server", "file_server"]` | *"Decoy network resources are deployed to web application servers, network file shares, or other network based sharing services."* | `d3f:kb-article`, section « How it works » | Affirmation factuelle et définitionnelle (pas une recommandation, section « How it works ») nommant explicitement deux catégories d'actifs de déploiement | **RETENUE, AVEC RÉSERVE DOCUMENTÉE** — voir note ci-dessous sur la clause ouverte « or other » |
| `required_asset_types` (troisième catégorie) | — (non encodée) | *"...or other network based sharing services."* | idem | Clause explicitement ouverte (« or other ») : ne nomme aucune catégorie concrète supplémentaire — l'encoder obligerait à inventer un type d'actif non nommé | **REJETÉE** — rien de concret à encoder sans inventer |
| `required_asset_types`/déploiement | — | *"Developing a deployment and placement strategy for the decoy network resource."* | `d3f:kb-article`, section « Considerations » | Recommandation générique de planification, ne nomme aucun type d'actif ou service | **REJETÉE** — trop générique |
| — | — | *"Personnel responsible for creation of decoy networks should consider the potential for resource exhaustion through denial of service attacks."* | `d3f:kb-article`, section « Considerations » | Recommandation de gestion de risque opérationnel, pas une contrainte de placement | **REJETÉE** — hors périmètre admissibilité |
| — | — | *"Honeypots are typically used to mimic a known system with fake vulnerabilities."* / *"Tarpits are used to monitor unallocated IP space..."* | `d3f:kb-article`, section « Examples » | Exemples illustratifs (honeypots, tarpits), ne généralisent à aucune exigence | **REJETÉE** — exemples isolés |

**Réserve documentée sur la valeur RETENUE.** La phrase se termine par
« or other network based sharing services », une clause ouverte qui
indique que la liste « web application servers, network file shares »
est **illustrative des catégories les plus citées**, pas nécessairement
exhaustive au sens strict. La décision de l'encoder malgré tout comme
`required_asset_types` repose sur : (1) la phrase figure en section
« How it works » (factuelle), pas « Considerations » (recommandation) ;
(2) elle nomme explicitement deux catégories concrètes et reconnaissables
d'actifs, contrairement aux autres passages rejetés dans cet audit ;
(3) la clause ouverte elle-même n'est PAS encodée (aucune troisième
catégorie inventée). Cette réserve est délibérément rendue visible ici
plutôt que dissimulée : un lecteur du mémoire doit pouvoir juger cette
zone grise par lui-même.

**MITRE Engage / littérature.** Recherche par mots-clés (« decoy network
resource », « network resource », « file share ») dans
`engage_activity_seed_1.0.json` : aucune activité ne nomme ni ne décrit
un mécanisme suffisamment proche pour corroborer ou contredire la valeur
retenue (activités les plus proches par mots-clés : `EAC0007` Network
Diversity, `EAC0020` Isolation — génériques, sans lien nommé explicite).
Recherche dans `literature_evidence_seed_1.2.json` : deux passages
mentionnent les honeypots en général (`usenixsec2004_provos_virtual_
honeypot_framework__ev001`, `doi_10.1109_csac.2003.1254322__ev001`) mais
restent définitionnels/génériques ("a honeypot is a closely monitored
network decoy...") — ne nomment aucun type d'actif précis et ne
corroborent ni n'infirment la valeur D3FEND retenue. **REJETÉS comme
source de `required_asset_types`** : trop généraux.

**Conclusion D3-DNR.** `required_asset_types = ["web_application_server",
"file_server"]` ajouté via `tools/deception_kb/catalog_builder.py`.
`required_services`/`required_artifacts` restent **vides** (`unknown`).

---

## Distinction « aucun prérequis » vs « prérequis inconnu »

**Constat sur `DeceptionAdmissibilityProfile` (`src/schemas.py`) et
`evaluate_requirements_satisfied` (`src/admissibility.py`).** Une liste
vide de `required_asset_types`/`required_services`/`required_artifacts`
est aujourd'hui interprétée uniformément comme « information inconnue »
(`RequirementsSatisfied="undetermined"`, politique prudente
OPEN_DECISION 4). Le schéma actuel ne distingue donc pas explicitement :

- **A. aucun prérequis exigé par le mécanisme** (`known_none`) ;
- **B. prérequis inconnus faute d'information** (`unknown`) ;
- **C. prérequis connus et listés** (`known_requirements` — déjà bien
  représenté par une liste non vide).

**Résultat de l'audit ci-dessus, appliqué aux 3 mécanismes réels : aucun
cas de type A (`known_none`) n'a été trouvé.** Pour chaque propriété
laissée vide (D3-DF : les trois listes ; D3-DUC : les trois listes ;
D3-DNR : `required_services`/`required_artifacts`), l'audit documentaire
n'a trouvé ni preuve d'une exigence, ni affirmation positive que
« aucune contrainte de placement n'existe » — c'est une absence
d'information (cas B), pas une conclusion documentée d'absence de
prérequis (cas A). Le cas C est déjà correctement représenté par une
liste non vide (nouveau cas : `D3-DNR.required_asset_types`).

**Décision : ne PAS introduire de champ de statut explicite
(`known_none`/`known_requirements`/`unknown`) dans cette passe.** Le
schéma actuel (liste vide → `undetermined`) est **sémantiquement correct
pour les données réellement disponibles aujourd'hui** : chaque liste
vide reflète effectivement une absence d'information, pas une absence de
prérequis confirmée — la conflation que ce point de la tâche
craignait ne se produit donc pas en pratique sur ce catalogue. Ajouter un
champ de statut supplémentaire sans un seul cas `known_none` réel à
représenter ajouterait de la complexité sans changer aucun résultat
observable, à l'encontre de la consigne de ne pas ajouter de complexité
non nécessaire. **Cette distinction reste une extension légitime et
documentée pour une future itération** si un mécanisme avec un « aucun
prérequis » réellement établi par une source est ajouté au catalogue —
à réévaluer à ce moment-là, pas anticipée ici.

---

## Synthèse des décisions RETENUES (implémentées dans `catalog_builder.py`)

| Mécanisme | Champ | Valeur ajoutée | Preuve |
|---|---|---|---|
| `D3-DF` | `admissibility_profile.allowed_location_types` / `possible_placements` | `+ "network_share"` | D3FEND kb-article, « How it works » : *"made available as a local or network resource"* |
| `D3-DNR` | `admissibility_profile.required_asset_types` | `["web_application_server", "file_server"]` | D3FEND kb-article, « How it works » : *"deployed to web application servers, network file shares, or other network based sharing services"* |

Aucune autre propriété n'a été jugée suffisamment justifiée par les
sources déjà versionnées. `D3-DUC` ne reçoit aucun enrichissement dans
cette passe.
