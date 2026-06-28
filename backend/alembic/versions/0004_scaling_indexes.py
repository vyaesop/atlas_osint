"""scaling indexes: trigram name search + JSONB GIN

Speeds up the two hot read patterns at scale:
  * ILIKE name search  → pg_trgm GIN index on entities.name
  * JSONB property/alias lookups → GIN indexes

PostgreSQL-only (the test suite runs on SQLite and never executes migrations).

Revision ID: 0004_scaling_indexes
Revises: 0003_documents_ai
Create Date: 2026-06-19
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004_scaling_indexes"
down_revision: Union[str, None] = "0003_documents_ai"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_entities_name_trgm "
        "ON entities USING gin (name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_entities_properties_gin "
        "ON entities USING gin (properties)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_entities_aliases_gin "
        "ON entities USING gin (aliases)"
    )
    # Audit-log queries are time-ordered; help the common "recent activity" read.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_log_created_at "
        "ON audit_log (created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_audit_log_created_at")
    op.execute("DROP INDEX IF EXISTS ix_entities_aliases_gin")
    op.execute("DROP INDEX IF EXISTS ix_entities_properties_gin")
    op.execute("DROP INDEX IF EXISTS ix_entities_name_trgm")
    # Leave the pg_trgm extension in place; other objects may rely on it.
