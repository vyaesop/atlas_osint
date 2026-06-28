"""Facet aggregations for histogram / brush filtering (#46).

Returns counts of entities bucketed by type, classification, confidence band,
AI-provenance, and creation month — the data a frontend brush-filter panel needs.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.abac import user_can_access
from app.models.entity import Entity
from app.models.enums import EntityType


@dataclass(slots=True)
class FacetBucket:
    value: str
    count: int


@dataclass(slots=True)
class Facets:
    total: int
    by_type: list[FacetBucket] = field(default_factory=list)
    by_classification: list[FacetBucket] = field(default_factory=list)
    by_confidence: list[FacetBucket] = field(default_factory=list)
    by_provenance: list[FacetBucket] = field(default_factory=list)
    by_month: list[FacetBucket] = field(default_factory=list)


def _confidence_band(score: float) -> str:
    if score < 0.2:
        return "0.0–0.2"
    if score < 0.4:
        return "0.2–0.4"
    if score < 0.6:
        return "0.4–0.6"
    if score < 0.8:
        return "0.6–0.8"
    return "0.8–1.0"


def _buckets(counter: Counter, *, sort_by_value: bool = False) -> list[FacetBucket]:
    items = sorted(counter.items()) if sort_by_value else counter.most_common()
    return [FacetBucket(value=str(k), count=v) for k, v in items]


async def compute_facets(
    db: AsyncSession, *, type_: EntityType | None = None, user=None
) -> Facets:
    """Faceted entity counts. When ``user`` is given, only entities the user is
    cleared for are counted — otherwise the histogram itself would leak the
    *existence and volume* of compartmented/classified data to a lower-clearance
    analyst (e.g. "3 TOP_SECRET entities"). ABAC must hold at the aggregate, not
    only at the row, level."""
    stmt = select(Entity)
    if type_ is not None:
        stmt = stmt.where(Entity.type == type_)
    entities = list((await db.execute(stmt)).scalars().all())
    if user is not None:
        entities = [
            e for e in entities
            if user_can_access(user, classification=e.classification, compartments=e.compartments)
        ]

    by_type, by_class, by_conf, by_prov, by_month = (Counter() for _ in range(5))
    for e in entities:
        by_type[e.type.value] += 1
        by_class[e.classification.value] += 1
        by_conf[_confidence_band(e.confidence_score)] += 1
        by_prov["ai_generated" if e.is_ai_generated else "analyst_entered"] += 1
        if e.created_at:
            by_month[e.created_at.strftime("%Y-%m")] += 1

    return Facets(
        total=len(entities),
        by_type=_buckets(by_type),
        by_classification=_buckets(by_class),
        by_confidence=_buckets(by_conf, sort_by_value=True),
        by_provenance=_buckets(by_prov),
        by_month=_buckets(by_month, sort_by_value=True),
    )
