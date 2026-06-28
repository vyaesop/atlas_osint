from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity
from app.models.enums import EntityType
from app.schemas.entity import EntityCreate, EntityUpdate, validate_properties


async def get(db: AsyncSession, entity_id: uuid.UUID) -> Entity | None:
    return await db.get(Entity, entity_id)


async def get_by_name(
    db: AsyncSession, name: str, type_: EntityType | None = None
) -> Entity | None:
    """Case-insensitive exact-name lookup, optionally scoped to a type.

    Used by ingestion to deduplicate extracted entities against existing ones.
    """
    stmt = select(Entity).where(func.lower(Entity.name) == name.lower())
    if type_ is not None:
        stmt = stmt.where(Entity.type == type_)
    result = await db.execute(stmt.limit(1))
    return result.scalar_one_or_none()


async def list_entities(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    type_: EntityType | None = None,
    q: str | None = None,
) -> list[Entity]:
    stmt = select(Entity)
    if type_ is not None:
        stmt = stmt.where(Entity.type == type_)
    if q:
        # Simple name contains. Fuzzy + alias matching arrive in Phase 2
        # (OpenSearch); JSON-array alias search is dialect-specific so it is
        # deliberately out of scope for this basic filter.
        stmt = stmt.where(Entity.name.ilike(f"%{q}%"))
    stmt = stmt.order_by(Entity.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def count(db: AsyncSession, *, type_: EntityType | None = None) -> int:
    stmt = select(func.count(Entity.id))
    if type_ is not None:
        stmt = stmt.where(Entity.type == type_)
    return int((await db.execute(stmt)).scalar_one())


async def create(db: AsyncSession, data: EntityCreate, *, created_by: uuid.UUID) -> Entity:
    entity = Entity(
        type=data.type,
        name=data.name,
        aliases=data.aliases,
        description=data.description,
        properties=data.properties,
        confidence_score=data.confidence_score,
        created_by=created_by,
    )
    db.add(entity)
    await db.flush()
    return entity


async def update(db: AsyncSession, entity: Entity, data: EntityUpdate) -> Entity:
    fields = data.model_dump(exclude_unset=True)
    if "properties" in fields and fields["properties"] is not None:
        # Re-validate against the entity's (immutable) type.
        fields["properties"] = validate_properties(entity.type, fields["properties"])
    for key, value in fields.items():
        setattr(entity, key, value)
    await db.flush()
    return entity


async def delete(db: AsyncSession, entity: Entity) -> None:
    await db.delete(entity)
    await db.flush()
