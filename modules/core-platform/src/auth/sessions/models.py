"""Local session model for core.sessions (SQLite-compatible shim).

Mirrors shared.db.models.sessions.UserSession but uses the module-local
Base and GUID type so tests run on SQLite without Postgres.

INTEGRATION NOTE: replace with shared.db.models.sessions.UserSession
when switching to the shared ORM layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.auth._models import GUID, Base


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class Session_(Base):
    """Active user session row.

    Named ``Session_`` to avoid shadowing ``sqlalchemy.orm.Session``.
    """

    __tablename__ = "sessions"
    __table_args__ = (
        Index("idx_sessions_user_active", "user_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    device_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
