from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    CaseItemType,
    CaseStatus,
    Classification,
    CommentTargetType,
    TaskKind,
    TaskStatus,
)


# ---- Case ---- #

class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    summary: str | None = None
    classification: Classification = Classification.UNCLASSIFIED
    priority: int = Field(default=3, ge=1, le=5)
    lead_id: uuid.UUID | None = None


class CaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    summary: str | None = None
    status: CaseStatus | None = None
    classification: Classification | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    lead_id: uuid.UUID | None = None


class CaseReview(BaseModel):
    """Review→dissemination transition (#34): submit / release / close."""
    action: str = Field(pattern="^(submit|release|close|reopen)$")


class CaseItemCreate(BaseModel):
    item_type: CaseItemType
    item_id: uuid.UUID
    note: str | None = None


class CaseItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    item_type: CaseItemType
    item_id: uuid.UUID
    note: str | None
    added_by: uuid.UUID | None
    created_at: datetime


class CaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    summary: str | None
    status: CaseStatus
    classification: Classification
    priority: int
    lead_id: uuid.UUID | None
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class CaseDetail(CaseRead):
    items: list[CaseItemRead]
    task_count: int
    comment_count: int


# ---- Task / RFI ---- #

class TaskCreate(BaseModel):
    case_id: uuid.UUID | None = None
    kind: TaskKind = TaskKind.TASK
    title: str = Field(min_length=1, max_length=512)
    description: str | None = None
    assignee_id: uuid.UUID | None = None
    due_date: date | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = None
    status: TaskStatus | None = None
    assignee_id: uuid.UUID | None = None
    due_date: date | None = None
    answer: str | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    case_id: uuid.UUID | None
    kind: TaskKind
    title: str
    description: str | None
    status: TaskStatus
    assignee_id: uuid.UUID | None
    due_date: date | None
    answer: str | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


# ---- Comment ---- #

class CommentCreate(BaseModel):
    target_type: CommentTargetType
    target_id: uuid.UUID
    body: str = Field(min_length=1)
    parent_id: uuid.UUID | None = None


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    target_type: CommentTargetType
    target_id: uuid.UUID
    body: str
    parent_id: uuid.UUID | None
    author_id: uuid.UUID | None
    created_at: datetime
