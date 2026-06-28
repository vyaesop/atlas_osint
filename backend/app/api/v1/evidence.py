from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_researcher
from app.crud import entity as entity_crud
from app.crud import evidence as evidence_crud
from app.crud import relationship as rel_crud
from app.db.session import get_db
from app.models.enums import AuditAction
from app.models.evidence import Evidence
from app.models.user import User
from app.schemas.evidence import (
    ConfidenceSummary,
    EvidenceCreate,
    EvidenceRead,
    EvidenceUpdate,
    EvidenceVerify,
)
from app.core import cache
from app.services import confidence, graph_sync
from app.services.audit import record_audit

router = APIRouter(prefix="/evidence", tags=["evidence"])


async def _recompute_parent(db: AsyncSession, ev: Evidence) -> None:
    """Recompute and persist the confidence of the entity/relationship an item
    backs, then re-project the updated score into Neo4j."""
    if ev.entity_id is not None:
        await confidence.recompute_entity_confidence(db, ev.entity_id)
    elif ev.relationship_id is not None:
        await confidence.recompute_relationship_confidence(db, ev.relationship_id)


async def _resync_parent_graph(db: AsyncSession, *, entity_id, relationship_id) -> None:
    if entity_id is not None:
        entity = await entity_crud.get(db, entity_id)
        if entity is not None:
            await graph_sync.upsert_entity(entity)
    elif relationship_id is not None:
        rel = await rel_crud.get(db, relationship_id)
        if rel is not None:
            await graph_sync.upsert_relationship(rel)
    # Evidence changes affect confidence → invalidate cached analytics/dashboards.
    await cache.invalidate_graph()


@router.get("", response_model=list[EvidenceRead])
async def list_evidence(
    entity_id: uuid.UUID | None = None,
    relationship_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await evidence_crud.list_evidence(
        db, entity_id=entity_id, relationship_id=relationship_id, skip=skip, limit=limit
    )


@router.post("", response_model=EvidenceRead, status_code=status.HTTP_201_CREATED)
async def create_evidence(
    payload: EvidenceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    # Validate the referenced target exists for a clean 422.
    if payload.entity_id is not None and await entity_crud.get(db, payload.entity_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Entity does not exist.")
    if payload.relationship_id is not None and await rel_crud.get(db, payload.relationship_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Relationship does not exist.")

    ev = await evidence_crud.create(db, payload, created_by=current_user.id)
    await _recompute_parent(db, ev)
    await record_audit(
        db, actor_id=current_user.id, action=AuditAction.CREATE,
        target_table="evidence", target_id=ev.id,
        changes=payload.model_dump(mode="json"),
    )
    await db.commit()
    await db.refresh(ev)
    await _resync_parent_graph(db, entity_id=ev.entity_id, relationship_id=ev.relationship_id)
    return ev


@router.get("/{evidence_id}", response_model=EvidenceRead)
async def get_evidence(
    evidence_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ev = await evidence_crud.get(db, evidence_id)
    if ev is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found.")
    return ev


@router.patch("/{evidence_id}", response_model=EvidenceRead)
async def update_evidence(
    evidence_id: uuid.UUID,
    payload: EvidenceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    ev = await evidence_crud.get(db, evidence_id)
    if ev is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found.")
    ev = await evidence_crud.update(db, ev, payload)
    await _recompute_parent(db, ev)
    await record_audit(
        db, actor_id=current_user.id, action=AuditAction.UPDATE,
        target_table="evidence", target_id=ev.id,
        changes=payload.model_dump(mode="json", exclude_unset=True),
    )
    await db.commit()
    await db.refresh(ev)
    await _resync_parent_graph(db, entity_id=ev.entity_id, relationship_id=ev.relationship_id)
    return ev


@router.post("/{evidence_id}/verify", response_model=EvidenceRead)
async def verify_evidence(
    evidence_id: uuid.UUID,
    payload: EvidenceVerify,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    """Promote, dispute, or reset the review status of a piece of evidence.

    Verified evidence is what the confidence engine counts, so a verification
    change triggers recomputation of the parent's confidence score.
    """
    ev = await evidence_crud.get(db, evidence_id)
    if ev is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found.")
    ev = await evidence_crud.set_verification(db, ev, payload.status, reviewer_id=current_user.id)
    await _recompute_parent(db, ev)
    await record_audit(
        db, actor_id=current_user.id, action=AuditAction.UPDATE,
        target_table="evidence", target_id=ev.id,
        changes={"verification_status": payload.status.value},
        reason="verification review",
    )
    await db.commit()
    await db.refresh(ev)
    await _resync_parent_graph(db, entity_id=ev.entity_id, relationship_id=ev.relationship_id)
    return ev


@router.delete("/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evidence(
    evidence_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    ev = await evidence_crud.get(db, evidence_id)
    if ev is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found.")
    entity_id, relationship_id = ev.entity_id, ev.relationship_id
    await evidence_crud.delete(db, ev)
    # Recompute the parent now that this item is gone.
    if entity_id is not None:
        await confidence.recompute_entity_confidence(db, entity_id)
    elif relationship_id is not None:
        await confidence.recompute_relationship_confidence(db, relationship_id)
    await record_audit(
        db, actor_id=current_user.id, action=AuditAction.DELETE,
        target_table="evidence", target_id=evidence_id,
    )
    await db.commit()
    await _resync_parent_graph(db, entity_id=entity_id, relationship_id=relationship_id)
