"""Audit-log helper with a tamper-evident hash chain (#39).

Each entry stores ``entry_hash = sha256(canonical_content + prev_hash)`` where
``prev_hash`` is the previous entry's hash. Any retroactive edit to a logged
field breaks the chain from that point on, which :func:`verify_chain` detects.

Ordering note: the chain is linked explicitly via ``prev_hash`` and walked in
insertion order. A production deployment under heavy concurrent writes would add
a monotonic sequence column; here the tip is taken by ``created_at`` (entries
are flushed as written), which is correct for sequential request handling.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.enums import AuditAction


def _canonical(actor_id, action, target_table, target_id, changes, reason, prev_hash) -> str:
    payload = {
        "actor_id": str(actor_id) if actor_id else None,
        "action": action.value if isinstance(action, AuditAction) else str(action),
        "target_table": target_table,
        "target_id": str(target_id) if target_id else None,
        "changes": changes or {},
        "reason": reason,
        "prev_hash": prev_hash,
    }
    return json.dumps(payload, sort_keys=True, default=str)


def compute_hash(*, actor_id, action, target_table, target_id, changes, reason, prev_hash) -> str:
    canonical = _canonical(actor_id, action, target_table, target_id, changes, reason, prev_hash)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def record_audit(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: AuditAction,
    target_table: str,
    target_id: uuid.UUID | None,
    changes: dict | None = None,
    reason: str | None = None,
) -> None:
    """Add a hash-chained audit entry to the session (flushed; caller commits)."""
    # The tip is the chain's tail: the entry whose hash nothing else links back
    # to. Deriving it from linkage (not timestamps) keeps the chain linear even
    # when many entries share a created_at under load.
    rows = (await db.execute(select(AuditLog.entry_hash, AuditLog.prev_hash))).all()
    hashes = {r.entry_hash for r in rows if r.entry_hash}
    used_as_prev = {r.prev_hash for r in rows if r.prev_hash}
    tails = hashes - used_as_prev
    prev_hash = next(iter(tails)) if tails else None

    entry_hash = compute_hash(
        actor_id=actor_id, action=action, target_table=target_table, target_id=target_id,
        changes=changes or {}, reason=reason, prev_hash=prev_hash,
    )
    db.add(AuditLog(
        actor_id=actor_id, action=action, target_table=target_table, target_id=target_id,
        changes=changes or {}, reason=reason, prev_hash=prev_hash, entry_hash=entry_hash,
    ))
    await db.flush()


@dataclass(slots=True)
class ChainStatus:
    valid: bool
    entries_checked: int
    broken_at: str | None = None  # id of the first tampered/broken entry


async def verify_chain(db: AsyncSession) -> ChainStatus:
    """Walk the chain by ``prev_hash`` linkage (robust to storage order) and
    report the first tampered/broken entry. A retroactive edit either makes an
    entry's recomputed hash mismatch, or orphans the entries that linked to it."""
    entries = list((await db.execute(select(AuditLog))).scalars().all())
    total = len(entries)
    if total == 0:
        return ChainStatus(valid=True, entries_checked=0)

    children: dict[str | None, list[AuditLog]] = {}
    for e in entries:
        children.setdefault(e.prev_hash, []).append(e)

    genesis = children.get(None, [])
    if len(genesis) != 1:
        return ChainStatus(valid=False, entries_checked=0, broken_at="genesis")

    prev_hash: str | None = None
    current: AuditLog | None = genesis[0]
    checked = 0
    while current is not None:
        expected = compute_hash(
            actor_id=current.actor_id, action=current.action,
            target_table=current.target_table, target_id=current.target_id,
            changes=current.changes, reason=current.reason, prev_hash=prev_hash,
        )
        if current.entry_hash != expected:
            return ChainStatus(valid=False, entries_checked=checked, broken_at=str(current.id))
        checked += 1
        nxt = children.get(current.entry_hash, [])
        if len(nxt) > 1:  # fork
            return ChainStatus(valid=False, entries_checked=checked, broken_at=str(nxt[0].id))
        prev_hash = current.entry_hash
        current = nxt[0] if nxt else None

    # Any entries not reached were orphaned by tampering.
    return ChainStatus(valid=(checked == total), entries_checked=checked,
                       broken_at=None if checked == total else "orphaned")
