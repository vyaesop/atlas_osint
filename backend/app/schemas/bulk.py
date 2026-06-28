from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import EntityType, RelationshipType


class BulkEntity(BaseModel):
    # Local key used by relationships in the same payload to reference this node.
    ref: str = Field(min_length=1)
    type: EntityType
    name: str = Field(min_length=1, max_length=512)
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)


class BulkRelationship(BaseModel):
    type: RelationshipType
    source_ref: str
    target_ref: str
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    notes: str | None = None


class BulkImportRequest(BaseModel):
    entities: list[BulkEntity] = Field(default_factory=list)
    relationships: list[BulkRelationship] = Field(default_factory=list)
    # Reuse existing entities with the same name+type instead of duplicating.
    deduplicate: bool = True


class BulkImportResult(BaseModel):
    entities_created: int
    entities_matched: int
    relationships_created: int
    skipped: int
