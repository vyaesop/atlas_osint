"""sanctions/watchlist entries (#18)

Revision ID: 0007_watchlist
Revises: 0006_entity_merges
Create Date: 2026-06-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_watchlist"
down_revision: Union[str, None] = "0006_entity_merges"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "watchlist_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("program", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=128), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_watchlist_entries_name", "watchlist_entries", ["name"])


def downgrade() -> None:
    op.drop_index("ix_watchlist_entries_name", table_name="watchlist_entries")
    op.drop_table("watchlist_entries")
