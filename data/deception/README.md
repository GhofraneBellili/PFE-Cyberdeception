# Catalogue normalisé de cyberdéception — emplacement attendu

Ce dossier accueillera le **catalogue normalisé PFE** de mécanismes de
cyberdéception, chargé par `src/knowledge_deception.py` (réf. architecture :
CLAUDE.md §7 « Catalogue global de cyberdéception » / §9 « Base de
connaissances cyberdéception »).

- **Fichier canonique recommandé** : `deception_catalog.json`
- **Ce que ce fichier n'est PAS** : ce catalogue n'est **pas** une copie
  brute de D3FEND, de MITRE Engage ou de tout autre format natif. Il suit le
  format interne normalisé du PFE (`catalog_version` + liste `mechanisms`,
  chaque mécanisme conforme au modèle `DeceptionMechanism` de
  `src/schemas.py`).
- **Construction future** : ce catalogue sera construit ultérieurement (phase
  distincte, non couverte par `knowledge_deception.py`) à partir de :
  - MITRE D3FEND ;
  - MITRE Engage ;
  - littérature scientifique sélectionnée sur la cyberdéception ;
  - documentation technique pertinente.
- **Traçabilité** : toute propriété d'un mécanisme doit être liée à une
  preuve documentaire (`evidence`) — voir §9.1 de CLAUDE.md.
- **Chargement** : `knowledge_deception.py` ne charge jamais un fichier par
  défaut ni ne télécharge quoi que ce soit automatiquement ; il reçoit
  toujours explicitement le chemin du catalogue via
  `load_deception_catalog(path)`.

Aucun catalogue synthétique de production n'est placé dans ce dossier : les
catalogues utilisés par les tests sont générés dans `tmp_path` (voir
`tests/test_knowledge_deception.py`).
