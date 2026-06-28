"""Synthetic-media / deepfake risk flag (#30).

A dependency-free heuristic that scores media for synthetic-origin risk from
metadata and text signals: known generator signatures (Stable Diffusion,
Midjourney, DALL·E, Firefly, GANs…), explicit AI-generation tags, and missing
provenance (no EXIF / no C2PA content credentials). It is a triage flag, not a
forensic verdict; a Gemini-vision pass (#20) can corroborate at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field

_GENERATOR_SIGNATURES = [
    "stable diffusion", "stablediffusion", "midjourney", "dall-e", "dalle",
    "dall·e", "adobe firefly", "firefly", "gan", "generative adversarial",
    "ai generated", "ai-generated", "synthesized", "deepfake", "faceswap",
    "this person does not exist", "runway", "sora", "flux.1", "comfyui",
    "automatic1111", "leonardo.ai",
]


@dataclass(slots=True)
class MediaRisk:
    risk: str               # high | medium | low
    score: float            # 0..1
    reasons: list[str] = field(default_factory=list)


def assess(
    *, filename: str | None = None, software: str | None = None,
    metadata: dict | None = None, text: str | None = None,
) -> MediaRisk:
    haystack_parts = [filename or "", software or "", text or ""]
    if metadata:
        haystack_parts.append(" ".join(f"{k} {v}" for k, v in metadata.items()))
    haystack = " ".join(haystack_parts).lower()

    score = 0.0
    reasons: list[str] = []

    matched = sorted({sig for sig in _GENERATOR_SIGNATURES if sig in haystack})
    if matched:
        score += 0.7
        reasons.append("Generator signature(s): " + ", ".join(matched))

    # Provenance signals (only meaningful when some metadata was supplied).
    if metadata is not None:
        keys = {k.lower() for k in metadata}
        if not keys & {"make", "model", "datetimeoriginal", "gpsinfo", "exif", "lensmodel"}:
            score += 0.2
            reasons.append("No camera EXIF (make/model/capture time) present.")
        if not keys & {"c2pa", "contentcredentials", "content_credentials"}:
            score += 0.1
            reasons.append("No C2PA content credentials.")

    score = min(1.0, round(score, 3))
    risk = "high" if score >= 0.7 else "medium" if score >= 0.3 else "low"
    if not reasons:
        reasons.append("No synthetic-media indicators detected.")
    return MediaRisk(risk=risk, score=score, reasons=reasons)
