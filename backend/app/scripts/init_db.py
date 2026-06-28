"""Create all tables directly from the ORM models (no Alembic).

For local development without Docker/Postgres: point ``DATABASE_URL`` at SQLite
(e.g. ``sqlite+aiosqlite:///./atlas.db``) and run::

    python -m app.scripts.init_db

This mirrors what the test suite does (``Base.metadata.create_all``) and avoids
the Postgres-specific Alembic migrations (pg_trgm indexes, etc.). For a real
Postgres deployment, use ``alembic upgrade head`` instead.
"""
from __future__ import annotations

import asyncio

import app.models  # noqa: F401 — import registers all tables on Base.metadata
from app.db.base import Base
from app.db.session import engine


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("All tables created.")


if __name__ == "__main__":
    asyncio.run(main())
