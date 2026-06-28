"""Cluster 6 (part 2): RAG (#25), agentic investigation (#27), deepfake flag
(#30), and multimodal availability (#20/#21)."""
from __future__ import annotations

import io

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import user as user_crud
from app.models.enums import Role
from app.schemas.user import UserCreate
from app.services import media_forensics

PREFIX = "/api/v1"


async def _researcher(client, db, email) -> dict[str, str]:
    await user_crud.create(
        db, UserCreate(email=email, password="password123", role=Role.RESEARCHER),
        role=Role.RESEARCHER,
    )
    await db.commit()
    resp = await client.post(f"{PREFIX}/auth/login",
                             data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _entity(client, h, name, type_="person", desc=None):
    return (await client.post(f"{PREFIX}/entities", headers=h, json={
        "type": type_, "name": name, "description": desc,
    })).json()


# --- #25 RAG --- #

@pytest.mark.asyncio
async def test_rag_retrieves_relevant_citation(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session, "rag@atlas.example.com")
    await client.post(f"{PREFIX}/ingestion/text", headers=h, json={
        "title": "Helios dossier", "text": "The Helios facility processes uranium in Karaganda."})
    await client.post(f"{PREFIX}/ingestion/text", headers=h, json={
        "title": "Unrelated", "text": "A bakery opened downtown selling croissants."})

    resp = await client.post(f"{PREFIX}/ai/rag", headers=h,
                             json={"question": "What does the Helios facility process?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["citations"], "expected at least one citation"
    assert body["citations"][0]["title"] == "Helios dossier"
    assert isinstance(body["answer"], str)


@pytest.mark.asyncio
async def test_rag_no_corpus_match(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session, "rag2@atlas.example.com")
    resp = await client.post(f"{PREFIX}/ai/rag", headers=h,
                             json={"question": "nonexistent topic xyzzy"})
    assert resp.status_code == 200
    assert resp.json()["citations"] == []


# --- #27 agentic investigation --- #

@pytest.mark.asyncio
async def test_investigation_flags_and_actions(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session, "inv@atlas.example.com")
    suspect = await _entity(client, h, "Ivan Volkov",
                            desc="reachable at ivan@mail.ru")
    # Watchlist hit drives a high-severity finding + action.
    await client.post(f"{PREFIX}/sanctions/watchlist", headers=h,
                      json={"entries": [{"name": "Ivan Volkov", "program": "OFAC-SDN"}]})

    resp = await client.post(f"{PREFIX}/ai/investigate/{suspect['id']}", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    kinds = {f["kind"] for f in body["findings"]}
    assert "sanctions" in kinds and "selectors" in kinds
    assert body["recommended_actions"]
    assert isinstance(body["narrative"], str)


# --- #30 deepfake flag --- #

def test_deepfake_heuristic_unit():
    high = media_forensics.assess(software="Stable Diffusion v1.5", metadata={})
    assert high.risk == "high" and high.score >= 0.7
    low = media_forensics.assess(metadata={"Make": "Canon", "Model": "EOS", "c2pa": "yes",
                                            "DateTimeOriginal": "2020"})
    assert low.risk == "low"


@pytest.mark.asyncio
async def test_deepfake_endpoint(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session, "df@atlas.example.com")
    resp = await client.post(f"{PREFIX}/ai/media/deepfake-check", headers=h,
                             json={"text": "Generated with Midjourney v6"})
    assert resp.status_code == 200
    assert resp.json()["risk"] == "high"


# --- #20/#21 multimodal availability (offline → 503) --- #

@pytest.mark.asyncio
async def test_image_requires_gemini(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session, "img@atlas.example.com")
    files = {"file": ("x.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")}
    resp = await client.post(f"{PREFIX}/ai/image", headers=h, files=files)
    # Tests run with the default heuristic provider → multimodal unavailable.
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_audio_requires_gemini(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session, "aud@atlas.example.com")
    files = {"file": ("x.mp3", io.BytesIO(b"ID3"), "audio/mpeg")}
    resp = await client.post(f"{PREFIX}/ai/audio", headers=h, files=files)
    assert resp.status_code == 503
