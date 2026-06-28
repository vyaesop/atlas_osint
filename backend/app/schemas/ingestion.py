from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.schemas.entity import EntityRead
from app.schemas.relationship import RelationshipRead


class IngestTextRequest(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    text: str = Field(min_length=1)


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
