"""Unit tests for the advanced analytics engine (no DB).

Covers brokerage/link-prediction (#14/#12), role inference (#16), structural
anomaly detection (#48), resilience/key-node removal (#50), influence
propagation (#51), and motif census (#52).
"""
from __future__ import annotations

import networkx as nx

from app.analytics import advanced
from app.analytics.graph_loader import LoadedGraph


def _graph(edges, nodes=None) -> LoadedGraph:
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


def _two_triangles_bridge() -> LoadedGraph:
    # Triangle {a,b,c} and {x,y,z}, joined only through c—x.
    return _graph([
        ("a", "b", 1.0), ("b", "c", 1.0), ("a", "c", 1.0),
        ("x", "y", 1.0), ("y", "z", 1.0), ("x", "z", 1.0),
        ("c", "x", 0.4),
    ])


# --- #14 brokerage / bridges / link prediction ---------------------------- #

def test_bridge_edge_detected():
    res = advanced.brokerage(_two_triangles_bridge())
    bridge_pairs = {frozenset((e.source, e.target)) for e in res.bridges}
    assert frozenset(("c", "x")) in bridge_pairs


def test_articulation_points_flagged_as_brokers():
    res = advanced.brokerage(_two_triangles_bridge())
    articulations = {b.id for b in res.brokers if b.is_articulation}
    assert {"c", "x"} <= articulations


def test_link_prediction_suggests_closing_a_triangle():
    # a-b, b-c but no a-c: a and c share neighbor b → suggested link.
    res = advanced.brokerage(_graph([("a", "b", 1.0), ("b", "c", 1.0)]))
    pairs = {frozenset((s.source, s.target)) for s in res.suggested_links}
    assert frozenset(("a", "c")) in pairs


# --- #16 role inference --------------------------------------------------- #

def test_isolate_role():
    res = advanced.infer_roles(_graph([("a", "b", 1.0)], nodes=["lonely"]))
    by_id = {r.id: r.role for r in res.roles}
    assert by_id["lonely"] == "isolate"


def test_broker_role_on_bridge_node():
    res = advanced.infer_roles(_two_triangles_bridge())
    by_id = {r.id: r.role for r in res.roles}
    # c and x sit between the two triangles → broker/leadership, never peripheral.
    assert by_id["c"] in {"broker", "leadership", "hub"}
    assert res.counts  # populated


# --- #48 anomaly detection ------------------------------------------------ #

def test_hub_flagged_as_anomaly():
    # One node wired to 10 leaves: a clear degree outlier.
    res = advanced.detect_anomalies(_graph([("hub", f"n{i}", 1.0) for i in range(10)]),
                                    z_threshold=2.0)
    kinds = {a.id: a.kind for a in res.anomalies}
    assert kinds.get("hub") == "hub"


def test_no_anomalies_in_uniform_graph():
    # A ring: every node has degree 2, so no degree outliers.
    ring = [(f"n{i}", f"n{(i + 1) % 6}", 1.0) for i in range(6)]
    res = advanced.detect_anomalies(_graph(ring), z_threshold=2.0)
    assert all(a.kind != "hub" for a in res.anomalies)


# --- #50 resilience / key-node removal ------------------------------------ #

def test_removing_bridge_node_fragments_graph():
    res = advanced.resilience(_two_triangles_bridge())
    top = res.impacts[0]
    assert top.id in {"c", "x"}
    assert top.components_after >= 2  # graph splits in two
    assert res.baseline_components == 1


# --- #51 influence propagation -------------------------------------------- #

def test_full_confidence_chain_spreads_everywhere():
    # All edges certain → cascade reaches the whole component every trial.
    g = _graph([("a", "b", 1.0), ("b", "c", 1.0), ("c", "d", 1.0)])
    res = advanced.influence_propagation(g, ["a"], trials=50)
    assert res.expected_spread == 4.0
    assert all(n.activation_probability == 1.0 for n in res.activated)


def test_zero_confidence_blocks_spread():
    g = _graph([("a", "b", 0.0)])
    res = advanced.influence_propagation(g, ["a"], trials=50)
    assert res.expected_spread == 1.0  # only the seed


def test_influence_ignores_unknown_seed():
    res = advanced.influence_propagation(_graph([("a", "b", 1.0)]), ["ghost"], trials=10)
    assert res.expected_spread == 0.0


# --- #52 motif census ----------------------------------------------------- #

def test_triangle_counted():
    res = advanced.motif_census(_graph([("a", "b", 1.0), ("b", "c", 1.0), ("a", "c", 1.0)]))
    assert res.triangle_count == 1
    assert any(m.kind == "triangle" for m in res.motifs)


def test_four_clique_detected():
    nodes = ["a", "b", "c", "d"]
    edges = [(u, v, 1.0) for i, u in enumerate(nodes) for v in nodes[i + 1:]]
    res = advanced.motif_census(_graph(edges))
    assert res.clique_size_distribution.get(4) == 1
    assert res.motifs[0].kind == "clique-4"


def test_empty_graph_is_safe():
    empty = LoadedGraph(directed=nx.DiGraph(), undirected=nx.Graph(), truncated=False)
    assert advanced.brokerage(empty).brokers == []
    assert advanced.infer_roles(empty).roles == []
    assert advanced.detect_anomalies(empty).anomalies == []
    assert advanced.resilience(empty).node_count == 0
    assert advanced.motif_census(empty).triangle_count == 0
