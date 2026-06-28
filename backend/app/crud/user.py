from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.enums import Role
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


async def get(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def list_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[User]:
    result = await db.execute(select(User).offset(skip).limit(limit).order_by(User.created_at))
    return list(result.scalars().all())


async def create(db: AsyncSession, data: UserCreate, *, role: Role | None = None) -> User:
    user = User(
        email=str(data.email),
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=role or data.role,
        clearance=data.clearance,
        compartments=data.compartments,
    )
    db.add(user)
    await db.flush()
    return user


async def update(db: AsyncSession, user: User, data: UserUpdate) -> User:
    fields = data.model_dump(exclude_unset=True)
    password = fields.pop("password", None)
    for key, value in fields.items():
        setattr(user, key, value)
    if password:
        user.hashed_password = hash_password(password)
    await db.flush()
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user
