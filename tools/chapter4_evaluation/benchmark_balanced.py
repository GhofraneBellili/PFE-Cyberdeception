"""
Réf. tâche « améliorer réellement la qualité et la latence du moteur RAG »
§1 : benchmark ÉQUILIBRÉ couvrant les 4 types de source (ATT&CK, D3FEND,
Engage, littérature) du corpus complet (1306 chunks) -- distinct du
benchmark historique (`data/rag/rag_eval_queries.json`, 17 requêtes,
CONSERVÉ TEL QUEL, jamais modifié).

Composition (28 requêtes) :
    - 17 requêtes REPRISES telles quelles de `rag_eval_queries.json`
      (déjà relues humainement, vérité terrain inchangée) ;
    - 7 requêtes NOUVELLES ATT&CK, construites à partir du texte RÉEL du
      chunk `description` de chaque technique de base (jamais un
      sous-technique, jamais un chunk name/tactic/platforms trop court
      pour justifier une vérité terrain) -- techniques choisies AVANT
      toute évaluation car ce sont les techniques de référence du graphe
      canonique du projet (CLAUDE.md §20) : T1566, T1003, T1059, T1078,
      T1190, T1041, T1110 ;
    - 2 requêtes NOUVELLES Engage (EAC0001 API Monitoring, EAC0002 Network
      Monitoring -- chunks non encore utilisés comme vérité terrain
      ailleurs) ;
    - 2 requêtes NOUVELLES littérature (Stackelberg attack-graph deception
      study ; effet quantifié des honeytokens sur le taux de succès de
      l'attaquant -- passage distinct de celui déjà utilisé par q16).

Séparation développement/test (réf. §1, décidée ICI, AVANT toute mesure,
jamais ajustée après coup) : affectation MANUELLE fixe, stratifiée par
groupe de source, ~2 requêtes de test par groupe -- garantit que chaque
type de source est représenté dans les deux ensembles malgré leur petit
effectif. Tout réglage (A-G) n'utilise QUE `dev`; `test` n'est consommé
qu'UNE SEULE FOIS, à la toute fin, sur la configuration déjà arrêtée.

Exécution :
    python -m tools.chapter4_evaluation.benchmark_balanced
"""

from __future__ import annotations

import json
from pathlib import Path

HISTORICAL_QUERIES_PATH = Path("data/rag/rag_eval_queries.json")
OUT_PATH = Path("docs/chapter4/evaluation/outputs/benchmark_balanced.json")

# ---------------------------------------------------------------------------
# Nouvelles requêtes ATT&CK -- réf. §1, texte reel lu dans
# data/attack/staging/attack_rag_seed_19.2.json (locator="description")
# ---------------------------------------------------------------------------

