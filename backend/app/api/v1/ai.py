from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import summaries
from app.ai.assistant import assistant, execute_spec
from app.ai.service import ai_service
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai import QueryRequest, QueryResponse, ReportResponse
from app.schemas.analytics import PathEdgeRead, PathRead, RankedNodeRead
from app.schemas.evidence import ConfidenceSummary
from app.schemas.ingestion import SummaryResponse
from app.services.report import build_report

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/query", response_model=QueryResponse)
async def natural_language_query(
    payload: QueryRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Answer a natural-language question by translating it to a graph query
    and executing it deterministically (#24)."""
    spec = assistant.parse(payload.question)
    result = await execute_spec(db, spec)

    path_read = None
    if result.path is not None and result.path.found and result.path.paths:
        p = result.path.paths[0]
        path_read = PathRead(
            kind=p.kind,
            nodes=[RankedNodeRead(id=n.id, name=n.name, type=n.type, score=n.score) for n in p.nodes],
            edges=[PathEdgeRead(rel_id=e.rel_id, source=e.source, target=e.target,
                                type=e.type, confidence=e.confidence) for e in p.edges],
            length=p.length, score=p.score, bottleneck_confidence=p.bottleneck_confidence,
        )
    return QueryResponse(
        intent=result.intent, provider=assistant.name, message=result.message,
        entities=result.entities, path=path_read,
    )


@router.post("/report/entity/{entity_id}", response_model=ReportResponse)
async def intelligence_report(
    entity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Generate a grounded, confidence-aware intelligence report / target
    package for an entity (#26)."""
    report = await build_report(db, entity_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found.")
    return ReportResponse(
        subject=report.dashboard.entity,
        provider=report.provider,
        narrative=report.narrative,
        key_findings=report.key_findings,
        confidence=ConfidenceSummary(**report.confidence.as_dict()),
        timeline_event_count=report.timeline_event_count,
        dashboard=report.dashboard,
    )


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
