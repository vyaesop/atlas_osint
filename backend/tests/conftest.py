"""Test fixtures: in-memory SQLite DB + ASGI client with deps overridden.

Neo4j is not exercised here — graph projection is best-effort and swallows
errors, and ASGITransport does not run the app lifespan, so the driver is never
initialized. CRUD correctness is verified against SQLite.

A single in-memory connection is shared (StaticPool) so committed data is
visible across sessions, while each API request still gets its own session —
mirroring production, where ``get_db`` yields a fresh session per request.
"""
from __future__ import annotations

import os

# Force a deterministic, offline AI provider for tests regardless of any local
# .env (which may select Gemini for running the app). OS env overrides .env in
# pydantic-settings, and this runs before app modules construct their settings.
os.environ["AI_PROVIDER"] = "heuristic"
os.environ["NEO4J_ENABLED"] = "false"

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  -- register tables (import before binding `app` name)
from app.db.base import Base
from app.db.session import get_db
from app.main import app as fastapi_app


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _reset_search_index():
    """The in-memory search backend is a process singleton; clear it per test."""
    from app.search.inmemory import InMemorySearchBackend
    from app.search.service import search_service

    backend = search_service.backend
    if isinstance(backend, InMemorySearchBackend):
        backend.clear()
    yield
    if isinstance(backend, InMemorySearchBackend):
        backend.clear()


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(session_factory) -> AsyncGenerator[AsyncSession, None]:
    """Session for test-side setup (creating users, etc.)."""
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(session_factory) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db():
        async with session_factory() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()
