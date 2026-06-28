"""Extraction/summarization provider protocol."""
from __future__ import annotations

from typing import Protocol

from app.ai.models import ExtractionResult


class ExtractionProvider(Protocol):
    name: str

    async def extract(self, text: str) -> ExtractionResult:
        """Extract entities and relationships from document text."""
        ...

    async def summarize(self, subject: str, context: str) -> str:
        """Produce a short natural-language summary of ``subject`` given context."""
        ...
