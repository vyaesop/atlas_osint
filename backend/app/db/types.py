"""Cross-dialect column types.

Production runs on PostgreSQL (native UUID + JSONB for indexing); the test
suite runs on SQLite. These aliases render to the right type per dialect so the
same models work in both.
"""
from __future__ import annotations

from sqlalchemy import JSON, Uuid
from sqlalchemy.dialects.postgresql import JSONB

# Native ``uuid`` on Postgres, CHAR(32) on SQLite — both round-trip uuid.UUID.
GUID = Uuid(as_uuid=True)

# JSONB on Postgres (indexable), plain JSON elsewhere.
JSONType = JSON().with_variant(JSONB(), "postgresql")
