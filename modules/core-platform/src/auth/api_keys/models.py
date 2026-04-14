"""Local model for core.api_keys (SQLite-compatible shim).

INTEGRATION NOTE: replace with shared.db.models.core.ApiKey
when switching to the shared ORM layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.auth._models import GUID, Base


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class ApiKey(Base):
    """API key row for service-to-service and external client access."""

    __tablename__ = "api_keys"
    __table_args__ = (
        Index("idx_api_keys_tenant", "tenant_id"),
        Index("idx_api_keys_prefix", "key_prefix"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("tenants.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    key_type: Mapped[str] = mapped_column(String(50), nullable=False)  # service | client | webhook
    permissions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    allowed_ips: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id"), nullable=True
    )
