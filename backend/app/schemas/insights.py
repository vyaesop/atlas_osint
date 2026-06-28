from __future__ import annotations

import uuid

from pydantic import BaseModel


# --- #49 risk ---
class RiskScoreRead(BaseModel):
    entity_id: uuid.UUID
    name: str
    score: float
    band: str
    factors: dict[str, float]
    reasons: list[str]


class RiskListResponse(BaseModel):
    count: int
    results: list[RiskScoreRead]


# --- #47 diff ---
class DiffItemRead(BaseModel):
    id: str
    kind: str
    label: str


class NetworkDiffResponse(BaseModel):
    since: str
    added_entities: list[DiffItemRead]
    modified_entities: list[DiffItemRead]
    added_relationships: list[DiffItemRead]
    modified_relationships: list[DiffItemRead]
    removed: list[DiffItemRead]


# --- #5 lineage ---
class LineageNodeRead(BaseModel):
    id: str
    kind: str
    label: str
    ai_generated: bool
    verified: bool | None


class LineageEdgeRead(BaseModel):
    source: str
    target: str
    relation: str


class LineageResponse(BaseModel):
    entity_id: uuid.UUID
    summary: str
    nodes: list[LineageNodeRead]
    edges: list[LineageEdgeRead]


# --- #46 facets ---
class FacetBucketRead(BaseModel):
    value: str
    count: int


class FacetsResponse(BaseModel):
    total: int
    by_type: list[FacetBucketRead]
    by_classification: list[FacetBucketRead]
    by_confidence: list[FacetBucketRead]
    by_provenance: list[FacetBucketRead]
    by_month: list[FacetBucketRead]
