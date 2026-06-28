"""Projects PostgreSQL entities/relationships into Neo4j.

PostgreSQL is the source of truth; these helpers keep the Neo4j graph in sync on
each write. In Phase 1 the projection is synchronous (best-effort) right after
the Postgres commit. Phase 6 moves this onto a background queue and adds a
full-reprojection job so the graph can always be rebuilt from Postgres.

Every entity becomes a node labelled ``:Entity`` plus a per-type label (e.g.
``:Person``). Relationships use their type as the Neo4j relationship type.
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.db.neo4j import neo4j_client
from app.models.entity import Entity
from app.models.relationship import Relationship

logger = logging.getLogger(__name__)


def _type_label(entity_type: str) -> str:
    # person -> Person, government_agency -> GovernmentAgency
    return "".join(part.capitalize() for part in entity_type.split("_"))


async def upsert_entity(entity: Entity) -> None:
    label = _type_label(entity.type.value)
    query = f"""
    MERGE (e:Entity {{id: $id}})
    SET e:{label},
        e.type = $type,
        e.name = $name,
        e.aliases = $aliases,
        e.confidence_score = $confidence_score,
        e.updated_at = timestamp()
    """
    await _safe_write(
        query,
        id=str(entity.id),
        type=entity.type.value,
        name=entity.name,
        aliases=entity.aliases or [],
        confidence_score=entity.confidence_score,
    )


async def delete_entity(entity_id: Any) -> None:
    await _safe_write(
        "MATCH (e:Entity {id: $id}) DETACH DELETE e", id=str(entity_id)
    )


async def upsert_relationship(rel: Relationship) -> None:
    # Relationship type is a controlled enum, so interpolation here is safe.
    query = f"""
    MATCH (a:Entity {{id: $source_id}})
    MATCH (b:Entity {{id: $target_id}})
    MERGE (a)-[r:{rel.type.value} {{id: $id}}]->(b)
    SET r.confidence_score = $confidence_score,
        r.source_count = $source_count,
        r.start_date = $start_date,
        r.end_date = $end_date,
        r.updated_at = timestamp()
    """
    await _safe_write(
        query,
        id=str(rel.id),
        source_id=str(rel.source_id),
        target_id=str(rel.target_id),
        confidence_score=rel.confidence_score,
        source_count=rel.source_count,
        start_date=rel.start_date.isoformat() if rel.start_date else None,
        end_date=rel.end_date.isoformat() if rel.end_date else None,
    )


async def delete_relationship(relationship_id: Any) -> None:
    await _safe_write(
        "MATCH ()-[r {id: $id}]->() DELETE r", id=str(relationship_id)
    )


async def _safe_write(query: str, **params: Any) -> None:
    """Run a write but never let a graph-sync failure roll back the API request.

    The Postgres record is already committed and authoritative; a failed
    projection is logged for the Phase 6 reconciliation job to repair.
    """
    if not settings.NEO4J_ENABLED:
        return  # Graph projection disabled (local dev); Postgres stays source of truth.
    try:
        await neo4j_client.run_write(query, **params)
    except Exception:  # pragma: no cover - defensive
        # First non-blank line identifies the query without assuming it spans
        # multiple lines (single-line queries like DETACH DELETE used to IndexError).
        summary = next((line.strip() for line in query.splitlines() if line.strip()), query)
        logger.exception("Neo4j projection failed for query: %s", summary)
