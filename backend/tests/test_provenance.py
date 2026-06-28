"""One-click provenance for confidence numbers (Task 13)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import user as user_crud
from app.models.enums import Role
from app.schemas.user import UserCreate
from app.scripts.redteam_corpus import seed_scenario, SCENARIOS
from app.services import confidence

PREFIX = "/api/v1"


def _scenario(key):
    return next(s for s in SCENARIOS if s.key == key)


async def _researcher(client, db, email="prov@atlas.example.com"):
    await user_crud.create(db, UserCreate(email=email, password="password123", role=Role.RESEARCHER), role=Role.RESEARCHER)
    await db.commit()
    resp = await client.post(f"{PREFIX}/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_explain_marks_duplicate_sources_uncounted(db_session: AsyncSession):
    entity = await seed_scenario(db_session, _scenario("sock_puppet_flood"))
    await db_session.commit()

    explanation = await confidence.explain_entity(db_session, entity.id)
    counted = [c for c in explanation.contributions if c.counted]
    uncounted = [c for c in explanation.contributions if not c.counted]

    # 10 items, one source → exactly one counts; the rest are collapsed duplicates.
    assert len(counted) == 1
    assert len(uncounted) == 9
    assert all("duplicate source" in c.reason for c in uncounted)


async def test_explain_marks_unverified(db_session: AsyncSession):
    entity = await seed_scenario(db_session, _scenario("unverified_padding"))
    await db_session.commit()

    explanation = await confidence.explain_entity(db_session, entity.id)
    unverified = [c for c in explanation.contributions if not c.verified]
    assert unverified
    assert all(not c.counted for c in unverified)
    assert all("unverified" in c.reason for c in unverified)


async def test_provenance_endpoint_traces_to_source(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    entity = await seed_scenario(db_session, _scenario("legitimate_corroboration"))
    await db_session.commit()

    resp = await client.get(f"{PREFIX}/entities/{entity.id}/confidence/provenance", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    # The aggregate number is present...
    assert body["score"] >= 0.9
    # ...and every counted contribution names its source (A1 grade).
    counted = [c for c in body["contributions"] if c["counted"]]
    assert len(counted) == 3
    assert all(c["source"] for c in counted)
    assert all(c["admiralty_code"] == "A1" for c in counted)
