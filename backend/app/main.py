"""FastAPI application entrypoint for Project Atlas (Phase 1)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.neo4j import neo4j_client
from app.search.service import search_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("atlas")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to Neo4j and ensure graph constraints on startup.
    if settings.NEO4J_ENABLED:
        try:
            await neo4j_client.connect()
            await neo4j_client.ensure_constraints()
            logger.info("Connected to Neo4j and ensured constraints.")
        except Exception:  # pragma: no cover - allow API to boot if graph is down
            logger.exception("Neo4j unavailable at startup; graph sync will retry per-write.")
    else:
        logger.info("Neo4j disabled (NEO4J_ENABLED=false); graph projection is a no-op.")
    try:
        await search_service.ensure_ready()
        logger.info("Search backend ready (%s).", settings.SEARCH_BACKEND)
        # The in-memory backend is per-process and ephemeral. Rebuild it from the
        # DB (source of truth) on startup so search works immediately after a
        # seed/import — no manual POST /search/reindex needed. OpenSearch persists
        # its own index, so we skip the (potentially large) rebuild there.
        if settings.SEARCH_BACKEND == "inmemory":
            from sqlalchemy import select

            from app.db.session import AsyncSessionLocal
            from app.models.entity import Entity

            indexed = 0
            async with AsyncSessionLocal() as db:
                async for entity in await db.stream_scalars(select(Entity)):
                    await search_service.index_entity(entity)
                    indexed += 1
            logger.info("Indexed %d entities into the in-memory search backend.", indexed)
    except Exception:  # pragma: no cover - allow API to boot if search is down
        logger.exception("Search backend unavailable at startup.")
    yield
    await neo4j_client.close()
    from app.core import cache

    await cache.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description="Graph-based intelligence & knowledge platform — Phase 1 API.",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
)

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.PROJECT_NAME}


@app.get("/health/consistency", tags=["health"])
async def consistency_health() -> dict[str, object]:
    """Summary of Postgres ⇄ Neo4j drift for uptime/monitoring checks.

    Intentionally returns only counts (no entity ids) since it is unauthenticated;
    the detailed report and repair action live under ``/api/v1/governance`` behind
    admin auth. ``status`` is ``ok`` when the stores agree (or the graph is
    disabled), ``drift`` when they diverge, ``unknown`` if the graph is
    unreachable.
    """
    from app.db.session import AsyncSessionLocal
    from app.services import reconcile

    async with AsyncSessionLocal() as db:
        report = await reconcile.check_consistency(db)

    if not report.neo4j_enabled:
        status_ = "ok"
    elif not report.checked:
        status_ = "unknown"
    elif report.in_sync:
        status_ = "ok"
    else:
        status_ = "drift"
    return {
        "status": status_,
        "neo4j_enabled": report.neo4j_enabled,
        "checked": report.checked,
        "in_sync": report.in_sync,
        "drift_count": report.drift_count,
        "counts": report.as_dict()["counts"],
    }


@app.get("/", tags=["health"])
async def root() -> dict[str, str]:
    return {"name": settings.PROJECT_NAME, "docs": "/docs", "version": "0.1.0"}
