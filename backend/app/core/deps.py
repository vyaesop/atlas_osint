"""FastAPI dependencies: current user resolution and role-based access control."""
from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import JWTError, decode_token
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")

_credentials_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_token(token)
    except JWTError:
        raise _credentials_exc

    if payload.get("type") != "access":
        raise _credentials_exc

    sub = payload.get("sub")
    if sub is None:
        raise _credentials_exc

    try:
        user_id = uuid.UUID(sub)
    except (ValueError, TypeError):
        raise _credentials_exc

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise _credentials_exc
    return user


# Role hierarchy: higher number => more privilege.
_ROLE_RANK = {Role.VIEWER: 0, Role.RESEARCHER: 1, Role.ADMIN: 2}


def require_role(minimum: Role) -> Callable[[User], User]:
    """Dependency factory enforcing at least ``minimum`` role."""

    async def _checker(current_user: User = Depends(get_current_user)) -> User:
        if _ROLE_RANK[current_user.role] < _ROLE_RANK[minimum]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires '{minimum.value}' role or higher.",
            )
        return current_user

    return _checker


# Convenience dependencies.
require_viewer = require_role(Role.VIEWER)
require_researcher = require_role(Role.RESEARCHER)
require_admin = require_role(Role.ADMIN)
