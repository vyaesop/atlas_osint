from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import EntityType, RelationshipType
from app.schemas.entity import EntityRead


class NeighborRef(BaseModel):
    id: uuid.UUID
    name: str
    type: EntityType
    relationship_id: uuid.UUID
    relationship_type: RelationshipType
    direction: str  # "outgoing" | "incoming"
    confidence: float
    is_ai_generated: bool


class DocumentRef(BaseModel):
    # Either a Document entity node (id set) or a bare evidence source (id null).
    id: uuid.UUID | None
    title: str
    source: str | None = None


class InfluenceMetrics(BaseModel):
    total_connections: int
    degree_centrality: float
    pagerank: float
    connections_by_type: dict[str, int]


class DashboardStats(BaseModel):
    total_connections: int
    total_evidence: int
    total_documents: int
    confidence_score: float


class DashboardSections(BaseModel):
    connections: list[NeighborRef] = []
    organizations: list[NeighborRef] = []   # person → org affiliations
    members: list[NeighborRef] = []          # org ← people
    partners: list[NeighborRef] = []         # PARTNER_OF
    events: list[NeighborRef] = []           # attended / participated
    locations: list[NeighborRef] = []        # LOCATED_IN
    related_entities: list[NeighborRef] = []
    documents: list[DocumentRef] = []


class DashboardResponse(BaseModel):
    entity: EntityRead
    kind: str  # "person" | "organization" | "company" | "event" | "generic"
    stats: DashboardStats
    influence: InfluenceMetrics
    sections: DashboardSections


class TimelineItem(BaseModel):
    date: date
    end_date: date | None = None
    kind: str  # "attribute" | "relationship" | "event"
    label: str
    relationship_type: RelationshipType | None = None
    related_id: uuid.UUID | None = None
    related_name: str | None = None
    confidence: float = 0.0


class TimelineResponse(BaseModel):
    entity_id: uuid.UUID
    entity_name: str
    items: list[TimelineItem]
