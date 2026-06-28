from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotation import Annotation
from app.models.enums import AnnotationKind
from app.schemas.annotation import AnnotationCreate


async def create(db: AsyncSession, data: AnnotationCreate, *, created_by: uuid.UUID) -> Annotation:
    ann = Annotation(**data.model_dump(), created_by=created_by)
    db.add(ann)
    await db.flush()
    return ann


async def get(db: AsyncSession, annotation_id: uuid.UUID) -> Annotation | None:
    return await db.get(Annotation, annotation_id)


async def list_annotations(
    db: AsyncSession,
    *,
    entity_id: uuid.UUID | None = None,
    relationship_id: uuid.UUID | None = None,
    kind: AnnotationKind | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Annotation]:
    stmt = select(Annotation)
    if entity_id is not None:
        stmt = stmt.where(Annotation.entity_id == entity_id)
    if relationship_id is not None:
        stmt = stmt.where(Annotation.relationship_id == relationship_id)
    if kind is not None:
        stmt = stmt.where(Annotation.kind == kind)
    stmt = stmt.order_by(Annotation.created_at.desc()).offset(skip).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


async def delete(db: AsyncSession, ann: Annotation) -> None:
    await db.delete(ann)
    await db.flush()
