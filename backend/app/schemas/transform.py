from __future__ import annotations

import uuid

from pydantic import BaseModel, Field, model_validator

from app.schemas.entity import EntityRead
from app.schemas.relationship import RelationshipRead


class TransformInfo(BaseModel):
    name: str
    description: str
    applies_to: list[str]


class SelectorRead(BaseModel):
    kind: str
    value: str


class TransformRunRequest(BaseModel):
    text: str | None = None
    entity_id: uuid.UUID | None = None
    # When an entity is given, persist selectors as linked ASSET nodes.
    persist: bool = False

    @model_validator(mode="after")
    def _one_input(self) -> "TransformRunRequest":
        if (self.text is None) == (self.entity_id is None):
            raise ValueError("Provide exactly one of text or entity_id.")
        if self.persist and self.entity_id is None:
            raise ValueError("persist requires entity_id (a node to attach selectors to).")
        return self


class TransformRunResponse(BaseModel):
    transform: str
    selectors: list[SelectorRead]
    created_entities: list[EntityRead] = Field(default_factory=list)
    created_relationships: list[RelationshipRead] = Field(default_factory=list)
