from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType
from app.models.enums import RelationshipType


class Relationship(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A directed, typed edge between two entities."""

    __tablename__ = "relationships"

    type: Mapped[RelationshipType] = mapped_column(
        SAEnum(RelationshipType, name="relationship_type"), nullable=False, index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    properties: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)

    __table_args__ = (
        Index("ix_relationships_source_target", "source_id", "target_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Relationship {self.source_id}-[{self.type.value}]->{self.target_id}>"
