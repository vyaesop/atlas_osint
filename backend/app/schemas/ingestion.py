from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.schemas.entity import EntityRead
from app.schemas.relationship import RelationshipRead


class IngestTextRequest(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    text: str = Field(min_length=1)


class IngestEmailRequest(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    content: str = Field(min_length=1, description="Raw EML or MBOX content")


class CryptoTransaction(BaseModel):
    from_address: str = Field(min_length=1)
    to_address: str = Field(min_length=1)
    amount: float | None = None
    tx_hash: str | None = None
    timestamp: str | None = None


class CryptoImportRequest(BaseModel):
    asset: str = Field(default="BTC", min_length=1, max_length=32)
    transactions: list[CryptoTransaction] = Field(min_length=1)


class FeedRequest(BaseModel):
    content: str = Field(min_length=1, description="Raw RSS 2.0 or Atom XML")
    ingest: bool = False
    max_items: int = Field(default=25, ge=1, le=200)


class FeedItemRead(BaseModel):
    title: str
    summary: str
    link: str
    published: str | None


class FeedResponse(BaseModel):
    feed_title: str
    count: int
    items: list[FeedItemRead]
    # Populated when ingest=true.
    documents_created: int = 0
    entities_created: int = 0
    relationships_created: int = 0


class IngestionSummary(BaseModel):
    entities_created: int
    relationships_created: int
    entities_total: int
    relationships_total: int


class IngestionResponse(BaseModel):
    document_id: uuid.UUID
    document_entity_id: uuid.UUID
    provider: str
    summary: IngestionSummary
    # All entities/relationships touched, so the UI can drop them on the canvas.
    entities: list[EntityRead]
    relationships: list[RelationshipRead]


class SummaryResponse(BaseModel):
    subject_id: uuid.UUID
    summary: str
    provider: str
    ai_generated: bool = True
