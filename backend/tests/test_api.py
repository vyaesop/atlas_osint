"""End-to-end API tests: auth, RBAC, and the full entity→relationship→evidence flow."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import user as user_crud
from app.models.enums import Role
from app.schemas.user import UserCreate

PREFIX = "/api/v1"


async def _make_user(db: AsyncSession, email: str, role: Role) -> None:
    await user_crud.create(
        db, UserCreate(email=email, password="password123", role=role), role=role
    )
    await db.commit()


async def _auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post(
        f"{PREFIX}/auth/login", data={"username": email, "password": "password123"}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    resp = await client.post(
        f"{PREFIX}/auth/register",
        json={"email": "viewer@atlas.example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "viewer"

    headers = await _auth_headers(client, "viewer@atlas.example.com")
    me = await client.get(f"{PREFIX}/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "viewer@atlas.example.com"


@pytest.mark.asyncio
async def test_viewer_cannot_create_entity(client: AsyncClient, db_session: AsyncSession):
    await _make_user(db_session, "v@atlas.example.com", Role.VIEWER)
    headers = await _auth_headers(client, "v@atlas.example.com")
    resp = await client.post(
        f"{PREFIX}/entities",
        headers=headers,
        json={"type": "person", "name": "Blocked"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_rejected(client: AsyncClient):
    resp = await client.get(f"{PREFIX}/entities")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_full_graph_flow(client: AsyncClient, db_session: AsyncSession):
    await _make_user(db_session, "r@atlas.example.com", Role.RESEARCHER)
    headers = await _auth_headers(client, "r@atlas.example.com")

    # Create two entities.
    person = (await client.post(
        f"{PREFIX}/entities", headers=headers,
        json={"type": "person", "name": "Jane Doe",
              "properties": {"occupation": "CEO"}},
    )).json()
    company = (await client.post(
        f"{PREFIX}/entities", headers=headers,
        json={"type": "company", "name": "Globex",
              "properties": {"industry": "Tech", "market_value": 1000.0}},
    )).json()

    # Link them.
    rel_resp = await client.post(
        f"{PREFIX}/relationships", headers=headers,
        json={"type": "WORKS_FOR", "source_id": person["id"],
              "target_id": company["id"], "confidence_score": 0.8},
    )
    assert rel_resp.status_code == 201, rel_resp.text
    rel = rel_resp.json()

    # Attach evidence to the relationship; source_count should bump to 1.
    ev_resp = await client.post(
        f"{PREFIX}/evidence", headers=headers,
        json={"title": "Annual report 2024", "relationship_id": rel["id"],
              "reliability_score": 0.9, "url": "https://example.com/report"},
    )
    assert ev_resp.status_code == 201, ev_resp.text

    refreshed = (await client.get(f"{PREFIX}/relationships/{rel['id']}", headers=headers)).json()
    assert refreshed["source_count"] == 1

    # Relationships filtered by entity returns our edge.
    listed = (await client.get(
        f"{PREFIX}/relationships?entity_id={person['id']}", headers=headers
    )).json()
    assert len(listed) == 1
    assert listed[0]["type"] == "WORKS_FOR"


@pytest.mark.asyncio
async def test_self_loop_rejected(client: AsyncClient, db_session: AsyncSession):
    await _make_user(db_session, "r2@atlas.example.com", Role.RESEARCHER)
    headers = await _auth_headers(client, "r2@atlas.example.com")
    ent = (await client.post(
        f"{PREFIX}/entities", headers=headers,
        json={"type": "person", "name": "Loner"},
    )).json()
    resp = await client.post(
        f"{PREFIX}/relationships", headers=headers,
        json={"type": "CONNECTED_TO", "source_id": ent["id"], "target_id": ent["id"]},
    )
    assert resp.status_code == 422
