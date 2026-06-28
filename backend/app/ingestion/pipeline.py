"""Document → graph ingestion pipeline.

Flow: store the document (raw text + a graph node) → run AI extraction →
materialize extracted entities/relationships as **AI-generated, unverified**
graph objects, each backed by AI-generated evidence quoting the source. Because
the evidence is unverified, confidence stays 0 until a researcher confirms it —
AI claims never silently inflate scores.

The pipeline owns no transaction; the caller commits.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models import ExtractionResult
from app.ai.service import ai_service
from app.crud import entity as entity_crud
from app.models.document import Document
from app.models.entity import Entity
from app.models.enums import (
    DocumentStatus,
    EntityType,
    EvidenceStance,
    VerificationStatus,
)
from app.models.evidence import Evidence
from app.models.relationship import Relationship


@dataclass(slots=True)
class IngestionOutcome:
    document: Document
    document_node: Entity
    entities: list[Entity] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    entities_created: int = 0
    relationships_created: int = 0
    provider: str = "heuristic"


async def ingest_text(
    db: AsyncSession,
    *,
    text: str,
    title: str,
    actor_id: uuid.UUID,
    filename: str | None = None,
    content_type: str | None = None,
) -> IngestionOutcome:
    # 1) Document graph node + record.
    doc_node = Entity(
        type=EntityType.DOCUMENT,
        name=title,
        aliases=[],
        description=None,
        properties={"filename": filename} if filename else {},
        created_by=actor_id,
        is_ai_generated=False,
    )
    db.add(doc_node)
    await db.flush()

    document = Document(
        title=title, filename=filename, content_type=content_type,
        raw_text=text, status=DocumentStatus.PENDING, entity_id=doc_node.id,
        created_by=actor_id,
    )
    db.add(document)
    await db.flush()

    # 2) Extract.
    try:
        result: ExtractionResult = await ai_service.extract(text)
    except Exception as exc:  # pragma: no cover - provider/runtime failure
        document.status = DocumentStatus.FAILED
        document.extraction = {"error": str(exc)}
        await db.flush()
        raise

    outcome = IngestionOutcome(
        document=document, document_node=doc_node, provider=result.provider
    )

    # 3) Materialize entities (dedupe by name+type).
    name_to_entity: dict[str, Entity] = {}
    for extracted in result.entities:
        entity = await _resolve_entity(
            db, extracted.name, extracted.type, actor_id, doc_node.name, outcome
        )
        if entity is not None:
            name_to_entity[extracted.name.lower()] = entity
            if extracted.context:
                _add_evidence(db, doc_node.name, extracted.context, actor_id,
                              entity_id=entity.id)

    # 4) Materialize relationships between resolved entities.
    for rel in result.relationships:
        src = name_to_entity.get(rel.source_name.lower()) or await _resolve_entity(
            db, rel.source_name, EntityType.PERSON, actor_id, doc_node.name, outcome
        )
        tgt = name_to_entity.get(rel.target_name.lower()) or await _resolve_entity(
            db, rel.target_name, EntityType.ORGANIZATION, actor_id, doc_node.name, outcome
        )
        if src is None or tgt is None or src.id == tgt.id:
            continue
        name_to_entity.setdefault(rel.source_name.lower(), src)
        name_to_entity.setdefault(rel.target_name.lower(), tgt)

        relationship = Relationship(
            type=rel.type, source_id=src.id, target_id=tgt.id,
            confidence_score=0.0, notes=None, properties={},
            is_ai_generated=True, created_by=actor_id,
        )
        db.add(relationship)
        await db.flush()
        outcome.relationships.append(relationship)
        outcome.relationships_created += 1
        if rel.supporting_text:
            _add_evidence(db, doc_node.name, rel.supporting_text, actor_id,
                          relationship_id=relationship.id)

    # 5) Finalize the document record.
    document.status = DocumentStatus.PROCESSED
    document.extraction = {
        "provider": result.provider,
        "entities_created": outcome.entities_created,
        "relationships_created": outcome.relationships_created,
        "entities_total": len(result.entities),
        "relationships_total": len(result.relationships),
    }
    await db.flush()
    return outcome


async def _resolve_entity(
    db: AsyncSession,
    name: str,
    etype: EntityType,
    actor_id: uuid.UUID,
    doc_title: str,
    outcome: IngestionOutcome,
) -> Entity | None:
    name = name.strip()
    if not name:
        return None
    existing = await entity_crud.get_by_name(db, name, etype)
    if existing is not None:
        if existing not in outcome.entities:
            outcome.entities.append(existing)
        return existing
    entity = Entity(
        type=etype, name=name, aliases=[], description=None, properties={},
        confidence_score=0.0, is_ai_generated=True, created_by=actor_id,
    )
    db.add(entity)
    await db.flush()
    outcome.entities.append(entity)
    outcome.entities_created += 1
    return entity


def _add_evidence(
    db: AsyncSession,
    doc_title: str,
    quote: str,
    actor_id: uuid.UUID,
    *,
    entity_id: uuid.UUID | None = None,
    relationship_id: uuid.UUID | None = None,
) -> None:
    db.add(
        Evidence(
            title=f"Extracted from: {doc_title}",
            source=doc_title,
            quote=quote[:2000],
            reliability_score=0.0,
            stance=EvidenceStance.SUPPORTS,
            verification_status=VerificationStatus.UNVERIFIED,
            is_ai_generated=True,
            entity_id=entity_id,
            relationship_id=relationship_id,
            created_by=actor_id,
        )
    )
