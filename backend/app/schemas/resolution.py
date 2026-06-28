from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DuplicateCandidateRead(BaseModel):
    a_id: uuid.UUID
    a_name: str
    b_id: uuid.UUID
    b_name: str
    type: str
    score: float
    reason: str
    shared_neighbors: int


class DuplicatesResponse(BaseModel):
    threshold: float
    candidates: list[DuplicateCandidateRead]


class MergeRequest(BaseModel):
    kept_id: uuid.UUID
    merged_id: uuid.UUID

    @model_validator(mode="after")
    def _distinct(self) -> "MergeRequest":
        if self.kept_id == self.merged_id:
            raise ValueError("kept_id and merged_id must differ.")
        return self


class MergeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kept_id: uuid.UUID
    merged_id: uuid.UUID
    merged_name: str
    added_aliases: list[str]
    moved_evidence_ids: list[uuid.UUID]
    moved_annotation_ids: list[uuid.UUID]
    undone: bool
    created_by: uuid.UUID | None
    created_at: datetime


class MergeResult(BaseModel):
    merge: MergeRead
    moved_relationships: int = Field(description="Relationships repointed onto the kept entity")
