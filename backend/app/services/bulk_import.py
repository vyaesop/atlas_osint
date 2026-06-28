"""Batch import of entities + relationships in a single transaction.

Entities carry a local ``ref`` so relationships can wire them up before any IDs
exist. Projection to Neo4j/search goes through the job dispatcher, so a large
import offloads to the worker when ``JOBS_ENABLED`` (otherwise inline). The
caller owns the commit; this flushes.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import entity as entity_crud
from app.models.entity import Entity
from app.models.relationship import Relationship
from app.schemas.bulk import BulkImportRequest, BulkImportResult
from app.schemas.entity import validate_properties


@dataclass(slots=True)
class BulkOutcome:
    result: BulkImportResult
    entities: list[Entity] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)


async def bulk_import(
    db: AsyncSession, payload: BulkImportRequest, *, actor_id: uuid.UUID
) -> BulkOutcome:
    ref_to_id: dict[str, uuid.UUID] = {}
    created_entities: list[Entity] = []
    created = matched = skipped = 0

    for item in payload.entities:
        props = validate_properties(item.type, item.properties)
        existing = None
        if payload.deduplicate:
            existing = await entity_crud.get_by_name(db, item.name, item.type)
        if existing is not None:
            ref_to_id[item.ref] = existing.id
            matched += 1
            continue
        entity = Entity(
            type=item.type, name=item.name, aliases=item.aliases,
            description=item.description, properties=props,
            confidence_score=item.confidence_score, created_by=actor_id,
        )
        db.add(entity)
        created_entities.append(entity)
        created += 1

    await db.flush()  # assign IDs to the newly created entities
    for item, entity in zip(
        (e for e in payload.entities if e.ref not in ref_to_id), created_entities
    ):
        ref_to_id[item.ref] = entity.id

    created_rels: list[Relationship] = []
    for rel in payload.relationships:
        src = ref_to_id.get(rel.source_ref)
        tgt = ref_to_id.get(rel.target_ref)
        if src is None or tgt is None or src == tgt:
            skipped += 1
            continue
        relationship = Relationship(
            type=rel.type, source_id=src, target_id=tgt,
            confidence_score=rel.confidence_score, notes=rel.notes,
            properties={}, created_by=actor_id,
        )
        db.add(relationship)
        created_rels.append(relationship)

    await db.flush()

    return BulkOutcome(
        result=BulkImportResult(
            entities_created=created, entities_matched=matched,
            relationships_created=len(created_rels), skipped=skipped,
        ),
        entities=created_entities,
        relationships=created_rels,
    )
