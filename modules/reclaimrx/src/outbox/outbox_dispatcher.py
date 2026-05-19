"""Outbox dispatcher -- background asyncio worker.

Polls pending OutboxEvent rows, publishes to the event bus, marks rows
published. On failure, increments attempt_count and sets last_error.
After MAX_ATTEMPTS failures, marks the row failed and logs an alert.

Spec 7.2: dispatcher polls every 1s, retries failed rows on the NEXT
poll cycle, 10 attempts max then status=failed + alert (audit 8, D14).
R6 BLOCK-20: per-row exponential backoff requires a next_attempt_at column
and is deferred to a follow-on wave.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any, Callable

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from shared.events.bus import EventBus
from shared.events.types import EventEnvelope
from src.models.tables import OutboxEvent

logger = logging.getLogger("reclaimrx.outbox_dispatcher")

_MAX_ATTEMPTS: int = 10
_DEFAULT_POLL_SECONDS: float = 1.0
_DEFAULT_BATCH_SIZE: int = 50


class OutboxDispatcher:
    """Long-running asyncio dispatcher for the transactional outbox.

    R6 BLOCK-14: system-wide -- drains reclaimrx_outbox_events for ALL tenants.
    Does NOT install tenant loader on its session -- intentionally cross-tenant.

    R6 BLOCK-13 orphan recovery: on start(), reclaims rows left in
    status='publishing' by a crashed previous run. SOLO DEPLOYMENT MODEL.

    Usage (in FastAPI lifespan)::

        dispatcher = OutboxDispatcher(
            session_factory=get_sessionmaker(),
            bus=event_bus,
        )
        task = asyncio.create_task(dispatcher.start())
    """

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any],
        bus: EventBus,
        batch_size: int = _DEFAULT_BATCH_SIZE,
        poll_interval_seconds: float = _DEFAULT_POLL_SECONDS,
    ) -> None:
        self._session_factory = session_factory
        self._bus = bus
        self._batch_size = batch_size
        self._poll_interval = poll_interval_seconds
        self._running = False

    async def start(self) -> None:
        """Blocking coroutine -- run until cancelled.

        R6 BLOCK-13: reclaim orphans BEFORE entering the poll loop.
        """
        self._reclaim_orphans()
        self._running = True
        logger.info(
            "reclaimrx.outbox_dispatcher.started",
            extra={
                "svc_batch_size": self._batch_size,
                "svc_poll_interval": self._poll_interval,
            },
        )
        while self._running:
            try:
                await self._poll_once()
            except Exception:  # noqa: BLE001
                logger.exception("reclaimrx.outbox_dispatcher.poll_error")
            # R8 BLOCK-25: ALWAYS yield to the event loop between polls.
            # asyncio.sleep(0) yields once per iteration without busy-looping.
            await asyncio.sleep(self._poll_interval)

    def _reclaim_orphans(self) -> None:
        """Revert rows stuck in 'publishing' from a prior crashed run.

        R6 BLOCK-13. Increments attempt_count to bound retry depth.
        """
        with self._session_factory() as session:
            result = session.execute(
                text(
                    "UPDATE reclaimrx_outbox_events "
                    "SET status = 'pending', attempt_count = attempt_count + 1 "
                    "WHERE status = 'publishing'"
                )
            )
            count = result.rowcount or 0
            session.commit()
            if count > 0:
                logger.warning(
                    "reclaimrx.outbox_dispatcher.orphans_reclaimed",
                    extra={"svc_orphan_count": count},
                )

    async def stop(self) -> None:
        """Signal the dispatcher to stop after the current poll completes."""
        self._running = False

    async def _poll_once(self) -> None:
        """Single poll: claim pending batch, publish, update status.

        R1 BLOCK 3: claim via UPDATE-RETURNING / SKIP LOCKED (Postgres)
        or SELECT-then-flip (SQLite).
        R6 BLOCK-16: session owned by THIS poll cycle.
        """
        with self._session_factory() as session:
            dialect = session.bind.dialect.name if session.bind else ""
            if dialect == "postgresql":
                rows = self._claim_postgres(session)
            else:
                rows = self._claim_generic(session)
            for row in rows:
                await self._dispatch_row(session, row)

    def _claim_postgres(self, session: Session) -> list[OutboxEvent]:
        """Atomically claim next batch pending -> publishing using SKIP LOCKED."""
        ids_result = session.execute(
            text(
                "WITH claimed AS ("
                "    SELECT id FROM reclaimrx_outbox_events"
                "    WHERE status = 'pending'"
                "    ORDER BY created_at"
                "    LIMIT :batch_size"
                "    FOR UPDATE SKIP LOCKED"
                ")"
                " UPDATE reclaimrx_outbox_events o"
                " SET status = 'publishing'"
                " FROM claimed"
                " WHERE o.id = claimed.id"
                " RETURNING o.id"
            ),
            {"batch_size": self._batch_size},
        )
        claimed_ids = [row[0] for row in ids_result]
        session.commit()
        if not claimed_ids:
            return []
        rows = (
            session.execute(
                select(OutboxEvent).where(OutboxEvent.id.in_(claimed_ids))
            )
            .scalars()
            .all()
        )
        return list(rows)

    def _claim_generic(self, session: Session) -> list[OutboxEvent]:
        """Fallback claim for non-Postgres backends (SQLite test fixture)."""
        rows = (
            session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.status == "pending")
                .order_by(OutboxEvent.created_at)
                .limit(self._batch_size)
            )
            .scalars()
            .all()
        )
        for row in rows:
            row.status = "publishing"
        session.commit()
        return list(rows)

    async def _dispatch_row(self, session: Session, row: OutboxEvent) -> None:
        """Attempt to publish one outbox row.

        Pre-condition: row.status == 'publishing'.
        On success -> 'published'.
        On retryable failure -> 'pending' (attempt_count++).
        On terminal failure (attempt_count >= _MAX_ATTEMPTS) -> 'failed'.
        """
        if row.attempt_count >= _MAX_ATTEMPTS:
            row.status = "failed"
            logger.error(
                "reclaimrx.outbox_dispatcher.row_failed_max_attempts",
                extra={
                    "svc_outbox_id": row.id,
                    "svc_event_type": row.event_type,
                    "svc_idempotency_key": row.idempotency_key,
                    "svc_attempt_count": row.attempt_count,
                },
            )
            session.commit()
            return

        try:
            envelope = EventEnvelope.from_wire(json.loads(row.envelope_json))
            await self._bus.publish(envelope)
            row.status = "published"
            row.published_at = datetime.now(UTC)
            session.commit()
        except Exception as exc:  # noqa: BLE001
            # R4 NEW-2: never serialize exception args -- they can carry PHI.
            # last_error stores exception class label only.
            # R11 BLOCK-31: do NOT use logger.exception (exc_info=True renders
            # str(exc) which may contain PHI). Use logger.error (exc_info=False).
            error_label = f"{exc.__class__.__module__}.{exc.__class__.__name__}"
            row.attempt_count += 1
            row.last_error = error_label
            # R10 WARN-6: check terminal-failure AFTER the increment.
            if row.attempt_count >= _MAX_ATTEMPTS:
                row.status = "failed"
                session.commit()
                logger.error(
                    "reclaimrx.outbox_dispatcher.row_failed_max_attempts",
                    extra={
                        "svc_outbox_id": row.id,
                        "svc_event_type": row.event_type,
                        "svc_idempotency_key": row.idempotency_key,
                        "svc_attempt_count": row.attempt_count,
                        "svc_error_class": error_label,
                    },
                )
                return
            row.status = "pending"
            session.commit()
            logger.error(
                "reclaimrx.outbox_dispatcher.publish_failed",
                extra={
                    "svc_outbox_id": row.id,
                    "svc_event_type": row.event_type,
                    "svc_attempt_count": row.attempt_count,
                    "svc_error_class": error_label,
                },
            )
