"""Result shapes returned by analytics backends (backend-agnostic)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CentralityMetric(str, Enum):
    DEGREE = "degree"
    BETWEENNESS = "betweenness"
    EIGENVECTOR = "eigenvector"
    PAGERANK = "pagerank"


class PathKind(str, Enum):
    SHORTEST = "shortest"        # fewest hops
    STRONGEST = "strongest"      # maximize the weakest edge (widest/bottleneck)
    MOST_LIKELY = "most_likely"  # maximize product of edge confidences


@dataclass(slots=True)
class RankedNode:
    id: str
    name: str
    type: str
    score: float


@dataclass(slots=True)
class Community:
    id: int
    size: int
    members: list[RankedNode]


@dataclass(slots=True)
class CommunityResult:
    algorithm: str
    modularity: float
    community_count: int
    communities: list[Community]


@dataclass(slots=True)
class PathEdge:
    rel_id: str | None
    source: str
    target: str
    type: str | None
    confidence: float


@dataclass(slots=True)
class GraphPath:
    kind: str
    nodes: list[RankedNode]
    edges: list[PathEdge]
    length: int                       # number of hops
    score: float                      # interpretation depends on kind
    bottleneck_confidence: float = 0.0  # min edge confidence along the path


@dataclass(slots=True)
class PathResult:
    found: bool
    paths: list[GraphPath] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Advanced analytics (brokerage, roles, anomalies, resilience, influence,
# motifs) — result shapes, backend-agnostic.
# --------------------------------------------------------------------------- #

@dataclass(slots=True)
class BrokerNode:
    id: str
    name: str
    type: str
    betweenness: float
    constraint: float        # Burt's constraint; lower ⇒ spans more structural holes
    effective_size: float    # number of non-redundant contacts
    is_articulation: bool     # removing it disconnects part of the graph


@dataclass(slots=True)
class SuggestedLink:
    """A plausible-but-unrecorded edge (link prediction / missing intermediary)."""
    source: str
    source_name: str
    target: str
    target_name: str
    score: float
    method: str
    common_neighbors: int


@dataclass(slots=True)
class BrokerageResult:
    brokers: list[BrokerNode] = field(default_factory=list)
    bridges: list[PathEdge] = field(default_factory=list)          # cut edges
    suggested_links: list[SuggestedLink] = field(default_factory=list)


@dataclass(slots=True)
class RoleAssignment:
    id: str
    name: str
    type: str
    role: str
    rationale: str
    degree: float
    betweenness: float
    pagerank: float
    clustering: float


@dataclass(slots=True)
class RoleResult:
    roles: list[RoleAssignment] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class Anomaly:
    id: str
    name: str
    type: str
    kind: str       # "hub" | "bridge" | "isolate"
    score: float    # severity (σ for hubs, percentile-rank for bridges)
    reason: str


@dataclass(slots=True)
class AnomalyResult:
    anomalies: list[Anomaly] = field(default_factory=list)
    degree_mean: float = 0.0
    degree_stdev: float = 0.0


@dataclass(slots=True)
class NodeImpact:
    id: str
    name: str
    type: str
    components_after: int
    largest_component_after: int
    fragmentation: float      # 1 − (largest component / remaining nodes)
    reachability_drop: float  # relative shrink of the largest component


@dataclass(slots=True)
class ResilienceResult:
    baseline_components: int
    baseline_largest: int
    node_count: int
    impacts: list[NodeImpact] = field(default_factory=list)


@dataclass(slots=True)
class InfluenceNode:
    id: str
    name: str
    type: str
    activation_probability: float


@dataclass(slots=True)
class InfluenceResult:
    seeds: list[str]
    trials: int
    expected_spread: float
    activated: list[InfluenceNode] = field(default_factory=list)


@dataclass(slots=True)
class Motif:
    kind: str               # "triangle" | "clique-4" | ...
    nodes: list[RankedNode]
    weight: float           # mean intra-motif edge confidence


@dataclass(slots=True)
class MotifResult:
    triangle_count: int
    clique_size_distribution: dict[int, int] = field(default_factory=dict)
    motifs: list[Motif] = field(default_factory=list)
