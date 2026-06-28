"""tradecraft: source grading, ACH, annotations

Adds (Cluster 2 — Tradecraft & Analytic Rigor):
  * #3 Admiralty source grading columns on ``evidence``
  * #1 ACH tables (analyses, hypotheses, items, ratings)
  * #4/#6 ``annotations`` table (key assumptions / dissent / devil's advocate)

Revision ID: 0005_tradecraft
Revises: 0004_scaling_indexes
Create Date: 2026-06-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_tradecraft"
down_revision: Union[str, None] = "0004_scaling_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


source_reliability = sa.Enum("A", "B", "C", "D", "E", "F", name="source_reliability")
info_credibility = sa.Enum("1", "2", "3", "4", "5", "6", name="info_credibility")
ach_consistency = sa.Enum(
    "consistent", "inconsistent", "neutral", "na", name="ach_consistency"
)
annotation_kind = sa.Enum(
    "note", "assumption", "dissent", "devils_advocate", name="annotation_kind"
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (source_reliability, info_credibility, ach_consistency, annotation_kind):
        enum.create(bind, checkfirst=True)

    # ---- #3 source grading on evidence ----
    op.add_column("evidence", sa.Column("source_reliability", source_reliability, nullable=True))
    op.add_column("evidence", sa.Column("info_credibility", info_credibility, nullable=True))

    # ---- #1 ACH ----
    op.create_table(
        "ach_analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "ach_hypotheses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["ach_analyses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ach_hypotheses_analysis_id", "ach_hypotheses", ["analysis_id"])
    op.create_table(
        "ach_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["ach_analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ach_items_analysis_id", "ach_items", ["analysis_id"])
    op.create_table(
        "ach_ratings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("hypothesis_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("consistency", ach_consistency, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["ach_analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hypothesis_id"], ["ach_hypotheses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["ach_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hypothesis_id", "item_id", name="uq_ach_rating_cell"),
    )
    op.create_index("ix_ach_ratings_analysis_id", "ach_ratings", ["analysis_id"])

    # ---- #4/#6 annotations ----
    op.create_table(
        "annotations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", annotation_kind, nullable=False, server_default="note"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("relationship_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["relationship_id"], ["relationships.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "(CASE WHEN entity_id IS NULL THEN 0 ELSE 1 END) "
            "+ (CASE WHEN relationship_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="ck_annotation_exactly_one_target",
        ),
    )
    op.create_index("ix_annotations_kind", "annotations", ["kind"])
    op.create_index("ix_annotations_entity_id", "annotations", ["entity_id"])
    op.create_index("ix_annotations_relationship_id", "annotations", ["relationship_id"])


def downgrade() -> None:
    op.drop_table("annotations")
    op.drop_index("ix_ach_ratings_analysis_id", table_name="ach_ratings")
    op.drop_table("ach_ratings")
    op.drop_index("ix_ach_items_analysis_id", table_name="ach_items")
    op.drop_table("ach_items")
    op.drop_index("ix_ach_hypotheses_analysis_id", table_name="ach_hypotheses")
    op.drop_table("ach_hypotheses")
    op.drop_table("ach_analyses")
    op.drop_column("evidence", "info_credibility")
    op.drop_column("evidence", "source_reliability")

    bind = op.get_bind()
    for enum in (annotation_kind, ach_consistency, info_credibility, source_reliability):
        enum.drop(bind, checkfirst=True)
