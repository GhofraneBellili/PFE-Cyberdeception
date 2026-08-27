# Technologies — Chapitre 4

Tableau des technologies **réellement utilisées** dans le dépôt à la date
de ce document. Rien n'est listé ici uniquement pour paraître exhaustif :
seules les dépendances effectivement présentes dans `pyproject.toml` et
effectivement importées par du code réel sont incluses.

| Technologie | Version | Utilisation réelle | Modules |
|---|---|---|---|
| Python | ≥ 3.11 (`pyproject.toml`) | Langage d'implémentation unique du projet | tous |
| Pydantic | 2.x (`pydantic>=2,<3`) | Modèles de données validés (occurrences `T_{i,h}`, graphe, mécanisme de déception, annotation, contexte d'annotation, instance système) | `src/schemas.py` |
| NetworkX | 3.x (`networkx>=3,<4`) | Représentation du graphe d'attaque comme `DiGraph`, utilitaires de parcours (parents/enfants) | `src/graph_builder.py` |
| pytest | ≥ 8.0 (dépendance `dev`) | Suite de tests (515 tests au moment de ce document) | `tests/` |

## Technologies explicitement NON utilisées à ce stade

Conformément à la consigne de ne pas ajouter de complexité artificielle,
aucun des éléments suivants n'est présent dans le dépôt : frontend web,
dashboard, chatbot, API REST, microservices, Docker/Docker Compose,
base SQL, Redis, Kafka, MongoDB.

## Technologies attendues mais NON ENCORE utilisées

| Technologie prévue | Rôle prévu | Module prévu | Statut |
|---|---|---|---|
| API LLM réelle (à choisir) | Annotation sémantique réelle des 11 sous-métriques | `src/annotator_llm.py` | NON IMPLEMENTE — repli déterministe `RuleBasedStubAnnotator` (`model_version="rule_based_stub"`) utilisé à la place, faute d'accès à une API LLM dans cet environnement (voir `IMPLEMENTATION_REPORT.md`, section 6) |

Aucun choix définitif n'est fait pour cette ligne tant qu'une API LLM
réelle n'est pas effectivement intégrée et codée.

## Choix techniques déterministes réalisés (pas de nouvelle dépendance)

Ces briques utilisent uniquement la bibliothèque standard Python — choix
technique explicite (simple/déterministe/testable), documenté comme tel
dans `IMPLEMENTATION_REPORT.md`, pas une décision scientifique du
chapitre 3 :

| Besoin | Choix réalisé | Module |
|---|---|---|
| Vectorisation des chunks RAG | TF-IDF avec « hashing trick » (`hashlib.blake2b`), 256 dimensions, normalisation L2 | `src/rag_indexer.py` |
| Index/recherche de similarité | Index en mémoire (`dict` Python) + similarité cosinus | `src/rag_indexer.py` / `src/rag_retriever.py` |
| Résolution de `(P)` sur petite instance | Énumération exhaustive (§23), pas de solveur externe | `src/optimizer.py` |
