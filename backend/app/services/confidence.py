"""Confidence scoring from a body of evidence.

The model has two intuitions:

* **Direction** — do sources agree? Supporting evidence pulls the score up,
  contradicting evidence pulls it down, weighted by each source's reliability.
* **Corroboration** — one source, however reliable, should never read as
  certain. Confidence saturates toward 1 as independent reliable sources
  accumulate.

Formally, with supporting mass ``S = Σ reliability`` over SUPPORTS evidence and
contradicting mass ``C`` over CONTRADICTS evidence (NEUTRAL is informational and
excluded from the math)::

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


def compute_confidence(
    evidence: Iterable[Evidence],
    *,
    verified_only: bool = True,
) -> ConfidenceResult:
    """Pure confidence computation over a collection of evidence items."""
    support_mass = contra_mass = 0.0
    supporting = contradicting = neutral = 0

    for ev in evidence:
        if verified_only and ev.verification_status is not VerificationStatus.VERIFIED:
            continue
        reliability = _clamp01(_reliability_of(ev))
        if ev.stance is EvidenceStance.SUPPORTS:
            support_mass += reliability
            supporting += 1
        elif ev.stance is EvidenceStance.CONTRADICTS:
            contra_mass += reliability
            contradicting += 1
        else:
            neutral += 1

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
