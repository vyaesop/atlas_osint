"""entity resolution: reversible merge records (#13)

Revision ID: 0006_entity_merges
Revises: 0005_tradecraft
Create Date: 2026-06-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_entity_merges"
down_revision: Union[str, None] = "0005_tradecraft"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "entity_merges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kept_id", sa.Uuid(), nullable=False),
        sa.Column("merged_id", sa.Uuid(), nullable=False),
        sa.Column("merged_name", sa.String(length=512), nullable=False),
        sa.Column("merged_snapshot", sa.JSON(), nullable=False),
        sa.Column("moved_relationships", sa.JSON(), nullable=False),
        sa.Column("moved_evidence_ids", sa.JSON(), nullable=False),
        sa.Column("moved_annotation_ids", sa.JSON(), nullable=False),
        sa.Column("added_aliases", sa.JSON(), nullable=False),
        sa.Column("added_property_keys", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("undone", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entity_merges_kept_id", "entity_merges", ["kept_id"])


def downgrade() -> None:
    op.drop_index("ix_entity_merges_kept_id", table_name="entity_merges")
    op.drop_table("entity_merges")
