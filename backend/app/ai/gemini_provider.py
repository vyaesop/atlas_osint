"""Google Gemini extraction/summarization via the google-genai SDK.

Uses structured output (``response_mime_type=application/json`` +
``response_schema``) so Gemini returns validated JSON. The ``google-genai``
package and client are imported/constructed lazily, so this is only a hard
dependency when ``AI_PROVIDER=gemini``.

Entity/relationship ``type`` fields are modeled as plain strings here and
coerced to the domain enums in Python — more robust across SDK schema quirks
than relying on enum translation, and unknown values are simply skipped.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from app.ai.models import ExtractedEntity, ExtractedRelationship, ExtractionResult
from app.ai.provider import ExtractionProvider
from app.core.config import settings
from app.models.enums import EntityType, RelationshipType

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are an information-extraction assistant for an intelligence-analysis "
    "platform. Extract only entities and relationships explicitly supported by "
    "the text. Do not infer or invent facts. For every relationship, quote the "
    "exact supporting sentence. All output is treated as unverified until a human "
    "analyst confirms it.\n\n"
    "Allowed entity types: " + ", ".join(t.value for t in EntityType) + ".\n"
    "Allowed relationship types: " + ", ".join(t.value for t in RelationshipType) + "."
)


class _GEntity(BaseModel):
    name: str
    type: str
    context: str | None = Field(default=None, description="Verbatim mention from the source")


class _GRelationship(BaseModel):
    source_name: str
    target_name: str
    type: str
    supporting_text: str | None = Field(default=None, description="Exact supporting sentence")
    confidence: float = 0.5


class _GExtraction(BaseModel):
    entities: list[_GEntity] = Field(default_factory=list)
    relationships: list[_GRelationship] = Field(default_factory=list)


def _coerce_entity_type(value: str) -> EntityType | None:
    try:
        return EntityType(value.strip().lower())
    except ValueError:
        return None


def _coerce_rel_type(value: str) -> RelationshipType | None:
    try:
        return RelationshipType(value.strip().upper())
    except ValueError:
        return None


class GeminiExtractor(ExtractionProvider):
    name = "gemini"

    def __init__(self) -> None:
        from google import genai  # lazy import

        if not settings.GEMINI_API_KEY:
            raise RuntimeError("AI_PROVIDER=gemini requires GEMINI_API_KEY to be set.")
        self._genai = genai
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def extract(self, text: str) -> ExtractionResult:
        from google.genai import types

        text = text[: settings.AI_MAX_INPUT_CHARS]
        response = await self._client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=f"Extract the entities and relationships from this document:\n\n{text}",
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM,
                response_mime_type="application/json",
                response_schema=_GExtraction,
                max_output_tokens=settings.AI_MAX_OUTPUT_TOKENS,
            ),
        )
        parsed: _GExtraction | None = getattr(response, "parsed", None)
        if parsed is None:
            return ExtractionResult(provider=self.name)

        entities: list[ExtractedEntity] = []
        for e in parsed.entities:
            etype = _coerce_entity_type(e.type)
            if etype is not None and e.name.strip():
                entities.append(ExtractedEntity(name=e.name.strip(), type=etype, context=e.context))

        relationships: list[ExtractedRelationship] = []
        for r in parsed.relationships:
            rtype = _coerce_rel_type(r.type)
            if rtype is not None and r.source_name.strip() and r.target_name.strip():
                relationships.append(
                    ExtractedRelationship(
                        source_name=r.source_name.strip(),
                        target_name=r.target_name.strip(),
                        type=rtype,
                        supporting_text=r.supporting_text,
                        confidence=max(0.0, min(1.0, r.confidence)),
                    )
                )

        return ExtractionResult(entities=entities, relationships=relationships, provider=self.name)

    async def summarize(self, subject: str, context: str) -> str:
        from google.genai import types

        response = await self._client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=f"Summarize {subject} from this graph context:\n\n{context}",
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You write concise, neutral analyst summaries. Use only the "
                    "provided structured context; do not add outside knowledge. "
                    "This summary is AI-generated and unverified."
                ),
                max_output_tokens=1024,
            ),
        )
        return (getattr(response, "text", None) or "").strip()
