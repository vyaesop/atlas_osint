from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Enum as SAEnum, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType
from app.models.enums import EntityType


class Entity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A graph node of any type.

    Common, queryable fields are first-class columns; type-specific fields
    (e.g. birth_date for a person, market_value for a company) live in the
    JSONB ``properties`` column. Type-specific validation is enforced in the
    Pydantic schema layer per ``EntityType``.
    """

    __tablename__ = "entities"

    type: Mapped[EntityType] = mapped_column(
        SAEnum(EntityType, name="entity_type"), nullable=False, index=True
    )
    # Canonical display name across all types (full_name, name, title...).
    name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    aliases: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    properties: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # AI-extracted entities are flagged until a researcher verifies them.
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)

    __table_args__ = (
        Index("ix_entities_type_name", "type", "name"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Entity {self.type.value}:{self.name}>"
