"""Geospatial & spatiotemporal API (#7 map, #8 pattern-of-life, #9 co-location)."""
from __future__ import annotations

import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.enums import EntityType
from app.models.user import User
from app.schemas.geo import (
    ColocationPairRead,
    ColocationResponse,
    GeoFeatureRead,
    MapResponse,
    PatternOfLifeResponse,
    VisitRead,
)
from app.services import geo

router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/map", response_model=MapResponse)
async def map_features(
    type: list[EntityType] | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """All entities placeable on a map — directly or via a LOCATED_IN edge (#7)."""
    features = await geo.map_features(db, types=type)
    return MapResponse(
        count=len(features),
        features=[GeoFeatureRead(**asdict(f)) for f in features],
    )


@router.get("/pattern-of-life/{entity_id}", response_model=PatternOfLifeResponse)
async def pattern_of_life(
    entity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Reconstruct an entity's movement over time from located edges + events (#8)."""
    result = await geo.pattern_of_life(db, entity_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found.")
    return PatternOfLifeResponse(
        entity_id=result.entity_id, entity_name=result.entity_name,
        place_count=result.place_count, total_distance_km=result.total_distance_km,
        visits=[
            VisitRead(
                date=v.date, location_id=v.location_id, location_name=v.location_name,
                lat=v.coords.lat, lon=v.coords.lon, source=v.source, label=v.label,
            )
            for v in result.visits
        ],
    )


@router.get("/colocation", response_model=ColocationResponse)
async def colocation(
    window_days: int = Query(default=7, ge=0, le=365),
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Actors seen at the same place → suggested ASSOCIATED_WITH edges (#9)."""
    pairs = await geo.colocation(db, window_days=window_days, limit=limit)
    return ColocationResponse(
        window_days=window_days,
        pairs=[ColocationPairRead(**asdict(p)) for p in pairs],
    )
