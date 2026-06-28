from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AchConsistency


# ---- write models ---- #

class AchAnalysisCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    question: str | None = None


class HypothesisCreate(BaseModel):
    text: str = Field(min_length=1)
    order: int = 0


class ItemCreate(BaseModel):
    text: str = Field(min_length=1)
    evidence_id: uuid.UUID | None = None
    weight: float = Field(default=1.0, ge=0.0, le=10.0)
    order: int = 0


class RatingSet(BaseModel):
    hypothesis_id: uuid.UUID
    item_id: uuid.UUID
    consistency: AchConsistency


# ---- read models ---- #

class HypothesisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    text: str
    order: int


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    text: str
    evidence_id: uuid.UUID | None
    weight: float
    order: int


class RatingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    hypothesis_id: uuid.UUID
    item_id: uuid.UUID
    consistency: AchConsistency


class HypothesisScoreRead(BaseModel):
    hypothesis_id: uuid.UUID
    text: str
    inconsistency_score: float
    consistent_count: int
    inconsistent_count: int
    neutral_count: int
    na_count: int
    rank: int


class ItemDiagnosticityRead(BaseModel):
    item_id: uuid.UUID
    text: str
    weight: float
    diagnosticity: float
    rated_hypotheses: int


class AchScoreRead(BaseModel):
    hypotheses: list[HypothesisScoreRead]
    items: list[ItemDiagnosticityRead]
    most_likely_hypothesis_id: uuid.UUID | None


class AchAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    question: str | None
    status: str
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class AchAnalysisDetail(AchAnalysisRead):
    hypotheses: list[HypothesisRead]
    items: list[ItemRead]
    ratings: list[RatingRead]
    scores: AchScoreRead
