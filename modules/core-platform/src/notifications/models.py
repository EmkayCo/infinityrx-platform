"""SQLAlchemy stand-in models for core.notifications + core.notification_preferences.

Mirrors DDL in docs/prd/prd-core-platform.md section 2.4. These live here
until Teammate 1 publishes the real models in ``shared.db.models.core``;
integration will reconcile by re-exporting the shared definitions.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR

from src._shim.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _uuidstr() -> str:
    return str(uuid.uuid4())


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=_uuidstr)
    tenant_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    notification_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(Text, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("user_id", "notification_type", name="uq_pref_user_type"),)

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=_uuidstr)
    user_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    notification_type: Mapped[str] = mapped_column(String(100), nullable=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
