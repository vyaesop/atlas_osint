"""Analysis of Competing Hypotheses (#1) API."""
from __future__ import annotations

import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import ach as ach_crud
from app.crud import evidence as evidence_crud
from app.core.deps import get_current_user, require_researcher
from app.db.session import get_db
from app.models.ach import AchAnalysis
from app.models.user import User
from app.schemas.ach import (
    AchAnalysisCreate,
    AchAnalysisDetail,
    AchAnalysisRead,
    AchScoreRead,
    HypothesisCreate,
    HypothesisRead,
    HypothesisScoreRead,
    ItemCreate,
    ItemDiagnosticityRead,
    ItemRead,
    RatingSet,
)

router = APIRouter(prefix="/ach", tags=["ach"])


async def _detail(db: AsyncSession, analysis: AchAnalysis) -> AchAnalysisDetail:
    hyps = await ach_crud.hypotheses_for(db, analysis.id)
    items = await ach_crud.items_for(db, analysis.id)
    ratings = await ach_crud.ratings_for(db, analysis.id)
    scores = await ach_crud.compute_scores(db, analysis.id)
    return AchAnalysisDetail(
        **AchAnalysisRead.model_validate(analysis).model_dump(),
        hypotheses=[HypothesisRead.model_validate(h) for h in hyps],
        items=[ItemRead.model_validate(i) for i in items],
        ratings=ratings,
        scores=AchScoreRead(
            hypotheses=[HypothesisScoreRead(**asdict(s)) for s in scores.hypotheses],
            items=[ItemDiagnosticityRead(**asdict(i)) for i in scores.items],
            most_likely_hypothesis_id=scores.most_likely_hypothesis_id,
        ),
    )


async def _require_analysis(db: AsyncSession, analysis_id: uuid.UUID) -> AchAnalysis:
    analysis = await ach_crud.get_analysis(db, analysis_id)
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ACH analysis not found.")
    return analysis


@router.post("", response_model=AchAnalysisRead, status_code=status.HTTP_201_CREATED)
async def create_analysis(
    payload: AchAnalysisCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    analysis = await ach_crud.create_analysis(db, payload, created_by=current_user.id)
    await db.commit()
    await db.refresh(analysis)
    return analysis


@router.get("", response_model=list[AchAnalysisRead])
async def list_analyses(
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await ach_crud.list_analyses(db, skip=skip, limit=limit)


@router.get("/{analysis_id}", response_model=AchAnalysisDetail)
async def get_analysis(
    analysis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Full matrix + computed scores: hypotheses ranked by least weighted
    inconsistency, and items ranked by diagnosticity."""
    analysis = await _require_analysis(db, analysis_id)
    return await _detail(db, analysis)


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_analysis(
    analysis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_researcher),
):
    analysis = await _require_analysis(db, analysis_id)
    await ach_crud.delete_analysis(db, analysis)
    await db.commit()


@router.post("/{analysis_id}/hypotheses", response_model=HypothesisRead, status_code=status.HTTP_201_CREATED)
async def add_hypothesis(
    analysis_id: uuid.UUID,
    payload: HypothesisCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_researcher),
):
    await _require_analysis(db, analysis_id)
    h = await ach_crud.add_hypothesis(db, analysis_id, payload)
    await db.commit()
    await db.refresh(h)
    return h


@router.post("/{analysis_id}/items", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
async def add_item(
    analysis_id: uuid.UUID,
    payload: ItemCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_researcher),
):
    await _require_analysis(db, analysis_id)
    if payload.evidence_id is not None and await evidence_crud.get(db, payload.evidence_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Linked evidence does not exist.")
    item = await ach_crud.add_item(db, analysis_id, payload)
    await db.commit()
    await db.refresh(item)
    return item


@router.put("/{analysis_id}/ratings", response_model=AchAnalysisDetail)
async def set_rating(
    analysis_id: uuid.UUID,
    payload: RatingSet,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_researcher),
):
    """Set one matrix cell's consistency, then return the rescored analysis."""
    analysis = await _require_analysis(db, analysis_id)
    hyp = await ach_crud.get_hypothesis(db, payload.hypothesis_id)
    item = await ach_crud.get_item(db, payload.item_id)
    if hyp is None or hyp.analysis_id != analysis_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Hypothesis not in this analysis.")
    if item is None or item.analysis_id != analysis_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Item not in this analysis.")
    await ach_crud.upsert_rating(
        db, analysis_id, payload.hypothesis_id, payload.item_id, payload.consistency
    )
    await db.commit()
    return await _detail(db, analysis)
