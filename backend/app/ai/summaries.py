"""Build structured context from the graph and ask the provider to summarize it.

Summaries are grounded strictly in recorded graph data (relationships + evidence)
and are returned labeled AI-generated/unverified — the model is an assistant, not
a source of truth.
"""
from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.service import ai_service
from app.models.entity import Entity
from app.models.evidence import Evidence
from app.models.relationship import Relationship


async def _entity_context(db: AsyncSession, entity: Entity) -> str:
    lines = [f"Entity: {entity.name} (type: {entity.type.value})"]
    if entity.description:
        lines.append(f"Description: {entity.description}")
    if entity.aliases:
        lines.append(f"Aliases: {', '.join(entity.aliases)}")

    rels = (await db.execute(
        select(Relationship).where(
            or_(Relationship.source_id == entity.id, Relationship.target_id == entity.id)
        )
    )).scalars().all()

    if rels:
        # Resolve neighbor names in one query.
        neighbor_ids = {r.source_id for r in rels} | {r.target_id for r in rels}
        neighbors = {
            e.id: e.name
            for e in (await db.execute(
                select(Entity).where(Entity.id.in_(neighbor_ids))
            )).scalars().all()
        }
        lines.append("Relationships:")
        for r in rels:
            direction = "→" if r.source_id == entity.id else "←"
            other = r.target_id if r.source_id == entity.id else r.source_id
            verified = "" if r.confidence_score > 0 else " [unverified]"
            lines.append(
                f"  {direction} {r.type.value} {neighbors.get(other, other)}{verified}"
            )

    evidence = (await db.execute(
        select(Evidence).where(Evidence.entity_id == entity.id).limit(20)
    )).scalars().all()
    if evidence:
        lines.append("Evidence:")
        for ev in evidence:
            tag = " [AI, unverified]" if ev.is_ai_generated else ""
            lines.append(f"  - {ev.title}{tag}: {(ev.quote or '')[:200]}")

    return "\n".join(lines)


async def summarize_entity(db: AsyncSession, entity_id: uuid.UUID) -> tuple[str, str] | None:
    entity = await db.get(Entity, entity_id)
    if entity is None:
        return None
    context = await _entity_context(db, entity)
    summary = await ai_service.summarize(entity.name, context)
    return summary, ai_service.provider_name


async def summarize_timeline(db: AsyncSession, entity_id: uuid.UUID) -> tuple[str, str] | None:
    entity = await db.get(Entity, entity_id)
    if entity is None:
        return None
    rels = (await db.execute(
        select(Relationship).where(
            or_(Relationship.source_id == entity_id, Relationship.target_id == entity_id)
        )
    )).scalars().all()
    dated = sorted(
        (r for r in rels if r.start_date is not None),
        key=lambda r: r.start_date,  # type: ignore[arg-type, return-value]
    )
    if not dated:
        context = f"No dated relationships recorded for {entity.name}."
    else:
        context = "Timeline of dated relationships:\n" + "\n".join(
            f"  {r.start_date.isoformat()}: {r.type.value}" for r in dated
        )
    summary = await ai_service.summarize(f"the timeline of {entity.name}", context)
    return summary, ai_service.provider_name
