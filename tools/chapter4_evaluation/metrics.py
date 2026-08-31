"""
Réf. tâche « campagne d'évaluation réelle RAG/LLM/système » — métriques de
recherche documentaire partagées par tous les scripts d'évaluation de ce
paquet. Aucune valeur fabriquée : chaque fonction calcule strictement à
partir des identifiants réellement récupérés (`retrieved_ids`) et de la
vérité terrain fournie (`expected_ids`).

Reprend et étend les fonctions historiques de
`examples/rag_semantic_evaluation.py` (Recall@k/MRR@k/nDCG@k), inchangées
dans leur formule, plus `hit_rate_at_k` (nouveau, réf. tâche §2).

Convention : identifiants de code en anglais, commentaires et docstrings
en français (§25.1).
"""

from __future__ import annotations

import math


class MetricsError(Exception):
    """Erreur de calcul d'une métrique d'évaluation."""


def recall_at_k(retrieved_ids: list[str], expected_ids: set[str], k: int) -> float:
    """Réf. tâche : proportion des éléments PERTINENTS effectivement
    retrouvés dans le top-k (peut dépasser un seul document si plusieurs
    chunks sont attendus)."""
    if not expected_ids:
        raise MetricsError("expected_ids ne doit jamais être vide (vérité terrain absente).")
    hits = len(set(retrieved_ids[:k]) & expected_ids)
    return hits / len(expected_ids)


def mrr_at_k(retrieved_ids: list[str], expected_ids: set[str], k: int) -> float:
    """Réciproque du rang du PREMIER élément pertinent dans le top-k, 0
    si aucun."""
    for rank, chunk_id in enumerate(retrieved_ids[:k], start=1):
        if chunk_id in expected_ids:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved_ids: list[str], expected_ids: set[str], k: int) -> float:
    """Gain cumulé actualisé normalisé (pertinence binaire)."""
    dcg = 0.0
    for rank, chunk_id in enumerate(retrieved_ids[:k], start=1):
        relevance = 1.0 if chunk_id in expected_ids else 0.0
        dcg += relevance / math.log2(rank + 1)
    ideal_hits = min(len(expected_ids), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def hit_rate_at_k(retrieved_ids: list[str], expected_ids: set[str], k: int) -> float:
    """Réf. tâche §2 (nouveau) : 1.0 si AU MOINS UNE preuve pertinente
    figure dans le top-k, sinon 0.0 — contrairement à `recall_at_k`, ne
    pénalise pas une requête à vérité terrain multiple qui n'en retrouve
    qu'une partie."""
    if not expected_ids:
        raise MetricsError("expected_ids ne doit jamais être vide (vérité terrain absente).")
    return 1.0 if set(retrieved_ids[:k]) & expected_ids else 0.0


def evaluate_queries(
    retrieved_by_query: dict[str, list[str]],
    queries: list[dict],
    *,
    ks: tuple[int, ...] = (5, 10),
) -> dict:
    """Réf. tâche §2 : calcule, POUR CHAQUE requête et en moyenne, toutes
    les métriques demandées (`recall@k` pour chaque `k` de `ks`, `mrr@5`,
    `ndcg@5`, `hit_rate@5`) — jamais une métrique supposée ou recopiée."""
    per_query = []
    for query in queries:
        expected = set(query["expected_chunk_ids"])
        retrieved = retrieved_by_query[query["query_id"]]
        entry = {
            "query_id": query["query_id"],
            "topic": query.get("topic"),
            "retrieved_top10": retrieved[:10],
        }
        for k in ks:
            entry[f"recall_at_{k}"] = recall_at_k(retrieved, expected, k)
        entry["mrr_at_5"] = mrr_at_k(retrieved, expected, 5)
        entry["ndcg_at_5"] = ndcg_at_k(retrieved, expected, 5)
        entry["hit_rate_at_5"] = hit_rate_at_k(retrieved, expected, 5)
        per_query.append(entry)

    n = len(per_query)
    if n == 0:
        raise MetricsError("Aucune requête à évaluer.")

    means: dict[str, float] = {}
    for k in ks:
        means[f"mean_recall_at_{k}"] = sum(q[f"recall_at_{k}"] for q in per_query) / n
    means["mean_mrr_at_5"] = sum(q["mrr_at_5"] for q in per_query) / n
    means["mean_ndcg_at_5"] = sum(q["ndcg_at_5"] for q in per_query) / n
    means["mean_hit_rate_at_5"] = sum(q["hit_rate_at_5"] for q in per_query) / n

    return {"query_count": n, **means, "per_query": per_query}
