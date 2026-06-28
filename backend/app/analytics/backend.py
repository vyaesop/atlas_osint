"""Analytics backend protocol implemented by NetworkX (now) and Neo4j GDS (future)."""
from __future__ import annotations

from typing import Protocol

from app.analytics.graph_loader import LoadedGraph
from app.analytics.models import (
    CentralityMetric,
    CommunityResult,
    PathKind,
    PathResult,
    RankedNode,
)


class AnalyticsBackend(Protocol):
    def centrality(
        self, graph: LoadedGraph, metric: CentralityMetric, *, limit: int
    ) -> list[RankedNode]: ...

    def communities(self, graph: LoadedGraph, *, min_size: int) -> CommunityResult: ...

    def paths(
        self,
        graph: LoadedGraph,
        source: str,
        target: str,
        kind: PathKind,
        *,
        k: int = 1,
        max_length: int | None = None,
    ) -> PathResult: ...
