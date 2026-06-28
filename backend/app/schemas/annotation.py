from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import AnnotationKind


class AnnotationCreate(BaseModel):
    kind: AnnotationKind = AnnotationKind.NOTE
    text: str = Field(min_length=1)
    entity_id: uuid.UUID | None = None
    relationship_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _exactly_one_target(self) -> "AnnotationCreate":
        if sum([self.entity_id is not None, self.relationship_id is not None]) != 1:
            raise ValueError("Annotation must attach to exactly one of entity_id or relationship_id.")
        return self


class AnnotationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kind: AnnotationKind
    text: str
    entity_id: uuid.UUID | None
    relationship_id: uuid.UUID | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
