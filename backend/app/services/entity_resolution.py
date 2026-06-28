"""Entity resolution / deduplication (#13).

Two parts:

* **candidate detection** — a pure, blocked pairwise scan that proposes likely
  duplicate entities (same type, similar name/aliases), so an analyst can review
  before merging. Blocking by a normalized name prefix keeps it near-linear.
* **merge / unmerge** — repoint a duplicate's relationships, evidence, and
  annotations onto the kept entity, fold in its aliases/properties, delete it,
  and record everything in an :class:`EntityMerge` so the operation is fully
  reversible and auditable.

Postgres stays the source of truth; Neo4j is resynced best-effort by the caller.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotation import Annotation
from app.models.entity import Entity
from app.models.entity_merge import EntityMerge
from app.models.enums import EntityType, RelationshipType
from app.models.evidence import Evidence
from app.models.relationship import Relationship

_WORD = re.compile(r"[^a-z0-9]+")


def _normalize(name: str) -> str:
    return _WORD.sub(" ", name.lower()).strip()


def _tokens(name: str) -> set[str]:
    return {t for t in _normalize(name).split() if t}


def _levenshtein_ratio(a: str, b: str) -> float:
    """Similarity in [0, 1] from edit distance (pure, no deps)."""
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    dist = prev[-1]
    return 1.0 - dist / max(len(a), len(b))


def similarity(name_a: str, aliases_a: list[str], name_b: str, aliases_b: list[str]) -> tuple[float, str]:
    """Best similarity across names + aliases, with a short reason."""
    na, nb = _normalize(name_a), _normalize(name_b)
    if na == nb:
        return 1.0, "identical normalized name"

    names_a = {na} | {_normalize(x) for x in aliases_a}
    names_b = {nb} | {_normalize(x) for x in aliases_b}
    if names_a & names_b:
        return 0.95, "shared name/alias"

    # Token Jaccard captures word reorderings ("John Smith" vs "Smith, John").
    ta, tb = _tokens(name_a), _tokens(name_b)
    jaccard = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
    lev = _levenshtein_ratio(na, nb)
    score = max(jaccard, lev)
    reason = "token overlap" if jaccard >= lev else "string similarity"
    return round(score, 4), reason


@dataclass(slots=True)
class DuplicateCandidate:
    a_id: str
    a_name: str
    b_id: str
    b_name: str
    type: str
    score: float
    reason: str
    shared_neighbors: int


async def find_duplicates(
    db: AsyncSession, *, threshold: float = 0.85, limit: int = 50, max_scan: int = 5000
) -> list[DuplicateCandidate]:
    entities = list((await db.execute(select(Entity).limit(max_scan))).scalars().all())

    # Adjacency for the shared-neighbor signal.
    rels = list((await db.execute(select(Relationship))).scalars().all())
    neighbors: dict[uuid.UUID, set[uuid.UUID]] = {}
    for r in rels:
        neighbors.setdefault(r.source_id, set()).add(r.target_id)
        neighbors.setdefault(r.target_id, set()).add(r.source_id)

    # Block by (type, normalized-name prefix) to avoid an O(n²) all-pairs scan.
    blocks: dict[tuple[str, str], list[Entity]] = {}
    for e in entities:
        key = (e.type.value, _normalize(e.name)[:3])
        blocks.setdefault(key, []).append(e)

    candidates: list[DuplicateCandidate] = []
    for block in blocks.values():
        for i, a in enumerate(block):
            for b in block[i + 1:]:
                score, reason = similarity(a.name, a.aliases, b.name, b.aliases)
                if score < threshold:
                    continue
                shared = len(neighbors.get(a.id, set()) & neighbors.get(b.id, set()))
                candidates.append(DuplicateCandidate(
                    a_id=str(a.id), a_name=a.name, b_id=str(b.id), b_name=b.name,
                    type=a.type.value, score=score, reason=reason, shared_neighbors=shared,
                ))

    candidates.sort(key=lambda c: (c.score, c.shared_neighbors), reverse=True)
    return candidates[:limit]


async def merge(
    db: AsyncSession, kept: Entity, merged: Entity, *, actor_id: uuid.UUID | None
) -> EntityMerge:
    """Merge ``merged`` into ``kept`` and return the reversible record. Flushes
    but does not commit (the caller owns the transaction)."""
    snapshot = {
        "id": str(merged.id), "type": merged.type.value, "name": merged.name,
        "aliases": list(merged.aliases or []), "description": merged.description,
        "properties": dict(merged.properties or {}),
        "confidence_score": merged.confidence_score,
        "is_ai_generated": merged.is_ai_generated,
        "created_by": str(merged.created_by) if merged.created_by else None,
    }

    # 1) Relationships incident to the merged entity.
    incident = list((await db.execute(
        select(Relationship).where(
            or_(Relationship.source_id == merged.id, Relationship.target_id == merged.id)
        )
    )).scalars().all())
    moved_rels: list[dict] = []
    for r in incident:
        record = {"id": str(r.id), "type": r.type.value, "old_source": str(r.source_id),
                  "old_target": str(r.target_id), "deleted": False}
        new_source = kept.id if r.source_id == merged.id else r.source_id
        new_target = kept.id if r.target_id == merged.id else r.target_id
        if new_source == new_target:
            # Would become a self-loop (the two were directly connected) → drop it.
            record["deleted"] = True
            await db.delete(r)
        else:
            r.source_id, r.target_id = new_source, new_target
        moved_rels.append(record)

    # 2) Evidence + annotations.
    moved_evidence = [str(e.id) for e in (await db.execute(
        select(Evidence).where(Evidence.entity_id == merged.id)
    )).scalars().all()]
    for ev_id in moved_evidence:
        ev = await db.get(Evidence, uuid.UUID(ev_id))
        if ev is not None:
            ev.entity_id = kept.id

    moved_annotations = [str(a.id) for a in (await db.execute(
        select(Annotation).where(Annotation.entity_id == merged.id)
    )).scalars().all()]
    for an_id in moved_annotations:
        an = await db.get(Annotation, uuid.UUID(an_id))
        if an is not None:
            an.entity_id = kept.id

    # 3) Fold aliases + properties into the kept entity (without overwriting).
    existing_aliases = set(kept.aliases or [])
    added_aliases: list[str] = []
    for candidate in [merged.name, *(merged.aliases or [])]:
        if candidate and candidate not in existing_aliases and candidate != kept.name:
            existing_aliases.add(candidate)
            added_aliases.append(candidate)
    kept.aliases = sorted(existing_aliases)

    kept_props = dict(kept.properties or {})
    added_keys: list[str] = []
    for k, v in (merged.properties or {}).items():
        if k not in kept_props:
            kept_props[k] = v
            added_keys.append(k)
    kept.properties = kept_props

    # 4) Delete the merged entity and record the operation.
    await db.delete(merged)

    record = EntityMerge(
        kept_id=kept.id, merged_id=uuid.UUID(snapshot["id"]), merged_name=snapshot["name"],
        merged_snapshot=snapshot, moved_relationships=moved_rels,
        moved_evidence_ids=moved_evidence, moved_annotation_ids=moved_annotations,
        added_aliases=added_aliases, added_property_keys=added_keys, created_by=actor_id,
    )
    db.add(record)
    await db.flush()
    return record


async def unmerge(db: AsyncSession, record: EntityMerge) -> Entity:
    """Reverse a merge using its stored record. Flushes; caller commits."""
    snap = record.merged_snapshot
    restored = Entity(
        id=uuid.UUID(snap["id"]), type=EntityType(snap["type"]), name=snap["name"],
        aliases=list(snap.get("aliases") or []), description=snap.get("description"),
        properties=dict(snap.get("properties") or {}),
        confidence_score=snap.get("confidence_score", 0.0),
        is_ai_generated=snap.get("is_ai_generated", False),
        created_by=uuid.UUID(snap["created_by"]) if snap.get("created_by") else None,
    )
    db.add(restored)
    await db.flush()

    # Restore relationships to their original endpoints (recreate dropped ones).
    for rec in record.moved_relationships:
        old_source = uuid.UUID(rec["old_source"])
        old_target = uuid.UUID(rec["old_target"])
        if rec.get("deleted"):
            db.add(Relationship(
                id=uuid.UUID(rec["id"]),
                type=RelationshipType(rec.get("type", "ASSOCIATED_WITH")),
                source_id=old_source, target_id=old_target,
            ))
        else:
            r = await db.get(Relationship, uuid.UUID(rec["id"]))
            if r is not None:
                r.source_id, r.target_id = old_source, old_target

    for ev_id in record.moved_evidence_ids:
        ev = await db.get(Evidence, uuid.UUID(ev_id))
        if ev is not None:
            ev.entity_id = restored.id

    for an_id in record.moved_annotation_ids:
        an = await db.get(Annotation, uuid.UUID(an_id))
        if an is not None:
            an.entity_id = restored.id

    kept = await db.get(Entity, record.kept_id)
    if kept is not None:
        kept.aliases = sorted(set(kept.aliases or []) - set(record.added_aliases))
        props = dict(kept.properties or {})
        for k in record.added_property_keys:
            props.pop(k, None)
        kept.properties = props

    record.undone = True
    await db.flush()
    return restored
