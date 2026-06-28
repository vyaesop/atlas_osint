"""Dependency-free, deterministic extractor.

Not as capable as an LLM, but private, fast, and reproducible — a sensible
default for local deployments. It recognizes:

* **Organizations / companies / agencies** by name suffix (Inc, Corp, Ltd,
  Foundation, University, Agency, Ministry, …).
* **People** via honorific/role prefixes (Mr., Dr., President, CEO, Senator …)
  or "<Name> founded/works for <Org>" patterns.
* **Relationships** via a small set of sentence templates (WORKS_FOR, FOUNDED,
  PARTNER_OF, …), plus ASSOCIATED_WITH for two people in the same sentence.

The LLM provider supersedes this when configured; the output shape is identical
so the ingestion pipeline doesn't care which produced it.
"""
from __future__ import annotations

import re

from app.ai.models import ExtractedEntity, ExtractedRelationship, ExtractionResult
from app.models.enums import EntityType, RelationshipType

# A proper-noun phrase: one or more Capitalized words (allowing & and .).
_NAME = r"[A-Z][\w.&'-]*(?:\s+[A-Z][\w.&'-]*){0,4}"

_ORG_SUFFIX_TYPE = [
    (r"\b(?:Corporation|Corp|Inc|LLC|Ltd|Limited|Company|Co|Holdings|Group|Bank|Industries|Partners|Capital)\b",
     EntityType.COMPANY),
    (r"\b(?:Foundation|University|Institute|Association|Council|Society|Committee|Organization|NGO)\b",
     EntityType.ORGANIZATION),
    (r"\b(?:Agency|Department|Ministry|Bureau|Administration|Commission|Authority)\b",
     EntityType.GOVERNMENT_AGENCY),
]

_PERSON_PREFIX = re.compile(
    rf"\b(?:Mr|Mrs|Ms|Dr|Prof|President|Senator|Governor|Chairman|CEO|CFO|CTO|Director|Minister|Ambassador)\.?\s+({_NAME})"
)

# Relationship sentence templates → (type, swap_source_target).
_REL_PATTERNS: list[tuple[re.Pattern[str], RelationshipType, bool]] = [
    (re.compile(rf"({_NAME})\s+(?:is|was|serves as|served as)\s+(?:the\s+)?(?:CEO|chief executive|president|chairman|chair|director|head)\s+of\s+({_NAME})"),
     RelationshipType.WORKS_FOR, False),
    (re.compile(rf"({_NAME}),?\s+(?:the\s+)?(?:CEO|president|chairman|founder|director)\s+of\s+({_NAME})"),
     RelationshipType.WORKS_FOR, False),
    (re.compile(rf"({_NAME})\s+founded\s+({_NAME})"),
     RelationshipType.FOUNDED, False),
    (re.compile(rf"({_NAME})\s+(?:works|worked)\s+(?:for|at)\s+({_NAME})"),
     RelationshipType.WORKS_FOR, False),
    (re.compile(rf"({_NAME})\s+(?:owns|acquired)\s+({_NAME})"),
     RelationshipType.OWNS, False),
    (re.compile(rf"({_NAME})\s+invested\s+in\s+({_NAME})"),
     RelationshipType.INVESTED_IN, False),
    (re.compile(rf"({_NAME})\s+(?:partnered|partners)\s+with\s+({_NAME})"),
     RelationshipType.PARTNER_OF, False),
    (re.compile(rf"({_NAME})\s+is\s+(?:a\s+)?member\s+of\s+({_NAME})"),
     RelationshipType.MEMBER_OF, False),
]

# Words that look like names but aren't entities.
_STOPWORDS = {
    "The", "This", "That", "These", "Those", "It", "He", "She", "They",
    "According", "However", "Meanwhile", "In", "On", "At", "A", "An",
}


def _classify_org(name: str) -> EntityType | None:
    for pattern, etype in _ORG_SUFFIX_TYPE:
        if re.search(pattern, name):
            return etype
    return None


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


_HONORIFIC_PREFIX = re.compile(
    r"^(?:(?:Mr|Mrs|Ms|Dr|Prof|President|Senator|Governor|Chairman|CEO|CFO|CTO|"
    r"Director|Minister|Ambassador)\.?\s+)+"
)


def _clean(name: str) -> str:
    name = name.strip(" .,;:'\"").strip()
    # Drop a leading honorific/role so "Dr. Jane Powell" and "Jane Powell" merge.
    return _HONORIFIC_PREFIX.sub("", name).strip()


class HeuristicExtractor:
    name = "heuristic"

    async def extract(self, text: str) -> ExtractionResult:
        entities: dict[str, ExtractedEntity] = {}
        relationships: list[ExtractedRelationship] = []

        def add_entity(name: str, etype: EntityType, context: str | None) -> str | None:
            name = _clean(name)
            if not name or name in _STOPWORDS or len(name) < 2:
                return None
            key = name.lower()
            if key not in entities:
                entities[key] = ExtractedEntity(name=name, type=etype, context=context)
            return name

        for sentence in _sentences(text):
            # Organizations / companies / agencies by suffix.
            for match in re.finditer(_NAME, sentence):
                candidate = _clean(match.group(0))
                etype = _classify_org(candidate)
                if etype is not None:
                    add_entity(candidate, etype, sentence)

            # People via honorific / role prefix.
            for match in _PERSON_PREFIX.finditer(sentence):
                add_entity(match.group(1), EntityType.PERSON, sentence)

            # Relationship templates.
            for pattern, rtype, swap in _REL_PATTERNS:
                for m in pattern.finditer(sentence):
                    src, tgt = _clean(m.group(1)), _clean(m.group(2))
                    if swap:
                        src, tgt = tgt, src
                    if not src or not tgt or src.lower() == tgt.lower():
                        continue
                    # Best-effort type the endpoints if not already known.
                    src_type = entities.get(src.lower())
                    tgt_type = _classify_org(tgt) or EntityType.ORGANIZATION
                    add_entity(src, src_type.type if src_type else EntityType.PERSON, sentence)
                    add_entity(tgt, tgt_type, sentence)
                    relationships.append(
                        ExtractedRelationship(
                            source_name=src, target_name=tgt, type=rtype,
                            supporting_text=sentence, confidence=0.5,
                        )
                    )

        return ExtractionResult(
            entities=list(entities.values()),
            relationships=relationships,
            provider=self.name,
        )

    async def summarize(self, subject: str, context: str) -> str:
        """Template summary — no model, so we assemble from the structured context."""
        context = context.strip()
        if not context:
            return f"{subject}: no connections or evidence recorded yet."
        snippet = context if len(context) <= 600 else context[:600] + "…"
        return (
            f"Summary of {subject} (auto-generated from recorded graph data): {snippet}"
        )
