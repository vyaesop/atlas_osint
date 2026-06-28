from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.models.enums import EntityType


class SearchHitRead(BaseModel):
    id: uuid.UUID
    type: EntityType
    name: str
    aliases: list[str]
    score: float
    matched_on: str


class SuggestionRead(BaseModel):
    id: uuid.UUID
    type: EntityType
    name: str
    score: float


class ReindexResult(BaseModel):
    indexed: int
