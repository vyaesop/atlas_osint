"""security & governance: clearance/compartments, classification, legal hold,
audit hash chain

Revision ID: 0009_governance
Revises: 0008_casework
Create Date: 2026-06-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009_governance"
down_revision: Union[str, None] = "0008_casework"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The "classification" enum was created in 0008 (casework); reference it without
# re-creating. create_type=False stops Alembic emitting CREATE TYPE again.
classification = sa.Enum(
    "unclassified", "official", "confidential", "secret", "top_secret",
    name="classification", create_type=False,
)


def upgrade() -> None:
    # ABAC on users (#38).
    op.add_column("users", sa.Column("clearance", classification, nullable=False, server_default="unclassified"))
    op.add_column("users", sa.Column("compartments", sa.JSON(), nullable=False, server_default="[]"))

    # Classification + compartments + legal hold on entities (#37/#40).
    op.add_column("entities", sa.Column("classification", classification, nullable=False, server_default="unclassified"))
    op.add_column("entities", sa.Column("compartments", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("entities", sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_entities_classification", "entities", ["classification"])

    # Classification on evidence (#37).
    op.add_column("evidence", sa.Column("classification", classification, nullable=False, server_default="unclassified"))

    # Tamper-evident audit hash chain (#39).
    op.add_column("audit_log", sa.Column("prev_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_log", sa.Column("entry_hash", sa.String(length=64), nullable=True))
    op.create_index("ix_audit_log_entry_hash", "audit_log", ["entry_hash"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_entry_hash", table_name="audit_log")
    op.drop_column("audit_log", "entry_hash")
    op.drop_column("audit_log", "prev_hash")
    op.drop_column("evidence", "classification")
    op.drop_index("ix_entities_classification", table_name="entities")
    op.drop_column("entities", "legal_hold")
    op.drop_column("entities", "compartments")
    op.drop_column("entities", "classification")
    op.drop_column("users", "compartments")
    op.drop_column("users", "clearance")
