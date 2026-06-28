"""End-to-end entity-resolution tests: detect duplicates, merge, unmerge (#13)."""
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
        db, UserCreate(email="er@atlas.example.com", password="password123",
                       role=Role.RESEARCHER),
        role=Role.RESEARCHER,
    )
    await db.commit()
    resp = await client.post(
        f"{PREFIX}/auth/login",
        data={"username": "er@atlas.example.com", "password": "password123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _entity(client, h, name, type_="person", aliases=None):
    return (await client.post(f"{PREFIX}/entities", headers=h, json={
        "type": type_, "name": name, "aliases": aliases or [],
    })).json()


async def _rel(client, h, s, t, type_="WORKS_FOR"):
    return (await client.post(f"{PREFIX}/relationships", headers=h, json={
        "type": type_, "source_id": s, "target_id": t, "confidence_score": 0.9,
    })).json()


@pytest.mark.asyncio
async def test_find_duplicates(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    await _entity(client, h, "John Smith")
    await _entity(client, h, "john smith")
    await _entity(client, h, "Totally Different")

    body = (await client.get(f"{PREFIX}/resolution/duplicates?threshold=0.85", headers=h)).json()
    assert body["candidates"], "expected a duplicate candidate"
    names = {body["candidates"][0]["a_name"].lower(), body["candidates"][0]["b_name"].lower()}
    assert names == {"john smith"}


@pytest.mark.asyncio
async def test_merge_and_unmerge_roundtrip(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    keep = await _entity(client, h, "Acme Corp", "company")
    dupe = await _entity(client, h, "ACME Corporation", "company", aliases=["ACME"])
    org = await _entity(client, h, "Globex", "company")
    # The duplicate has a relationship that should move onto the kept entity.
    await _rel(client, h, dupe["id"], org["id"], type_="PARTNER_OF")

    # --- merge ---
    merged = await client.post(f"{PREFIX}/resolution/merge", headers=h,
                               json={"kept_id": keep["id"], "merged_id": dupe["id"]})
    assert merged.status_code == 200
    result = merged.json()
    assert result["moved_relationships"] == 1
    merge_id = result["merge"]["id"]
    assert "ACME Corporation" in result["merge"]["added_aliases"]

    # Duplicate is gone; its relationship now belongs to the kept entity.
    assert (await client.get(f"{PREFIX}/entities/{dupe['id']}", headers=h)).status_code == 404
    kept_rels = (await client.get(f"{PREFIX}/relationships?entity_id={keep['id']}", headers=h)).json()
    assert any(r["source_id"] == keep["id"] and r["target_id"] == org["id"] for r in kept_rels)

    # --- unmerge ---
    undo = await client.post(f"{PREFIX}/resolution/merges/{merge_id}/unmerge", headers=h)
    assert undo.status_code == 200
    assert undo.json()["undone"] is True

    # The duplicate is restored and its relationship moved back.
    restored = await client.get(f"{PREFIX}/entities/{dupe['id']}", headers=h)
    assert restored.status_code == 200
    dupe_rels = (await client.get(f"{PREFIX}/relationships?entity_id={dupe['id']}", headers=h)).json()
    assert any(r["source_id"] == dupe["id"] and r["target_id"] == org["id"] for r in dupe_rels)

    # A second unmerge is rejected.
    again = await client.post(f"{PREFIX}/resolution/merges/{merge_id}/unmerge", headers=h)
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_merge_requires_same_type(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    person = await _entity(client, h, "X", "person")
    company = await _entity(client, h, "X", "company")
    resp = await client.post(f"{PREFIX}/resolution/merge", headers=h,
                             json={"kept_id": person["id"], "merged_id": company["id"]})
    assert resp.status_code == 422
