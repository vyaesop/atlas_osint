"""Redis read-through cache with global graph-version invalidation.

Analytics and dashboards are pure functions of the graph, so instead of tracking
per-entity cache dependencies we namespace every cache key with a single
monotonic *graph version* stored in Redis. Any mutation bumps the version, which
instantly orphans all previously cached results — simple and always-correct.

Everything degrades to a no-op when ``CACHE_ENABLED`` is false or Redis is
unreachable, so callers never need to branch on cache availability.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Awaitable, Callable

from app.core.config import settings

logger = logging.getLogger(__name__)

_VERSION_KEY = "atlas:graph:version"
_client = None  # type: ignore[var-annotated]
_unavailable = False


async def _get_client():
    """Lazily connect to Redis. Returns None if disabled or unreachable."""
    global _client, _unavailable
    if not settings.CACHE_ENABLED or _unavailable:
        return None
    if _client is None:
        try:
            import redis.asyncio as aioredis

            _client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            await _client.ping()
        except Exception:  # pragma: no cover - degrade gracefully
            logger.warning("Cache disabled: Redis unavailable at %s", settings.REDIS_URL)
            _unavailable = True
            _client = None
    return _client


async def graph_version() -> int:
    client = await _get_client()
    if client is None:
        return 0
    try:
        v = await client.get(_VERSION_KEY)
        return int(v) if v is not None else 1
    except Exception:  # pragma: no cover
        return 0


async def invalidate_graph() -> None:
    """Bump the graph version so all versioned cache entries become stale."""
    client = await _get_client()
    if client is None:
        return
    try:
        await client.incr(_VERSION_KEY)
    except Exception:  # pragma: no cover
        logger.debug("Cache invalidation failed (non-fatal).")


def _key(namespace: str, version: int, params: dict[str, Any]) -> str:
    blob = json.dumps(params, sort_keys=True, default=str)
    digest = hashlib.sha1(blob.encode()).hexdigest()[:16]
    return f"atlas:cache:{namespace}:v{version}:{digest}"


async def cached_call(
    namespace: str,
    params: dict[str, Any],
    compute: Callable[[], Awaitable[Any]],
    *,
    serialize: Callable[[Any], Any] = lambda x: x,
    deserialize: Callable[[Any], Any] = lambda x: x,
) -> Any:
    """Return a cached result for (namespace, params) or compute and store it.

    ``compute`` returns the domain object; ``serialize`` converts it to a
    JSON-able value for storage and ``deserialize`` reconstructs it on a hit.
    """
    client = await _get_client()
    if client is None:
        return await compute()

    version = await graph_version()
    key = _key(namespace, version, params)
    try:
        hit = await client.get(key)
        if hit is not None:
            return deserialize(json.loads(hit))
    except Exception:  # pragma: no cover
        return await compute()

    result = await compute()
    try:
        await client.set(key, json.dumps(serialize(result), default=str),
                         ex=settings.CACHE_TTL_SECONDS)
    except Exception:  # pragma: no cover
        pass
    return result


async def close() -> None:  # pragma: no cover
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
