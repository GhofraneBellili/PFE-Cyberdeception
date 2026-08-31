"""
Réf. tâche « campagne d'évaluation réelle RAG/LLM/système » §8 : validité
des métriques de recherche documentaire sur un cas jouet CONNU (valeurs
calculées à la main, pas devinées).

Tests unitaires de `tools/chapter4_evaluation/metrics.py` (§25.4 : pytest
obligatoire). Aucune dépendance réseau/modèle — calcul pur.
"""

import math

import pytest

from tools.chapter4_evaluation.metrics import (
    MetricsError,
    evaluate_queries,
    hit_rate_at_k,
    mrr_at_k,
    ndcg_at_k,
    recall_at_k,
)


# ---------------------------------------------------------------------------
# A. Cas jouet connu — valeurs calculées à la main
# ---------------------------------------------------------------------------

RETRIEVED = ["a", "b", "c", "d", "e", "f"]
EXPECTED = {"c", "z"}  # "z" n'apparaît jamais dans RETRIEVED


class TestRecallAtK:
    def test_toy_case_recall_at_5(self):
        # hit = {"c"} (1 sur les 2 attendus) -> 1/2 = 0.5
        assert recall_at_k(RETRIEVED, EXPECTED, 5) == pytest.approx(0.5)

    def test_toy_case_recall_at_10_same_as_5_when_list_shorter(self):
        assert recall_at_k(RETRIEVED, EXPECTED, 10) == pytest.approx(0.5)

    def test_full_recall_when_all_expected_present(self):
        assert recall_at_k(["x", "y"], {"x", "y"}, 5) == pytest.approx(1.0)

    def test_zero_recall_when_nothing_relevant_retrieved(self):
        assert recall_at_k(["a", "b"], {"z"}, 5) == pytest.approx(0.0)

    def test_empty_expected_ids_raises(self):
        with pytest.raises(MetricsError):
            recall_at_k(RETRIEVED, set(), 5)


class TestMrrAtK:
    def test_toy_case_mrr_at_5(self):
        # "c" est en position 3 (1-indexed) -> 1/3
        assert mrr_at_k(RETRIEVED, EXPECTED, 5) == pytest.approx(1.0 / 3.0)

    def test_zero_when_relevant_item_beyond_k(self):
        assert mrr_at_k(["a", "b", "c"], {"c"}, 2) == pytest.approx(0.0)

    def test_one_when_first_result_is_relevant(self):
        assert mrr_at_k(["c", "a"], {"c"}, 5) == pytest.approx(1.0)


class TestNdcgAtK:
    def test_toy_case_ndcg_at_5(self):
        # dcg = 1/log2(3+1) = 0.5 ; idcg (2 pertinents ideaux aux rangs 1,2)
        # = 1/log2(2) + 1/log2(3) = 1 + 0.6309297535714... = 1.6309297535714...
        dcg = 1.0 / math.log2(4)
        idcg = 1.0 / math.log2(2) + 1.0 / math.log2(3)
        expected_ndcg = dcg / idcg
        assert ndcg_at_k(RETRIEVED, EXPECTED, 5) == pytest.approx(expected_ndcg)

    def test_one_when_perfect_ranking(self):
        assert ndcg_at_k(["x", "y"], {"x", "y"}, 5) == pytest.approx(1.0)

    def test_zero_when_no_relevant_result(self):
        assert ndcg_at_k(["a", "b"], {"z"}, 5) == pytest.approx(0.0)


class TestHitRateAtK:
    def test_toy_case_hit_rate_at_5_is_one(self):
        assert hit_rate_at_k(RETRIEVED, EXPECTED, 5) == pytest.approx(1.0)

    def test_zero_when_no_relevant_result_in_k(self):
        assert hit_rate_at_k(["a", "b", "c"], {"z"}, 5) == pytest.approx(0.0)

    def test_still_one_even_with_only_one_of_several_expected_found(self):
        """Différence clé avec recall_at_k : hit_rate ne pénalise pas une
        vérité terrain multiple partiellement retrouvée."""
        assert hit_rate_at_k(RETRIEVED, EXPECTED, 5) == pytest.approx(1.0)
        assert recall_at_k(RETRIEVED, EXPECTED, 5) == pytest.approx(0.5)

    def test_empty_expected_ids_raises(self):
        with pytest.raises(MetricsError):
            hit_rate_at_k(RETRIEVED, set(), 5)


class TestEvaluateQueries:
    def test_aggregates_all_metrics_for_toy_queries(self):
        queries = [
            {"query_id": "q1", "topic": "toy", "expected_chunk_ids": ["c", "z"]},
            {"query_id": "q2", "topic": "toy", "expected_chunk_ids": ["x", "y"]},
        ]
        retrieved_by_query = {"q1": RETRIEVED, "q2": ["x", "y"]}
        result = evaluate_queries(retrieved_by_query, queries, ks=(5, 10))

        assert result["query_count"] == 2
        assert result["mean_recall_at_5"] == pytest.approx((0.5 + 1.0) / 2)
        assert result["mean_hit_rate_at_5"] == pytest.approx((1.0 + 1.0) / 2)
        assert "recall_at_10" in result["per_query"][0]
        assert len(result["per_query"]) == 2

    def test_raises_on_empty_query_list(self):
        with pytest.raises(MetricsError):
            evaluate_queries({}, [])
