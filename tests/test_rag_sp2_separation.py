"""
Réf. architecture : CLAUDE.md §17 « Séparation non négociable des
responsabilités » — réf. tâche « renforcer l'architecture et
l'implémentation du module RAG utilisé par SP2 », §25 « Vérifier via des
tests les invariants de séparation des responsabilités ».

Tests unitaires transversaux (§25.4 : pytest obligatoire), COMPLÉMENTAIRES
aux invariants déjà couverts localement dans chaque module (ex.
`TestGenericity` dans `tests/test_admissibility.py`,
`TestNeverComputesAggregates` dans `tests/test_annotator_llm.py`,
`TestRetrieveSemanticVsLexicalNoRagDependencyLeak` dans
`tests/test_rag_retriever.py`) :

- SP1 (`src/admissibility.py`) ne dépend jamais du RAG ni du LLM ;
- le RAG contextuel de SP2 (`src/rag_candidate_context.py`,
  `src/rag_query_builder.py`, `src/rag_evidence.py`, `src/reranker.py`) ne
  dépend jamais du budget, du coût ni de l'optimiseur ;
- l'optimiseur (`src/optimizer.py`) n'appelle jamais le RAG ni le LLM.

Analyse STATIQUE des imports (pas seulement absence d'appel observé à
l'exécution) — même principe que
`tests/test_rag_query_builder.py::TestNoLlmInvolvement`.
"""

import ast
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"


def _imported_modules(module_filename: str) -> set[str]:
    tree = ast.parse((SRC_DIR / module_filename).read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


RAG_LLM_MARKERS = ("rag_indexer", "rag_retriever", "rag_query_builder", "rag_evidence", "reranker", "annotator_llm", "llm_provider")
BUDGET_COST_OPTIMIZATION_MARKERS = ("cost_engine", "optimizer")


class TestSP1IndependentOfRagAndLlm:
    def test_admissibility_module_never_imports_rag_or_llm(self):
        modules = _imported_modules("admissibility.py")
        assert not any(marker in module for module in modules for marker in RAG_LLM_MARKERS)


class TestRagContextualPipelineIndependentOfBudgetAndOptimization:
    def test_rag_candidate_context_never_imports_cost_or_optimizer(self):
        modules = _imported_modules("rag_candidate_context.py")
        assert not any(marker in module for module in modules for marker in BUDGET_COST_OPTIMIZATION_MARKERS)

    def test_rag_query_builder_never_imports_cost_or_optimizer(self):
        modules = _imported_modules("rag_query_builder.py")
        assert not any(marker in module for module in modules for marker in BUDGET_COST_OPTIMIZATION_MARKERS)

    def test_rag_evidence_never_imports_cost_or_optimizer(self):
        modules = _imported_modules("rag_evidence.py")
        assert not any(marker in module for module in modules for marker in BUDGET_COST_OPTIMIZATION_MARKERS)

    def test_reranker_never_imports_cost_or_optimizer(self):
        modules = _imported_modules("reranker.py")
        assert not any(marker in module for module in modules for marker in BUDGET_COST_OPTIMIZATION_MARKERS)

    def test_reranker_never_imports_the_main_llm_annotator(self):
        """Réf. tâche §9 : « le LLM principal n'est JAMAIS utilisé comme
        reranker »."""
        modules = _imported_modules("reranker.py")
        assert not any("annotator_llm" in module for module in modules)


class TestOptimizerNeverCallsRagOrLlm:
    def test_optimizer_module_never_imports_rag_or_llm(self):
        modules = _imported_modules("optimizer.py")
        assert not any(marker in module for module in modules for marker in RAG_LLM_MARKERS)
