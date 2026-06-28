"""Unit tests for the NetworkX analytics backend (no DB)."""
from __future__ import annotations

import networkx as nx
import pytest

from app.analytics.graph_loader import LoadedGraph
from app.analytics.models import CentralityMetric, PathKind
from app.analytics.networkx_backend import NetworkXBackend

backend = NetworkXBackend()


def _graph(edges: list[tuple[str, str, float]], nodes: list[str] | None = None) -> LoadedGraph:
    directed = nx.DiGraph()
    undirected = nx.Graph()
    for n in nodes or []:
        for g in (directed, undirected):
            g.add_node(n, name=n, type="person", confidence=0.5)
    for s, t, c in edges:
        for nid in (s, t):
            if nid not in directed:
                directed.add_node(nid, name=nid, type="person", confidence=0.5)
                undirected.add_node(nid, name=nid, type="person", confidence=0.5)
        directed.add_edge(s, t, rel_id=f"{s}-{t}", type="CONNECTED_TO", confidence=c)
        undirected.add_edge(s, t, rel_id=f"{s}-{t}", type="CONNECTED_TO", confidence=c)
    return LoadedGraph(directed=directed, undirected=undirected, truncated=False)


def _star() -> LoadedGraph:
    # hub connected to a, b, c, d
    return _graph([("hub", n, 1.0) for n in ("a", "b", "c", "d")])


@pytest.mark.parametrize(
    "metric",
    [CentralityMetric.DEGREE, CentralityMetric.BETWEENNESS, CentralityMetric.EIGENVECTOR],
)
def test_hub_is_top_central(metric):
    # These run on the undirected view, so the hub dominates a star.
    result = backend.centrality(_star(), metric, limit=10)
    assert result[0].id == "hub"


def test_pagerank_rewards_being_pointed_to():
    # PageRank is directional: edges leaf -> hub make the hub authoritative.
    g = _graph([(n, "hub", 1.0) for n in ("a", "b", "c", "d")])
    result = backend.centrality(g, CentralityMetric.PAGERANK, limit=10)
    assert result[0].id == "hub"


def test_communities_finds_two_factions():
    # Two triangles linked by a single bridge edge.
    edges = [
        ("a", "b", 1.0), ("b", "c", 1.0), ("a", "c", 1.0),
        ("x", "y", 1.0), ("y", "z", 1.0), ("x", "z", 1.0),
        ("c", "x", 0.2),  # weak bridge
    ]
    result = backend.communities(_graph(edges), min_size=2)
    assert result.community_count == 2
    assert result.modularity > 0


def test_shortest_path_hops():
    g = _graph([("a", "b", 0.9), ("b", "c", 0.9), ("a", "c", 0.1)])
    res = backend.paths(g, "a", "c", PathKind.SHORTEST)
    assert res.found
    assert res.paths[0].length == 1  # direct a->c edge


def test_shortest_alternatives():
    g = _graph([("a", "b", 0.9), ("b", "c", 0.9), ("a", "c", 0.1)])
    res = backend.paths(g, "a", "c", PathKind.SHORTEST, k=3)
    assert len(res.paths) == 2  # direct, and via b


def test_strongest_avoids_weak_link():
    # Direct edge is weak (0.1); detour via b is strong (0.9 each).
    g = _graph([("a", "c", 0.1), ("a", "b", 0.9), ("b", "c", 0.9)])
    res = backend.paths(g, "a", "c", PathKind.STRONGEST)
    assert res.found
    path = res.paths[0]
    assert [n.id for n in path.nodes] == ["a", "b", "c"]
    assert path.bottleneck_confidence == pytest.approx(0.9)


def test_most_likely_maximizes_product():
    # Direct 0.5 vs. via b: 0.9 * 0.9 = 0.81 > 0.5
    g = _graph([("a", "c", 0.5), ("a", "b", 0.9), ("b", "c", 0.9)])
    res = backend.paths(g, "a", "c", PathKind.MOST_LIKELY)
    assert [n.id for n in res.paths[0].nodes] == ["a", "b", "c"]
    assert res.paths[0].score == pytest.approx(0.81)


def test_no_path_when_disconnected():
    g = _graph([("a", "b", 1.0)], nodes=["z"])
    res = backend.paths(g, "a", "z", PathKind.SHORTEST)
    assert res.found is False
