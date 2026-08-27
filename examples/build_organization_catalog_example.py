"""
Réf. architecture : CLAUDE.md §7/§9/§10 — réf. tâche « separate knowledge
and organization capabilities » (§3, §11, §12).

Génère UNE fixture d'exemple de catalogue OPÉRATIONNEL d'organisation
(`examples/data/organization_deception_catalog.json`) à partir du
catalogue de CONNAISSANCES réel (51 mécanismes,
`data/deception/deception_catalog.json`) — jamais l'inverse : ce script ne
prétend décrire aucune organisation réelle, c'est une fixture de
démonstration pour les exemples runtime (`examples/sp1_extended_real_example.py`)
et les tests (`tests/test_organization_catalog.py`).

**Politique organisationnelle simulée** (documentée ici, pas un algorithme
générique de src/) : une entreprise de taille moyenne, sans environnement
industriel (OT/ICS), sans contrôle sur sa chaîne de compilation, et sans
infrastructure SDN — référence donc la majorité du catalogue de
connaissances, à l'exception explicite de :

- mécanismes nécessitant un environnement OT/ICS (LIT-ICS-DECOY) ;
- mécanismes nécessitant un contrôle bas niveau du pilote/NIC
  (LIT-DECOY-NIC) ;
- mécanismes nécessitant un contrôle de la chaîne de compilation/du
  binaire applicatif (LIT-SOFTWARE-TRAP, LIT-SOFTWARE-DIVERSITY,
  LIT-PLATFORM-MIGRATION) ;
- mécanismes nécessitant une infrastructure SDN (LIT-MULTIPATH-ROUTING) ;
- diffusion de média publique (D3-DPR, hors périmètre de l'équipe
  sécurité) ;
- programme de honeynet à plusieurs niveaux (D3-SHN, D3-IHN — seul un
  honeynet connecté, D3-CHN, est envisagé).

Parmi les mécanismes référencés, certains sont volontairement `enabled:
false` (évalués mais non encore déployés, pour une raison opérationnelle
explicite dans `notes`) — pas tous `true`, pour rendre visible la
distinction D_org (référencé + activé) vs simplement référencé.

`allowed_location_types` par défaut = `possible_placements` déjà
documenté par le mécanisme dans le catalogue de connaissances (choix de
politique la plus simple et non arbitraire pour cette fixture : "cette
organisation autorise chaque mécanisme activé partout où le catalogue de
connaissances documente qu'il s'applique généralement"), sauf override
explicite ci-dessous pour quelques mécanismes où l'organisation restreint
davantage (mêmes valeurs déjà auditées lors de la passe précédente pour
D3-DUC/D3-DNR/EAC0009/EAC0021, réf. docs/chapter4/CATALOG_AUDIT.md §6bis).

Exécution :
    python -m examples.build_organization_catalog_example

Sortie :
    examples/data/organization_deception_catalog.json
"""

from __future__ import annotations

import json
from pathlib import Path

from src.knowledge_deception import load_deception_catalog

CATALOG_PATH = Path("data/deception/deception_catalog.json")
OUT_PATH = Path("examples/data/organization_deception_catalog.json")

# Réf. docstring : pas d'environnement OT/ICS, pas de contrôle bas niveau
# du pilote/NIC, pas de contrôle de la chaîne de compilation, pas de SDN,
# pas de diffusion média publique par l'équipe sécurité, un seul niveau de
# honeynet envisagé.
NOT_REFERENCED = {
    "LIT-ICS-DECOY": "aucun environnement OT/ICS dans cette organisation",
    "LIT-DECOY-NIC": "hors du controle operationnel de l'equipe securite (pilote reseau bas niveau)",
    "LIT-SOFTWARE-TRAP": "l'organisation ne controle pas sa chaine de compilation applicative",
    "LIT-SOFTWARE-DIVERSITY": "l'organisation ne controle pas sa chaine de compilation applicative",
    "LIT-PLATFORM-MIGRATION": "aucune infrastructure de migration inter-plateforme en place",
    "LIT-MULTIPATH-ROUTING": "aucune infrastructure SDN disponible",
    "D3-DPR": "hors perimetre de l'equipe securite (relations publiques/marketing)",
    "D3-SHN": "un seul niveau de honeynet envisage pour l'instant (D3-CHN)",
    "D3-IHN": "un seul niveau de honeynet envisage pour l'instant (D3-CHN)",
}

