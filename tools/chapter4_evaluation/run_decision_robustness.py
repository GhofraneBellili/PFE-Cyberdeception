"""
Réf. tâche « campagne d'évaluation réelle RAG/LLM/système » §5 : construit
une table DE gelée RÉELLE (un seul appel LLM par candidat, réutilisant le
jeu fixe de §4) sur l'instance de référence à 3 occurrences, puis exécute
l'analyse de robustesse (`tools/chapter4_evaluation/decision_robustness.py`,
qui n'appelle plus jamais le LLM au-delà de ce point).

Si aucun provider LLM réel n'est exploitable, ce script s'ARRÊTE
proprement : aucune table DE synthétique n'est utilisée à la place (réf.
tâche §1/§5 — la table DE doit être réelle).

Coûts et paramètres de risque (`horizon`, `budget_total`, `theta_*`,
`q_by_occurrence`, `impact_by_occurrence`) : mêmes valeurs EXACTES que
`examples/orchestrator_example.py::main()` pour la même instance
(`build_small_real_instance`), dupliquées ici car non exposées comme
constantes réutilisables par ce module (aucune modification de
`examples/`, réf. « CHAPTER 4 IMPLEMENTATION FROZEN »).

Exécution :
    python -m tools.chapter4_evaluation.run_decision_robustness
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from examples.orchestrator_example import THETA
from src.annotation_validator import freeze_table
from src.annotator_llm import RealLlmAnnotator, detect_provider
from src.cost_engine import compute_cost_by_mechanism
from tools.chapter4_evaluation.decision_robustness import DEFAULT_EPSILONS, DEFAULT_N_DRAWS, run_decision_robustness
from tools.chapter4_evaluation.llm_fixed_candidates import FixedCandidatesError, build_fixed_annotation_candidates

OUT_DIR = Path("docs/chapter4/evaluation/outputs")
HORIZON = 720.0
BUDGET_TOTAL = 5000.0
Q_BY_OCCURRENCE = {"T1566@WS01": 0.5, "T1110.001@DC01": 0.6, "T1003@DC01": 0.65}
IMPACT_BY_OCCURRENCE = {"T1566@WS01": 0.14, "T1110.001@DC01": 0.35, "T1003@DC01": 0.61}
COST_INPUTS_TEMPLATE = {
    "deployment": {"t_setup": 4.0, "w_eng": 50.0, "l_data": 1.0, "w_data": 20.0, "c_integration": 50.0},
    "resource": {"r_cpu": 0.5, "c_cpu": 0.02, "r_ram": 1.0, "c_ram": 0.01, "r_disk": 5.0, "c_disk": 0.001, "r_network": 0.1, "c_network": 0.05},
    "maintenance": {"t_monitoring": 0.1, "w_eng": 50.0, "s_logs": 0.5, "w_storage": 0.01, "c_updates": 0.2},
}


def main() -> dict:
    detection = detect_provider()
    if detection.annotation_type != "real_llm":
        message = (
            f"BLOQUE (reference tache section 5) : aucun provider LLM reel exploitable "
            f"(raison : {detection.reason}). La table DE gelee doit etre reelle -- "
            f"aucun fichier decision_robustness.json n'est produit."
        )
        print(message)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "decision_robustness_blocked.txt").write_text(message + "\n", encoding="utf-8")
        return {"blocked": True, "reason": detection.reason}

    annotator: RealLlmAnnotator = detection.provider
    print(f"Provider LLM reel detecte : {annotator.config.provider} / {annotator.config.model}.")

    try:
        candidates, candidates_metadata, reusable = build_fixed_annotation_candidates()
    except FixedCandidatesError as exc:
        message = f"BLOQUE (reference tache section 5) : construction du jeu fixe de candidats impossible : {exc}"
        print(message)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "decision_robustness_blocked.txt").write_text(message + "\n", encoding="utf-8")
        return {"blocked": True, "reason": str(exc)}

    print(f"Annotation reelle (1 appel/candidat) de {len(candidates)} candidats pour geler la table DE...")
    candidates_for_freeze = []
    for candidate in candidates:
        annotations = annotator.annotate(candidate.context)
        candidates_for_freeze.append((candidate.occurrence_id, candidate.mechanism_id, candidate.location_id, annotations))
    frozen_table = freeze_table(candidates_for_freeze, annotation_set_version="decision-robustness-v1")
    de_by_candidate = frozen_table.de_by_candidate()
    print(f"Table DE gelee : {json.dumps({str(k): round(v, 4) for k, v in de_by_candidate.items()})}")

    kb_mechanisms = reusable["deception_catalog"]
    cost_inputs_by_mechanism = {mechanism_id: COST_INPUTS_TEMPLATE for mechanism_id in kb_mechanisms}
    cost_by_mechanism_full = compute_cost_by_mechanism(HORIZON, cost_inputs_by_mechanism)
    cost_by_mechanism = {mechanism_id: values["Cost"] for mechanism_id, values in cost_by_mechanism_full.items()}

    print(f"Analyse de robustesse : epsilons={DEFAULT_EPSILONS}, n_draws={DEFAULT_N_DRAWS} par niveau (aucun appel LLM)...")
    robustness = run_decision_robustness(
        reusable["system_instance"].graph,
        reusable["admissibility_report"],
        de_by_candidate=de_by_candidate,
        cost_by_mechanism=cost_by_mechanism,
        budget_total=BUDGET_TOTAL,
        q_by_occurrence=Q_BY_OCCURRENCE,
        impact_by_occurrence=IMPACT_BY_OCCURRENCE,
        theta_c=THETA,
        theta_i=THETA,
        theta_a=THETA,
    )

    output = {
        "provider": annotator.config.provider,
        "model": annotator.config.model,
        "candidates": candidates_metadata,
        "frozen_de_by_candidate": {"|".join(k): v for k, v in de_by_candidate.items()},
        "annotation_set_version": frozen_table.annotation_set_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **robustness,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "decision_robustness.json").write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    for level in robustness["levels"]:
        print(f"epsilon={level['epsilon']} : plan identique {level['identical_plan_rate']:.1%}, "
              f"pareto identique {level['identical_pareto_rate']:.1%}")
    print(f"Ecrit : {OUT_DIR / 'decision_robustness.json'}")
    return {"blocked": False, **robustness}


if __name__ == "__main__":
    main()
