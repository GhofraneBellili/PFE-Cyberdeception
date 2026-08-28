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
| pytest | ≥ 8.0 (dépendance `dev`) | Suite de tests (820 tests + 4 optionnels : 2 `pytest -m real_llm`, 2 `pytest -m real_reranker` au moment de ce document) | `tests/` |
| `urllib.request` (bibliothèque standard) | — | Appel HTTP vers un provider LLM réel (Ollama local ou endpoint OpenAI-compatible) — choix technique explicite pour éviter une nouvelle dépendance (`requests`) alors que la bibliothèque standard suffit. Envoie un `User-Agent` explicite (`DEFAULT_USER_AGENT`) — requis en pratique : le `User-Agent` par défaut d'`urllib` est bloqué (HTTP 403) par le WAF Cloudflare devant l'endpoint Groq réellement utilisé | `src/llm_provider.py` |
| `sentence-transformers` | 3.x (`sentence-transformers>=3,<4`, dépendance optionnelle `rag`) | Modèle d'embeddings sémantiques réel pour le RAG — **moteur principal** depuis la passe « remplacer le TF-IDF par un vrai RAG sémantique ». Modèle configurable (`RAG_EMBEDDING_MODEL`), jamais codé en dur : défaut `BAAI/bge-small-en-v1.5` (dimension 384), repli documenté `sentence-transformers/all-MiniLM-L6-v2`. Depuis la passe « renforcer le RAG utilisé par SP2 », la MÊME dépendance fournit aussi le reranker cross-encoder réel (`sentence_transformers.CrossEncoder`, aucune nouvelle bibliothèque) | `src/semantic_embedder.py`, `src/reranker.py` |
| `faiss-cpu` | 1.x (`faiss-cpu>=1.8,<2`, dépendance optionnelle `rag`) | Index vectoriel local (`IndexFlatIP`, produit scalaire normalisé = cosinus) pour la recherche par similarité sémantique — jamais un service externe ; repli NumPy pur si `faiss-cpu` n'est pas installable | `src/vector_index.py` |
| NumPy | 1.x/2.x (`numpy>=1.26,<3`, dépendance optionnelle `rag`) | Manipulation des vecteurs d'embeddings ; sérialisation/désérialisation portable de l'index RAG persisté (`embeddings.npy`, réf. tâche « maturation technique finale du chapitre 4 » §5-§9) ; repli d'index vectoriel pur si FAISS indisponible | `src/vector_index.py`, `src/rag_index_store.py`, `src/semantic_embedder.py` |
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

## API LLM réelle — code intégré, exécuté lors d'un smoke test technique

`src/annotator_llm.py`/`src/llm_provider.py` implémentent et testent
(mocks HTTP dans la suite standard, aucun appel réseau réel pendant
`pytest` par défaut) un provider LLM réel pour **deux familles de
service**, choisies par variable d'environnement `LLM_PROVIDER` — aucun
modèle n'est imposé dans le code :

| Provider | Configuration | Statut dans cet environnement |
|---|---|---|
| Ollama (local) | `LLM_PROVIDER=ollama`, `LLM_MODEL`, `LLM_BASE_URL` (optionnel, défaut `http://localhost:11434`) | Code implémenté et testé (mocks) ; **aucune instance Ollama détectée dans cet environnement** (`ollama` absent du PATH, aucun service sur `localhost:11434`) |
| Endpoint OpenAI-compatible | `LLM_PROVIDER=openai_compatible`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY` (optionnelle) | Code implémenté et testé (mocks) ; **réellement exercé une fois via Groq** (`LLM_BASE_URL=https://api.groq.com/openai/v1`, `LLM_MODEL=openai/gpt-oss-120b`) — interface OpenAI-compatible générique, aucun fournisseur imposé dans le code |

**Groq, avec le modèle `openai/gpt-oss-120b`, a été utilisé lors d'un
smoke test technique contrôlé** (`pytest -m real_llm -v`, vert, + un
candidat SP2 contextuel réel annoté de bout en bout) — preuve
d'intégration technique conservée dans
`docs/chapter4/outputs/groq_real_llm_smoke_test.json` (sans secret). Ceci
**ne constitue pas** une campagne expérimentale (chapitre 5) : un seul
candidat, pas de comparaison de modèles ni de mesure de qualité
d'annotation à grande échelle. `detect_provider()` (`src/annotator_llm.py`)
sélectionne automatiquement entre un provider réel et le repli
déterministe `RuleBasedStubAnnotator` selon ce qui est réellement
exploitable — voir `docs/chapter4/FINAL_TECHNICAL_REPORT.md`, section
4.4.2, pour la commande exacte permettant de reproduire une vraie
annotation localement.

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
| Reranking contextuel (§9 tâche RAG SP2) | Cross-encoder `sentence-transformers` réel (`cross-encoder/ms-marco-MiniLM-L-6-v2` par défaut, configurable `RAG_RERANKER_MODEL`) — jamais le LLM principal, jamais simulé | `src/reranker.py` |
| Persistance de l'index RAG OFFLINE/ONLINE (§5-§9 tâche « maturation technique finale ») | `chunks.json` (JSON) + `embeddings.npy` (NumPy, toujours sauvegardé) + `faiss.index` (sérialisation FAISS native si backend faiss) + `manifest.json` (hash de corpus SHA-256, modèle, dimension, schema_version) — jamais de ré-encodage au rechargement | `src/rag_index_store.py`, `tools/rag/build_index.py` |
| Résolution de `(P)` sur petite instance | Énumération exhaustive (§23), pas de solveur externe | `src/optimizer.py` |
