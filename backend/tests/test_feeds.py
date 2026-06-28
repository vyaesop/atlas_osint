"""Feed parsing (#19): RSS/Atom unit tests + ingest API test."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import user as user_crud
from app.ingestion.feeds import parse_feed
from app.models.enums import Role
from app.schemas.user import UserCreate

PREFIX = "/api/v1"

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>Threat Intel Daily</title>
<item><title>Acme breached</title><description>Acme Corp reported an incident.</description>
<link>http://news/1</link><pubDate>Mon, 02 Mar 2020 10:00:00 +0000</pubDate></item>
<item><title>Sanctions update</title><description>New OFAC listings.</description>
<link>http://news/2</link></item>
</channel></rss>"""

ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>Gov Feed</title>
<entry><title>Notice A</title><summary>Summary A</summary>
<link href="http://gov/a"/><updated>2020-03-02T10:00:00Z</updated></entry>
</feed>"""


def test_parse_rss():
    title, items = parse_feed(RSS)
    assert title == "Threat Intel Daily"
    assert len(items) == 2
    assert items[0].title == "Acme breached"
    assert items[0].link == "http://news/1"


def test_parse_atom():
    title, items = parse_feed(ATOM)
    assert title == "Gov Feed"
    assert len(items) == 1
    assert items[0].link == "http://gov/a"
    assert items[0].summary == "Summary A"


async def _researcher(client: AsyncClient, db: AsyncSession) -> dict[str, str]:
    await user_crud.create(
        db, UserCreate(email="feed@atlas.example.com", password="password123",
                       role=Role.RESEARCHER),
        role=Role.RESEARCHER,
    )
    await db.commit()
    resp = await client.post(
        f"{PREFIX}/auth/login",
        data={"username": "feed@atlas.example.com", "password": "password123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_feed_parse_only(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    resp = await client.post(f"{PREFIX}/ingestion/feed", headers=h,
                             json={"content": RSS, "ingest": False})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2 and body["documents_created"] == 0


@pytest.mark.asyncio
async def test_feed_ingest_creates_documents(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    resp = await client.post(f"{PREFIX}/ingestion/feed", headers=h,
                             json={"content": RSS, "ingest": True})
    assert resp.status_code == 200
    assert resp.json()["documents_created"] == 2


@pytest.mark.asyncio
async def test_feed_invalid_xml(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    resp = await client.post(f"{PREFIX}/ingestion/feed", headers=h,
                             json={"content": "<not valid", "ingest": False})
    assert resp.status_code == 422
