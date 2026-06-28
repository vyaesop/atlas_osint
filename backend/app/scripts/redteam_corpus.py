"""Adversarial red-team corpus (Task 11).

A library of deliberately *hard* evidence scenarios an analyst-grade platform
must handle without being fooled. The failure mode that destroys an intelligence
tool's credibility is **confidently wrong** — laundering disinformation,
sock-puppet floods, or single-source rumour into high confidence. This corpus
exists to prove Atlas does not.

Each :class:`RedTeamScenario` bundles an entity, a set of evidence items (with
stance, Admiralty grade or raw reliability, source, and verification state), and
the *expected* behaviour of the detection engines. It is both:

* a **test oracle** (see ``tests/test_redteam.py``), and
* a runnable **seeder** (``python -m app.scripts.redteam_corpus``) so an operator
  can drop the corpus into a live instance and watch the alert feed / confidence
  scores react.

Add scenarios here as new attacks are imagined; the test will hold the engines
to them.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.models.entity import Entity
from app.models.enums import (
    EntityType,
    EvidenceStance,
    InfoCredibility,
    SourceReliability,
    VerificationStatus,
)
from app.models.evidence import Evidence


@dataclass(slots=True)
class EvidenceSpec:
    stance: EvidenceStance
    source: str | None = None
    # Either an Admiralty grade (preferred) ...
    reliability: SourceReliability | None = None
    credibility: InfoCredibility | None = None
    # ... or a raw [0,1] reliability score.
    reliability_score: float = 0.0
    verified: bool = True

    def build(self, entity_id) -> Evidence:
        return Evidence(
            title=f"{self.source or 'unsourced'} ({self.stance.value})",
            source=self.source,
            stance=self.stance,
            reliability_score=self.reliability_score,
            source_reliability=self.reliability,
            info_credibility=self.credibility,
            verification_status=(
                VerificationStatus.VERIFIED if self.verified
                else VerificationStatus.UNVERIFIED
            ),
            entity_id=entity_id,
        )


@dataclass(slots=True)
class RedTeamScenario:
    key: str
    description: str
    attack: str  # what an adversary is attempting
    evidence: list[EvidenceSpec]
    # Expectations the detection engines must satisfy.
    expect_contradicted: bool = False
    expect_alert_kind: str | None = None  # e.g. "contradiction"
    expect_max_score: float | None = None  # confidence must stay at/below this
    expect_min_score: float | None = None  # confidence must reach at least this
    entity_type: EntityType = EntityType.PERSON
    entity_name: str = ""


A = SourceReliability.A
E = SourceReliability.E
C1 = InfoCredibility.C1
C5 = InfoCredibility.C5


SCENARIOS: list[RedTeamScenario] = [
    RedTeamScenario(
        key="sock_puppet_flood",
        entity_name="Sockpuppet Target",
        description="Ten 'supporting' items all originate from one blog.",
        attack="Coordinated inauthentic amplification — inflate confidence by volume.",
        evidence=[
            EvidenceSpec(EvidenceStance.SUPPORTS, source="the-one-blog.example",
                         reliability=A, credibility=C1)
            for _ in range(10)
        ],
        # One real voice, however loud, must not read as near-certain.
        expect_max_score=0.7,
    ),
    RedTeamScenario(
        key="disinformation_low_grade",
        entity_name="Disinfo Subject",
        description="Several supporting items, all from unreliable/improbable sources (E5).",
        attack="Launder a false claim via many low-quality sources.",
        evidence=[
            EvidenceSpec(EvidenceStance.SUPPORTS, source=f"rumor-site-{i}.example",
                         reliability=E, credibility=C5)
            for i in range(4)
        ],
        # Low Admiralty weight must keep confidence weak even with several sources.
        expect_max_score=0.5,
    ),
    RedTeamScenario(
        key="planted_contradiction",
        entity_name="Contested Claim",
        description="Credible support AND credible contradiction from distinct sources.",
        attack="Genuine dispute the tool must surface rather than silently average away.",
        evidence=[
            EvidenceSpec(EvidenceStance.SUPPORTS, source="reuters.example", reliability=A, credibility=C1),
            EvidenceSpec(EvidenceStance.SUPPORTS, source="apnews.example", reliability=A, credibility=C1),
            EvidenceSpec(EvidenceStance.CONTRADICTS, source="court-record.example", reliability=A, credibility=C1),
        ],
        expect_contradicted=True,
        expect_alert_kind="contradiction",
    ),
    RedTeamScenario(
        key="unverified_padding",
        entity_name="Unverified Padding",
        description="One weak verified item plus a pile of unverified 'support'.",
        attack="Pad the record with unverified claims hoping they bump confidence.",
        evidence=(
            [EvidenceSpec(EvidenceStance.SUPPORTS, source="single.example",
                          reliability=SourceReliability.C, credibility=InfoCredibility.C3)]
            + [EvidenceSpec(EvidenceStance.SUPPORTS, source=f"unverified-{i}.example",
                            reliability=A, credibility=C1, verified=False)
               for i in range(6)]
        ),
        # Unverified items contribute nothing; score reflects the one weak source.
        expect_max_score=0.6,
    ),
    RedTeamScenario(
        key="legitimate_corroboration",
        entity_name="Well-Sourced Fact",
        description="Control: three independent A1 sources, no contradiction.",
        attack="(none) — a true, well-corroborated fact must score high.",
        evidence=[
            EvidenceSpec(EvidenceStance.SUPPORTS, source="reuters.example", reliability=A, credibility=C1),
            EvidenceSpec(EvidenceStance.SUPPORTS, source="apnews.example", reliability=A, credibility=C1),
            EvidenceSpec(EvidenceStance.SUPPORTS, source="bbc.example", reliability=A, credibility=C1),
        ],
        expect_min_score=0.9,
    ),
]


async def seed_scenario(db, scenario: RedTeamScenario) -> Entity:
    """Create the entity + its evidence for one scenario. Caller commits."""
    entity = Entity(type=scenario.entity_type, name=scenario.entity_name or scenario.key)
    db.add(entity)
    await db.flush()
    for spec in scenario.evidence:
        db.add(spec.build(entity.id))
    await db.flush()
    return entity


async def seed_all(db) -> list[Entity]:
    entities = [await seed_scenario(db, s) for s in SCENARIOS]
    await db.commit()
    return entities


async def _main() -> None:
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        entities = await seed_all(db)
        print(f"Seeded {len(entities)} red-team scenarios:")
        for s, e in zip(SCENARIOS, entities):
            print(f"  - {s.key}: {e.name} ({len(s.evidence)} evidence)")


if __name__ == "__main__":
    asyncio.run(_main())
