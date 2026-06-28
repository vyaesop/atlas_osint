"""Cluster 9 backend tests: risk (#49), diff (#47), lineage (#5), facets (#46)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import user as user_crud
from app.models.enums import Role
from app.schemas.user import UserCreate

PREFIX = "/api/v1"


async def _researcher(client, db, email="ins@a.com") -> dict[str, str]:
    await user_crud.create(
        db, UserCreate(email=email, password="password123", role=Role.RESEARCHER),
        role=Role.RESEARCHER,
    )
    await db.commit()
    resp = await client.post(f"{PREFIX}/auth/login",
                             data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _entity(client, h, name, type_="person"):
    return (await client.post(f"{PREFIX}/entities", headers=h,
            json={"type": type_, "name": name})).json()


async def _rel(client, h, s, t):
    return (await client.post(f"{PREFIX}/relationships", headers=h,
            json={"type": "ASSOCIATED_WITH", "source_id": s, "target_id": t,
                  "confidence_score": 0.8})).json()


# --- #49 risk --- #

@pytest.mark.asyncio
async def test_risk_elevated_by_sanctions(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    suspect = await _entity(client, h, "Viktor Sanctioned")
    clean = await _entity(client, h, "Ordinary Citizen")
    await client.post(f"{PREFIX}/sanctions/watchlist", headers=h,
                      json={"entries": [{"name": "Viktor Sanctioned", "program": "OFAC"}]})

    risky = (await client.get(f"{PREFIX}/insights/risk/{suspect['id']}", headers=h)).json()
    assert risky["factors"]["sanctions_hit"] == 1.0
    assert risky["band"] in {"medium", "high"}

    low = (await client.get(f"{PREFIX}/insights/risk/{clean['id']}", headers=h)).json()
    assert low["band"] == "low"

    top = (await client.get(f"{PREFIX}/insights/risk", headers=h)).json()
    assert top["results"][0]["entity_id"] == suspect["id"]


# --- #47 diff --- #

@pytest.mark.asyncio
async def test_network_diff_added_and_bounds(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session, "diff@a.com")
    a = await _entity(client, h, "Alpha")
    await _entity(client, h, "Beta")

    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    # Pass timestamps via params so httpx encodes "+" in the offset correctly.
    since_past = (await client.get(f"{PREFIX}/insights/diff", headers=h,
                                   params={"since": past})).json()
    assert len(since_past["added_entities"]) >= 2

    since_future = (await client.get(f"{PREFIX}/insights/diff", headers=h,
                                     params={"since": future})).json()
    assert since_future["added_entities"] == []

    # Delete → shows up under removed.
    await client.delete(f"{PREFIX}/entities/{a['id']}", headers=h)
    after_del = (await client.get(f"{PREFIX}/insights/diff", headers=h,
                                  params={"since": past})).json()
    assert any(r["id"] == a["id"] for r in after_del["removed"])


# --- #5 lineage --- #

@pytest.mark.asyncio
async def test_lineage_from_ingestion(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session, "lin@a.com")
    ingest = (await client.post(f"{PREFIX}/ingestion/text", headers=h, json={
        "title": "Source Memo",
        "text": "Jane Powell founded Globex Corporation."})).json()
    # Pick an AI-extracted entity from the ingestion.
    ent = next(e for e in ingest["entities"] if e["type"] != "document")

    lineage = (await client.get(f"{PREFIX}/insights/lineage/{ent['id']}", headers=h)).json()
    kinds = {n["kind"] for n in lineage["nodes"]}
    assert "entity" in kinds and "evidence" in kinds
    assert "AI-extracted" in lineage["summary"]
    assert lineage["edges"]


# --- #46 facets --- #

@pytest.mark.asyncio
async def test_facets_counts(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session, "fac@a.com")
    await _entity(client, h, "P1", "person")
    await _entity(client, h, "P2", "person")
    await _entity(client, h, "C1", "company")

    facets = (await client.get(f"{PREFIX}/insights/facets", headers=h)).json()
    assert facets["total"] == 3
    type_counts = {b["value"]: b["count"] for b in facets["by_type"]}
    assert type_counts["person"] == 2 and type_counts["company"] == 1
    # Everything defaults to unclassified, analyst-entered.
    assert any(b["value"] == "unclassified" for b in facets["by_classification"])
    assert any(b["value"] == "analyst_entered" for b in facets["by_provenance"])
