"""Analytic lineage / provenance graph (#5).

For an entity, traces *why the system believes it exists*: the source documents
and evidence behind it, whether each link was AI-extracted or human-entered, and
its verification state — surfaced as a small provenance graph plus a summary.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity
from app.models.enums import EntityType
from app.models.evidence import Evidence
from app.models.enums import VerificationStatus
from app.models.relationship import Relationship


@dataclass(slots=True)
class LineageNode:
    id: str
    kind: str          # entity | evidence | document | user
    label: str
    ai_generated: bool = False
    verified: bool | None = None


@dataclass(slots=True)
class LineageEdge:
    source: str
    target: str
    relation: str


@dataclass(slots=True)
class Lineage:
    entity_id: str
    summary: str
    nodes: list[LineageNode] = field(default_factory=list)
    edges: list[LineageEdge] = field(default_factory=list)


async def build_lineage(db: AsyncSession, entity: Entity) -> Lineage:
    nodes: list[LineageNode] = [LineageNode(
        id=str(entity.id), kind="entity", label=entity.name,
        ai_generated=entity.is_ai_generated,
    )]
    edges: list[LineageEdge] = []
    seen: set[str] = {str(entity.id)}

    evidence = list((await db.execute(
        select(Evidence).where(Evidence.entity_id == entity.id)
    )).scalars().all())
    verified_count = 0
    sources: set[str] = set()
    for ev in evidence:
        ev_id = str(ev.id)
        is_verified = ev.verification_status is VerificationStatus.VERIFIED
        verified_count += int(is_verified)
        nodes.append(LineageNode(id=ev_id, kind="evidence", label=ev.title,
                                 ai_generated=ev.is_ai_generated, verified=is_verified))
        edges.append(LineageEdge(source=ev_id, target=str(entity.id), relation=ev.stance.value))
        if ev.source:
            src_key = f"doc:{ev.source}"
            if src_key not in seen:
                seen.add(src_key)
                nodes.append(LineageNode(id=src_key, kind="document", label=ev.source))
            sources.add(ev.source)
            edges.append(LineageEdge(source=src_key, target=ev_id, relation="source_of"))

    # Connected DOCUMENT entities also count as provenance.
    rels = list((await db.execute(
        select(Relationship).where(
            or_(Relationship.source_id == entity.id, Relationship.target_id == entity.id)
        )
    )).scalars().all())
    neighbor_ids = {r.source_id for r in rels} | {r.target_id for r in rels}
    neighbor_ids.discard(entity.id)
    if neighbor_ids:
        for doc in (await db.execute(
            select(Entity).where(Entity.id.in_(neighbor_ids), Entity.type == EntityType.DOCUMENT)
        )).scalars().all():
            did = str(doc.id)
            if did not in seen:
                seen.add(did)
                nodes.append(LineageNode(id=did, kind="document", label=doc.name))
            edges.append(LineageEdge(source=did, target=str(entity.id), relation="mentions"))
            sources.add(doc.name)

    origin = "AI-extracted" if entity.is_ai_generated else "analyst-entered"
    summary = (
        f"{entity.name} is {origin}; backed by {len(evidence)} evidence item(s) "
        f"({verified_count} verified) from {len(sources)} source(s)."
    )
    return Lineage(entity_id=str(entity.id), summary=summary, nodes=nodes, edges=edges)
