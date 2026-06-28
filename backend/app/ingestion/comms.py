"""Email / comms ingestion → communication network (#22).

Parses EML or MBOX content with the standard library only (``email`` +
``email.utils``), then builds a graph: each participant becomes a Person and
each message links its sender to every recipient with the subject/date as
evidence. Fully offline.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from email import message_from_string
from email.utils import getaddresses, parsedate_to_datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import entity as entity_crud
from app.ingestion.pipeline import IngestionOutcome
from app.models.document import Document
from app.models.entity import Entity
from app.models.enums import (
    DocumentStatus,
    EntityType,
    EvidenceStance,
    RelationshipType,
    VerificationStatus,
)
from app.models.evidence import Evidence
from app.models.relationship import Relationship

# mbox separates messages with a line beginning "From " (the envelope sender).
_MBOX_SEP = re.compile(r"(?m)^From .*\r?\n")


@dataclass(slots=True)
class ParsedEmail:
    sender: tuple[str, str] | None  # (display, email)
    recipients: list[tuple[str, str]] = field(default_factory=list)
    subject: str = ""
    date: str | None = None


def parse_emails(content: str) -> list[ParsedEmail]:
    """Parse one EML or a multi-message MBOX string into structured messages."""
    chunks = [c for c in _MBOX_SEP.split(content) if c.strip()]
    if not chunks:
        chunks = [content]

    parsed: list[ParsedEmail] = []
    for chunk in chunks:
        msg = message_from_string(chunk)
        from_pairs = getaddresses(msg.get_all("from", []))
        to_pairs = getaddresses(msg.get_all("to", []) + msg.get_all("cc", []))
        sender = _clean(from_pairs[0]) if from_pairs else None
        recipients = [_clean(p) for p in to_pairs if p[1]]
        if sender is None and not recipients:
            continue
        date = None
        try:
            dt = parsedate_to_datetime(msg.get("date")) if msg.get("date") else None
            date = dt.date().isoformat() if dt else None
        except (TypeError, ValueError):
            date = None
        parsed.append(ParsedEmail(
            sender=sender, recipients=recipients,
            subject=(msg.get("subject") or "").strip(), date=date,
        ))
    return parsed


def _clean(pair: tuple[str, str]) -> tuple[str, str]:
    name, email = pair
    return (name.strip() or email.strip()), email.strip().lower()


async def ingest_emails(
    db: AsyncSession, *, content: str, title: str, actor_id: uuid.UUID
) -> IngestionOutcome:
    messages = parse_emails(content)

    doc_node = Entity(
        type=EntityType.DOCUMENT, name=title, aliases=[], description=None,
        properties={"kind": "email_corpus"}, created_by=actor_id, is_ai_generated=False,
    )
    db.add(doc_node)
    await db.flush()
    document = Document(
        title=title, filename=None, content_type="message/rfc822",
        raw_text=content[:50000], status=DocumentStatus.PENDING,
        entity_id=doc_node.id, created_by=actor_id,
    )
    db.add(document)
    await db.flush()

    outcome = IngestionOutcome(document=document, document_node=doc_node, provider="email-parser")
    by_email: dict[str, Entity] = {}

    async def person(display: str, email: str) -> Entity:
        if email in by_email:
            return by_email[email]
        existing = await entity_crud.get_by_name(db, display, EntityType.PERSON)
        if existing is None:
            existing = Entity(
                type=EntityType.PERSON, name=display,
                aliases=[email] if email and email != display.lower() else [],
                description=None, properties={}, confidence_score=0.0,
                is_ai_generated=True, created_by=actor_id,
            )
            db.add(existing)
            await db.flush()
            outcome.entities.append(existing)
            outcome.entities_created += 1
        else:
            outcome.entities.append(existing)
        by_email[email] = existing
        return existing

    for m in messages:
        if m.sender is None:
            continue
        sender = await person(*m.sender)
        quote = f"Email: {m.subject or '(no subject)'}" + (f" ({m.date})" if m.date else "")
        for rname, remail in m.recipients:
            if not remail or remail == m.sender[1]:
                continue
            recipient = await person(rname, remail)
            if recipient.id == sender.id:
                continue
            rel = Relationship(
                type=RelationshipType.CONNECTED_TO, source_id=sender.id, target_id=recipient.id,
                start_date=None, confidence_score=0.0,
                notes=quote, properties={"subject": m.subject, "date": m.date},
                is_ai_generated=True, created_by=actor_id,
            )
            db.add(rel)
            await db.flush()
            outcome.relationships.append(rel)
            outcome.relationships_created += 1
            db.add(Evidence(
                title=f"Extracted from: {title}", source=title, quote=quote[:2000],
                reliability_score=0.0, stance=EvidenceStance.SUPPORTS,
                verification_status=VerificationStatus.UNVERIFIED, is_ai_generated=True,
                relationship_id=rel.id, created_by=actor_id,
            ))

    document.status = DocumentStatus.PROCESSED
    document.extraction = {
        "provider": "email-parser",
        "entities_created": outcome.entities_created,
        "relationships_created": outcome.relationships_created,
        "entities_total": len(by_email),
        "relationships_total": outcome.relationships_created,
        "messages": len(messages),
    }
    await db.flush()
    return outcome
