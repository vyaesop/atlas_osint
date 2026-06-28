"""ABAC must hold on derived/aggregate insights endpoints too (Task 17, F-1…F-4).

Row-level ABAC elsewhere does not automatically cover risk leaderboards, network
diffs, or lineage — these were leaking compartmented entity names/existence. A
low-clearance researcher must not see them.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import user as user_crud
from app.models.entity import Entity
from app.models.enums import Classification, EntityType, Role
from app.schemas.user import UserCreate

PREFIX = "/api/v1"


async def _login(client, db, email, clearance=Classification.UNCLASSIFIED):
    user = await user_crud.create(
        db, UserCreate(email=email, password="password123", role=Role.RESEARCHER),
        role=Role.RESEARCHER,
    )
    user.clearance = clearance
    await db.commit()
    resp = await client.post(f"{PREFIX}/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _seed_secret_and_public(db: AsyncSession):
    pub = Entity(type=EntityType.PERSON, name="Public Figure",
                 classification=Classification.UNCLASSIFIED)
    sec = Entity(type=EntityType.PERSON, name="SECRET Codename Falcon",
                 classification=Classification.SECRET)
    db.add_all([pub, sec])
    await db.commit()
    return pub, sec


async def test_facets_hide_classified_from_low_clearance(client: AsyncClient, db_session):
    await _seed_secret_and_public(db_session)
    h = await _login(client, db_session, "low-facet@atlas.example.com")

    body = (await client.get(f"{PREFIX}/insights/facets", headers=h)).json()
    assert body["total"] == 1
    assert "secret" not in {b["value"] for b in body["by_classification"]}


async def test_risk_leaderboard_hides_classified(client: AsyncClient, db_session):
    await _seed_secret_and_public(db_session)
    h = await _login(client, db_session, "low-risk@atlas.example.com")

    body = (await client.get(f"{PREFIX}/insights/risk", headers=h)).json()
    names = {r["name"] for r in body["results"]}
    assert "Public Figure" in names
    assert "SECRET Codename Falcon" not in names


async def test_diff_hides_classified(client: AsyncClient, db_session):
    await _seed_secret_and_public(db_session)
    h = await _login(client, db_session, "low-diff@atlas.example.com")

    since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    body = (await client.get(f"{PREFIX}/insights/diff", headers=h,
                             params={"since": since})).json()
    labels = {i["label"] for i in body["added_entities"]}
    assert "Public Figure" in labels
    assert "SECRET Codename Falcon" not in labels


async def test_risk_and_lineage_by_id_404_hide(client: AsyncClient, db_session):
    _, sec = await _seed_secret_and_public(db_session)
    h = await _login(client, db_session, "low-id@atlas.example.com")

    assert (await client.get(f"{PREFIX}/insights/risk/{sec.id}", headers=h)).status_code == 404
    assert (await client.get(f"{PREFIX}/insights/lineage/{sec.id}", headers=h)).status_code == 404


async def test_cleared_user_sees_everything(client: AsyncClient, db_session):
    await _seed_secret_and_public(db_session)
    h = await _login(client, db_session, "high@atlas.example.com", Classification.TOP_SECRET)

    body = (await client.get(f"{PREFIX}/insights/facets", headers=h)).json()
    assert body["total"] == 2
