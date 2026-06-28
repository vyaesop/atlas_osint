from __future__ import annotations

import uuid

from pydantic import BaseModel


class ChainStatusRead(BaseModel):
    valid: bool
    entries_checked: int
    broken_at: str | None


class RetentionPreview(BaseModel):
    older_than_days: int
    ai_only: bool
    count: int
    entity_ids: list[uuid.UUID]


class PurgeResult(BaseModel):
    older_than_days: int
    ai_only: bool
    purged: int


class ExportEntityRead(BaseModel):
    id: str
    type: str
    name: str
    classification: str
    redacted: bool


class ExportRelationshipRead(BaseModel):
    id: str
    type: str
    source: str
    target: str


class ExportPackageRead(BaseModel):
    case_id: str
    entities: list[ExportEntityRead]
    relationships: list[ExportRelationshipRead]
    redacted_count: int


class InsiderFindingRead(BaseModel):
    actor_id: str
    total_actions: int
    deletes: int
    off_hours: int
    distinct_targets: int
    risk: str
    flags: list[str]


class InsiderResponse(BaseModel):
    count: int
    findings: list[InsiderFindingRead]
