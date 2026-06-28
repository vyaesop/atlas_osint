"""Unit tests for the confidence engine (pure math, no DB)."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import EvidenceStance, VerificationStatus
from app.services.confidence import compute_confidence


@dataclass
class FakeEvidence:
    reliability_score: float
    stance: EvidenceStance
    verification_status: VerificationStatus = VerificationStatus.VERIFIED


def test_no_evidence_is_zero():
    assert compute_confidence([]).score == 0.0


def test_unverified_evidence_excluded_by_default():
    ev = [FakeEvidence(1.0, EvidenceStance.SUPPORTS, VerificationStatus.UNVERIFIED)]
    assert compute_confidence(ev).score == 0.0
    assert compute_confidence(ev, verified_only=False).score > 0.0


def test_more_corroboration_increases_confidence():
    one = compute_confidence([FakeEvidence(1.0, EvidenceStance.SUPPORTS)])
    three = compute_confidence([FakeEvidence(1.0, EvidenceStance.SUPPORTS)] * 3)
    assert three.score > one.score
    assert one.score < 1.0  # a single source is never certain


def test_contradiction_lowers_and_flags():
    res = compute_confidence([
        FakeEvidence(1.0, EvidenceStance.SUPPORTS),
        FakeEvidence(1.0, EvidenceStance.CONTRADICTS),
    ])
    assert res.is_contradicted
    assert res.score < compute_confidence([FakeEvidence(1.0, EvidenceStance.SUPPORTS)]).score


def test_neutral_is_counted_but_not_scored():
    res = compute_confidence([
        FakeEvidence(1.0, EvidenceStance.SUPPORTS),
        FakeEvidence(0.9, EvidenceStance.NEUTRAL),
    ])
    assert res.neutral_count == 1
    assert res.supporting_count == 1
    # neutral does not change the directional score vs. support-only
    assert res.score == compute_confidence([FakeEvidence(1.0, EvidenceStance.SUPPORTS)]).score


def test_score_bounded():
    res = compute_confidence([FakeEvidence(1.0, EvidenceStance.SUPPORTS)] * 50)
    assert 0.0 <= res.score <= 1.0
