from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import VerificationStatus
from app.models.evidence import Evidence
from app.schemas.evidence import EvidenceCreate, EvidenceUpdate


async def get(db: AsyncSession, evidence_id: uuid.UUID) -> Evidence | None:
    return await db.get(Evidence, evidence_id)


async def list_evidence(
    db: AsyncSession,
    *,
    entity_id: uuid.UUID | None = None,
    relationship_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Evidence]:
    stmt = select(Evidence)
    if entity_id is not None:
        stmt = stmt.where(Evidence.entity_id == entity_id)
    if relationship_id is not None:
        stmt = stmt.where(Evidence.relationship_id == relationship_id)
    stmt = stmt.order_by(Evidence.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create(db: AsyncSession, data: EvidenceCreate, *, created_by: uuid.UUID) -> Evidence:
    ev = Evidence(**data.model_dump(), created_by=created_by)
    db.add(ev)
    await db.flush()
    return ev


async def update(db: AsyncSession, ev: Evidence, data: EvidenceUpdate) -> Evidence:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(ev, key, value)
    await db.flush()
    return ev


async def set_verification(
    db: AsyncSession, ev: Evidence, status: VerificationStatus, *, reviewer_id: uuid.UUID
) -> Evidence:
    ev.verification_status = status
    if status is VerificationStatus.VERIFIED:
        ev.verified_by = reviewer_id
        ev.verified_at = datetime.now(timezone.utc)
    else:
        ev.verified_by = None
        ev.verified_at = None
    await db.flush()
    return ev


async def delete(db: AsyncSession, ev: Evidence) -> None:
    await db.delete(ev)
    await db.flush()
