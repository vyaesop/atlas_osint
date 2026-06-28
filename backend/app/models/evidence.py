from __future__ import annotations

import uuid
from datetime import date

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import GUID
from app.models.enums import (
    Classification,
    EvidenceStance,
    InfoCredibility,
    SourceReliability,
    VerificationStatus,
)
from app.services.source_grading import admiralty_weight


class Evidence(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A source-backed piece of evidence supporting an entity or relationship.

    Exactly one of ``entity_id`` / ``relationship_id`` must be set, enforced by
    a DB-level check constraint. Each item declares a ``stance`` (supports /
    contradicts / neutral) and carries a review ``verification_status``; the
    confidence engine aggregates these into the parent's confidence score.
    """

    __tablename__ = "evidence"

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    source: Mapped[str | None] = mapped_column(String(512), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reliability_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Admiralty/NATO source grading (#3). Optional; when both are set they
    # derive the effective reliability used by the confidence engine, otherwise
    # the manual ``reliability_score`` above is used.
    source_reliability: Mapped[SourceReliability | None] = mapped_column(
        SAEnum(SourceReliability, name="source_reliability"), nullable=True
    )
    info_credibility: Mapped[InfoCredibility | None] = mapped_column(
        SAEnum(InfoCredibility, name="info_credibility"), nullable=True
    )
    classification: Mapped[Classification] = mapped_column(
        SAEnum(Classification, name="classification"),
        default=Classification.UNCLASSIFIED, nullable=False,
    )

    stance: Mapped[EvidenceStance] = mapped_column(
        SAEnum(EvidenceStance, name="evidence_stance"),
        default=EvidenceStance.SUPPORTS,
        nullable=False,
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, name="verification_status"),
        default=VerificationStatus.UNVERIFIED,
        nullable=False,
        index=True,
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    relationship_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        ForeignKey("relationships.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN entity_id IS NULL THEN 0 ELSE 1 END) "
            "+ (CASE WHEN relationship_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="ck_evidence_exactly_one_target",
        ),
    )

    @property
    def effective_reliability(self) -> float:
        """Reliability weight the confidence engine should use for this item.

        Prefers the Admiralty grade when both axes are set; otherwise falls back
        to the manually-entered ``reliability_score``.
        """
        if self.source_reliability is not None and self.info_credibility is not None:
            return admiralty_weight(self.source_reliability, self.info_credibility)
        return self.reliability_score
