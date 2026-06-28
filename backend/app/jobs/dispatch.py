"""Dispatch graph/search side effects either inline or to the job queue.

Each helper also invalidates the analytics/dashboard cache. Inline mode keeps
the exact synchronous behavior used in dev/tests; queued mode hands off by id
and the worker reloads from PostgreSQL (the source of truth).
"""
from __future__ import annotations

import uuid

from app.core import cache
from app.core.config import settings
from app.models.entity import Entity
from app.models.relationship import Relationship
from app.search.service import search_service
from app.services import graph_sync

_pool = None  # cached arq pool


async def _enqueue(task: str, *args: object) -> None:
    global _pool
    from arq import create_pool
    from arq.connections import RedisSettings

    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    await _pool.enqueue_job(task, *args)


async def sync_entity(entity: Entity) -> None:
    if settings.JOBS_ENABLED:
        await _enqueue("project_entity", str(entity.id))
    else:
        await graph_sync.upsert_entity(entity)
        await search_service.index_entity(entity)
    await cache.invalidate_graph()


async def remove_entity(entity_id: uuid.UUID) -> None:
    if settings.JOBS_ENABLED:
        await _enqueue("remove_entity", str(entity_id))
    else:
        await graph_sync.delete_entity(entity_id)
        await search_service.remove_entity(entity_id)
    await cache.invalidate_graph()


async def sync_relationship(rel: Relationship) -> None:
    if settings.JOBS_ENABLED:
        await _enqueue("project_relationship", str(rel.id))
    else:
        await graph_sync.upsert_relationship(rel)
    await cache.invalidate_graph()


async def remove_relationship(rel_id: uuid.UUID) -> None:
    if settings.JOBS_ENABLED:
        await _enqueue("remove_relationship", str(rel_id))
    else:
        await graph_sync.delete_relationship(rel_id)
    await cache.invalidate_graph()
