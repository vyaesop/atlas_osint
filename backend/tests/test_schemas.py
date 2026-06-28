"""Validation tests for the per-type entity properties and evidence targeting."""
from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.models.enums import EntityType
from app.schemas.entity import EntityCreate
from app.schemas.evidence import EvidenceCreate


def test_person_properties_accepted():
    e = EntityCreate(
        type=EntityType.PERSON,
        name="Ada Lovelace",
        properties={"nationality": "British", "occupation": "Mathematician"},
    )
    assert e.properties["nationality"] == "British"


def test_unknown_property_rejected():
    with pytest.raises(ValidationError):
        EntityCreate(
            type=EntityType.PERSON,
            name="Ada",
            properties={"market_value": 10_000_000},  # company field, not person
        )


def test_company_market_value_typed():
    e = EntityCreate(
        type=EntityType.COMPANY,
        name="Acme",
        properties={"industry": "Defense", "market_value": 5_000_000.0},
    )
    assert e.properties["market_value"] == 5_000_000.0


def test_evidence_requires_exactly_one_target():
    with pytest.raises(ValidationError):
        EvidenceCreate(title="x")  # no target
    with pytest.raises(ValidationError):
        EvidenceCreate(title="x", entity_id=uuid.uuid4(), relationship_id=uuid.uuid4())
    # exactly one is fine
    EvidenceCreate(title="x", entity_id=uuid.uuid4())
