from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.abac import user_can_access
from app.core.deps import get_current_user, require_researcher
from app.crud import entity as entity_crud
from app.db.session import get_db
from app.models.enums import AuditAction, EntityType
from app.models.user import User
from app.schemas.entity import EntityCreate, EntityRead, EntityUpdate
from app.jobs import dispatch
from app.schemas.evidence import ConfidenceSummary
from app.services import confidence
from app.services.audit import record_audit

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("", response_model=list[EntityRead])
async def list_entities(
    type: EntityType | None = None,
    q: str | None = Query(default=None, description="Name/alias contains filter"),
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entities = await entity_crud.list_entities(db, skip=skip, limit=limit, type_=type, q=q)
    # ABAC (#38): hide entities the caller is not cleared / compartmented for.
    return [
        e for e in entities
        if user_can_access(current_user, classification=e.classification, compartments=e.compartments)
    ]


@router.post("", response_model=EntityRead, status_code=status.HTTP_201_CREATED)
async def create_entity(
    payload: EntityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    entity = await entity_crud.create(db, payload, created_by=current_user.id)
    await record_audit(
        db, actor_id=current_user.id, action=AuditAction.CREATE,
        target_table="entities", target_id=entity.id,
        changes=payload.model_dump(mode="json"),
    )
    await db.commit()
    await db.refresh(entity)
    await dispatch.sync_entity(entity)
    return entity


@router.get("/{entity_id}", response_model=EntityRead)
async def get_entity(
    entity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entity = await entity_crud.get(db, entity_id)
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found.")
    # 404 (not 403) when not cleared, so existence isn't disclosed.
    if not user_can_access(current_user, classification=entity.classification,
                           compartments=entity.compartments):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found.")
    return entity


@router.get("/{entity_id}/confidence", response_model=ConfidenceSummary)
async def entity_confidence(
    entity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    entity = await entity_crud.get(db, entity_id)
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found.")
    result = await confidence.summarize_entity(db, entity_id)
    return ConfidenceSummary(**result.as_dict())


@router.patch("/{entity_id}", response_model=EntityRead)
async def update_entity(
    entity_id: uuid.UUID,
    payload: EntityUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    entity = await entity_crud.get(db, entity_id)
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found.")
    entity = await entity_crud.update(db, entity, payload)
    await record_audit(
        db, actor_id=current_user.id, action=AuditAction.UPDATE,
        target_table="entities", target_id=entity.id,
        changes=payload.model_dump(mode="json", exclude_unset=True),
    )
    await db.commit()
    await db.refresh(entity)
    await dispatch.sync_entity(entity)
    return entity


@router.delete("/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity(
    entity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    entity = await entity_crud.get(db, entity_id)
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found.")
    await entity_crud.delete(db, entity)
    await record_audit(
        db, actor_id=current_user.id, action=AuditAction.DELETE,
        target_table="entities", target_id=entity_id,
    )
    await db.commit()
    await dispatch.remove_entity(entity_id)
