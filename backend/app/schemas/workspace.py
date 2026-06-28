from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import NotebookBlockKind, SavedViewKind


# ---- Saved view / pinboard ---- #

class SavedViewCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    kind: SavedViewKind = SavedViewKind.GRAPH
    state: dict[str, Any] = Field(default_factory=dict)
    shared: bool = False
    case_id: uuid.UUID | None = None


class SavedViewUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    state: dict[str, Any] | None = None
    shared: bool | None = None


class SavedViewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    kind: SavedViewKind
    state: dict[str, Any]
    shared: bool
    case_id: uuid.UUID | None
    owner_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


# ---- Notebook ---- #

class NotebookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    case_id: uuid.UUID | None = None


class NotebookBlockCreate(BaseModel):
    kind: NotebookBlockKind = NotebookBlockKind.TEXT
    content: str | None = None
    ref: dict[str, Any] = Field(default_factory=dict)
    order: int = 0


class NotebookBlockUpdate(BaseModel):
    content: str | None = None
    ref: dict[str, Any] | None = None
    order: int | None = None


class NotebookBlockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    notebook_id: uuid.UUID
    order: int
    kind: NotebookBlockKind
    content: str | None
    ref: dict[str, Any]


class NotebookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    case_id: uuid.UUID | None
    owner_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class NotebookDetail(NotebookRead):
    blocks: list[NotebookBlockRead]
