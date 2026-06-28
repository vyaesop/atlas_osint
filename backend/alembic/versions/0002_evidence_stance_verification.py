"""evidence stance + verification workflow

Revision ID: 0002_evidence_stance
Revises: 0001_initial
Create Date: 2026-06-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_evidence_stance"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


evidence_stance = sa.Enum("supports", "contradicts", "neutral", name="evidence_stance")
verification_status = sa.Enum(
    "unverified", "verified", "disputed", name="verification_status"
)


def upgrade() -> None:
    bind = op.get_bind()
    evidence_stance.create(bind, checkfirst=True)
    verification_status.create(bind, checkfirst=True)

    op.add_column(
        "evidence",
        sa.Column("stance", evidence_stance, nullable=False, server_default="supports"),
    )
    op.add_column(
        "evidence",
        sa.Column(
            "verification_status", verification_status,
            nullable=False, server_default="unverified",
        ),
    )
    op.add_column("evidence", sa.Column("verified_by", sa.Uuid(), nullable=True))
    op.add_column(
        "evidence", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "ix_evidence_verification_status", "evidence", ["verification_status"]
    )


def downgrade() -> None:
    op.drop_index("ix_evidence_verification_status", table_name="evidence")
    op.drop_column("evidence", "verified_at")
    op.drop_column("evidence", "verified_by")
    op.drop_column("evidence", "verification_status")
    op.drop_column("evidence", "stance")
    verification_status.drop(op.get_bind(), checkfirst=True)
    evidence_stance.drop(op.get_bind(), checkfirst=True)
