"""Workspace API: saved views / pinboards (#36) and analytic notebooks (#35)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.enums import SavedViewKind
from app.models.user import User
from app.models.workspace import Notebook, NotebookBlock, SavedView
from app.schemas.workspace import (
    NotebookBlockCreate,
    NotebookBlockRead,
    NotebookBlockUpdate,
    NotebookCreate,
    NotebookDetail,
    NotebookRead,
    SavedViewCreate,
    SavedViewRead,
    SavedViewUpdate,
)

router = APIRouter(tags=["workspace"])


# ------------------------- Saved views ------------------------- #

@router.post("/views", response_model=SavedViewRead, status_code=status.HTTP_201_CREATED)
async def create_view(
    payload: SavedViewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    view = SavedView(**payload.model_dump(), owner_id=current_user.id)
    db.add(view)
    await db.commit()
    await db.refresh(view)
    return view


@router.get("/views", response_model=list[SavedViewRead])
async def list_views(
    kind: SavedViewKind | None = None,
    case_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Visible = your own views OR shared views.
    stmt = select(SavedView).where(
        or_(SavedView.owner_id == current_user.id, SavedView.shared.is_(True))
    )
    if kind is not None:
        stmt = stmt.where(SavedView.kind == kind)
    if case_id is not None:
        stmt = stmt.where(SavedView.case_id == case_id)
    stmt = stmt.order_by(SavedView.updated_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def _get_view(db: AsyncSession, view_id: uuid.UUID, user: User) -> SavedView:
    view = await db.get(SavedView, view_id)
    if view is None or (view.owner_id != user.id and not view.shared):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Saved view not found.")
    return view


@router.get("/views/{view_id}", response_model=SavedViewRead)
async def get_view(
    view_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _get_view(db, view_id, current_user)


@router.patch("/views/{view_id}", response_model=SavedViewRead)
async def update_view(
    view_id: uuid.UUID,
    payload: SavedViewUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    view = await db.get(SavedView, view_id)
    if view is None or view.owner_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Saved view not found.")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(view, k, v)
    await db.commit()
    await db.refresh(view)
    return view


@router.delete("/views/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_view(
    view_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    view = await db.get(SavedView, view_id)
    if view is None or view.owner_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Saved view not found.")
    await db.delete(view)
    await db.commit()


# -------------------------- Notebooks -------------------------- #

async def _get_notebook(db: AsyncSession, notebook_id: uuid.UUID) -> Notebook:
    nb = await db.get(Notebook, notebook_id)
    if nb is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notebook not found.")
    return nb


async def _blocks(db: AsyncSession, notebook_id: uuid.UUID) -> list[NotebookBlock]:
    stmt = (
        select(NotebookBlock)
        .where(NotebookBlock.notebook_id == notebook_id)
        .order_by(NotebookBlock.order, NotebookBlock.created_at)
    )
    return list((await db.execute(stmt)).scalars().all())


@router.post("/notebooks", response_model=NotebookRead, status_code=status.HTTP_201_CREATED)
async def create_notebook(
    payload: NotebookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    nb = Notebook(**payload.model_dump(), owner_id=current_user.id)
    db.add(nb)
    await db.commit()
    await db.refresh(nb)
    return nb


@router.get("/notebooks", response_model=list[NotebookRead])
async def list_notebooks(
    case_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Notebook).order_by(Notebook.updated_at.desc())
    if case_id is not None:
        stmt = stmt.where(Notebook.case_id == case_id)
    return list((await db.execute(stmt)).scalars().all())


@router.get("/notebooks/{notebook_id}", response_model=NotebookDetail)
async def get_notebook(
    notebook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    nb = await _get_notebook(db, notebook_id)
    blocks = await _blocks(db, notebook_id)
    return NotebookDetail(
        **NotebookRead.model_validate(nb).model_dump(),
        blocks=[NotebookBlockRead.model_validate(b) for b in blocks],
    )


@router.delete("/notebooks/{notebook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notebook(
    notebook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    nb = await _get_notebook(db, notebook_id)
    await db.delete(nb)
    await db.commit()


@router.post("/notebooks/{notebook_id}/blocks", response_model=NotebookBlockRead,
             status_code=status.HTTP_201_CREATED)
async def add_block(
    notebook_id: uuid.UUID,
    payload: NotebookBlockCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    await _get_notebook(db, notebook_id)
    block = NotebookBlock(notebook_id=notebook_id, **payload.model_dump())
    db.add(block)
    await db.commit()
    await db.refresh(block)
    return block


@router.patch("/notebooks/{notebook_id}/blocks/{block_id}", response_model=NotebookBlockRead)
async def update_block(
    notebook_id: uuid.UUID,
    block_id: uuid.UUID,
    payload: NotebookBlockUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    block = await db.get(NotebookBlock, block_id)
    if block is None or block.notebook_id != notebook_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Block not found.")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(block, k, v)
    await db.commit()
    await db.refresh(block)
    return block


@router.delete("/notebooks/{notebook_id}/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block(
    notebook_id: uuid.UUID,
    block_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    block = await db.get(NotebookBlock, block_id)
    if block is None or block.notebook_id != notebook_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Block not found.")
    await db.delete(block)
    await db.commit()
