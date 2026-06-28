"""Proactive alert feed API (#28)."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.alerts import AlertRead, AlertsResponse
from app.services import alerts as alerts_service

router = APIRouter(prefix="/alerts", tags=["alerts"])

_VALID_KINDS = {"contradiction", "anomaly", "sanctions"}


@router.get("", response_model=AlertsResponse)
async def list_alerts(
    kind: list[str] | None = Query(default=None, description="contradiction | anomaly | sanctions"),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Ranked feed of contradictions, structural anomalies, and watchlist hits."""
    kinds = {k for k in kind if k in _VALID_KINDS} if kind else None
    results = await alerts_service.compute_alerts(db, kinds=kinds, limit=limit)
    return AlertsResponse(
        count=len(results),
        alerts=[AlertRead(**asdict(a)) for a in results],
    )
