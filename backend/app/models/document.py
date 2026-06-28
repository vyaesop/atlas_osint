from __future__ import annotations

import uuid

from sqlalchemy import Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID, JSONType
from app.models.enums import DocumentStatus


class Document(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An ingested source document and its extraction record.

    The document is also represented in the graph as an Entity of type
    ``document`` (``entity_id``); this table holds the raw text and ingestion
    metadata that don't belong on the graph node.
    """

    __tablename__ = "documents"

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, name="document_status"),
        default=DocumentStatus.PENDING,
        nullable=False,
        index=True,
    )
    # Extraction summary: counts, provider, error, etc.
    extraction: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
