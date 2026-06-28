"""Phase 6 tests: cache no-op behavior, dispatch inline path, and bulk import."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.crud import user as user_crud
from app.models.enums import Role
from app.schemas.user import UserCreate

PREFIX = "/api/v1"


async def _researcher(client: AsyncClient, db: AsyncSession) -> dict[str, str]:
    await user_crud.create(
        db, UserCreate(email="scale@atlas.example.com", password="password123",
                       role=Role.RESEARCHER),
        role=Role.RESEARCHER,
    )
    await db.commit()
    resp = await client.post(
        f"{PREFIX}/auth/login",
        data={"username": "scale@atlas.example.com", "password": "password123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_cache_disabled_is_noop():
    # With CACHE_ENABLED false (default in tests), the cache is transparent.
    assert await cache.graph_version() == 0
    await cache.invalidate_graph()  # must not raise
    calls = {"n": 0}

    async def compute():
        calls["n"] += 1
        return {"value": 42}

    a = await cache.cached_call("x", {"k": 1}, compute)
    b = await cache.cached_call("x", {"k": 1}, compute)
    assert a == b == {"value": 42}
    assert calls["n"] == 2  # never cached → computed every time


@pytest.mark.asyncio
async def test_bulk_import_creates_graph(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    payload = {
        "entities": [
            {"ref": "jane", "type": "person", "name": "Jane Powell"},
            {"ref": "globex", "type": "company", "name": "Globex",
             "properties": {"industry": "Energy"}},
            {"ref": "geneva", "type": "location", "name": "Geneva"},
        ],
        "relationships": [
            {"type": "WORKS_FOR", "source_ref": "jane", "target_ref": "globex"},
            {"type": "LOCATED_IN", "source_ref": "globex", "target_ref": "geneva"},
            {"type": "OWNS", "source_ref": "jane", "target_ref": "missing"},  # skipped
        ],
    }
    resp = await client.post(f"{PREFIX}/imports/bulk", headers=h, json=payload)
    assert resp.status_code == 201, resp.text
    result = resp.json()
    assert result["entities_created"] == 3
    assert result["relationships_created"] == 2
    assert result["skipped"] == 1

    # The imported entities are searchable / queryable.
    hits = (await client.get(f"{PREFIX}/search?q=Globex", headers=h)).json()
    assert any(hit["name"] == "Globex" for hit in hits)


@pytest.mark.asyncio
async def test_bulk_import_deduplicates(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    # Pre-create an entity.
    await client.post(f"{PREFIX}/entities", headers=h,
                      json={"type": "company", "name": "Acme"})

    payload = {
        "entities": [
            {"ref": "acme", "type": "company", "name": "Acme"},   # matches existing
            {"ref": "x", "type": "person", "name": "New Person"},
        ],
        "relationships": [
            {"type": "WORKS_FOR", "source_ref": "x", "target_ref": "acme"},
        ],
    }
    result = (await client.post(f"{PREFIX}/imports/bulk", headers=h, json=payload)).json()
    assert result["entities_matched"] == 1
    assert result["entities_created"] == 1
    assert result["relationships_created"] == 1


@pytest.mark.asyncio
async def test_bulk_import_empty_rejected(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    resp = await client.post(f"{PREFIX}/imports/bulk", headers=h,
                             json={"entities": [], "relationships": []})
    assert resp.status_code == 422
