"""initial schema: users, entities, relationships, evidence, audit_log

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


entity_type = sa.Enum(
    "person", "organization", "company", "government_agency",
    "event", "location", "document", "asset",
    name="entity_type",
)
relationship_type = sa.Enum(
    "WORKS_FOR", "OWNS", "FOUNDED", "MEMBER_OF", "INVESTED_IN", "PARTNER_OF",
    "ATTENDED", "PARTICIPATED_IN", "LOCATED_IN", "REPORTED_BY",
    "ASSOCIATED_WITH", "MANAGES", "SUPERVISES", "FUNDED_BY", "CONNECTED_TO",
    name="relationship_type",
)
user_role = sa.Enum("admin", "researcher", "viewer", name="user_role")
audit_action = sa.Enum("create", "update", "delete", name="audit_action")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", entity_type, nullable=False),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("aliases", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("properties", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_entities_type", "entities", ["type"])
    op.create_index("ix_entities_name", "entities", ["name"])
    op.create_index("ix_entities_type_name", "entities", ["type", "name"])

    op.create_table(
        "relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", relationship_type, nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("properties", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_relationships_type", "relationships", ["type"])
    op.create_index("ix_relationships_source_id", "relationships", ["source_id"])
    op.create_index("ix_relationships_target_id", "relationships", ["target_id"])
    op.create_index("ix_relationships_source_target", "relationships", ["source_id", "target_id"])

    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("source", sa.String(512), nullable=True),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("reliability_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=True),
        sa.Column("relationship_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("relationships.id", ondelete="CASCADE"), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "(CASE WHEN entity_id IS NULL THEN 0 ELSE 1 END) "
            "+ (CASE WHEN relationship_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="ck_evidence_exactly_one_target",
        ),
    )
    op.create_index("ix_evidence_entity_id", "evidence", ["entity_id"])
    op.create_index("ix_evidence_relationship_id", "evidence", ["relationship_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", audit_action, nullable=False),
        sa.Column("target_table", sa.String(64), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("changes", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"])
    op.create_index("ix_audit_log_target_table", "audit_log", ["target_table"])
    op.create_index("ix_audit_log_target_id", "audit_log", ["target_id"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("evidence")
    op.drop_table("relationships")
    op.drop_table("entities")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    for enum in (audit_action, relationship_type, entity_type, user_role):
        enum.drop(op.get_bind(), checkfirst=True)
