from __future__ import annotations

import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import summaries
from app.ai.assistant import assistant, execute_spec
from app.ai.service import ai_service
from app.core.deps import get_current_user, require_researcher
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai import (
    CitationRead,
    DeepfakeRequest,
    FindingRead,
    InvestigateResponse,
    MediaRiskResponse,
    MultimodalResponse,
    QueryRequest,
    QueryResponse,
    RagRequest,
    RagResponse,
    ReportResponse,
)
from app.schemas.analytics import PathEdgeRead, PathRead, RankedNodeRead
from app.schemas.evidence import ConfidenceSummary
from app.schemas.ingestion import SummaryResponse
from app.crud import entity as entity_crud
from app.ingestion.pipeline import ingest_text
from app.jobs import dispatch
from app.services import investigate as investigate_service
from app.services import media_forensics, multimodal, rag
from app.services.multimodal import MultimodalUnavailable
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


@router.post("/rag", response_model=RagResponse)
async def rag_answer(
    payload: RagRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Answer a question from the document corpus, grounded with citations (#25)."""
    result = await rag.answer(db, payload.question, k=payload.k)
    return RagResponse(
        answer=result.answer, provider=result.provider, grounded=result.grounded,
        citations=[CitationRead(**asdict(c)) for c in result.citations],
    )


@router.post("/investigate/{entity_id}", response_model=InvestigateResponse)
async def investigate(
    entity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Autonomously run analyses on a lead entity and propose next actions (#27)."""
    entity = await entity_crud.get(db, entity_id)
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found.")
    inv = await investigate_service.investigate(db, entity)
    findings_text = "\n".join(f"- [{f.severity}] {f.kind}: {f.detail}" for f in inv.findings)
    narrative = await ai_service.summarize(
        f"investigation of {entity.name}",
        f"Findings:\n{findings_text}\nRecommended actions:\n" + "\n".join(inv.recommended_actions),
    )
    return InvestigateResponse(
        subject=entity, provider=ai_service.provider_name, narrative=narrative,
        findings=[FindingRead(kind=f.kind, severity=f.severity, detail=f.detail) for f in inv.findings],
        recommended_actions=inv.recommended_actions,
    )


@router.post("/media/deepfake-check", response_model=MediaRiskResponse)
async def deepfake_check(
    payload: DeepfakeRequest,
    _: User = Depends(get_current_user),
):
    """Heuristic synthetic-media / deepfake risk flag from metadata + text (#30)."""
    risk = media_forensics.assess(
        filename=payload.filename, software=payload.software,
        metadata=payload.metadata, text=payload.text,
    )
    return MediaRiskResponse(risk=risk.risk, score=risk.score, reasons=risk.reasons)


async def _multimodal_ingest(db, text, title, user, kind) -> MultimodalResponse:
    """Shared tail for image/audio endpoints: optionally graph the extracted text."""
    outcome = await ingest_text(db, text=text, title=title, actor_id=user.id)
    await db.commit()
    await dispatch.sync_entity(outcome.document_node)
    for e in outcome.entities:
        await dispatch.sync_entity(e)
    for r in outcome.relationships:
        await dispatch.sync_relationship(r)
    return MultimodalResponse(
        provider="gemini", text=text, ingested=True, document_id=str(outcome.document.id),
        entities_created=outcome.entities_created, relationships_created=outcome.relationships_created,
    )


@router.post("/image", response_model=MultimodalResponse)
async def analyze_image(
    file: UploadFile = File(...),
    ingest: bool = Form(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    """Image intelligence via Gemini vision — caption, OCR, entity listing (#20)."""
    data = await file.read()
    try:
        text = await multimodal.analyze_image(data, file.content_type or "image/jpeg")
    except MultimodalUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    if not ingest:
        return MultimodalResponse(provider="gemini", text=text)
    return await _multimodal_ingest(db, text, file.filename or "Image", current_user, "image")


@router.post("/audio", response_model=MultimodalResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    ingest: bool = Form(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    """Audio/video transcription via Gemini, then optional extraction (#21)."""
    data = await file.read()
    try:
        text = await multimodal.transcribe_audio(data, file.content_type or "audio/mpeg")
    except MultimodalUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    if not ingest:
        return MultimodalResponse(provider="gemini", text=text)
    return await _multimodal_ingest(db, text, file.filename or "Audio", current_user, "audio")


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
