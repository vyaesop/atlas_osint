from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_researcher
from app.crud import entity as entity_crud
from app.crud import relationship as rel_crud
from app.db.session import get_db
from app.models.enums import AuditAction, RelationshipType
from app.models.user import User
from app.jobs import dispatch
from app.schemas.evidence import ConfidenceSummary
from app.schemas.relationship import (
    RelationshipCreate,
    RelationshipRead,
    RelationshipUpdate,
)
from app.services import confidence
from app.services.audit import record_audit

router = APIRouter(prefix="/relationships", tags=["relationships"])


@router.get("", response_model=list[RelationshipRead])
async def list_relationships(
    entity_id: uuid.UUID | None = None,
    type: RelationshipType | None = None,
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await rel_crud.list_relationships(
        db, skip=skip, limit=limit, entity_id=entity_id, type_=type
    )


@router.post("", response_model=RelationshipRead, status_code=status.HTTP_201_CREATED)
async def create_relationship(
    payload: RelationshipCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    if payload.source_id == payload.target_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Self-loops are not allowed.")
    # Both endpoints must exist (FKs would catch this, but give a clean 422).
    for endpoint in (payload.source_id, payload.target_id):
        if await entity_crud.get(db, endpoint) is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, f"Entity {endpoint} does not exist."
            )
    rel = await rel_crud.create(db, payload, created_by=current_user.id)
    await record_audit(
        db, actor_id=current_user.id, action=AuditAction.CREATE,
        target_table="relationships", target_id=rel.id,
        changes=payload.model_dump(mode="json"),
    )
    await db.commit()
    await db.refresh(rel)
    await dispatch.sync_relationship(rel)
    return rel


@router.get("/{rel_id}", response_model=RelationshipRead)
async def get_relationship(
    rel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rel = await rel_crud.get(db, rel_id)
    if rel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relationship not found.")
    return rel


@router.get("/{rel_id}/confidence", response_model=ConfidenceSummary)
async def relationship_confidence(
    rel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rel = await rel_crud.get(db, rel_id)
    if rel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relationship not found.")
    result = await confidence.summarize_relationship(db, rel_id)
    return ConfidenceSummary(**result.as_dict())


@router.patch("/{rel_id}", response_model=RelationshipRead)
async def update_relationship(
    rel_id: uuid.UUID,
    payload: RelationshipUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    rel = await rel_crud.get(db, rel_id)
    if rel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relationship not found.")
    rel = await rel_crud.update(db, rel, payload)
    await record_audit(
        db, actor_id=current_user.id, action=AuditAction.UPDATE,
        target_table="relationships", target_id=rel.id,
        changes=payload.model_dump(mode="json", exclude_unset=True),
    )
    await db.commit()
    await db.refresh(rel)
    await dispatch.sync_relationship(rel)
    return rel


@router.delete("/{rel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_relationship(
    rel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    rel = await rel_crud.get(db, rel_id)
    if rel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relationship not found.")
    await rel_crud.delete(db, rel)
    await record_audit(
        db, actor_id=current_user.id, action=AuditAction.DELETE,
        target_table="relationships", target_id=rel_id,
    )
    await db.commit()
    await dispatch.remove_relationship(rel_id)
