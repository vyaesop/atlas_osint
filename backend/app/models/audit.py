from __future__ import annotations

import uuid

from sqlalchemy import Enum as SAEnum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType
from app.models.enums import AuditAction


class AuditLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Immutable record of who changed what, when, and (optionally) why."""

    __tablename__ = "audit_log"

    actor_id: Mapped[uuid.UUID | None] = mapped_column(GUID, index=True)
    action: Mapped[AuditAction] = mapped_column(
        SAEnum(AuditAction, name="audit_action"), nullable=False
    )
    target_table: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(GUID, index=True)
    # Snapshot of changed fields / before-after diff.
    changes: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Tamper-evident hash chain (#39): entry_hash = H(content + prev_hash).
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entry_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
