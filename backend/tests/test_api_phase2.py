"""End-to-end Phase 2 API tests: confidence lifecycle, verification, and search."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import user as user_crud
from app.models.enums import Role
from app.schemas.user import UserCreate

PREFIX = "/api/v1"


async def _researcher(client: AsyncClient, db: AsyncSession) -> dict[str, str]:
    await user_crud.create(
        db, UserCreate(email="p2@atlas.example.com", password="password123",
                       role=Role.RESEARCHER),
        role=Role.RESEARCHER,
    )
    await db.commit()
    resp = await client.post(
        f"{PREFIX}/auth/login",
        data={"username": "p2@atlas.example.com", "password": "password123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_confidence_requires_verified_evidence(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)

    entity = (await client.post(
        f"{PREFIX}/entities", headers=h,
        json={"type": "person", "name": "Subject A"},
    )).json()

    ev = (await client.post(
        f"{PREFIX}/evidence", headers=h,
        json={"title": "Filing", "entity_id": entity["id"],
              "reliability_score": 1.0, "stance": "supports"},
    )).json()

    # Unverified evidence -> confidence still zero.
    summary = (await client.get(f"{PREFIX}/entities/{entity['id']}/confidence", headers=h)).json()
    assert summary["score"] == 0.0
    assert summary["supporting_count"] == 0  # only verified are counted

    # Verify it -> confidence rises and entity score is persisted.
    await client.post(f"{PREFIX}/evidence/{ev['id']}/verify", headers=h,
                      json={"status": "verified"})
    summary = (await client.get(f"{PREFIX}/entities/{entity['id']}/confidence", headers=h)).json()
    assert summary["score"] > 0.0
    assert summary["supporting_count"] == 1

    refreshed = (await client.get(f"{PREFIX}/entities/{entity['id']}", headers=h)).json()
    assert refreshed["confidence_score"] == summary["score"]


@pytest.mark.asyncio
async def test_contradiction_flagged(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    rel_source = (await client.post(f"{PREFIX}/entities", headers=h,
                  json={"type": "person", "name": "Alice"})).json()
    rel_target = (await client.post(f"{PREFIX}/entities", headers=h,
                  json={"type": "company", "name": "Widget Corp"})).json()
    rel = (await client.post(f"{PREFIX}/relationships", headers=h,
           json={"type": "WORKS_FOR", "source_id": rel_source["id"],
                 "target_id": rel_target["id"]})).json()

    for stance in ("supports", "contradicts"):
        ev = (await client.post(f"{PREFIX}/evidence", headers=h,
              json={"title": stance, "relationship_id": rel["id"],
                    "reliability_score": 0.9, "stance": stance})).json()
        await client.post(f"{PREFIX}/evidence/{ev['id']}/verify", headers=h,
                          json={"status": "verified"})

    summary = (await client.get(f"{PREFIX}/relationships/{rel['id']}/confidence", headers=h)).json()
    assert summary["is_contradicted"] is True
    assert summary["supporting_count"] == 1
    assert summary["contradicting_count"] == 1


@pytest.mark.asyncio
async def test_search_and_suggest_endpoints(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    await client.post(f"{PREFIX}/entities", headers=h,
                      json={"type": "person", "name": "Vladimir Petrov",
                            "aliases": ["V. Petrov"]})
    await client.post(f"{PREFIX}/entities", headers=h,
                      json={"type": "company", "name": "Petra Industries"})

    # Fuzzy: typo still finds the person.
    hits = (await client.get(f"{PREFIX}/search?q=Vladmir&semantic=false", headers=h)).json()
    assert any(hit["name"] == "Vladimir Petrov" for hit in hits)

    # Type filter.
    hits = (await client.get(f"{PREFIX}/search?q=Petr&type=company", headers=h)).json()
    assert all(hit["type"] == "company" for hit in hits)

    # Suggest.
    sugg = (await client.get(f"{PREFIX}/search/suggest?q=vlad", headers=h)).json()
    assert any(s["name"] == "Vladimir Petrov" for s in sugg)
