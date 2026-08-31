"""
Réf. tâche « améliorer réellement la qualité et la latence du moteur RAG »
§1/§5 : validité structurelle du benchmark équilibré -- dev/test disjoints,
chaque groupe de source représenté dans les deux ensembles autant que
possible, vérité terrain jamais vide, aucune requête dupliquée.
"""

from tools.chapter4_evaluation.benchmark_balanced import build_balanced_benchmark


class TestBalancedBenchmarkStructure:
    def test_query_ids_are_unique(self):
        benchmark = build_balanced_benchmark()
        ids = [q["query_id"] for q in benchmark["queries"]]
        assert len(ids) == len(set(ids))

    def test_dev_and_test_are_disjoint_and_cover_all_queries(self):
        benchmark = build_balanced_benchmark()
        dev_ids = {q["query_id"] for q in benchmark["queries"] if q["split"] == "dev"}
        test_ids = {q["query_id"] for q in benchmark["queries"] if q["split"] == "test"}
        all_ids = {q["query_id"] for q in benchmark["queries"]}
        assert dev_ids & test_ids == set()
        assert dev_ids | test_ids == all_ids
        assert len(test_ids) > 0
        assert len(dev_ids) > 0

    def test_every_query_has_non_empty_ground_truth(self):
        benchmark = build_balanced_benchmark()
        for q in benchmark["queries"]:
            assert len(q["expected_chunk_ids"]) > 0, q["query_id"]

    def test_every_source_group_represented_in_dev(self):
        benchmark = build_balanced_benchmark()
        dev_groups = {q["source_group"] for q in benchmark["queries"] if q["split"] == "dev"}
        assert {"attack", "d3fend", "engage"} <= dev_groups

    def test_every_source_group_represented_in_test(self):
        benchmark = build_balanced_benchmark()
        test_groups = {q["source_group"] for q in benchmark["queries"] if q["split"] == "test"}
        assert {"attack", "d3fend", "engage"} <= test_groups

    def test_query_count_matches_split_counts(self):
        benchmark = build_balanced_benchmark()
        assert benchmark["query_count"] == len(benchmark["queries"])
        assert benchmark["split_counts"]["dev"] + benchmark["split_counts"]["test"] == benchmark["query_count"]
