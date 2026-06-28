"""Cryptocurrency transaction ingestion → wallet flow graph (#23).

Imports a list of transactions (from a block-explorer export or analyst CSV/JSON)
and builds wallet ASSET nodes linked by directed transfer edges
(source = sender, target = recipient), with amount/tx-hash kept on the edge.
The existing path / centrality / influence analytics then work directly on the
money-flow graph. Offline; no chain access required.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import entity as entity_crud
from app.ingestion.pipeline import IngestionOutcome
from app.models.document import Document
from app.models.entity import Entity
from app.models.enums import DocumentStatus, EntityType, RelationshipType
from app.models.relationship import Relationship


@dataclass(slots=True)
class Transaction:
    from_address: str
    to_address: str
    amount: float | None = None
    tx_hash: str | None = None
    timestamp: str | None = None


async def import_transactions(
    db: AsyncSession, *, asset: str, transactions: list[Transaction], actor_id: uuid.UUID
) -> IngestionOutcome:
    asset_type = f"{asset.lower()}_wallet"
    title = f"Crypto import: {asset} ({len(transactions)} tx)"

    doc_node = Entity(
        type=EntityType.DOCUMENT, name=title, aliases=[], description=None,
        properties={"kind": "crypto_import", "asset": asset}, created_by=actor_id,
        is_ai_generated=False,
    )
    db.add(doc_node)
    await db.flush()
    document = Document(
        title=title, filename=None, content_type="application/json",
        raw_text="", status=DocumentStatus.PENDING, entity_id=doc_node.id, created_by=actor_id,
    )
    db.add(document)
    await db.flush()

    outcome = IngestionOutcome(document=document, document_node=doc_node, provider="crypto-import")
    wallets: dict[str, Entity] = {}

    async def wallet(address: str) -> Entity:
        key = address.strip()
        if key in wallets:
            return wallets[key]
        existing = await entity_crud.get_by_name(db, key, EntityType.ASSET)
        if existing is None:
            existing = Entity(
                type=EntityType.ASSET, name=key, aliases=[], description=None,
                properties={"asset_type": asset_type, "blockchain": asset},
                confidence_score=0.0, is_ai_generated=True, created_by=actor_id,
            )
            db.add(existing)
            await db.flush()
            outcome.entities.append(existing)
            outcome.entities_created += 1
        else:
            outcome.entities.append(existing)
        wallets[key] = existing
        return existing

    for tx in transactions:
        if not tx.from_address.strip() or not tx.to_address.strip():
            continue
        src = await wallet(tx.from_address)
        dst = await wallet(tx.to_address)
        if src.id == dst.id:
            continue
        note = f"{tx.amount if tx.amount is not None else '?'} {asset}"
        if tx.tx_hash:
            note += f" · tx {tx.tx_hash[:16]}"
        rel = Relationship(
            type=RelationshipType.ASSOCIATED_WITH, source_id=src.id, target_id=dst.id,
            confidence_score=0.0, notes=note,
            properties={"amount": tx.amount, "asset": asset, "tx_hash": tx.tx_hash,
                        "timestamp": tx.timestamp, "flow": "sender->recipient"},
            is_ai_generated=True, created_by=actor_id,
        )
        db.add(rel)
        await db.flush()
        outcome.relationships.append(rel)
        outcome.relationships_created += 1

    document.status = DocumentStatus.PROCESSED
    document.extraction = {
        "provider": "crypto-import",
        "entities_created": outcome.entities_created,
        "relationships_created": outcome.relationships_created,
        "entities_total": len(wallets),
        "relationships_total": outcome.relationships_created,
    }
    await db.flush()
    return outcome
