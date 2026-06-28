"""Postgres ⇄ Neo4j drift detection and repair (Task 3 / Task 4).

PostgreSQL is the source of truth; Neo4j is a best-effort projection kept in sync
on each write (see ``graph_sync``). Projection writes can fail silently (graph
down, lost arq job, a crash between the two stores) and the two stores then
*drift* — and an analyst drawing conclusions from a stale graph is exactly the
failure this platform exists to prevent.

This module:

* **checks** consistency without mutating anything (powers ``/health/consistency``
  and an analyst's "is my graph trustworthy right now?" question), and
* **reconciles** by re-projecting anything missing/stale from Postgres and
  deleting Neo4j nodes/edges that no longer exist in Postgres.

The diffing core (:func:`compute_entity_diff`, :func:`compute_rel_diff`) is pure
and unit-tested without a live Neo4j; the async wrappers just load both sides.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.neo4j import neo4j_client
from app.models.entity import Entity
from app.models.relationship import Relationship
from app.services import graph_sync

logger = logging.getLogger(__name__)

# Confidence scores are rounded to 4dp on write; anything coarser is real drift.
_CONF_TOLERANCE = 1e-4
# Cap on how many ids we echo back in a report — counts are always exact, but we
# never want to serialize millions of ids into an HTTP response.
_SAMPLE_LIMIT = 100


@dataclass(slots=True)
class EntityFingerprint:
    """The subset of entity state that the Neo4j projection mirrors."""

    name: str
    confidence_score: float


@dataclass(slots=True)
class ConsistencyReport:
    neo4j_enabled: bool
    checked: bool
    entities_postgres: int = 0
    entities_neo4j: int = 0
    relationships_postgres: int = 0
    relationships_neo4j: int = 0
    # In Postgres but absent from Neo4j (failed/lost projection).
    missing_entities: list[str] = field(default_factory=list)
    missing_relationships: list[str] = field(default_factory=list)
    # In Neo4j but no longer in Postgres (failed delete projection).
    orphan_entities: list[str] = field(default_factory=list)
    orphan_relationships: list[str] = field(default_factory=list)
    # Present in both but property drift (stale name/confidence in the graph).
    stale_entities: list[str] = field(default_factory=list)

    @property
    def drift_count(self) -> int:
        return (
            len(self.missing_entities) + len(self.orphan_entities)
            + len(self.stale_entities) + len(self.missing_relationships)
            + len(self.orphan_relationships)
        )

    @property
    def in_sync(self) -> bool:
        # A disabled/unchecked graph is trivially "in sync" — there is nothing to
        # diverge from. Callers distinguish via ``checked``/``neo4j_enabled``.
        return self.drift_count == 0

    def as_dict(self) -> dict:
        return {
            "neo4j_enabled": self.neo4j_enabled,
            "checked": self.checked,
            "in_sync": self.in_sync,
            "drift_count": self.drift_count,
            "counts": {
                "entities_postgres": self.entities_postgres,
                "entities_neo4j": self.entities_neo4j,
                "relationships_postgres": self.relationships_postgres,
                "relationships_neo4j": self.relationships_neo4j,
            },
            "missing_entities": self.missing_entities,
            "orphan_entities": self.orphan_entities,
            "stale_entities": self.stale_entities,
            "missing_relationships": self.missing_relationships,
            "orphan_relationships": self.orphan_relationships,
        }


@dataclass(slots=True)
class ReconcileResult:
    report_before: ConsistencyReport
    reprojected_entities: int = 0
    deleted_entities: int = 0
    reprojected_relationships: int = 0
    deleted_relationships: int = 0

    def as_dict(self) -> dict:
        return {
            "drift_before": self.report_before.drift_count,
            "reprojected_entities": self.reprojected_entities,
            "deleted_entities": self.deleted_entities,
            "reprojected_relationships": self.reprojected_relationships,
            "deleted_relationships": self.deleted_relationships,
        }


# --------------------------- pure diff core --------------------------- #

def _trim(ids: set[str]) -> list[str]:
    return sorted(ids)[:_SAMPLE_LIMIT]


def compute_entity_diff(
    postgres: dict[str, EntityFingerprint],
    neo4j: dict[str, EntityFingerprint],
) -> tuple[list[str], list[str], list[str]]:
    """Return (missing, orphan, stale) entity-id lists. Pure — no I/O."""
    pg_ids, gx_ids = set(postgres), set(neo4j)
    missing = _trim(pg_ids - gx_ids)
    orphan = _trim(gx_ids - pg_ids)
    stale: set[str] = set()
    for eid in pg_ids & gx_ids:
        p, g = postgres[eid], neo4j[eid]
        if p.name != g.name or abs(p.confidence_score - g.confidence_score) > _CONF_TOLERANCE:
            stale.add(eid)
    return missing, orphan, _trim(stale)


def compute_rel_diff(
    postgres: set[str], neo4j: set[str]
) -> tuple[list[str], list[str]]:
    """Return (missing, orphan) relationship-id lists. Pure — no I/O."""
    return _trim(postgres - neo4j), _trim(neo4j - postgres)


# --------------------------- loaders --------------------------- #

async def _postgres_entities(db: AsyncSession) -> dict[str, EntityFingerprint]:
    rows = (await db.execute(
        select(Entity.id, Entity.name, Entity.confidence_score)
    )).all()
    return {
        str(eid): EntityFingerprint(name=name, confidence_score=float(conf or 0.0))
        for eid, name, conf in rows
    }


async def _postgres_relationships(db: AsyncSession) -> set[str]:
    rows = (await db.execute(select(Relationship.id))).scalars().all()
    return {str(rid) for rid in rows}


async def _neo4j_entities() -> dict[str, EntityFingerprint]:
    records = await neo4j_client.run_read(
        "MATCH (e:Entity) RETURN e.id AS id, e.name AS name, "
        "e.confidence_score AS confidence_score"
    )
    return {
        r["id"]: EntityFingerprint(
            name=r.get("name") or "",
            confidence_score=float(r.get("confidence_score") or 0.0),
        )
        for r in records if r.get("id")
    }


async def _neo4j_relationships() -> set[str]:
    records = await neo4j_client.run_read(
        "MATCH ()-[r]->() WHERE r.id IS NOT NULL RETURN r.id AS id"
    )
    return {r["id"] for r in records if r.get("id")}


# --------------------------- public API --------------------------- #

async def check_consistency(db: AsyncSession) -> ConsistencyReport:
    """Diff Postgres against Neo4j without mutating either store."""
    if not settings.NEO4J_ENABLED:
        return ConsistencyReport(neo4j_enabled=False, checked=False)

    pg_entities = await _postgres_entities(db)
    pg_rels = await _postgres_relationships(db)
    try:
        gx_entities = await _neo4j_entities()
        gx_rels = await _neo4j_relationships()
    except Exception:
        logger.exception("Consistency check could not read Neo4j.")
        return ConsistencyReport(
            neo4j_enabled=True, checked=False,
            entities_postgres=len(pg_entities),
            relationships_postgres=len(pg_rels),
        )

    missing_e, orphan_e, stale_e = compute_entity_diff(pg_entities, gx_entities)
    missing_r, orphan_r = compute_rel_diff(pg_rels, gx_rels)
    return ConsistencyReport(
        neo4j_enabled=True, checked=True,
        entities_postgres=len(pg_entities), entities_neo4j=len(gx_entities),
        relationships_postgres=len(pg_rels), relationships_neo4j=len(gx_rels),
        missing_entities=missing_e, orphan_entities=orphan_e, stale_entities=stale_e,
        missing_relationships=missing_r, orphan_relationships=orphan_r,
    )


async def reconcile(db: AsyncSession) -> ReconcileResult:
    """Repair drift: re-project missing/stale rows from Postgres, drop orphans.

    Postgres is authoritative, so repair is one-directional. Safe to run
    repeatedly (idempotent MERGE/DELETE). Returns the pre-repair report plus a
    tally of actions taken.
    """
    before = await check_consistency(db)
    result = ReconcileResult(report_before=before)
    if not before.checked or before.in_sync:
        return result

    # Re-project entities that are missing or stale in the graph. Ids that came
    # from Postgres are always valid UUIDs; orphan ids originate in Neo4j and may
    # be arbitrary strings, so they are only ever passed to a string-keyed delete.
    to_reproject = set(before.missing_entities) | set(before.stale_entities)
    for eid in to_reproject:
        entity = await db.get(Entity, uuid.UUID(eid))
        if entity is not None:
            await graph_sync.upsert_entity(entity)
            result.reprojected_entities += 1
    for eid in before.orphan_entities:
        await graph_sync.delete_entity(eid)
        result.deleted_entities += 1

    for rid in before.missing_relationships:
        rel = await db.get(Relationship, uuid.UUID(rid))
        if rel is not None:
            await graph_sync.upsert_relationship(rel)
            result.reprojected_relationships += 1
    for rid in before.orphan_relationships:
        await graph_sync.delete_relationship(rid)
        result.deleted_relationships += 1

    logger.info("Reconcile complete: %s", result.as_dict())
    return result