NEW_ATTACK_QUERIES = [
    {
        "query_id": "attack_T1566_phishing",
        "topic": "phishing initial access",
        "source_group": "attack",
        "query": "phishing messages used by adversaries to gain initial access to victim systems",
        "query_minimal": "Phishing",
        "expected_chunk_ids": ["attack:T1566:1"],
        "justification": (
            "T1566 (Phishing), chunk description reel : \"Adversaries may send phishing messages to gain "
            "access to victim systems...\" -- technique d'entree du graphe de reference (CLAUDE.md §20)."
        ),
    },
    {
        "query_id": "attack_T1003_credential_dumping",
        "topic": "OS credential dumping",
        "source_group": "attack",
        "query": "dumping operating system credentials to obtain account login and password material",
        "query_minimal": "OS Credential Dumping",
        "expected_chunk_ids": ["attack:T1003:1"],
        "justification": (
            "T1003 (OS Credential Dumping), chunk description reel : \"Adversaries may attempt to dump "
            "credentials to obtain account login and credential material...\"."
        ),
    },
    {
        "query_id": "attack_T1059_command_scripting",
        "topic": "command and scripting interpreter",
        "source_group": "attack",
        "query": "abuse of command and script interpreters to execute commands or scripts on a system",
        "query_minimal": "Command and Scripting Interpreter",
        "expected_chunk_ids": ["attack:T1059:1"],
        "justification": (
            "T1059 (Command and Scripting Interpreter), chunk description reel : \"Adversaries may abuse "
            "command and script interpreters to execute commands, scripts, or binaries...\"."
        ),
    },
    {
        "query_id": "attack_T1078_valid_accounts",
        "topic": "valid accounts abuse",
        "source_group": "attack",
        "query": "abuse of valid compromised account credentials to bypass access controls",
        "query_minimal": "Valid Accounts",
        "expected_chunk_ids": ["attack:T1078:1"],
        "justification": (
            "T1078 (Valid Accounts), chunk description reel : \"Adversaries may obtain and abuse "
            "credentials of existing accounts...to bypass access controls...\"."
        ),
    },
    {
        "query_id": "attack_T1190_exploit_public_app",
        "topic": "exploit public-facing application",
        "source_group": "attack",
        "query": "exploiting a weakness in an internet-facing application or server to gain initial access",
        "query_minimal": "Exploit Public-Facing Application",
        "expected_chunk_ids": ["attack:T1190:1"],
        "justification": (
            "T1190 (Exploit Public-Facing Application), chunk description reel : \"Adversaries may attempt "
            "to exploit a weakness in an Internet-facing host or system...\"."
        ),
    },
    {
        "query_id": "attack_T1041_exfiltration_c2",
        "topic": "exfiltration over C2 channel",
        "source_group": "attack",
        "query": "exfiltrating stolen data over an existing command and control communication channel",
        "query_minimal": "Exfiltration Over C2 Channel",
        "expected_chunk_ids": ["attack:T1041:1"],
        "justification": (
            "T1041 (Exfiltration Over C2 Channel), chunk description reel : \"Adversaries may steal data "
            "by exfiltrating it over an existing command and control channel...\"."
        ),
    },
    {
        "query_id": "attack_T1110_brute_force",
        "topic": "brute force password guessing",
        "source_group": "attack",
        "query": "brute force guessing of account passwords when credentials or password hashes are unknown",
        "query_minimal": "Brute Force",
        "expected_chunk_ids": ["attack:T1110:1"],
        "justification": (
            "T1110 (Brute Force), chunk description reel : \"Adversaries may use brute force techniques to "
            "gain access to accounts when passwords are unknown...\"."
        ),
    },
]

# ---------------------------------------------------------------------------
# Nouvelles requêtes Engage -- réf. §1, texte reel lu dans
# data/deception/staging/engage_activity_seed_1.0.json
# ---------------------------------------------------------------------------

NEW_ENGAGE_QUERIES = [
    {
        "query_id": "engage_new_api_monitoring",
        "topic": "API monitoring",
        "source_group": "engage",
        "query": "monitor operating system API calls invoked by adversary tooling",
        "query_minimal": "API Monitoring",
        "expected_chunk_ids": ["engage:EAC0001:description", "engage:EAC0001:long_description"],
        "justification": "EAC0001 (API Monitoring) : \"Monitor local APIs that might be used by adversary tools and activity.\".",
    },
    {
        "query_id": "engage_new_network_monitoring",
        "topic": "network traffic monitoring",
        "source_group": "engage",
        "query": "capture network traffic in order to detect adversary communications",
        "query_minimal": "Network Monitoring",
        "expected_chunk_ids": ["engage:EAC0002:description", "engage:EAC0002:long_description"],
        "justification": "EAC0002 (Network Monitoring) : \"Monitor network traffic in order to detect adversary activity.\".",
    },
]

# ---------------------------------------------------------------------------
# Nouvelles requêtes littérature -- réf. §1, texte reel lu dans
# data/deception/staging/literature_evidence_seed_1.2.json
# ---------------------------------------------------------------------------

NEW_LITERATURE_QUERIES = [
    {
        "query_id": "literature_new_stackelberg_attack_graph",
        "topic": "deception in attack-graph security games",
        "source_group": "literature",
        "query": "use of deception strategies modeled within attack-graph-based security games",
        "query_minimal": "deception attack graph Stackelberg game",
        "expected_chunk_ids": ["doi_10.1007_978-3-030-64793-3_8__ev001", "doi_10.1007_978-3-030-64793-3_8__ev002"],
        "justification": (
            "Etude reelle : \"We study the use of deception in attack graph-based Stackelberg security "
            "games\" / \"the defender can strategically manipulate the attack graph through three main "
            "types of deceptive actions.\" -- directement pertinent au modele du projet (graphe d'attaque)."
        ),
    },
    {
        "query_id": "literature_new_honeytoken_risk_reduction",
        "topic": "quantified effect of honeytokens",
        "source_group": "literature",
        "query": "quantified reduction in attacker success rate attributable to honeytokens",
        "query_minimal": "honeytoken risk reduction quantified",
        "expected_chunk_ids": ["doi_10.1145_3678890.3678897__ev002"],
        "justification": (
            "Etude reelle : \"the presence of cyber deception can significantly reduce the risk that "
            "adversaries will find a true security risk by about 22% on average.\" (chunk distinct de celui "
            "deja utilise par q16_honeytoken)."
        ),
    },
]

