"""SQLAlchemy stand-in models for core.audit_log.

These mirror the DDL in docs/prd/prd-core-platform.md section 2.3. They
live here until Teammate 1 (Infrastructure & Database) publishes the real
models in ``shared.db.models.core``; integration will reconcile by having
``src.audit.models`` re-export the shared definitions.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR, JSON

from src._shim.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    tenant_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    before_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

def _as_uuid_str(value: uuid.UUID | str | None) -> str | None:
    if value is None:
        return None
    return str(value)
