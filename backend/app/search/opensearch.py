"""OpenSearch-backed search with a text + kNN-vector index.

Imports of ``opensearchpy`` are deferred to construction time so the dependency
is only required when this backend is actually selected.
"""
from __future__ import annotations

import logging

from app.core.config import settings
from app.search.embeddings import get_embedder
from app.search.models import SearchDocument, SearchHit, Suggestion

logger = logging.getLogger(__name__)


def _index_body(dim: int) -> dict:
    return {
        "settings": {"index": {"knn": True}},
        "mappings": {
            "properties": {
                "type": {"type": "keyword"},
                "name": {"type": "text", "fields": {"raw": {"type": "keyword"}}},
                "aliases": {"type": "text"},
                "description": {"type": "text"},
                "confidence_score": {"type": "float"},
                "embedding": {"type": "knn_vector", "dimension": dim},
            }
        },
    }


class OpenSearchBackend:
    def __init__(self) -> None:
        from opensearchpy import AsyncOpenSearch  # deferred import

        self._client = AsyncOpenSearch(hosts=[settings.OPENSEARCH_URL])
        self._index = settings.OPENSEARCH_INDEX

    async def ensure_ready(self) -> None:
        if not await self._client.indices.exists(index=self._index):
            await self._client.indices.create(
                index=self._index, body=_index_body(settings.EMBEDDING_DIM)
            )

    async def index(self, doc: SearchDocument) -> None:
        await self._client.index(
            index=self._index,
            id=doc.id,
            body={
                "type": doc.type,
                "name": doc.name,
                "aliases": doc.aliases,
                "description": doc.description,
                "confidence_score": doc.confidence_score,
                "embedding": doc.embedding,
            },
            refresh=True,
        )

    async def delete(self, doc_id: str) -> None:
        try:
            await self._client.delete(index=self._index, id=doc_id, refresh=True)
        except Exception:  # pragma: no cover - not-found is fine
            logger.debug("delete miss for %s", doc_id)

    async def search(
        self,
        query: str,
        *,
        types: list[str] | None = None,
        limit: int = 20,
        fuzzy: bool = True,
        semantic: bool = True,
    ) -> list[SearchHit]:
        should: list[dict] = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["name^3", "aliases^2", "description"],
                    "fuzziness": "AUTO" if fuzzy else "0",
                }
            }
        ]
        if semantic:
            should.append(
                {"knn": {"embedding": {"vector": get_embedder().embed(query), "k": limit}}}
            )

        bool_query: dict = {"should": should, "minimum_should_match": 1}
        if types:
            bool_query["filter"] = [{"terms": {"type": types}}]

        resp = await self._client.search(
            index=self._index, body={"size": limit, "query": {"bool": bool_query}}
        )
        hits = []
        max_score = resp["hits"].get("max_score") or 1.0
        for h in resp["hits"]["hits"]:
            src = h["_source"]
            hits.append(
                SearchHit(
                    id=h["_id"], type=src["type"], name=src["name"],
                    aliases=src.get("aliases", []),
                    score=round((h["_score"] or 0.0) / max_score, 4),
                    matched_on="opensearch",
                )
            )
        return hits

    async def suggest(self, prefix: str, *, limit: int = 10) -> list[Suggestion]:
        resp = await self._client.search(
            index=self._index,
            body={
                "size": limit,
                "query": {"match_phrase_prefix": {"name": {"query": prefix}}},
            },
        )
        return [
            Suggestion(
                id=h["_id"], type=h["_source"]["type"],
                name=h["_source"]["name"], score=round(h["_score"] or 0.0, 4),
            )
            for h in resp["hits"]["hits"]
        ]

    async def close(self) -> None:  # pragma: no cover
        await self._client.close()
