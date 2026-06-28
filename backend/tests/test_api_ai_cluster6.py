"""Cluster 6 tests: alert feed (#28) and NL→graph query (#24, heuristic)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.assistant import HeuristicAssistant
from app.crud import user as user_crud
from app.models.enums import Role
from app.schemas.user import UserCreate

PREFIX = "/api/v1"


async def _researcher(client: AsyncClient, db: AsyncSession, email="c6@atlas.example.com") -> dict[str, str]:
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


async def _rel(client, h, s, t, type_="WORKS_FOR"):
    return (await client.post(f"{PREFIX}/relationships", headers=h,
            json={"type": type_, "source_id": s, "target_id": t, "confidence_score": 0.9})).json()


async def _evidence(client, h, entity_id, stance):
    ev = (await client.post(f"{PREFIX}/evidence", headers=h, json={
        "title": f"{stance} src", "entity_id": entity_id, "stance": stance,
        "source_reliability": "A", "info_credibility": "1",
    })).json()
    await client.post(f"{PREFIX}/evidence/{ev['id']}/verify", headers=h, json={"status": "verified"})
    return ev


# --- #28 alerts --- #

@pytest.mark.asyncio
async def test_contradiction_alert(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    ent = await _entity(client, h, "Disputed Person")
    await _evidence(client, h, ent["id"], "supports")
    await _evidence(client, h, ent["id"], "contradicts")

    body = (await client.get(f"{PREFIX}/alerts?kind=contradiction", headers=h)).json()
    assert body["count"] >= 1
    top = body["alerts"][0]
    assert top["kind"] == "contradiction" and top["entity_id"] == ent["id"]


@pytest.mark.asyncio
async def test_anomaly_and_sanctions_alerts(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    hub = await _entity(client, h, "Mr Hub")
    for i in range(8):
        leaf = await _entity(client, h, f"leaf{i}")
        await _rel(client, h, hub["id"], leaf["id"])
    # Watchlist match on the hub.
    await client.post(f"{PREFIX}/sanctions/watchlist", headers=h,
                      json={"entries": [{"name": "Mr Hub", "program": "OFAC-SDN"}]})

    body = (await client.get(f"{PREFIX}/alerts", headers=h)).json()
    kinds = {a["kind"] for a in body["alerts"]}
    assert "anomaly" in kinds
    assert "sanctions" in kinds
    # High-severity sanctions alert sorts above medium anomalies.
    assert body["alerts"][0]["severity"] == "high"


# --- #24 NL query (heuristic parse) --- #

def test_heuristic_parse_intents():
    a = HeuristicAssistant()
    assert a.parse("find all people named Smith").intent == "search"
    assert a.parse("find all people named Smith").entity_type.value == "person"
    assert a.parse("who is connected to Acme Corp").intent == "neighbors"
    assert a.parse("connected to Acme Corp").name == "Acme Corp"
    p = a.parse("show the connection between Alice and Bob")
    assert p.intent == "path" and p.name == "Alice" and p.target_name == "Bob"


@pytest.mark.asyncio
async def test_nl_query_search_and_neighbors(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    alice = await _entity(client, h, "Alice Anderson")
    acme = await _entity(client, h, "Acme Corp", "company")
    await _rel(client, h, alice["id"], acme["id"])

    # search
    s = (await client.post(f"{PREFIX}/ai/query", headers=h,
         json={"question": "find companies named Acme"})).json()
    assert s["intent"] == "search"
    assert any(e["name"] == "Acme Corp" for e in s["entities"])

    # neighbors
    n = (await client.post(f"{PREFIX}/ai/query", headers=h,
         json={"question": "who is connected to Acme Corp"})).json()
    assert n["intent"] == "neighbors"
    assert any(e["name"] == "Alice Anderson" for e in n["entities"])

    # path
    p = (await client.post(f"{PREFIX}/ai/query", headers=h,
         json={"question": "connection between Alice Anderson and Acme Corp"})).json()
    assert p["intent"] == "path" and p["path"] is not None
    assert len(p["path"]["nodes"]) == 2  # Alice — Acme, one hop


# --- #26 intelligence report --- #

@pytest.mark.asyncio
async def test_intelligence_report(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session, email="rep@atlas.example.com")
    target = await _entity(client, h, "Target Subject")
    org = await _entity(client, h, "Front Company", "company")
    await _rel(client, h, target["id"], org["id"])

    resp = await client.post(f"{PREFIX}/ai/report/entity/{target['id']}", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["subject"]["name"] == "Target Subject"
    assert body["key_findings"]  # deterministic findings always present
    assert "estimative_label" in body["confidence"]
    assert isinstance(body["narrative"], str)
    assert body["dashboard"]["entity"]["id"] == target["id"]


@pytest.mark.asyncio
async def test_report_404_for_missing_entity(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session, email="rep404@atlas.example.com")
    import uuid as _uuid
    resp = await client.post(f"{PREFIX}/ai/report/entity/{_uuid.uuid4()}", headers=h)
    assert resp.status_code == 404
