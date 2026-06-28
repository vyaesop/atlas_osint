"""Selects and exposes the configured AI provider."""
from __future__ import annotations

from app.ai.heuristic import HeuristicExtractor
from app.ai.models import ExtractionResult
from app.ai.provider import ExtractionProvider
from app.core.config import settings


def _build_provider() -> ExtractionProvider:
    if settings.AI_PROVIDER == "anthropic":
        from app.ai.anthropic_provider import AnthropicExtractor  # lazy import

        return AnthropicExtractor()
    if settings.AI_PROVIDER == "gemini":
        from app.ai.gemini_provider import GeminiExtractor  # lazy import

        return GeminiExtractor()
    return HeuristicExtractor()


class AIService:
    def __init__(self, provider: ExtractionProvider | None = None) -> None:
        self._provider = provider or _build_provider()

    @property
    def provider_name(self) -> str:
        return self._provider.name

    async def extract(self, text: str) -> ExtractionResult:
        text = (text or "")[: settings.AI_MAX_INPUT_CHARS]
        if not text.strip():
            return ExtractionResult(provider=self.provider_name)
        return await self._provider.extract(text)

    async def summarize(self, subject: str, context: str) -> str:
        return await self._provider.summarize(subject, context)


ai_service = AIService()
