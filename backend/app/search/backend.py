"""Search backend protocol implemented by the in-memory and OpenSearch backends."""
from __future__ import annotations

from typing import Protocol

from app.search.models import SearchDocument, SearchHit, Suggestion


class SearchBackend(Protocol):
    async def ensure_ready(self) -> None:
        """Create indices/mappings if needed. Safe to call repeatedly."""
        ...

    async def index(self, doc: SearchDocument) -> None: ...

    async def delete(self, doc_id: str) -> None: ...

    async def search(
        self,
        query: str,
        *,
        types: list[str] | None = None,
        limit: int = 20,
        fuzzy: bool = True,
        semantic: bool = True,
    ) -> list[SearchHit]: ...

    async def suggest(self, prefix: str, *, limit: int = 10) -> list[Suggestion]: ...
