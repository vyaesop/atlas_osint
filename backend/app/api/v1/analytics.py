from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.graph_loader import GraphFilters
from app.analytics.models import CentralityMetric, PathKind
from app.analytics.service import analytics_service
from app.core import cache
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.enums import EntityType, RelationshipType
from app.models.user import User
from app.schemas.analytics import (
    AnomaliesResponse,
    AnomalyRead,
    BrokerageResponse,
    BrokerNodeRead,
    CellRead,
    CellsResponse,
    CentralityResponse,
    CommunitiesResponse,
    CommunityRead,
    HierarchyNodeRead,
    HierarchyResponse,
    InfluenceNodeRead,
    InfluenceResponse,
    MotifRead,
    MotifsResponse,
    NodeImpactRead,
    PathEdgeRead,
    PathRead,
    PathsResponse,
    RankedNodeRead,
    ResilienceResponse,
    RoleAssignmentRead,
    RolesResponse,
    SuggestedLinkRead,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _filters(
    type: list[EntityType] | None,
    relationship_type: list[RelationshipType] | None,
    min_confidence: float,
    ego_entity_id: uuid.UUID | None,
    depth: int,
) -> GraphFilters:
    return GraphFilters(
        types=type,
        relationship_types=relationship_type,
        min_confidence=min_confidence,
        ego_entity_id=ego_entity_id,
        depth=depth,
    )


def _node(n) -> RankedNodeRead:
    return RankedNodeRead(id=n.id, name=n.name, type=n.type, score=n.score)


@router.get("/centrality", response_model=CentralityResponse)
async def centrality(
    metric: CentralityMetric = Query(default=CentralityMetric.DEGREE),
    limit: int = Query(default=25, ge=1, le=200),
    type: list[EntityType] | None = Query(default=None),
    relationship_type: list[RelationshipType] | None = Query(default=None),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    ego_entity_id: uuid.UUID | None = Query(default=None, description="Scope to this node's neighborhood"),
    depth: int = Query(default=2, ge=1, le=4),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Rank nodes by influence: degree, betweenness, eigenvector, or PageRank."""
    filters = _filters(type, relationship_type, min_confidence, ego_entity_id, depth)

    async def compute() -> CentralityResponse:
        results, graph = await analytics_service.centrality(db, metric, filters, limit=limit)
        return CentralityResponse(
            metric=metric.value, graph_order=graph.order, truncated=graph.truncated,
            results=[_node(n) for n in results],
        )

    params = {
        "metric": metric.value, "limit": limit,
        "type": [t.value for t in type] if type else None,
        "rel": [t.value for t in relationship_type] if relationship_type else None,
        "min_conf": min_confidence, "ego": str(ego_entity_id) if ego_entity_id else None,
        "depth": depth,
    }
    return await cache.cached_call(
        "centrality", params, compute,
        serialize=lambda r: r.model_dump(mode="json"),
        deserialize=lambda d: CentralityResponse(**d),
    )


@router.get("/communities", response_model=CommunitiesResponse)
async def communities(
    min_size: int = Query(default=2, ge=1, le=1000),
    type: list[EntityType] | None = Query(default=None),
    relationship_type: list[RelationshipType] | None = Query(default=None),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    ego_entity_id: uuid.UUID | None = Query(default=None),
    depth: int = Query(default=2, ge=1, le=4),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Detect communities/factions via Louvain modularity maximization."""
    filters = _filters(type, relationship_type, min_confidence, ego_entity_id, depth)

    async def compute() -> CommunitiesResponse:
        result, graph = await analytics_service.communities(db, filters, min_size=min_size)
        return CommunitiesResponse(
            algorithm=result.algorithm, modularity=result.modularity,
            community_count=result.community_count, graph_order=graph.order,
            truncated=graph.truncated,
            communities=[
                CommunityRead(id=c.id, size=c.size, members=[_node(m) for m in c.members])
                for c in result.communities
            ],
        )

    params = {
        "min_size": min_size,
        "type": [t.value for t in type] if type else None,
        "rel": [t.value for t in relationship_type] if relationship_type else None,
        "min_conf": min_confidence, "ego": str(ego_entity_id) if ego_entity_id else None,
        "depth": depth,
    }
    return await cache.cached_call(
        "communities", params, compute,
        serialize=lambda r: r.model_dump(mode="json"),
        deserialize=lambda d: CommunitiesResponse(**d),
    )


@router.get("/paths", response_model=PathsResponse)
async def paths(
    source: uuid.UUID,
    target: uuid.UUID,
    kind: PathKind = Query(default=PathKind.SHORTEST),
    k: int = Query(default=1, ge=1, le=10, description="Alternatives (SHORTEST only)"),
    max_length: int | None = Query(default=None, ge=1, le=12),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    relationship_type: list[RelationshipType] | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Discover paths between two entities.

    * **shortest** — fewest hops (set ``k`` > 1 for alternative routes)
    * **strongest** — maximizes the weakest link (bottleneck confidence)
    * **most_likely** — maximizes the product of edge confidences
    """
    filters = GraphFilters(
        relationship_types=relationship_type,
        min_confidence=min_confidence,
        # Paths need the whole reachable graph, not an ego scope.
        ego_entity_id=None,
    )
    result = await analytics_service.paths(
        db, str(source), str(target), kind, filters, k=k, max_length=max_length
    )
    if not result.found:
        # 200 with found=false is friendlier for "no path" than an error;
        # reserve 404 for a genuinely missing endpoint node.
        return PathsResponse(found=False, paths=[])
    return PathsResponse(
        found=True,
        paths=[
            PathRead(
                kind=p.kind,
                nodes=[_node(n) for n in p.nodes],
                edges=[
                    PathEdgeRead(
                        rel_id=e.rel_id, source=e.source, target=e.target,
                        type=e.type, confidence=e.confidence,
                    )
                    for e in p.edges
                ],
                length=p.length,
                score=p.score,
                bottleneck_confidence=p.bottleneck_confidence,
            )
            for p in result.paths
        ],
    )


# --------------------------------------------------------------------------- #
# Advanced analytics (#14, #16, #48, #50, #51, #52)
# --------------------------------------------------------------------------- #

@router.get("/brokers", response_model=BrokerageResponse)
async def brokers(
    limit: int = Query(default=25, ge=1, le=200),
    type: list[EntityType] | None = Query(default=None),
    relationship_type: list[RelationshipType] | None = Query(default=None),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    ego_entity_id: uuid.UUID | None = Query(default=None),
    depth: int = Query(default=2, ge=1, le=4),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Brokers & structural holes (#14): rank nodes by betweenness + Burt's
    constraint, list graph bridges (cut edges), and propose missing-intermediary
    links via Adamic-Adar link prediction (#12)."""
    filters = _filters(type, relationship_type, min_confidence, ego_entity_id, depth)
    result, graph = await analytics_service.brokerage(db, filters, limit=limit)
    return BrokerageResponse(
        graph_order=graph.order, truncated=graph.truncated,
        brokers=[
            BrokerNodeRead(
                id=b.id, name=b.name, type=b.type, betweenness=b.betweenness,
                constraint=b.constraint, effective_size=b.effective_size,
                is_articulation=b.is_articulation,
            )
            for b in result.brokers
        ],
        bridges=[
            PathEdgeRead(rel_id=e.rel_id, source=e.source, target=e.target,
                         type=e.type, confidence=e.confidence)
            for e in result.bridges
        ],
        suggested_links=[
            SuggestedLinkRead(
                source=s.source, source_name=s.source_name, target=s.target,
                target_name=s.target_name, score=s.score, method=s.method,
                common_neighbors=s.common_neighbors,
            )
            for s in result.suggested_links
        ],
    )


@router.get("/roles", response_model=RolesResponse)
async def roles(
    limit: int | None = Query(default=None, ge=1, le=1000),
    type: list[EntityType] | None = Query(default=None),
    relationship_type: list[RelationshipType] | None = Query(default=None),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    ego_entity_id: uuid.UUID | None = Query(default=None),
    depth: int = Query(default=2, ge=1, le=4),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Infer each entity's structural role (#16): leadership, hub, broker,
    gatekeeper, peripheral, core_member, associate, or isolate."""
    filters = _filters(type, relationship_type, min_confidence, ego_entity_id, depth)
    result, graph = await analytics_service.roles(db, filters, limit=limit)
    return RolesResponse(
        graph_order=graph.order, truncated=graph.truncated, counts=result.counts,
        roles=[
            RoleAssignmentRead(
                id=r.id, name=r.name, type=r.type, role=r.role, rationale=r.rationale,
                degree=r.degree, betweenness=r.betweenness, pagerank=r.pagerank,
                clustering=r.clustering,
            )
            for r in result.roles
        ],
    )


@router.get("/anomalies", response_model=AnomaliesResponse)
async def anomalies(
    z_threshold: float = Query(default=2.0, ge=0.5, le=6.0),
    limit: int = Query(default=50, ge=1, le=500),
    type: list[EntityType] | None = Query(default=None),
    relationship_type: list[RelationshipType] | None = Query(default=None),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    ego_entity_id: uuid.UUID | None = Query(default=None),
    depth: int = Query(default=2, ge=1, le=4),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Flag structural anomalies (#48): degree outliers (hubs), low-degree
    choke points (bridges), and isolates."""
    filters = _filters(type, relationship_type, min_confidence, ego_entity_id, depth)
    result, graph = await analytics_service.anomalies(
        db, filters, z_threshold=z_threshold, limit=limit
    )
    return AnomaliesResponse(
        graph_order=graph.order, truncated=graph.truncated,
        degree_mean=result.degree_mean, degree_stdev=result.degree_stdev,
        anomalies=[
            AnomalyRead(id=a.id, name=a.name, type=a.type, kind=a.kind,
                        score=a.score, reason=a.reason)
            for a in result.anomalies
        ],
    )


@router.get("/resilience", response_model=ResilienceResponse)
async def resilience(
    limit: int = Query(default=25, ge=1, le=200),
    type: list[EntityType] | None = Query(default=None),
    relationship_type: list[RelationshipType] | None = Query(default=None),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    ego_entity_id: uuid.UUID | None = Query(default=None),
    depth: int = Query(default=2, ge=1, le=4),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """What-if node removal (#50): for the top-degree nodes, measure how much
    removing each one fragments the network (components + reachability drop)."""
    filters = _filters(type, relationship_type, min_confidence, ego_entity_id, depth)
    result, graph = await analytics_service.resilience(db, filters, limit=limit)
    return ResilienceResponse(
        graph_order=graph.order, truncated=graph.truncated,
        baseline_components=result.baseline_components,
        baseline_largest=result.baseline_largest, node_count=result.node_count,
        impacts=[
            NodeImpactRead(
                id=i.id, name=i.name, type=i.type, components_after=i.components_after,
                largest_component_after=i.largest_component_after,
                fragmentation=i.fragmentation, reachability_drop=i.reachability_drop,
            )
            for i in result.impacts
        ],
    )


@router.get("/influence", response_model=InfluenceResponse)
async def influence(
    seed: list[uuid.UUID] = Query(..., description="One or more seed entity IDs"),
    trials: int = Query(default=200, ge=10, le=2000),
    type: list[EntityType] | None = Query(default=None),
    relationship_type: list[RelationshipType] | None = Query(default=None),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Influence / diffusion propagation (#51): Monte-Carlo Independent Cascade
    from the seed set over confidence-weighted edges. Returns each node's
    activation probability and the expected total spread."""
    # Diffusion needs the whole reachable graph, not an ego scope.
    filters = _filters(type, relationship_type, min_confidence, None, 2)
    result, graph = await analytics_service.influence(
        db, [str(s) for s in seed], filters, trials=trials
    )
    return InfluenceResponse(
        graph_order=graph.order, truncated=graph.truncated, seeds=result.seeds,
        trials=result.trials, expected_spread=result.expected_spread,
        activated=[
            InfluenceNodeRead(id=a.id, name=a.name, type=a.type,
                              activation_probability=a.activation_probability)
            for a in result.activated
        ],
    )


@router.get("/motifs", response_model=MotifsResponse)
async def motifs(
    limit: int = Query(default=50, ge=1, le=500),
    type: list[EntityType] | None = Query(default=None),
    relationship_type: list[RelationshipType] | None = Query(default=None),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    ego_entity_id: uuid.UUID | None = Query(default=None),
    depth: int = Query(default=2, ge=1, le=4),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Subgraph motif mining (#52): triangle census, maximal-clique size
    distribution, and the strongest cliques (size ≥ 3) by membership + weight."""
    filters = _filters(type, relationship_type, min_confidence, ego_entity_id, depth)
    result, graph = await analytics_service.motifs(db, filters, limit=limit)
    return MotifsResponse(
        graph_order=graph.order, truncated=graph.truncated,
        triangle_count=result.triangle_count,
        clique_size_distribution=result.clique_size_distribution,
        motifs=[
            MotifRead(kind=m.kind, nodes=[_node(n) for n in m.nodes], weight=m.weight)
            for m in result.motifs
        ],
    )


@router.get("/hierarchy", response_model=HierarchyResponse)
async def hierarchy(
    type: list[EntityType] | None = Query(default=None),
    relationship_type: list[RelationshipType] | None = Query(default=None),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    ego_entity_id: uuid.UUID | None = Query(default=None),
    depth: int = Query(default=2, ge=1, le=4),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Infer chain of command from MANAGES/SUPERVISES edges (#15): layered
    hierarchy, who-reports-to-whom, depth, and cycle detection."""
    filters = _filters(type, relationship_type, min_confidence, ego_entity_id, depth)
    result, graph = await analytics_service.hierarchy(db, filters)
    return HierarchyResponse(
        graph_order=graph.order, truncated=graph.truncated,
        is_acyclic=result.is_acyclic, max_depth=result.max_depth, roots=result.roots,
        nodes=[
            HierarchyNodeRead(
                id=n.id, name=n.name, type=n.type, level=n.level,
                reports_to=n.reports_to, subordinate_count=n.subordinate_count,
            )
            for n in result.nodes
        ],
    )


@router.get("/cells", response_model=CellsResponse)
async def cells(
    min_size: int = Query(default=3, ge=2, le=1000),
    type: list[EntityType] | None = Query(default=None),
    relationship_type: list[RelationshipType] | None = Query(default=None),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    ego_entity_id: uuid.UUID | None = Query(default=None),
    depth: int = Query(default=2, ge=1, le=4),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Classify each detected community's internal topology (#15):
    hub_and_spoke / clique / chain / distributed."""
    filters = _filters(type, relationship_type, min_confidence, ego_entity_id, depth)
    result, graph = await analytics_service.cells(db, filters, min_size=min_size)
    return CellsResponse(
        graph_order=graph.order, truncated=graph.truncated,
        cells=[
            CellRead(
                id=c.id, size=c.size, topology=c.topology, density=c.density,
                centralization=c.centralization, clustering=c.clustering,
                hub=_node(c.hub) if c.hub else None,
                members=[_node(m) for m in c.members],
            )
            for c in result.cells
        ],
    )