# Réf. docstring : référencés (évalués) mais pas encore activés, avec la
# raison opérationnelle explicite.
REFERENCED_BUT_DISABLED = {
    "D3-CHN": "honeynet connecte planifie pour le prochain trimestre, pas encore deploye",
    "EAC0016": "necessite l'accord prealable de l'equipe reseau (changement de topologie)",
    "EAC0018": "necessite une revue du comite de gestion du changement",
    "LIT-DECEPTIVE-ATTACK-GRAPH": "necessite un engagement d'equipe red-team non encore planifie",
    "LIT-DECOY-COMPUTE": "cout de duplication du serveur d'application juge trop eleve pour l'instant",
    "LIT-HONEY-ENCRYPTION": "necessite une integration cryptographique applicative non encore evaluee",
    "LIT-DYNAMIC-IDS": "l'infrastructure IDS actuelle ne supporte pas le placement dynamique",
    "LIT-IP-ROTATION": "adressage IP statique impose par une exigence de conformite",
    "LIT-FAKE-HONEYPOT": "pas encore evalue par l'equipe securite",
    "LIT-SHADOW-HONEYPOT": "necessite une integration applicative non encore evaluee",
    "LIT-DECOY-SOURCECODE": "aucune preoccupation de fuite de code source identifiee a ce jour",
    "LIT-HONEY-CONFIG": "pas encore priorise dans la feuille de route de l'equipe web",
}

# Réf. audit précédent (docs/chapter4/CATALOG_AUDIT.md §6bis) : mêmes
# restrictions déjà justifiées documentairement, reprises ici comme choix
# organisationnels (plus jamais comme faits scientifiques D3FEND) — plus
# quelques choix organisationnels supplémentaires, cohérents avec les
# target_artifacts déjà documentés par chaque mécanisme dans le catalogue
# de connaissances (jamais un asset_type sans rapport avec le mécanisme).
ASSET_TYPE_OVERRIDES: dict[str, list[str]] = {
    "D3-DUC": ["domain_controller"],
    "D3-DNR": ["file_server", "web_application_server"],
    "D3-DF": ["file_server", "workstation", "application_server", "database_server"],
    "EAC0005": ["workstation", "domain_controller", "file_server"],
    "EAC0006": ["web_application_server", "application_server"],
    "EAC0008": ["workstation", "domain_controller"],
    "EAC0011": ["workstation", "file_server"],
    "EAC0014": ["application_server", "file_server", "workstation"],
    "EAC0022": ["workstation", "domain_controller", "file_server"],
    "LIT-HONEYWORD": ["domain_controller"],
    "LIT-HONEYTOKEN": ["database_server", "file_server"],
}
REQUIRED_SERVICES_OVERRIDES: dict[str, list[str]] = {
    "D3-DUC": ["ldap"],
    "EAC0009": ["email"],
    "EAC0021": ["email"],
}


def build_capability(mechanism_id: str, mechanism) -> dict:
    enabled = mechanism_id not in REFERENCED_BUT_DISABLED
    notes = REFERENCED_BUT_DISABLED.get(mechanism_id, "actif dans la posture de deception courante de l'organisation")
    return {
        "mechanism_id": mechanism_id,
        "enabled": enabled,
        "allowed_asset_types": ASSET_TYPE_OVERRIDES.get(mechanism_id, []),
        "allowed_location_types": list(mechanism.possible_placements),
        "required_services": REQUIRED_SERVICES_OVERRIDES.get(mechanism_id, []),
        "required_artifacts": [],
        "forbidden_asset_types": [],
        "forbidden_locations": [],
        "operational_parameters": {},
        "cost_profile_id": mechanism_id,
        "notes": notes,
    }


def main() -> None:
    kb = load_deception_catalog(CATALOG_PATH)

    unknown_not_referenced = set(NOT_REFERENCED) - set(kb.mechanisms_by_id)
    unknown_disabled = set(REFERENCED_BUT_DISABLED) - set(kb.mechanisms_by_id)
    if unknown_not_referenced or unknown_disabled:
        raise SystemExit(
            f"mechanism_id inconnu(s) du catalogue de connaissances : "
            f"{sorted(unknown_not_referenced | unknown_disabled)}"
        )

    capabilities = [
        build_capability(mechanism_id, mechanism)
        for mechanism_id, mechanism in sorted(kb.mechanisms_by_id.items())
        if mechanism_id not in NOT_REFERENCED
    ]

    organization_catalog = {
        "organization_id": "example-mid-size-enterprise",
        "catalog_version": "example-org-catalog-1.0",
        "capabilities": capabilities,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(organization_catalog, indent=2, ensure_ascii=False), encoding="utf-8")

    enabled_count = sum(1 for c in capabilities if c["enabled"])
    print(f"D_knowledge = {len(kb.mechanisms_by_id)} mecanismes")
    print(f"D_org (reference)  = {len(capabilities)} mecanismes")
    print(f"D_org (enabled)    = {enabled_count} mecanismes")
    print(f"Non reference      = {len(NOT_REFERENCED)} mecanismes")
    print(f"Sortie : {OUT_PATH}")


if __name__ == "__main__":
    main()
