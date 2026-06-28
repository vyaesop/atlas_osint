from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import Role


class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = None
    role: Role = Role.VIEWER


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(BaseModel):
    """Public self-registration. Always creates a VIEWER; role is admin-only."""
    email: EmailStr
    full_name: str | None = None
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
