from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import summaries
from app.ai.service import ai_service
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.ingestion import SummaryResponse

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/provider")
async def provider_info(_: User = Depends(get_current_user)) -> dict[str, str]:
    """Which extraction/summarization provider is active."""
    return {"provider": ai_service.provider_name}


@router.post("/summarize/entity/{entity_id}", response_model=SummaryResponse)
async def summarize_entity(
    entity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """AI summary of an entity from its recorded connections and evidence."""
    result = await summaries.summarize_entity(db, entity_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found.")
    summary, provider = result
    return SummaryResponse(subject_id=entity_id, summary=summary, provider=provider)


@router.post("/summarize/timeline/{entity_id}", response_model=SummaryResponse)
async def summarize_timeline(
    entity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """AI summary of an entity's dated relationships as a timeline."""
    result = await summaries.summarize_timeline(db, entity_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found.")
    summary, provider = result
    return SummaryResponse(subject_id=entity_id, summary=summary, provider=provider)