# ---------------------------------------------------------------------------
# Répartition dev/test -- réf. §1, décidée AVANT toute évaluation, jamais
# ajustée après coup. Stratifiée par groupe de source (chaque groupe
# représenté dans les deux ensembles).
# ---------------------------------------------------------------------------

TEST_QUERY_IDS = frozenset(
    {
        # ATT&CK (7 -> 2 test)
        "attack_T1041_exfiltration_c2",
        "attack_T1110_brute_force",
        # D3FEND pur (6 -> 2 test)
        "q07_network_share",
        "q08_web_application",
        # Engage (5 -> 2 test)
        "engage_new_api_monitoring",
        "engage_new_network_monitoring",
        # Litterature pure (2 -> 1 test, l'autre en dev pour representation des deux ensembles)
        "literature_new_stackelberg_attack_graph",
        # D3FEND+Engage mixte (4 -> 1 test)
        "q12_discovery",
    }
)


def _source_group_for_reused(prefixes: list[str]) -> str:
    prefix_set = set(prefixes)
    if prefix_set == {"d3fend"}:
        return "d3fend"
    if prefix_set == {"engage"}:
        return "engage"
    if prefix_set == {"literature"}:
        return "literature"
    if prefix_set <= {"d3fend", "engage"}:
        return "d3fend_engage_mixed"
    if "literature" in prefix_set:
        return "literature_touching"
    return "mixed"


def build_balanced_benchmark() -> dict:
    historical = json.loads(HISTORICAL_QUERIES_PATH.read_text(encoding="utf-8"))
    entries = []

    for q in historical["queries"]:
        prefixes = sorted({cid.split(":")[0] if ":" in cid else "literature" for cid in q["expected_chunk_ids"]})
        entries.append(
            {
                "query_id": q["query_id"],
                "topic": q["topic"],
                "source_group": _source_group_for_reused(prefixes),
                "query": q["query"],
                "query_minimal": None,
                "expected_chunk_ids": q["expected_chunk_ids"],
                "justification": q["justification"],
                "provenance": "reused_verbatim_from_rag_eval_queries_v1.0",
            }
        )

    for q in NEW_ATTACK_QUERIES + NEW_ENGAGE_QUERIES + NEW_LITERATURE_QUERIES:
        entries.append({**q, "provenance": "new_for_balanced_benchmark_real_chunk_text"})

    for entry in entries:
        entry["split"] = "test" if entry["query_id"] in TEST_QUERY_IDS else "dev"

    by_split = {"dev": 0, "test": 0}
    by_group = {}
    for entry in entries:
        by_split[entry["split"]] += 1
        by_group.setdefault(entry["source_group"], {"dev": 0, "test": 0})[entry["split"]] += 1

    return {
        "version": "1.0",
        "description": (
            "Benchmark equilibre (ATT&CK/D3FEND/Engage/litterature) pour la campagne d'amelioration du "
            "moteur RAG -- distinct du benchmark historique (data/rag/rag_eval_queries.json), qui reste "
            "inchange et sert de reference historique."
        ),
        "corpus_reference": {"full_corpus_chunk_count": 1306, "sources": ["attack", "d3fend", "engage", "literature"]},
        "historical_benchmark_path": str(HISTORICAL_QUERIES_PATH),
        "query_count": len(entries),
        "split_counts": by_split,
        "split_counts_by_source_group": by_group,
        "split_policy": (
            "Affectation manuelle fixe decidee AVANT toute evaluation, stratifiee par groupe de source "
            "(chaque groupe represente en dev et en test) -- jamais ajustee apres consultation des scores."
        ),
        "queries": entries,
    }


def main() -> dict:
    benchmark = build_balanced_benchmark()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(benchmark, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Benchmark equilibre : {benchmark['query_count']} requetes "
          f"(dev={benchmark['split_counts']['dev']}, test={benchmark['split_counts']['test']})")
    for group, counts in benchmark["split_counts_by_source_group"].items():
        print(f"  {group}: dev={counts['dev']}, test={counts['test']}")
    print(f"Ecrit : {OUT_PATH}")
    return benchmark


if __name__ == "__main__":
    main()
