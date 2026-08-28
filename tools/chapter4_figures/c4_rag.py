"""
Réf. tâche « renforcer l'architecture et l'implémentation du module RAG
utilisé par SP2 », §21 « Mettre à jour la figure C4 ».

Remplace l'ancienne figure C4 (tableau plat de retrieval TF-IDF seul, qui
ne représentait plus l'architecture réellement implémentée depuis
l'introduction du RAG sémantique puis du RAG contextuel par famille) par
un diagramme d'architecture OFFLINE / ONLINE :

  OFFLINE : ATT&CK + D3FEND + Engage + Littérature -> chunking + métadonnées
            -> embeddings sémantiques -> index vectoriel FAISS
  ONLINE  : candidat (T_i,h,d,l) -> RagCandidateContext -> Q_realism/
            Q_interaction/Q_effect -> retrieval large (lexical + sémantique)
            -> reranking contextuel (cross-encoder) -> diversification
            -> CandidateEvidenceBundle -> LLM (annotation des 11 sous-métriques)

Contenu structurel fixe (diagramme d'architecture, même registre que
C1/C8) ; les COMPTEURS affichés dans chaque bloc sont réels, lus dans
docs/chapter4/outputs/rag_evidence_bundle_example.json et
docs/chapter4/outputs/rag_queries_example.json (produits par
`python -m examples.rag_sp2_context_example`, jamais retapés à la main).

Sortie : docs/chapter4/screenshots/04_rag/rag_architecture.png
"""

from __future__ import annotations

import json
from pathlib import Path

from matplotlib.patches import FancyArrow, FancyBboxPatch, Rectangle

from tools.chapter4_figures.common import (
    COLOR_BORDER,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_MONO,
    FONT_SANS,
    new_figure,
    save_figure,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BUNDLE_PATH = REPO_ROOT / "docs" / "chapter4" / "outputs" / "rag_evidence_bundle_example.json"
QUERIES_PATH = REPO_ROOT / "docs" / "chapter4" / "outputs" / "rag_queries_example.json"
OUTPUT_PATH = REPO_ROOT / "docs" / "chapter4" / "screenshots" / "04_rag" / "rag_architecture.png"

OFFLINE_BG = "#eef2f8"
ONLINE_BG = "#eef8ef"
BOX_BG = "#ffffff"
ARROW_COLOR = "#555555"


def _box(ax, x, y, w, h, label, *, fontsize=9.2, sub=None):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06", facecolor=BOX_BG, edgecolor=COLOR_BORDER, linewidth=0.9
        )
    )
    if sub:
        ax.text(x + w / 2, y + h / 2 + 0.1, label, fontsize=fontsize, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="center", ha="center")
        ax.text(x + w / 2, y + h / 2 - 0.16, sub, fontsize=7.2, color=COLOR_TEXT_SECONDARY, family=FONT_MONO, va="center", ha="center")
    else:
        ax.text(x + w / 2, y + h / 2, label, fontsize=fontsize, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="center", ha="center")


def _harrow(ax, x0, x1, y):
    ax.add_patch(FancyArrow(x0, y, x1 - x0, 0, width=0.012, head_width=0.09, head_length=0.1, color=ARROW_COLOR, length_includes_head=True))


def _varrow(ax, x, y0, y1):
    ax.add_patch(FancyArrow(x, y0, 0, y1 - y0, width=0.012, head_width=0.09, head_length=0.1, color=ARROW_COLOR, length_includes_head=True))


def _arrow(ax, x0, y0, x1, y1):
    """Flèche générique (diagonale autorisée) — réf. convergence des trois
    requêtes vers la même étape de retrieval large."""
    ax.add_patch(FancyArrow(x0, y0, x1 - x0, y1 - y0, width=0.01, head_width=0.08, head_length=0.09, color=ARROW_COLOR, length_includes_head=True))


