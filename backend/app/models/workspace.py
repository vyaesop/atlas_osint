"""Workspace models: saved views / pinboards (#36) and analytic notebooks (#35).

A :class:`SavedView` stores a named, reusable view configuration (graph focus +
filters, a map extent, a dashboard, or a pinboard of entity ids). A
:class:`Notebook` is an analytic narrative of ordered :class:`NotebookBlock`s;
graph/timeline/entity blocks reference live data so they stay current.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType
from app.models.enums import NotebookBlockKind, SavedViewKind


class SavedView(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "saved_views"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[SavedViewKind] = mapped_column(
        SAEnum(SavedViewKind, name="saved_view_kind"), default=SavedViewKind.GRAPH, nullable=False
    )
    # Arbitrary view config: focus entity, filters, layout, pinned ids, map extent…
    state: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True, index=True)


class Notebook(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notebooks"

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)


class NotebookBlock(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notebook_blocks"

    notebook_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    kind: Mapped[NotebookBlockKind] = mapped_column(
        SAEnum(NotebookBlockKind, name="notebook_block_kind"),
        default=NotebookBlockKind.TEXT, nullable=False,
    )
    content: Mapped[str | None] = mapped_column(Text, nullable=True)  # markdown for text blocks
    # For live blocks: {"entity_ids": [...]} / {"saved_view_id": ...} / {"entity_id": ...}
    ref: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
