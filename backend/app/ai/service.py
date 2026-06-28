"""Selects and exposes the configured AI provider."""
from __future__ import annotations

import logging

from app.ai.heuristic import HeuristicExtractor
from app.ai.models import ExtractionResult
from app.ai.provider import ExtractionProvider
from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_provider() -> ExtractionProvider:
    """Construct the configured provider, degrading to the offline heuristic.

    Gemini is the intended default, but a missing key or SDK must never stop the
    app from booting — a solo researcher should get a working (if less capable)
    extractor with no setup. We therefore fall back to the heuristic extractor
    and log loudly rather than raising. ``build_assistant`` does the same for the
    NL→query path; keep the two in sync.
    """
    provider = settings.AI_PROVIDER
    try:
        if provider == "anthropic":
            from app.ai.anthropic_provider import AnthropicExtractor  # lazy import

            return AnthropicExtractor()
        if provider == "gemini":
            from app.ai.gemini_provider import GeminiExtractor  # lazy import

            return GeminiExtractor()
    except Exception as exc:  # missing key, SDK not installed, etc.
        logger.warning(
            "AI_PROVIDER=%s unavailable (%s); falling back to the offline "
            "heuristic extractor. Set the provider's API key to enable it.",
            provider, exc,
        )
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
