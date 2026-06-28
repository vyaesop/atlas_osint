"""Postgres ⇄ Neo4j reconciler (Tasks 3 & 4).

The pure diff core is tested directly; the async ``check_consistency`` /
``reconcile`` paths are tested by simulating a Neo4j projection (the loaders and
``graph_sync`` writers are monkeypatched, since the test suite runs with
NEO4J_ENABLED=false and no live graph).
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity
from app.models.enums import EntityType, RelationshipType
from app.models.relationship import Relationship
from app.services import reconcile
from app.services.reconcile import (
    EntityFingerprint,
    compute_entity_diff,
    compute_rel_diff,
)


# --------------------------- pure diff core --------------------------- #

def _fp(name: str, conf: float) -> EntityFingerprint:
    return EntityFingerprint(name=name, confidence_score=conf)


def test_entity_diff_detects_missing_orphan_stale():
    postgres = {"a": _fp("Alice", 0.9), "b": _fp("Bob", 0.5), "c": _fp("Carol", 0.7)}
    neo4j = {"b": _fp("Bob", 0.5), "c": _fp("Carol-OLD", 0.7), "z": _fp("Ghost", 0.1)}

    missing, orphan, stale = compute_entity_diff(postgres, neo4j)
    assert missing == ["a"]          # in PG, not in graph
    assert orphan == ["z"]           # in graph, not in PG
    assert stale == ["c"]            # name drift
    assert "b" not in stale          # identical → not stale


def test_entity_diff_confidence_drift_is_stale():
    postgres = {"a": _fp("Alice", 0.90)}
    neo4j = {"a": _fp("Alice", 0.80)}
    _, _, stale = compute_entity_diff(postgres, neo4j)
    assert stale == ["a"]


def test_entity_diff_within_tolerance_not_stale():
    postgres = {"a": _fp("Alice", 0.9000)}
    neo4j = {"a": _fp("Alice", 0.90004)}  # < 1e-4 apart
    _, _, stale = compute_entity_diff(postgres, neo4j)
    assert stale == []


def test_rel_diff():
    missing, orphan = compute_rel_diff({"r1", "r2"}, {"r2", "r3"})
    assert missing == ["r1"]
    assert orphan == ["r3"]


def test_in_sync_when_identical():
    fp = {"a": _fp("Alice", 0.9)}
    missing, orphan, stale = compute_entity_diff(fp, fp)
    assert not (missing or orphan or stale)


# --------------------------- async check / reconcile --------------------------- #

async def _seed(db: AsyncSession) -> tuple[Entity, Entity, Relationship]:
    a = Entity(type=EntityType.PERSON, name="Alice", confidence_score=0.9)
    b = Entity(type=EntityType.PERSON, name="Bob", confidence_score=0.5)
    db.add_all([a, b])
    await db.flush()
    r = Relationship(type=RelationshipType.ASSOCIATED_WITH, source_id=a.id, target_id=b.id)
    db.add(r)
    await db.commit()
    return a, b, r


async def test_check_consistency_disabled_returns_unchecked(db_session: AsyncSession):
    # Suite runs with NEO4J_ENABLED=false.
    report = await reconcile.check_consistency(db_session)
    assert report.neo4j_enabled is False
    assert report.checked is False
    assert report.in_sync is True  # nothing to diverge from


async def test_check_consistency_detects_drift(db_session, monkeypatch):
    a, b, r = await _seed(db_session)

    # Pretend the graph is enabled but only has a stale copy of `a` and an orphan.
    monkeypatch.setattr(reconcile.settings, "NEO4J_ENABLED", True)

    async def fake_entities():
        return {
            str(a.id): EntityFingerprint(name="Alice-OLD", confidence_score=0.9),  # stale
            "orphan-id": EntityFingerprint(name="Ghost", confidence_score=0.1),    # orphan
            # `b` is missing entirely
        }

    async def fake_rels():
        return set()  # relationship missing

    monkeypatch.setattr(reconcile, "_neo4j_entities", fake_entities)
    monkeypatch.setattr(reconcile, "_neo4j_relationships", fake_rels)

    report = await reconcile.check_consistency(db_session)
    assert report.checked is True
    assert str(b.id) in report.missing_entities
    assert str(a.id) in report.stale_entities
    assert "orphan-id" in report.orphan_entities
    assert str(r.id) in report.missing_relationships
    assert not report.in_sync


async def test_reconcile_repairs_drift(db_session, monkeypatch):
    a, b, r = await _seed(db_session)
    monkeypatch.setattr(reconcile.settings, "NEO4J_ENABLED", True)

    async def fake_entities():
        return {"orphan-id": EntityFingerprint(name="Ghost", confidence_score=0.1)}

    async def fake_rels():
        return {"orphan-rel"}

    monkeypatch.setattr(reconcile, "_neo4j_entities", fake_entities)
    monkeypatch.setattr(reconcile, "_neo4j_relationships", fake_rels)

    # Capture the repair writes instead of touching a real graph.
    calls: list[tuple[str, str]] = []

    async def rec_upsert_entity(entity):
        calls.append(("upsert_entity", str(entity.id)))

    async def rec_delete_entity(eid):
        calls.append(("delete_entity", str(eid)))

    async def rec_upsert_rel(rel):
        calls.append(("upsert_rel", str(rel.id)))

    async def rec_delete_rel(rid):
        calls.append(("delete_rel", str(rid)))

    monkeypatch.setattr(reconcile.graph_sync, "upsert_entity", rec_upsert_entity)
    monkeypatch.setattr(reconcile.graph_sync, "delete_entity", rec_delete_entity)
    monkeypatch.setattr(reconcile.graph_sync, "upsert_relationship", rec_upsert_rel)
    monkeypatch.setattr(reconcile.graph_sync, "delete_relationship", rec_delete_rel)

    result = await reconcile.reconcile(db_session)

    # Both PG entities were missing in the graph → re-projected; orphan deleted.
    assert result.reprojected_entities == 2
    assert result.deleted_entities == 1
    assert result.reprojected_relationships == 1
    assert result.deleted_relationships == 1
    assert ("delete_entity", "orphan-id") in calls
    assert ("delete_rel", "orphan-rel") in calls


async def test_health_consistency_endpoint(client: AsyncClient):
    resp = await client.get("/health/consistency")
    assert resp.status_code == 200
    body = resp.json()
    # Graph disabled in tests → reported as ok / not-checked.
    assert body["status"] == "ok"
    assert body["neo4j_enabled"] is False
    assert body["checked"] is False
    assert "counts" in body
