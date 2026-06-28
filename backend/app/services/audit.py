"""Helper for writing audit-log entries within the caller's DB session."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.enums import AuditAction


async def record_audit(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: AuditAction,
    target_table: str,
    target_id: uuid.UUID | None,
    changes: dict | None = None,
    reason: str | None = None,
) -> None:
    """Add an audit entry to the session. Flushed/committed by the caller."""
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            target_table=target_table,
            target_id=target_id,
            changes=changes or {},
            reason=reason,
        )
    )
