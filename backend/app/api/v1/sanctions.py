"""Sanctions / watchlist screening API (#18)."""
from __future__ import annotations

import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_researcher
from app.db.session import get_db
from app.models.user import User
from app.models.watchlist import WatchlistEntry
from app.schemas.sanctions import (
    ScreeningHitRead,
    ScreeningResponse,
    WatchlistBulkCreate,
    WatchlistEntryRead,
)
from app.services import sanctions

router = APIRouter(prefix="/sanctions", tags=["sanctions"])


@router.get("/watchlist", response_model=list[WatchlistEntryRead])
async def list_watchlist(
    skip: int = 0,
    limit: int = Query(default=100, le=1000),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(WatchlistEntry).order_by(WatchlistEntry.name).offset(skip).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


@router.post("/watchlist", response_model=list[WatchlistEntryRead], status_code=status.HTTP_201_CREATED)
async def add_watchlist(
    payload: WatchlistBulkCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_researcher),
):
    """Bulk-load watchlist entries (from a downloaded OFAC/UN/EU list or upload)."""
    created = [WatchlistEntry(**e.model_dump()) for e in payload.entries]
    db.add_all(created)
    await db.commit()
    for e in created:
        await db.refresh(e)
    return created


@router.delete("/watchlist/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist_entry(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_researcher),
):
    entry = await db.get(WatchlistEntry, entry_id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Watchlist entry not found.")
    await db.delete(entry)
    await db.commit()


@router.get("/screen/{entity_id}", response_model=ScreeningResponse)
async def screen_entity(
    entity_id: uuid.UUID,
    threshold: float = Query(default=0.85, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Screen a single entity against the loaded watchlist."""
    entity = await sanctions.get_entity(db, entity_id)
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found.")
    hits = await sanctions.screen_entity(db, entity, threshold=threshold)
    return ScreeningResponse(threshold=threshold, hits=[ScreeningHitRead(**asdict(h)) for h in hits])


@router.get("/scan", response_model=ScreeningResponse)
async def scan(
    threshold: float = Query(default=0.85, ge=0.0, le=1.0),
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Screen every entity against the loaded watchlist (batch)."""
    hits = await sanctions.scan_all(db, threshold=threshold, limit=limit)
    return ScreeningResponse(threshold=threshold, hits=[ScreeningHitRead(**asdict(h)) for h in hits])
