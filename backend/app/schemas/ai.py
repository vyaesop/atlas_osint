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


class QueryResponse(BaseModel):
    intent: str
    provider: str
    message: str
    entities: list[EntityRead] = Field(default_factory=list)
    path: PathRead | None = None
