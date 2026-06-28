"""Agentic investigation assistant (#27).

Given a lead entity, autonomously runs the platform's analyses — connectivity,
sanctions screening, duplicate detection, contradiction check, selector
extraction — and turns the results into findings plus concrete recommended next
actions (including data gaps to fill). Deterministic and testable; an optional
AI narrative summarises the plan. Every action it takes is an existing,
auditable read — it proposes, the analyst disposes.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity
from app.models.enums import EntityType, RelationshipType
from app.models.evidence import Evidence
from app.models.relationship import Relationship
from app.services import confidence, entity_resolution, sanctions
from app.transforms.selectors import extract_selectors


@dataclass(slots=True)
class Finding:
    kind: str
    severity: str       # high | medium | low | info
    detail: str


@dataclass(slots=True)
class Investigation:
    entity: Entity
    findings: list[Finding] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)


async def investigate(db: AsyncSession, entity: Entity) -> Investigation:
    inv = Investigation(entity=entity)
    f, a = inv.findings, inv.recommended_actions

    # 1) Connectivity.
    rels = list((await db.execute(
        select(Relationship).where(
            or_(Relationship.source_id == entity.id, Relationship.target_id == entity.id)
        )
    )).scalars().all())
    rel_types = {r.type for r in rels}
    f.append(Finding("connectivity", "info", f"{len(rels)} direct relationships."))
    if len(rels) == 0:
        a.append("Entity is isolated — ingest documents or run transforms to find links.")

    # 2) Sanctions screening.
    hits = await sanctions.screen_entity(db, entity, threshold=0.85)
    if hits:
        f.append(Finding("sanctions", "high",
                         f"Matches watchlist: {hits[0].entry_name} ({hits[0].program})."))
        a.append("Verify the watchlist match and escalate per compliance policy.")

    # 3) Duplicate candidates involving this entity.
    dups = [
        c for c in await entity_resolution.find_duplicates(db, threshold=0.85, limit=100)
        if str(entity.id) in (c.a_id, c.b_id)
    ]
    if dups:
        other = dups[0].b_name if dups[0].a_id == str(entity.id) else dups[0].a_name
        f.append(Finding("duplicate", "medium", f"Likely duplicate of '{other}'."))
        a.append(f"Review and merge with '{other}' if they are the same entity.")

    # 4) Contradictions.
    conf = await confidence.summarize_entity(db, entity.id)
    if conf.is_contradicted:
        f.append(Finding("contradiction", "high",
                         "Contradicting verified evidence — treat as disputed."))
        a.append("Adjudicate the contradicting sources before relying on this entity.")

    # 5) Selectors hiding in free text.
    text = "\n".join([entity.description or "", " ".join(entity.aliases or [])])
    selectors = extract_selectors(text)
    if selectors:
        kinds = sorted({s.kind for s in selectors})
        f.append(Finding("selectors", "info", f"Selectors in text: {', '.join(kinds)}."))
        a.append("Run the extract-selectors transform to pivot on these identifiers.")

    # 6) Data-gap analysis.
    if entity.type is EntityType.PERSON:
        if RelationshipType.LOCATED_IN not in rel_types:
            a.append("No location data — add LOCATED_IN edges for geospatial analysis.")
        if not any(r.type in {RelationshipType.WORKS_FOR, RelationshipType.MEMBER_OF} for r in rels):
            a.append("No affiliation recorded — establish employer/membership.")
    evidence_count = len((await db.execute(
        select(Evidence).where(Evidence.entity_id == entity.id)
    )).scalars().all())
    if evidence_count == 0:
        a.append("No evidence attached — corroborate key claims with sources.")

    if not a:
        a.append("No immediate gaps — entity is well-characterised.")
    return inv
