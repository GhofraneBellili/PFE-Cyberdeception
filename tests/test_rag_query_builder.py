"""
Réf. architecture : CLAUDE.md §11.3 — réf. tâche « renforcer le RAG
utilisé par SP2 », §6/§7 « Construction de requêtes spécifiques par
famille de sous-métriques ».

Tests unitaires de `src/rag_query_builder.py` (§25.4 : pytest
obligatoire). Couvre les critères §19-D (les trois requêtes d'un même
candidat diffèrent) et §19-E (les requêtes changent pour deux candidats
différents), ainsi que §19-N (le LLM n'intervient jamais dans la
construction des requêtes — aucun import de `src.annotator_llm` ici).
"""

import ast
from pathlib import Path

from src.rag_query_builder import build_effect_query, build_interaction_query, build_rag_queries, build_realism_query
from src.schemas import RagCandidateContext, RagGraphContext, SIPlacementContext


def make_context(**overrides) -> RagCandidateContext:
    base = dict(
        occurrence_id="T1566@WS01",
        technique_id="T1566",
        technique_name="Phishing",
        tactics=["initial-access"],
        asset_id="WS01",
        asset_type="workstation",
        mechanism_id="D1",
        mechanism_name="Decoy Mailbox",
        mechanism_description="A decoy mailbox lures phishing payloads.",
        target_artifacts=["email", "attachment"],
        interaction_mechanism="attacker sends a phishing email to the decoy mailbox",
        location_id="mailbox-ws01",
        location_type="mailbox",
        si_context=SIPlacementContext(relevant_services=["email"], relevant_artifacts=[]),
        graph_context=RagGraphContext(
            direct_parent_technique_ids=[],
            direct_child_technique_ids=["T1110"],
            is_entry=True,
            is_terminal=False,
            neighboring_tactics=["credential-access"],
        ),
    )
    base.update(overrides)
    return RagCandidateContext(**base)


# ---------------------------------------------------------------------------
# A. build_rag_queries — forme générale
# ---------------------------------------------------------------------------


class TestBuildRagQueries:
    def test_returns_exactly_three_families(self):
        context = make_context()
        queries = build_rag_queries(context)
        assert set(queries.keys()) == {"realism", "interaction", "effect"}

    def test_all_queries_are_non_empty_strings(self):
        context = make_context()
        queries = build_rag_queries(context)
        for query in queries.values():
            assert isinstance(query, str)
            assert query.strip()

    def test_matches_individual_builder_functions(self):
        context = make_context()
        queries = build_rag_queries(context)
        assert queries["realism"] == build_realism_query(context)
        assert queries["interaction"] == build_interaction_query(context)
        assert queries["effect"] == build_effect_query(context)


# ---------------------------------------------------------------------------
# B. Critère §19-D — les trois requêtes d'un même candidat diffèrent
# ---------------------------------------------------------------------------


class TestQueriesDifferWithinCandidate:
    def test_three_queries_are_pairwise_distinct(self):
        context = make_context()
        queries = build_rag_queries(context)
        values = list(queries.values())
        assert len(set(values)) == 3

    def test_realism_query_mentions_asset_and_location_type(self):
        context = make_context()
        query = build_realism_query(context)
        assert context.asset_type in query
        assert context.location_type in query

    def test_interaction_query_mentions_target_artifacts(self):
        context = make_context()
        query = build_interaction_query(context)
        for artifact in context.target_artifacts:
            assert artifact in query

    def test_effect_query_mentions_downstream_technique(self):
        context = make_context()
        query = build_effect_query(context)
        assert "T1110" in query


# ---------------------------------------------------------------------------
# C. Critère §19-E — les requêtes changent pour deux candidats différents
# ---------------------------------------------------------------------------


class TestQueriesDifferAcrossCandidates:
    def test_different_mechanism_changes_all_three_queries(self):
        context_a = make_context()
        context_b = make_context(
            mechanism_id="D2",
            mechanism_name="Honeytoken Credential",
            mechanism_description="A fake credential lures credential dumping.",
            interaction_mechanism="attacker attempts to use the fake credential",
            target_artifacts=["credential"],
        )
        queries_a = build_rag_queries(context_a)
        queries_b = build_rag_queries(context_b)
        for family in ("realism", "interaction", "effect"):
            assert queries_a[family] != queries_b[family]

    def test_different_technique_changes_queries(self):
        context_a = make_context()
        context_b = make_context(technique_id="T1003", technique_name="OS Credential Dumping", tactics=["credential-access"])
        queries_a = build_rag_queries(context_a)
        queries_b = build_rag_queries(context_b)
        assert queries_a["effect"] != queries_b["effect"]

    def test_different_location_changes_realism_query(self):
        context_a = make_context()
        context_b = make_context(location_id="host-ws01", location_type="host")
        assert build_realism_query(context_a) != build_realism_query(context_b)


# ---------------------------------------------------------------------------
# D. Déterminisme — même candidat -> mêmes requêtes
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_context_produces_identical_queries(self):
        context = make_context()
        assert build_rag_queries(context) == build_rag_queries(context)


# ---------------------------------------------------------------------------
# E. Critère §19-N — aucune intervention du LLM dans la construction des
# requêtes (analyse statique du module, pas seulement absence d'appel
# observé à l'exécution)
# ---------------------------------------------------------------------------


class TestNoLlmInvolvement:
    def test_module_does_not_import_annotator_llm(self):
        source_path = Path(__file__).resolve().parent.parent / "src" / "rag_query_builder.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
        assert not any("annotator_llm" in module or "llm_provider" in module for module in imported_modules)
