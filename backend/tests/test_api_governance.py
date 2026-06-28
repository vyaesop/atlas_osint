"""Cluster 8 tests: ABAC/classification (#37/#38), audit hash chain (#39),
retention/legal-hold (#40), sanitized export (#41), insider detection (#42)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import user as user_crud
from app.models.audit import AuditLog
from app.models.enums import AuditAction, Classification, Role
from app.schemas.user import UserCreate
from app.services import audit, governance

PREFIX = "/api/v1"


async def _user(client, db, email, role=Role.RESEARCHER, clearance=Classification.UNCLASSIFIED,
                compartments=None):
    await user_crud.create(
        db, UserCreate(email=email, password="password123", role=role,
                       clearance=clearance, compartments=compartments or []),
        role=role,
    )
    await db.commit()
    resp = await client.post(f"{PREFIX}/auth/login",
                             data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# --- #37/#38 ABAC --- #

@pytest.mark.asyncio
async def test_clearance_gates_entity_visibility(client: AsyncClient, db_session: AsyncSession):
    author = await _user(client, db_session, "auth@a.com", clearance=Classification.SECRET)
    secret = (await client.post(f"{PREFIX}/entities", headers=author, json={
        "type": "person", "name": "Asset X", "classification": "secret"})).json()

    low = await _user(client, db_session, "low@a.com", clearance=Classification.UNCLASSIFIED)
    high = await _user(client, db_session, "high@a.com", clearance=Classification.TOP_SECRET)

    # Low clearance: hidden from get and list.
    assert (await client.get(f"{PREFIX}/entities/{secret['id']}", headers=low)).status_code == 404
    low_list = (await client.get(f"{PREFIX}/entities", headers=low)).json()
    assert all(e["id"] != secret["id"] for e in low_list)
    # High clearance: visible.
    assert (await client.get(f"{PREFIX}/entities/{secret['id']}", headers=high)).status_code == 200


@pytest.mark.asyncio
async def test_compartment_need_to_know(client: AsyncClient, db_session: AsyncSession):
    author = await _user(client, db_session, "ca@a.com", clearance=Classification.TOP_SECRET,
                         compartments=["ALPHA"])
    ent = (await client.post(f"{PREFIX}/entities", headers=author, json={
        "type": "person", "name": "Compartmented", "classification": "confidential",
        "compartments": ["ALPHA"]})).json()
    # Cleared by level but lacking the compartment → denied.
    outsider = await _user(client, db_session, "out@a.com", clearance=Classification.TOP_SECRET)
    assert (await client.get(f"{PREFIX}/entities/{ent['id']}", headers=outsider)).status_code == 404
    insider = await _user(client, db_session, "in@a.com", clearance=Classification.SECRET,
                          compartments=["ALPHA", "BRAVO"])
    assert (await client.get(f"{PREFIX}/entities/{ent['id']}", headers=insider)).status_code == 200


# --- #39 audit hash chain --- #

@pytest.mark.asyncio
async def test_audit_chain_valid_then_tampered(client: AsyncClient, db_session: AsyncSession):
    admin = await _user(client, db_session, "adm@a.com", role=Role.ADMIN,
                        clearance=Classification.TOP_SECRET)
    # Generate audited activity.
    for n in ("A", "B", "C"):
        await client.post(f"{PREFIX}/entities", headers=admin, json={"type": "person", "name": n})

    ok = (await client.get(f"{PREFIX}/governance/audit/verify", headers=admin)).json()
    assert ok["valid"] is True and ok["entries_checked"] >= 3

    # Tamper with a stored entry directly.
    entry = (await db_session.execute(select(AuditLog).limit(1))).scalars().first()
    entry.reason = "tampered!"
    await db_session.commit()

    bad = (await client.get(f"{PREFIX}/governance/audit/verify", headers=admin)).json()
    assert bad["valid"] is False and bad["broken_at"] is not None


# --- #40 retention / legal hold --- #

@pytest.mark.asyncio
async def test_retention_respects_legal_hold(client: AsyncClient, db_session: AsyncSession):
    admin = await _user(client, db_session, "ret@a.com", role=Role.ADMIN)
    e1 = (await client.post(f"{PREFIX}/entities", headers=admin, json={"type": "person", "name": "Old1"})).json()
    e2 = (await client.post(f"{PREFIX}/entities", headers=admin, json={"type": "person", "name": "Old2"})).json()

    # Everything is "older than 0 days"; ai_only=false to include manual entities.
    preview = (await client.get(
        f"{PREFIX}/governance/retention/preview?older_than_days=0&ai_only=false", headers=admin)).json()
    assert preview["count"] == 2

    # Put one under legal hold → excluded.
    await client.patch(f"{PREFIX}/entities/{e1['id']}", headers=admin, json={"legal_hold": True})
    preview2 = (await client.get(
        f"{PREFIX}/governance/retention/preview?older_than_days=0&ai_only=false", headers=admin)).json()
    assert preview2["count"] == 1 and preview2["entity_ids"] == [e2["id"]]

    purged = (await client.post(
        f"{PREFIX}/governance/retention/purge?older_than_days=0&ai_only=false", headers=admin)).json()
    assert purged["purged"] == 1


# --- #41 sanitized export --- #

@pytest.mark.asyncio
async def test_sanitized_export_redacts(client: AsyncClient, db_session: AsyncSession):
    author = await _user(client, db_session, "exp@a.com", clearance=Classification.SECRET)
    pub = (await client.post(f"{PREFIX}/entities", headers=author, json={
        "type": "person", "name": "Public Person"})).json()
    sec = (await client.post(f"{PREFIX}/entities", headers=author, json={
        "type": "person", "name": "Secret Person", "classification": "secret"})).json()
    case = (await client.post(f"{PREFIX}/cases", headers=author, json={"title": "Case"})).json()
    for e in (pub, sec):
        await client.post(f"{PREFIX}/cases/{case['id']}/items", headers=author,
                          json={"item_type": "entity", "item_id": e["id"]})

    # Requester without clearance sees the secret entity redacted.
    low = await _user(client, db_session, "exlow@a.com", clearance=Classification.UNCLASSIFIED)
    pkg = (await client.get(f"{PREFIX}/governance/cases/{case['id']}/export", headers=low)).json()
    assert pkg["redacted_count"] == 1
    names = {e["name"] for e in pkg["entities"]}
    assert "Public Person" in names and "[REDACTED]" in names


# --- #42 insider-misuse (service-level) --- #

@pytest.mark.asyncio
async def test_insider_detection_flags_bulk_deletes(client: AsyncClient, db_session: AsyncSession):
    import uuid
    actor = uuid.uuid4()
    for _ in range(6):
        db_session.add(AuditLog(actor_id=actor, action=AuditAction.DELETE,
                                target_table="entities", target_id=uuid.uuid4(), changes={}))
    db_session.add(AuditLog(actor_id=actor, action=AuditAction.CREATE,
                            target_table="entities", target_id=uuid.uuid4(), changes={}))
    await db_session.commit()

    findings = await governance.detect_insider_anomalies(db_session)
    assert findings
    mine = next(f for f in findings if f.actor_id == str(actor))
    assert mine.deletes == 6
    assert any("deletion" in flag for flag in mine.flags)
