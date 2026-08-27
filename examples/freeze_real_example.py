"""
Réf. architecture : CLAUDE.md §13 (Validation et gel des annotations) —
tâche « gel réel après LLM ».

Commande UNIQUE permettant, après une vraie exécution LLM
(`python -m examples.annotator_llm_real_example`, qui produit
`docs/chapter4/outputs/llm_annotation_real.json`), de produire :

    docs/chapter4/outputs/frozen_annotations_real.json
    docs/chapter4/outputs/frozen_annotations_real.csv

`Realisme`/`P_interaction`/`P_engagement`/`Effet_prog`/`DE` sont
calculés PAR CODE (`src.annotation_validator`) — jamais par le LLM
(§11.5). Aucune valeur dérivée ne vient de la sortie brute du modèle.

**Si `llm_annotation_real.json` n'existe pas** (aucune annotation LLM
réelle produite dans cet environnement), ce script ne fabrique RIEN : il
affiche la commande à exécuter d'abord.

Exécution (après une vraie annotation LLM) :
    python -m examples.freeze_real_example

Sorties :
    docs/chapter4/outputs/frozen_annotations_real.json
    docs/chapter4/outputs/frozen_annotations_real.csv
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from src.annotation_validator import ELEVEN_METRICS, freeze_candidate
from src.schemas import Annotation

OUT_DIR = Path("docs/chapter4/outputs")
REAL_ANNOTATION_PATH = OUT_DIR / "llm_annotation_real.json"


def freeze_from_payload(payload: dict, *, annotation_set_version: str = "chapter4-real-llm-v1"):
    """Réf. tâche « gel réel après LLM » : reconstruit les `Annotation`
    depuis le JSON produit par `examples.annotator_llm_real_example` et
    gèle le candidat. Fonction pure (aucune E/S) — testable indépendamment
    de la présence du fichier réel."""
    candidate = payload["candidate"]
    annotations = [
        Annotation(
            metric=raw["metric"],
            score=raw["score"],
            justification=raw["justification"],
            evidence=raw["evidence"],
            confidence=raw["confidence"],
            model_version=raw["model_version"],
            prompt_version=raw["prompt_version"],
            annotated_at=datetime.fromisoformat(raw["annotated_at"]) if raw.get("annotated_at") else None,
            annotation_id=raw["annotation_id"],
        )
        for raw in payload["annotations"]
    ]

    return freeze_candidate(
        occurrence_id=candidate["occurrence_id"],
        mechanism_id=candidate["mechanism_id"],
        location_id=candidate["location_id"],
        annotations=annotations,
        annotation_set_version=annotation_set_version,
    )


def main() -> None:
    if not REAL_ANNOTATION_PATH.exists():
        print(f"'{REAL_ANNOTATION_PATH}' n'existe pas : aucune annotation LLM reelle a geler.")
        print("Executer d'abord une vraie annotation :")
        print()
        print("  LLM_PROVIDER=ollama LLM_MODEL=<votre_modele_local> \\")
        print("    python -m examples.annotator_llm_real_example")
        print()
        print("(ou LLM_PROVIDER=openai_compatible avec LLM_MODEL/LLM_BASE_URL/LLM_API_KEY)")
        print("Ce script n'ecrit AUCUN fichier frozen_annotations_real.* sans cela (anti-fabrication).")
        return

    payload = json.loads(REAL_ANNOTATION_PATH.read_text(encoding="utf-8"))
    frozen = freeze_from_payload(payload)

    frozen_json = {
        "annotation_id": frozen.annotation_id,
        "occurrence_id": frozen.occurrence_id,
        "mechanism_id": frozen.mechanism_id,
        "location_id": frozen.location_id,
        "model": frozen.model,
        "prompt_version": frozen.prompt_version,
        "evidence_ids": list(frozen.evidence_ids),
        "submetrics": frozen.submetrics,
        "Realisme": frozen.Realisme,
        "P_interaction": frozen.P_interaction,
        "P_engagement": frozen.P_engagement,
        "Effet_prog": frozen.Effet_prog,
        "DE": frozen.DE,
        "confidence": frozen.confidence,
        "annotation_set_version": frozen.annotation_set_version,
        "source": "real_llm",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "frozen_annotations_real.json").write_text(
        json.dumps(frozen_json, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    fieldnames = (
        ["annotation_id", "occurrence_id", "mechanism_id", "location_id", "model", "prompt_version"]
        + list(ELEVEN_METRICS)
        + ["Realisme", "P_interaction", "P_engagement", "Effet_prog", "DE", "confidence", "evidence_ids", "annotation_set_version"]
    )
    with (OUT_DIR / "frozen_annotations_real.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        row = {
            "annotation_id": frozen.annotation_id,
            "occurrence_id": frozen.occurrence_id,
            "mechanism_id": frozen.mechanism_id,
            "location_id": frozen.location_id,
            "model": frozen.model,
            "prompt_version": frozen.prompt_version,
            "Realisme": f"{frozen.Realisme:.4f}",
            "P_interaction": f"{frozen.P_interaction:.4f}",
            "P_engagement": f"{frozen.P_engagement:.4f}",
            "Effet_prog": f"{frozen.Effet_prog:.4f}",
            "DE": f"{frozen.DE:.4f}",
            "confidence": f"{frozen.confidence:.4f}",
            "evidence_ids": ";".join(frozen.evidence_ids),
            "annotation_set_version": frozen.annotation_set_version,
        }
        for metric in ELEVEN_METRICS:
            row[metric] = f"{frozen.submetrics[metric]:.4f}"
        writer.writerow(row)

    print(f"Gel reel produit pour {frozen.occurrence_id}/{frozen.mechanism_id}/{frozen.location_id} :")
    print(f"  Realisme={frozen.Realisme:.3f} P_interaction={frozen.P_interaction:.3f} "
          f"P_engagement={frozen.P_engagement:.3f} Effet_prog={frozen.Effet_prog:.3f} DE={frozen.DE:.3f}")
    print(f"Sorties : {OUT_DIR / 'frozen_annotations_real.json'} / .csv")


if __name__ == "__main__":
    main()
