from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import require_researcher
from app.db.session import get_db
from app.jobs import dispatch
from app.models.enums import AuditAction
from app.models.user import User
from app.schemas.bulk import BulkImportRequest, BulkImportResult
from app.services import bulk_import as bulk_service
from app.services.audit import record_audit

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/bulk", response_model=BulkImportResult, status_code=status.HTTP_201_CREATED)
async def bulk_import(
    payload: BulkImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    """Batch-create entities and relationships in one transaction.

    Entities reference each other by a local ``ref``. Projection to Neo4j/search
    runs through the job queue when enabled, so large imports don't block.
    """
    total = len(payload.entities) + len(payload.relationships)
    if total == 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Nothing to import.")
    if total > settings.BULK_IMPORT_MAX_ITEMS:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Import exceeds the {settings.BULK_IMPORT_MAX_ITEMS}-item limit.",
        )

    outcome = await bulk_service.bulk_import(db, payload, actor_id=current_user.id)
    await record_audit(
        db, actor_id=current_user.id, action=AuditAction.CREATE,
        target_table="entities", target_id=None,
        changes=outcome.result.model_dump(), reason="bulk import",
    )
    await db.commit()

    for entity in outcome.entities:
        await dispatch.sync_entity(entity)
    for rel in outcome.relationships:
        await dispatch.sync_relationship(rel)

    return outcome.result
