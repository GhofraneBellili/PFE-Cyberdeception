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
| pytest | ≥ 8.0 (dépendance `dev`) | Suite de tests (347 tests au moment de ce document) | `tests/` |

## Technologies explicitement NON utilisées à ce stade

Conformément à la consigne de ne pas ajouter de complexité artificielle,
aucun des éléments suivants n'est présent dans le dépôt : frontend web,
dashboard, chatbot, API REST, microservices, Docker/Docker Compose,
base SQL, Redis, Kafka, MongoDB.

## Technologies attendues mais NON ENCORE utilisées

Ces technologies seront introduites uniquement lorsque le module
correspondant sera réellement implémenté (voir `IMPLEMENTATION_REPORT.md`,
statut `NON IMPLEMENTE`) :

| Technologie prévue | Rôle prévu | Module prévu | Statut |
|---|---|---|---|
| Bibliothèque d'embeddings (à choisir) | Vectorisation des chunks RAG | `src/rag_indexer.py` | NON IMPLEMENTE |
| Index/base vectoriel (à choisir) | Recherche de similarité pour le retrieval | `src/rag_indexer.py` / `src/rag_retriever.py` | NON IMPLEMENTE |
| API LLM (à choisir) | Annotation structurée des 11 sous-métriques | `src/annotator_llm.py` | NON IMPLEMENTE |
| Stratégie d'optimisation (exploration exacte/incrémentale, à choisir) | Résolution de `(P)` sur petite instance | `src/optimizer.py` | NON IMPLEMENTE |

Aucun choix définitif n'est fait pour ces lignes tant que le module
correspondant n'est pas atteint dans l'ordre d'implémentation imposé —
consigner ces choix ici uniquement lorsqu'ils sont réellement faits et
codés.
