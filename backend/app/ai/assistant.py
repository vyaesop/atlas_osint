"""Natural-language → graph query (#24).

Translates a plain-English question into a structured :class:`QuerySpec`, then
executes it deterministically against the graph. Following the platform's
local-first pattern, a dependency-free **heuristic** parser is the default (and
keeps this fully testable offline); setting ``AI_PROVIDER=gemini`` swaps in
Gemini for more robust parsing behind the same interface.
"""
from __future__ import annotations

import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.graph_loader import GraphFilters
from app.analytics.models import PathKind, PathResult
from app.analytics.service import analytics_service
from app.core.config import settings
from app.models.entity import Entity
from app.models.enums import EntityType
from app.models.relationship import Relationship

_TYPE_KEYWORDS = {
    "people": EntityType.PERSON, "person": EntityType.PERSON, "individual": EntityType.PERSON,
    "company": EntityType.COMPANY, "companies": EntityType.COMPANY,
    "organization": EntityType.ORGANIZATION, "organisation": EntityType.ORGANIZATION,
    "org": EntityType.ORGANIZATION,
    "agency": EntityType.GOVERNMENT_AGENCY, "government": EntityType.GOVERNMENT_AGENCY,
    "event": EntityType.EVENT, "events": EntityType.EVENT,
    "location": EntityType.LOCATION, "place": EntityType.LOCATION,
    "document": EntityType.DOCUMENT, "asset": EntityType.ASSET, "wallet": EntityType.ASSET,
}


@dataclass(slots=True)
class QuerySpec:
    intent: str                         # search | neighbors | path
    entity_type: EntityType | None = None
    name: str | None = None
    target_name: str | None = None
    limit: int = 25


@dataclass(slots=True)
class QueryResult:
    intent: str
    message: str
    entities: list[Entity] = field(default_factory=list)
    path: PathResult | None = None


class Assistant(ABC):
    name: str

    @abstractmethod
    def parse(self, question: str) -> QuerySpec: ...


class HeuristicAssistant(Assistant):
    name = "heuristic"

    _PATH = re.compile(r"between\s+(.+?)\s+and\s+(.+?)[?.]?$", re.IGNORECASE)
    _NEIGHBORS = re.compile(
        r"(?:connected to|connections of|neighbou?rs of|linked to|associated with|"
        r"contacts of|related to)\s+(.+?)[?.]?$",
        re.IGNORECASE,
    )
    _NAMED = re.compile(r"(?:named|called)\s+(.+?)[?.]?$", re.IGNORECASE)

    def parse(self, question: str) -> QuerySpec:
        q = question.strip()
        if (m := self._PATH.search(q)):
            return QuerySpec(intent="path", name=m.group(1).strip(), target_name=m.group(2).strip())
        if (m := self._NEIGHBORS.search(q)):
            return QuerySpec(intent="neighbors", name=m.group(1).strip())

        etype = next((t for kw, t in _TYPE_KEYWORDS.items() if re.search(rf"\b{kw}\b", q, re.I)), None)
        name = None
        if (m := self._NAMED.search(q)):
            name = m.group(1).strip()
        return QuerySpec(intent="search", entity_type=etype, name=name)


def build_assistant() -> Assistant:
    if settings.AI_PROVIDER == "gemini" and settings.GEMINI_API_KEY:
        try:
            from app.ai.gemini_assistant import GeminiAssistant

            return GeminiAssistant()
        except Exception:  # pragma: no cover - fall back if SDK/key unavailable
            return HeuristicAssistant()
    return HeuristicAssistant()


# --------------------------------------------------------------------------- #
# Deterministic execution
# --------------------------------------------------------------------------- #

async def _find_entity(db: AsyncSession, name: str) -> Entity | None:
    stmt = select(Entity).where(Entity.name.ilike(f"%{name}%")).limit(1)
    return (await db.execute(stmt)).scalars().first()


async def execute_spec(db: AsyncSession, spec: QuerySpec) -> QueryResult:
    if spec.intent == "neighbors":
        base = await _find_entity(db, spec.name or "")
        if base is None:
            return QueryResult(intent=spec.intent, message=f"No entity matching '{spec.name}'.")
        rels = list((await db.execute(
            select(Relationship).where(
                or_(Relationship.source_id == base.id, Relationship.target_id == base.id)
            )
        )).scalars().all())
        neighbor_ids = {r.target_id if r.source_id == base.id else r.source_id for r in rels}
        entities = list((await db.execute(
            select(Entity).where(Entity.id.in_(neighbor_ids))
        )).scalars().all()) if neighbor_ids else []
        return QueryResult(intent=spec.intent, entities=entities,
                           message=f"{len(entities)} entities connected to {base.name}.")

    if spec.intent == "path":
        a = await _find_entity(db, spec.name or "")
        b = await _find_entity(db, spec.target_name or "")
        if a is None or b is None:
            return QueryResult(intent=spec.intent, message="Could not resolve both endpoints.")
        path = await analytics_service.paths(
            db, str(a.id), str(b.id), PathKind.SHORTEST, GraphFilters(), k=1
        )
        msg = (f"Path found between {a.name} and {b.name}." if path.found
               else f"No path between {a.name} and {b.name}.")
        return QueryResult(intent=spec.intent, path=path, message=msg)

    # search
    stmt = select(Entity)
    if spec.entity_type is not None:
        stmt = stmt.where(Entity.type == spec.entity_type)
    if spec.name:
        stmt = stmt.where(Entity.name.ilike(f"%{spec.name}%"))
    stmt = stmt.limit(spec.limit)
    entities = list((await db.execute(stmt)).scalars().all())
    descriptor = spec.entity_type.value if spec.entity_type else "entities"
    return QueryResult(intent="search", entities=entities,
                       message=f"{len(entities)} {descriptor} found.")


assistant = build_assistant()
