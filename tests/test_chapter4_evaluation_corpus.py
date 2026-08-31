"""
Réf. tâche « campagne d'évaluation réelle RAG/LLM/système » §8 : validité de
la construction du corpus complet (1306 chunks) utilisé par la campagne
d'évaluation retrieval (§2/§3) — vérifie les comptes RÉELS, pas supposés.
"""

from tools.chapter4_evaluation.retrieval_campaign import load_deception_only_chunks, load_full_corpus_chunks


class TestFullCorpusConstruction:
    def test_deception_only_corpus_has_149_chunks(self):
        chunks = load_deception_only_chunks()
        assert len(chunks) == 149

    def test_full_corpus_has_1306_chunks(self):
        chunks = load_full_corpus_chunks()
        assert len(chunks) == 1306

    def test_full_corpus_chunk_count_by_source(self):
        chunks = load_full_corpus_chunks()
        counts = {}
        for chunk in chunks:
            counts[chunk.source_type] = counts.get(chunk.source_type, 0) + 1
        assert counts.get("attack") == 1157
        assert counts.get("d3fend") == 44
        assert counts.get("engage") == 62
        assert counts.get("literature") == 43

    def test_full_corpus_contains_deception_only_corpus(self):
        """Le corpus complet ajoute des chunks ATT&CK, il ne remplace rien :
        chaque chunk_id du corpus reduit doit exister dans le corpus complet."""
        deception_ids = {c.chunk_id for c in load_deception_only_chunks()}
        full_ids = {c.chunk_id for c in load_full_corpus_chunks()}
        assert deception_ids <= full_ids

    def test_all_chunk_ids_unique_in_full_corpus(self):
        chunks = load_full_corpus_chunks()
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))
