from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.entity import Entity
from app.models.enums import EntityType
from app.models.user import User
from app.schemas.search import ReindexResult, SearchHitRead, SuggestionRead
from app.search.service import search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=list[SearchHitRead])
async def search(
    q: str = Query(min_length=1, description="Search query"),
    type: list[EntityType] | None = Query(default=None, description="Filter by entity type(s)"),
    limit: int = Query(default=20, ge=1, le=100),
    fuzzy: bool = Query(default=True, description="Enable fuzzy / typo-tolerant matching"),
    semantic: bool = Query(default=True, description="Enable semantic (embedding) ranking"),
    _: User = Depends(get_current_user),
):
    """Full-text + fuzzy + alias + semantic search over entities."""
    types = [t.value for t in type] if type else None
    hits = await search_service.search(
        q, types=types, limit=limit, fuzzy=fuzzy, semantic=semantic
    )
    return [
        SearchHitRead(
            id=h.id, type=h.type, name=h.name, aliases=h.aliases,
            score=h.score, matched_on=h.matched_on,
        )
        for h in hits
    ]


@router.get("/suggest", response_model=list[SuggestionRead])
async def suggest(
    q: str = Query(min_length=1, description="Prefix to autocomplete"),
    limit: int = Query(default=10, ge=1, le=25),
    _: User = Depends(get_current_user),
):
    """Type-ahead entity suggestions for the given prefix."""
    suggestions = await search_service.suggest(q, limit=limit)
    return [
        SuggestionRead(id=s.id, type=s.type, name=s.name, score=s.score)
        for s in suggestions
    ]


@router.post("/reindex", response_model=ReindexResult)
async def reindex(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Rebuild the search index from PostgreSQL (the source of truth).

    Useful after a backend switch or to repair drift; admin-only.
    """
    await search_service.ensure_ready()
    result = await db.stream_scalars(select(Entity))
    count = 0
    async for entity in result:
        await search_service.index_entity(entity)
        count += 1
    return ReindexResult(indexed=count)
