"""NetworkX analytics backend.

Centrality, community detection, and path discovery computed in-process.
PageRank and eigenvector centrality use pure-Python power iteration so the only
dependency is NetworkX itself (no scipy/numpy) — keeping local deployment light.
"""
from __future__ import annotations

import heapq
import math

import networkx as nx

from app.analytics.graph_loader import LoadedGraph
from app.analytics.models import (
    CentralityMetric,
    Community,
    CommunityResult,
    GraphPath,
    PathEdge,
    PathKind,
    PathResult,
    RankedNode,
)

_EPS = 1e-9


def _ranked(graph: LoadedGraph, scores: dict[str, float], limit: int) -> list[RankedNode]:
    attrs = graph.undirected.nodes
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [
        RankedNode(
            id=nid,
            name=attrs.get(nid, {}).get("name", nid),
            type=attrs.get(nid, {}).get("type", "unknown"),
            score=round(score, 6),
        )
        for nid, score in ranked
    ]


# --------------------------------------------------------------------------- #
# Pure-Python centrality (no scipy/numpy)
# --------------------------------------------------------------------------- #

def _pagerank(g: nx.DiGraph, alpha: float = 0.85, max_iter: int = 200, tol: float = 1e-9) -> dict[str, float]:
    n = g.number_of_nodes()
    if n == 0:
        return {}
    nodes = list(g.nodes())
    rank = {v: 1.0 / n for v in nodes}

    # Weighted out-strength per node.
    out_strength: dict[str, float] = {}
    for u in nodes:
        s = sum(max(g[u][v].get("confidence", 1.0), _EPS) for v in g.successors(u))
        out_strength[u] = s

    for _ in range(max_iter):
        dangling = alpha * sum(rank[u] for u in nodes if out_strength[u] == 0.0) / n
        nxt = {v: (1.0 - alpha) / n + dangling for v in nodes}
        for u in nodes:
            if out_strength[u] == 0.0:
                continue
            share = alpha * rank[u] / out_strength[u]
            for v in g.successors(u):
                nxt[v] += share * max(g[u][v].get("confidence", 1.0), _EPS)
        err = sum(abs(nxt[v] - rank[v]) for v in nodes)
        rank = nxt
        if err < tol:
            break
    return rank


def _eigenvector(g: nx.Graph, max_iter: int = 500, tol: float = 1e-6) -> dict[str, float]:
    if g.number_of_nodes() == 0:
        return {}
    x = {v: 1.0 for v in g.nodes()}
    for _ in range(max_iter):
        prev = x
        x = {v: 0.0 for v in g.nodes()}
        for u in g.nodes():
            for v in g[u]:
                x[u] += prev[v] * max(g[u][v].get("confidence", 1.0), _EPS)
        norm = math.sqrt(sum(val * val for val in x.values())) or 1.0
        x = {v: val / norm for v, val in x.items()}
        if sum(abs(x[v] - prev[v]) for v in g.nodes()) < tol:
            break
    return x


# --------------------------------------------------------------------------- #
# Backend
# --------------------------------------------------------------------------- #

