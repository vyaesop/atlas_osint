from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_researcher
from app.db.session import get_db
from app.ingestion.parsers import UnsupportedDocumentError, parse_document
from app.ingestion.pipeline import IngestionOutcome, ingest_text
from app.jobs import dispatch
from app.models.enums import AuditAction
from app.models.user import User
from app.schemas.ingestion import (
    IngestionResponse,
    IngestionSummary,
    IngestTextRequest,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


async def _finalize(db: AsyncSession, outcome: IngestionOutcome, actor: User) -> IngestionResponse:
    """Audit, commit, then project new graph objects to Neo4j + search."""
    await record_audit(
        db, actor_id=actor.id, action=AuditAction.CREATE,
        target_table="documents", target_id=outcome.document.id,
        changes=outcome.document.extraction,
        reason=f"ingested via {outcome.provider}",
    )
    await db.commit()

    # Project the document node + extracted entities/relationships (inline or queued).
    await dispatch.sync_entity(outcome.document_node)
    for entity in outcome.entities:
        await dispatch.sync_entity(entity)
    for rel in outcome.relationships:
        await dispatch.sync_relationship(rel)

    return IngestionResponse(
        document_id=outcome.document.id,
        document_entity_id=outcome.document_node.id,
        provider=outcome.provider,
        summary=IngestionSummary(**{
            "entities_created": outcome.document.extraction.get("entities_created", 0),
            "relationships_created": outcome.document.extraction.get("relationships_created", 0),
            "entities_total": outcome.document.extraction.get("entities_total", 0),
            "relationships_total": outcome.document.extraction.get("relationships_total", 0),
        }),
        entities=outcome.entities,
        relationships=outcome.relationships,
    )


@router.post("/text", response_model=IngestionResponse, status_code=status.HTTP_201_CREATED)
async def ingest_raw_text(
    payload: IngestTextRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    """Ingest pasted text, extract entities/relationships (AI-generated, unverified)."""
    outcome = await ingest_text(
        db, text=payload.text, title=payload.title, actor_id=current_user.id,
    )
    return await _finalize(db, outcome, current_user)


@router.post("/upload", response_model=IngestionResponse, status_code=status.HTTP_201_CREATED)
async def ingest_upload(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    """Upload a TXT/CSV/JSON/PDF/DOCX document and ingest it."""
    raw = await file.read()
    try:
        parsed = parse_document(raw, filename=file.filename, content_type=file.content_type)
    except UnsupportedDocumentError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc))
    if not parsed.text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Document has no extractable text.")

    outcome = await ingest_text(
        db, text=parsed.text, title=title or file.filename or "Untitled document",
        actor_id=current_user.id, filename=file.filename, content_type=file.content_type,
    )
    return await _finalize(db, outcome, current_user)
