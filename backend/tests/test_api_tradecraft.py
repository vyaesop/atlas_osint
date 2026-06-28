"""End-to-end tests for Cluster 2 APIs: ACH (#1), annotations (#4/#6),
graded evidence + estimative confidence (#2/#3)."""
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
        db, UserCreate(email="tc@atlas.example.com", password="password123",
                       role=Role.RESEARCHER),
        role=Role.RESEARCHER,
    )
    await db.commit()
    resp = await client.post(
        f"{PREFIX}/auth/login",
        data={"username": "tc@atlas.example.com", "password": "password123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _entity(client, h, name, type_="person"):
    return (await client.post(f"{PREFIX}/entities", headers=h,
            json={"type": type_, "name": name})).json()


# --- #1 ACH --------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_ach_full_flow(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    analysis = (await client.post(f"{PREFIX}/ach", headers=h,
                json={"title": "Who funded the op?", "question": "Funding source?"})).json()
    aid = analysis["id"]

    h1 = (await client.post(f"{PREFIX}/ach/{aid}/hypotheses", headers=h,
          json={"text": "Funded by Org A"})).json()
    h2 = (await client.post(f"{PREFIX}/ach/{aid}/hypotheses", headers=h,
          json={"text": "Funded by Org B"})).json()
    e1 = (await client.post(f"{PREFIX}/ach/{aid}/items", headers=h,
          json={"text": "Wire transfer record", "weight": 2.0})).json()

    # e1 is consistent with h1, inconsistent with h2.
    await client.put(f"{PREFIX}/ach/{aid}/ratings", headers=h,
                     json={"hypothesis_id": h1["id"], "item_id": e1["id"],
                           "consistency": "consistent"})
    detail = (await client.put(f"{PREFIX}/ach/{aid}/ratings", headers=h,
              json={"hypothesis_id": h2["id"], "item_id": e1["id"],
                    "consistency": "inconsistent"})).json()

    assert detail["scores"]["most_likely_hypothesis_id"] == h1["id"]
    ranks = {s["hypothesis_id"]: s["rank"] for s in detail["scores"]["hypotheses"]}
    assert ranks[h1["id"]] == 1
    # The diagnostic item should carry non-zero diagnosticity.
    assert detail["scores"]["items"][0]["diagnosticity"] > 0


@pytest.mark.asyncio
async def test_ach_rating_rejects_foreign_hypothesis(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    a1 = (await client.post(f"{PREFIX}/ach", headers=h, json={"title": "A1"})).json()
    a2 = (await client.post(f"{PREFIX}/ach", headers=h, json={"title": "A2"})).json()
    h2 = (await client.post(f"{PREFIX}/ach/{a2['id']}/hypotheses", headers=h,
          json={"text": "H"})).json()
    e1 = (await client.post(f"{PREFIX}/ach/{a1['id']}/items", headers=h,
          json={"text": "E"})).json()
    resp = await client.put(f"{PREFIX}/ach/{a1['id']}/ratings", headers=h,
                            json={"hypothesis_id": h2["id"], "item_id": e1["id"],
                                  "consistency": "consistent"})
    assert resp.status_code == 422


# --- #4/#6 annotations ---------------------------------------------------- #

@pytest.mark.asyncio
async def test_annotation_create_list_delete(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    ent = await _entity(client, h, "Subject")
    created = await client.post(f"{PREFIX}/annotations", headers=h, json={
        "kind": "assumption", "text": "Assumes the source is not compromised.",
        "entity_id": ent["id"],
    })
    assert created.status_code == 201

    listed = (await client.get(
        f"{PREFIX}/annotations?entity_id={ent['id']}&kind=assumption", headers=h)).json()
    assert len(listed) == 1
    assert listed[0]["kind"] == "assumption"

    ann_id = listed[0]["id"]
    assert (await client.delete(f"{PREFIX}/annotations/{ann_id}", headers=h)).status_code == 204


@pytest.mark.asyncio
async def test_annotation_requires_one_target(client: AsyncClient, db_session: AsyncSession):
    h = await _researcher(client, db_session)
    resp = await client.post(f"{PREFIX}/annotations", headers=h,
                             json={"kind": "note", "text": "orphan"})
    assert resp.status_code == 422


# --- #2/#3 graded evidence + estimative confidence ------------------------ #

@pytest.mark.asyncio
async def test_graded_evidence_drives_confidence_and_estimative(
    client: AsyncClient, db_session: AsyncSession
):
    h = await _researcher(client, db_session)
    ent = await _entity(client, h, "Graded Subject")

    # Add three A1 (perfectly reliable) verified supporting evidence items.
    for i in range(3):
        ev = (await client.post(f"{PREFIX}/evidence", headers=h, json={
            "title": f"Source {i}", "entity_id": ent["id"], "stance": "supports",
            "source_reliability": "A", "info_credibility": "1",
        })).json()
        await client.post(f"{PREFIX}/evidence/{ev['id']}/verify", headers=h,
                          json={"status": "verified"})

    summary = (await client.get(f"{PREFIX}/entities/{ent['id']}/confidence", headers=h)).json()
    assert summary["support_mass"] == pytest.approx(3.0)   # 3 × weight 1.0
    assert summary["score"] > 0.9
    assert summary["estimative_label"] in {"very likely", "almost certain"}
    assert summary["analytic_confidence"] == "high"
