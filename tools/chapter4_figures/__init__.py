"""
Réf. tâche « finaliser les artefacts visuels du chapitre 4 ».

Génération reproductible des figures PNG C1/C2/C3/C4/C7 à partir des
sorties réelles déjà présentes dans le dépôt (`docs/chapter4/outputs/`,
`data/deception/`) — jamais de valeur inventée. C5/C6 (annotation LLM
réelle et table figée correspondante) ne sont volontairement PAS
générées ici : elles dépendent d'une exécution LLM réelle absente de cet
environnement (voir `docs/chapter4/SCREENSHOT_MANIFEST.md`).

Ce paquet est un outil de documentation (génération de figures pour le
mémoire), pas une partie du runtime SP1-SP3/optimizer — dépendance
optionnelle `matplotlib` (groupe `docs` de `pyproject.toml`), jamais
importée par `src/`.

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""
