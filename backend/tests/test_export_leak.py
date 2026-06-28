"""Compartmented data must not leak through export or facets (Task 14).

An intelligence platform's redaction is only as good as its worst leak path.
These tests adversarially probe the two aggregate paths most likely to leak —
sanitized case export (#41) and facet histograms (#46) — proving a
low-clearance requester can neither read nor *infer the existence of* data above
their clearance/compartments.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.casework import Case, CaseItem
from app.models.entity import Entity
from app.models.enums import (
    CaseItemType,
    Classification,
    EntityType,
    RelationshipType,
    Role,
)
from app.models.relationship import Relationship
from app.models.user import User
from app.services import facets as facets_service
from app.services import governance


class _Requester:
    """Minimal subject for ABAC (matches what user_can_access reads)."""

    def __init__(self, clearance: Classification, compartments: list[str]):
        self.clearance = clearance
        self.compartments = compartments


async def _case_with_mixed_classification(db: AsyncSession):
    public = Entity(type=EntityType.PERSON, name="Public Person",
                    classification=Classification.UNCLASSIFIED)
    secret = Entity(type=EntityType.PERSON, name="SECRET Source Codename",
                    classification=Classification.SECRET)
    compartmented = Entity(type=EntityType.PERSON, name="Compartmented Asset",
                           classification=Classification.UNCLASSIFIED, compartments=["GAMMA"])
    db.add_all([public, secret, compartmented])
    await db.flush()

    # An edge between the two restricted entities.
    rel = Relationship(type=RelationshipType.ASSOCIATED_WITH,
                       source_id=public.id, target_id=secret.id)
    db.add(rel)

    case = Case(title="Mixed case")
    db.add(case)
    await db.flush()
    for e in (public, secret, compartmented):
        db.add(CaseItem(case_id=case.id, item_type=CaseItemType.ENTITY, item_id=e.id))
    await db.commit()
    return case, public, secret, compartmented


async def test_export_redacts_above_clearance(db_session: AsyncSession):
    case, public, secret, comp = await _case_with_mixed_classification(db_session)
    requester = _Requester(Classification.UNCLASSIFIED, [])

    pkg = await governance.export_case(db_session, case.id, requester)
    by_id = {e.id: e for e in pkg.entities}

    # The cleared entity is exported in full...
    assert by_id[str(public.id)].name == "Public Person"
    assert by_id[str(public.id)].redacted is False
    # ...the SECRET one is present only as a redacted stub (no codename leaks).
    assert by_id[str(secret.id)].name == "[REDACTED]"
    assert by_id[str(secret.id)].redacted is True
    # ...and the compartmented asset is redacted despite being UNCLASSIFIED.
    assert by_id[str(comp.id)].redacted is True
    assert pkg.redacted_count == 2


async def test_export_drops_edges_touching_redacted_nodes(db_session: AsyncSession):
    case, public, secret, comp = await _case_with_mixed_classification(db_session)
    requester = _Requester(Classification.UNCLASSIFIED, [])

    pkg = await governance.export_case(db_session, case.id, requester)
    # The only edge connects public→secret; since secret is not releasable, the
    # edge must be withheld (it would otherwise confirm the hidden node exists).
    assert pkg.relationships == []


async def test_export_full_when_cleared(db_session: AsyncSession):
    case, public, secret, comp = await _case_with_mixed_classification(db_session)
    cleared = _Requester(Classification.TOP_SECRET, ["GAMMA"])

    pkg = await governance.export_case(db_session, case.id, cleared)
    assert pkg.redacted_count == 0
    assert all(not e.redacted for e in pkg.entities)
    # With both endpoints releasable, the edge is now included.
    assert len(pkg.relationships) == 1


async def test_facets_do_not_leak_compartmented_counts(db_session: AsyncSession):
    await _case_with_mixed_classification(db_session)
    low = _Requester(Classification.UNCLASSIFIED, [])

    facets = await facets_service.compute_facets(db_session, user=low)
    # Only the single fully-public entity is counted; SECRET + compartmented hidden.
    assert facets.total == 1
    classifications = {b.value for b in facets.by_classification}
    assert "secret" not in classifications


async def test_facets_full_for_cleared_user(db_session: AsyncSession):
    await _case_with_mixed_classification(db_session)
    cleared = _Requester(Classification.TOP_SECRET, ["GAMMA"])

    facets = await facets_service.compute_facets(db_session, user=cleared)
    assert facets.total == 3
