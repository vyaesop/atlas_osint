"""Placeholder for a future Neo4j Graph Data Science backend.

When the graph outgrows in-process computation (Phase 6 scaling), implement
:class:`~app.analytics.backend.AnalyticsBackend` here by projecting a GDS graph
and calling ``gds.pageRank``, ``gds.betweenness``, ``gds.louvain``,
``gds.shortestPath.*`` etc. The service layer and API contract stay unchanged —
only ``ANALYTICS_BACKEND=neo4j_gds`` flips the implementation.
"""
from __future__ import annotations

from app.analytics.graph_loader import LoadedGraph
from app.analytics.models import (
    CentralityMetric,
    CommunityResult,
    PathKind,
    PathResult,
    RankedNode,
)

_NOT_IMPLEMENTED = (
    "The Neo4j GDS analytics backend is planned for Phase 6. "
    "Set ANALYTICS_BACKEND=networkx for local analytics."
)


class Neo4jGDSBackend:  # pragma: no cover - intentional stub
    def centrality(self, graph: LoadedGraph, metric: CentralityMetric, *, limit: int) -> list[RankedNode]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def communities(self, graph: LoadedGraph, *, min_size: int) -> CommunityResult:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def paths(self, graph, source, target, kind: PathKind, *, k=1, max_length=None) -> PathResult:
        raise NotImplementedError(_NOT_IMPLEMENTED)
