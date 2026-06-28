"""Entity resolution / deduplication (#13) API: find duplicates, merge, unmerge."""
from __future__ import annotations

import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.deps import get_current_user, require_researcher
from app.crud import entity as entity_crud
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.entity_merge import EntityMerge
from app.models.enums import AuditAction
from app.models.user import User
from app.schemas.resolution import (
    DuplicateCandidateRead,
    DuplicatesResponse,
    MergeRead,
    MergeRequest,
    MergeResult,
)
from app.services import entity_resolution, graph_sync
from app.services.audit import record_audit

router = APIRouter(prefix="/resolution", tags=["resolution"])


@router.get("/duplicates", response_model=DuplicatesResponse)
async def find_duplicates(
    threshold: float = Query(default=0.85, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Propose likely-duplicate entity pairs for analyst review (#13)."""
    candidates = await entity_resolution.find_duplicates(db, threshold=threshold, limit=limit)
    return DuplicatesResponse(
        threshold=threshold,
        candidates=[DuplicateCandidateRead(**asdict(c)) for c in candidates],
    )


@router.post("/merge", response_model=MergeResult)
async def merge_entities(
    payload: MergeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    """Merge ``merged_id`` into ``kept_id`` (reversible, audited)."""
    kept = await entity_crud.get(db, payload.kept_id)
    merged = await entity_crud.get(db, payload.merged_id)
    if kept is None or merged is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Both entities must exist.")
    if kept.type is not merged.type:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Entities must share a type.")

    record = await entity_resolution.merge(db, kept, merged, actor_id=current_user.id)
    moved_count = len(record.moved_relationships)
    from app.services import confidence
    await confidence.recompute_entity_confidence(db, kept.id)
    await record_audit(
        db, actor_id=current_user.id, action=AuditAction.DELETE,
        target_table="entities", target_id=merged.id,
        changes={"merged_into": str(kept.id), "merge_record": str(record.id)},
        reason="entity merge",
    )
    await db.commit()
    await db.refresh(record)

    # Best-effort graph resync: refresh kept, drop merged from Neo4j.
    refreshed = await entity_crud.get(db, kept.id)
    if refreshed is not None:
        await graph_sync.upsert_entity(refreshed)
    await graph_sync.delete_entity(merged.id)
    await cache.invalidate_graph()

    return MergeResult(merge=MergeRead.model_validate(record), moved_relationships=moved_count)


@router.get("/merges", response_model=list[MergeRead])
async def list_merges(
    include_undone: bool = False,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(EntityMerge).order_by(EntityMerge.created_at.desc())
    if not include_undone:
        stmt = stmt.where(EntityMerge.undone.is_(False))
    return list((await db.execute(stmt)).scalars().all())


@router.post("/merges/{merge_id}/unmerge", response_model=MergeRead)
async def unmerge_entities(
    merge_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    """Reverse a previous merge, restoring the merged entity and its links."""
    record = await db.get(EntityMerge, merge_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merge record not found.")
    if record.undone:
        raise HTTPException(status.HTTP_409_CONFLICT, "This merge was already undone.")

    restored = await entity_resolution.unmerge(db, record)
    from app.services import confidence
    await confidence.recompute_entity_confidence(db, restored.id)
    await confidence.recompute_entity_confidence(db, record.kept_id)
    await record_audit(
        db, actor_id=current_user.id, action=AuditAction.CREATE,
        target_table="entities", target_id=restored.id,
        changes={"unmerged_from": str(record.kept_id), "merge_record": str(record.id)},
        reason="entity unmerge",
    )
    await db.commit()
    await db.refresh(record)

    refreshed = await entity_crud.get(db, restored.id)
    if refreshed is not None:
        await graph_sync.upsert_entity(refreshed)
    kept = await entity_crud.get(db, record.kept_id)
    if kept is not None:
        await graph_sync.upsert_entity(kept)
    await cache.invalidate_graph()
    return MergeRead.model_validate(record)
