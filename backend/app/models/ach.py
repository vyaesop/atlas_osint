"""Analysis of Competing Hypotheses (#1) — Heuer's structured analytic technique.

An :class:`AchAnalysis` poses a question and gathers competing
:class:`AchHypothesis` rows and :class:`AchItem` rows (pieces of evidence /
arguments, optionally linked to a real :class:`~app.models.evidence.Evidence`).
Each (hypothesis, item) cell is rated for consistency in :class:`AchRating`.
The scoring (``app.services.ach``) then ranks hypotheses by *least* weighted
inconsistency — the core ACH discipline of seeking to disprove rather than
confirm.
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID
from app.models.enums import AchConsistency


class AchAnalysis(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ach_analyses"

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)


class AchHypothesis(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ach_hypotheses"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("ach_analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class AchItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ach_items"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("ach_analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional link to a real evidence record this argument draws on.
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("evidence.id", ondelete="SET NULL"), nullable=True
    )
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class AchRating(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ach_ratings"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("ach_analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("ach_hypotheses.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("ach_items.id", ondelete="CASCADE"), nullable=False
    )
    consistency: Mapped[AchConsistency] = mapped_column(
        SAEnum(AchConsistency, name="ach_consistency"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("hypothesis_id", "item_id", name="uq_ach_rating_cell"),
    )
