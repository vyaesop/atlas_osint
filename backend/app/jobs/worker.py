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


async def reconcile_graph(ctx) -> None:
    """Periodic Postgres ⇄ Neo4j drift repair (scheduled via cron below).

    Self-healing safety net: even if individual projection jobs are lost, the
    graph converges back to Postgres within the cron interval so analysts never
    reason over a silently-stale graph.
    """
    from app.services import reconcile

    async with AsyncSessionLocal() as db:
        result = await reconcile.reconcile(db)
    if result.report_before.drift_count:
        logger.info("Scheduled reconcile repaired drift: %s", result.as_dict())


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


def _cron_jobs():
    from arq import cron

    # Reconcile every 15 minutes (top of, and quarter-past/half/quarter-to each
    # hour). Cheap when already in sync; converges the graph when not.
    return [cron(reconcile_graph, minute={0, 15, 30, 45})]


class WorkerSettings:
    functions = [project_entity, remove_entity, project_relationship, remove_relationship]
    cron_jobs = _cron_jobs()
    on_startup = _startup
    on_shutdown = _shutdown
    redis_settings = _redis_settings()
