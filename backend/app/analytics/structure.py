"""Hierarchy & cell-structure inference (#15).

Two complementary readings of organisation:

* **Hierarchy / chain of command** — from directional command edges
  (``MANAGES``, ``SUPERVISES``), build the superior→subordinate DAG, layer it,
  and report who reports to whom and how deep the chain runs.
* **Cell topology** — detect communities, then classify each one's internal
  shape: *hub-and-spoke* (one dominant figure), *clique* (dense mesh), *chain*,
  or *distributed*. Counter-network analysis cares which it is.

Pure NetworkX, no scipy/numpy — same posture as the rest of the analytics layer.
"""
from __future__ import annotations

import networkx as nx

from app.analytics.graph_loader import LoadedGraph
from app.analytics.models import (
    Cell,
    CellResult,
    HierarchyNode,
    HierarchyResult,
    RankedNode,
)

# Edge types that denote authority (source is superior to target).
_COMMAND_EDGES = {"MANAGES", "SUPERVISES"}


def _ranked(graph: LoadedGraph, nid: str, score: float) -> RankedNode:
    a = graph.undirected.nodes.get(nid, {})
    return RankedNode(id=nid, name=a.get("name", nid), type=a.get("type", "unknown"),
                      score=round(score, 4))


def infer_hierarchy(graph: LoadedGraph, *, command_edges: set[str] = _COMMAND_EDGES) -> HierarchyResult:
    dg = nx.DiGraph()
    for u, v, data in graph.directed.edges(data=True):
        if data.get("type") in command_edges:
            dg.add_edge(u, v)
    if dg.number_of_nodes() == 0:
        return HierarchyResult(is_acyclic=True, max_depth=0, roots=[])

    is_dag = nx.is_directed_acyclic_graph(dg)
    roots = [n for n in dg.nodes if dg.in_degree(n) == 0] or [next(iter(dg.nodes))]

    # Level = longest distance from any root (DAG via topo DP; else BFS layers).
    level: dict[str, int] = {n: 0 for n in dg.nodes}
    if is_dag:
        for n in nx.topological_sort(dg):
            for succ in dg.successors(n):
                level[succ] = max(level[succ], level[n] + 1)
    else:
        from collections import deque
        seen: set[str] = set()
        dq: deque[tuple[str, int]] = deque((r, 0) for r in roots)
        while dq:
            node, lvl = dq.popleft()
            if node in seen:
                continue
            seen.add(node)
            level[node] = lvl
            for succ in dg.successors(node):
                if succ not in seen:
                    dq.append((succ, lvl + 1))

    nodes = [
        HierarchyNode(
            id=n, name=graph.undirected.nodes.get(n, {}).get("name", n),
            type=graph.undirected.nodes.get(n, {}).get("type", "unknown"),
            level=level[n], reports_to=sorted(dg.predecessors(n)),
            subordinate_count=dg.out_degree(n),
        )
        for n in dg.nodes
    ]
    nodes.sort(key=lambda x: (x.level, -x.subordinate_count))
    return HierarchyResult(
        is_acyclic=is_dag,
        max_depth=max(level.values()) if level else 0,
        roots=sorted(roots), nodes=nodes,
    )


def _centralization(sub: nx.Graph) -> tuple[float, str | None]:
    """Freeman degree centralization in [0, 1] and the hub node id (if any)."""
    n = sub.number_of_nodes()
    if n < 3:
        return 0.0, None
    degrees = dict(sub.degree())
    hub = max(degrees, key=degrees.get)
    d_max = degrees[hub]
    numerator = sum(d_max - d for d in degrees.values())
    denominator = (n - 1) * (n - 2)
    return (round(numerator / denominator, 4) if denominator else 0.0), hub


def detect_cells(graph: LoadedGraph, *, min_size: int = 3) -> CellResult:
    ug = graph.undirected
    if ug.number_of_nodes() == 0:
        return CellResult()

    groups = nx.community.louvain_communities(ug, weight="confidence", seed=42)
    cells: list[Cell] = []
    for idx, members in enumerate(sorted(groups, key=len, reverse=True)):
        if len(members) < min_size:
            continue
        sub = ug.subgraph(members)
        density = round(nx.density(sub), 4)
        clustering = round(nx.average_clustering(sub), 4)
        centralization, hub = _centralization(sub)

        if centralization >= 0.6:
            topology = "hub_and_spoke"
        elif density >= 0.7:
            topology = "clique"
        elif max((d for _, d in sub.degree()), default=0) <= 2 and clustering < 0.1:
            topology = "chain"
        else:
            topology = "distributed"

        ranked = sorted(
            (_ranked(graph, m, sub.degree(m)) for m in members),
            key=lambda r: r.score, reverse=True,
        )
        cells.append(Cell(
            id=idx, size=len(members), topology=topology, density=density,
            centralization=centralization, clustering=clustering,
            hub=_ranked(graph, hub, sub.degree(hub)) if (hub and topology == "hub_and_spoke") else None,
            members=ranked,
        ))
    return CellResult(cells=cells)
