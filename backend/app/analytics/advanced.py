"""Advanced graph analytics: brokerage & link prediction, role inference,
structural anomaly detection, network resilience (key-node removal), influence
propagation, and motif census.

All functions are **pure**: they take a :class:`LoadedGraph` and return the
dataclasses from :mod:`app.analytics.models`. No DB access, no external
services, and — like :mod:`app.analytics.networkx_backend` — no scipy/numpy, so
local deployment stays dependency-light.

Backed features (see INTEL_FEATURES.md):
  * #14 hidden-broker + missing-intermediary detection  → :func:`brokerage`
  * #12 link prediction (Adamic-Adar)                   → :func:`brokerage`
  * #16 role inference                                  → :func:`infer_roles`
  * #48 structural anomaly detection                    → :func:`detect_anomalies`
  * #50 what-if node removal / fragmentation            → :func:`resilience`
  * #51 influence / diffusion propagation               → :func:`influence_propagation`
  * #52 subgraph motif mining                           → :func:`motif_census`
"""
from __future__ import annotations

import math
import random
import statistics
from collections import Counter

import networkx as nx

from app.analytics.graph_loader import LoadedGraph
from app.analytics.models import (
    Anomaly,
    AnomalyResult,
    BrokerageResult,
    BrokerNode,
    InfluenceNode,
    InfluenceResult,
    Motif,
    MotifResult,
    NodeImpact,
    PathEdge,
    RankedNode,
    ResilienceResult,
    RoleAssignment,
    RoleResult,
    SuggestedLink,
)
from app.analytics.networkx_backend import _pagerank


def _node(g: nx.Graph, nid: str, score: float = 0.0) -> RankedNode:
    a = g.nodes.get(nid, {})
    return RankedNode(id=nid, name=a.get("name", nid), type=a.get("type", "unknown"), score=score)


