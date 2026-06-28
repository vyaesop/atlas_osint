"""End-to-end ingestion + AI-summary API tests (heuristic provider)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import user as user_crud
from app.models.enums import Role
from app.schemas.user import UserCreate

PREFIX = "/api/v1"

DOC = (
    "Dr. Jane Powell founded Globex Corporation. "
    "Jane Powell works for Globex Corporation. "
    "Globex Corporation partnered with Initech Inc."
)


async def _researcher(client: AsyncClient, db: AsyncSession) -> dict[str, str]:
    await user_crud.create(
        db, UserCreate(email="ing@atlas.example.com", password="password123",
                       role=Role.RESEARCHER),
        role=Role.RESEARCHER,
    )
    await db.commit()
    resp = await client.post(
        f"{PREFIX}/auth/login",
        data={"username": "ing@atlas.example.com", "password": "password123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_ingest_text_creates_ai_labeled_graph(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    resp = await client.post(
        f"{PREFIX}/ingestion/text", headers=h,
        json={"title": "Filing 2024", "text": DOC},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert body["provider"] == "heuristic"
    assert body["summary"]["entities_created"] >= 2
    assert body["summary"]["relationships_created"] >= 1

    # Extracted entities are flagged AI-generated and start unverified (confidence 0).
    ai_entities = [e for e in body["entities"] if e["is_ai_generated"]]
    assert ai_entities
    assert all(e["confidence_score"] == 0.0 for e in ai_entities)

    # The extracted relationships are AI-generated too.
    assert all(r["is_ai_generated"] for r in body["relationships"])


@pytest.mark.asyncio
async def test_ingest_attaches_unverified_evidence(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    body = (await client.post(
        f"{PREFIX}/ingestion/text", headers=h,
        json={"title": "Filing", "text": DOC},
    )).json()

    rel_id = body["relationships"][0]["id"]
    evidence = (await client.get(
        f"{PREFIX}/evidence?relationship_id={rel_id}", headers=h
    )).json()
    assert evidence
    ev = evidence[0]
    assert ev["is_ai_generated"] is True
    assert ev["verification_status"] == "unverified"
    assert ev["quote"]


@pytest.mark.asyncio
async def test_ingest_upload_csv(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    files = {"file": ("people.csv", b"text\nViktor Stone founded Initech Inc.\n", "text/csv")}
    resp = await client.post(f"{PREFIX}/ingestion/upload", headers=h, files=files)
    assert resp.status_code == 201, resp.text
    assert resp.json()["provider"] == "heuristic"


@pytest.mark.asyncio
async def test_unsupported_upload_rejected(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    files = {"file": ("pic.xyz", b"\x00\x01", "application/octet-stream")}
    resp = await client.post(f"{PREFIX}/ingestion/upload", headers=h, files=files)
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_entity_summary_endpoint(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    body = (await client.post(
        f"{PREFIX}/ingestion/text", headers=h,
        json={"title": "Filing", "text": DOC},
    )).json()
    entity_id = body["entities"][0]["id"]

    resp = await client.post(f"{PREFIX}/ai/summarize/entity/{entity_id}", headers=h)
    assert resp.status_code == 200, resp.text
    summary = resp.json()
    assert summary["ai_generated"] is True
    assert summary["provider"] == "heuristic"
    assert len(summary["summary"]) > 0
