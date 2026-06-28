"""Gemini-backed NL→QuerySpec parsing (#24).

Used when ``AI_PROVIDER=gemini``; falls back to the heuristic assistant if the
SDK/key is unavailable (see ``assistant.build_assistant``).
"""
from __future__ import annotations

from pydantic import BaseModel

from app.ai.assistant import Assistant, QuerySpec
from app.core.config import settings
from app.models.enums import EntityType

_SYSTEM = (
    "You translate an analyst's natural-language question about an intelligence "
    "graph into a structured query. intent is one of: 'search' (find entities), "
    "'neighbors' (entities connected to one named entity), 'path' (connection "
    "between two named entities). Set 'name' (and 'target_name' for path) to the "
    "entity names mentioned. entity_type, when clear, is one of: "
    + ", ".join(t.value for t in EntityType) + "."
)


class _Spec(BaseModel):
    intent: str = "search"
    entity_type: str | None = None
    name: str | None = None
    target_name: str | None = None


class GeminiAssistant(Assistant):
    name = "gemini"

    def __init__(self) -> None:
        from google import genai  # lazy import

        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GeminiAssistant requires GEMINI_API_KEY.")
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def parse(self, question: str) -> QuerySpec:
        from google.genai import types

        # Synchronous call (parse is sync in the Assistant interface).
        response = self._client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=f"Question: {question}",
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM,
                response_mime_type="application/json",
                response_schema=_Spec,
                max_output_tokens=256,
            ),
        )
        parsed: _Spec | None = getattr(response, "parsed", None)
        if parsed is None:
            return QuerySpec(intent="search")
        etype: EntityType | None = None
        if parsed.entity_type:
            try:
                etype = EntityType(parsed.entity_type.strip().lower())
            except ValueError:
                etype = None
        intent = parsed.intent if parsed.intent in {"search", "neighbors", "path"} else "search"
        return QuerySpec(intent=intent, entity_type=etype, name=parsed.name,
                         target_name=parsed.target_name)