class NetworkXBackend:
    def centrality(
        self, graph: LoadedGraph, metric: CentralityMetric, *, limit: int
    ) -> list[RankedNode]:
        ug = graph.undirected
        if metric is CentralityMetric.DEGREE:
            scores = nx.degree_centrality(ug)
        elif metric is CentralityMetric.BETWEENNESS:
            scores = nx.betweenness_centrality(ug, normalized=True)
        elif metric is CentralityMetric.EIGENVECTOR:
            scores = _eigenvector(ug)
        elif metric is CentralityMetric.PAGERANK:
            scores = _pagerank(graph.directed)
        else:  # pragma: no cover - exhaustive
            raise ValueError(f"Unknown metric {metric}")
        return _ranked(graph, scores, limit)

    def communities(self, graph: LoadedGraph, *, min_size: int = 1) -> CommunityResult:
        ug = graph.undirected
        if ug.number_of_nodes() == 0:
            return CommunityResult("louvain", 0.0, 0, [])

        groups = nx.community.louvain_communities(ug, weight="confidence", seed=42)
        modularity = (
            nx.community.modularity(ug, groups, weight="confidence")
            if ug.number_of_edges() > 0
            else 0.0
        )

        communities: list[Community] = []
        attrs = ug.nodes
        for idx, members in enumerate(sorted(groups, key=len, reverse=True)):
            if len(members) < min_size:
                continue
            ranked = [
                RankedNode(
                    id=m,
                    name=attrs.get(m, {}).get("name", m),
                    type=attrs.get(m, {}).get("type", "unknown"),
                    score=ug.degree(m),
                )
                for m in sorted(members, key=lambda m: ug.degree(m), reverse=True)
            ]
            communities.append(Community(id=idx, size=len(members), members=ranked))

        return CommunityResult(
            algorithm="louvain",
            modularity=round(modularity, 6),
            community_count=len(communities),
            communities=communities,
        )

    def paths(
        self,
        graph: LoadedGraph,
        source: str,
        target: str,
        kind: PathKind,
        *,
        k: int = 1,
        max_length: int | None = None,
    ) -> PathResult:
        g = graph.undirected
        if source not in g or target not in g:
            return PathResult(found=False)
        if source == target:
            node = self._node(g, source)
            return PathResult(found=True, paths=[GraphPath(kind.value, [node], [], 0, 0.0, 1.0)])

        if kind is PathKind.SHORTEST:
            sequences = self._k_shortest(g, source, target, k, max_length)
        elif kind is PathKind.STRONGEST:
            seq = self._widest(g, source, target)
            sequences = [seq] if seq else []
        elif kind is PathKind.MOST_LIKELY:
            seq = self._most_likely(g, source, target)
            sequences = [seq] if seq else []
        else:  # pragma: no cover
            raise ValueError(f"Unknown path kind {kind}")

        paths = [self._build_path(g, seq, kind) for seq in sequences if seq]
        return PathResult(found=bool(paths), paths=paths)

    # -- path helpers --

    @staticmethod
    def _node(g: nx.Graph, nid: str) -> RankedNode:
        a = g.nodes.get(nid, {})
        return RankedNode(id=nid, name=a.get("name", nid), type=a.get("type", "unknown"),
                          score=a.get("confidence", 0.0))

    def _k_shortest(self, g, source, target, k, max_length):
        out: list[list[str]] = []
        try:
            for seq in nx.shortest_simple_paths(g, source, target):
                if max_length is not None and len(seq) - 1 > max_length:
                    break
                out.append(seq)
                if len(out) >= max(1, k):
                    break
        except nx.NetworkXNoPath:
            return []
        return out

    @staticmethod
    def _widest(g, s, t):
        """Path maximizing the minimum edge confidence (bottleneck)."""
        width = {n: -1.0 for n in g}
        width[s] = math.inf
        prev: dict[str, str] = {}
        visited: set[str] = set()
        heap: list[tuple[float, str]] = [(-math.inf, s)]
        while heap:
            negw, u = heapq.heappop(heap)
            if u in visited:
                continue
            visited.add(u)
            if u == t:
                break
            w = -negw
            for v in g[u]:
                b = min(w, g[u][v].get("confidence", 0.0))
                if b > width[v]:
                    width[v] = b
                    prev[v] = u
                    heapq.heappush(heap, (-b, v))
        if t != s and t not in prev:
            return None
        seq = [t]
        while seq[-1] != s:
            seq.append(prev[seq[-1]])
        return list(reversed(seq))

    @staticmethod
    def _most_likely(g, s, t):
        """Path maximizing the product of edge confidences (= min sum of -log)."""
        def weight(_u, _v, data):
            return -math.log(max(data.get("confidence", 0.0), _EPS))

        try:
            return nx.dijkstra_path(g, s, t, weight=weight)
        except nx.NetworkXNoPath:
            return None

    def _build_path(self, g: nx.Graph, seq: list[str], kind: PathKind) -> GraphPath:
        nodes = [self._node(g, nid) for nid in seq]
        edges: list[PathEdge] = []
        confidences: list[float] = []
        for u, v in zip(seq, seq[1:]):
            data = g[u][v]
            conf = data.get("confidence", 0.0)
            confidences.append(conf)
            edges.append(PathEdge(rel_id=data.get("rel_id"), source=u, target=v,
                                  type=data.get("type"), confidence=round(conf, 6)))
        bottleneck = min(confidences) if confidences else 1.0
        product = math.prod(confidences) if confidences else 1.0
        if kind is PathKind.STRONGEST:
            score = bottleneck
        elif kind is PathKind.MOST_LIKELY:
            score = product
        else:
            score = float(len(seq) - 1)
        return GraphPath(
            kind=kind.value, nodes=nodes, edges=edges, length=len(seq) - 1,
            score=round(score, 6), bottleneck_confidence=round(bottleneck, 6),
        )
