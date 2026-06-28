from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ach import AchAnalysis, AchHypothesis, AchItem, AchRating
from app.schemas.ach import AchAnalysisCreate, HypothesisCreate, ItemCreate
from app.services import ach as ach_scoring


async def create_analysis(
    db: AsyncSession, data: AchAnalysisCreate, *, created_by: uuid.UUID
) -> AchAnalysis:
    analysis = AchAnalysis(title=data.title, question=data.question, created_by=created_by)
    db.add(analysis)
    await db.flush()
    return analysis


async def get_analysis(db: AsyncSession, analysis_id: uuid.UUID) -> AchAnalysis | None:
    return await db.get(AchAnalysis, analysis_id)


async def list_analyses(db: AsyncSession, *, skip: int = 0, limit: int = 100) -> list[AchAnalysis]:
    stmt = select(AchAnalysis).order_by(AchAnalysis.created_at.desc()).offset(skip).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


async def delete_analysis(db: AsyncSession, analysis: AchAnalysis) -> None:
    await db.delete(analysis)
    await db.flush()


async def add_hypothesis(
    db: AsyncSession, analysis_id: uuid.UUID, data: HypothesisCreate
) -> AchHypothesis:
    h = AchHypothesis(analysis_id=analysis_id, text=data.text, order=data.order)
    db.add(h)
    await db.flush()
    return h


async def add_item(db: AsyncSession, analysis_id: uuid.UUID, data: ItemCreate) -> AchItem:
    item = AchItem(
        analysis_id=analysis_id, text=data.text, evidence_id=data.evidence_id,
        weight=data.weight, order=data.order,
    )
    db.add(item)
    await db.flush()
    return item


async def hypotheses_for(db: AsyncSession, analysis_id: uuid.UUID) -> list[AchHypothesis]:
    stmt = (
        select(AchHypothesis)
        .where(AchHypothesis.analysis_id == analysis_id)
        .order_by(AchHypothesis.order, AchHypothesis.created_at)
    )
    return list((await db.execute(stmt)).scalars().all())


async def items_for(db: AsyncSession, analysis_id: uuid.UUID) -> list[AchItem]:
    stmt = (
        select(AchItem)
        .where(AchItem.analysis_id == analysis_id)
        .order_by(AchItem.order, AchItem.created_at)
    )
    return list((await db.execute(stmt)).scalars().all())


async def ratings_for(db: AsyncSession, analysis_id: uuid.UUID) -> list[AchRating]:
    stmt = select(AchRating).where(AchRating.analysis_id == analysis_id)
    return list((await db.execute(stmt)).scalars().all())


async def get_hypothesis(db: AsyncSession, hypothesis_id: uuid.UUID) -> AchHypothesis | None:
    return await db.get(AchHypothesis, hypothesis_id)


async def get_item(db: AsyncSession, item_id: uuid.UUID) -> AchItem | None:
    return await db.get(AchItem, item_id)


async def upsert_rating(
    db: AsyncSession, analysis_id: uuid.UUID, hypothesis_id: uuid.UUID,
    item_id: uuid.UUID, consistency,
) -> AchRating:
    """Set (or update) the consistency of one matrix cell."""
    stmt = select(AchRating).where(
        AchRating.hypothesis_id == hypothesis_id, AchRating.item_id == item_id
    )
    rating = (await db.execute(stmt)).scalar_one_or_none()
    if rating is None:
        rating = AchRating(
            analysis_id=analysis_id, hypothesis_id=hypothesis_id,
            item_id=item_id, consistency=consistency,
        )
        db.add(rating)
    else:
        rating.consistency = consistency
    await db.flush()
    return rating


async def compute_scores(db: AsyncSession, analysis_id: uuid.UUID) -> ach_scoring.AchScoreResult:
    """Load the matrix and run the pure ACH scorer."""
    hyps = await hypotheses_for(db, analysis_id)
    items = await items_for(db, analysis_id)
    ratings = await ratings_for(db, analysis_id)

    rating_map = {(str(r.hypothesis_id), str(r.item_id)): r.consistency for r in ratings}
    return ach_scoring.score(
        [ach_scoring._Hypothesis(id=str(h.id), text=h.text) for h in hyps],
        [ach_scoring._Item(id=str(i.id), text=i.text, weight=i.weight) for i in items],
        rating_map,
    )
