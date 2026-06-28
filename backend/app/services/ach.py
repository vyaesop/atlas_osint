"""ACH scoring (#1) — pure functions over a rating matrix.

Implements Heuer's central discipline: rank hypotheses by *least weighted
inconsistency* rather than most support, and surface which items are most
*diagnostic* (i.e. actually discriminate between hypotheses). A piece of
evidence consistent with every hypothesis has no diagnostic value, however
compelling it reads.

Scoring
-------
For each hypothesis, over all rated items:
  * INCONSISTENT contributes ``2 × weight`` to its inconsistency score
  * NEUTRAL contributes ``0.5 × weight``
  * CONSISTENT / NA contribute ``0``
The most likely hypothesis is the one with the lowest inconsistency score
(ties broken by the most consistent ratings).

Item diagnosticity is ``weight × (1 − max_share)`` where ``max_share`` is the
largest fraction of rated hypotheses sharing a single consistency value — 0 when
every hypothesis agrees, rising as ratings split.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from app.models.enums import AchConsistency

_INCONSISTENCY_PENALTY = {
    AchConsistency.INCONSISTENT: 2.0,
    AchConsistency.NEUTRAL: 0.5,
    AchConsistency.CONSISTENT: 0.0,
    AchConsistency.NA: 0.0,
}


@dataclass(slots=True)
class HypothesisScore:
    hypothesis_id: str
    text: str
    inconsistency_score: float
    consistent_count: int
    inconsistent_count: int
    neutral_count: int
    na_count: int
    rank: int = 0


@dataclass(slots=True)
class ItemDiagnosticity:
    item_id: str
    text: str
    weight: float
    diagnosticity: float
    rated_hypotheses: int


@dataclass(slots=True)
class AchScoreResult:
    hypotheses: list[HypothesisScore] = field(default_factory=list)
    items: list[ItemDiagnosticity] = field(default_factory=list)
    most_likely_hypothesis_id: str | None = None


@dataclass(slots=True)
class _Item:
    id: str
    text: str
    weight: float


@dataclass(slots=True)
class _Hypothesis:
    id: str
    text: str


def score(
    hypotheses: list[_Hypothesis],
    items: list[_Item],
    ratings: dict[tuple[str, str], AchConsistency],
) -> AchScoreResult:
    """Score an ACH matrix.

    ``ratings`` is keyed by ``(hypothesis_id, item_id)``. Missing cells are
    treated as unrated and ignored.
    """
    if not hypotheses:
        return AchScoreResult()

    item_weight = {it.id: it.weight for it in items}

    hyp_scores: list[HypothesisScore] = []
    for h in hypotheses:
        counts: Counter[AchConsistency] = Counter()
        inconsistency = 0.0
        for it in items:
            rating = ratings.get((h.id, it.id))
            if rating is None:
                continue
            counts[rating] += 1
            inconsistency += _INCONSISTENCY_PENALTY[rating] * item_weight.get(it.id, 1.0)
        hyp_scores.append(
            HypothesisScore(
                hypothesis_id=h.id, text=h.text,
                inconsistency_score=round(inconsistency, 4),
                consistent_count=counts[AchConsistency.CONSISTENT],
                inconsistent_count=counts[AchConsistency.INCONSISTENT],
                neutral_count=counts[AchConsistency.NEUTRAL],
                na_count=counts[AchConsistency.NA],
            )
        )

    # Rank by least inconsistency, then most consistent support.
    hyp_scores.sort(key=lambda s: (s.inconsistency_score, -s.consistent_count))
    for i, s in enumerate(hyp_scores, start=1):
        s.rank = i

    # Diagnosticity per item.
    item_diags: list[ItemDiagnosticity] = []
    for it in items:
        ratings_for_item = [
            ratings[(h.id, it.id)] for h in hypotheses if (h.id, it.id) in ratings
        ]
        n = len(ratings_for_item)
        if n <= 1:
            diag = 0.0
        else:
            max_share = max(Counter(ratings_for_item).values()) / n
            diag = it.weight * (1.0 - max_share)
        item_diags.append(
            ItemDiagnosticity(
                item_id=it.id, text=it.text, weight=it.weight,
                diagnosticity=round(diag, 4), rated_hypotheses=n,
            )
        )
    item_diags.sort(key=lambda d: d.diagnosticity, reverse=True)

    most_likely = hyp_scores[0].hypothesis_id if hyp_scores else None
    return AchScoreResult(
        hypotheses=hyp_scores, items=item_diags, most_likely_hypothesis_id=most_likely
    )
