"""Geospatial & spatiotemporal analysis (#7 map data, #8 pattern-of-life,
#9 co-location / co-travel).

Coordinates live in an entity's JSONB ``properties`` — this module reads them
flexibly (``latitude``/``longitude``, ``lat``/``lon``/``lng``, or a
``coordinates: [lat, lon]`` pair). Actors (people, orgs, …) are placed in space
either directly (own coords) or by following ``LOCATED_IN`` edges and event
participation, which also reconstructs movement over time.

The coordinate parsing and haversine helpers are pure and unit-tested; the
placement/visit functions read a snapshot from PostgreSQL (the source of truth).
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity
from app.models.enums import EntityType, RelationshipType
from app.models.relationship import Relationship

_LAT_KEYS = ("latitude", "lat")
_LON_KEYS = ("longitude", "lon", "lng", "long")

# Relationship types that place an actor at an event.
_PARTICIPATION = {RelationshipType.ATTENDED, RelationshipType.PARTICIPATED_IN}

# Actor entity types we track through space (everything but place/event/document).
_ACTOR_TYPES = {
    EntityType.PERSON, EntityType.ORGANIZATION, EntityType.COMPANY,
    EntityType.GOVERNMENT_AGENCY, EntityType.ASSET,
}


@dataclass(slots=True)
class Coords:
    lat: float
    lon: float


def _first(props: dict, keys: tuple[str, ...]) -> object | None:
    for k in keys:
        if k in props and props[k] is not None:
            return props[k]
    return None


def extract_coords(properties: dict | None) -> Coords | None:
    """Pull a valid lat/lon out of an entity's properties, or ``None``."""
    if not properties:
        return None
    pair = properties.get("coordinates")
    if isinstance(pair, (list, tuple)) and len(pair) == 2:
        c = _coerce(pair[0], pair[1])
        if c is not None:
            return c
    return _coerce(_first(properties, _LAT_KEYS), _first(properties, _LON_KEYS))


def _coerce(lat: object, lon: object) -> Coords | None:
    if lat is None or lon is None:
        return None
    try:
        la, lo = float(lat), float(lon)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if -90.0 <= la <= 90.0 and -180.0 <= lo <= 180.0:
        return Coords(round(la, 6), round(lo, 6))
    return None


def haversine_km(a: Coords, b: Coords) -> float:
    """Great-circle distance between two points in kilometres."""
    r = 6371.0
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dphi = math.radians(b.lat - a.lat)
    dlmb = math.radians(b.lon - a.lon)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return round(2 * r * math.asin(min(1.0, math.sqrt(h))), 3)


# --------------------------------------------------------------------------- #
# Internal: visit reconstruction (shared by pattern-of-life and co-location)
# --------------------------------------------------------------------------- #

@dataclass(slots=True)
class Visit:
    actor_id: str
    actor_name: str
    date: date | None
    location_id: str
    location_name: str
    coords: Coords
    source: str        # "located_in" | "event"
    label: str


async def _snapshot(db: AsyncSession):
    entities = {
        e.id: e for e in (await db.execute(select(Entity))).scalars().all()
    }
    rels = list((await db.execute(select(Relationship))).scalars().all())
    return entities, rels


def _build_visits(entities: dict, rels: list, actor_ids: set | None) -> dict[str, list[Visit]]:
    """Reconstruct each actor's located visits from LOCATED_IN edges and events.

    ``actor_ids`` (UUIDs) restricts the actors processed; ``None`` means all.
    """
    coords_of = {eid: extract_coords(e.properties) for eid, e in entities.items()}

    # event_id -> (location_id, coords) for events anchored to a place.
    event_place: dict[uuid.UUID, tuple[uuid.UUID, Coords]] = {}
    for r in rels:
        if r.type is RelationshipType.LOCATED_IN:
            src = entities.get(r.source_id)
            loc_coords = coords_of.get(r.target_id)
            if src is not None and src.type is EntityType.EVENT and loc_coords is not None:
                event_place[r.source_id] = (r.target_id, loc_coords)

    visits: dict[str, list[Visit]] = {}

    def _add(actor: Entity, d: date | None, loc_id, coords: Coords, source: str, label: str):
        visits.setdefault(str(actor.id), []).append(
            Visit(
                actor_id=str(actor.id), actor_name=actor.name, date=d,
                location_id=str(loc_id), location_name=entities[loc_id].name,
                coords=coords, source=source, label=label,
            )
        )

    for r in rels:
        actor = entities.get(r.source_id)
        if actor is None or actor.type not in _ACTOR_TYPES:
            continue
        if actor_ids is not None and actor.id not in actor_ids:
            continue

        # Direct placement: actor LOCATED_IN place.
        if r.type is RelationshipType.LOCATED_IN:
            c = coords_of.get(r.target_id)
            if c is not None:
                _add(actor, r.start_date, r.target_id, c, "located_in",
                     f"Located in {entities[r.target_id].name}")

        # Placement via an event the actor took part in.
        elif r.type in _PARTICIPATION and r.target_id in event_place:
            loc_id, c = event_place[r.target_id]
            event = entities[r.target_id]
            d = _parse_date((event.properties or {}).get("date")) or r.start_date
            _add(actor, d, loc_id, c, "event",
                 f"{event.name} @ {entities[loc_id].name}")

    for vlist in visits.values():
        vlist.sort(key=lambda v: (v.date is None, v.date or date.min))
    return visits


def _parse_date(value: object) -> date | None:
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


# --------------------------------------------------------------------------- #
# #7 — Map features
# --------------------------------------------------------------------------- #

