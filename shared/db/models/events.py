"""ORM models for event bus reliability tables.

New tables live in the ``core`` schema alongside the Core Platform baseline.
This file is separate from core.py (which is locked after Phase 1) so Phase 2
additions can land without touching the frozen baseline.

Tables
------
- ``core.event_dlq``       — dead-letter queue entries for failed messages.
- ``core.processed_events`` — idempotency tracking (composite PK prevents duplicates).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base

SCHEMA = "core"


class EventDLQEntry(Base):
    """Dead-letter queue entry for a message that exhausted its retry budget.

    Populated by the RabbitMQ bus after max_retries is reached.  The DLQ
    service exposes list/replay/drop operations on these records.
    """

    __tablename__ = "event_dlq"
    __table_args__ = (
        Index("ix_event_dlq_event_id", "event_id"),
        Index("ix_event_dlq_tenant_id", "tenant_id"),
        Index("ix_event_dlq_event_type", "event_type"),
        Index("ix_event_dlq_status", "status"),
        CheckConstraint(
            "status IN ('queued', 'replayed', 'dropped')",
            name="event_dlq_status_valid",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=lambda: __import__("uuid").uuid4(),
    )
    event_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(200), nullable=False)
    # Full EventEnvelope wire dict stored for replay
    envelope: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    failure_reason: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # Original topic so replay can route back to the right exchange/routing key
    dlq_topic: Mapped[str] = mapped_column(String(200), nullable=False)
    replayed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued"
    )


class ProcessedEvent(Base):
    """Idempotency tracking table for event consumers.

    Composite primary key of (idempotency_key, consumer_name) means each
    consumer tracks its own processing state independently.  Multiple
    consumers receiving the same event will each have their own row.

    Populated by PostgresIdempotencyStore.mark().
    """

    __tablename__ = "processed_events"
    __table_args__ = (
        {"schema": SCHEMA},
    )

    idempotency_key: Mapped[str] = mapped_column(
        Text, nullable=False, primary_key=True
    )
    consumer_name: Mapped[str] = mapped_column(
        Text, nullable=False, primary_key=True, default=""
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
