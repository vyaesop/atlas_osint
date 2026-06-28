"""Transform interface + registry + built-in transforms (#17)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.ai.models import ExtractedEntity, ExtractedRelationship
from app.transforms.selectors import Selector, extract_selectors


@dataclass(slots=True)
class TransformResult:
    selectors: list[Selector] = field(default_factory=list)
    entities: list[ExtractedEntity] = field(default_factory=list)
    relationships: list[ExtractedRelationship] = field(default_factory=list)


class Transform(ABC):
    name: str
    description: str
    # Entity types this applies to, or {"*"} / {"text"} for any text input.
    applies_to: set[str] = {"*"}

    @abstractmethod
    def run_text(self, text: str) -> TransformResult: ...


class SelectorExtractTransform(Transform):
    name = "extract-selectors"
    description = "Extract emails, domains, URLs, IPs, phones, crypto addresses, and hashes from text."
    applies_to = {"*"}

    def run_text(self, text: str) -> TransformResult:
        return TransformResult(selectors=extract_selectors(text))


REGISTRY: dict[str, Transform] = {
    t.name: t for t in (SelectorExtractTransform(),)
}
