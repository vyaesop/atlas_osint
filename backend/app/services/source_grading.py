"""Admiralty/NATO source-evaluation system (#3).

Two independent axes — *source reliability* (A–F) and *information credibility*
(1–6) — are each mapped to a [0, 1] weight, then combined into a single
effective-reliability weight via their geometric mean (so a high score requires
*both* a trustworthy source and credible content; one strong axis can't mask a
weak one). The "cannot be judged" grades (F / 6) map to a deliberately neutral
0.5 rather than 0, since they assert ignorance, not unreliability.

This weight feeds the confidence engine in place of a hand-entered
``reliability_score`` whenever both grades are present (see
``Evidence.effective_reliability``). Pure functions, no DB.
"""
from __future__ import annotations

import math

from app.models.enums import InfoCredibility, SourceReliability

_RELIABILITY_WEIGHT: dict[SourceReliability, float] = {
    SourceReliability.A: 1.0,
    SourceReliability.B: 0.8,
    SourceReliability.C: 0.6,
    SourceReliability.D: 0.4,
    SourceReliability.E: 0.1,
    SourceReliability.F: 0.5,
}

_CREDIBILITY_WEIGHT: dict[InfoCredibility, float] = {
    InfoCredibility.C1: 1.0,
    InfoCredibility.C2: 0.8,
    InfoCredibility.C3: 0.6,
    InfoCredibility.C4: 0.4,
    InfoCredibility.C5: 0.1,
    InfoCredibility.C6: 0.5,
}

RELIABILITY_LABELS: dict[SourceReliability, str] = {
    SourceReliability.A: "Completely reliable",
    SourceReliability.B: "Usually reliable",
    SourceReliability.C: "Fairly reliable",
    SourceReliability.D: "Not usually reliable",
    SourceReliability.E: "Unreliable",
    SourceReliability.F: "Reliability cannot be judged",
}

CREDIBILITY_LABELS: dict[InfoCredibility, str] = {
    InfoCredibility.C1: "Confirmed by other sources",
    InfoCredibility.C2: "Probably true",
    InfoCredibility.C3: "Possibly true",
    InfoCredibility.C4: "Doubtful",
    InfoCredibility.C5: "Improbable",
    InfoCredibility.C6: "Truth cannot be judged",
}


def admiralty_weight(reliability: SourceReliability, credibility: InfoCredibility) -> float:
    """Combine the two axes into a single [0, 1] reliability weight."""
    r = _RELIABILITY_WEIGHT[reliability]
    c = _CREDIBILITY_WEIGHT[credibility]
    return round(math.sqrt(r * c), 4)


def admiralty_code(reliability: SourceReliability, credibility: InfoCredibility) -> str:
    """The canonical two-character code, e.g. ``"B2"``."""
    return f"{reliability.value}{credibility.value}"
