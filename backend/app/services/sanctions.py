"""Sanctions / watchlist screening (#18).

Screens graph entities against loaded :class:`WatchlistEntry` records using the
same name-similarity logic as entity resolution (normalized exact, alias
overlap, token-Jaccard, Levenshtein). Pure matching helper + DB-driven scans.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity
from app.models.watchlist import WatchlistEntry
from app.services.entity_resolution import similarity


@dataclass(slots=True)
class ScreeningHit:
    entity_id: str
    entity_name: str
    entry_id: str
    entry_name: str
    program: str | None
    source: str | None
    score: float
    reason: str


def best_match(
    entity_name: str, entity_aliases: list[str], entry: WatchlistEntry
) -> tuple[float, str]:
    return similarity(entity_name, entity_aliases, entry.name, list(entry.aliases or []))


def _hit(entity: Entity, entry: WatchlistEntry, score: float, reason: str) -> ScreeningHit:
    return ScreeningHit(
        entity_id=str(entity.id), entity_name=entity.name,
        entry_id=str(entry.id), entry_name=entry.name,
        program=entry.program, source=entry.source, score=score, reason=reason,
    )


async def screen_entity(
    db: AsyncSession, entity: Entity, *, threshold: float = 0.85
) -> list[ScreeningHit]:
    entries = list((await db.execute(select(WatchlistEntry))).scalars().all())
    hits: list[ScreeningHit] = []
    for entry in entries:
        score, reason = best_match(entity.name, list(entity.aliases or []), entry)
        if score >= threshold:
            hits.append(_hit(entity, entry, round(score, 4), reason))
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits


async def scan_all(
    db: AsyncSession, *, threshold: float = 0.85, limit: int = 200, max_scan: int = 5000
) -> list[ScreeningHit]:
    entries = list((await db.execute(select(WatchlistEntry))).scalars().all())
    if not entries:
        return []
    entities = list((await db.execute(select(Entity).limit(max_scan))).scalars().all())
    hits: list[ScreeningHit] = []
    for entity in entities:
        aliases = list(entity.aliases or [])
        for entry in entries:
            score, reason = best_match(entity.name, aliases, entry)
            if score >= threshold:
                hits.append(_hit(entity, entry, round(score, 4), reason))
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:limit]


async def get_entity(db: AsyncSession, entity_id: uuid.UUID) -> Entity | None:
    return await db.get(Entity, entity_id)
