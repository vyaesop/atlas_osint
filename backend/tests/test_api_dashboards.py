"""End-to-end dashboard + timeline API tests."""
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
        db, UserCreate(email="dash@atlas.example.com", password="password123",
                       role=Role.RESEARCHER),
        role=Role.RESEARCHER,
    )
    await db.commit()
    resp = await client.post(
        f"{PREFIX}/auth/login",
        data={"username": "dash@atlas.example.com", "password": "password123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _entity(client, h, name, type_, **props):
    body = {"type": type_, "name": name}
    if props:
        body["properties"] = props
    return (await client.post(f"{PREFIX}/entities", headers=h, json=body)).json()


async def _rel(client, h, s, t, type_, **extra):
    return (await client.post(f"{PREFIX}/relationships", headers=h,
            json={"type": type_, "source_id": s, "target_id": t, **extra})).json()


@pytest.mark.asyncio
async def test_person_dashboard_sections(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    jane = await _entity(client, h, "Jane Powell", "person")
    globex = await _entity(client, h, "Globex", "company")
    davos = await _entity(client, h, "Davos 2024", "event", date="2024-01-15")
    geneva = await _entity(client, h, "Geneva", "location")

    await _rel(client, h, jane["id"], globex["id"], "WORKS_FOR")
    await _rel(client, h, jane["id"], davos["id"], "ATTENDED")
    await _rel(client, h, globex["id"], geneva["id"], "LOCATED_IN")

    dash = (await client.get(f"{PREFIX}/dashboards/entities/{jane['id']}", headers=h)).json()
    assert dash["kind"] == "person"
    assert dash["stats"]["total_connections"] == 2  # Globex + Davos
    org_names = {n["name"] for n in dash["sections"]["organizations"]}
    assert "Globex" in org_names
    event_names = {n["name"] for n in dash["sections"]["events"]}
    assert "Davos 2024" in event_names
    assert dash["influence"]["connections_by_type"]["WORKS_FOR"] == 1


@pytest.mark.asyncio
async def test_organization_dashboard_members(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    globex = await _entity(client, h, "Globex", "company")
    initech = await _entity(client, h, "Initech", "company")
    p1 = await _entity(client, h, "Alice", "person")
    p2 = await _entity(client, h, "Bob", "person")

    await _rel(client, h, p1["id"], globex["id"], "WORKS_FOR")
    await _rel(client, h, p2["id"], globex["id"], "MEMBER_OF")
    await _rel(client, h, globex["id"], initech["id"], "PARTNER_OF")

    dash = (await client.get(f"{PREFIX}/dashboards/entities/{globex['id']}", headers=h)).json()
    assert dash["kind"] == "company"
    member_names = {n["name"] for n in dash["sections"]["members"]}
    assert member_names == {"Alice", "Bob"}
    partner_names = {n["name"] for n in dash["sections"]["partners"]}
    assert "Initech" in partner_names


@pytest.mark.asyncio
async def test_timeline_orders_and_filters(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    jane = await _entity(client, h, "Jane", "person", birth_date="1970-05-01")
    a = await _entity(client, h, "A Corp", "company")
    b = await _entity(client, h, "B Corp", "company")

    await _rel(client, h, jane["id"], a["id"], "WORKS_FOR", start_date="2000-01-01", end_date="2010-01-01")
    await _rel(client, h, jane["id"], b["id"], "WORKS_FOR", start_date="2010-02-01")

    tl = (await client.get(f"{PREFIX}/timeline/entities/{jane['id']}", headers=h)).json()
    dates = [i["date"] for i in tl["items"]]
    assert dates == sorted(dates)
    # born + (A start, A end) + (B start) = 4 items
    assert len(tl["items"]) == 4
    assert any(i["kind"] == "attribute" and i["label"] == "Born" for i in tl["items"])

    # Date-window filter excludes the 1970 birth and pre-2010 items.
    filtered = (await client.get(
        f"{PREFIX}/timeline/entities/{jane['id']}?date_from=2010-01-01", headers=h
    )).json()
    assert all(i["date"] >= "2010-01-01" for i in filtered["items"])


@pytest.mark.asyncio
async def test_dashboard_404(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    import uuid
    resp = await client.get(f"{PREFIX}/dashboards/entities/{uuid.uuid4()}", headers=h)
    assert resp.status_code == 404
