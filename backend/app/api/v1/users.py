from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.crud import user as user_crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[UserRead])
async def list_users(
    skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)
) -> list[User]:
    return await user_crud.list_users(db, skip=skip, limit=limit)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    if await user_crud.get_by_email(db, str(payload.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered.")
    user = await user_crud.create(db, payload)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> User:
    user = await user_crud.get(db, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    return user


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID, payload: UserUpdate, db: AsyncSession = Depends(get_db)
) -> User:
    user = await user_crud.get(db, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    user = await user_crud.update(db, user, payload)
    await db.commit()
    await db.refresh(user)
    return user
