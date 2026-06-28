"""Entity request/response schemas with per-type property validation.

The unified ``entities`` table stores type-specific fields in JSONB. To keep
those fields meaningful, each :class:`EntityType` has a Pydantic property model
defining its allowed/typed fields (from the spec's domain model). On create /
update we validate the submitted ``properties`` against the right model.
"""
from __future__ import annotations

import uuid
from datetime import date
from datetime import date as Date  # alias avoids shadowing by a field named `date`
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import Classification, EntityType


# --- Per-type property models (extra fields rejected for data hygiene) ---

class _Props(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PersonProps(_Props):
    birth_date: date | None = None
    nationality: str | None = None
    occupation: str | None = None
    biography: str | None = None
    profile_image: str | None = None


class OrganizationProps(_Props):
    org_type: str | None = None
    founded_date: date | None = None
    website: str | None = None
    headquarters: str | None = None


class CompanyProps(_Props):
    industry: str | None = None
    market_value: float | None = None


class GovernmentAgencyProps(_Props):
    jurisdiction: str | None = None


class EventProps(_Props):
    date: Date | None = None
    location: str | None = None


class LocationProps(_Props):
    latitude: float | None = None
    longitude: float | None = None
    country: str | None = None
    region: str | None = None


class DocumentProps(_Props):
    doc_type: str | None = None
    source: str | None = None
    publication_date: date | None = None
    file_reference: str | None = None


class AssetProps(_Props):
    asset_type: str | None = None


PROPERTY_MODELS: dict[EntityType, type[_Props]] = {
    EntityType.PERSON: PersonProps,
    EntityType.ORGANIZATION: OrganizationProps,
    EntityType.COMPANY: CompanyProps,
    EntityType.GOVERNMENT_AGENCY: GovernmentAgencyProps,
    EntityType.EVENT: EventProps,
    EntityType.LOCATION: LocationProps,
    EntityType.DOCUMENT: DocumentProps,
    EntityType.ASSET: AssetProps,
}


def validate_properties(entity_type: EntityType, properties: dict[str, Any]) -> dict[str, Any]:
    model = PROPERTY_MODELS[entity_type]
    return model.model_validate(properties or {}).model_dump(exclude_none=True, mode="json")


# --- API schemas ---

class EntityCreate(BaseModel):
    type: EntityType
    name: str = Field(min_length=1, max_length=512)
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    classification: Classification = Classification.UNCLASSIFIED
    compartments: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_props(self) -> "EntityCreate":
        self.properties = validate_properties(self.type, self.properties)
        return self


class EntityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=512)
    aliases: list[str] | None = None
    description: str | None = None
    properties: dict[str, Any] | None = None
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    classification: Classification | None = None
    compartments: list[str] | None = None
    legal_hold: bool | None = None


class EntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: EntityType
    name: str
    aliases: list[str]
    description: str | None
    properties: dict[str, Any]
    confidence_score: float
    is_ai_generated: bool
    classification: Classification
    compartments: list[str]
    legal_hold: bool
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
