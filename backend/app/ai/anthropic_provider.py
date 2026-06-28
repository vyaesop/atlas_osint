"""Claude-powered extraction/summarization via the Anthropic SDK.

Uses ``claude-opus-4-8`` with **structured outputs** (``messages.parse`` against a
Pydantic schema) so the model returns validated JSON, plus adaptive thinking.
The ``anthropic`` package and the client are imported/constructed lazily so this
module is only a hard dependency when ``AI_PROVIDER=anthropic``.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.ai.models import ExtractedEntity, ExtractedRelationship, ExtractionResult
from app.ai.provider import ExtractionProvider
from app.core.config import settings
from app.models.enums import EntityType, RelationshipType

_SYSTEM = (
    "You are an information-extraction assistant for an intelligence-analysis "
    "platform. Extract only entities and relationships explicitly supported by "
    "the text. Do not infer or invent facts. For every relationship, quote the "
    "exact supporting sentence. All output is treated as unverified until a human "
    "analyst confirms it."
)


class _AIEntity(BaseModel):
    name: str
    type: EntityType
    context: str | None = Field(default=None, description="Verbatim mention from the source")


class _AIRelationship(BaseModel):
    source_name: str
    target_name: str
    type: RelationshipType
    supporting_text: str | None = Field(default=None, description="Exact supporting sentence")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class _AIExtraction(BaseModel):
    entities: list[_AIEntity]
    relationships: list[_AIRelationship]


class AnthropicExtractor(ExtractionProvider):
    name = "anthropic"

    def __init__(self) -> None:
        from anthropic import AsyncAnthropic  # lazy import

        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError(
                "AI_PROVIDER=anthropic requires ANTHROPIC_API_KEY to be set."
            )
        self._client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def extract(self, text: str) -> ExtractionResult:
        text = text[: settings.AI_MAX_INPUT_CHARS]
        response = await self._client.messages.parse(
            model=settings.AI_MODEL,
            max_tokens=settings.AI_MAX_OUTPUT_TOKENS,
            thinking={"type": "adaptive"},
            system=_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Extract the entities and relationships from this document:\n\n"
                        f"{text}"
                    ),
                }
            ],
            output_format=_AIExtraction,
        )
        parsed = response.parsed_output
        if parsed is None:
            return ExtractionResult(provider=self.name)
        return ExtractionResult(
            entities=[
                ExtractedEntity(name=e.name, type=e.type, context=e.context)
                for e in parsed.entities
            ],
            relationships=[
                ExtractedRelationship(
                    source_name=r.source_name, target_name=r.target_name,
                    type=r.type, supporting_text=r.supporting_text,
                    confidence=r.confidence,
                )
                for r in parsed.relationships
            ],
            provider=self.name,
        )

    async def summarize(self, subject: str, context: str) -> str:
        response = await self._client.messages.create(
            model=settings.AI_MODEL,
            max_tokens=1024,
            thinking={"type": "adaptive"},
            system=(
                "You write concise, neutral analyst summaries. Use only the "
                "provided structured context; do not add outside knowledge. "
                "This summary is AI-generated and unverified."
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"Summarize {subject} from this graph context:\n\n{context}",
                }
            ],
        )
        return "".join(b.text for b in response.content if b.type == "text").strip()
