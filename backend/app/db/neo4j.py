"""Neo4j async driver wrapper and connection lifecycle.

The driver is a long-lived singleton created at app startup and closed at
shutdown. Query helpers are thin; higher-level graph projection logic lives in
``app.services.graph_sync``.
"""
from __future__ import annotations

from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

from app.core.config import settings


class Neo4jClient:
    def __init__(self) -> None:
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )

    async def close(self) -> None:
        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    @property
    def driver(self) -> AsyncDriver:
        if self._driver is None:
            raise RuntimeError("Neo4j driver not initialized. Call connect() first.")
        return self._driver

    async def verify_connectivity(self) -> bool:
        await self.connect()
        await self.driver.verify_connectivity()
        return True

    async def run_write(self, query: str, **params: Any) -> list[dict[str, Any]]:
        async with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            result = await session.run(query, **params)
            return [record.data() async for record in result]

    async def run_read(self, query: str, **params: Any) -> list[dict[str, Any]]:
        async with self.driver.session(
            database=settings.NEO4J_DATABASE, default_access_mode="READ"
        ) as session:
            result = await session.run(query, **params)
            return [record.data() async for record in result]

    async def ensure_constraints(self) -> None:
        """Create uniqueness constraints so entity ids map 1:1 with Postgres."""
        await self.run_write(
            "CREATE CONSTRAINT entity_id IF NOT EXISTS "
            "FOR (e:Entity) REQUIRE e.id IS UNIQUE"
        )


neo4j_client = Neo4jClient()
