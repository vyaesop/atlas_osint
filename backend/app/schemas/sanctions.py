from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WatchlistEntryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=512)
    aliases: list[str] = Field(default_factory=list)
    program: str | None = None
    source: str | None = None
    country: str | None = None
    entity_type: str | None = None


class WatchlistBulkCreate(BaseModel):
    entries: list[WatchlistEntryCreate] = Field(min_length=1)


class WatchlistEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    aliases: list[str]
    program: str | None
    source: str | None
    country: str | None
    entity_type: str | None
    created_at: datetime


class ScreeningHitRead(BaseModel):
    entity_id: uuid.UUID
    entity_name: str
    entry_id: uuid.UUID
    entry_name: str
    program: str | None
    source: str | None
    score: float
    reason: str


class ScreeningResponse(BaseModel):
    threshold: float
    hits: list[ScreeningHitRead]
