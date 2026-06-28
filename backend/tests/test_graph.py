"""Tests for the graph neighborhood endpoint."""
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
        db, UserCreate(email="g@atlas.example.com", password="password123",
                       role=Role.RESEARCHER),
        role=Role.RESEARCHER,
    )
    await db.commit()
    resp = await client.post(
        f"{PREFIX}/auth/login",
        data={"username": "g@atlas.example.com", "password": "password123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_neighbors_returns_subgraph(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    center = (await client.post(f"{PREFIX}/entities", headers=h,
              json={"type": "person", "name": "Hub"})).json()
    a = (await client.post(f"{PREFIX}/entities", headers=h,
         json={"type": "company", "name": "A Corp"})).json()
    b = (await client.post(f"{PREFIX}/entities", headers=h,
         json={"type": "company", "name": "B Corp"})).json()

    await client.post(f"{PREFIX}/relationships", headers=h,
                      json={"type": "WORKS_FOR", "source_id": center["id"], "target_id": a["id"]})
    await client.post(f"{PREFIX}/relationships", headers=h,
                      json={"type": "OWNS", "source_id": center["id"], "target_id": b["id"]})

    graph = (await client.get(f"{PREFIX}/graph/entities/{center['id']}/neighbors", headers=h)).json()
    node_ids = {n["id"] for n in graph["nodes"]}
    assert node_ids == {center["id"], a["id"], b["id"]}
    assert len(graph["edges"]) == 2
