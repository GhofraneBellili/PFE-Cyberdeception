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
| pytest | ≥ 8.0 (dépendance `dev`) | Suite de tests (697 tests + 2 optionnels `pytest -m real_llm` au moment de ce document) | `tests/` |
| `urllib.request` (bibliothèque standard) | — | Appel HTTP vers un provider LLM réel (Ollama local ou endpoint OpenAI-compatible) — choix technique explicite pour éviter une nouvelle dépendance (`requests`) alors que la bibliothèque standard suffit | `src/llm_provider.py` |
| `sentence-transformers` | 3.x (`sentence-transformers>=3,<4`, dépendance optionnelle `rag`) | Modèle d'embeddings sémantiques réel pour le RAG — **moteur principal** depuis cette passe (réf. tâche « remplacer le TF-IDF par un vrai RAG sémantique »). Modèle configurable (`RAG_EMBEDDING_MODEL`), jamais codé en dur : défaut `BAAI/bge-small-en-v1.5` (dimension 384), repli documenté `sentence-transformers/all-MiniLM-L6-v2` | `src/semantic_embedder.py` |
| `faiss-cpu` | 1.x (`faiss-cpu>=1.8,<2`, dépendance optionnelle `rag`) | Index vectoriel local (`IndexFlatIP`, produit scalaire normalisé = cosinus) pour la recherche par similarité sémantique — jamais un service externe ; repli NumPy pur si `faiss-cpu` n'est pas installable | `src/vector_index.py` |
| matplotlib | 3.x (`matplotlib>=3.8,<4`, dépendance optionnelle `docs`) | Génération reproductible des figures PNG du chapitre 4 à partir des sorties réelles du dépôt — outil de documentation, jamais importé par `src/` (voir `pyproject.toml`, groupe `[project.optional-dependencies].docs`) | `tools/chapter4_figures/` |

## Technologies explicitement NON utilisées à ce stade

Conformément à la consigne de ne pas ajouter de complexité artificielle,
aucun des éléments suivants n'est présent dans le dépôt : frontend web,
dashboard, chatbot, API REST, microservices, Docker/Docker Compose,
base SQL, Redis, Kafka, MongoDB, bibliothèque cliente HTTP tierce
(`requests`), service de base vectorielle externe managé (Chroma serveur,
Pinecone, Weaviate). **FAISS est utilisé, mais exclusivement en local, en
mémoire, sans service externe** — voir la ligne `faiss-cpu` ci-dessus,
distincte de ce qui est exclu ici.

## API LLM réelle — code intégré, non exécutée dans cet environnement

`src/annotator_llm.py`/`src/llm_provider.py` implémentent et testent
(mocks HTTP, aucun appel réseau réel pendant `pytest`) un provider LLM
réel pour **deux familles de service**, choisies par variable
d'environnement `LLM_PROVIDER` — aucun modèle n'est imposé dans le code :

| Provider | Configuration | Statut dans cet environnement |
|---|---|---|
| Ollama (local) | `LLM_PROVIDER=ollama`, `LLM_MODEL`, `LLM_BASE_URL` (optionnel, défaut `http://localhost:11434`) | Code implémenté et testé (mocks) ; **aucune instance Ollama détectée dans cet environnement** (`ollama` absent du PATH, aucun service sur `localhost:11434`) |
| Endpoint OpenAI-compatible | `LLM_PROVIDER=openai_compatible`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY` (optionnelle) | Code implémenté et testé (mocks) ; **aucune configuration fournie dans cet environnement** |

`detect_provider()` (`src/annotator_llm.py`) sélectionne automatiquement
entre un provider réel et le repli déterministe `RuleBasedStubAnnotator`
selon ce qui est réellement exploitable — voir
`docs/chapter4/FINAL_TECHNICAL_REPORT.md`, section 4.4.2, pour la
commande exacte permettant de produire une vraie annotation localement.

## Choix techniques déterministes réalisés (pas de nouvelle dépendance)

Ces briques utilisent uniquement la bibliothèque standard Python — choix
technique explicite (simple/déterministe/testable), documenté comme tel
dans `IMPLEMENTATION_REPORT.md`, pas une décision scientifique du
chapitre 3 :

| Besoin | Choix réalisé | Module |
|---|---|---|
| Vectorisation des chunks RAG (baseline lexicale, sans dépendance) | TF-IDF avec « hashing trick » (`hashlib.blake2b`), 256 dimensions, normalisation L2 | `src/rag_indexer.py` |
| Index/recherche de similarité (baseline lexicale) | Index en mémoire (`dict` Python) + similarité cosinus | `src/rag_indexer.py` / `src/rag_retriever.py` |
| Vectorisation des chunks RAG (moteur principal) | Embeddings `sentence-transformers` réels, normalisés L2 | `src/semantic_embedder.py` |
| Index/recherche de similarité (moteur principal) | Index vectoriel FAISS `IndexFlatIP` (repli NumPy pur si FAISS indisponible) | `src/vector_index.py` |
| Fusion lexical/sémantique | `score = alpha·score_sémantique + (1-alpha)·score_lexical`, alpha=0.8 retenu après évaluation réelle (Recall@5/MRR@5/nDCG@5 sur `data/rag/rag_eval_queries.json`) | `src/rag_retriever.py::retrieve_hybrid` |
| Résolution de `(P)` sur petite instance | Énumération exhaustive (§23), pas de solveur externe | `src/optimizer.py` |
