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
    try:
        await neo4j_client.connect()
        await neo4j_client.ensure_constraints()
        logger.info("Connected to Neo4j and ensured constraints.")
    except Exception:  # pragma: no cover - allow API to boot if graph is down
        logger.exception("Neo4j unavailable at startup; graph sync will retry per-write.")
    try:
        await search_service.ensure_ready()
        logger.info("Search backend ready (%s).", settings.SEARCH_BACKEND)
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


@app.get("/", tags=["health"])
async def root() -> dict[str, str]:
    return {"name": settings.PROJECT_NAME, "docs": "/docs", "version": "0.1.0"}
