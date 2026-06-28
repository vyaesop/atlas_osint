"""End-to-end analytics API tests over a small graph built through the API."""
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
        db, UserCreate(email="an@atlas.example.com", password="password123",
                       role=Role.RESEARCHER),
        role=Role.RESEARCHER,
    )
    await db.commit()
    resp = await client.post(
        f"{PREFIX}/auth/login",
        data={"username": "an@atlas.example.com", "password": "password123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _entity(client, h, name, type_="person"):
    return (await client.post(f"{PREFIX}/entities", headers=h,
            json={"type": type_, "name": name})).json()


async def _rel(client, h, s, t, conf=1.0, type_="CONNECTED_TO"):
    return (await client.post(f"{PREFIX}/relationships", headers=h,
            json={"type": type_, "source_id": s, "target_id": t,
                  "confidence_score": conf})).json()


@pytest.mark.asyncio
async def test_centrality_endpoint(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    hub = await _entity(client, h, "Hub")
    for name in ("A", "B", "C"):
        leaf = await _entity(client, h, name)
        await _rel(client, h, hub["id"], leaf["id"])

    resp = await client.get(f"{PREFIX}/analytics/centrality?metric=degree", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["metric"] == "degree"
    assert body["results"][0]["name"] == "Hub"
    assert body["graph_order"] == 4


@pytest.mark.asyncio
async def test_communities_endpoint(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    # Two triangles + weak bridge.
    ids = {n: (await _entity(client, h, n))["id"] for n in ("a", "b", "c", "x", "y", "z")}
    for s, t in [("a", "b"), ("b", "c"), ("a", "c"), ("x", "y"), ("y", "z"), ("x", "z")]:
        await _rel(client, h, ids[s], ids[t], conf=1.0)
    await _rel(client, h, ids["c"], ids["x"], conf=0.1)

    resp = await client.get(f"{PREFIX}/analytics/communities?min_size=2", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["community_count"] == 2


@pytest.mark.asyncio
async def test_paths_endpoint_strongest(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    a = await _entity(client, h, "A")
    b = await _entity(client, h, "B")
    c = await _entity(client, h, "C")
    await _rel(client, h, a["id"], c["id"], conf=0.1)   # weak direct
    await _rel(client, h, a["id"], b["id"], conf=0.9)
    await _rel(client, h, b["id"], c["id"], conf=0.9)

    resp = await client.get(
        f"{PREFIX}/analytics/paths?source={a['id']}&target={c['id']}&kind=strongest",
        headers=h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    names = [n["name"] for n in body["paths"][0]["nodes"]]
    assert names == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_paths_not_found(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    a = await _entity(client, h, "Lonely A")
    b = await _entity(client, h, "Lonely B")
    resp = await client.get(
        f"{PREFIX}/analytics/paths?source={a['id']}&target={b['id']}", headers=h
    )
    assert resp.status_code == 200
    assert resp.json()["found"] is False


async def _two_triangles_bridge(client, h):
    """Triangle {a,b,c} + {x,y,z} joined only through c—x. Returns id map."""
    ids = {n: (await _entity(client, h, n))["id"] for n in ("a", "b", "c", "x", "y", "z")}
    for s, t in [("a", "b"), ("b", "c"), ("a", "c"), ("x", "y"), ("y", "z"), ("x", "z")]:
        await _rel(client, h, ids[s], ids[t], conf=1.0)
    await _rel(client, h, ids["c"], ids["x"], conf=0.4)
    return ids


@pytest.mark.asyncio
async def test_brokers_endpoint(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    ids = await _two_triangles_bridge(client, h)
    resp = await client.get(f"{PREFIX}/analytics/brokers", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    bridge_pairs = {frozenset((e["source"], e["target"])) for e in body["bridges"]}
    assert frozenset((ids["c"], ids["x"])) in bridge_pairs
    articulations = {b["id"] for b in body["brokers"] if b["is_articulation"]}
    assert {ids["c"], ids["x"]} <= articulations


@pytest.mark.asyncio
async def test_roles_endpoint(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    await _two_triangles_bridge(client, h)
    resp = await client.get(f"{PREFIX}/analytics/roles", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["counts"]
    assert all("role" in r and "rationale" in r for r in body["roles"])


@pytest.mark.asyncio
async def test_resilience_and_anomalies_endpoints(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    ids = await _two_triangles_bridge(client, h)
    res = await client.get(f"{PREFIX}/analytics/resilience", headers=h)
    assert res.status_code == 200
    top = res.json()["impacts"][0]
    assert top["id"] in {ids["c"], ids["x"]}
    assert top["components_after"] >= 2

    anom = await client.get(f"{PREFIX}/analytics/anomalies?z_threshold=1.0", headers=h)
    assert anom.status_code == 200
    assert "anomalies" in anom.json()


@pytest.mark.asyncio
async def test_influence_endpoint(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    a = await _entity(client, h, "A")
    b = await _entity(client, h, "B")
    c = await _entity(client, h, "C")
    await _rel(client, h, a["id"], b["id"], conf=1.0)
    await _rel(client, h, b["id"], c["id"], conf=1.0)
    resp = await client.get(f"{PREFIX}/analytics/influence?seed={a['id']}&trials=30", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["expected_spread"] == 3.0  # certain edges reach the whole chain


@pytest.mark.asyncio
async def test_motifs_endpoint(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    ids = {n: (await _entity(client, h, n))["id"] for n in ("a", "b", "c")}
    for s, t in [("a", "b"), ("b", "c"), ("a", "c")]:
        await _rel(client, h, ids[s], ids[t], conf=1.0)
    resp = await client.get(f"{PREFIX}/analytics/motifs", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["triangle_count"] == 1
    assert any(m["kind"] == "triangle" for m in body["motifs"])
