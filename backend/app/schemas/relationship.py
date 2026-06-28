from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RelationshipType


class RelationshipCreate(BaseModel):
    type: RelationshipType
    source_id: uuid.UUID
    target_id: uuid.UUID
    start_date: date | None = None
    end_date: date | None = None
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    notes: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class RelationshipUpdate(BaseModel):
    type: RelationshipType | None = None
    start_date: date | None = None
    end_date: date | None = None
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: str | None = None
    properties: dict[str, Any] | None = None


class RelationshipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: RelationshipType
    source_id: uuid.UUID
    target_id: uuid.UUID
    start_date: date | None
    end_date: date | None
    confidence_score: float
    source_count: int
    notes: str | None
    properties: dict[str, Any]
    is_ai_generated: bool
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
