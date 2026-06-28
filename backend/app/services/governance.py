"""Governance services: data retention/purge (#40), sanitized export (#41),
and insider-misuse detection (#42)."""
from __future__ import annotations

import statistics
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.abac import user_can_access
from app.models.audit import AuditLog
from app.models.casework import CaseItem
from app.models.entity import Entity
from app.models.enums import AuditAction, CaseItemType, Classification
from app.models.relationship import Relationship


# --------------------------- #40 retention --------------------------- #

async def _retention_candidates(db: AsyncSession, *, older_than_days: int, ai_only: bool) -> list[Entity]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    stmt = select(Entity).where(Entity.created_at < cutoff, Entity.legal_hold.is_(False))
    if ai_only:
        stmt = stmt.where(Entity.is_ai_generated.is_(True))
    return list((await db.execute(stmt)).scalars().all())


async def retention_preview(db: AsyncSession, *, older_than_days: int, ai_only: bool) -> list[Entity]:
    return await _retention_candidates(db, older_than_days=older_than_days, ai_only=ai_only)


async def retention_purge(db: AsyncSession, *, older_than_days: int, ai_only: bool) -> int:
    """Delete eligible entities (respecting legal holds). Caller commits."""
    candidates = await _retention_candidates(db, older_than_days=older_than_days, ai_only=ai_only)
    for e in candidates:
        await db.delete(e)
    await db.flush()
    return len(candidates)


# --------------------------- #41 sanitized export --------------------------- #

@dataclass(slots=True)
class ExportEntity:
    id: str
    type: str
    name: str
    classification: str
    redacted: bool


@dataclass(slots=True)
class ExportRelationship:
    id: str
    type: str
    source: str
    target: str


@dataclass(slots=True)
class ExportPackage:
    case_id: str
    entities: list[ExportEntity] = field(default_factory=list)
    relationships: list[ExportRelationship] = field(default_factory=list)
    redacted_count: int = 0


async def export_case(db: AsyncSession, case_id: uuid.UUID, requester) -> ExportPackage:
    """Export a case's entities + interconnecting relationships, redacting any
    object the requester is not cleared for (name/description stripped)."""
    item_ids = [
        ci.item_id for ci in (await db.execute(
            select(CaseItem).where(
                CaseItem.case_id == case_id, CaseItem.item_type == CaseItemType.ENTITY
            )
        )).scalars().all()
    ]
    pkg = ExportPackage(case_id=str(case_id))
    if not item_ids:
        return pkg

    entities = list((await db.execute(
        select(Entity).where(Entity.id.in_(item_ids))
    )).scalars().all())
    allowed_ids: set[uuid.UUID] = set()
    for e in entities:
        ok = user_can_access(requester, classification=e.classification, compartments=e.compartments)
        if ok:
            allowed_ids.add(e.id)
        else:
            pkg.redacted_count += 1
        pkg.entities.append(ExportEntity(
            id=str(e.id), type=e.type.value,
            name=e.name if ok else "[REDACTED]",
            classification=e.classification.value, redacted=not ok,
        ))

    rels = list((await db.execute(
        select(Relationship).where(
            Relationship.source_id.in_(item_ids), Relationship.target_id.in_(item_ids)
        )
    )).scalars().all())
    for r in rels:
        # Only release edges whose both endpoints are releasable.
        if r.source_id in allowed_ids and r.target_id in allowed_ids:
            pkg.relationships.append(ExportRelationship(
                id=str(r.id), type=r.type.value,
                source=str(r.source_id), target=str(r.target_id),
            ))
    return pkg


# --------------------------- #42 insider-misuse --------------------------- #

@dataclass(slots=True)
class InsiderFinding:
    actor_id: str
    total_actions: int
    deletes: int
    off_hours: int
    distinct_targets: int
    risk: str
    flags: list[str] = field(default_factory=list)


def _is_off_hours(ts: datetime) -> bool:
    hour = ts.astimezone(timezone.utc).hour if ts.tzinfo else ts.hour
    return hour < 6 or hour >= 22


async def detect_insider_anomalies(db: AsyncSession, *, z_threshold: float = 2.0) -> list[InsiderFinding]:
    entries = list((await db.execute(select(AuditLog))).scalars().all())
    by_actor: dict[uuid.UUID, list[AuditLog]] = {}
    for e in entries:
        if e.actor_id is not None:
            by_actor.setdefault(e.actor_id, []).append(e)
    if not by_actor:
        return []

    totals = [len(v) for v in by_actor.values()]
    mean = statistics.fmean(totals)
    stdev = statistics.pstdev(totals) if len(totals) > 1 else 0.0

    findings: list[InsiderFinding] = []
    for actor_id, acts in by_actor.items():
        deletes = sum(1 for a in acts if a.action is AuditAction.DELETE)
        off_hours = sum(1 for a in acts if _is_off_hours(a.created_at))
        distinct = len({a.target_id for a in acts if a.target_id})
        flags: list[str] = []
        if stdev > 0 and (len(acts) - mean) / stdev >= z_threshold:
            flags.append(f"activity volume {((len(acts) - mean) / stdev):.1f}σ above peers")
        if deletes >= 5 and deletes / len(acts) >= 0.5:
            flags.append(f"high deletion rate ({deletes}/{len(acts)})")
        if off_hours / len(acts) >= 0.5 and len(acts) >= 4:
            flags.append(f"mostly off-hours activity ({off_hours}/{len(acts)})")
        if flags:
            risk = "high" if len(flags) >= 2 else "medium"
            findings.append(InsiderFinding(
                actor_id=str(actor_id), total_actions=len(acts), deletes=deletes,
                off_hours=off_hours, distinct_targets=distinct, risk=risk, flags=flags,
            ))
    findings.sort(key=lambda f: (f.risk == "high", len(f.flags)), reverse=True)
    return findings
