"""Per-entity risk scoring (#49).

A transparent weighted score in [0, 1] from features the platform already
computes: direct watchlist match, proximity to a sanctioned entity, contradicted
evidence, network centrality (degree), and unverified-AI provenance. Every score
ships with its factor breakdown and human-readable reasons — decision support,
not a black box.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.abac import user_can_access
from app.models.entity import Entity
from app.models.relationship import Relationship
from app.services import confidence, sanctions

_WEIGHTS = {
    "sanctions_hit": 0.40,
    "neighbor_sanctioned": 0.20,
    "contradiction": 0.15,
    "centrality": 0.15,
    "unverified": 0.10,
}


@dataclass(slots=True)
class RiskScore:
    entity_id: str
    name: str
    score: float
    band: str
    factors: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


def _band(score: float) -> str:
    return "high" if score >= 0.6 else "medium" if score >= 0.3 else "low"


async def score_entity(db: AsyncSession, entity: Entity) -> RiskScore:
    factors: dict[str, float] = {}
    reasons: list[str] = []

    hits = await sanctions.screen_entity(db, entity, threshold=0.9)
    factors["sanctions_hit"] = 1.0 if hits else 0.0
    if hits:
        reasons.append(f"Direct watchlist match: {hits[0].entry_name}")

    rels = list((await db.execute(
        select(Relationship).where(
            or_(Relationship.source_id == entity.id, Relationship.target_id == entity.id)
        )
    )).scalars().all())
    neighbor_ids = {r.target_id if r.source_id == entity.id else r.source_id for r in rels}
    factors["neighbor_sanctioned"] = 0.0
    if neighbor_ids:
        neighbors = list((await db.execute(
            select(Entity).where(Entity.id.in_(neighbor_ids))
        )).scalars().all())
        for nb in neighbors:
            if await sanctions.screen_entity(db, nb, threshold=0.9):
                factors["neighbor_sanctioned"] = 1.0
                reasons.append(f"Connected to sanctioned entity: {nb.name}")
                break

    conf = await confidence.summarize_entity(db, entity.id)
    factors["contradiction"] = 1.0 if conf.is_contradicted else 0.0
    if conf.is_contradicted:
        reasons.append("Carries contradicting verified evidence")

    factors["centrality"] = round(min(1.0, len(rels) / 10.0), 4)
    if len(rels) >= 8:
        reasons.append(f"Highly connected ({len(rels)} relationships)")

    factors["unverified"] = 1.0 if (entity.is_ai_generated and entity.confidence_score < 0.5) else 0.0

    score = round(min(1.0, sum(_WEIGHTS[k] * v for k, v in factors.items())), 4)
    if not reasons:
        reasons.append("No elevated risk indicators")
    return RiskScore(entity_id=str(entity.id), name=entity.name, score=score,
                     band=_band(score), factors=factors, reasons=reasons)


async def top_risky(
    db: AsyncSession, *, limit: int = 25, max_scan: int = 500, user=None
) -> list[RiskScore]:
    """Highest-risk entities. When ``user`` is given, only entities the user is
    cleared for are scanned/returned — the leaderboard must not surface the names
    of compartmented entities to an uncleared analyst."""
    entities = list((await db.execute(select(Entity).limit(max_scan))).scalars().all())
    if user is not None:
        entities = [
            e for e in entities
            if user_can_access(user, classification=e.classification, compartments=e.compartments)
        ]
    scored = [await score_entity(db, e) for e in entities]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:limit]


async def get_entity(db: AsyncSession, entity_id: uuid.UUID) -> Entity | None:
    return await db.get(Entity, entity_id)
