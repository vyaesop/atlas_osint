from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.enums import RelationshipType
from app.models.user import User
from app.schemas.dashboard import DashboardResponse, TimelineResponse
from app.services import dashboards as dashboard_service
from app.services import timeline as timeline_service

router = APIRouter(tags=["dashboards"])


@router.get("/dashboards/entities/{entity_id}", response_model=DashboardResponse)
async def entity_dashboard(
    entity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Aggregated dashboard for an entity: connections, sections by type,
    document references, and influence metrics."""
    async def compute() -> DashboardResponse | None:
        return await dashboard_service.build_dashboard(db, entity_id)

    result = await cache.cached_call(
        "dashboard", {"id": str(entity_id)}, compute,
        serialize=lambda r: r.model_dump(mode="json") if r else None,
        deserialize=lambda d: DashboardResponse(**d) if d else None,
    )
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found.")
    return result


@router.get("/timeline/entities/{entity_id}", response_model=TimelineResponse)
async def entity_timeline(
    entity_id: uuid.UUID,
    relationship_type: list[RelationshipType] | None = Query(default=None),
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Chronological timeline for an entity, with optional type / date filtering."""
    result = await timeline_service.build_timeline(
        db, entity_id, relationship_types=relationship_type,
        date_from=date_from, date_to=date_to,
    )
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found.")
    return result
