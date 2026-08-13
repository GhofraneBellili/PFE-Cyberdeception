"""
Réf. architecture : CLAUDE.md — contrat technique du PFE Cyberdéception.

Structures de données communes du modèle (§26 "schemas.py"). Ce module ne
contient aucune logique métier (pas de calcul de risque, pas d'admissibilité,
pas d'optimisation) : uniquement la définition et la validation des objets
échangés entre les autres modules.

Convention : identifiants de code en anglais, commentaires et docstrings en
français (§25.1).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

# ---------------------------------------------------------------------------
# Types communs
# ---------------------------------------------------------------------------

# Réf. architecture : "25.2 Bornes" — toute quantité probabiliste ou score
# normalisé doit vérifier 0 <= x <= 1 (q, impacts, sous-métriques LLM,
# Realism, InteractionLikelihood, P_engage, Effectiveness_prog, DE, Gamma,
# pi, A, P, R si impact normalisé).
UnitInterval = Annotated[float, Field(ge=0.0, le=1.0)]

# Réf. architecture : "3.1 Graphe d'attaque" / "8. Base de connaissances
# ATT&CK" — Ti est un identifiant de technique MITRE ATT&CK (ex. "T1566",
# "T1078.001").
ATTACK_TECHNIQUE_ID_PATTERN = r"^T\d{4}(\.\d{3})?$"


class StrictModel(BaseModel):
    """Modèle de base : rejette tout champ non déclaré.

    Aucun modèle de ce fichier n'autorise de champs supplémentaires
    implicites (extra="allow") afin de ne jamais masquer une faute de frappe
    sur un nom de champ ; les extensions explicitement autorisées par
    l'architecture (ex. §9.2 pour la fiche de déception) passent par un champ
    `metadata` nommé et typé plutôt que par extra="allow".
    """

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# a) Occurrence T_{i,h} et graphe d'attaque
# Réf. architecture : "3.1 Graphe d'attaque", "3.2 Outcomes",
# "3.3 Attributs minimums d'un nœud" (§2.3 PDF)
# ---------------------------------------------------------------------------


class NodeAttributes(StrictModel):
    """Réf. architecture : "3.3 Attributs minimums d'un nœud" (§2.3 PDF).

    Dictionnaire d'attributs Attr(T_{i,h}) d'une occurrence d'attaque.
    Aucun champ n'a de valeur par défaut inventée (§25.3) : une donnée
    manquante doit provoquer une erreur de validation explicite.
    """

    tactics: list[str] = Field(
        ...,
        min_length=1,
        description="Tactics(T_i) : tactiques ATT&CK associées à la technique T_i.",
    )
    # OPEN_DECISION levée le 2026-08-12 avec l'utilisateur : ni CLAUDE.md
    # (§3.3) ni le PDF (§2.3 : « ensemble des outcomes produits par la
    # réussite de T_i sur h ») ne définissent de sous-schéma pour un
    # outcome. Retenu : une liste de libellés (list[str]).
    outcomes: list[str] = Field(
        default_factory=list,
        description="O_{i,h} : outcomes produits par la réussite de T_i sur "
        "h. Attribut du nœud uniquement — ne doit jamais devenir un sommet "
        "indépendant du graphe (§3.2).",
    )
    q_local_success: UnitInterval = Field(
        ..., description="q_{i,h} : probabilité locale de réussite (§12.1)."
    )
    impact_confidentiality: UnitInterval = Field(..., description="I^C_{i,h}")
    impact_integrity: UnitInterval = Field(..., description="I^I_{i,h}")
    impact_availability: UnitInterval = Field(..., description="I^A_{i,h}")
    critical_asset: bool = Field(
        ..., description="Critical(h) : l'actif h constitue un objectif critique."
    )
    accessible_asset: bool = Field(
        ...,
        description="Accessible(h) : l'actif h est accessible à l'attaquant à l'état initial.",
    )


def build_occurrence_id(technique_id: str, asset_id: str) -> str:
    """Construit l'identifiant canonique T_{i,h} = technique_id@asset_id.

    Réf. architecture : "3.1 Graphe d'attaque" — un nœud est le couple
    (T_i, h). Fonction partagée pour que TechniqueOccurrence et les arêtes
    du graphe utilisent systématiquement la même règle de construction.
    """
    return f"{technique_id}@{asset_id}"


class TechniqueOccurrence(StrictModel):
    """Réf. architecture : "3.1 Graphe d'attaque" / "3.3 Attributs minimums
    d'un nœud" (§2.3 PDF).

    Un nœud V = {T_{i,h}} : occurrence de la technique ATT&CK technique_id
    exécutée sur l'actif asset_id.
    """

    technique_id: str = Field(
        ...,
        pattern=ATTACK_TECHNIQUE_ID_PATTERN,
        description="T_i : identifiant MITRE ATT&CK (ex. 'T1566', 'T1078.001').",
    )
    asset_id: str = Field(..., min_length=1, description="h : actif d'exécution.")
    attributes: NodeAttributes

    @computed_field  # type: ignore[misc]
    @property
    def occurrence_id(self) -> str:
        """Identifiant canonique T_{i,h}, ex. 'T1003@DC' (réf. §3.1)."""
        return build_occurrence_id(self.technique_id, self.asset_id)


class AttackGraphEdge(StrictModel):
    """Réf. architecture : "3.1 Graphe d'attaque" — arête
    (T_{i,h}, T_{j,h'}) ∈ E.

    Signifie que l'occurrence source_id précède l'occurrence target_id dans
    le scénario d'attaque. source_id/target_id doivent correspondre à un
    occurrence_id existant du graphe (vérifié au niveau AttackGraph).
    """

    source_id: str = Field(..., description="occurrence_id du nœud parent T_{u,g}.")
    target_id: str = Field(..., description="occurrence_id du nœud enfant T_{i,h}.")
    branch_probability: UnitInterval | None = Field(
        default=None,
        description="π_{(u,g)→(i,h)} explicite (§14.4). None : calculé comme "
        "1/|Children| en divergence par le moteur de risque (défaut autorisé, "
        "§25.3). Doit rester None si le parent n'a qu'un seul enfant (π "
        "uniquement en divergence, invariant §29.15).",
    )

    @model_validator(mode="after")
    def _no_self_loop(self) -> AttackGraphEdge:
        """Réf. architecture : "3.1 Graphe d'attaque" — une arête relie
        deux occurrences distinctes."""
        if self.source_id == self.target_id:
            raise ValueError("Une arête ne peut pas relier un nœud à lui-même.")
        return self


class AttackGraph(StrictModel):
    """Réf. architecture : "3.1 Graphe d'attaque" — G = (V, E)."""

    nodes: list[TechniqueOccurrence] = Field(..., min_length=1)
    edges: list[AttackGraphEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_graph_integrity(self) -> AttackGraph:
        """Vérifie l'unicité des occurrences et la validité des références
        des arêtes.

        Le typage nodes: list[TechniqueOccurrence] est la garantie
        structurelle principale qu'un outcome (chaîne libre) ne peut jamais
        être ajouté comme sommet indépendant (§3.2) : seule une occurrence
        T_{i,h} valide (avec un technique_id ATT&CK) peut figurer dans
        `nodes`.
        """
        occurrence_ids = [node.occurrence_id for node in self.nodes]
        if len(occurrence_ids) != len(set(occurrence_ids)):
            raise ValueError("Des occurrences T_{i,h} dupliquées ont été détectées dans V.")
        known_ids = set(occurrence_ids)
        for edge in self.edges:
            if edge.source_id not in known_ids:
                raise ValueError(f"Arête invalide : source '{edge.source_id}' absente de V.")
            if edge.target_id not in known_ids:
                raise ValueError(f"Arête invalide : cible '{edge.target_id}' absente de V.")
        return self

    @model_validator(mode="after")
    def _validate_divergence_invariants(self) -> AttackGraph:
        """Réf. architecture : "14.4 Probabilité transmise sur une arête" —
        π intervient uniquement en divergence (invariant §29.15).

        - out-degree = 1 (parent non divergent) : branch_probability doit
          être None.
        - out-degree > 1 (parent divergent) : soit toutes les arêtes du
          parent portent un branch_probability explicite dont la somme vaut
          1, soit aucune n'en porte (défaut équiprobable calculé en aval,
          §25.3). Aucun mélange explicite/None n'est toléré pour un même
          parent.
        """
        edges_by_parent: dict[str, list[AttackGraphEdge]] = {}
        for edge in self.edges:
            edges_by_parent.setdefault(edge.source_id, []).append(edge)

        for parent_id, children_edges in edges_by_parent.items():
            probabilities = [edge.branch_probability for edge in children_edges]

            if len(children_edges) == 1:
                if probabilities[0] is not None:
                    raise ValueError(
                        f"Nœud '{parent_id}' non divergent (un seul enfant) : "
                        "branch_probability doit être None (§14.4, π uniquement "
                        "en divergence)."
                    )
                continue

            n_explicit = sum(p is not None for p in probabilities)
            if 0 < n_explicit < len(probabilities):
                raise ValueError(
                    f"Nœud '{parent_id}' divergent : mélange de branch_probability "
                    "explicites et implicites interdit (toutes les branches ou "
                    "aucune)."
                )
            if n_explicit == len(probabilities):
                total = sum(p for p in probabilities if p is not None)
                if abs(total - 1.0) > 1e-6:
                    raise ValueError(
                        f"Nœud '{parent_id}' divergent : la somme des "
                        f"branch_probability ({total}) doit être égale à 1 (§14.4)."
                    )
        return self


# ---------------------------------------------------------------------------
# b) Fiche de mécanisme de déception
# Réf. architecture : "9.2 Schéma conceptuel recommandé pour une fiche de
# déception" (§7.2.3 PDF)
# ---------------------------------------------------------------------------


class DeceptionEvidence(StrictModel):
    """Réf. architecture : "9.2 Schéma conceptuel recommandé pour une fiche
    de déception" — élément de preuve associé à un champ de la fiche."""

    source: str = Field(..., min_length=1)
    passage: str = Field(..., min_length=1)


class DeceptionResourceRequirements(StrictModel):
    """Réf. architecture : "9.2 Schéma conceptuel recommandé pour une fiche
    de déception" — resource_requirements. cpu/ram sont les deux champs du
    schéma de référence ; disk/network sont ajoutés pour couvrir les quatre
    dimensions du coût des ressources (§15.2 : r_CPU, r_RAM, r_disk,
    r_network), utiles au futur cost_engine.py. Tous optionnels car non
    toujours documentés par la source (§25.3 : ne pas inventer une valeur
    absente)."""

    cpu: str | None = None
    ram: str | None = None
    disk: str | None = None
    network: str | None = None


class DeceptionAdmissibilityProfile(StrictModel):
    """Réf. architecture : "10.4 Étape 3 — Emplacements admissibles" (§5.3.1
    PDF) — représentation normalisée minimale destinée aux futures règles
    déterministes Allowed(d, l) et RequirementsSatisfied(d, l) du module
    admissibility.py (§26, SP1). Cette structure ne prend aucune décision
    SP1 elle-même : elle ne fait que porter, sous forme normalisée, des
    données déjà présentes de façon documentaire dans requirements,
    target_artifacts et possible_placements. Le calcul de L_{i,h,d} et
    C_{i,h} reste hors périmètre de schemas.py.

    exposure_mode reste un champ libre (pas d'énumération fermée à ce
    stade, l'architecture ne l'impose pas).
    """

    allowed_location_types: list[str] = Field(default_factory=list)
    required_asset_types: list[str] = Field(default_factory=list)
    required_services: list[str] = Field(default_factory=list)
    required_artifacts: list[str] = Field(default_factory=list)
    exposure_mode: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeceptionMechanism(StrictModel):
    """Réf. architecture : "9.2 Schéma conceptuel recommandé pour une fiche
    de déception" (§7.2.3 PDF).

    Fiche décrivant un mécanisme d appartenant au catalogue fermé D (§7).
    """

    id: str = Field(
        ...,
        min_length=1,
        description="Identifiant du mécanisme dans le catalogue fermé D. "
        "'DTxx' n'est qu'illustratif dans la source : la KB peut utiliser "
        "d'autres schémas d'identifiants (ex. issus de D3FEND).",
    )
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    target_artifacts: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    possible_placements: list[str] = Field(default_factory=list)
    interaction_mechanism: str = Field(..., min_length=1)
    realism_factors: list[str] = Field(default_factory=list)
    progression_effects: list[Literal["stop", "redirect", "contain", "delay"]] = Field(
        default_factory=list,
        description="Effets de progression correspondant aux sous-métriques "
        "S_stop, S_redirect, S_contain, S_delay (§11.3).",
    )
    resource_requirements: DeceptionResourceRequirements = Field(
        default_factory=DeceptionResourceRequirements
    )
    maintenance_requirements: list[str] = Field(default_factory=list)
    evidence: list[DeceptionEvidence] = Field(default_factory=list)
    version: str = Field(..., min_length=1)
    admissibility_profile: DeceptionAdmissibilityProfile = Field(
        default_factory=DeceptionAdmissibilityProfile,
        description="Représentation normalisée préparant l'admissibilité "
        "SP1 (§10.4) — ne remplace pas requirements/target_artifacts/"
        "possible_placements, qui restent les champs documentaires de "
        "référence.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Champs techniques supplémentaires explicitement "
        "autorisés par §9.2, sans changer le sens des champs de référence "
        "ci-dessus.",
    )


# ---------------------------------------------------------------------------
# c) Annotation auditable
# Réf. architecture : "11.3 Sous-métriques annotées par le LLM",
# "11.4 Format minimum de sortie d'une annotation" (§8.3/§8.4 PDF)
# ---------------------------------------------------------------------------


AnnotationMetricName = Literal[
    "R_tech",
    "R_context",
    "R_perception",
    "R_behavior",
    "A_object",
    "A_action",
    "A_source",
    "S_stop",
    "S_redirect",
    "S_contain",
    "S_delay",
]


class Annotation(StrictModel):
    """Réf. architecture : "11.3 Sous-métriques annotées par le LLM" +
    "11.4 Format minimum de sortie d'une annotation" (§8.3/§8.4 PDF).

    Annotation auditable d'une sous-métrique sémantique pour un candidat
    (T_{i,h}, d, l). Le LLM ne calcule jamais Realism, InteractionLikelihood,
    P_engage, Effectiveness_prog, DE ni le risque (§11.5) : cette structure
    ne porte que le résultat brut d'une annotation de sous-métrique.
    """

    metric: AnnotationMetricName
    score: UnitInterval
    justification: str = Field(
        ..., min_length=1, description="Justification textuelle obligatoire (§28)."
    )
    evidence: list[str] = Field(
        ...,
        min_length=1,
        description="Identifiants de source ou de chunk RAG (§11.4), ex. "
        "'source_A#chunk_17'.",
    )
    confidence: UnitInterval

    # Champs de traçabilité recommandés par §11.4 — optionnels car non
    # strictement obligatoires dans le format minimum, mais jamais générés
    # silencieusement s'ils sont absents (§25.3).
    model_version: str | None = None
    prompt_version: str | None = None
    kb_version: str | None = None
    annotated_at: datetime | None = None
    annotation_id: str | None = None


# ---------------------------------------------------------------------------
# d) Contexte remis à l'annotateur
# Réf. architecture : "27. Schéma minimal conseillé pour le contexte
# d'annotation" (§8.2 PDF)
# ---------------------------------------------------------------------------


class AttackOccurrenceRef(StrictModel):
    """Réf. architecture : "27. Schéma minimal conseillé pour le contexte
    d'annotation" — bloc attack_occurrence. Le champ est nommé asset_id
    (plutôt que 'asset' comme dans l'exemple JSON du §27) pour rester
    cohérent avec TechniqueOccurrence, Asset et Location ; §27 autorise
    explicitement cette évolution de format (« le format exact de code peut
    évoluer »)."""

    technique_id: str = Field(..., pattern=ATTACK_TECHNIQUE_ID_PATTERN)
    asset_id: str = Field(..., min_length=1)
    attributes: NodeAttributes

    @computed_field  # type: ignore[misc]
    @property
    def occurrence_id(self) -> str:
        """Identifiant canonique T_{i,h}, cohérent avec TechniqueOccurrence."""
        return build_occurrence_id(self.technique_id, self.asset_id)


class DeceptionRef(StrictModel):
    """Réf. architecture : "27. Schéma minimal conseillé pour le contexte
    d'annotation" — bloc deception (référence légère, pas la fiche
    complète)."""

    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)


