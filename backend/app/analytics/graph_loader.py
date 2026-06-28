"""Load a working graph from PostgreSQL into NetworkX structures.

PostgreSQL stays the source of truth; analytics reads a snapshot on demand.
A :class:`LoadedGraph` carries both a directed view (for PageRank and direction-
aware traversal) and an undirected, confidence-weighted view (for centrality,
community detection, and path discovery). Node attributes (name, type,
confidence) ride along so results are self-describing without extra queries.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import networkx as nx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.entity import Entity
from app.models.enums import EntityType, RelationshipType
from app.models.relationship import Relationship


@dataclass(slots=True)
class GraphFilters:
    types: list[EntityType] | None = None
    relationship_types: list[RelationshipType] | None = None
    min_confidence: float = 0.0
    ego_entity_id: uuid.UUID | None = None
    depth: int = 2
    max_nodes: int | None = None


@dataclass(slots=True)
class LoadedGraph:
    directed: nx.DiGraph
    undirected: nx.Graph
    truncated: bool  # True if the node cap was hit

    @property
    def order(self) -> int:
        return self.directed.number_of_nodes()

    def name_of(self, node_id: str) -> str:
        return self.directed.nodes.get(node_id, {}).get("name", node_id)


async def _load_ego_edges(
    db: AsyncSession, center: uuid.UUID, depth: int, max_nodes: int
) -> list[Relationship]:
    """Breadth-first expansion around ``center`` up to ``depth`` hops."""
    frontier = {center}
    visited: set[uuid.UUID] = set()
    edges: dict[uuid.UUID, Relationship] = {}
    for _ in range(max(1, depth)):
        if not frontier or len(visited) >= max_nodes:
            break
        result = await db.execute(
            select(Relationship).where(
                or_(
                    Relationship.source_id.in_(frontier),
                    Relationship.target_id.in_(frontier),
                )
            )
        )
        visited |= frontier
        next_frontier: set[uuid.UUID] = set()
        for rel in result.scalars().all():
            edges[rel.id] = rel
            for nid in (rel.source_id, rel.target_id):
                if nid not in visited:
                    next_frontier.add(nid)
        frontier = next_frontier
    return list(edges.values())


async def load_graph(db: AsyncSession, filters: GraphFilters) -> LoadedGraph:
    max_nodes = filters.max_nodes or settings.ANALYTICS_MAX_NODES

    # 1) Gather the relevant relationships.
    if filters.ego_entity_id is not None:
        rels = await _load_ego_edges(db, filters.ego_entity_id, filters.depth, max_nodes)
    else:
        rels = list((await db.execute(select(Relationship))).scalars().all())

    if filters.relationship_types:
        wanted = set(filters.relationship_types)
        rels = [r for r in rels if r.type in wanted]

    # 2) Resolve the entities referenced by those edges (plus the ego node, so a
    #    lone node with no edges still appears).
    entity_ids: set[uuid.UUID] = set()
    for r in rels:
        entity_ids.add(r.source_id)
        entity_ids.add(r.target_id)
    if filters.ego_entity_id is not None:
        entity_ids.add(filters.ego_entity_id)

    if not entity_ids and filters.ego_entity_id is None:
        # No ego scope and no edges → fall back to standalone entities.
        ent_stmt = select(Entity)
        if filters.types:
            ent_stmt = ent_stmt.where(Entity.type.in_(filters.types))
        entities = list((await db.execute(ent_stmt.limit(max_nodes))).scalars().all())
    else:
        ent_stmt = select(Entity).where(Entity.id.in_(entity_ids))
        if filters.types:
            ent_stmt = ent_stmt.where(Entity.type.in_(filters.types))
        entities = list((await db.execute(ent_stmt)).scalars().all())

    # 3) Apply node cap deterministically (highest-confidence first).
    truncated = False
    if len(entities) > max_nodes:
        entities.sort(key=lambda e: e.confidence_score, reverse=True)
        entities = entities[:max_nodes]
        truncated = True
    allowed = {e.id for e in entities}

    directed = nx.DiGraph()
    undirected = nx.Graph()
    for e in entities:
        attrs = {"name": e.name, "type": e.type.value, "confidence": e.confidence_score}
        directed.add_node(str(e.id), **attrs)
        undirected.add_node(str(e.id), **attrs)

    for r in rels:
        if r.source_id not in allowed or r.target_id not in allowed:
            continue
        if r.confidence_score < filters.min_confidence:
            continue
        s, t = str(r.source_id), str(r.target_id)
        weight = max(r.confidence_score, 0.0)
        directed.add_edge(s, t, rel_id=str(r.id), type=r.type.value, confidence=weight)
        # Collapse parallel/edges in the undirected view, keeping the strongest.
        if undirected.has_edge(s, t):
            if weight > undirected[s][t]["confidence"]:
                undirected[s][t].update(rel_id=str(r.id), type=r.type.value, confidence=weight)
        else:
            undirected.add_edge(s, t, rel_id=str(r.id), type=r.type.value, confidence=weight)

    return LoadedGraph(directed=directed, undirected=undirected, truncated=truncated)
