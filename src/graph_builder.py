"""
Réf. architecture : CLAUDE.md — contrat technique du PFE Cyberdéception.

Construction, chargement, représentation opérationnelle (NetworkX) et
navigation du graphe d'attaque G = (V, E) (§26 "graph_builder.py"), ainsi
que l'identification des nœuds Entry (§5) et Terminal (§6).

Ce module ne calcule aucune propagation de risque (A, P, Gamma, P^e, I
agrégé, R, DE) : ces calculs appartiennent au futur risk_engine.py (SP3).
Il ne contient aucune règle spécifique à un cas d'usage particulier :
aucun identifiant de technique ATT&CK ni d'actif n'est codé en dur dans ce
module, seulement dans les tests.

Convention : identifiants de code en anglais, commentaires et docstrings en
français (§25.1).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import networkx as nx

from src.schemas import AttackGraph, AttackGraphEdge, TechniqueOccurrence

# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def build_attack_graph(
    nodes: Sequence[TechniqueOccurrence],
    edges: Sequence[AttackGraphEdge],
) -> AttackGraph:
    """Réf. architecture : "3.1 Graphe d'attaque" — G = (V, E).

    Construit un AttackGraph à partir de séquences génériques de nœuds et
    d'arêtes. Toute validation (unicité des occurrences, arêtes dupliquées,
    références invalides, invariants de divergence de π) reste déléguée au
    modèle AttackGraph de schemas.py : ce module n'en duplique aucune.
    """
    return AttackGraph(nodes=list(nodes), edges=list(edges))


def load_attack_graph_json(path: str | Path) -> AttackGraph:
    """Réf. architecture : "3.1 Graphe d'attaque" — chargement depuis un
    fichier JSON conforme au schéma AttackGraph.

    Aucune valeur manquante n'est complétée automatiquement (§25.3) : un
    JSON syntaxiquement invalide lève json.JSONDecodeError, un contenu qui
    ne respecte pas le schéma lève pydantic.ValidationError. Le chemin est
    générique : aucun fichier de cas d'usage n'est codé en dur ici.
    """
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as file:
        raw_data = json.load(file)
    return AttackGraph.model_validate(raw_data)


# ---------------------------------------------------------------------------
# Représentation opérationnelle NetworkX
# ---------------------------------------------------------------------------


def to_networkx(graph: AttackGraph) -> nx.DiGraph:
    """Réf. architecture : "26. Modules recommandés — graph_builder.py" —
    représentation opérationnelle de G = (V, E) pour la navigation, les
    degrés et les parcours des futurs modules.

    Copie fidèle, sans recalcul : la clé de chaque nœud NetworkX est
    occurrence_id, l'objet TechniqueOccurrence est conservé sous la clé
    "occurrence", et branch_probability est conservé tel quel sur chaque
    arête (y compris None). AttackGraph interdit déjà les arêtes
    dupliquées (E est un ensemble, §3.1) : un DiGraph simple suffit, pas de
    MultiDiGraph.
    """
    nx_graph = nx.DiGraph()
    for node in graph.nodes:
        nx_graph.add_node(node.occurrence_id, occurrence=node)
    for edge in graph.edges:
        nx_graph.add_edge(
            edge.source_id,
            edge.target_id,
            branch_probability=edge.branch_probability,
        )
    return nx_graph


# ---------------------------------------------------------------------------
# Navigation parents / enfants
# ---------------------------------------------------------------------------


def get_parent_ids(graph: AttackGraph, occurrence_id: str) -> list[str]:
    """Réf. architecture : "3.1 Graphe d'attaque" — occurrence_id des
    parents T_{u,g} tels que (T_{u,g}, T_{i,h}) ∈ E, dans l'ordre où ces
    arêtes ont été ajoutées à la représentation NetworkX (donc l'ordre de
    graph.edges)."""
    nx_graph = to_networkx(graph)
    if occurrence_id not in nx_graph:
        raise ValueError(f"Occurrence '{occurrence_id}' absente du graphe.")
    return list(nx_graph.predecessors(occurrence_id))


def get_child_ids(graph: AttackGraph, occurrence_id: str) -> list[str]:
    """Réf. architecture : "3.1 Graphe d'attaque" — occurrence_id des
    enfants T_{j,h'} tels que (T_{i,h}, T_{j,h'}) ∈ E, dans l'ordre où ces
    arêtes ont été ajoutées à la représentation NetworkX (donc l'ordre de
    graph.edges)."""
    nx_graph = to_networkx(graph)
    if occurrence_id not in nx_graph:
        raise ValueError(f"Occurrence '{occurrence_id}' absente du graphe.")
    return list(nx_graph.successors(occurrence_id))


# ---------------------------------------------------------------------------
# Nœuds Entry
# ---------------------------------------------------------------------------

# Réf. architecture : "5. Nœuds d'entrée" — libellé canonique retenu pour
# InitialAccess dans Tactics(T_i). La normalisation des tactiques ATT&CK
# brutes vers ce libellé est la responsabilité future de
# knowledge_attack.py ; graph_builder.py suppose que Tactics(T_i) est déjà
# normalisé dans NodeAttributes.tactics.
ENTRY_TACTIC_LABEL = "initial-access"


def is_entry_node(node: TechniqueOccurrence) -> bool:
    """Réf. architecture : "5. Nœuds d'entrée" —

    Entry(T_{i,h}) = 1 ssi InitialAccess ∈ Tactics(T_i) ET Accessible(h) = 1.

    Aucune autre condition n'est appliquée : ni correspondance approximative
    sur les tactiques, ni degré entrant, ni budget.
    """
    return ENTRY_TACTIC_LABEL in node.attributes.tactics and node.attributes.accessible_asset


def identify_entry_nodes(graph: AttackGraph) -> list[str]:
    """Réf. architecture : "5. Nœuds d'entrée" — occurrence_id des nœuds
    Entry, dans l'ordre de graph.nodes."""
    return [node.occurrence_id for node in graph.nodes if is_entry_node(node)]


