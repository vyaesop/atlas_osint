"""Reversible record of an entity merge (#13).

When entity *B* is merged into *A*, this row captures everything needed to undo
it: a full snapshot of *B*, which relationships were repointed (with their
original endpoints), which evidence/annotations were moved, and which aliases /
property keys were added to *A*. That makes merges fully auditable and
reversible via the unmerge endpoint.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType


class EntityMerge(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "entity_merges"

    kept_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    merged_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False)
    merged_name: Mapped[str] = mapped_column(String(512), nullable=False)

    # Full snapshot of the merged (deleted) entity, for recreation on unmerge.
    merged_snapshot: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    # [{id, old_source, old_target, deleted}] for each repointed relationship.
    moved_relationships: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    moved_evidence_ids: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    moved_annotation_ids: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    added_aliases: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    added_property_keys: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    undone: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
