"""Provider-agnostic shapes for extraction results."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import EntityType, RelationshipType


@dataclass(slots=True)
class ExtractedEntity:
    name: str
    type: EntityType
    # Verbatim snippet from the source that mentions this entity (evidence quote).
    context: str | None = None


@dataclass(slots=True)
class ExtractedRelationship:
    source_name: str
    target_name: str
    type: RelationshipType
    # The sentence/phrase the relationship was inferred from (evidence quote).
    supporting_text: str | None = None
    confidence: float = 0.5


@dataclass(slots=True)
class ExtractionResult:
    entities: list[ExtractedEntity] = field(default_factory=list)
    relationships: list[ExtractedRelationship] = field(default_factory=list)
    provider: str = "heuristic"
