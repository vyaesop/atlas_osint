from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    Classification,
    EvidenceStance,
    InfoCredibility,
    SourceReliability,
    VerificationStatus,
)


class EvidenceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    source: str | None = None
    url: str | None = Field(default=None, max_length=2048)
    publication_date: date | None = None
    quote: str | None = None
    author: str | None = None
    reliability_score: float = Field(default=0.0, ge=0.0, le=1.0)
    source_reliability: SourceReliability | None = None
    info_credibility: InfoCredibility | None = None
    classification: Classification = Classification.UNCLASSIFIED
    stance: EvidenceStance = EvidenceStance.SUPPORTS
    entity_id: uuid.UUID | None = None
    relationship_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _exactly_one_target(self) -> "EvidenceCreate":
        targets = [self.entity_id is not None, self.relationship_id is not None]
        if sum(targets) != 1:
            raise ValueError(
                "Evidence must attach to exactly one of entity_id or relationship_id."
            )
        return self


class EvidenceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    source: str | None = None
    url: str | None = Field(default=None, max_length=2048)
    publication_date: date | None = None
    quote: str | None = None
    author: str | None = None
    reliability_score: float | None = Field(default=None, ge=0.0, le=1.0)
    source_reliability: SourceReliability | None = None
    info_credibility: InfoCredibility | None = None
    stance: EvidenceStance | None = None


class EvidenceVerify(BaseModel):
    """Reviewer decision in the verification workflow."""

    status: VerificationStatus


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    source: str | None
    url: str | None
    publication_date: date | None
    quote: str | None
    author: str | None
    reliability_score: float
    source_reliability: SourceReliability | None
    info_credibility: InfoCredibility | None
    classification: Classification
    stance: EvidenceStance
    verification_status: VerificationStatus
    verified_by: uuid.UUID | None
    verified_at: datetime | None
    is_ai_generated: bool
    entity_id: uuid.UUID | None
    relationship_id: uuid.UUID | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ConfidenceSummary(BaseModel):
    """Computed confidence breakdown for an entity or relationship."""

    score: float
    support_mass: float
    contradiction_mass: float
    supporting_count: int
    contradicting_count: int
    neutral_count: int
    is_contradicted: bool
    # ICD 203 estimative language (#2)
    estimative_label: str
    probability_band: str
    analytic_confidence: str
