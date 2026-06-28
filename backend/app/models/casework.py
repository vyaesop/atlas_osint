"""Casework models (#31 cases, #32 tasks/RFIs, #33 comments, #34 review flow).

A :class:`Case` is the first-class container for an investigation: it carries a
status lifecycle (incl. the review→dissemination flow) and a classification
marking, and gathers graph objects via :class:`CaseItem`. Tasks/RFIs and
threaded comments hang off cases (or, for comments, any target).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID
from app.models.enums import (
    CaseItemType,
    CaseStatus,
    Classification,
    CommentTargetType,
    TaskKind,
    TaskStatus,
)


class Case(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "cases"

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CaseStatus] = mapped_column(
        SAEnum(CaseStatus, name="case_status"), default=CaseStatus.OPEN, nullable=False, index=True
    )
    classification: Mapped[Classification] = mapped_column(
        SAEnum(Classification, name="classification"),
        default=Classification.UNCLASSIFIED, nullable=False,
    )
    priority: Mapped[int] = mapped_column(default=3, nullable=False)  # 1 (high) – 5 (low)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)


class CaseItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Associates a graph object (entity/relationship/document/ach/view) to a case."""

    __tablename__ = "case_items"

    case_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_type: Mapped[CaseItemType] = mapped_column(
        SAEnum(CaseItemType, name="case_item_type"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)

    __table_args__ = (
        UniqueConstraint("case_id", "item_type", "item_id", name="uq_case_item"),
    )


class Task(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A task or request-for-information, optionally scoped to a case (#32)."""

    __tablename__ = "tasks"

    case_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True
    )
    kind: Mapped[TaskKind] = mapped_column(
        SAEnum(TaskKind, name="task_kind"), default=TaskKind.TASK, nullable=False
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, name="task_status"), default=TaskStatus.OPEN, nullable=False, index=True
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)


class Comment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A threaded comment on a case, entity, relationship, or task (#33)."""

    __tablename__ = "comments"

    target_type: Mapped[CommentTargetType] = mapped_column(
        SAEnum(CommentTargetType, name="comment_target_type"), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
