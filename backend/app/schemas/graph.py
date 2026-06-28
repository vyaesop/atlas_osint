from __future__ import annotations

from pydantic import BaseModel

from app.schemas.entity import EntityRead
from app.schemas.relationship import RelationshipRead


class GraphResponse(BaseModel):
    """A subgraph: the requested node(s), their neighbors, and connecting edges."""

    nodes: list[EntityRead]
    edges: list[RelationshipRead]
