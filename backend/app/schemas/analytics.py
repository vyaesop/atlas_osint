from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.models.enums import EntityType


class RankedNodeRead(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    score: float


class CentralityResponse(BaseModel):
    metric: str
    graph_order: int
    truncated: bool
    results: list[RankedNodeRead]


class CommunityRead(BaseModel):
    id: int
    size: int
    members: list[RankedNodeRead]


class CommunitiesResponse(BaseModel):
    algorithm: str
    modularity: float
    community_count: int
    graph_order: int
    truncated: bool
    communities: list[CommunityRead]


class PathEdgeRead(BaseModel):
    rel_id: uuid.UUID | None
    source: uuid.UUID
    target: uuid.UUID
    type: str | None
    confidence: float


class PathRead(BaseModel):
    kind: str
    nodes: list[RankedNodeRead]
    edges: list[PathEdgeRead]
    length: int
    score: float
    bottleneck_confidence: float


class PathsResponse(BaseModel):
    found: bool
    paths: list[PathRead]


# --------------------------------------------------------------------------- #
# Advanced analytics responses
# --------------------------------------------------------------------------- #

class BrokerNodeRead(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    betweenness: float
    constraint: float
    effective_size: float
    is_articulation: bool


class SuggestedLinkRead(BaseModel):
    source: uuid.UUID
    source_name: str
    target: uuid.UUID
    target_name: str
    score: float
    method: str
    common_neighbors: int


class BrokerageResponse(BaseModel):
    graph_order: int
    truncated: bool
    brokers: list[BrokerNodeRead]
    bridges: list[PathEdgeRead]
    suggested_links: list[SuggestedLinkRead]


class RoleAssignmentRead(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    role: str
    rationale: str
    degree: float
    betweenness: float
    pagerank: float
    clustering: float


class RolesResponse(BaseModel):
    graph_order: int
    truncated: bool
    counts: dict[str, int]
    roles: list[RoleAssignmentRead]


class AnomalyRead(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    kind: str
    score: float
    reason: str


class AnomaliesResponse(BaseModel):
    graph_order: int
    truncated: bool
    degree_mean: float
    degree_stdev: float
    anomalies: list[AnomalyRead]


class NodeImpactRead(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    components_after: int
    largest_component_after: int
    fragmentation: float
    reachability_drop: float


class ResilienceResponse(BaseModel):
    graph_order: int
    truncated: bool
    baseline_components: int
    baseline_largest: int
    node_count: int
    impacts: list[NodeImpactRead]


class InfluenceNodeRead(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    activation_probability: float


class InfluenceResponse(BaseModel):
    graph_order: int
    truncated: bool
    seeds: list[uuid.UUID]
    trials: int
    expected_spread: float
    activated: list[InfluenceNodeRead]


class MotifRead(BaseModel):
    kind: str
    nodes: list[RankedNodeRead]
    weight: float


class MotifsResponse(BaseModel):
    graph_order: int
    truncated: bool
    triangle_count: int
    clique_size_distribution: dict[int, int]
    motifs: list[MotifRead]


# --- #15 hierarchy & cells ---

class HierarchyNodeRead(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    level: int
    reports_to: list[uuid.UUID]
    subordinate_count: int


class HierarchyResponse(BaseModel):
    graph_order: int
    truncated: bool
    is_acyclic: bool
    max_depth: int
    roots: list[uuid.UUID]
    nodes: list[HierarchyNodeRead]


class CellRead(BaseModel):
    id: int
    size: int
    topology: str
    density: float
    centralization: float
    clustering: float
    hub: RankedNodeRead | None
    members: list[RankedNodeRead]


class CellsResponse(BaseModel):
    graph_order: int
    truncated: bool
    cells: list[CellRead]


# Reusable query-filter doc (kept here for discoverability).
class AnalyticsFilterInfo(BaseModel):
    type: list[EntityType] | None = None
    min_confidence: float = 0.0
    ego_entity_id: uuid.UUID | None = None
    depth: int = 2
