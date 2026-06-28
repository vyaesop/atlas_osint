from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import RelationshipType
from app.models.relationship import Relationship
from app.schemas.relationship import RelationshipCreate, RelationshipUpdate


async def get(db: AsyncSession, rel_id: uuid.UUID) -> Relationship | None:
    return await db.get(Relationship, rel_id)


async def list_relationships(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    entity_id: uuid.UUID | None = None,
    type_: RelationshipType | None = None,
) -> list[Relationship]:
    stmt = select(Relationship)
    if entity_id is not None:
        stmt = stmt.where(
            or_(Relationship.source_id == entity_id, Relationship.target_id == entity_id)
        )
    if type_ is not None:
        stmt = stmt.where(Relationship.type == type_)
    stmt = stmt.order_by(Relationship.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create(
    db: AsyncSession, data: RelationshipCreate, *, created_by: uuid.UUID
) -> Relationship:
    rel = Relationship(
        type=data.type,
        source_id=data.source_id,
        target_id=data.target_id,
        start_date=data.start_date,
        end_date=data.end_date,
        confidence_score=data.confidence_score,
        notes=data.notes,
        properties=data.properties,
        created_by=created_by,
    )
    db.add(rel)
    await db.flush()
    return rel


async def update(
    db: AsyncSession, rel: Relationship, data: RelationshipUpdate
) -> Relationship:
    fields = data.model_dump(exclude_unset=True)
    for key, value in fields.items():
        setattr(rel, key, value)
    await db.flush()
    return rel


async def delete(db: AsyncSession, rel: Relationship) -> None:
    await db.delete(rel)
    await db.flush()
