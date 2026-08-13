# Base de connaissances ATT&CK — emplacement attendu

Ce dossier est l'emplacement prévu pour le fichier de connaissance offensive
utilisé par `src/knowledge_attack.py` (réf. architecture : CLAUDE.md §8
« Base de connaissances ATT&CK »).

- **Fichier attendu** : `enterprise-attack.json`
- **Provenance** : il doit provenir d'une source MITRE ATT&CK officielle
  (bundle STIX Enterprise ATT&CK). Ce fichier n'est **pas** inclus dans ce
  dépôt et ne doit **jamais** être généré artificiellement.
- **Utilisation** : `knowledge_attack.py` ne lit jamais un chemin codé en
  dur. `load_attack_knowledge(path, ...)` reçoit explicitement le chemin
  vers ce fichier ; aucun chargement automatique ni téléchargement n'est
  effectué par le code.

Les tests de `tests/test_knowledge_attack.py` n'utilisent jamais ce fichier :
ils construisent uniquement de petits bundles STIX synthétiques dans
`tmp_path`, afin que la suite de tests et la CI puissent s'exécuter hors
ligne, sans dépendre d'Internet ni du vrai `enterprise-attack.json`.
