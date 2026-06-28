from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.security import (
    JWTError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.crud import user as user_crud
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User
from app.schemas.token import RefreshRequest, TokenPair
from app.schemas.user import UserCreate, UserRead, UserRegister

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(str(user.id), user.role.value),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)) -> User:
    """Public self-registration. Always creates a Viewer account."""
    if await user_crud.get_by_email(db, str(payload.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered.")
    user = await user_crud.create(
        db,
        UserCreate(email=payload.email, full_name=payload.full_name, password=payload.password),
        role=Role.VIEWER,
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
async def login(
    form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
) -> TokenPair:
    """OAuth2 password flow. ``username`` field carries the email."""
    user = await user_crud.authenticate(db, form.username, form.password)
    if user is None or not user.is_active:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _issue_tokens(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    try:
        claims = decode_token(payload.refresh_token)
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token.")
    if claims.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not a refresh token.")
    user = await user_crud.get(db, uuid.UUID(claims["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer active.")
    return _issue_tokens(user)


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
