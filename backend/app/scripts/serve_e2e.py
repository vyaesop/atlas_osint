"""Bootstrap an ephemeral SQLite DB + seeded admin, then serve the API.

Used only by the Playwright end-to-end smoke test (see
``frontend/playwright.config.ts``). Keeping the whole bootstrap in one Python
entrypoint means the Playwright ``webServer`` command needs no shell operators,
so it behaves identically on a developer's Windows box and on Linux CI.

    DATABASE_URL=sqlite+aiosqlite:///./e2e.db python -m app.scripts.serve_e2e
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import uvicorn

from app.core.config import settings
from app.scripts.init_db import main as create_tables
from app.scripts.seed_admin import main as seed_admin


def _reset_local_sqlite() -> None:
    """If pointed at a local SQLite file, delete it so each e2e run is hermetic
    (a stale DB from a previous run would keep an old admin hash and break the
    seeded-login smoke test)."""
    url = settings.SQLALCHEMY_DATABASE_URI
    if "sqlite" not in url or ":///" not in url:
        return
    db_path = Path(url.split(":///", 1)[1])  # e.g. ./e2e.db
    if db_path.suffix and db_path.exists():
        db_path.unlink()


async def _bootstrap() -> None:
    _reset_local_sqlite()
    await create_tables()
    await seed_admin()


def main() -> None:
    asyncio.run(_bootstrap())
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=int(os.environ.get("E2E_BACKEND_PORT", "8000")),
        log_level="warning",
    )


if __name__ == "__main__":
    main()
