# PFE — Cyberdéception : contrat d’architecture et d’implémentation

> **But de ce fichier**
>
> Ce fichier sert de **contrat technique unique** pour toute IA, tout développeur et tout module logiciel travaillant sur le PFE.
> Il décrit la version de référence du modèle de cyberdéception : représentation du graphe d’attaque, SP1–SP3, métriques, LLM+RAG, propagation du risque, coût et optimisation.
>
> **Source de vérité scientifique :**
>
> `docs/architecture_complete_cyberdeception_PFE.pdf`
>
> Version consolidée : **11 août 2026**.
>
> En cas de contradiction entre le code, un ancien notebook, une ancienne présentation, une ancienne chaîne MCDM/ILP ou une ancienne formulation et le document de référence, **le document de référence gagne**.
>
> Ne jamais réintroduire automatiquement d’anciens composants supprimés de l’architecture.

---

# 1. Objectif global du PFE

Le système doit déterminer :

- **quelle technique de cyberdéception** déployer ;
- **contre quelle occurrence d’attaque** ;
- **à quel emplacement** dans le système d’information ;
- sous **contraintes opérationnelles et budgétaires** ;
- afin de **réduire le risque résiduel sur les objectifs critiques**.

La sortie n’est pas une simple liste de mécanismes de déception : c’est un **plan de déploiement exécutable**.

\[
Y^*=\{(T_i,h,d,\ell)\mid y^*_{i,h,d,\ell}=1\}
\]

---

# 2. Principe fondamental : un seul problème global

Il existe **un seul problème global d’optimisation**, noté \((P)\).

Les blocs SP1, SP2 et SP3 **ne sont pas trois optimisations indépendantes**. Ils préparent les données nécessaires à \((P)\).

Chaîne conceptuelle :

\[
\boxed{
SP1 \rightarrow C_{i,h}
\quad|\quad
SP2 \rightarrow DE_{i,h,d,\ell}
\quad|\quad
SP3 \rightarrow R_{i,h}(y)
\quad|\quad
(P)\rightarrow y^*,Y^*
}
\]

Interprétation :

- **SP1 — Admissibilité :** quels couples déception–emplacement sont possibles ?
- **SP2 — Annotation :** quel effet peut-on attendre de chaque candidat admissible ?
- **SP3 — Risque :** comment une décision de déploiement modifie-t-elle la propagation et le risque ?
- **(P) — Optimisation :** quelle combinaison admissible choisir sous contraintes ?

---

# 3. Objets fondamentaux

## 3.1 Graphe d’attaque

Le système d’information est représenté par un graphe orienté :

\[
G=(V,E)
\]

avec :

\[
V=\{T_{i,h}\}
\]

où :

- \(T_i\) = technique d’attaque MITRE ATT&CK ;
- \(h\) = actif sur lequel la technique est exécutée ;
- \(T_{i,h}\) = **occurrence** de la technique \(T_i\) sur l’actif \(h\).

Une même technique ATT&CK peut donc apparaître plusieurs fois si elle est exécutée sur plusieurs actifs.

Une arête :

