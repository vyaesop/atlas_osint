"""Aggregate a per-entity dashboard from the graph.

Reuses the existing stores: relationships for connections/sections, evidence for
document references, and the analytics engine for influence metrics. The section
set is the same for every entity; the frontend renders the ones relevant to the
entity's type (Person / Organization / Event).
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.graph_loader import GraphFilters
from app.analytics.models import CentralityMetric
from app.analytics.service import analytics_service
from app.models.entity import Entity
from app.models.enums import EntityType, RelationshipType
from app.models.evidence import Evidence
from app.models.relationship import Relationship
from app.schemas.dashboard import (
    DashboardResponse,
    DashboardSections,
    DashboardStats,
    DocumentRef,
    InfluenceMetrics,
    NeighborRef,
)

_ORG_TYPES = {EntityType.ORGANIZATION, EntityType.COMPANY, EntityType.GOVERNMENT_AGENCY}
_AFFILIATION = {
    RelationshipType.WORKS_FOR,
    RelationshipType.MEMBER_OF,
    RelationshipType.FOUNDED,
    RelationshipType.MANAGES,
}
_ENTITY_LIKE = _ORG_TYPES | {EntityType.PERSON, EntityType.ASSET}

_KIND_BY_TYPE = {
    EntityType.PERSON: "person",
    EntityType.ORGANIZATION: "organization",
    EntityType.COMPANY: "company",
    EntityType.GOVERNMENT_AGENCY: "organization",
    EntityType.EVENT: "event",
}


async def build_dashboard(db: AsyncSession, entity_id: uuid.UUID) -> DashboardResponse | None:
    entity = await db.get(Entity, entity_id)
    if entity is None:
        return None

    rels = list((await db.execute(
        select(Relationship).where(
            or_(Relationship.source_id == entity_id, Relationship.target_id == entity_id)
        )
    )).scalars().all())

    neighbor_ids = {
        nid for r in rels for nid in (r.source_id, r.target_id) if nid != entity_id
    }
    neighbors: dict[uuid.UUID, Entity] = {}
    if neighbor_ids:
        neighbors = {
            e.id: e
            for e in (await db.execute(
                select(Entity).where(Entity.id.in_(neighbor_ids))
            )).scalars().all()
        }

    sections = DashboardSections()
    by_type: dict[str, int] = {}

    for rel in rels:
        outgoing = rel.source_id == entity_id
        other_id = rel.target_id if outgoing else rel.source_id
        other = neighbors.get(other_id)
        if other is None:
            continue
        ref = NeighborRef(
            id=other.id, name=other.name, type=other.type,
            relationship_id=rel.id, relationship_type=rel.type,
            direction="outgoing" if outgoing else "incoming",
            confidence=rel.confidence_score, is_ai_generated=rel.is_ai_generated,
        )
        by_type[rel.type.value] = by_type.get(rel.type.value, 0) + 1
        sections.connections.append(ref)

        if other.type is EntityType.EVENT:
            sections.events.append(ref)
        if other.type is EntityType.LOCATION:
            sections.locations.append(ref)
        if other.type is EntityType.DOCUMENT:
            sections.documents.append(DocumentRef(id=other.id, title=other.name))
        if rel.type is RelationshipType.PARTNER_OF:
            sections.partners.append(ref)
        if outgoing and other.type in _ORG_TYPES and rel.type in _AFFILIATION:
            sections.organizations.append(ref)
        if (not outgoing and other.type is EntityType.PERSON
                and rel.type in {RelationshipType.WORKS_FOR, RelationshipType.MEMBER_OF}):
            sections.members.append(ref)
        if other.type in _ENTITY_LIKE:
            sections.related_entities.append(ref)

    # Documents also surface from evidence sources attached to this entity.
    evidence_rows = list((await db.execute(
        select(Evidence).where(Evidence.entity_id == entity_id)
    )).scalars().all())
    seen_sources = {d.title for d in sections.documents}
    for ev in evidence_rows:
        if ev.source and ev.source not in seen_sources:
            seen_sources.add(ev.source)
            sections.documents.append(DocumentRef(id=None, title=ev.source, source=ev.source))

    influence = await _influence(db, entity_id, by_type, total_connections=len(rels))

    stats = DashboardStats(
        total_connections=len(rels),
        total_evidence=len(evidence_rows),
        total_documents=len(sections.documents),
        confidence_score=entity.confidence_score,
    )

    return DashboardResponse(
        entity=entity,
        kind=_KIND_BY_TYPE.get(entity.type, "generic"),
        stats=stats,
        influence=influence,
        sections=sections,
    )


async def _influence(
    db: AsyncSession,
    entity_id: uuid.UUID,
    by_type: dict[str, int],
    *,
    total_connections: int,
) -> InfluenceMetrics:
    """Centrality of the node within its 2-hop neighborhood."""
    filters = GraphFilters(ego_entity_id=entity_id, depth=2)
    key = str(entity_id)
    degree = pagerank = 0.0
    try:
        deg, _ = await analytics_service.centrality(
            db, CentralityMetric.DEGREE, filters, limit=100_000
        )
        degree = next((n.score for n in deg if n.id == key), 0.0)
        pr, _ = await analytics_service.centrality(
            db, CentralityMetric.PAGERANK, filters, limit=100_000
        )
        pagerank = next((n.score for n in pr if n.id == key), 0.0)
    except Exception:  # pragma: no cover - never let analytics break the dashboard
        pass
    return InfluenceMetrics(
        total_connections=total_connections,
        degree_centrality=round(degree, 4),
        pagerank=round(pagerank, 4),
        connections_by_type=by_type,
    )
