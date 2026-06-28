from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.analytics import PathRead
from app.schemas.dashboard import DashboardResponse
from app.schemas.entity import EntityRead
from app.schemas.evidence import ConfidenceSummary


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class ReportResponse(BaseModel):
    subject: EntityRead
    provider: str
    narrative: str
    key_findings: list[str]
    confidence: ConfidenceSummary
    timeline_event_count: int
    dashboard: DashboardResponse


# --- #25 RAG ---
class RagRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    k: int = Field(default=5, ge=1, le=20)


class CitationRead(BaseModel):
    document_id: str
    entity_id: str | None
    title: str
    snippet: str
    score: float


class RagResponse(BaseModel):
    answer: str
    provider: str
    citations: list[CitationRead]


# --- #27 agentic investigation ---
class FindingRead(BaseModel):
    kind: str
    severity: str
    detail: str


class InvestigateResponse(BaseModel):
    subject: EntityRead
    provider: str
    narrative: str
    findings: list[FindingRead]
    recommended_actions: list[str]


# --- #30 deepfake / synthetic-media flag ---
class DeepfakeRequest(BaseModel):
    filename: str | None = None
    software: str | None = None
    metadata: dict | None = None
    text: str | None = None


class MediaRiskResponse(BaseModel):
    risk: str
    score: float
    reasons: list[str]


# --- #20/#21 multimodal ---
class MultimodalResponse(BaseModel):
    provider: str
    text: str
    ingested: bool = False
    document_id: str | None = None
    entities_created: int = 0
    relationships_created: int = 0


class QueryResponse(BaseModel):
    intent: str
    provider: str
    message: str
    entities: list[EntityRead] = Field(default_factory=list)
    path: PathRead | None = None
