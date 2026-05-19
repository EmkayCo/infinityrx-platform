"""Unit tests for OutboxDispatcher -- background publisher.

TDD: MUST FAIL before Task 4 implements the dispatcher.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.outbox.outbox_dispatcher import OutboxDispatcher  # FAILS until Task 4


def _shared_session(db_session):
    """Return a context-manager factory that yields db_session without closing it.

    R13 WARN-13 fix: OutboxDispatcher._poll_once enters the result of
    self._session_factory() as a context manager: with self._session_factory() as session:.
    Passing lambda: db_session directly would let Session.__exit__ close the
    SAVEPOINT-test-fixture session. contextlib.nullcontext yields the same session
    without calling close on exit.
    """
    return lambda: contextlib.nullcontext(db_session)


class TestOutboxDispatcherPollAndPublish:
    """Dispatcher polls pending rows, publishes, marks published."""

    @pytest.mark.asyncio
    async def test_publishes_pending_row_and_marks_published(self, db_session, mock_event_bus):
        """Pending row is published and marked status='published' with published_at set."""
        from src.models.tables import OutboxEvent
        from shared.events.types import EventEnvelope

        hold_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        envelope = EventEnvelope(
            event_type="payment.hold_released",
            tenant_id=tenant_id,
            correlation_id=uuid.uuid4(),
            source_module="reclaimrx",
            ordering_key=str(hold_id),
            idempotency_key=f"hold:release:{hold_id}",
            payload={"hold_id": str(hold_id), "amount": "99.50"},
        )
        row = OutboxEvent(
            id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            event_type="payment.hold_released",
            envelope_json=json.dumps(envelope.to_wire()),
            status="pending",
            created_at=datetime.now(UTC),
            published_at=None,
            attempt_count=0,
            last_error=None,
            idempotency_key=f"hold:release:{hold_id}",
        )
        db_session.add(row)
        db_session.commit()

        dispatcher = OutboxDispatcher(
            session_factory=_shared_session(db_session),
            bus=mock_event_bus,
            batch_size=10,
            poll_interval_seconds=0,
        )
        await dispatcher._poll_once()

        db_session.refresh(row)
        assert row.status == "published"
        assert row.published_at is not None
        assert mock_event_bus.publish.called

    @pytest.mark.asyncio
    async def test_publish_failure_increments_attempt_count(self, db_session):
        """When publish raises, row stays pending; attempt_count incremented; last_error set."""
        from src.models.tables import OutboxEvent
        from shared.events.types import EventEnvelope

        hold_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        envelope = EventEnvelope(
            event_type="payment.hold_released",
            tenant_id=tenant_id,
            correlation_id=uuid.uuid4(),
            source_module="reclaimrx",
            ordering_key=str(hold_id),
            idempotency_key=f"hold:release:{hold_id}",
            payload={"hold_id": str(hold_id)},
        )
        row = OutboxEvent(
            id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            event_type="payment.hold_released",
            envelope_json=json.dumps(envelope.to_wire()),
            status="pending",
            created_at=datetime.now(UTC),
            published_at=None,
            attempt_count=0,
            last_error=None,
            idempotency_key=f"hold:release:{hold_id}",
        )
        db_session.add(row)
        db_session.commit()

        failing_bus = MagicMock()
        failing_bus.publish = AsyncMock(side_effect=ConnectionError("broker down"))

        dispatcher = OutboxDispatcher(
            session_factory=_shared_session(db_session),
            bus=failing_bus,
            batch_size=10,
            poll_interval_seconds=0,
        )
        await dispatcher._poll_once()

        db_session.refresh(row)
        assert row.status == "pending"
        assert row.attempt_count == 1
        # PHI safety: last_error stores class label only, never exception message
        assert row.last_error is not None
        assert row.last_error.endswith(".ConnectionError")
        assert "broker down" not in row.last_error

    @pytest.mark.asyncio
    async def test_row_marked_failed_after_max_attempts(self, db_session):
        """Row with attempt_count >= 10 is marked status='failed' (not retried)."""
        from src.models.tables import OutboxEvent
        from shared.events.types import EventEnvelope

        hold_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        envelope = EventEnvelope(
            event_type="payment.hold_released",
            tenant_id=tenant_id,
            correlation_id=uuid.uuid4(),
            source_module="reclaimrx",
            ordering_key=str(hold_id),
            idempotency_key=f"hold:release:{hold_id}",
            payload={"hold_id": str(hold_id)},
        )
        row = OutboxEvent(
            id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            event_type="payment.hold_released",
            envelope_json=json.dumps(envelope.to_wire()),
            status="pending",
            created_at=datetime.now(UTC),
            published_at=None,
            attempt_count=10,
            last_error="previous error",
            idempotency_key=f"hold:release:{hold_id}",
        )
        db_session.add(row)
        db_session.commit()

        failing_bus = MagicMock()
        failing_bus.publish = AsyncMock(side_effect=ConnectionError("still down"))

        dispatcher = OutboxDispatcher(
            session_factory=_shared_session(db_session),
            bus=failing_bus,
            batch_size=10,
            poll_interval_seconds=0,
        )
        await dispatcher._poll_once()

        db_session.refresh(row)
        assert row.status == "failed"

    @pytest.mark.asyncio
    async def test_row_marked_failed_on_post_increment_threshold(self, db_session):
        """R10 WARN-6: attempt_count=9 that fails once -> status='failed' on same poll cycle.
        Proves terminal-failure check runs AFTER the increment in _dispatch_row except.
        """
        from src.models.tables import OutboxEvent
        from shared.events.types import EventEnvelope

        hold_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        envelope = EventEnvelope(
            event_type="payment.hold_released",
            tenant_id=tenant_id,
            correlation_id=uuid.uuid4(),
            source_module="reclaimrx",
            ordering_key=str(hold_id),
            idempotency_key=f"hold:release:{hold_id}",
            payload={"hold_id": str(hold_id)},
        )
        row = OutboxEvent(
            id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            event_type="payment.hold_released",
            envelope_json=json.dumps(envelope.to_wire()),
            status="pending",
            created_at=datetime.now(UTC),
            published_at=None,
            attempt_count=9,
            last_error=None,
            idempotency_key=f"hold:release:{hold_id}",
        )
        db_session.add(row)
        db_session.commit()

        failing_bus = MagicMock()
        failing_bus.publish = AsyncMock(side_effect=ConnectionError("broker down"))

        dispatcher = OutboxDispatcher(
            session_factory=_shared_session(db_session),
            bus=failing_bus,
            batch_size=10,
            poll_interval_seconds=0,
        )
        await dispatcher._poll_once()

        db_session.refresh(row)
        assert row.attempt_count == 10
        assert row.status == "failed"
        assert row.last_error is not None
        assert row.last_error.endswith(".ConnectionError")
        assert "broker down" not in row.last_error
