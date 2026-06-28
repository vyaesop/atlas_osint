"""Network diff — what changed since a point in time (#47).

Reports entities/relationships added or modified since ``since`` (from
created_at/updated_at) and those removed (from the audit log's DELETE entries),
so an analyst can see how the picture evolved between two reviews.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.abac import user_can_access
from app.models.audit import AuditLog
from app.models.entity import Entity
from app.models.enums import AuditAction
from app.models.relationship import Relationship


@dataclass(slots=True)
class DiffItem:
    id: str
    kind: str          # entity type or relationship type
    label: str


@dataclass(slots=True)
class NetworkDiff:
    since: str
    added_entities: list[DiffItem] = field(default_factory=list)
    modified_entities: list[DiffItem] = field(default_factory=list)
    added_relationships: list[DiffItem] = field(default_factory=list)
    modified_relationships: list[DiffItem] = field(default_factory=list)
    removed: list[DiffItem] = field(default_factory=list)


async def compute_diff(db: AsyncSession, since: datetime, *, user=None) -> NetworkDiff:
    diff = NetworkDiff(since=since.isoformat())

    def _ok(entity: Entity) -> bool:
        # No user → unfiltered (internal/admin use). With a user, ABAC applies so
        # the change feed never reveals compartmented entities by name.
        if user is None:
            return True
        return user_can_access(user, classification=entity.classification,
                               compartments=entity.compartments)

    added_e = [e for e in (await db.execute(
        select(Entity).where(Entity.created_at >= since))).scalars().all() if _ok(e)]
    diff.added_entities = [DiffItem(str(e.id), e.type.value, e.name) for e in added_e]

    modified_e = [e for e in (await db.execute(
        select(Entity).where(and_(Entity.updated_at >= since, Entity.created_at < since)))
    ).scalars().all() if _ok(e)]
    diff.modified_entities = [DiffItem(str(e.id), e.type.value, e.name) for e in modified_e]

    # A relationship is releasable only if both endpoints are. Cache endpoint
    # accessibility to avoid re-loading entities per edge.
    _access_cache: dict = {}

    async def _rel_ok(rel: Relationship) -> bool:
        if user is None:
            return True
        for eid in (rel.source_id, rel.target_id):
            if eid not in _access_cache:
                ent = await db.get(Entity, eid)
                _access_cache[eid] = ent is not None and _ok(ent)
            if not _access_cache[eid]:
                return False
        return True

    added_r = (await db.execute(
        select(Relationship).where(Relationship.created_at >= since)
    )).scalars().all()
    diff.added_relationships = [
        DiffItem(str(r.id), r.type.value, str(r.id)) for r in added_r if await _rel_ok(r)
    ]

    modified_r = (await db.execute(
        select(Relationship).where(
            and_(Relationship.updated_at >= since, Relationship.created_at < since)
        )
    )).scalars().all()
    diff.modified_relationships = [
        DiffItem(str(r.id), r.type.value, str(r.id)) for r in modified_r if await _rel_ok(r)
    ]

    removed = (await db.execute(
        select(AuditLog).where(
            and_(
                AuditLog.action == AuditAction.DELETE,
                AuditLog.created_at >= since,
                AuditLog.target_table.in_(["entities", "relationships"]),
            )
        )
    )).scalars().all()
    diff.removed = [
        DiffItem(str(a.target_id) if a.target_id else "", a.target_table, a.target_table)
        for a in removed
    ]
    return diff
