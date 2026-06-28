"""Domain enumerations shared by models and schemas."""
from __future__ import annotations

import enum


class Role(str, enum.Enum):
    ADMIN = "admin"
    RESEARCHER = "researcher"
    VIEWER = "viewer"


class EntityType(str, enum.Enum):
    PERSON = "person"
    ORGANIZATION = "organization"
    COMPANY = "company"
    GOVERNMENT_AGENCY = "government_agency"
    EVENT = "event"
    LOCATION = "location"
    DOCUMENT = "document"
    ASSET = "asset"


class RelationshipType(str, enum.Enum):
    WORKS_FOR = "WORKS_FOR"
    OWNS = "OWNS"
    FOUNDED = "FOUNDED"
    MEMBER_OF = "MEMBER_OF"
    INVESTED_IN = "INVESTED_IN"
    PARTNER_OF = "PARTNER_OF"
    ATTENDED = "ATTENDED"
    PARTICIPATED_IN = "PARTICIPATED_IN"
    LOCATED_IN = "LOCATED_IN"
    REPORTED_BY = "REPORTED_BY"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    MANAGES = "MANAGES"
    SUPERVISES = "SUPERVISES"
    FUNDED_BY = "FUNDED_BY"
    CONNECTED_TO = "CONNECTED_TO"


class AuditAction(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class EvidenceStance(str, enum.Enum):
    """Whether a piece of evidence supports or contradicts the claim it backs."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"


class VerificationStatus(str, enum.Enum):
    """Review state of a piece of evidence.

    AI-extracted evidence (Phase 4) lands as ``unverified`` and must be promoted
    by a researcher; ``disputed`` flags items a reviewer has actively rejected.
    """

    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    DISPUTED = "disputed"


class DocumentStatus(str, enum.Enum):
    """Lifecycle of an ingested source document."""

    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"


class SourceReliability(str, enum.Enum):
    """Admiralty/NATO source-reliability rating (the letter axis)."""

    A = "A"  # Completely reliable
    B = "B"  # Usually reliable
    C = "C"  # Fairly reliable
    D = "D"  # Not usually reliable
    E = "E"  # Unreliable
    F = "F"  # Reliability cannot be judged


class InfoCredibility(str, enum.Enum):
    """Admiralty/NATO information-credibility rating (the number axis)."""

    C1 = "1"  # Confirmed by other sources
    C2 = "2"  # Probably true
    C3 = "3"  # Possibly true
    C4 = "4"  # Doubtful
    C5 = "5"  # Improbable
    C6 = "6"  # Truth cannot be judged


class AchConsistency(str, enum.Enum):
    """How a piece of evidence relates to a hypothesis in an ACH matrix."""

    CONSISTENT = "consistent"
    INCONSISTENT = "inconsistent"
    NEUTRAL = "neutral"
    NA = "na"  # not applicable / not relevant


class AnnotationKind(str, enum.Enum):
    """Structured analytic annotations attached to an entity or relationship."""

    NOTE = "note"
    ASSUMPTION = "assumption"          # a key assumption underpinning analysis
    DISSENT = "dissent"               # a recorded analytic disagreement
    DEVILS_ADVOCATE = "devils_advocate"  # a deliberate challenge to the line
