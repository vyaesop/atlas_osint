"""documents table + AI-provenance flags

Revision ID: 0003_documents_ai
Revises: 0002_evidence_stance
Create Date: 2026-06-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_documents_ai"
down_revision: Union[str, None] = "0002_evidence_stance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

document_status = sa.Enum("pending", "processed", "failed", name="document_status")


def upgrade() -> None:
    for table in ("entities", "relationships", "evidence"):
        op.add_column(
            table,
            sa.Column("is_ai_generated", sa.Boolean(), nullable=False,
                      server_default=sa.false()),
        )

    document_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("filename", sa.String(512), nullable=True),
        sa.Column("content_type", sa.String(128), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", document_status, nullable=False, server_default="pending"),
        sa.Column("extraction", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("entity_id", sa.Uuid(),
                  sa.ForeignKey("entities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_entity_id", "documents", ["entity_id"])


def downgrade() -> None:
    op.drop_table("documents")
    document_status.drop(op.get_bind(), checkfirst=True)
    for table in ("evidence", "relationships", "entities"):
        op.drop_column(table, "is_ai_generated")
