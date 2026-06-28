"""Sanctions / PEP / watchlist entries (#18).

A provider-agnostic store of watchlist records (e.g. OFAC SDN, UN, EU consolidated
lists, or a PEP list) that entities are screened against. Entries are loaded via
the API — from a downloaded official list or a manual upload — so screening works
fully offline once a list is present.
"""
from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType


class WatchlistEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "watchlist_entries"

    name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    aliases: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    program: Mapped[str | None] = mapped_column(String(255), nullable=True)   # e.g. "OFAC-SDN"
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)    # list provenance
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)  # person/company/...
