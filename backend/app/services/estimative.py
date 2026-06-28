"""ICD 203 estimative language (#2).

Maps a numeric confidence score to the Intelligence Community's standardized
"words of estimative probability" (ICD 203), and separately expresses
*analytic confidence* — how much the underlying sourcing supports the judgement
— as low / moderate / high. Probability and analytic confidence are deliberately
distinct axes in ICD 203: a judgement can be "likely" with only "low"
confidence. Pure functions, no DB.
"""
from __future__ import annotations

# (lower_inclusive, upper_exclusive, term, human-readable band)
_BANDS: list[tuple[float, float, str, str]] = [
    (0.00, 0.05, "almost no chance", "01–05%"),
    (0.05, 0.20, "very unlikely", "05–20%"),
    (0.20, 0.45, "unlikely", "20–45%"),
    (0.45, 0.55, "roughly even chance", "45–55%"),
    (0.55, 0.80, "likely", "55–80%"),
    (0.80, 0.95, "very likely", "80–95%"),
    (0.95, 1.01, "almost certain", "95–99%"),
]


def estimative_label(score: float) -> tuple[str, str]:
    """Return ``(term, band)`` for a confidence score in [0, 1]."""
    s = max(0.0, min(1.0, score))
    for lo, hi, term, band in _BANDS:
        if lo <= s < hi:
            return term, band
    return _BANDS[-1][2], _BANDS[-1][3]  # pragma: no cover - score == 1.0 edge


def analytic_confidence(
    support_mass: float, contradiction_mass: float, *, is_contradicted: bool
) -> str:
    """Low / moderate / high, from corroborating reliability mass.

    Contradiction caps confidence at "moderate": a disputed judgement is never
    high-confidence regardless of how much supporting mass exists.
    """
    total = support_mass + contradiction_mass
    if total >= 2.5 and not is_contradicted:
        return "high"
    if total >= 1.0:
        return "moderate"
    return "low"


def summarize(
    score: float, support_mass: float, contradiction_mass: float, *, is_contradicted: bool
) -> dict[str, str]:
    """Flat dict of the estimative fields, ready to merge into a summary."""
    term, band = estimative_label(score)
    return {
        "estimative_label": term,
        "probability_band": band,
        "analytic_confidence": analytic_confidence(
            support_mass, contradiction_mass, is_contradicted=is_contradicted
        ),
    }
