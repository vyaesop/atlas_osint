"""Create the initial admin user from FIRST_ADMIN_* settings.

Idempotent: running it again when the admin already exists is a no-op.

    python -m app.scripts.seed_admin
"""
from __future__ import annotations

import asyncio

from app.core.config import settings
from app.crud import user as user_crud
from app.db.session import AsyncSessionLocal
from app.models.enums import Role
from app.schemas.user import UserCreate


async def main() -> None:
    async with AsyncSessionLocal() as db:
        existing = await user_crud.get_by_email(db, settings.FIRST_ADMIN_EMAIL)
        if existing:
            print(f"Admin {settings.FIRST_ADMIN_EMAIL} already exists; nothing to do.")
            return
        await user_crud.create(
            db,
            UserCreate(
                email=settings.FIRST_ADMIN_EMAIL,
                full_name="Atlas Administrator",
                password=settings.FIRST_ADMIN_PASSWORD,
                role=Role.ADMIN,
            ),
            role=Role.ADMIN,
        )
        await db.commit()
        print(f"Created admin user: {settings.FIRST_ADMIN_EMAIL}")


if __name__ == "__main__":
    asyncio.run(main())
