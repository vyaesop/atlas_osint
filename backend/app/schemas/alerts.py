from __future__ import annotations

import uuid

from pydantic import BaseModel


class AlertRead(BaseModel):
    kind: str
    severity: str
    title: str
    detail: str
    score: float
    entity_id: uuid.UUID | None


class AlertsResponse(BaseModel):
    count: int
    alerts: list[AlertRead]
