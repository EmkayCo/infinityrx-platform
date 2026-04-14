"""Transactional outbox pattern for crash-safe event publishing.

Problem: If the application crashes between DB.commit() and bus.publish(),
financial events (payment_batch.submitted, claim.ingested) are permanently lost.

Solution: Write events to an outbox table IN the same transaction as the
business data. A separate relay process polls unpublished outbox entries
and publishes them to RabbitMQ with publisher confirms, then marks them
as published.

Usage
-----
Enqueue an event in the SAME session/transaction as your business write::

    async with session.begin():
        # business write
        session.add(claim_record)
        # event write (same transaction)
        await enqueue_event(session, envelope)
    # Both committed atomically. Relay publishes to bus.

The relay runs as a background task and is started in lifespan::

    relay = OutboxRelay(engine=get_engine(), bus=get_event_bus())
    asyncio.create_task(relay.run())

This module is CRITICAL for financial correctness — 100% test coverage required.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Integer,
    String,
    Text,
    and_,
    select,
    update,
)
from sqlalchemy import UUID as SA_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from shared.events.types import EventEnvelope

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from shared.events.bus import EventBus

logger = logging.getLogger("shared.events.outbox")

# Maximum number of attempts before an entry is considered poisoned.
MAX_RELAY_ATTEMPTS = 5
# Polling interval for the relay in seconds.
RELAY_POLL_INTERVAL_SECONDS = 5


class _OutboxBase(DeclarativeBase):
    """Declarative base for outbox-only models."""


class OutboxEntry(_OutboxBase):
    """Persistent outbox entry — one row per event pending publication.

    Written in the same DB transaction as the business data it represents.
    The relay reads unpublished rows and publishes them to the event bus.
    """

    __tablename__ = "outbox_entries"
    __table_args__ = {"schema": "shared_events"}

    id: Mapped[uuid.UUID] = mapped_column(
        SA_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(SA_UUID(as_uuid=True), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(255), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    ordering_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
    source_module: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


async def ensure_outbox_schema(engine: "AsyncEngine") -> None:
    """Create the shared_events schema and outbox_entries table if they do not exist.

    Idempotent DDL — safe to call at every application startup.
    """
    from sqlalchemy import text as _text

    async with engine.begin() as conn:
        await conn.execute(_text("CREATE SCHEMA IF NOT EXISTS shared_events"))
    async with engine.begin() as conn:
        await conn.run_sync(_OutboxBase.metadata.create_all)


async def enqueue_event(session: AsyncSession, envelope: EventEnvelope) -> OutboxEntry:
    """Write an event to the outbox IN the current session transaction.

    Must be called INSIDE an active transaction context::

        async with session.begin():
            session.add(business_object)
            entry = await enqueue_event(session, envelope)
        # Both written atomically.

    The relay will pick up unpublished entries and publish them to the bus.

    Args:
        session: An active AsyncSession within an open transaction.
        envelope: The EventEnvelope to eventually publish.

    Returns:
        The persisted OutboxEntry (not yet published).
    """
    wire = envelope.to_wire()
    entry = OutboxEntry(
        id=envelope.event_id,
        tenant_id=envelope.tenant_id,
        event_type=envelope.event_type,
        topic=envelope.event_type,  # topic == event_type by convention
        payload_json=json.dumps(wire),
        idempotency_key=envelope.idempotency_key,
        ordering_key=envelope.ordering_key,
        schema_version=envelope.schema_version,
        source_module=envelope.source_module,
    )
    session.add(entry)
    return entry


class OutboxRelay:
    """Background task that polls the outbox and publishes to the event bus.

    Publishes entries in order of creation (FIFO within tenant).
    Marks published_at on success. Increments attempts on failure.
    Entries exceeding MAX_RELAY_ATTEMPTS are left for manual intervention.

    Usage::

        relay = OutboxRelay(engine=get_engine(), bus=get_event_bus())
        # In lifespan:
        task = asyncio.create_task(relay.run())
        try:
            yield
        finally:
            relay.stop()
            await task
    """

    def __init__(
        self,
        engine: "AsyncEngine",
        bus: "EventBus",
        *,
        poll_interval: float = RELAY_POLL_INTERVAL_SECONDS,
        batch_size: int = 50,
    ) -> None:
        self._engine = engine
        self._bus = bus
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._running = False

    def stop(self) -> None:
        """Signal the relay to stop after the current poll cycle."""
        self._running = False

    async def run(self) -> None:
        """Poll loop — runs until stop() is called."""
        self._running = True
        logger.info("outbox_relay.started")
        while self._running:
            try:
                published = await self._relay_batch()
                if published > 0:
                    logger.info(
                        "outbox_relay.batch_published",
                        extra={"svc_count": published},
                    )
            except Exception as exc:
                logger.error(
                    "outbox_relay.poll_error",
                    extra={"svc_error": str(exc)},
                    exc_info=True,
                )
            await asyncio.sleep(self._poll_interval)
        logger.info("outbox_relay.stopped")

    async def _relay_batch(self) -> int:
        """Fetch and publish one batch of unpublished entries. Returns count published."""
        from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession
        from sqlalchemy.orm import sessionmaker

        async_session = sessionmaker(
            self._engine, class_=_AsyncSession, expire_on_commit=False
        )
        published = 0
        async with async_session() as session:
            async with session.begin():
                stmt = (
                    select(OutboxEntry)
                    .where(
                        and_(
                            OutboxEntry.published_at.is_(None),
                            OutboxEntry.attempts < MAX_RELAY_ATTEMPTS,
                        )
                    )
                    .order_by(OutboxEntry.created_at)
                    .limit(self._batch_size)
                    .with_for_update(skip_locked=True)
                )
                result = await session.execute(stmt)
                entries = result.scalars().all()

            for entry in entries:
                async with session.begin():
                    try:
                        wire = json.loads(entry.payload_json)
                        envelope = EventEnvelope.from_wire(wire)
                        await self._bus.publish(envelope)
                        await session.execute(
                            update(OutboxEntry)
                            .where(OutboxEntry.id == entry.id)
                            .values(published_at=datetime.now(UTC))
                        )
                        published += 1
                    except Exception as exc:
                        logger.error(
                            "outbox_relay.publish_failed",
                            extra={
                                "svc_entry_id": str(entry.id),
                                "svc_event_type": entry.event_type,
                                "svc_error": str(exc),
                            },
                        )
                        await session.execute(
                            update(OutboxEntry)
                            .where(OutboxEntry.id == entry.id)
                            .values(attempts=entry.attempts + 1)
                        )
        return published
