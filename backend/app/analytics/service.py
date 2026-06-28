"""High-level analytics facade used by the API.

Selects the backend, loads a graph snapshot from PostgreSQL per request, and
delegates the (CPU-bound, synchronous) computation to the backend. Graph loading
is async (DB I/O); the algorithms themselves run in-process.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics import advanced, structure
from app.analytics.backend import AnalyticsBackend
from app.analytics.graph_loader import GraphFilters, LoadedGraph, load_graph
from app.analytics.models import (
    AnomalyResult,
    BrokerageResult,
    CellResult,
    CentralityMetric,
    CommunityResult,
    HierarchyResult,
    InfluenceResult,
    MotifResult,
    PathKind,
    PathResult,
    RankedNode,
    ResilienceResult,
    RoleResult,
)
from app.analytics.networkx_backend import NetworkXBackend
from app.core.config import settings


def _build_backend() -> AnalyticsBackend:
    if settings.ANALYTICS_BACKEND == "neo4j_gds":
        from app.analytics.neo4j_gds import Neo4jGDSBackend

        return Neo4jGDSBackend()
    return NetworkXBackend()


class AnalyticsService:
    def __init__(self, backend: AnalyticsBackend | None = None) -> None:
        self._backend = backend or _build_backend()

    async def _graph(self, db: AsyncSession, filters: GraphFilters) -> LoadedGraph:
        return await load_graph(db, filters)

    async def centrality(
        self, db: AsyncSession, metric: CentralityMetric, filters: GraphFilters, *, limit: int
    ) -> tuple[list[RankedNode], LoadedGraph]:
        graph = await self._graph(db, filters)
        return self._backend.centrality(graph, metric, limit=limit), graph

    async def communities(
        self, db: AsyncSession, filters: GraphFilters, *, min_size: int
    ) -> tuple[CommunityResult, LoadedGraph]:
        graph = await self._graph(db, filters)
        return self._backend.communities(graph, min_size=min_size), graph

    async def paths(
        self,
        db: AsyncSession,
        source: str,
        target: str,
        kind: PathKind,
        filters: GraphFilters,
        *,
        k: int = 1,
        max_length: int | None = None,
    ) -> PathResult:
        graph = await self._graph(db, filters)
        return self._backend.paths(graph, source, target, kind, k=k, max_length=max_length)

    # ------------------------------------------------------------------ #
    # Advanced analytics. These run over a loaded snapshot via pure
    # functions in app.analytics.advanced (NetworkX only). Each returns the
    # graph order/truncation alongside the result so callers can report scope.
    # ------------------------------------------------------------------ #

    async def brokerage(
        self, db: AsyncSession, filters: GraphFilters, *, limit: int
    ) -> tuple[BrokerageResult, LoadedGraph]:
        graph = await self._graph(db, filters)
        return advanced.brokerage(graph, limit=limit), graph

    async def roles(
        self, db: AsyncSession, filters: GraphFilters, *, limit: int | None
    ) -> tuple[RoleResult, LoadedGraph]:
        graph = await self._graph(db, filters)
        return advanced.infer_roles(graph, limit=limit), graph

    async def anomalies(
        self, db: AsyncSession, filters: GraphFilters, *, z_threshold: float, limit: int
    ) -> tuple[AnomalyResult, LoadedGraph]:
        graph = await self._graph(db, filters)
        return advanced.detect_anomalies(graph, z_threshold=z_threshold, limit=limit), graph

    async def resilience(
        self, db: AsyncSession, filters: GraphFilters, *, limit: int
    ) -> tuple[ResilienceResult, LoadedGraph]:
        graph = await self._graph(db, filters)
        return advanced.resilience(graph, limit=limit), graph

    async def influence(
        self, db: AsyncSession, seeds: list[str], filters: GraphFilters, *, trials: int
    ) -> tuple[InfluenceResult, LoadedGraph]:
        graph = await self._graph(db, filters)
        return advanced.influence_propagation(graph, seeds, trials=trials), graph

    async def motifs(
        self, db: AsyncSession, filters: GraphFilters, *, limit: int
    ) -> tuple[MotifResult, LoadedGraph]:
        graph = await self._graph(db, filters)
        return advanced.motif_census(graph, limit=limit), graph

    async def hierarchy(
        self, db: AsyncSession, filters: GraphFilters
    ) -> tuple[HierarchyResult, LoadedGraph]:
        graph = await self._graph(db, filters)
        return structure.infer_hierarchy(graph), graph

    async def cells(
        self, db: AsyncSession, filters: GraphFilters, *, min_size: int
    ) -> tuple[CellResult, LoadedGraph]:
        graph = await self._graph(db, filters)
        return structure.detect_cells(graph, min_size=min_size), graph


analytics_service = AnalyticsService()