def _quantile(values: list[float], q: float) -> float:
    """Linear-interpolation quantile (q in [0, 1]); 0.0 for an empty list."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


# --------------------------------------------------------------------------- #
# #14 / #12 — Brokerage, structural holes, bridges, link prediction
# --------------------------------------------------------------------------- #

def _suggest_links(ug: nx.Graph, *, limit: int) -> list[SuggestedLink]:
    """Adamic-Adar link prediction over non-adjacent pairs sharing a neighbor.

    These surface as *missing intermediaries*: two entities the topology says
    "should" be connected but aren't recorded as such. Restricted to two-hop
    candidates so it stays near-linear in practice rather than O(V²).
    """
    candidates: list[tuple[float, int, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for u in ug.nodes():
        nbrs_u = set(ug[u])
        two_hop: set[str] = set()
        for w in nbrs_u:
            two_hop |= set(ug[w])
        two_hop.discard(u)
        for v in two_hop:
            if v in nbrs_u:
                continue  # already connected
            key = (u, v) if u < v else (v, u)
            if key in seen:
                continue
            seen.add(key)
            common = nbrs_u & set(ug[v])
            if not common:
                continue
            aa = sum(1.0 / math.log(ug.degree(w)) for w in common if ug.degree(w) > 1)
            candidates.append((aa, len(common), key[0], key[1]))

    candidates.sort(reverse=True)
    return [
        SuggestedLink(
            source=a, source_name=ug.nodes.get(a, {}).get("name", a),
            target=b, target_name=ug.nodes.get(b, {}).get("name", b),
            score=round(aa, 4), method="adamic_adar", common_neighbors=cn,
        )
        for aa, cn, a, b in candidates[:limit]
    ]


def brokerage(graph: LoadedGraph, *, limit: int = 25) -> BrokerageResult:
    ug = graph.undirected
    if ug.number_of_nodes() == 0:
        return BrokerageResult()

    betweenness = nx.betweenness_centrality(ug, normalized=True)
    try:
        constraint = nx.constraint(ug, weight="confidence")
    except Exception:  # pragma: no cover - defensive against NaN/degenerate graphs
        constraint = {}
    try:
        effective = nx.effective_size(ug, weight="confidence")
    except Exception:  # pragma: no cover
        effective = {}
    articulation = set(nx.articulation_points(ug)) if ug.number_of_nodes() > 2 else set()

    brokers: list[BrokerNode] = []
    for nid, b in sorted(betweenness.items(), key=lambda kv: kv[1], reverse=True)[:limit]:
        c = constraint.get(nid, float("nan"))
        e = effective.get(nid, 0.0)
        a = ug.nodes.get(nid, {})
        brokers.append(
            BrokerNode(
                id=nid, name=a.get("name", nid), type=a.get("type", "unknown"),
                betweenness=round(b, 6),
                constraint=round(c, 6) if c == c else 0.0,  # NaN guard
                effective_size=round(e, 4) if e == e else 0.0,
                is_articulation=nid in articulation,
            )
        )

    bridges: list[PathEdge] = []
    for u, v in nx.bridges(ug):
        data = ug[u][v]
        bridges.append(
            PathEdge(
                rel_id=data.get("rel_id"), source=u, target=v,
                type=data.get("type"), confidence=round(data.get("confidence", 0.0), 6),
            )
        )

    return BrokerageResult(
        brokers=brokers,
        bridges=bridges[:limit],
        suggested_links=_suggest_links(ug, limit=limit),
    )


# --------------------------------------------------------------------------- #
# #16 — Role inference from graph position
# --------------------------------------------------------------------------- #

def _classify_role(
    *, degree_raw: int, degree: float, betweenness: float, clustering: float,
    deg_hi: float, btw_hi: float, neighbor_is_hub: bool,
) -> tuple[str, str]:
    if degree_raw == 0:
        return "isolate", "no recorded connections"
    if degree >= deg_hi and betweenness >= btw_hi:
        return "leadership", "high connectivity and sits on many shortest paths"
    if betweenness >= btw_hi and degree < deg_hi:
        return "broker", "bridges otherwise separated groups (high betweenness, modest degree)"
    if degree >= deg_hi:
        return "hub", "unusually many direct connections"
    if degree_raw <= 2 and neighbor_is_hub:
        return "peripheral", "few connections, attached to a central figure"
    if clustering >= 0.6:
        return "core_member", "embedded in a tightly-knit cluster"
    return "associate", "ordinary connectivity"


def infer_roles(graph: LoadedGraph, *, limit: int | None = None) -> RoleResult:
    ug = graph.undirected
    if ug.number_of_nodes() == 0:
        return RoleResult()

    degree = nx.degree_centrality(ug)
    betweenness = nx.betweenness_centrality(ug, normalized=True)
    pagerank = _pagerank(graph.directed)
    clustering = nx.clustering(ug)

    deg_hi = _quantile(list(degree.values()), 0.8)
    btw_hi = max(_quantile(list(betweenness.values()), 0.8), 1e-9)

    roles: list[RoleAssignment] = []
    counts: Counter[str] = Counter()
    for nid in ug.nodes():
        d, b, c = degree[nid], betweenness[nid], clustering.get(nid, 0.0)
        neighbor_is_hub = any(degree.get(w, 0.0) >= deg_hi for w in ug[nid])
        role, rationale = _classify_role(
            degree_raw=ug.degree(nid), degree=d, betweenness=b, clustering=c,
            deg_hi=deg_hi, btw_hi=btw_hi, neighbor_is_hub=neighbor_is_hub,
        )
        counts[role] += 1
        a = ug.nodes.get(nid, {})
        roles.append(
            RoleAssignment(
                id=nid, name=a.get("name", nid), type=a.get("type", "unknown"),
                role=role, rationale=rationale,
                degree=round(d, 6), betweenness=round(b, 6),
                pagerank=round(pagerank.get(nid, 0.0), 6), clustering=round(c, 4),
            )
        )

    roles.sort(key=lambda r: (r.betweenness + r.degree), reverse=True)
    if limit is not None:
        roles = roles[:limit]
    return RoleResult(roles=roles, counts=dict(counts))


# --------------------------------------------------------------------------- #
# #48 — Structural anomaly detection
# --------------------------------------------------------------------------- #

def detect_anomalies(
    graph: LoadedGraph, *, z_threshold: float = 2.0, limit: int = 50
) -> AnomalyResult:
    ug = graph.undirected
    degrees = dict(ug.degree())
    if not degrees:
        return AnomalyResult()

    values = list(degrees.values())
    mean = statistics.fmean(values)
    stdev = statistics.pstdev(values) if len(values) > 1 else 0.0
    betweenness = nx.betweenness_centrality(ug, normalized=True)
    btw_p95 = _quantile(list(betweenness.values()), 0.95)

    best: dict[str, Anomaly] = {}  # one (strongest) anomaly per node

    def _offer(nid: str, kind: str, score: float, reason: str) -> None:
        a = ug.nodes.get(nid, {})
        cand = Anomaly(id=nid, name=a.get("name", nid), type=a.get("type", "unknown"),
                       kind=kind, score=round(score, 4), reason=reason)
        if nid not in best or cand.score > best[nid].score:
            best[nid] = cand

    for nid, d in degrees.items():
        if stdev > 0:
            z = (d - mean) / stdev
            if z >= z_threshold:
                _offer(nid, "hub", z, f"degree {d} is {z:.1f}σ above the mean ({mean:.1f})")
        if d == 0 and ug.number_of_nodes() > 2:
            _offer(nid, "isolate", 1.0, "no connections in an otherwise connected graph")

    if btw_p95 > 0:
        for nid, b in betweenness.items():
            if b >= btw_p95 and degrees[nid] <= max(2, mean):
                _offer(nid, "bridge", b, "high betweenness despite low degree — a structural choke point")

    anomalies = sorted(best.values(), key=lambda x: x.score, reverse=True)[:limit]
    return AnomalyResult(anomalies=anomalies, degree_mean=round(mean, 3), degree_stdev=round(stdev, 3))


# --------------------------------------------------------------------------- #
# #50 — Network resilience / key-node removal (what-if)
# --------------------------------------------------------------------------- #

def resilience(graph: LoadedGraph, *, limit: int = 25) -> ResilienceResult:
    ug = graph.undirected
    n = ug.number_of_nodes()
    if n == 0:
        return ResilienceResult(0, 0, 0, [])

    components = list(nx.connected_components(ug))
    base_components = len(components)
    base_largest = max((len(c) for c in components), default=0)

    degree = dict(ug.degree())
    candidates = [nid for nid, _ in sorted(degree.items(), key=lambda kv: kv[1], reverse=True)[:limit]]

    impacts: list[NodeImpact] = []
    for nid in candidates:
        h = ug.copy()
        h.remove_node(nid)
        remaining = h.number_of_nodes()
        if remaining == 0:
            comps_after, largest_after = 0, 0
        else:
            comps = list(nx.connected_components(h))
            comps_after = len(comps)
            largest_after = max((len(c) for c in comps), default=0)
        frag = 1.0 - (largest_after / remaining) if remaining else 1.0
        reach_drop = (base_largest - largest_after) / base_largest if base_largest else 0.0
        a = ug.nodes.get(nid, {})
        impacts.append(
            NodeImpact(
                id=nid, name=a.get("name", nid), type=a.get("type", "unknown"),
                components_after=comps_after, largest_component_after=largest_after,
                fragmentation=round(frag, 4), reachability_drop=round(reach_drop, 4),
            )
        )

    impacts.sort(key=lambda i: (i.reachability_drop, i.components_after), reverse=True)
    return ResilienceResult(base_components, base_largest, n, impacts)


# --------------------------------------------------------------------------- #
# #51 — Influence / diffusion propagation (Independent Cascade)
# --------------------------------------------------------------------------- #

def influence_propagation(
    graph: LoadedGraph, seeds: list[str], *, trials: int = 100, rng_seed: int = 42
) -> InfluenceResult:
    """Monte-Carlo Independent Cascade over the confidence-weighted graph.

    Each newly-activated node gets one chance to activate each neighbour with
    probability equal to the edge confidence. Returns each node's empirical
    activation probability and the expected total spread.
    """
    ug = graph.undirected
    valid_seeds = [s for s in seeds if s in ug]
    if not valid_seeds:
        return InfluenceResult(seeds=valid_seeds, trials=trials, expected_spread=0.0)

    rng = random.Random(rng_seed)
    activation_counts: Counter[str] = Counter()
    total_spread = 0
    for _ in range(max(1, trials)):
        active = set(valid_seeds)
        frontier = list(valid_seeds)
        while frontier:
            newly: list[str] = []
            for u in frontier:
                for v in ug[u]:
                    if v in active:
                        continue
                    if rng.random() < ug[u][v].get("confidence", 0.0):
                        active.add(v)
                        newly.append(v)
            frontier = newly
        total_spread += len(active)
        activation_counts.update(active)

    activated = [
        InfluenceNode(
            id=nid, name=ug.nodes.get(nid, {}).get("name", nid),
            type=ug.nodes.get(nid, {}).get("type", "unknown"),
            activation_probability=round(count / trials, 4),
        )
        for nid, count in activation_counts.most_common()
    ]
    return InfluenceResult(
        seeds=valid_seeds, trials=trials,
        expected_spread=round(total_spread / trials, 4), activated=activated,
    )


# --------------------------------------------------------------------------- #
# #52 — Motif mining (triangle census + maximal cliques)
# --------------------------------------------------------------------------- #

def _avg_clique_weight(ug: nx.Graph, members: list[str]) -> float:
    weights: list[float] = []
    for i, u in enumerate(members):
        for v in members[i + 1:]:
            if ug.has_edge(u, v):
                weights.append(ug[u][v].get("confidence", 0.0))
    return statistics.fmean(weights) if weights else 0.0


def motif_census(graph: LoadedGraph, *, limit: int = 50) -> MotifResult:
    ug = graph.undirected
    if ug.number_of_nodes() == 0:
        return MotifResult(triangle_count=0)

    triangle_count = sum(nx.triangles(ug).values()) // 3

    size_distribution: Counter[int] = Counter()
    cliques3plus: list[list[str]] = []
    for clique in nx.find_cliques(ug):
        size_distribution[len(clique)] += 1
        if len(clique) >= 3:
            cliques3plus.append(clique)

    cliques3plus.sort(key=len, reverse=True)
    motifs: list[Motif] = []
    for members in cliques3plus[:limit]:
        weight = _avg_clique_weight(ug, members)
        kind = "triangle" if len(members) == 3 else f"clique-{len(members)}"
        motifs.append(
            Motif(
                kind=kind,
                nodes=[_node(ug, m, score=ug.degree(m)) for m in members],
                weight=round(weight, 4),
            )
        )

    return MotifResult(
        triangle_count=triangle_count,
        clique_size_distribution=dict(sorted(size_distribution.items())),
        motifs=motifs,
    )
