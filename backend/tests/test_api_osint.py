"""End-to-end Cluster 5 OSINT tests: transforms (#17), sanctions (#18),
email comms (#22), crypto import (#23)."""
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
        db, UserCreate(email="osint@atlas.example.com", password="password123",
                       role=Role.RESEARCHER),
        role=Role.RESEARCHER,
    )
    await db.commit()
    resp = await client.post(
        f"{PREFIX}/auth/login",
        data={"username": "osint@atlas.example.com", "password": "password123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _entity(client, h, name, type_="person", props=None):
    return (await client.post(f"{PREFIX}/entities", headers=h, json={
        "type": type_, "name": name, "properties": props or {},
    })).json()


# --- #17 transforms ---

@pytest.mark.asyncio
async def test_transform_list_and_run_with_persist(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    listed = (await client.get(f"{PREFIX}/transforms", headers=h)).json()
    assert any(t["name"] == "extract-selectors" for t in listed)

    ent = await _entity(client, h, "Suspect One",
                        props={"biography": "Reachable at ops@darkmail.net and 0x52908400098527886E0F7030069857D2E4169EE7"})
    run = await client.post(f"{PREFIX}/transforms/extract-selectors/run", headers=h,
                            json={"entity_id": ent["id"], "persist": True})
    assert run.status_code == 200
    body = run.json()
    kinds = {s["kind"] for s in body["selectors"]}
    assert "email" in kinds and "eth_address" in kinds
    # Persisted ASSET nodes linked back to the entity.
    assert len(body["created_entities"]) >= 2
    assert all(e["type"] == "asset" for e in body["created_entities"])
    assert len(body["created_relationships"]) >= 2


@pytest.mark.asyncio
async def test_transform_text_only_no_persist(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    run = await client.post(f"{PREFIX}/transforms/extract-selectors/run", headers=h,
                            json={"text": "mail me a@b.com"})
    assert run.status_code == 200
    assert run.json()["created_entities"] == []


# --- #18 sanctions ---

@pytest.mark.asyncio
async def test_sanctions_screening(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    await client.post(f"{PREFIX}/sanctions/watchlist", headers=h, json={
        "entries": [
            {"name": "Vladimir Petrov", "aliases": ["V. Petrov"], "program": "OFAC-SDN"},
            {"name": "Globex Holdings", "program": "EU"},
        ]
    })
    suspect = await _entity(client, h, "vladimir petrov")
    clean = await _entity(client, h, "Jane Ordinary")

    hit = (await client.get(f"{PREFIX}/sanctions/screen/{suspect['id']}", headers=h)).json()
    assert hit["hits"] and hit["hits"][0]["entry_name"] == "Vladimir Petrov"
    assert hit["hits"][0]["program"] == "OFAC-SDN"

    no_hit = (await client.get(f"{PREFIX}/sanctions/screen/{clean['id']}", headers=h)).json()
    assert no_hit["hits"] == []

    scan = (await client.get(f"{PREFIX}/sanctions/scan?threshold=0.85", headers=h)).json()
    assert any(x["entity_name"].lower() == "vladimir petrov" for x in scan["hits"])


# --- #22 email comms ---

EML = """From: Alice Boss <alice@corp.com>
To: Bob Worker <bob@corp.com>, Carol <carol@corp.com>
Subject: Q3 plan
Date: Mon, 02 Mar 2020 10:00:00 +0000

Let's meet about the plan.
"""


@pytest.mark.asyncio
async def test_email_ingestion_builds_comms_network(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    resp = await client.post(f"{PREFIX}/ingestion/email", headers=h,
                             json={"title": "Mailbox dump", "content": EML})
    assert resp.status_code == 201
    body = resp.json()
    # Alice + Bob + Carol = 3 people, sender→2 recipients = 2 edges.
    names = {e["name"] for e in body["entities"]}
    assert {"Alice Boss", "Bob Worker", "Carol"} <= names
    assert body["summary"]["relationships_created"] == 2


# --- #23 crypto ---

@pytest.mark.asyncio
async def test_crypto_import_builds_flow_graph(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    resp = await client.post(f"{PREFIX}/ingestion/crypto", headers=h, json={
        "asset": "BTC",
        "transactions": [
            {"from_address": "wallet_A", "to_address": "wallet_B", "amount": 1.5, "tx_hash": "abc123"},
            {"from_address": "wallet_B", "to_address": "wallet_C", "amount": 0.5},
        ],
    })
    assert resp.status_code == 201
    body = resp.json()
    wallets = {e["name"] for e in body["entities"] if e["type"] == "asset"}
    assert {"wallet_A", "wallet_B", "wallet_C"} <= wallets
    assert body["summary"]["relationships_created"] == 2
