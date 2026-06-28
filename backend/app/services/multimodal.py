"""Gemini multimodal extraction: image intelligence (#20) and audio/video
transcription (#21).

Uses Gemini's free-tier multimodal models to caption + OCR images and transcribe
audio, returning text that the existing extraction pipeline can turn into graph
objects. Requires ``AI_PROVIDER=gemini``; raises :class:`MultimodalUnavailable`
otherwise so callers can return a clean 503 (the deterministic path tests cover).
"""
from __future__ import annotations

from app.core.config import settings


class MultimodalUnavailable(RuntimeError):
    """Raised when no multimodal-capable provider is configured."""


def _require_gemini() -> None:
    if settings.AI_PROVIDER != "gemini" or not settings.GEMINI_API_KEY:
        raise MultimodalUnavailable(
            "Image/audio analysis requires AI_PROVIDER=gemini with GEMINI_API_KEY set."
        )


_IMAGE_PROMPT = (
    "You are an imagery-intelligence analyst. Describe this image, transcribe any "
    "visible text (OCR), and list notable people, organizations, locations, and "
    "objects. Be factual; do not speculate."
)
_AUDIO_PROMPT = (
    "Transcribe this audio verbatim, then list the people, organizations, and "
    "locations mentioned. Be factual; do not speculate."
)


async def _generate(data: bytes, mime_type: str, prompt: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = await client.aio.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=[types.Part.from_bytes(data=data, mime_type=mime_type), prompt],
        config=types.GenerateContentConfig(max_output_tokens=settings.AI_MAX_OUTPUT_TOKENS),
    )
    return (getattr(response, "text", None) or "").strip()


async def analyze_image(data: bytes, mime_type: str) -> str:
    """Caption + OCR + entity listing for an image (#20)."""
    _require_gemini()
    return await _generate(data, mime_type, _IMAGE_PROMPT)


async def transcribe_audio(data: bytes, mime_type: str) -> str:
    """Transcribe audio and surface mentioned entities (#21)."""
    _require_gemini()
    return await _generate(data, mime_type, _AUDIO_PROMPT)
