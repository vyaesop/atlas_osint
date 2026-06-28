"""Unit tests for hierarchy & cell-structure inference (#15), no DB."""
from __future__ import annotations

import networkx as nx

from app.analytics import structure
from app.analytics.graph_loader import LoadedGraph


def _graph(edges) -> LoadedGraph:
    """edges: list of (source, target, type)."""
    directed = nx.DiGraph()
    undirected = nx.Graph()
    for s, t, typ in edges:
        for nid in (s, t):
            if nid not in directed:
                directed.add_node(nid, name=nid, type="person", confidence=0.5)
                undirected.add_node(nid, name=nid, type="person", confidence=0.5)
        directed.add_edge(s, t, rel_id=f"{s}-{t}", type=typ, confidence=1.0)
        undirected.add_edge(s, t, rel_id=f"{s}-{t}", type=typ, confidence=1.0)
    return LoadedGraph(directed=directed, undirected=undirected, truncated=False)


# --- hierarchy --- #

def test_hierarchy_layers_command_chain():
    # boss MANAGES mid; mid MANAGES worker1, worker2
    g = _graph([
        ("boss", "mid", "MANAGES"),
        ("mid", "w1", "SUPERVISES"),
        ("mid", "w2", "SUPERVISES"),
    ])
    res = structure.infer_hierarchy(g)
    assert res.is_acyclic
    assert res.roots == ["boss"]
    assert res.max_depth == 2
    levels = {n.id: n.level for n in res.nodes}
    assert levels["boss"] == 0 and levels["mid"] == 1 and levels["w1"] == 2
    mid = next(n for n in res.nodes if n.id == "mid")
    assert mid.reports_to == ["boss"]
    assert mid.subordinate_count == 2


def test_hierarchy_ignores_non_command_edges():
    g = _graph([("a", "b", "ASSOCIATED_WITH"), ("a", "c", "CONNECTED_TO")])
    res = structure.infer_hierarchy(g)
    assert res.nodes == []  # no command edges → empty hierarchy


def test_hierarchy_detects_cycle():
    g = _graph([("a", "b", "MANAGES"), ("b", "a", "MANAGES")])
    res = structure.infer_hierarchy(g)
    assert res.is_acyclic is False


# --- cells --- #

def test_cell_hub_and_spoke():
    # A star: hub connected to 6 leaves → high centralization.
    g = _graph([("hub", f"n{i}", "CONNECTED_TO") for i in range(6)])
    res = structure.detect_cells(g, min_size=3)
    assert res.cells
    star = res.cells[0]
    assert star.topology == "hub_and_spoke"
    assert star.hub is not None and star.hub.id == "hub"


def test_cell_clique():
    # K5 complete graph → dense mesh.
    nodes = [f"n{i}" for i in range(5)]
    edges = [(u, v, "CONNECTED_TO") for i, u in enumerate(nodes) for v in nodes[i + 1:]]
    res = structure.detect_cells(_graph(edges), min_size=3)
    assert res.cells[0].topology == "clique"


def test_cells_empty_graph():
    empty = LoadedGraph(directed=nx.DiGraph(), undirected=nx.Graph(), truncated=False)
    assert structure.detect_cells(empty).cells == []
