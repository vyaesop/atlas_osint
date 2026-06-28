from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel


class GeoFeatureRead(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    lat: float
    lon: float
    confidence: float
    placed_via: str
    location_name: str | None


class MapResponse(BaseModel):
    count: int
    features: list[GeoFeatureRead]


class VisitRead(BaseModel):
    date: date | None
    location_id: uuid.UUID
    location_name: str
    lat: float
    lon: float
    source: str
    label: str


class PatternOfLifeResponse(BaseModel):
    entity_id: uuid.UUID
    entity_name: str
    place_count: int
    total_distance_km: float
    visits: list[VisitRead]


class ColocationPairRead(BaseModel):
    a_id: uuid.UUID
    a_name: str
    b_id: uuid.UUID
    b_name: str
    location_id: uuid.UUID
    location_name: str
    shared_visits: int
    temporally_overlapping: bool
    already_connected: bool
    suggested_type: str
    score: float


class ColocationResponse(BaseModel):
    window_days: int
    pairs: list[ColocationPairRead]
