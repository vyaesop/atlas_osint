"""arq worker: drains projection/indexing jobs.

Run with:  arq app.jobs.worker.WorkerSettings

Each task reloads the target from PostgreSQL (the source of truth) and applies
the Neo4j projection + search indexing, so a lost or retried job is always safe.
"""
from __future__ import annotations

import logging
import uuid

from app.crud import entity as entity_crud
from app.crud import relationship as rel_crud
from app.db.neo4j import neo4j_client
from app.db.session import AsyncSessionLocal
from app.search.service import search_service
from app.services import graph_sync

logger = logging.getLogger("atlas.worker")


async def project_entity(ctx, entity_id: str) -> None:
    async with AsyncSessionLocal() as db:
        entity = await entity_crud.get(db, uuid.UUID(entity_id))
        if entity is not None:
            await graph_sync.upsert_entity(entity)
            await search_service.index_entity(entity)


async def remove_entity(ctx, entity_id: str) -> None:
    await graph_sync.delete_entity(uuid.UUID(entity_id))
    await search_service.remove_entity(uuid.UUID(entity_id))


async def project_relationship(ctx, rel_id: str) -> None:
    async with AsyncSessionLocal() as db:
        rel = await rel_crud.get(db, uuid.UUID(rel_id))
        if rel is not None:
            await graph_sync.upsert_relationship(rel)


async def remove_relationship(ctx, rel_id: str) -> None:
    await graph_sync.delete_relationship(uuid.UUID(rel_id))


async def _startup(ctx) -> None:
    try:
        await neo4j_client.connect()
        await neo4j_client.ensure_constraints()
        await search_service.ensure_ready()
    except Exception:  # pragma: no cover
        logger.exception("Worker startup: backend connectivity issue (will retry per-job).")


async def _shutdown(ctx) -> None:  # pragma: no cover
    await neo4j_client.close()


def _redis_settings():
    from arq.connections import RedisSettings

    from app.core.config import settings

    return RedisSettings.from_dsn(settings.REDIS_URL)


class WorkerSettings:
    functions = [project_entity, remove_entity, project_relationship, remove_relationship]
    on_startup = _startup
    on_shutdown = _shutdown
    redis_settings = _redis_settings()