# ---------------------------------------------------------------------------
# Nœuds Terminal
# ---------------------------------------------------------------------------


def _validate_unit_threshold(value: float, name: str) -> None:
    """Réf. architecture : "25.2 Bornes" — un seuil theta doit être dans
    [0,1]. Aucune valeur par défaut n'est prévue par l'architecture pour
    theta_C, theta_I, theta_A (§6) : ils doivent donc toujours être fournis
    explicitement par l'appelant (§25.3)."""
    if not 0.0 <= value <= 1.0:
        raise ValueError(
            f"Le seuil '{name}' doit être compris dans [0,1] (valeur reçue : {value})."
        )


def is_terminal_node(
    node: TechniqueOccurrence,
    theta_c: float,
    theta_i: float,
    theta_a: float,
) -> bool:
    """Réf. architecture : "6. Nœuds terminaux" —

    Terminal(T_{i,h}) = 1 si Critical(h) = 1 OU I^C_{i,h} >= theta_C OU
    I^I_{i,h} >= theta_I OU I^A_{i,h} >= theta_A.

    L'absence d'enfants (out-degree = 0) n'est jamais, à elle seule, un
    critère Terminal.
    """
    _validate_unit_threshold(theta_c, "theta_c")
    _validate_unit_threshold(theta_i, "theta_i")
    _validate_unit_threshold(theta_a, "theta_a")
    attrs = node.attributes
    return (
        attrs.critical_asset
        or attrs.impact_confidentiality >= theta_c
        or attrs.impact_integrity >= theta_i
        or attrs.impact_availability >= theta_a
    )


def identify_terminal_nodes(
    graph: AttackGraph,
    theta_c: float,
    theta_i: float,
    theta_a: float,
) -> list[str]:
    """Réf. architecture : "6. Nœuds terminaux" — occurrence_id des nœuds
    Terminal, dans l'ordre de graph.nodes."""
    return [
        node.occurrence_id
        for node in graph.nodes
        if is_terminal_node(node, theta_c, theta_i, theta_a)
    ]
