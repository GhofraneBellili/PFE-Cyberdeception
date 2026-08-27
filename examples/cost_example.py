"""
Réf. architecture : CLAUDE.md §15 (Coût) — exemple exécutable réel.

Calcule Cost(d;H) pour deux mécanismes candidats sur un horizon explicite,
avec des paramètres numériques illustratifs (mais réellement calculés par
src/cost_engine.py, pas recopiés à la main).

Exécution :
    python -m examples.cost_example

Sortie :
    docs/chapter4/outputs/cost_example.txt
"""

from __future__ import annotations

from pathlib import Path

from src.cost_engine import compute_cost_by_mechanism

OUT_DIR = Path("docs/chapter4/outputs")


def main() -> None:
    horizon = 720.0  # H, ex. horizon en heures (30 jours)
    mechanism_inputs = {
        "D3-DUC": {
            "deployment": {"t_setup": 4.0, "w_eng": 50.0, "l_data": 1.0, "w_data": 20.0, "c_integration": 50.0},
            "resource": {"r_cpu": 0.5, "c_cpu": 0.02, "r_ram": 1.0, "c_ram": 0.01, "r_disk": 5.0, "c_disk": 0.001, "r_network": 0.1, "c_network": 0.05},
            "maintenance": {"t_monitoring": 0.1, "w_eng": 50.0, "s_logs": 0.5, "w_storage": 0.01, "c_updates": 0.2},
        },
        "D3-DF": {
            "deployment": {"t_setup": 2.0, "w_eng": 50.0, "l_data": 0.5, "w_data": 20.0, "c_integration": 20.0},
            "resource": {"r_cpu": 0.2, "c_cpu": 0.02, "r_ram": 0.5, "c_ram": 0.01, "r_disk": 20.0, "c_disk": 0.001, "r_network": 0.05, "c_network": 0.05},
            "maintenance": {"t_monitoring": 0.05, "w_eng": 50.0, "s_logs": 1.0, "w_storage": 0.01, "c_updates": 0.1},
        },
    }

    results = compute_cost_by_mechanism(horizon, mechanism_inputs)

    lines = ["Cost(d;H) - resultats reels", "-" * 66, f"{'Mecanisme':<12}{'C_deploy':<12}{'C_resource':<12}{'C_maintenance':<16}{'Cost'}"]
    for mechanism_id, values in results.items():
        lines.append(
            f"{mechanism_id:<12}{values['C_deploy']:<12.2f}{values['C_resource']:<12.2f}"
            f"{values['C_maintenance']:<16.2f}{values['Cost']:.2f}"
        )
    lines.append("-" * 66)
    lines.append(f"Horizon H = {horizon}")
    text = "\n".join(lines) + "\n"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "cost_example.txt").write_text(text, encoding="utf-8")
    print(text)
    print(f"Resume texte : {OUT_DIR / 'cost_example.txt'}")


if __name__ == "__main__":
    main()
