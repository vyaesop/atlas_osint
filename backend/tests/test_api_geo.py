"""End-to-end geospatial API tests (#7 map, #8 pattern-of-life, #9 co-location)."""
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
        db, UserCreate(email="geo@atlas.example.com", password="password123",
                       role=Role.RESEARCHER),
        role=Role.RESEARCHER,
    )
    await db.commit()
    resp = await client.post(
        f"{PREFIX}/auth/login",
        data={"username": "geo@atlas.example.com", "password": "password123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _entity(client, h, name, type_="person", props=None):
    return (await client.post(f"{PREFIX}/entities", headers=h, json={
        "type": type_, "name": name, "properties": props or {},
    })).json()


async def _located(client, h, person_id, place_id, start_date):
    return (await client.post(f"{PREFIX}/relationships", headers=h, json={
        "type": "LOCATED_IN", "source_id": person_id, "target_id": place_id,
        "start_date": start_date, "confidence_score": 0.8,
    })).json()


async def _scenario(client, h):
    addis = await _entity(client, h, "Addis Ababa", "location",
                          {"latitude": 9.03, "longitude": 38.74})
    london = await _entity(client, h, "London", "location",
                           {"latitude": 51.5074, "longitude": -0.1278})
    p1 = await _entity(client, h, "Alice")
    p2 = await _entity(client, h, "Bob")
    await _located(client, h, p1["id"], addis["id"], "2020-01-01")
    await _located(client, h, p1["id"], london["id"], "2020-03-01")
    await _located(client, h, p2["id"], addis["id"], "2020-01-03")  # near Alice in time
    return {"addis": addis, "london": london, "p1": p1, "p2": p2}


@pytest.mark.asyncio
async def test_map_places_entities(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    s = await _scenario(client, h)
    body = (await client.get(f"{PREFIX}/geo/map", headers=h)).json()
    by_id = {f["id"]: f for f in body["features"]}
    # Locations placed by their own coords; people placed via LOCATED_IN.
    assert by_id[s["addis"]["id"]]["placed_via"] == "self"
    assert by_id[s["p1"]["id"]]["placed_via"] == "located_in"
    assert by_id[s["p1"]["id"]]["lat"] in (9.03, 51.5074)


@pytest.mark.asyncio
async def test_pattern_of_life(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    s = await _scenario(client, h)
    body = (await client.get(f"{PREFIX}/geo/pattern-of-life/{s['p1']['id']}", headers=h)).json()
    assert body["place_count"] == 2
    # Two dated visits → a positive travelled distance (Addis → London).
    assert body["total_distance_km"] > 1000
    assert [v["location_name"] for v in body["visits"]] == ["Addis Ababa", "London"]


@pytest.mark.asyncio
async def test_colocation_suggests_edge(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    s = await _scenario(client, h)
    body = (await client.get(f"{PREFIX}/geo/colocation?window_days=7", headers=h)).json()
    assert body["pairs"], "expected at least one co-located pair"
    top = body["pairs"][0]
    assert {top["a_id"], top["b_id"]} == {s["p1"]["id"], s["p2"]["id"]}
    assert top["location_name"] == "Addis Ababa"
    assert top["temporally_overlapping"] is True
    assert top["already_connected"] is False
    assert top["suggested_type"] == "ASSOCIATED_WITH"
