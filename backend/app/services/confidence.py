"""Confidence scoring from a body of evidence.

The model has two intuitions:

* **Direction** — do sources agree? Supporting evidence pulls the score up,
  contradicting evidence pulls it down, weighted by each source's reliability.
* **Corroboration** — one source, however reliable, should never read as
  certain. Confidence saturates toward 1 as *independent* reliable sources
  accumulate.

**Source independence (anti-disinformation).** Corroboration must come from
*independent* sources, not volume. Ten items that all cite the same blog (or a
ring of sock-puppets all pointing at one origin) are one voice, not ten — and an
adversary seeding coordinated inauthentic "support" must not be able to inflate
confidence by sheer count. So before scoring we collapse evidence sharing a
``source`` (or ``url``) to that source's single strongest item; only genuinely
distinct origins add mass. Items with no named source are treated as independent
(we can't prove they aren't), so manual/typical entry is unaffected.

Formally, with supporting mass ``S = Σ over distinct sources of their strongest
SUPPORTS reliability`` and contradicting mass ``C`` likewise over CONTRADICTS
(NEUTRAL is informational and excluded)::

    direction     = S / (S + C)              # in [0, 1], 0.5 when balanced
    corroboration = 1 - exp(-(S + C) / TAU)  # saturating, in [0, 1)
    confidence    = direction * corroboration

Only *verified* evidence contributes by default, so unverified/AI-extracted
claims can be attached without inflating confidence until a researcher signs off.
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity
from app.models.enums import EvidenceStance, VerificationStatus
from app.models.evidence import Evidence
from app.models.relationship import Relationship
from app.services import estimative

# Corroboration constant: ~63% of the way to 1.0 at one unit of reliability mass,
# ~86% at two units. Tuned so a single perfect source ≈ 0.63, not 1.0.
TAU = 1.0


@dataclass(frozen=True)
class ConfidenceResult:
    score: float
    support_mass: float
    contradiction_mass: float
    supporting_count: int
    contradicting_count: int
    neutral_count: int

    @property
    def is_contradicted(self) -> bool:
        """True when both supporting and contradicting evidence are present."""
        return self.supporting_count > 0 and self.contradicting_count > 0

    def as_dict(self) -> dict:
        """Flat dict including the derived ``is_contradicted`` flag and ICD 203
        estimative language (#2), ready to feed the :class:`ConfidenceSummary`
        response schema."""
        return {
            "score": self.score,
            "support_mass": self.support_mass,
            "contradiction_mass": self.contradiction_mass,
            "supporting_count": self.supporting_count,
            "contradicting_count": self.contradicting_count,
            "neutral_count": self.neutral_count,
            "is_contradicted": self.is_contradicted,
            **estimative.summarize(
                self.score, self.support_mass, self.contradiction_mass,
                is_contradicted=self.is_contradicted,
            ),
        }


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _reliability_of(ev: Evidence) -> float:
    """Effective reliability for an item — Admiralty grade when present, else the
    manual ``reliability_score``. Tolerant of lightweight test doubles that
    lack the ``effective_reliability`` property."""
    eff = getattr(ev, "effective_reliability", None)
    return eff if eff is not None else ev.reliability_score


def _source_key(ev: Evidence) -> object:
    """Identity an adversary would have to forge to count as a *new* source.

    Items naming the same ``source`` (or the same ``url``) are one voice. Items
    with no named source are treated as independent — we can't prove otherwise,
    and forcing analysts to label every source would be worse — so each gets a
    unique key.
    """
    src = getattr(ev, "source", None)
    if src and src.strip():
        return ("source", src.strip().lower())
    url = getattr(ev, "url", None)
    if url and url.strip():
        return ("url", url.strip().lower())
    return ("unique", id(ev))


def compute_confidence(
    evidence: Iterable[Evidence],
    *,
    verified_only: bool = True,
) -> ConfidenceResult:
    """Pure confidence computation over a collection of evidence items.

    Mass is accumulated per *distinct source* (strongest item per source), so
    coordinated/duplicate sources cannot inflate corroboration. Counts remain
    raw item counts (an analyst still sees "10 supporting", just not 10× the
    confidence).
    """
    # source_key -> strongest reliability seen for that source, per stance.
    support_sources: dict[object, float] = {}
    contra_sources: dict[object, float] = {}
    supporting = contradicting = neutral = 0

    for ev in evidence:
        if verified_only and ev.verification_status is not VerificationStatus.VERIFIED:
            continue
        reliability = _clamp01(_reliability_of(ev))
        if ev.stance is EvidenceStance.SUPPORTS:
            supporting += 1
            key = _source_key(ev)
            support_sources[key] = max(support_sources.get(key, 0.0), reliability)
        elif ev.stance is EvidenceStance.CONTRADICTS:
            contradicting += 1
            key = _source_key(ev)
            contra_sources[key] = max(contra_sources.get(key, 0.0), reliability)
        else:
            neutral += 1

    support_mass = sum(support_sources.values())
    contra_mass = sum(contra_sources.values())
    total_mass = support_mass + contra_mass
    if total_mass <= 0:
        score = 0.0
    else:
        direction = support_mass / total_mass
        corroboration = 1.0 - math.exp(-total_mass / TAU)
        score = direction * corroboration

    return ConfidenceResult(
        score=round(_clamp01(score), 4),
        support_mass=round(support_mass, 4),
        contradiction_mass=round(contra_mass, 4),
        supporting_count=supporting,
        contradicting_count=contradicting,
        neutral_count=neutral,
    )


@dataclass(frozen=True)
class EvidenceContribution:
    """One evidence item's role in a confidence score — the provenance of a number."""

    evidence_id: str
    title: str
    source: str | None
    url: str | None
    stance: str
    reliability: float   # effective reliability weight used by the engine
    admiralty_code: str | None
    verified: bool
    counted: bool        # did this item add mass to the score?
    reason: str          # why it counted, or why it did not

    def as_dict(self) -> dict:
        return {
            "evidence_id": self.evidence_id, "title": self.title,
            "source": self.source, "url": self.url, "stance": self.stance,
            "reliability": round(self.reliability, 4),
            "admiralty_code": self.admiralty_code, "verified": self.verified,
            "counted": self.counted, "reason": self.reason,
        }


@dataclass(frozen=True)
class ConfidenceExplanation:
    result: ConfidenceResult
    contributions: list[EvidenceContribution]

    def as_dict(self) -> dict:
        return {
            **self.result.as_dict(),
            "contributions": [c.as_dict() for c in self.contributions],
        }


def explain(evidence: Iterable[Evidence]) -> ConfidenceExplanation:
    """Compute confidence *and* the per-evidence provenance behind every number.

    Mirrors :func:`compute_confidence` exactly, additionally reporting, for each
    item, whether it counted toward the score and why not when it didn't
    (unverified, neutral, or collapsed as a duplicate of a stronger same-source
    item). This is what makes a confidence number one-click traceable to source.
    """
    items = list(evidence)
    result = compute_confidence(items)

    # Re-derive the winning item per (stance, source) group to mark duplicates.
    best_per_group: dict[object, float] = {}
    for ev in items:
        if ev.verification_status is not VerificationStatus.VERIFIED:
            continue
        if ev.stance not in (EvidenceStance.SUPPORTS, EvidenceStance.CONTRADICTS):
            continue
        key = (ev.stance, _source_key(ev))
        rel = _clamp01(_reliability_of(ev))
        best_per_group[key] = max(best_per_group.get(key, -1.0), rel)

    used_group: set[object] = set()
    contributions: list[EvidenceContribution] = []
    for ev in items:
        verified = ev.verification_status is VerificationStatus.VERIFIED
        rel = _clamp01(_reliability_of(ev))
        code = None
        if getattr(ev, "source_reliability", None) and getattr(ev, "info_credibility", None):
            code = f"{ev.source_reliability.value}{ev.info_credibility.value}"

        counted, reason = False, ""
        if not verified:
            reason = "unverified — does not affect confidence until reviewed"
        elif ev.stance is EvidenceStance.NEUTRAL:
            reason = "neutral — informational only"
        else:
            key = (ev.stance, _source_key(ev))
            if key not in used_group and rel >= best_per_group.get(key, 0.0):
                counted, reason = True, "counted as this source's contribution"
                used_group.add(key)
            else:
                counted = False
                reason = "duplicate source — collapsed into the strongest item from this source"

        contributions.append(EvidenceContribution(
            evidence_id=str(ev.id), title=ev.title, source=ev.source,
            url=getattr(ev, "url", None), stance=ev.stance.value, reliability=rel,
            admiralty_code=code, verified=verified, counted=counted, reason=reason,
        ))
    return ConfidenceExplanation(result=result, contributions=contributions)


async def explain_entity(db: AsyncSession, entity_id: uuid.UUID) -> ConfidenceExplanation:
    """Confidence breakdown for an entity, with full per-evidence provenance."""
    return explain(await _evidence_for_entity(db, entity_id))


async def _evidence_for_entity(db: AsyncSession, entity_id: uuid.UUID) -> list[Evidence]:
    res = await db.execute(select(Evidence).where(Evidence.entity_id == entity_id))
    return list(res.scalars().all())


async def _evidence_for_relationship(
    db: AsyncSession, relationship_id: uuid.UUID
) -> list[Evidence]:
    res = await db.execute(
        select(Evidence).where(Evidence.relationship_id == relationship_id)
    )
    return list(res.scalars().all())


async def summarize_entity(db: AsyncSession, entity_id: uuid.UUID) -> ConfidenceResult:
    """Compute (without persisting) the confidence breakdown for an entity."""
    return compute_confidence(await _evidence_for_entity(db, entity_id))


async def summarize_relationship(
    db: AsyncSession, relationship_id: uuid.UUID
) -> ConfidenceResult:
    return compute_confidence(await _evidence_for_relationship(db, relationship_id))


async def recompute_entity_confidence(
    db: AsyncSession, entity_id: uuid.UUID
) -> ConfidenceResult | None:
    """Recompute and persist an entity's confidence from its evidence.

    Returns the result, or ``None`` if the entity no longer exists. The caller
    owns the transaction (this only flushes).
    """
    entity = await db.get(Entity, entity_id)
    if entity is None:
        return None
    result = compute_confidence(await _evidence_for_entity(db, entity_id))
    entity.confidence_score = result.score
    await db.flush()
    return result


async def recompute_relationship_confidence(
    db: AsyncSession, relationship_id: uuid.UUID
) -> ConfidenceResult | None:
    rel = await db.get(Relationship, relationship_id)
    if rel is None:
        return None
    evidence = await _evidence_for_relationship(db, relationship_id)
    result = compute_confidence(evidence)
    rel.confidence_score = result.score
    rel.source_count = len(evidence)
    await db.flush()
    return result
