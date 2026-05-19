"""Tests for DB-backed DLQRepository.

TDD: MUST FAIL before Task 6 implements the repository.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from src.events.dlq_repository import ReclaimRxDLQRepository  # FAILS until Task 6


class TestReclaimRxDLQRepository:
    """Real DB-backed DLQ repository satisfies DLQRepository Protocol."""

    @pytest.mark.asyncio
    async def test_save_and_get(self, async_db_engine):
        """save() persists an entry; get() retrieves it by id."""
        from shared.db.models.events import EventDLQEntry

        repo = ReclaimRxDLQRepository(async_db_engine)
        entry_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        entry = EventDLQEntry(
            id=entry_id,
            event_id=uuid.uuid4(),
            tenant_id=tenant_id,
            event_type="payment.hold_released",
            envelope={"event_type": "payment.hold_released", "tenant_id": str(tenant_id)},
            failure_reason="broker timeout",
            attempt_count=1,
            dlq_topic="reclaimrx.dlq",
            status="queued",
            first_failed_at=datetime.now(UTC),
            last_failed_at=datetime.now(UTC),
        )
        await repo.save(entry)

        fetched = await repo.get(entry_id, tenant_id=tenant_id)
        assert fetched is not None
        assert fetched.event_type == "payment.hold_released"
        assert fetched.failure_reason == "broker timeout"

    @pytest.mark.asyncio
    async def test_list_filters_by_status(self, async_db_engine):
        """list(status='queued') returns only queued entries for the tenant."""
        from shared.db.models.events import EventDLQEntry

        repo = ReclaimRxDLQRepository(async_db_engine)
        tenant_id = uuid.uuid4()

        for status in ("queued", "replayed", "dropped"):
            await repo.save(EventDLQEntry(
                id=uuid.uuid4(),
                event_id=uuid.uuid4(),
                tenant_id=tenant_id,
                event_type="payment.hold_released",
                envelope={},
                failure_reason="test",
                attempt_count=1,
                dlq_topic="reclaimrx.dlq",
                status=status,
                first_failed_at=datetime.now(UTC),
                last_failed_at=datetime.now(UTC),
            ))

        queued = await repo.list(tenant_id=tenant_id, status="queued", limit=10)
        assert len(queued) == 1
        assert queued[0].status == "queued"
