"""Build a chronological timeline for an entity.

Combines three sources of dated facts:

* **attributes** — the entity's own dates (born, founded, published, event date)
* **relationships** — dated edges incident to the entity (start, and end as a
  separate item), e.g. career/membership changes
* **events** — dated Event entities the node is connected to

Supports filtering by relationship type and date range; comparison across two
entities is done client-side by fetching two timelines.
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity
from app.models.enums import EntityType, RelationshipType
from app.models.relationship import Relationship
from app.schemas.dashboard import TimelineItem, TimelineResponse

# entity property keys that carry a date → human label.
_ATTRIBUTE_DATES = {
    "birth_date": "Born",
    "founded_date": "Founded",
    "date": "Occurred",
    "publication_date": "Published",
}


def _parse_date(value: object) -> date | None:
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


async def build_timeline(
    db: AsyncSession,
    entity_id: uuid.UUID,
    *,
    relationship_types: list[RelationshipType] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> TimelineResponse | None:
    entity = await db.get(Entity, entity_id)
    if entity is None:
        return None

    items: list[TimelineItem] = []

    # 1) Attribute dates from the entity's own properties.
    for key, label in _ATTRIBUTE_DATES.items():
        d = _parse_date((entity.properties or {}).get(key))
        if d is not None:
            items.append(TimelineItem(date=d, kind="attribute", label=label,
                                      confidence=entity.confidence_score))

    # 2) Dated relationships incident to the entity.
    rels = list((await db.execute(
        select(Relationship).where(
            or_(Relationship.source_id == entity_id, Relationship.target_id == entity_id)
        )
    )).scalars().all())

    neighbor_ids = {
        nid for r in rels for nid in (r.source_id, r.target_id) if nid != entity_id
    }
    neighbors = {}
    if neighbor_ids:
        neighbors = {
            e.id: e for e in (await db.execute(
                select(Entity).where(Entity.id.in_(neighbor_ids))
            )).scalars().all()
        }

    for rel in rels:
        if relationship_types and rel.type not in relationship_types:
            continue
        other_id = rel.target_id if rel.source_id == entity_id else rel.source_id
        other = neighbors.get(other_id)
        other_name = other.name if other else str(other_id)

        if rel.start_date is not None:
            items.append(TimelineItem(
                date=rel.start_date, end_date=rel.end_date,
                kind="relationship",
                label=f"{rel.type.value.replace('_', ' ').title()} — {other_name}",
                relationship_type=rel.type, related_id=other_id,
                related_name=other_name, confidence=rel.confidence_score,
            ))
        if rel.end_date is not None:
            items.append(TimelineItem(
                date=rel.end_date, kind="relationship",
                label=f"End: {rel.type.value.replace('_', ' ').title()} — {other_name}",
                relationship_type=rel.type, related_id=other_id,
                related_name=other_name, confidence=rel.confidence_score,
            ))

        # Connected events carry their own date.
        if other is not None and other.type is EntityType.EVENT:
            ed = _parse_date((other.properties or {}).get("date"))
            if ed is not None:
                items.append(TimelineItem(
                    date=ed, kind="event", label=f"Event: {other.name}",
                    relationship_type=rel.type, related_id=other_id,
                    related_name=other.name, confidence=other.confidence_score,
                ))

    # 3) Filter by date window and sort.
    def in_window(d: date) -> bool:
        return (date_from is None or d >= date_from) and (date_to is None or d <= date_to)

    items = [i for i in items if in_window(i.date)]
    items.sort(key=lambda i: i.date)

    return TimelineResponse(entity_id=entity_id, entity_name=entity.name, items=items)