def generate(output_path: Path = OUTPUT_PATH) -> Path:
    bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    queries = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
    evidence_counts = {name: len(family["evidence"]) for name, family in bundle["families"].items()}

    width, height = 13.0, 10.4
    fig = new_figure(width, height)
    ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")

    margin = 0.35
    ax.text(margin, height - 0.4, "Architecture RAG contextuelle (SP2) — réf. tâche §21", fontsize=16, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="top", ha="left")
    ax.text(
        margin, height - 0.75,
        "Le RAG récupère et ordonne des passages documentaires pour l'évaluation contextuelle du candidat — il ne calcule jamais DE, la sélection ou le risque.",
        fontsize=9, color=COLOR_TEXT_SECONDARY, family=FONT_SANS, va="top", ha="left", style="italic",
    )

    # --- Bloc OFFLINE ---
    offline_top, offline_h = height - 1.1, 2.55
    offline_bottom = offline_top - offline_h
    ax.add_patch(Rectangle((margin, offline_bottom), width - 2 * margin, offline_h, facecolor=OFFLINE_BG, edgecolor=COLOR_BORDER, linewidth=1.1))
    ax.text(margin + 0.2, offline_top - 0.28, "OFFLINE — préparation du corpus (jamais recalculé par candidat)", fontsize=11.5, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="top", ha="left")

    src_w, src_h = 2.1, 0.75
    src_y = offline_top - 1.05
    sources = ["ATT&CK", "D3FEND", "Engage", "Littérature\nscientifique"]
    src_gap = (width - 2 * margin - 4 * src_w) / 5
    src_xs = []
    for i, name in enumerate(sources):
        x = margin + src_gap + i * (src_w + src_gap)
        src_xs.append(x)
        _box(ax, x, src_y, src_w, src_h, name)

    chunk_w, chunk_h = width - 2 * margin - 1.0, 0.85
    chunk_x = margin + 0.5
    chunk_y = offline_bottom + 0.3
    _box(
        ax, chunk_x, chunk_y, chunk_w, chunk_h,
        "Chunking + métadonnées → embeddings sémantiques → index vectoriel FAISS",
        sub=f"{bundle['corpus_chunk_count']} chunks | modèle={bundle['embedding_model']} | backend={bundle['vector_backend']}",
        fontsize=10.5,
    )
    for x in src_xs:
        _varrow(ax, x + src_w / 2, src_y - 0.03, chunk_y + chunk_h + 0.03)

    # --- Bloc ONLINE ---
    online_top = offline_bottom - 0.55

    # Ligne 1 : candidat -> contexte -> 3 requêtes (colonne verticale, plus
    # haute que les autres boîtes -> centrée sur le même axe horizontal).
    q_w, q_h, q_gap = 2.0, 0.55, 0.2
    q_column_h = 3 * q_h + 2 * q_gap
    row1_center_y = online_top - 0.7 - q_column_h / 2
    q_x0 = None  # défini plus bas, après ctx_x

    cand_w, cand_h = 2.5, 0.75
    cand_x = margin + 0.3
    cand_y = row1_center_y - cand_h / 2
    _box(ax, cand_x, cand_y, cand_w, cand_h, "Candidat SP1", sub="(T_i,h, d, l)", fontsize=9.5)

    ctx_w = 2.9
    ctx_x = cand_x + cand_w + 0.45
    ctx_y = row1_center_y - cand_h / 2
    _box(ax, ctx_x, ctx_y, ctx_w, cand_h, "RagCandidateContext", sub="jamais de budget/coût/risque", fontsize=9)
    _harrow(ax, cand_x + cand_w + 0.03, ctx_x - 0.03, row1_center_y)

    q_x0 = ctx_x + ctx_w + 0.45
    query_labels = ["Q_realism", "Q_interaction", "Q_effect"]
    q_top = row1_center_y + q_column_h / 2
    q_centers_y = []
    for i, label in enumerate(query_labels):
        qy = q_top - (i + 1) * q_h - i * q_gap
        _box(ax, q_x0, qy, q_w, q_h, label, fontsize=9.5)
        q_centers_y.append(qy + q_h / 2)
        _harrow(ax, ctx_x + ctx_w + 0.03, q_x0 - 0.03, qy + q_h / 2)

    row1_bottom = row1_center_y - max(cand_h, q_column_h) / 2

    # Ligne 2 : retrieval large -> reranking -> diversification
    row2_top = row1_bottom - 0.55
    pipe_w, pipe_h = 2.75, 0.85
    row2_y = row2_top - pipe_h
    pipe_gap = (width - 2 * margin - 3 * pipe_w) / 4
    pipe_labels = [
        ("Retrieval large\n(lexical + sémantique)", "RAG_RETRIEVAL_CANDIDATES par requête"),
        ("Reranking contextuel", f"cross-encoder ({bundle['reranker_model']})"),
        ("Diversification", "max chunks/document, après reranking"),
    ]
    pipe_centers = []
    x = margin + pipe_gap
    prev_center = None
    for label, sub in pipe_labels:
        _box(ax, x, row2_y, pipe_w, pipe_h, label, sub=sub, fontsize=9)
        center = x + pipe_w / 2
        pipe_centers.append(center)
        if prev_center is not None:
            _harrow(ax, prev_center + pipe_w / 2, center - pipe_w / 2, row2_y + pipe_h / 2)
        prev_center = center
        x += pipe_w + pipe_gap
    # Les trois requêtes convergent vers l'ÉTAPE DE RETRIEVAL (première boîte
    # de la ligne 2), jamais directement vers le reranking — arrêtes
    # diagonales explicites plutôt qu'un alignement x fortuit trompeur.
    retrieval_center_x = pipe_centers[0]
    for qy in q_centers_y:
        _arrow(ax, q_x0 + q_w / 2, qy, retrieval_center_x, row2_top + 0.03)

    # Ligne 3 : evidence bundle -> LLM
    row3_top = row2_y - 0.55
    bundle_w, bundle_h = 5.6, 0.9
    row3_y = row3_top - bundle_h
    bundle_x = margin + (width - 2 * margin) / 2 - bundle_w - 0.3
    _box(
        ax, bundle_x, row3_y, bundle_w, bundle_h,
        "CandidateEvidenceBundle",
        sub=f"realism={evidence_counts.get('realism', 0)} | interaction={evidence_counts.get('interaction', 0)} | effect={evidence_counts.get('effect', 0)} preuves",
        fontsize=10,
    )
    _varrow(ax, pipe_centers[-1], row2_y - 0.03, row3_y + bundle_h + 0.03)

    llm_w, llm_h = 3.6, 0.9
    llm_x = bundle_x + bundle_w + 0.6
    _box(ax, llm_x, row3_y, llm_w, llm_h, "LLM", sub="11 sous-métriques annotées (§11.3)", fontsize=10.5)
    _harrow(ax, bundle_x + bundle_w + 0.03, llm_x - 0.03, row3_y + bundle_h / 2)

    footer_top = row3_y - 0.35
    online_bottom = footer_top - 0.9
    online_h = online_top - online_bottom
    ax.add_patch(Rectangle((margin, online_bottom), width - 2 * margin, online_h, facecolor=ONLINE_BG, edgecolor=COLOR_BORDER, linewidth=1.1, zorder=0))
    ax.text(margin + 0.2, online_top - 0.28, "ONLINE — pipeline par candidat admissible (T_i,h,d,l)", fontsize=11.5, fontweight="bold", color=COLOR_TEXT_PRIMARY, family=FONT_SANS, va="top", ha="left")
    _varrow(ax, chunk_x + chunk_w / 2, offline_bottom - 0.03, online_top - 0.03)

    ax.text(
        margin, footer_top - 0.05,
        f"Requête réelle Q_realism (candidat {queries['candidate']['occurrence_id']}) : « {queries['queries']['realism'][:95]}… »",
        fontsize=8, color=COLOR_TEXT_SECONDARY, family=FONT_MONO, va="top", ha="left",
    )
    ax.text(
        margin, footer_top - 0.37,
        "Aucun appel LLM pendant la construction des requêtes ni le retrieval/reranking (§17.2, §9). Preuves d'ATT&CK, D3FEND, Engage et littérature combinées simultanément (§15).",
        fontsize=8, color=COLOR_TEXT_SECONDARY, family=FONT_SANS, va="top", ha="left", style="italic",
    )

    save_figure(fig, output_path)
    return output_path


if __name__ == "__main__":
    path = generate()
    print(f"Genere : {path}")
