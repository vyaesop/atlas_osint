"""Internal data shapes passed between the indexer, backends, and service."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SearchDocument:
    """A denormalized, indexable view of an entity."""

    id: str
    type: str
    name: str
    aliases: list[str] = field(default_factory=list)
    description: str | None = None
    confidence_score: float = 0.0
    embedding: list[float] | None = None

    def text_blob(self) -> str:
        """Concatenated searchable text (name + aliases + description)."""
        parts = [self.name, *self.aliases]
        if self.description:
            parts.append(self.description)
        return " ".join(p for p in parts if p)


@dataclass(slots=True)
class SearchHit:
    id: str
    type: str
    name: str
    score: float
    aliases: list[str] = field(default_factory=list)
    matched_on: str = "text"  # "text" | "fuzzy" | "alias" | "semantic"


@dataclass(slots=True)
class Suggestion:
    id: str
    type: str
    name: str
    score: float
