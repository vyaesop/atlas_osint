"""High-level search facade used by the API and write paths.

Owns backend selection, turns ORM entities into :class:`SearchDocument`s
(computing embeddings at index time), and degrades gracefully: an indexing
failure never breaks the originating write, mirroring the graph-sync contract.
"""
from __future__ import annotations

import logging

from app.core.config import settings
from app.models.entity import Entity
from app.search.backend import SearchBackend
from app.search.embeddings import get_embedder
from app.search.inmemory import InMemorySearchBackend
from app.search.models import SearchDocument, SearchHit, Suggestion

logger = logging.getLogger(__name__)


def _build_backend() -> SearchBackend:
    if settings.SEARCH_BACKEND == "opensearch":
        from app.search.opensearch import OpenSearchBackend  # deferred

        return OpenSearchBackend()
    return InMemorySearchBackend()


def entity_to_document(entity: Entity) -> SearchDocument:
    doc = SearchDocument(
        id=str(entity.id),
        type=entity.type.value,
        name=entity.name,
        aliases=list(entity.aliases or []),
        description=entity.description,
        confidence_score=entity.confidence_score,
    )
    if settings.SEMANTIC_SEARCH_ENABLED:
        doc.embedding = get_embedder().embed(doc.text_blob())
    return doc


class SearchService:
    def __init__(self, backend: SearchBackend | None = None) -> None:
        self._backend = backend or _build_backend()

    @property
    def backend(self) -> SearchBackend:
        return self._backend

    async def ensure_ready(self) -> None:
        await self._backend.ensure_ready()

    async def index_entity(self, entity: Entity) -> None:
        try:
            await self._backend.index(entity_to_document(entity))
        except Exception:  # pragma: no cover - defensive, like graph_sync
            logger.exception("Search indexing failed for entity %s", entity.id)

    async def remove_entity(self, entity_id) -> None:
        try:
            await self._backend.delete(str(entity_id))
        except Exception:  # pragma: no cover
            logger.exception("Search delete failed for entity %s", entity_id)

    async def search(
        self,
        query: str,
        *,
        types: list[str] | None = None,
        limit: int = 20,
        fuzzy: bool = True,
        semantic: bool = True,
    ) -> list[SearchHit]:
        return await self._backend.search(
            query, types=types, limit=limit, fuzzy=fuzzy, semantic=semantic
        )

    async def suggest(self, prefix: str, *, limit: int = 10) -> list[Suggestion]:
        return await self._backend.suggest(prefix, limit=limit)


search_service = SearchService()
