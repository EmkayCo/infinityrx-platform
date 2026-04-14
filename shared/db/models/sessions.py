"""ORM model for ``core.sessions``.

Tracks active user sessions for concurrent session management, idle
timeout enforcement, and force-logout. One row per issued JWT.

Security notes
--------------
* ``token_hash`` stores SHA-256(jti) — never the raw JWT.
* ``device_info`` is advisory metadata (user-agent, IP, fingerprint) used
  for the session list UI. Never trusted for access decisions.
* Tenant-scoped: every query MUST filter on ``tenant_id``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base
from shared.db.tenant_context import TenantScopedMixin

SCHEMA = "core"


class UserSession(Base, TenantScopedMixin):
    """Active (or recently expired) user session row.

    Inherits :class:`TenantScopedMixin` so the ORM event listener in
    ``shared.db.tenant_context`` auto-filters every query by the active
    tenant contextvar. Any code that calls ``db.get(UserSession, id)``
    without tenant context will raise ``MissingTenantContextError``
    rather than silently returning a cross-tenant row.
    """

    __tablename__ = "sessions"
    __table_args__ = (
        Index("idx_sessions_user_active", "user_id", "is_active"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.users.id"),
        nullable=False,
    )
    # Denormalized for tenant scoping — avoids a join on every validate()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
    )

    # SHA-256 of the JWT jti claim — NEVER the token itself
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Advisory: {user_agent, ip, fingerprint} — never used for access decisions
    device_info: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
