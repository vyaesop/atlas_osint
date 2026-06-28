"""Red-team verification (Task 12).

Drives every scenario in the adversarial corpus through the real detection
engines — confidence scoring (#2), Admiralty grading (#3), and the alert feed
(#28) — and asserts the platform is not fooled: disinformation and sock-puppet
floods stay low-confidence, genuine disputes are flagged, and well-sourced facts
score high.
"""
from __future__ import annotations

import pytest

from app.scripts.redteam_corpus import SCENARIOS, seed_scenario
from app.services import alerts, confidence


def _scenario(key: str):
    return next(s for s in SCENARIOS if s.key == key)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.key)
async def test_scenario_confidence_bounds(scenario, db_session):
    entity = await seed_scenario(db_session, scenario)
    await db_session.commit()

    result = await confidence.summarize_entity(db_session, entity.id)

    if scenario.expect_contradicted:
        assert result.is_contradicted, f"{scenario.key} should be flagged contradicted"
    if scenario.expect_max_score is not None:
        assert result.score <= scenario.expect_max_score, (
            f"{scenario.key}: score {result.score} exceeded cap "
            f"{scenario.expect_max_score} — possible confidence inflation"
        )
    if scenario.expect_min_score is not None:
        assert result.score >= scenario.expect_min_score, (
            f"{scenario.key}: score {result.score} below floor {scenario.expect_min_score}"
        )


async def test_sock_puppet_flood_does_not_beat_two_independent(db_session):
    """The 10-item flood must score no higher than 2 genuinely independent A1 sources."""
    flood = await seed_scenario(db_session, _scenario("sock_puppet_flood"))
    legit = await seed_scenario(db_session, _scenario("legitimate_corroboration"))
    await db_session.commit()

    flood_score = (await confidence.summarize_entity(db_session, flood.id)).score
    legit_score = (await confidence.summarize_entity(db_session, legit.id)).score
    assert flood_score < legit_score


async def test_disinformation_scores_below_legitimate(db_session):
    """Low-grade (E5) sources must not reach the confidence of A1 sources."""
    disinfo = await seed_scenario(db_session, _scenario("disinformation_low_grade"))
    legit = await seed_scenario(db_session, _scenario("legitimate_corroboration"))
    await db_session.commit()

    disinfo_score = (await confidence.summarize_entity(db_session, disinfo.id)).score
    legit_score = (await confidence.summarize_entity(db_session, legit.id)).score
    assert disinfo_score < legit_score


async def test_planted_contradiction_raises_alert(db_session):
    """A genuine dispute must surface in the contradiction alert feed (#28)."""
    entity = await seed_scenario(db_session, _scenario("planted_contradiction"))
    await db_session.commit()

    feed = await alerts.compute_alerts(db_session, kinds={"contradiction"})
    contradiction = [a for a in feed if a.entity_id == str(entity.id)]
    assert contradiction, "planted contradiction did not raise an alert"
    assert contradiction[0].kind == "contradiction"
    assert contradiction[0].severity == "high"


async def test_admiralty_grading_separates_quality(db_session):
    """A1 (completely reliable) must out-weigh E5 (unreliable/improbable) for one source each."""
    from app.models.enums import InfoCredibility, SourceReliability
    from app.services.source_grading import admiralty_weight

    a1 = admiralty_weight(SourceReliability.A, InfoCredibility.C1)
    e5 = admiralty_weight(SourceReliability.E, InfoCredibility.C5)
    assert a1 > 0.9
    assert e5 < 0.2
    assert a1 > e5
