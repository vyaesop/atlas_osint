"""Casework API: cases (#31), review/dissemination (#34), tasks/RFIs (#32),
threaded comments (#33)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_researcher
from app.db.session import get_db
from app.models.casework import Case, CaseItem, Comment, Task
from app.models.enums import AuditAction, CaseStatus, CommentTargetType, TaskStatus
from app.models.user import User
from app.schemas.casework import (
    CaseCreate,
    CaseDetail,
    CaseItemCreate,
    CaseItemRead,
    CaseRead,
    CaseReview,
    CaseUpdate,
    CommentCreate,
    CommentRead,
    TaskCreate,
    TaskRead,
    TaskUpdate,
)
from app.services.audit import record_audit

router = APIRouter(tags=["casework"])

# review action → resulting status
_REVIEW_TRANSITIONS = {
    "submit": CaseStatus.IN_REVIEW,
    "release": CaseStatus.RELEASED,
    "close": CaseStatus.CLOSED,
    "reopen": CaseStatus.ACTIVE,
}


async def _get_case(db: AsyncSession, case_id: uuid.UUID) -> Case:
    case = await db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found.")
    return case


# ----------------------------- Cases ----------------------------- #

@router.post("/cases", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    case = Case(**payload.model_dump(), created_by=current_user.id)
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return case


@router.get("/cases", response_model=list[CaseRead])
async def list_cases(
    status_filter: CaseStatus | None = Query(default=None, alias="status"),
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Case).order_by(Case.priority, Case.updated_at.desc())
    if status_filter is not None:
        stmt = stmt.where(Case.status == status_filter)
    stmt = stmt.offset(skip).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


@router.get("/cases/{case_id}", response_model=CaseDetail)
async def get_case(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    case = await _get_case(db, case_id)
    items = list((await db.execute(
        select(CaseItem).where(CaseItem.case_id == case_id).order_by(CaseItem.created_at)
    )).scalars().all())
    task_count = (await db.execute(
        select(func.count()).select_from(Task).where(Task.case_id == case_id)
    )).scalar_one()
    comment_count = (await db.execute(
        select(func.count()).select_from(Comment).where(
            Comment.target_type == CommentTargetType.CASE, Comment.target_id == case_id
        )
    )).scalar_one()
    return CaseDetail(
        **CaseRead.model_validate(case).model_dump(),
        items=[CaseItemRead.model_validate(i) for i in items],
        task_count=task_count, comment_count=comment_count,
    )


@router.patch("/cases/{case_id}", response_model=CaseRead)
async def update_case(
    case_id: uuid.UUID,
    payload: CaseUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_researcher),
):
    case = await _get_case(db, case_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(case, k, v)
    await db.commit()
    await db.refresh(case)
    return case


@router.post("/cases/{case_id}/review", response_model=CaseRead)
async def review_case(
    case_id: uuid.UUID,
    payload: CaseReview,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    """Advance a case through the review→dissemination workflow (#34)."""
    case = await _get_case(db, case_id)
    case.status = _REVIEW_TRANSITIONS[payload.action]
    if payload.action == "release":
        case.reviewed_by = current_user.id
        case.reviewed_at = datetime.now(timezone.utc)
    await record_audit(
        db, actor_id=current_user.id, action=AuditAction.UPDATE,
        target_table="cases", target_id=case.id,
        changes={"status": case.status.value}, reason=f"case {payload.action}",
    )
    await db.commit()
    await db.refresh(case)
    return case


# ------------------------- Case items ------------------------- #

@router.post("/cases/{case_id}/items", response_model=CaseItemRead, status_code=status.HTTP_201_CREATED)
async def add_case_item(
    case_id: uuid.UUID,
    payload: CaseItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    await _get_case(db, case_id)
    existing = (await db.execute(
        select(CaseItem).where(
            CaseItem.case_id == case_id, CaseItem.item_type == payload.item_type,
            CaseItem.item_id == payload.item_id,
        )
    )).scalar_one_or_none()
    if existing is not None:
        return existing
    item = CaseItem(case_id=case_id, added_by=current_user.id, **payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/cases/{case_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_case_item(
    case_id: uuid.UUID,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_researcher),
):
    item = await db.get(CaseItem, item_id)
    if item is None or item.case_id != case_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case item not found.")
    await db.delete(item)
    await db.commit()


# ----------------------------- Tasks ----------------------------- #

@router.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_researcher),
):
    if payload.case_id is not None:
        await _get_case(db, payload.case_id)
    task = Task(**payload.model_dump(), created_by=current_user.id)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.get("/tasks", response_model=list[TaskRead])
async def list_tasks(
    case_id: uuid.UUID | None = None,
    assignee_id: uuid.UUID | None = None,
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Task).order_by(Task.created_at.desc())
    if case_id is not None:
        stmt = stmt.where(Task.case_id == case_id)
    if assignee_id is not None:
        stmt = stmt.where(Task.assignee_id == assignee_id)
    if status_filter is not None:
        stmt = stmt.where(Task.status == status_filter)
    return list((await db.execute(stmt)).scalars().all())


@router.patch("/tasks/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_researcher),
):
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found.")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(task, k, v)
    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_researcher),
):
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found.")
    await db.delete(task)
    await db.commit()


# ---------------------------- Comments ---------------------------- #

@router.post("/comments", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
async def create_comment(
    payload: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comment = Comment(**payload.model_dump(), author_id=current_user.id)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


@router.get("/comments", response_model=list[CommentRead])
async def list_comments(
    target_type: CommentTargetType,
    target_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = (
        select(Comment)
        .where(Comment.target_type == target_type, Comment.target_id == target_id)
        .order_by(Comment.created_at)
    )
    return list((await db.execute(stmt)).scalars().all())


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comment = await db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found.")
    # Authors delete their own; admins delete any.
    if comment.author_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot delete another user's comment.")
    await db.delete(comment)
    await db.commit()