@dataclass(slots=True)
class GeoFeature:
    id: str
    name: str
    type: str
    lat: float
    lon: float
    confidence: float
    placed_via: str          # "self" | "located_in"
    location_name: str | None


async def map_features(
    db: AsyncSession, *, types: list[EntityType] | None = None
) -> list[GeoFeature]:
    """Every entity that can be placed on a map — directly (own coords) or via a
    LOCATED_IN edge to a place with coords."""
    entities, rels = await _snapshot(db)
    coords_of = {eid: extract_coords(e.properties) for eid, e in entities.items()}
    type_filter = set(types) if types else None

    # actor -> first place with coords it's LOCATED_IN (for entities lacking own coords).
    placed: dict[uuid.UUID, tuple[uuid.UUID, Coords]] = {}
    for r in rels:
        if r.type is RelationshipType.LOCATED_IN and r.source_id not in placed:
            c = coords_of.get(r.target_id)
            if c is not None:
                placed[r.source_id] = (r.target_id, c)

    features: list[GeoFeature] = []
    for eid, e in entities.items():
        if type_filter and e.type not in type_filter:
            continue
        own = coords_of.get(eid)
        if own is not None:
            features.append(GeoFeature(
                id=str(eid), name=e.name, type=e.type.value, lat=own.lat, lon=own.lon,
                confidence=e.confidence_score, placed_via="self", location_name=None,
            ))
        elif eid in placed:
            loc_id, c = placed[eid]
            features.append(GeoFeature(
                id=str(eid), name=e.name, type=e.type.value, lat=c.lat, lon=c.lon,
                confidence=e.confidence_score, placed_via="located_in",
                location_name=entities[loc_id].name,
            ))
    return features


# --------------------------------------------------------------------------- #
# #8 — Pattern of life
# --------------------------------------------------------------------------- #

@dataclass(slots=True)
class PatternOfLife:
    entity_id: str
    entity_name: str
    visits: list[Visit]
    place_count: int
    total_distance_km: float


async def pattern_of_life(db: AsyncSession, entity_id: uuid.UUID) -> PatternOfLife | None:
    entity = await db.get(Entity, entity_id)
    if entity is None:
        return None
    entities, rels = await _snapshot(db)
    visits = _build_visits(entities, rels, {entity_id}).get(str(entity_id), [])

    distance = 0.0
    dated = [v for v in visits if v.date is not None]
    for prev, curr in zip(dated, dated[1:]):
        distance += haversine_km(prev.coords, curr.coords)

    return PatternOfLife(
        entity_id=str(entity_id), entity_name=entity.name, visits=visits,
        place_count=len({v.location_id for v in visits}),
        total_distance_km=round(distance, 3),
    )


# --------------------------------------------------------------------------- #
# #9 — Co-location / co-travel
# --------------------------------------------------------------------------- #

@dataclass(slots=True)
class ColocationPair:
    a_id: str
    a_name: str
    b_id: str
    b_name: str
    location_id: str
    location_name: str
    shared_visits: int
    temporally_overlapping: bool
    already_connected: bool
    suggested_type: str
    score: float


async def colocation(
    db: AsyncSession, *, window_days: int = 7, limit: int = 50
) -> list[ColocationPair]:
    """Find actor pairs seen at the same place (within ``window_days`` when both
    visits are dated) and propose ASSOCIATED_WITH edges for those not already
    directly connected."""
    entities, rels = await _snapshot(db)
    visits_by_actor = _build_visits(entities, rels, None)

    connected: set[frozenset[str]] = {
        frozenset((str(r.source_id), str(r.target_id))) for r in rels
    }

    # location_id -> list[Visit]
    by_place: dict[str, list[Visit]] = {}
    for vlist in visits_by_actor.values():
        for v in vlist:
            by_place.setdefault(v.location_id, []).append(v)

    # Aggregate per (actor-pair, location).
    agg: dict[tuple[str, str, str], dict] = {}
    for loc_id, vlist in by_place.items():
        for i, v1 in enumerate(vlist):
            for v2 in vlist[i + 1:]:
                if v1.actor_id == v2.actor_id:
                    continue
                a, b = sorted((v1.actor_id, v2.actor_id))
                overlap = (
                    v1.date is not None and v2.date is not None
                    and abs((v1.date - v2.date).days) <= window_days
                )
                key = (a, b, loc_id)
                rec = agg.setdefault(key, {"count": 0, "overlap": False,
                                           "a_name": "", "b_name": "", "loc_name": v1.location_name})
                rec["count"] += 1
                rec["overlap"] = rec["overlap"] or overlap
                names = {v1.actor_id: v1.actor_name, v2.actor_id: v2.actor_name}
                rec["a_name"], rec["b_name"] = names[a], names[b]

    pairs: list[ColocationPair] = []
    for (a, b, loc_id), rec in agg.items():
        already = frozenset((a, b)) in connected
        # Temporal overlap and repeat visits both strengthen the inference.
        score = rec["count"] * (2.0 if rec["overlap"] else 1.0)
        pairs.append(ColocationPair(
            a_id=a, a_name=rec["a_name"], b_id=b, b_name=rec["b_name"],
            location_id=loc_id, location_name=rec["loc_name"],
            shared_visits=rec["count"], temporally_overlapping=rec["overlap"],
            already_connected=already, suggested_type="ASSOCIATED_WITH",
            score=round(score, 3),
        ))

    pairs.sort(key=lambda p: (p.already_connected, -p.score))
    return pairs[:limit]