\[
(T_{i,h},T_{j,h'})\in E
\]

signifie :

> l’occurrence \(T_i\) exécutée sur \(h\) précède l’occurrence \(T_j\) exécutée sur \(h'\) dans le scénario d’attaque.

## 3.2 Outcomes

Les outcomes \(O_{i,h}\) sont des **attributs du nœud**.

Ils ne doivent **jamais** être ajoutés comme sommets indépendants du graphe.

## 3.3 Attributs minimums d’un nœud

Chaque occurrence \(T_{i,h}\) possède au minimum les informations conceptuelles suivantes :

\[
Attr(T_{i,h})=
\{
Tactics(T_i),
O_{i,h},
q_{i,h},
I^C_{i,h},
I^I_{i,h},
I^A_{i,h},
Critical(h),
Accessible(h)
\}
\]

Signification :

- `Tactics(T_i)` : tactiques ATT&CK associées à \(T_i\) ;
- \(O_{i,h}\) : outcomes ;
- \(q_{i,h}\) : probabilité locale de réussite ;
- \(I^C,I^I,I^A\) : impacts Confidentialité / Intégrité / Disponibilité ;
- `Critical(h)` : actif critique / objectif critique ;
- `Accessible(h)` : actif initialement accessible à l’attaquant.

---

# 4. Construction / génération du graphe

Le cœur du modèle suppose qu’un graphe \(G\) **validé** est disponible.

La génération du graphe peut être :

- manuelle ;
- semi-automatique ;
- automatique.

Procédure conceptuelle de génération :

1. inventorier les actifs du SI ;
2. enrichir les actifs : accessibilité, criticité, services, configurations, vulnérabilités, etc. ;
3. identifier les techniques ATT&CK applicables à partir de scénarios, règles expertes, vulnérabilités, journaux ou observations ;
4. instancier les occurrences \(T_{i,h}\) ;
5. établir les relations de précédence ;
6. enrichir les nœuds avec leurs attributs ;
7. identifier les nœuds d’entrée et terminaux.

### Hypothèse de validation du PFE

Pour le **cas d’usage expérimental de référence**, le graphe peut être construit **manuellement** afin de permettre une validation analytique complète.

La génération automatique du graphe peut être considérée comme un module amont futur ; elle n’est pas indispensable à la validation du modèle d’optimisation.

---

# 5. Nœuds d’entrée

Un nœud est un nœud d’entrée lorsque :

\[
Entry(T_{i,h})=1
\iff
\begin{cases}
InitialAccess\in Tactics(T_i)\\
Accessible(h)=1
\end{cases}
\]

Pour tout nœud d’entrée :

\[
\boxed{A_{i,h}(y)=1}
\]

Attention :

- \(A_{i,h}\) = atteignabilité du nœud ;
- \(P_{i,h}\) = probabilité que le nœud soit atteint **et que la technique réussisse**.

Pour une entrée :

\[
P_{i,h}=q_{i,h}
\]

car \(A_{i,h}=1\).

---

# 6. Nœuds terminaux

Un nœud \(T_{i,h}\) est terminal si :

\[
Terminal(T_{i,h})=1
\]

lorsque au moins l’une des conditions suivantes est satisfaite :

\[
Critical(h)=1
\]

ou :

\[
I^C_{i,h}\ge \theta_C
\]

ou :

\[
I^I_{i,h}\ge \theta_I
\]

ou :

\[
I^A_{i,h}\ge \theta_A
\]

On définit :

\[
V_{term}
=
\{
T_{i,h}\in V
\mid
Terminal(T_{i,h})=1
\}
\]

Dans l’implémentation de référence, les nœuds terminaux sont considérés comme **objectifs absorbants** pour l’évaluation du risque.

### Hypothèse retenue pour l’implémentation de référence

Lorsque la déception sert uniquement à réduire la continuation d’un parent vers ses vrais enfants :

\[
\boxed{
C_{i,h}=\varnothing
\quad
\forall T_{i,h}\in V_{term}
}
\]

Donc aucune variable de déploiement n’est créée sur un nœud terminal.

---

# 7. Catalogue global de cyberdéception

On travaille avec un **catalogue fermé** :

\[
\mathcal D=\{d_1,d_2,\ldots,d_m\}
\]

Le LLM ne doit **jamais inventer une nouvelle technique de cyberdéception pendant la résolution**.

Les mécanismes disponibles doivent déjà appartenir à \(\mathcal D\).

---

# 8. Base de connaissances ATT&CK

La base de connaissances offensive repose principalement sur :

`enterprise-attack.json`

Elle fournit notamment :

- identifiant ATT&CK ;
- nom ;
- description ;
- tactiques ;
- plateformes ;
- propriétés utiles au mapping et à l’annotation.

Cette base constitue la connaissance structurée des techniques \(T_i\).

---

# 9. Base de connaissances cyberdéception

Contrairement à ATT&CK, la version de référence ne suppose pas qu’une seule source fournisse tous les champs requis.

La base cyberdéception peut agréger :

- MITRE D3FEND ;
- MITRE Engage ;
- littérature scientifique sur la cyberdéception ;
- documentation technique pertinente.

Bell & Whaley peut être conservé comme **métadonnée descriptive** uniquement.

Bell & Whaley n’est **pas** une étape obligatoire de sélection et ne doit pas être réintroduit comme ancien MCDM2.

**État d’implémentation (hors runtime, `tools/deception_kb/`) :** le
staging documentaire MITRE D3FEND, le staging documentaire MITRE Engage et
le staging du corpus scientifique de cyberdéception (littérature) sont
implémentés et testés (voir README.md, étapes 5, 6 et 7). Ce sont des
couches de préparation de données situées en amont de la KB déception
normalisée — elles ne constituent pas le catalogue fermé \(\mathcal D\)
(`deception_catalog.json`) ni `knowledge_deception.py`, qui restent
inchangés par cette implémentation.

## 9.1 Pipeline de construction de la KB déception

Pipeline conceptuel :

1. collecte des sources et conservation de leur version / provenance ;
2. extraction des mécanismes et propriétés utiles ;
3. normalisation des noms, synonymes et identifiants ;
4. structuration dans un schéma commun ;
5. enrichissement des champs nécessaires à l’admissibilité et à l’annotation ;
6. traçabilité : chaque champ conserve sa source et une preuve ;
7. indexation RAG des documents et fiches structurées ;
8. versionnage du catalogue.

### Automatisation autorisée

Cette construction peut être automatisée ou semi-automatisée par :

- scripts Python déterministes ;
- extraction structurée ;
- RAG ;
- agents LLM spécialisés.

Cependant :

> les agents peuvent **extraire, structurer, normaliser et proposer** ;
> ils ne doivent pas créer des propriétés sans preuve documentaire.

Une validation humaine ou automatique est exigée pour les champs critiques.

## 9.2 Schéma conceptuel recommandé pour une fiche de déception

```json
{
  "id": "DTxx",
  "name": "...",
  "description": "...",
  "target_artifacts": ["..."],
  "requirements": ["..."],
  "possible_placements": ["..."],
  "interaction_mechanism": "...",
  "realism_factors": ["..."],
  "progression_effects": ["stop", "redirect", "contain", "delay"],
  "resource_requirements": {
    "cpu": "...",
    "ram": "..."
  },
  "maintenance_requirements": ["..."],
  "evidence": [
    {
      "source": "...",
      "passage": "..."
    }
  ],
  "version": "..."
}
```

L’implémentation peut ajouter des champs techniques supplémentaires, mais elle ne doit pas changer le sens des champs de référence.

---

# 10. SP1 — Construction de l’espace admissible

## 10.1 But exact

SP1 répond à la question :

> Pour une occurrence d’attaque \(T_{i,h}\), quels mécanismes de déception peuvent être utilisés et à quels emplacements peuvent-ils réellement être déployés ?

La sortie de SP1 est :

\[
\boxed{C_{i,h}}
\]

SP1 ne calcule ni \(P_{engage}\), ni \(Effectiveness_{prog}\), ni \(DE\), ni le risque.

---

## 10.2 Étape 1 — Mapping attaque ↔ déception

Pour chaque technique ATT&CK \(T_i\) :

\[
M_{i,d}
=
\begin{cases}
1 & \text{si }d\text{ est applicable à }T_i\\
0 & \text{sinon}
\end{cases}
\]

puis :

\[
\boxed{
D_i
=
\{
d\in\mathcal D
\mid
M_{i,d}=1
\}
}
\]

Priorité de construction du mapping :

1. utiliser d’abord les associations documentées explicitement par les sources ;
2. utiliser LLM+RAG uniquement pour compléter des lacunes sémantiques ;
3. travailler exclusivement dans le catalogue fermé \(\mathcal D\) ;
4. conserver justification, preuve et provenance pour toute association complétée.

Le LLM ne doit pas inventer un mécanisme absent du catalogue.

---

## 10.3 Étape 2 — Ensemble global des emplacements

On définit :

\[
L^{SI}
\]

comme l’ensemble des emplacements réellement disponibles dans l’inventaire du système d’information.

Exemples conceptuels :

- postes ;
- serveurs ;
- services ;
- comptes ;
- bases de données ;
- segments réseau ;
- magasins de credentials ;
- ressources applicatives.

Le graphe d’attaque **ne crée pas** \(L^{SI}\).

\(L^{SI}\) vient de l’inventaire du SI.

---

## 10.4 Étape 3 — Emplacements admissibles

Pour chaque occurrence \(T_{i,h}\) et chaque déception \(d\in D_i\) :

\[
\boxed{
L_{i,h,d}
=
\{
\ell\in L^{SI}
\mid
Allowed(d,\ell)=1
\land
RequirementsSatisfied(d,\ell)=1
\land
Relevant(T_{i,h},d,\ell)=1
\}
}
\]

### `Allowed(d, l)`

Question :

> Le mécanisme \(d\) peut-il, par nature, être placé sur ce type d’emplacement \(\ell\) ?

Origine principale :

- base de connaissances cyberdéception ;
- `possible_placements` ;
- `target_artifacts` ;
- type d’actif / service / support.

### `RequirementsSatisfied(d, l)`

Question :

> Les prérequis nécessaires au mécanisme sont-ils satisfaits sur \(\ell\) ?

Exemples :

- service requis ;
- permissions ;
- capacité ;
- plateforme ;
- intégration ;
- ressources ;
- visibilité ;
- artefacts présents.

Origine principale :

- exigences documentées du mécanisme ;
- inventaire et configuration réels du SI.

### `Relevant(T_i,h,d,l)`

Question :

> Le placement de \(d\) en \(\ell\) peut-il réellement être rencontré par l’attaquant ou influencer la continuation de l’occurrence \(T_{i,h}\) ?

Cette condition est **contextuelle**.

Elle peut dépendre de :

- l’actif d’exécution \(h\) ;
- la relation topologique entre \(h\) et \(\ell\) ;
- le voisinage de \(T_{i,h}\) dans le graphe ;
- les parents et enfants ;
- les chemins vers les objectifs terminaux ;
- la manière dont \(d\) est exposé ;
- l’accessibilité de l’emplacement.

Donc :

\[
L_{i,h,d}
\]

dépend conjointement du :

- SI ;
- graphe ;
- contexte de l’occurrence ;
- mécanisme de déception.

Le graphe influence donc \(L_{i,h,d}\), mais **n’est pas sa seule source**.

---

## 10.5 Étape 4 — Couples admissibles

Enfin :

\[
\boxed{
C_{i,h}
=
\{
(d,\ell)
\mid
d\in D_i,
\ell\in L_{i,h,d}
\}
}
\]

Une variable de décision est créée **uniquement** pour les couples appartenant à \(C_{i,h}\).

---

## 10.6 Pseudo-algorithme SP1

Entrées :

- \(G\) ;
- inventaire SI ;
- \(L^{SI}\) ;
- catalogue \(\mathcal D\) ;
- KB ATT&CK ;
- KB cyberdéception ;
- mapping documenté ATT&CK ↔ déception.

Algorithme :

```text
pour chaque technique T_i présente dans G:
    construire D_i

    pour chaque occurrence T_{i,h}:
        pour chaque d dans D_i:
            L_{i,h,d} = vide

            pour chaque emplacement l dans L^SI:
                si Allowed(d,l)
                   ET RequirementsSatisfied(d,l)
                   ET Relevant(T_{i,h},d,l):
                       ajouter l à L_{i,h,d}

        construire C_{i,h}
```

Sortie :

\[
\{C_{i,h}\}_{T_{i,h}\in V}
\]

---

# 11. SP2 — Annotation contextuelle LLM+RAG

## 11.1 But exact

SP2 répond à :

> Quel effet de déception peut-on attendre de chaque placement admissible \((T_{i,h},d,\ell)\) ?

SP2 utilise le LLM uniquement pour les dimensions sémantiques difficiles à calculer directement.

Le RAG fournit les preuves nécessaires.

---

## 11.2 Entrées du LLM

Pour chaque candidat :

\[
(T_{i,h},d,\ell)
\]

le contexte peut inclure :

- fiche ATT&CK de \(T_i\) ;
- fiche cyberdéception de \(d\) ;
- actif d’exécution \(h\) ;
- emplacement \(\ell\) ;
- attributs de \(T_{i,h}\) ;
- parents ;
- enfants ;
- chemins vers les nœuds terminaux ;
- caractéristiques pertinentes du SI ;
- passages récupérés par RAG.

### Interdiction

Le budget \(B_{total}\) ne doit **pas** être fourni à l’annotateur LLM lors de l’évaluation de l’efficacité.

Objectif : éviter un biais économique dans l’annotation.

---

## 11.3 Sous-métriques annotées par le LLM

Le LLM annote exactement les sous-métriques sémantiques suivantes.

### Realism

- \(R_{tech}\)
- \(R_{context}\)
- \(R_{perception}\)
- \(R_{behavior}\)

### InteractionLikelihood

- \(A_{object}\)
- \(A_{action}\)
- \(A_{source}\)

### Effectiveness sur la progression

- \(S_{stop}\)
- \(S_{redirect}\)
- \(S_{contain}\)
- \(S_{delay}\)

Soit **11 sous-métriques**.

---

## 11.4 Format minimum de sortie d’une annotation

Chaque sous-métrique doit avoir au minimum :

```json
{
  "metric": "R_context",
  "score": 0.80,
  "justification": "...",
  "evidence": [
    "source_or_chunk_id"
  ],
  "confidence": 0.87
}
```

Pour la traçabilité de l’implémentation, il est recommandé d’ajouter :

- version du modèle ;
- version du prompt ;
- version de la KB ;
- date ;
- identifiant unique de l’annotation.

---

## 11.5 Ce que le LLM ne calcule jamais

Le LLM ne calcule **jamais directement** :

- `Realism` ;
- `InteractionLikelihood` ;
- \(P_{engage}\) ;
- \(Effectiveness_{prog}\) ;
- \(DE\) ;
- \(\Gamma\) ;
- \(P^e\) ;
- \(A\) ;
- \(P\) ;
- \(I\) ;
- \(R\) ;
- `Cost` ;
- \(y^*\) ;
- \(Y^*\).

Ces valeurs sont calculées par programme ou solveur.

---

# 12. Métriques déterministes du modèle

## 12.1 Probabilité locale de réussite

\[
q_{i,h}\in[0,1]
\]

représente la probabilité locale que \(T_i\) réussisse sur \(h\), conditionnellement au fait que l’occurrence soit atteinte.

Formule générale :

\[
q_{i,h}
=
w_{Ca}Ca_{i,h}
+
w_HH_{i,h}
+
w_FF_{i,h}
\]

avec :

\[
w_{Ca}+w_H+w_F=1
\]

Sans justification spécifique des poids :

\[
\boxed{
q_{i,h}
=
\frac{Ca_{i,h}+H_{i,h}+F_{i,h}}{3}
}
\]

---

## 12.2 Impact agrégé

\[
I_{i,h}\in[0,1]
\]

Formule :

\[
\boxed{
I_{i,h}
=
w_CI^C_{i,h}
+
w_II^I_{i,h}
+
w_AI^A_{i,h}
}
\]

avec :

\[
w_C+w_I+w_A=1
\]

Une moyenne simple peut être utilisée si aucune pondération n’est justifiée.

---

## 12.3 Realism

\[
\boxed{
Realism(T_{i,h},d,\ell)
=
\frac{
R_{tech}
+
R_{context}
+
R_{perception}
+
R_{behavior}
}{4}
}
\]

si aucune pondération spécifique n’est justifiée.

---

## 12.4 InteractionLikelihood

\[
\boxed{
InteractionLikelihood(T_{i,h},d,\ell)
=
\frac{
A_{object}
+
A_{action}
+
A_{source}
}{3}
}
\]

si aucune pondération spécifique n’est justifiée.

Abréviation code autorisée :

`interaction_likelihood`

Éviter d’utiliser uniquement `IL` dans les structures de données si cela crée une ambiguïté.

---

## 12.5 Probabilité d’engagement

\[
\boxed{
P_{engage}(T_{i,h},d,\ell)
=
Realism(T_{i,h},d,\ell)
\times
InteractionLikelihood(T_{i,h},d,\ell)
}
\]

Le LLM ne produit pas directement \(P_{engage}\).

---

## 12.6 Effectiveness sur la progression

\[
Effectiveness_{prog}(T_{i,h},d,\ell)\in[0,1]
\]

Formule générale :

\[
Effectiveness_{prog}
=
w_SS_{stop}
+
w_RS_{redirect}
+
w_CS_{contain}
+
w_DS_{delay}
\]

avec :

\[
w_S+w_R+w_C+w_D=1
\]

Sans pondération spécifique :

\[
\boxed{
Effectiveness_{prog}
=
\frac{
S_{stop}
+
S_{redirect}
+
S_{contain}
+
S_{delay}
}{4}
}
\]

### Bénéfices secondaires

`DetectionConfidence` et `IntelligenceGain` peuvent être conservés comme bénéfices opérationnels secondaires.

Ils ne doivent **pas** être intégrés directement dans \(\Gamma\) dans la version de référence.

---

## 12.7 DeceptionEffect

\[
DE_{i,h,d,\ell}\in[0,1]
\]

représente la proportion attendue de progression neutralisée, détournée, contenue ou suffisamment retardée.

\[
\boxed{
DE_{i,h,d,\ell}
=
P_{engage}(T_{i,h},d,\ell)
\times
Effectiveness_{prog}(T_{i,h},d,\ell)
}
\]

---

# 13. Validation et gel des annotations

Avant la résolution :

\[
\boxed{
LLM+RAG
\rightarrow
Annotation
\rightarrow
Validation
\rightarrow
Table\ figée
\rightarrow
Optimisation
}
\]

Une table d’annotations propre à l’instance du SI doit être sauvegardée.

Une fois gelée :

- aucun score ne doit être recalculé arbitrairement ;
- aucun appel LLM n’est nécessaire pendant l’optimisation ;
- une même instance doit pouvoir être réoptimisée de manière reproductible.

---

# 14. SP3 — Propagation déterministe du risque

## 14.1 But exact

SP3 répond à :

> Comment les décisions \(y\) modifient-elles la propagation de l’attaque et le risque final ?

Entrées principales :

\[
G,\ q_{i,h},\ I_{i,h},\ C_{i,h},\ DE_{i,h,d,\ell},\ y
\]

Sortie :

\[
R_{i,h}(y)
\]

pour tous les nœuds, en particulier les terminaux.

---

## 14.2 Variable de décision

Pour chaque occurrence \(T_{i,h}\) et chaque couple admissible :

\[
(d,\ell)\in C_{i,h}
\]

on définit :

\[
\boxed{
y_{i,h,d,\ell}
=
\begin{cases}
1 & \text{si }d\text{ est sélectionné en }\ell\text{ contre }T_{i,h}\\
0 & \text{sinon}
\end{cases}
}
\]

---

## 14.3 Facteur résiduel de continuation

Sous l’hypothèse d’au plus un mécanisme par occurrence :

\[
\boxed{
\Gamma_{i,h}(y)
=
1
-
\sum_{(d,\ell)\in C_{i,h}}
DE_{i,h,d,\ell}\,
y_{i,h,d,\ell}
}
\]

Interprétation :

- aucune déception sélectionnée : \(\Gamma=1\) ;
- \(DE=0.56\) : \(\Gamma=0.44\).

\(\Gamma\) mesure la fraction de progression qui reste transmise depuis un parent vers ses vrais enfants.

---

## 14.4 Probabilité transmise sur une arête

Notation officielle :

\[
\boxed{P^e_{(u,g)\rightarrow(i,h)}}
\]

Ne pas remplacer cette notation conceptuelle par une autre dans la documentation.

### Parent non divergent

Si \(T_{u,g}\) possède un seul enfant :

\[
\boxed{
P^e_{(u,g)\rightarrow(i,h)}(y)
=
P_{u,g}(y)\Gamma_{u,g}(y)
}
\]

### Parent divergent

Si \(T_{u,g}\) possède plusieurs enfants :

\[
\boxed{
P^e_{(u,g)\rightarrow(i,h)}(y)
=
P_{u,g}(y)
\Gamma_{u,g}(y)
\pi_{(u,g)\rightarrow(i,h)}
}
\]

avec :

\[
\sum_{v\in Children(T_{u,g})}
\pi_{(u,g)\rightarrow v}
=
1
\]

Sans données permettant de distinguer les branches :

\[
\boxed{
\pi_{(u,g)\rightarrow(i,h)}
=
\frac{1}{|Children(T_{u,g})|}
}
\]

### Règle gelée

\[
\boxed{
\pi\text{ intervient uniquement en divergence}
}
\]

Ne jamais utiliser \(\pi\) sur une transition depuis un parent non divergent.

---

## 14.5 Convergence

Pour un nœud ayant plusieurs parents :

\[
\boxed{
A_{i,h}(y)
=
1
-
\prod_{T_{u,g}\in Parents(T_{i,h})}
\left[
1-
P^e_{(u,g)\rightarrow(i,h)}(y)
\right]
}
\]

Cette formule repose sur l’hypothèse de contributions entrantes indépendantes conditionnellement aux probabilités transmises.

C’est un agrégateur de type **noisy-OR**.

---

## 14.6 Probabilité propagée de réussite

Pour tout nœud :

\[
\boxed{
P_{i,h}(y)
=
A_{i,h}(y)
q_{i,h}
}
\]

Pour un nœud d’entrée :

\[
A_{i,h}=1
\]

donc :

\[
P_{i,h}=q_{i,h}
\]

---

## 14.7 Risque

\[
\boxed{
R_{i,h}(y)
=
P_{i,h}(y)
I_{i,h}
}
\]

Chaîne officielle complète :

\[
\boxed{
y
\rightarrow
DE
\rightarrow
\Gamma
\rightarrow
P^e
\rightarrow
A
\rightarrow
P
\rightarrow
I
\rightarrow
R
}
\]

---

# 15. Coût

Le coût total d’un mécanisme pendant l’horizon \(H\) est :

\[
\boxed{
Cost(d;H)
=
C_{deploy}(d)
+
C_{resource}(d;H)
+
C_{maintenance}(d;H)
}
\]

## 15.1 Déploiement

\[
C_{deploy}(d)
=
t_{setup}(d)w_{eng}
+
L_{data}(d)w_{data}
+
C_{integration}(d)
\]

## 15.2 Ressources

\[
C_{resource}(d;H)
=
H[
r_{CPU}(d)c_{CPU}
+
r_{RAM}(d)c_{RAM}
+
r_{disk}(d)c_{disk}
+
r_{network}(d)c_{network}
]
\]

## 15.3 Maintenance

\[
C_{maintenance}(d;H)
=
H[
t_{monitoring}(d)w_{eng}
+
S_{logs}(d)w_{storage}
+
C_{updates}(d)
]
\]

### Hypothèse de référence gelée pour l’implémentation initiale

Le coût ne dépend pas de l’emplacement :

\[
\boxed{
Cost(d,\ell;H)=Cost(d;H)
}
\]

Chaque décision sélectionnée est considérée comme une instance de déploiement facturable.

### Extension future non requise

Si un même déploiement physique \((d,\ell)\) protège plusieurs occurrences, on peut introduire :

\[
z_{d,\ell}
\]

avec :

\[
y_{i,h,d,\ell}\le z_{d,\ell}
\]

pour éviter une double facturation.

**Ne pas implémenter cette extension dans la version de référence**, sauf décision explicite ultérieure.

---

# 16. Problème global d’optimisation \((P)\)

Soit :

\[
V_{term}
=
\{
T_{i_1,h_1},
\dots,
T_{i_m,h_m}
\}
\]

Le problème est :

\[
\boxed{
(P):
\min_y
\left(
R_{i_1,h_1}(y),
\dots,
R_{i_m,h_m}(y)
\right)
}
\]

au sens d’une minimisation multiobjectif.

Le front de Pareto peut être utilisé pour identifier les solutions non dominées.

Une règle d’agrégation peut également être utilisée si elle est explicitement définie et justifiée.

---

## 16.1 Contrainte d’unicité locale

Sous l’hypothèse de référence :

\[
\boxed{
\sum_{(d,\ell)\in C_{i,h}}
y_{i,h,d,\ell}
\le 1
\quad
\forall T_{i,h}\in V
}
\]

Donc :

> au plus un couple \((d,\ell)\) peut être sélectionné pour une occurrence \(T_{i,h}\).

---

## 16.2 Contrainte budgétaire

\[
\boxed{
\sum_{T_{i,h}\in V}
\sum_{(d,\ell)\in C_{i,h}}
Cost(d;H)
y_{i,h,d,\ell}
\le
B_{total}
}
\]

---

## 16.3 Domaine

\[
\boxed{
y_{i,h,d,\ell}\in\{0,1\}}
\]

Une variable n’existe que si :

\[
(d,\ell)\in C_{i,h}
\]

Dans l’hypothèse des terminaux absorbants :

\[
C_{i,h}=\varnothing
\quad
\forall T_{i,h}\in V_{term}
\]

---

# 17. Séparation non négociable des responsabilités

## 17.1 Sources / KB / RAG

Rôle :

- fournir les connaissances ;
- fournir les preuves ;
- récupérer les passages pertinents.

Ils ne prennent pas la décision d’optimisation.

## 17.2 LLM

Rôle autorisé :

- comprendre des descriptions hétérogènes ;
- compléter les lacunes sémantiques du mapping dans un catalogue fermé ;
- annoter les 11 sous-métriques contextuelles ;
- produire justification + preuve + confiance.

Rôle interdit :

- calculer le risque ;
- calculer arbitrairement le coût ;
- sélectionner directement \(y^*\) ;
- inventer de nouvelles déceptions ;
- décider en fonction du budget pendant l’annotation.

## 17.3 Règles déterministes

Rôle :

- vérifier les placements admissibles ;
- construire \(L_{i,h,d}\) ;
- construire \(C_{i,h}\) ;
- calculer les agrégations mathématiques ;
- valider les bornes et formats.

## 17.4 Moteur probabiliste / risk engine

Rôle :

\[
\Gamma
\rightarrow
P^e
\rightarrow
A
\rightarrow
P
\rightarrow
R
\]

## 17.5 Solveur

Rôle :

- recevoir un problème entièrement défini ;
- explorer / optimiser les décisions binaires ;
- respecter les contraintes ;
- produire \(y^*\).

Le solveur ne :

- construit pas la KB ;
- n’appelle pas le LLM ;
- n’invente pas de métriques ;
- ne crée pas de nouveaux placements.

## 17.6 Reporter

Rôle :

transformer \(y^*\) en :

\[
Y^*
\]

et produire un rapport interprétable contenant, pour chaque placement :

- occurrence protégée ;
- mécanisme ;
- emplacement ;
- coût ;
- effet attendu ;
- risque avant ;
- risque après ;
- variation du risque ;
- preuves / justification associées lorsque pertinentes.

---

# 18. Ce qui est hors ligne

Deux niveaux doivent être distingués.

## 18.1 Hors ligne général

- collecte documentaire ;
- normalisation ;
- catalogue ;
- règles de placement ;
- index RAG ;
- mappings documentés ;
- versionnage.

## 18.2 Initialisation d’une instance

Pour un graphe \(G\) précis :

- construction de \(D_i\) ;
- construction de \(L_{i,h,d}\) ;
- construction de \(C_{i,h}\) ;
- annotation contextuelle ;
- validation ;
- gel de la table d’annotations.

## 18.3 Pendant l’optimisation

\[
\boxed{
Aucun\ appel\ LLM
}
\]

---

# 19. Workflow complet d’exécution

Ordre recommandé :

1. charger / construire la KB ATT&CK ;
2. charger / construire la KB cyberdéception versionnée ;
3. charger ou construire le graphe \(G\) ;
4. charger l’inventaire SI et \(L^{SI}\) ;
5. enrichir les nœuds ;
6. identifier `Entry` et `Terminal` ;
7. construire \(D_i\) ;
8. construire \(L_{i,h,d}\) ;
9. construire \(C_{i,h}\) ;
10. récupérer les preuves RAG pour chaque candidat ;
11. annoter les 11 sous-métriques ;
12. valider et geler les annotations ;
13. calculer `Realism`, `InteractionLikelihood`, \(P_{engage}\), \(Effectiveness_{prog}\), \(DE\) ;
14. calculer / charger \(Cost(d;H)\) et \(B_{total}\) ;
15. construire la fonction de risque \(R(y)\) via SP3 ;
16. construire \((P)\) ;
17. résoudre \((P)\) ;
18. produire \(y^*\) ;
19. transformer \(y^*\) en \(Y^*\) ;
20. produire le rapport explicatif.

---

# 20. Test analytique de référence — ne pas modifier sans changer la source de vérité

Ce test sert d’oracle manuel du moteur de risque.

Il ne valide pas encore toute l’optimisation ; il valide la chaîne de propagation et l’effet des déceptions.

## 20.1 Graphe

Sous-graphe :

\[
T1566
\text{ ou }
T1190
\rightarrow
T1003
\rightarrow
T1078
\rightarrow
T1059
\rightarrow
T1041
\]

Hypothèses :

- \(T1566\) et \(T1190\) sont des entrées ;
- \(T1041\) est terminal ;
- \(T1078\) possède trois enfants dans le graphe complet ;
- branche vers \(T1059\) :

\[
\pi=\frac13
\]

## 20.2 Probabilités locales

```text
T1566 : q = 0.55
T1190 : q = 0.35
T1003 : q = 0.80
T1078 : q = 0.75
T1059 : q = 0.55
T1041 : q = 0.70
```

---

## 20.3 Convergence vers T1003

Pour les entrées :

\[
P_{1566}=0.55
\]

\[
P_{1190}=0.35
\]

Donc :

\[
A_{1003}
=
1-(1-0.55)(1-0.35)
=
0.7075
\]

\[
\boxed{
P_{1003}
=
0.7075\times0.80
=
0.566
}
\]

---

## 20.4 Déception sur T1003

Hypothèses :

\[
P_{engage}(T1003,DT11)=0.70
\]

\[
Effectiveness_{prog}(T1003,DT11)=0.60
\]

Donc :

\[
DE_{1003}=0.70\times0.60=0.42
\]

\[
\Gamma_{1003}=1-0.42=0.58
\]

Puis :

\[
A_{1078}
=
0.566\times0.58
=
0.32828
\]

\[
\boxed{
P_{1078}
=
0.32828\times0.75
=
0.24621
}
\]

---

## 20.5 Déception sur T1078 + divergence

Hypothèses :

\[
P_{engage}(T1078,DT12)=0.60
\]

\[
Effectiveness_{prog}(T1078,DT12)=0.50
\]

Donc :

\[
DE_{1078}=0.30
\]

\[
\Gamma_{1078}=0.70
\]

Pour la branche vers \(T1059\) :

\[
A_{1059}
=
0.24621
\times
0.70
\times
\frac13
\approx
0.05745
\]

\[
P_{1059}
=
0.05745
\times
0.55
\approx
0.03160
\]

Puis :

\[
P_{1041}
=
0.03160
\times
0.70
\approx
0.02212
\]

---

## 20.6 Impact et risque terminal

Hypothèses :

\[
I^C=1.0
\]

\[
I^I=0.2
\]

\[
I^A=0.1
\]

avec :

\[
w_C=0.6,\quad
w_I=0.3,\quad
w_A=0.1
\]

Donc :

\[
I_{1041}
=
0.6(1.0)
+
0.3(0.2)
+
0.1(0.1)
=
0.67
\]

Risque avec les deux déceptions :

\[
\boxed{
R^{avec}_{1041}
\approx
0.02212\times0.67
\approx
0.0148
}
\]

Sans déception :

\[
\boxed{
R^{sans}_{1041}
\approx
0.0365
}
\]

Réduction relative :

\[
\boxed{
\frac{
R^{sans}-R^{avec}
}{
R^{sans}
}
\approx
59.5\%
}
\]

### Tolérance de test

Pour les tests unitaires, utiliser une tolérance numérique raisonnable, par exemple :

```python
abs(actual - expected) <= 1e-4
```

Ne pas arrondir trop tôt dans les calculs intermédiaires.

---

# 21. Important : ce que prouve le test de référence

Le test analytique prouve la cohérence de la chaîne :

\[
entrée
\rightarrow
convergence
\rightarrow
Déception\ sur\ parent
\rightarrow
\Gamma
\rightarrow
divergence\ avec\ \pi
\rightarrow
propagation
\rightarrow
impact
\rightarrow
risque
\]

Il ne prouve pas à lui seul :

- la qualité du RAG ;
- la qualité des scores LLM ;
- la qualité du catalogue complet ;
- la scalabilité ;
- l’optimalité d’un solveur sur de grandes instances.

Ces éléments doivent être validés séparément.

---

# 22. Validation du moteur de risque

Le moteur doit posséder des tests unitaires au minimum sur :

1. cas linéaire ;
2. divergence simple ;
3. convergence simple ;
4. parent divergent alimentant ensuite une convergence ;
5. comparaison sans déception / avec déception ;
6. test de référence du chapitre précédent ;
7. bornes :

\[
0\le A,P,\Gamma,R\le1
\]

lorsque les impacts sont normalisés.

---

# 23. Validation du solveur

Sur de petites instances :

1. énumérer toutes les configurations faisables ;
2. calculer leur objectif ;
3. comparer la/les meilleure(s) solution(s) exacte(s) avec le solveur.

La réduction de l’espace de décision et la scalabilité sont **hors périmètre de la première validation**.

Ne pas introduire prématurément un mécanisme de réduction qui pourrait masquer une erreur de la formulation de référence.

---

# 24. Hors périmètre de la version de référence

Ne pas implémenter sans décision explicite :

- ancienne chaîne ILP → MCDM1 → MCDM2 → MCDM3 ;
- Bell & Whaley comme étape de sélection ;
- génération libre de nouvelles déceptions par LLM ;
- réduction arbitraire de l’espace de décision ;
- Top-K arbitraire avant validation du modèle ;
- coût partagé avec \(z_{d,\ell}\) ;
- `DetectionConfidence` ou `IntelligenceGain` dans \(\Gamma\) ;
- appels LLM pendant la résolution ;
- outcomes comme nœuds ;
- \(\pi\) hors divergence.

---

# 25. Règles strictes de code

## 25.1 Langue

- commentaires : français ;
- docstrings : français ;
- identifiants de code : anglais.

## 25.2 Bornes

Toute quantité probabiliste ou score normalisé doit être vérifié :

\[
0\le x\le1
\]

Exemples :

- \(q\) ;
- impacts normalisés ;
- sous-métriques LLM ;
- `Realism` ;
- `InteractionLikelihood` ;
- \(P_{engage}\) ;
- \(Effectiveness_{prog}\) ;
- \(DE\) ;
- \(\Gamma\) ;
- \(\pi\) ;
- \(A\) ;
- \(P\) ;
- \(R\), si impact normalisé.

## 25.3 Valeurs manquantes

Une IA ou un module ne doit **jamais inventer silencieusement une valeur manquante**.

Si une donnée est absente :

- lever une erreur ;
- marquer `missing` / `unknown` ;
- ou appliquer une valeur par défaut **uniquement si cette valeur par défaut est explicitement prévue par l’architecture**.

Exemples de défauts autorisés :

- poids égaux lorsque aucune pondération n’est justifiée ;
- branches équiprobables lorsque aucune information sur \(\pi\) n’est disponible.

## 25.4 Tests

`pytest` obligatoire.

Aucun module critique ne doit être considéré terminé sans tests verts.

## 25.5 Traçabilité

Chaque fonction importante doit référencer le concept du document qu’elle implémente.

Préférer un commentaire stable par nom de section, par exemple :

```python
# Réf. architecture : "4.7 Facteur résiduel de continuation"
```

plutôt qu’un numéro de page fragile.

---

# 26. Modules recommandés

Structure logique recommandée :

```text
src/
├── schemas.py
├── graph_builder.py
├── knowledge_attack.py
├── knowledge_deception.py
├── admissibility.py
├── rag_indexer.py
├── rag_retriever.py
├── annotator_llm.py
├── annotation_validator.py
├── risk_engine.py
├── cost_engine.py
├── optimizer.py
└── reporter.py
```

Responsabilités :

### `schemas.py`

Structures de données communes.

### `graph_builder.py`

- chargement ;
- construction du graphe ;
- attributs ;
- Entry ;
- Terminal.

### `knowledge_attack.py`

Accès à `enterprise-attack.json`.

### `knowledge_deception.py`

- catalogue \(\mathcal D\) ;
- fiches ;
- mapping ;
- preuves ;
- versionnage.

### `admissibility.py` — SP1

- \(D_i\) ;
- `Allowed` ;
- `RequirementsSatisfied` ;
- `Relevant` ;
- \(L_{i,h,d}\) ;
- \(C_{i,h}\).

### `rag_indexer.py`

- ingestion ;
- chunking ;
- métadonnées ;
- embeddings ;
- index.

### `rag_retriever.py`

Récupération des passages pertinents.

### `annotator_llm.py` — partie sémantique de SP2

Annotation des 11 sous-métriques.

### `annotation_validator.py`

- validation JSON ;
- bornage ;
- preuves ;
- confiance ;
- gel.

### `risk_engine.py` — SP3

- \(q\) ;
- \(I\) ;
- agrégations ;
- \(DE\) si souhaité dans ce module ou module métriques ;
- \(\Gamma\) ;
- \(P^e\) ;
- \(A\) ;
- \(P\) ;
- \(R\).

### `cost_engine.py`

Calcul de :

\[
Cost(d;H)
\]

### `optimizer.py`

Construction et résolution de \((P)\).

### `reporter.py`

Construction de \(Y^*\) et explication de la solution.

---

# 27. Schéma minimal conseillé pour le contexte d’annotation

Le format exact de code peut évoluer, mais il doit représenter au minimum :

```json
{
  "attack_occurrence": {
    "technique_id": "Txxxx",
    "asset": "h",
    "attributes": {}
  },
  "deception": {
    "id": "DTxx",
    "name": "..."
  },
  "placement": "l",
  "graph_context": {
    "parents": [],
    "children": [],
    "terminal_paths": []
  },
  "system_context": {},
  "retrieved_evidence": []
}
```

---

# 28. Règles d’explicabilité

Toute décision finale doit être traçable selon quatre niveaux :

\[
\boxed{
Connaissance
\rightarrow
Annotation
\rightarrow
Calcul
\rightarrow
Décision
}
\]

Exemple :

1. **Connaissance**
   - source ATT&CK / D3FEND / Engage / article ;
2. **Annotation**
   - score ;
   - justification ;
   - preuve ;
   - confiance ;
3. **Calcul**
   - `Realism` ;
   - `InteractionLikelihood` ;
   - \(P_{engage}\) ;
   - \(Effectiveness_{prog}\) ;
   - \(DE\) ;
   - risque ;
4. **Décision**
   - \(y^*=1\) ou \(0\) ;
   - coût ;
   - effet ;
   - variation de risque.

---

# 29. Invariants à ne jamais violer

Toute IA qui modifie le code doit respecter les invariants suivants.

1. Il n’existe qu’un seul problème global \((P)\).
2. SP1, SP2, SP3 ne sont pas des optimisations indépendantes.
3. Les nœuds sont des occurrences \(T_{i,h}\).
4. Les outcomes sont des attributs.
5. \(D_i\) dépend principalement de \(T_i\).
6. \(L_{i,h,d}\) est contextuel au SI, au graphe, à \(h\), à \(d\) et à \(\ell\).
7. Une variable \(y\) n’existe que pour un couple admissible.
8. Le LLM ne calcule pas le risque.
9. Le LLM ne résout pas \((P)\).
10. Aucun appel LLM pendant l’optimisation.
11. Les annotations sont validées puis gelées.
12. \(P_{engage}=Realism\times InteractionLikelihood\).
13. \(DE=P_{engage}\times Effectiveness_{prog}\).
14. La déception d’un parent agit via \(\Gamma\) sur sa continuation vers ses enfants.
15. \(\pi\) intervient uniquement en divergence.
16. Une convergence utilise le noisy-OR.
17. \(P=Aq\).
18. \(R=PI\).
19. Le coût de référence est indépendant de \(\ell\).
20. Le solveur choisit uniquement parmi les décisions déjà admissibles.

---

# 30. Résumé ultra-court pour une autre IA

Si une IA ne lit qu’une seule section, elle doit retenir ceci :

```text
ENTRÉES
  - graphe d’attaque G avec nœuds T_{i,h}
  - inventaire SI et emplacements L^SI
  - KB ATT&CK
  - catalogue fermé de cyberdéception
  - budget

SP1 — ADMISSIBILITÉ
  T_i -> D_i
  (T_{i,h}, d) -> L_{i,h,d}
  -> C_{i,h}

SP2 — ANNOTATION
  RAG + LLM annotent uniquement 11 sous-métriques
  programme calcule :
  Realism
  InteractionLikelihood
  P_engage
  Effectiveness_prog
  DE
  annotations validées puis gelées

SP3 — RISQUE
  y -> Gamma -> P^e -> A -> P -> I -> R
  pi uniquement en divergence
  noisy-OR en convergence

OPTIMISATION
  y_{i,h,d,l} binaire
  au plus 1 couple par occurrence
  contrainte de budget
  minimisation multiobjectif des risques terminaux

SORTIE
  y*
  Y* = plan de déploiement optimal

INTERDIT
  - LLM qui invente une déception
  - LLM qui calcule R ou y*
  - appel LLM pendant le solveur
  - outcomes comme nœuds
  - pi hors divergence
  - anciens MCDM/ILP réintroduits automatiquement
```

---

# 31. État d’implémentation

À mettre à jour uniquement lorsque le module existe et que ses tests sont verts.

- [x] `schemas.py`
- [x] `graph_builder.py`
- [x] `knowledge_attack.py`
- [x] `knowledge_deception.py`
- [x] `admissibility.py`
- [ ] `rag_indexer.py`
- [ ] `rag_retriever.py`
- [ ] `annotator_llm.py`
- [ ] `annotation_validator.py`
- [x] `risk_engine.py`
- [x] `cost_engine.py`
- [ ] `optimizer.py`
- [ ] `reporter.py`
- [x] test analytique de référence
- [ ] validation exhaustive du solveur sur petite instance

---

# 32. Règle finale

Lorsqu’une information n’est pas définie par l’architecture :

> **ne pas l’inventer et ne pas modifier implicitement le modèle.**

Documenter le point comme :

`OPEN_DECISION`

et demander une décision explicite avant de changer :

- une hypothèse ;
- une formule ;
- une métrique ;
- une contrainte ;
- une responsabilité ;
- une source de données ;
- une règle de placement ;
- la fonction objectif.

# Git / GitHub — règle de livraison

Le dépôt GitHub distant `origin` constitue le dépôt de référence du projet.

Après chaque tâche d'implémentation demandée :

1. modifier uniquement les fichiers correspondant à la tâche ;
2. exécuter les tests concernés ;
3. ne jamais pousser si les tests échouent ;
4. afficher un résumé des modifications ;
5. exécuter `git status` ;
6. ajouter uniquement les fichiers pertinents avec `git add` ;
7. créer un commit avec un message explicite décrivant l'étape réalisée ;
8. pousser automatiquement le commit vers la branche distante courante avec `git push`.

Règles de sécurité :
- ne jamais utiliser `git push --force` ;
- ne jamais supprimer l'historique Git ;
- ne jamais réécrire un commit déjà poussé ;
- ne jamais pousser `.venv/`, secrets, tokens, clés API ou fichiers contenant des identifiants sensibles ;
- ne jamais changer de branche sans instruction explicite ;
- si le push échoue pour une raison d'authentification, de conflit ou de divergence avec le dépôt distant, arrêter et signaler le problème au lieu de forcer ;
- avant chaque push, vérifier que les tests de l'étape sont verts.

Format recommandé des commits :

`type(module): description courte`

Exemples :
- `feat(schemas): add validated Pydantic data models`
- `feat(graph): implement attack graph builder`
- `feat(sp1): implement admissibility candidate generation`
- `test(risk): add reference propagation tests`
- `fix(sp1): correct placement relevance validation`

# Documentation technique — README.md

Après validation de chaque étape technique, README.md doit être mis à jour
avec l'implémentation réellement réalisée, les entrées/sorties, tests,
provenance, limites et commit de validation.
