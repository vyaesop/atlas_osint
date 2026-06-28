"""Analytic annotations (#4 key assumptions, #6 dissent) API."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_researcher
from app.crud import annotation as annotation_crud
from app.crud import entity as entity_crud
from app.crud import relationship as rel_crud
from app.db.session import get_db
from app.models.enums import AnnotationKind, AuditAction
from app.models.user import User
from app.schemas.annotation import AnnotationCreate, AnnotationRead
from app.services.audit import record_audit

router = APIRouter(prefix="/annotations", tags=["annotations"])


@router.get("", response_model=list[AnnotationRead])
async def list_annotations(
    entity_id: uuid.UUID | None = None,
    relationship_id: uuid.UUID | None = None,
    kind: AnnotationKind | None = None,
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await annotation_crud.list_annotations(
        db, entity_id=entity_id, relationship_id=relationship_id, kind=kind,
        skip=skip, limit=limit,
    )


@router.post("", response_model=AnnotationRead, status_code=status.HTTP_201_CREATED)
async def create_annotation(
    payload: AnnotationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    if payload.entity_id is not None and await entity_crud.get(db, payload.entity_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Entity does not exist.")
    if payload.relationship_id is not None and await rel_crud.get(db, payload.relationship_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Relationship does not exist.")

    ann = await annotation_crud.create(db, payload, created_by=current_user.id)
    await record_audit(
        db, actor_id=current_user.id, action=AuditAction.CREATE,
        target_table="annotations", target_id=ann.id,
        changes=payload.model_dump(mode="json"),
    )
    await db.commit()
    await db.refresh(ann)
    return ann


@router.delete("/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_annotation(
    annotation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    ann = await annotation_crud.get(db, annotation_id)
    if ann is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Annotation not found.")
    await annotation_crud.delete(db, ann)
    await record_audit(
        db, actor_id=current_user.id, action=AuditAction.DELETE,
        target_table="annotations", target_id=annotation_id,
    )
    await db.commit()
