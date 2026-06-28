"""Insights API: risk scoring (#49), network diff (#47), lineage (#5), facets (#46)."""
from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.abac import user_can_access
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.enums import EntityType
from app.models.user import User
from app.schemas.insights import (
    FacetsResponse,
    LineageResponse,
    NetworkDiffResponse,
    RiskListResponse,
    RiskScoreRead,
)
from app.services import diff as diff_service
from app.services import facets as facets_service
from app.services import lineage as lineage_service
from app.services import risk as risk_service

router = APIRouter(prefix="/insights", tags=["insights"])


def _require_access(entity, user) -> None:
    """404-hide an entity the caller is not cleared for (no existence disclosure)."""
    if entity is None or not user_can_access(
        user, classification=entity.classification, compartments=entity.compartments
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found.")


@router.get("/risk/{entity_id}", response_model=RiskScoreRead)
async def entity_risk(
    entity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Composite risk score for one entity, with factor breakdown (#49)."""
    entity = await risk_service.get_entity(db, entity_id)
    _require_access(entity, current_user)
    return RiskScoreRead(**asdict(await risk_service.score_entity(db, entity)))


@router.get("/risk", response_model=RiskListResponse)
async def top_risk(
    limit: int = Query(default=25, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Highest-risk entities across the graph (#49), ABAC-filtered to the caller."""
    results = await risk_service.top_risky(db, limit=limit, user=current_user)
    return RiskListResponse(count=len(results), results=[RiskScoreRead(**asdict(r)) for r in results])


@router.get("/diff", response_model=NetworkDiffResponse)
async def network_diff(
    since: datetime = Query(..., description="ISO timestamp; report changes at/after this time"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """What entities/relationships changed since a point in time (#47),
    ABAC-filtered so the change feed never names compartmented entities."""
    result = await diff_service.compute_diff(db, since, user=current_user)
    return NetworkDiffResponse(
        since=result.since,
        added_entities=[asdict(i) for i in result.added_entities],
        modified_entities=[asdict(i) for i in result.modified_entities],
        added_relationships=[asdict(i) for i in result.added_relationships],
        modified_relationships=[asdict(i) for i in result.modified_relationships],
        removed=[asdict(i) for i in result.removed],
    )


@router.get("/lineage/{entity_id}", response_model=LineageResponse)
async def entity_lineage(
    entity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Provenance graph for an entity: sources, evidence, AI vs human (#5)."""
    entity = await risk_service.get_entity(db, entity_id)
    _require_access(entity, current_user)
    result = await lineage_service.build_lineage(db, entity)
    return LineageResponse(
        entity_id=entity_id, summary=result.summary,
        nodes=[asdict(n) for n in result.nodes],
        edges=[asdict(e) for e in result.edges],
    )


@router.get("/facets", response_model=FacetsResponse)
async def facets(
    type: EntityType | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Faceted entity counts for brush-filtering (#46), ABAC-filtered so the
    histogram cannot leak the existence/volume of data above the caller's
    clearance."""
    result = await facets_service.compute_facets(db, type_=type, user=current_user)
    return FacetsResponse(
        total=result.total,
        by_type=[asdict(b) for b in result.by_type],
        by_classification=[asdict(b) for b in result.by_classification],
        by_confidence=[asdict(b) for b in result.by_confidence],
        by_provenance=[asdict(b) for b in result.by_provenance],
        by_month=[asdict(b) for b in result.by_month],
    )
