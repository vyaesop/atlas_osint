"""Structured analytic annotations (#4 key assumptions, #6 analyst dissent).

A single annotation type carries a ``kind`` discriminator so the same surface
captures plain notes, key assumptions, recorded dissent, and devil's-advocate
challenges against a specific entity or relationship. Like evidence, exactly one
target must be set.
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    Enum as SAEnum,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID
from app.models.enums import AnnotationKind


class Annotation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "annotations"

    kind: Mapped[AnnotationKind] = mapped_column(
        SAEnum(AnnotationKind, name="annotation_kind"),
        default=AnnotationKind.NOTE,
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("entities.id", ondelete="CASCADE"), nullable=True, index=True
    )
    relationship_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("relationships.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN entity_id IS NULL THEN 0 ELSE 1 END) "
            "+ (CASE WHEN relationship_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="ck_annotation_exactly_one_target",
        ),
    )
