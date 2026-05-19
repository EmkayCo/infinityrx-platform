"""Transactional outbox service for ReclaimRx.

Callers invoke write() INSIDE the same DB transaction as the domain change
(hold release, graph run completion). The OutboxEvent row is committed
atomically with the domain row — no dual-write risk (R1 BLOCK 4).

The outbox_dispatcher (outbox_dispatcher.py) polls pending rows and publishes
them to the event bus. On per-row publish failure the row is reverted to
status='pending' (with attempt_count incremented) and retried on the NEXT poll
cycle. After _MAX_ATTEMPTS failures the row is moved to status='failed' and an
alert is logged. No per-row delay/backoff is implemented — retry cadence is
bounded by the dispatcher's fixed `poll_interval_seconds` (default 1.0s).
Per-row exponential backoff requires a `next_attempt_at` column on
`reclaimrx_outbox_events` and is deferred to a follow-on wave (R6 BLOCK-20).
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from shared.events.types import EventEnvelope
from src.models.tables import OutboxEvent


class OutboxService:
    """Write EventEnvelope rows to the transactional outbox.

    Usage (inside an open DB transaction)::

        svc = OutboxService(db)
        svc.write(
            event_type="payment.hold_released",
            tenant_id=tenant_uuid,
            idempotency_key=f"hold:release:{hold_id}",
            ordering_key=str(hold_id),
            payload={
                "hold_id": str(hold_id),
                "amount": str(amount),       # Decimal as str per financial-precision.md
                "released_by": str(user_id),
                "reason": reason,
            },
            source_module="reclaimrx",
        )
        db.commit()   # both domain row and outbox row commit atomically
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def write(
        self,
        *,
        event_type: str,
        tenant_id: uuid.UUID,
        idempotency_key: str,
        ordering_key: str,
        payload: dict[str, Any],
        source_module: str = "reclaimrx",
        schema_version: str = "1.0",
    ) -> OutboxEvent:
        """Insert a pending OutboxEvent row into the current session.

        The envelope is constructed with correct EventEnvelope field names
        (event_type, tenant_id, correlation_id, source_module, timestamp).
        The row is flushed but NOT committed -- the caller owns the transaction
        boundary.

        Raises:
            sqlalchemy.exc.IntegrityError: if idempotency_key already exists
                (UNIQUE constraint). Caller must handle this as a replay signal.
        """
        envelope = EventEnvelope(
            event_type=event_type,
            tenant_id=uuid.UUID(str(tenant_id)),
            correlation_id=uuid.uuid4(),
            source_module=source_module,
            schema_version=schema_version,
            ordering_key=ordering_key,
            idempotency_key=idempotency_key,
            payload=payload,
        )

        row = OutboxEvent(
            id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            event_type=event_type,
            envelope_json=json.dumps(envelope.to_wire()),
            status="pending",
            created_at=datetime.now(UTC),
            published_at=None,
            attempt_count=0,
            last_error=None,
            idempotency_key=idempotency_key,
        )
        self._session.add(row)
        self._session.flush()  # surfaces IntegrityError if duplicate
        return row