class GraphContext(StrictModel):
    """Réf. architecture : "27. Schéma minimal conseillé pour le contexte
    d'annotation" — bloc graph_context."""

    parents: list[str] = Field(default_factory=list)
    children: list[str] = Field(default_factory=list)
    terminal_paths: list[list[str]] = Field(
        default_factory=list,
        description="Chemins (listes d'occurrence_id) vers des nœuds terminaux.",
    )


_FORBIDDEN_BUDGET_KEYS = {"budget", "b_total", "budget_total", "total_budget"}


def _contains_budget_key(value: Any) -> bool:
    """Parcourt récursivement une structure dict/list pour détecter une clé
    évoquant le budget total, y compris dans un sous-dictionnaire imbriqué.

    Réf. architecture : "11.2 Entrées du LLM — Interdiction" : B_total ne
    doit jamais être fourni à l'annotateur, pour éviter un biais économique.
    """
    if isinstance(value, dict):
        for key, sub_value in value.items():
            if str(key).lower() in _FORBIDDEN_BUDGET_KEYS:
                return True
            if _contains_budget_key(sub_value):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_budget_key(item) for item in value)
    return False


class AnnotationContext(StrictModel):
    """Réf. architecture : "27. Schéma minimal conseillé pour le contexte
    d'annotation" (§8.2 PDF).

    Contexte remis à l'annotateur LLM+RAG pour un candidat (T_{i,h}, d, l).
    """

    attack_occurrence: AttackOccurrenceRef
    deception: DeceptionRef
    placement: str = Field(..., min_length=1, description="l : emplacement candidat.")
    graph_context: GraphContext = Field(default_factory=GraphContext)
    system_context: dict[str, Any] = Field(default_factory=dict)
    retrieved_evidence: list[DeceptionEvidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def _no_budget_leak(self) -> AnnotationContext:
        """Réf. architecture : "11.2 Entrées du LLM — Interdiction"."""
        if _contains_budget_key(self.system_context):
            raise ValueError(
                "Le budget B_total ne doit jamais être inclus, même de "
                "manière imbriquée, dans le contexte d'annotation (§11.2)."
            )
        return self


# ---------------------------------------------------------------------------
# e) Instance : graphe, inventaire SI, emplacements
# Réf. architecture : "10.3 Étape 2 — Ensemble global des emplacements",
# "4. Construction / génération du graphe" (§5.3/§2.2 PDF)
# ---------------------------------------------------------------------------


class Asset(StrictModel):
    """Réf. architecture : "4. Construction / génération du graphe" (§2.2
    PDF, étapes 1-2) — élément de l'inventaire du SI, potentiel actif
    d'exécution h d'une occurrence.
    """

    asset_id: str = Field(..., min_length=1)
    asset_type: str | None = Field(
        default=None,
        description="Type d'actif (poste, serveur, ... — exemples non "
        "exhaustifs, §2.2).",
    )
    critical: bool = Field(..., description="Critical(h), source de vérité de l'inventaire.")
    accessible: bool = Field(
        ..., description="Accessible(h), source de vérité de l'inventaire."
    )
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Enrichissement ouvert (services exposés, "
        "configurations, vulnérabilités, « et autres informations "
        "pertinentes », §2.2/§4) : aucun schéma fermé n'est donné par "
        "l'architecture pour ces données.",
    )


class Location(StrictModel):
    """Réf. architecture : "10.3 Étape 2 — Ensemble global des
    emplacements" (§5.3.1 PDF) — élément de L^SI, cible possible de
    placement d'un mécanisme de déception.
    """

    location_id: str = Field(..., min_length=1)
    location_type: str | None = Field(
        default=None,
        description="Type d'emplacement (poste, serveur, service, compte, "
        "base de données, segment réseau, magasin de credentials, "
        "ressource applicative — exemples non exhaustifs du §10.3, pas une "
        "énumération fermée).",
    )
    asset_id: str | None = Field(
        default=None,
        description="Lien topologique optionnel vers l'actif de "
        "l'inventaire sur lequel repose cet emplacement (§5.3.2 : relation "
        "topologique entre h et l).",
    )


class SITopologyEdge(StrictModel):
    """Réf. architecture : "10.4 Étape 3 — Emplacements admissibles" (§5.3.1
    PDF) — Relevant(T_{i,h}, d, l) peut dépendre de la relation topologique
    entre h et l. Représentation minimale et générique d'une relation
    physique/logique entre deux actifs du SI.

    À distinguer explicitement de AttackGraphEdge : une arête topologique
    relie deux actifs du SI (relation d'infrastructure), alors qu'une arête
    du graphe d'attaque relie deux occurrences T_{i,h} (précédence dans un
    scénario). relation_type est volontairement un champ libre : ni
    CLAUDE.md ni le PDF ne définissent d'ontologie fermée de relations
    topologiques. Aucune contrainte d'acyclicité n'est imposée à ce stade.
    """

    source_asset_id: str = Field(..., min_length=1)
    target_asset_id: str = Field(..., min_length=1)
    relation_type: str = Field(
        ...,
        min_length=1,
        description="Nature de la relation (ex. 'network_adjacency', "
        "'hosts_service', 'trust_relationship', ...) — champ libre, non "
        "fermé par l'architecture.",
    )
    bidirectional: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


class SIInventory(StrictModel):
    """Réf. architecture : "10.3 Étape 2 — Ensemble global des
    emplacements" — inventaire du système d'information : actifs,
    emplacements L^SI et topologie entre actifs (§10.4, Relevant)."""

    assets: list[Asset] = Field(default_factory=list)
    locations: list[Location] = Field(default_factory=list)
    topology_edges: list[SITopologyEdge] = Field(default_factory=list)


class SystemInstance(StrictModel):
    """Réf. architecture : Figure 6.1 (§6.1 PDF) — bloc « Instance du
    système d'information » : G = (V, E), attributs, inventaire, topologie,
    emplacements disponibles.

    Regroupe le graphe d'attaque et l'inventaire SI (actifs + emplacements)
    d'une instance concrète, avec vérification croisée de leur cohérence.
    """

    graph: AttackGraph
    si_inventory: SIInventory

    @model_validator(mode="after")
    def _validate_instance_consistency(self) -> SystemInstance:
        """Vérifie l'unicité des identifiants de l'inventaire, l'existence
        des actifs référencés par le graphe et les emplacements, et la
        cohérence stricte de Critical(h)/Accessible(h) entre l'inventaire
        (source de vérité) et les attributs de chaque occurrence."""
        asset_ids = [asset.asset_id for asset in self.si_inventory.assets]
        if len(asset_ids) != len(set(asset_ids)):
            raise ValueError("Identifiants d'actifs dupliqués dans l'inventaire SI.")

        location_ids = [loc.location_id for loc in self.si_inventory.locations]
        if len(location_ids) != len(set(location_ids)):
            raise ValueError("Identifiants d'emplacements dupliqués dans L^SI.")

        assets_by_id = {asset.asset_id: asset for asset in self.si_inventory.assets}

        for node in self.graph.nodes:
            asset = assets_by_id.get(node.asset_id)
            if asset is None:
                raise ValueError(
                    f"L'actif '{node.asset_id}' utilisé par le nœud "
                    f"'{node.occurrence_id}' est absent de l'inventaire SI."
                )
            if node.attributes.critical_asset != asset.critical:
                raise ValueError(
                    f"Incohérence Critical(h) entre le nœud '{node.occurrence_id}' "
                    f"({node.attributes.critical_asset}) et l'inventaire SI pour "
                    f"l'actif '{node.asset_id}' ({asset.critical})."
                )
            if node.attributes.accessible_asset != asset.accessible:
                raise ValueError(
                    f"Incohérence Accessible(h) entre le nœud "
                    f"'{node.occurrence_id}' ({node.attributes.accessible_asset}) "
                    f"et l'inventaire SI pour l'actif '{node.asset_id}' "
                    f"({asset.accessible})."
                )

        for location in self.si_inventory.locations:
            if location.asset_id is not None and location.asset_id not in assets_by_id:
                raise ValueError(
                    f"L'emplacement '{location.location_id}' référence un "
                    f"actif '{location.asset_id}' absent de l'inventaire SI."
                )

        for edge in self.si_inventory.topology_edges:
            if edge.source_asset_id not in assets_by_id:
                raise ValueError(
                    f"L'arête topologique référence un actif source "
                    f"'{edge.source_asset_id}' absent de l'inventaire SI."
                )
            if edge.target_asset_id not in assets_by_id:
                raise ValueError(
                    f"L'arête topologique référence un actif cible "
                    f"'{edge.target_asset_id}' absent de l'inventaire SI."
                )

        return self
