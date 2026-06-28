"""End-to-end Cluster 7 tests: cases (#31), review (#34), tasks (#32),
comments (#33), saved views (#36), notebooks (#35)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import user as user_crud
from app.models.enums import Role
from app.schemas.user import UserCreate

PREFIX = "/api/v1"


async def _researcher(client, db, email="cw@atlas.example.com") -> dict[str, str]:
    await user_crud.create(
        db, UserCreate(email=email, password="password123", role=Role.RESEARCHER),
        role=Role.RESEARCHER,
    )
    await db.commit()
    resp = await client.post(f"{PREFIX}/auth/login",
                             data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _entity(client, h, name):
    return (await client.post(f"{PREFIX}/entities", headers=h,
            json={"type": "person", "name": name})).json()


# --- #31 cases + items --- #

@pytest.mark.asyncio
async def test_case_lifecycle_and_items(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    case = (await client.post(f"{PREFIX}/cases", headers=h, json={
        "title": "Operation Nightfall", "classification": "secret", "priority": 1})).json()
    assert case["status"] == "open" and case["classification"] == "secret"

    ent = await _entity(client, h, "Person of Interest")
    added = await client.post(f"{PREFIX}/cases/{case['id']}/items", headers=h,
                              json={"item_type": "entity", "item_id": ent["id"]})
    assert added.status_code == 201
    # Idempotent add returns the same item.
    again = await client.post(f"{PREFIX}/cases/{case['id']}/items", headers=h,
                              json={"item_type": "entity", "item_id": ent["id"]})
    assert again.json()["id"] == added.json()["id"]

    detail = (await client.get(f"{PREFIX}/cases/{case['id']}", headers=h)).json()
    assert len(detail["items"]) == 1 and detail["task_count"] == 0


# --- #34 review workflow --- #

@pytest.mark.asyncio
async def test_case_review_workflow(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session, "rev@atlas.example.com")
    case = (await client.post(f"{PREFIX}/cases", headers=h, json={"title": "C"})).json()
    submitted = (await client.post(f"{PREFIX}/cases/{case['id']}/review", headers=h,
                 json={"action": "submit"})).json()
    assert submitted["status"] == "in_review"
    released = (await client.post(f"{PREFIX}/cases/{case['id']}/review", headers=h,
                json={"action": "release"})).json()
    assert released["status"] == "released" and released["reviewed_by"] is not None


# --- #32 tasks / RFIs --- #

@pytest.mark.asyncio
async def test_tasks_and_rfis(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session, "task@atlas.example.com")
    case = (await client.post(f"{PREFIX}/cases", headers=h, json={"title": "C"})).json()
    task = (await client.post(f"{PREFIX}/tasks", headers=h, json={
        "case_id": case["id"], "kind": "rfi", "title": "Confirm address"})).json()
    assert task["status"] == "open" and task["kind"] == "rfi"

    updated = (await client.patch(f"{PREFIX}/tasks/{task['id']}", headers=h,
               json={"status": "answered", "answer": "123 Main St"})).json()
    assert updated["status"] == "answered" and updated["answer"] == "123 Main St"

    listed = (await client.get(f"{PREFIX}/tasks?case_id={case['id']}&status=answered", headers=h)).json()
    assert len(listed) == 1


# --- #33 comments --- #

@pytest.mark.asyncio
async def test_comments_thread(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session, "cmt@atlas.example.com")
    case = (await client.post(f"{PREFIX}/cases", headers=h, json={"title": "C"})).json()
    c1 = (await client.post(f"{PREFIX}/comments", headers=h, json={
        "target_type": "case", "target_id": case["id"], "body": "Initial assessment."})).json()
    await client.post(f"{PREFIX}/comments", headers=h, json={
        "target_type": "case", "target_id": case["id"], "body": "Reply.", "parent_id": c1["id"]})

    thread = (await client.get(
        f"{PREFIX}/comments?target_type=case&target_id={case['id']}", headers=h)).json()
    assert len(thread) == 2


# --- #36 saved views / pinboards --- #

@pytest.mark.asyncio
async def test_saved_views_visibility(client: AsyncClient, db_session: AsyncSession):
    h1 = await _researcher(client, db_session, "v1@atlas.example.com")
    h2 = await _researcher(client, db_session, "v2@atlas.example.com")
    # User 1 makes a private and a shared view.
    await client.post(f"{PREFIX}/views", headers=h1, json={
        "name": "Private graph", "kind": "graph", "state": {"focus": "x"}})
    await client.post(f"{PREFIX}/views", headers=h1, json={
        "name": "Team pinboard", "kind": "pinboard", "shared": True,
        "state": {"pinned": ["a", "b"]}})

    mine = (await client.get(f"{PREFIX}/views", headers=h1)).json()
    assert len(mine) == 2
    # User 2 sees only the shared one.
    theirs = (await client.get(f"{PREFIX}/views", headers=h2)).json()
    assert len(theirs) == 1 and theirs[0]["name"] == "Team pinboard"


# --- #35 notebooks --- #

@pytest.mark.asyncio
async def test_notebook_with_blocks(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session, "nb@atlas.example.com")
    ent = await _entity(client, h, "Subject")
    nb = (await client.post(f"{PREFIX}/notebooks", headers=h, json={"title": "Findings"})).json()

    await client.post(f"{PREFIX}/notebooks/{nb['id']}/blocks", headers=h, json={
        "kind": "text", "content": "## Summary", "order": 0})
    await client.post(f"{PREFIX}/notebooks/{nb['id']}/blocks", headers=h, json={
        "kind": "graph", "ref": {"entity_ids": [ent["id"]]}, "order": 1})

    detail = (await client.get(f"{PREFIX}/notebooks/{nb['id']}", headers=h)).json()
    assert len(detail["blocks"]) == 2
    assert detail["blocks"][0]["kind"] == "text"
    assert detail["blocks"][1]["ref"]["entity_ids"] == [ent["id"]]
