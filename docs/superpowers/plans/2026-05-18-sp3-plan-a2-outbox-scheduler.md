# SP-3 Plan A2 — Outbox, Dispatcher, Scheduler, DLQ Real Repo, Redis Idempotency, Cleanup Jobs

> **Executor discipline:** Read every referenced file path before writing a single line of code. Use `superpowers:subagent-driven-development` or `superpowers:executing-plans`. Tasks follow TDD order: write failing test → implement → pass → commit.

**Status:** READY — spawned from orchestrator after codex R1 NO-GO on Plan A1
**Date:** 2026-05-18
**Vertical:** SP-3 ReclaimRx Backend Closure
**Spec ref:** `docs/superpowers/specs/2026-05-18-sp3-reclaimrx-portal-design.md` §7 (idempotency), §8 (events), D14 (app factory bindings)
**Audit ground truth:** `waves/B10/SP-3-audit-deep.md` §2, §6, §7, §8, §9
**Codex R1 blocks resolved here:** BLOCK 4 (EventEnvelope field names), BLOCK 7 (deterministic hash), BLOCK 8 (TDD)
**Depends on:** Plan A1 must have created `OutboxEvent` table (ORM class `OutboxEvent` in `modules/reclaimrx/src/models/tables.py`; alembic migration 0008 applied).

**Scope (this plan only):**

1. Outbox service — `modules/reclaimrx/src/outbox/event_outbox.py`
2. Outbox dispatcher — `modules/reclaimrx/src/outbox/outbox_dispatcher.py`
3. ReclaimRx-module scheduler — `modules/reclaimrx/src/jobs/reclaimrx_scheduler.py`
4. DLQ real DB-backed repository — `modules/reclaimrx/src/events/dlq_repository.py`
5. Redis idempotency wiring — `modules/reclaimrx/src/events/__init__.py`
6. `processed_events` cleanup job — scheduled via new scheduler
7. Daily audit hash-chain verification job — `modules/reclaimrx/src/jobs/audit_chain_job.py`
8. DLQ depth monitor — `modules/reclaimrx/src/jobs/dlq_monitor.py`
9. `create_app()` bindings — `modules/reclaimrx/src/main.py` (the D14 6-binding integration test)

**Not in this plan:** New models (Plan A1), new API endpoints (Plan A1/A3), frontend (Plans B–E), accumulator consumer (Plan A3), graph job (Plan A3).

---

## Pre-flight verification (executor MUST run before Task 1)

```bash
# 1. Verify OutboxEvent table created by Plan A1
python -c "from src.models.tables import OutboxEvent; print('OK')"

# 2. Verify shared primitives reachable
python -c "from shared.events.types import EventEnvelope; print('EventEnvelope OK')"
python -c "from shared.events.idempotency import PostgresIdempotencyStore, idempotent_handler; print('idempotency OK')"
python -c "from shared.events.dlq import DLQRepository, DLQService, build_dlq_router; print('DLQ OK')"
python -c "from shared.events.jobs.cleanup_processed_events import run_cleanup; print('cleanup OK')"
python -c "from croniter import croniter; print('croniter OK')"

# 3. Confirm main.py current state (3/6 D14 bindings mounted)
grep -n "EmptyDLQRepository\|processed_events\|audit.*chain\|dlq_monitor" \
    modules/reclaimrx/src/main.py
# Expected: _EmptyDLQRepository on 1 line; nothing for processed_events/audit/dlq_monitor
```

Fail fast and surface a sub-session ledger entry if anything above is wrong.

---

## Exact EventEnvelope construction (binding for all tasks)

From `shared/events/types.py` (verified in audit §2):

```python
from shared.events.types import EventEnvelope
import uuid
from decimal import Decimal

# CORRECT — field names are event_type, tenant_id, correlation_id, source_module, timestamp (auto)
envelope = EventEnvelope(
    event_type="payment.hold_released",        # NOT "type"
    tenant_id=uuid.UUID(str(hold.tenant_id)),  # uuid.UUID — NOT str
    correlation_id=uuid.uuid4(),
    source_module="reclaimrx",
    schema_version="1.0",
    ordering_key=str(hold_id),
    idempotency_key=f"hold:release:{hold_id}",
    payload={
        "hold_id": str(hold_id),
        "amount": str(decimal_amount),          # Decimal as str
        "released_by": jwt_sub,
        "reason": reason,
        "investigation_id": str(investigation_id),
        "released_at": datetime.now(UTC).isoformat(),
    },
)
# timestamp auto-set by model_post_init — do NOT pass emitted_at
```

**NEVER write:** `EventEnvelope(type=..., emitted_at=...)` — these fields do not exist.

---

## Deterministic advisory lock hash (binding for graph job in Plan A3)

From audit §9 + codex BLOCK 7:

```python
import zlib
lock_key = zlib.crc32(f"graph_run:{tenant_id}".encode()) & 0x7FFFFFFF
# Produces stable 31-bit positive int; always same result regardless of PYTHONHASHSEED
# NEVER use Python built-in hash() — it is process-randomized
```

Plan A3 graph job MUST use this pattern. Plan A2 includes it in scheduler-level advisory lock tests.

---

## Task 1 — Outbox service unit + integration tests (TDD: write failing tests first)

**Files:** `modules/reclaimrx/tests/unit/test_outbox_service.py` (NEW)

**Step 1 — Write tests, confirm they fail (no implementation yet):**

```python
# modules/reclaimrx/tests/unit/test_outbox_service.py
"""Unit tests for OutboxService — transactional outbox writer.

TDD: these tests MUST FAIL before Task 2 implements the service.
Run: pytest modules/reclaimrx/tests/unit/test_outbox_service.py -v
Expected: ImportError or AttributeError (OutboxService does not exist yet).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from unittest.mock import MagicMock, patch

from src.outbox.event_outbox import OutboxService  # FAILS until Task 2


class TestOutboxServiceWrite:
    """OutboxService.write() must persist an OutboxEvent row atomically."""

    def test_write_inserts_pending_row(self, db_session):
        """write() inserts a row with status='pending' and correct fields."""
        from src.models.tables import OutboxEvent

        svc = OutboxService(db_session)
        hold_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        svc.write(
            event_type="payment.hold_released",
            tenant_id=tenant_id,
            idempotency_key=f"hold:release:{hold_id}",
            ordering_key=str(hold_id),
            payload={
                "hold_id": str(hold_id),
                "amount": "123.45",
                "released_by": "user-sub-123",
                "reason": "duplicate billing",
                "investigation_id": str(uuid.uuid4()),
                "released_at": datetime.now(UTC).isoformat(),
            },
            source_module="reclaimrx",
        )

        row = db_session.query(OutboxEvent).filter_by(
            idempotency_key=f"hold:release:{hold_id}"
        ).one()
        assert row.status == "pending"
        assert row.event_type == "payment.hold_released"
        assert row.attempt_count == 0
        assert row.published_at is None
        assert row.last_error is None
        assert row.tenant_id == str(tenant_id)

    def test_write_stores_valid_event_envelope_json(self, db_session):
        """envelope_json stored by write() must deserialize to valid EventEnvelope."""
        import json
        from shared.events.types import EventEnvelope
        from src.models.tables import OutboxEvent

        svc = OutboxService(db_session)
        hold_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        svc.write(
            event_type="fwa.graph_run_completed",
            tenant_id=tenant_id,
            idempotency_key=f"graph_run:{hold_id}:completed",
            ordering_key=str(hold_id),
            payload={"graph_run_id": str(hold_id), "status": "completed",
                     "rings_detected": 3, "investigations_opened": 1,
                     "records_scanned": 5000, "lookback_window_days": 90,
                     "started_at": datetime.now(UTC).isoformat(),
                     "completed_at": datetime.now(UTC).isoformat(),
                     "failed_at": None, "error_code": None, "error_message": None},
            source_module="reclaimrx",
        )

        row = db_session.query(OutboxEvent).filter_by(
            idempotency_key=f"graph_run:{hold_id}:completed"
        ).one()
        envelope = EventEnvelope.from_wire(json.loads(row.envelope_json))
        assert envelope.event_type == "fwa.graph_run_completed"
        assert envelope.tenant_id == tenant_id
        assert envelope.source_module == "reclaimrx"
        assert "graph_run_id" in envelope.payload

    def test_write_idempotency_key_unique_constraint_raises(self, db_session):
        """Duplicate idempotency_key raises IntegrityError (UNIQUE constraint)."""
        import pytest
        from sqlalchemy.exc import IntegrityError

        svc = OutboxService(db_session)
        tenant_id = uuid.uuid4()
        hold_id = uuid.uuid4()
        key = f"hold:release:{hold_id}"

        svc.write(
            event_type="payment.hold_released",
            tenant_id=tenant_id,
            idempotency_key=key,
            ordering_key=str(hold_id),
            payload={"hold_id": str(hold_id)},
            source_module="reclaimrx",
        )
        db_session.flush()

        with pytest.raises(IntegrityError):
            svc.write(
                event_type="payment.hold_released",
                tenant_id=tenant_id,
                idempotency_key=key,  # same key
                ordering_key=str(hold_id),
                payload={"hold_id": str(hold_id)},
                source_module="reclaimrx",
            )
            db_session.flush()
```

**Step 2 — Confirm failure:**

```bash
cd modules/reclaimrx
python -m pytest tests/unit/test_outbox_service.py -v 2>&1 | head -20
# Must show ImportError — test_outbox_service.py imports OutboxService which does not exist
```

Proceed to Task 2 only after confirming ImportError.

---

## Task 2 — Implement OutboxService

**File:** `modules/reclaimrx/src/outbox/event_outbox.py` (NEW)
**File:** `modules/reclaimrx/src/outbox/__init__.py` (NEW, empty)

```python
# modules/reclaimrx/src/outbox/event_outbox.py
"""Transactional outbox service for ReclaimRx.

Callers invoke write() INSIDE the same DB transaction as the domain change
(hold release, graph run completion). The OutboxEvent row is committed
atomically with the domain row — no dual-write risk (R1 BLOCK 4).

The outbox_dispatcher (Task 4) polls pending rows and publishes them to
the event bus with retry/exponential-backoff semantics.
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

    Usage (inside an open DB transaction):

        svc = OutboxService(db)
        svc.write(
            event_type="payment.hold_released",
            tenant_id=tenant_uuid,
            idempotency_key=f"hold:release:{hold_id}",
            ordering_key=str(hold_id),
            payload={...},
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
        The row is flushed but NOT committed — the caller owns the transaction
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
```

**Step 3 — Run tests, confirm pass:**

```bash
cd modules/reclaimrx
python -m pytest tests/unit/test_outbox_service.py -v
# All 3 tests must PASS
```

**Coverage check (100% required — security/idempotency path):**

```bash
python -m pytest tests/unit/test_outbox_service.py -v \
    --cov=src/outbox/event_outbox --cov-report=term-missing
# Must show 100% coverage on event_outbox.py
```

---

## Task 3 — Dispatcher unit tests (write failing tests first)

**File:** `modules/reclaimrx/tests/unit/test_outbox_dispatcher.py` (NEW)

```python
# modules/reclaimrx/tests/unit/test_outbox_dispatcher.py
"""Unit tests for OutboxDispatcher — background publisher.

TDD: MUST FAIL before Task 4 implements the dispatcher.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.outbox.outbox_dispatcher import OutboxDispatcher  # FAILS until Task 4


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
            session_factory=lambda: db_session,
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
            session_factory=lambda: db_session,
            bus=failing_bus,
            batch_size=10,
            poll_interval_seconds=0,
        )
        await dispatcher._poll_once()

        db_session.refresh(row)
        assert row.status == "pending"
        assert row.attempt_count == 1
        assert "broker down" in (row.last_error or "")

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
            attempt_count=10,   # already at max
            last_error="previous error",
            idempotency_key=f"hold:release:{hold_id}",
        )
        db_session.add(row)
        db_session.commit()

        failing_bus = MagicMock()
        failing_bus.publish = AsyncMock(side_effect=ConnectionError("still down"))

        dispatcher = OutboxDispatcher(
            session_factory=lambda: db_session,
            bus=failing_bus,
            batch_size=10,
            poll_interval_seconds=0,
        )
        await dispatcher._poll_once()

        db_session.refresh(row)
        assert row.status == "failed"
```

**Confirm failure:**

```bash
python -m pytest tests/unit/test_outbox_dispatcher.py -v 2>&1 | head -20
# Must show ImportError
```

---

## Task 4 — Implement OutboxDispatcher

**File:** `modules/reclaimrx/src/outbox/outbox_dispatcher.py` (NEW)

```python
# modules/reclaimrx/src/outbox/outbox_dispatcher.py
"""Outbox dispatcher — background asyncio worker.

Polls pending OutboxEvent rows, publishes to the event bus, marks rows
published. On failure, increments attempt_count and sets last_error.
After MAX_ATTEMPTS failures, marks the row failed and logs an alert.

Spec §7.2: dispatcher polls every 1s, exponential backoff on failure,
10 attempts max then status='failed' + alert (audit §8, D14).
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any, Callable

from sqlalchemy import select
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

    Usage (in FastAPI lifespan)::

        dispatcher = OutboxDispatcher(
            session_factory=get_session,
            bus=event_bus,
        )
        task = asyncio.create_task(dispatcher.start())

    The task runs until cancelled (e.g., on app shutdown).
    """

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
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
        """Blocking coroutine — run until cancelled."""
        self._running = True
        logger.info("reclaimrx.outbox_dispatcher.started",
                    extra={"svc_batch_size": self._batch_size,
                           "svc_poll_interval": self._poll_interval})
        while self._running:
            try:
                await self._poll_once()
            except Exception:
                logger.exception("reclaimrx.outbox_dispatcher.poll_error")
            if self._poll_interval > 0:
                await asyncio.sleep(self._poll_interval)

    async def stop(self) -> None:
        """Signal the dispatcher to stop after the current poll completes."""
        self._running = False

    async def _poll_once(self) -> None:
        """Single poll: fetch pending batch, publish, update status."""
        session = self._session_factory()
        try:
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
                await self._dispatch_row(session, row)
        finally:
            # Session is caller-managed; we do not close here to allow
            # test fixtures to retain the connection.
            pass

    async def _dispatch_row(self, session: Session, row: OutboxEvent) -> None:
        """Attempt to publish one outbox row."""
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
            # Sanitize: do not log PHI from payload
            error_str = f"{type(exc).__name__}: {str(exc)[:200]}"
            row.attempt_count += 1
            row.last_error = error_str
            session.commit()
            logger.warning(
                "reclaimrx.outbox_dispatcher.publish_failed",
                extra={
                    "svc_outbox_id": row.id,
                    "svc_event_type": row.event_type,
                    "svc_attempt_count": row.attempt_count,
                    "svc_error": error_str,
                },
            )
```

**Step 3 — Run tests:**

```bash
python -m pytest tests/unit/test_outbox_dispatcher.py -v
# All 3 tests must PASS
python -m pytest tests/unit/test_outbox_dispatcher.py \
    --cov=src/outbox/outbox_dispatcher --cov-report=term-missing
# Must show 100% on outbox_dispatcher.py
```

---

## Task 5 — DLQ real repository + Redis idempotency tests (write failing first)

**Files:**
- `modules/reclaimrx/tests/unit/test_dlq_repository.py` (NEW)
- `modules/reclaimrx/tests/unit/test_redis_idempotency.py` (NEW)

### 5a — DLQ repository test

```python
# modules/reclaimrx/tests/unit/test_dlq_repository.py
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

        fetched = await repo.get(entry_id)
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
```

### 5b — Redis idempotency tenant-prefix test

```python
# modules/reclaimrx/tests/unit/test_redis_idempotency.py
"""Tests for tenant-prefixed Redis idempotency key isolation.

Verifies the key format: tenant:{tenant_id}:reclaimrx:idempotency:{key}
per .claude/rules/tenant-isolation.md (Redis must use tenant-prefixed keys).
"""
from __future__ import annotations

import uuid
import pytest


class TestTenantPrefixedIdempotencyKeys:
    """Redis idempotency keys must be prefixed tenant:{tenant_id}:reclaimrx:idempotency:..."""

    def test_build_redis_key_format(self):
        """build_redis_key() returns correctly prefixed key."""
        from src.events.idempotency_keys import build_reclaimrx_idempotency_key  # Task 6

        tenant_id = uuid.UUID("12345678-1234-1234-1234-123456789012")
        raw_key = "hold:release:abc"
        result = build_reclaimrx_idempotency_key(tenant_id, raw_key)
        assert result == f"tenant:{tenant_id}:reclaimrx:idempotency:{raw_key}"

    def test_different_tenants_produce_different_keys(self):
        """Two tenants with same raw_key produce different Redis keys (isolation)."""
        from src.events.idempotency_keys import build_reclaimrx_idempotency_key

        t1 = uuid.uuid4()
        t2 = uuid.uuid4()
        key1 = build_reclaimrx_idempotency_key(t1, "hold:release:abc")
        key2 = build_reclaimrx_idempotency_key(t2, "hold:release:abc")
        assert key1 != key2
        assert str(t1) in key1
        assert str(t2) in key2
```

**Confirm both fail:**

```bash
python -m pytest tests/unit/test_dlq_repository.py tests/unit/test_redis_idempotency.py -v 2>&1 | head -20
```

---

## Task 6 — Implement DLQ real repository + idempotency key helper

### 6a — DLQ real repository

**File:** `modules/reclaimrx/src/events/dlq_repository.py` (NEW)

```python
# modules/reclaimrx/src/events/dlq_repository.py
"""DB-backed DLQ repository for ReclaimRx.

Replaces _EmptyDLQRepository stub in main.py.
Uses shared.db.models.events.EventDLQEntry ORM model.
Satisfies shared.events.dlq.DLQRepository Protocol.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

from shared.db.models.events import EventDLQEntry


class ReclaimRxDLQRepository:
    """Async SQLAlchemy DLQ repository backed by shared EventDLQEntry table.

    Tenant-scoped: list() filters by tenant_id when provided.
    """

    def __init__(self, engine: "AsyncEngine") -> None:
        self._engine = engine

    async def list(
        self,
        *,
        tenant_id: uuid.UUID | None = None,
        event_type: str | None = None,
        status: str = "queued",
        limit: int = 100,
    ) -> list[EventDLQEntry]:
        async with self._engine.connect() as conn:
            from sqlalchemy.ext.asyncio import AsyncSession  # noqa: PLC0415
            async_session = AsyncSession(bind=conn)
            q = select(EventDLQEntry).where(EventDLQEntry.status == status)
            if tenant_id is not None:
                q = q.where(EventDLQEntry.tenant_id == tenant_id)
            if event_type is not None:
                q = q.where(EventDLQEntry.event_type == event_type)
            q = q.limit(limit)
            result = await async_session.execute(q)
            return list(result.scalars().all())

    async def get(self, entry_id: uuid.UUID) -> EventDLQEntry | None:
        async with self._engine.connect() as conn:
            from sqlalchemy.ext.asyncio import AsyncSession  # noqa: PLC0415
            async_session = AsyncSession(bind=conn)
            result = await async_session.execute(
                select(EventDLQEntry).where(EventDLQEntry.id == entry_id)
            )
            return result.scalar_one_or_none()

    async def save(self, entry: EventDLQEntry) -> None:
        from sqlalchemy.ext.asyncio import AsyncSession  # noqa: PLC0415
        async with self._engine.begin() as conn:
            async_session = AsyncSession(bind=conn)
            async_session.add(entry)
            await async_session.commit()
```

### 6b — Idempotency key helper

**File:** `modules/reclaimrx/src/events/idempotency_keys.py` (NEW)

```python
# modules/reclaimrx/src/events/idempotency_keys.py
"""Tenant-prefixed Redis idempotency key builder for ReclaimRx.

Per .claude/rules/tenant-isolation.md:
    Redis keys MUST be prefixed: tenant:{tenant_id}:
Per the spec D8 binding:
    Full prefix: tenant:{tenant_id}:reclaimrx:idempotency:{raw_key}
"""
from __future__ import annotations

import uuid


def build_reclaimrx_idempotency_key(tenant_id: uuid.UUID, raw_key: str) -> str:
    """Build a tenant-scoped Redis idempotency key for ReclaimRx consumers.

    Args:
        tenant_id: The tenant UUID. Used as the first segment to ensure
            zero cross-tenant key collision per tenant-isolation.md.
        raw_key: The business-level idempotency key
            (e.g. 'hold:release:{hold_id}').

    Returns:
        'tenant:{tenant_id}:reclaimrx:idempotency:{raw_key}'
    """
    return f"tenant:{tenant_id}:reclaimrx:idempotency:{raw_key}"
```

**Run tests:**

```bash
python -m pytest tests/unit/test_dlq_repository.py tests/unit/test_redis_idempotency.py -v
# All tests must PASS
python -m pytest tests/unit/test_dlq_repository.py tests/unit/test_redis_idempotency.py \
    --cov=src/events/dlq_repository --cov=src/events/idempotency_keys --cov-report=term-missing
# 100% coverage required (security/tenant-isolation paths)
```

---

## Task 7 — Scheduler, cleanup job, audit hash-chain job, DLQ monitor (write failing tests first)

**File:** `modules/reclaimrx/tests/unit/test_reclaimrx_scheduler.py` (NEW)

```python
# modules/reclaimrx/tests/unit/test_reclaimrx_scheduler.py
"""Tests for ReclaimRxScheduler — asyncio.create_task + croniter pattern.

Scheduler pattern from shared/data_ingestion/scheduler.py (audit §7).
APScheduler is NOT installed — do NOT import it.

TDD: MUST FAIL before Task 8 implements the scheduler.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.jobs.reclaimrx_scheduler import ReclaimRxScheduler  # FAILS until Task 8


class TestReclaimRxScheduler:
    """ReclaimRxScheduler uses asyncio + croniter, not APScheduler."""

    def test_register_job_stores_it(self):
        """register() stores the job name + cron + callable."""
        sched = ReclaimRxScheduler()
        mock_fn = AsyncMock()
        sched.register("cleanup_processed_events", mock_fn, cron="0 2 * * *")
        assert "cleanup_processed_events" in sched._jobs

    @pytest.mark.asyncio
    async def test_stop_prevents_further_ticks(self):
        """stop() sets _running=False; start() exits after current tick."""
        sched = ReclaimRxScheduler(tick_interval_seconds=0)
        mock_fn = AsyncMock()
        sched.register("test_job", mock_fn, cron="0 0 1 1 *")  # Jan 1 only — won't fire
        task = asyncio.create_task(sched.start())
        await asyncio.sleep(0)  # yield
        await sched.stop()
        await asyncio.wait_for(task, timeout=1.0)
        # If stop() works, the task finishes cleanly within timeout
        assert True

    def test_no_apscheduler_import(self):
        """Verify the scheduler module does not import APScheduler."""
        import importlib
        import importlib.util
        spec = importlib.util.find_spec("apscheduler")
        assert spec is None or True  # APScheduler may or may not be installed
        # The real check: reclaimrx_scheduler does not USE it
        import src.jobs.reclaimrx_scheduler as sched_mod
        module_source = open(sched_mod.__file__).read()
        assert "apscheduler" not in module_source.lower()


class TestAuditHashChainJob:
    """Audit hash-chain verification job walks audit table, detects breaks."""

    @pytest.mark.asyncio
    async def test_clean_chain_returns_ok(self, db_session):
        """An intact hash chain returns result with status='ok', breaks=0."""
        from src.jobs.audit_chain_job import verify_audit_hash_chain  # FAILS until Task 8
        result = await verify_audit_hash_chain(db_session, tenant_id=None)
        assert result["status"] in ("ok", "no_entries")
        assert result["breaks"] == 0

    @pytest.mark.asyncio
    async def test_broken_chain_returns_alert(self, db_session, mocker):
        """A tampered prev_entry_hash triggers status='alert' with breaks > 0."""
        from src.jobs.audit_chain_job import verify_audit_hash_chain

        # Seed a broken chain row — prev_entry_hash does not match prior entry_hash
        from src.models.tables import ThresholdConfigAudit  # must exist from Plan A1
        import uuid, hashlib
        from datetime import UTC, datetime

        tenant_id = uuid.uuid4()
        # Entry 1
        e1 = ThresholdConfigAudit(
            id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            threshold_config_id=str(uuid.uuid4()),
            field="ml_score_thresholds.open",
            old_value="0.70",
            new_value="0.75",
            changed_at=datetime.now(UTC),
            changed_by="user-abc",
            reason="tuning",
            entry_hash=hashlib.sha256(b"entry1").hexdigest(),
            prev_entry_hash=None,
        )
        db_session.add(e1)
        # Entry 2 with WRONG prev_entry_hash (tampered)
        e2 = ThresholdConfigAudit(
            id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            threshold_config_id=str(uuid.uuid4()),
            field="ml_score_thresholds.open",
            old_value="0.75",
            new_value="0.80",
            changed_at=datetime.now(UTC),
            changed_by="user-abc",
            reason="tuning",
            entry_hash=hashlib.sha256(b"entry2").hexdigest(),
            prev_entry_hash="TAMPERED_HASH",  # does not match e1.entry_hash
        )
        db_session.add(e2)
        db_session.commit()

        result = await verify_audit_hash_chain(db_session, tenant_id=tenant_id)
        assert result["status"] == "alert"
        assert result["breaks"] >= 1


class TestDLQMonitorJob:
    """DLQ depth monitor alerts when depth > 0 for extended period."""

    @pytest.mark.asyncio
    async def test_zero_depth_returns_ok(self, async_db_engine):
        """Empty DLQ returns status='ok'."""
        from src.jobs.dlq_monitor import check_dlq_depth  # FAILS until Task 8
        result = await check_dlq_depth(async_db_engine)
        assert result["status"] == "ok"
        assert result["queued_count"] == 0
```

**Confirm failure:**

```bash
python -m pytest tests/unit/test_reclaimrx_scheduler.py -v 2>&1 | head -20
```

---

## Task 8 — Implement scheduler, jobs (audit chain, DLQ monitor, cleanup)

### 8a — ReclaimRxScheduler

**File:** `modules/reclaimrx/src/jobs/reclaimrx_scheduler.py` (NEW)

```python
# modules/reclaimrx/src/jobs/reclaimrx_scheduler.py
"""ReclaimRx module scheduler — asyncio.create_task + croniter pattern.

Mirrors the pattern from shared/data_ingestion/scheduler.py (audit §7).
APScheduler is NOT installed; do NOT import it.

Registered jobs (wired in create_app() lifespan):
  - cleanup_processed_events  cron: "0 1 * * *"   (01:00 UTC daily)
  - verify_audit_hash_chain   cron: "0 3 * * *"   (03:00 UTC daily per D14)
  - check_dlq_depth           cron: "*/15 * * * *" (every 15 min per event-bus.md)
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from croniter import croniter

logger = logging.getLogger("reclaimrx.scheduler")

_DEFAULT_TICK_SECONDS: float = 60.0

JobFn = Callable[[], Awaitable[None]]


class ReclaimRxScheduler:
    """Long-running cron scheduler for ReclaimRx jobs.

    Usage::

        scheduler = ReclaimRxScheduler()
        scheduler.register("cleanup", cleanup_fn, cron="0 1 * * *")
        task = asyncio.create_task(scheduler.start())
    """

    def __init__(self, tick_interval_seconds: float = _DEFAULT_TICK_SECONDS) -> None:
        self._tick_interval = tick_interval_seconds
        self._jobs: dict[str, tuple[JobFn, str, datetime | None]] = {}
        self._running = False
        self._running_tasks: set[asyncio.Task] = set()

    def register(self, name: str, fn: JobFn, *, cron: str) -> None:
        """Register a job with a cron expression.

        Args:
            name: Unique job name (used in logs).
            fn: Async callable; zero arguments; called when cron fires.
            cron: Standard 5-field cron expression (UTC).
        """
        next_run = _next_run(cron)
        self._jobs[name] = (fn, cron, next_run)
        logger.info(
            "reclaimrx.scheduler.job_registered",
            extra={"svc_job": name, "svc_cron": cron,
                   "svc_next_run": next_run.isoformat()},
        )

    async def start(self) -> None:
        """Blocking coroutine — run until stop() is called."""
        self._running = True
        logger.info("reclaimrx.scheduler.started")
        while self._running:
            await self._tick()
            if self._tick_interval > 0:
                await asyncio.sleep(self._tick_interval)

    async def stop(self) -> None:
        """Stop after the current tick completes."""
        self._running = False

    async def _tick(self) -> None:
        now = datetime.now(UTC)
        for name, (fn, cron, next_run) in list(self._jobs.items()):
            if next_run is not None and next_run <= now:
                logger.info("reclaimrx.scheduler.firing", extra={"svc_job": name})
                task = asyncio.create_task(self._run_job(name, fn))
                self._running_tasks.add(task)
                task.add_done_callback(self._running_tasks.discard)
                # Advance next_run
                self._jobs[name] = (fn, cron, _next_run(cron, after=now))

    async def _run_job(self, name: str, fn: JobFn) -> None:
        try:
            await fn()
        except Exception:
            logger.exception("reclaimrx.scheduler.job_error", extra={"svc_job": name})


def _next_run(cron_expr: str, after: datetime | None = None) -> datetime:
    base = (after or datetime.now(UTC)).replace(tzinfo=None)
    return croniter(cron_expr, base).get_next(datetime).replace(tzinfo=UTC)
```

### 8b — Audit hash-chain job

**File:** `modules/reclaimrx/src/jobs/audit_chain_job.py` (NEW)

```python
# modules/reclaimrx/src/jobs/audit_chain_job.py
"""Daily audit hash-chain verification job.

Scheduled at 03:00 UTC per D14 + .claude/rules/hipaa-2026.md:
    "MUST run daily integrity verification job."
    "MUST compute entry_hash on EVERY audit log write — never write with empty hash."

Walks ThresholdConfigAudit rows in chronological order per tenant,
verifies each entry's prev_entry_hash matches the prior entry's entry_hash.
Logs CRITICAL + alerts on any break.

Also verifies no entry has an empty entry_hash (write-time invariant).
"""
from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger("reclaimrx.jobs.audit_chain")


async def verify_audit_hash_chain(
    session: Session,
    *,
    tenant_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Walk ThresholdConfigAudit entries, verify hash chain integrity.

    Args:
        session: SQLAlchemy Session (sync — reclaimrx uses sync sessions).
        tenant_id: If provided, verify only entries for this tenant.
            If None, verifies all tenants (used in scheduled daily run).

    Returns:
        dict with keys: status ('ok'|'alert'|'no_entries'), breaks (int),
        empty_hashes (int), entries_checked (int), checked_at (ISO-8601).
    """
    from src.models.tables import ThresholdConfigAudit  # noqa: PLC0415 — local import

    q = select(ThresholdConfigAudit).order_by(
        ThresholdConfigAudit.tenant_id,
        ThresholdConfigAudit.changed_at,
    )
    if tenant_id is not None:
        q = q.where(ThresholdConfigAudit.tenant_id == str(tenant_id))

    entries = session.execute(q).scalars().all()

    if not entries:
        return {
            "status": "no_entries",
            "breaks": 0,
            "empty_hashes": 0,
            "entries_checked": 0,
            "checked_at": datetime.now(UTC).isoformat(),
        }

    breaks = 0
    empty_hashes = 0
    prev_by_tenant: dict[str, str | None] = {}

    for entry in entries:
        tid = entry.tenant_id

        # Check for empty entry_hash (write-time invariant from hipaa-2026.md)
        if not entry.entry_hash:
            empty_hashes += 1
            logger.critical(
                "reclaimrx.audit_chain.empty_entry_hash",
                extra={
                    "svc_entry_id": str(entry.id),
                    "svc_tenant_id": tid,
                    "audit_action": "audit_chain_verification",
                },
            )

        # Check prev_entry_hash matches prior entry's entry_hash
        expected_prev = prev_by_tenant.get(tid)
        if expected_prev is not None and entry.prev_entry_hash != expected_prev:
            breaks += 1
            logger.critical(
                "reclaimrx.audit_chain.hash_break",
                extra={
                    "svc_entry_id": str(entry.id),
                    "svc_tenant_id": tid,
                    "svc_expected_prev": expected_prev[:16] + "...",
                    "svc_actual_prev": str(entry.prev_entry_hash)[:16] + "...",
                    "audit_action": "audit_chain_verification",
                },
            )

        prev_by_tenant[tid] = entry.entry_hash

    status = "ok" if (breaks == 0 and empty_hashes == 0) else "alert"
    result = {
        "status": status,
        "breaks": breaks,
        "empty_hashes": empty_hashes,
        "entries_checked": len(entries),
        "checked_at": datetime.now(UTC).isoformat(),
    }
    if status == "alert":
        logger.critical(
            "reclaimrx.audit_chain.verification_failed",
            extra={"svc_breaks": breaks, "svc_empty_hashes": empty_hashes,
                   "audit_action": "audit_chain_verification"},
        )
    else:
        logger.info(
            "reclaimrx.audit_chain.verification_ok",
            extra={"svc_entries_checked": len(entries),
                   "audit_action": "audit_chain_verification"},
        )
    return result
```

### 8c — DLQ depth monitor

**File:** `modules/reclaimrx/src/jobs/dlq_monitor.py` (NEW)

```python
# modules/reclaimrx/src/jobs/dlq_monitor.py
"""DLQ depth monitor — event-bus.md rule:
    "MUST monitor DLQ depth — alert when > 0 for > 15 minutes."

Runs every 15 minutes via ReclaimRxScheduler (cron: "*/15 * * * *").
Queries EventDLQEntry for 'queued' status. Logs CRITICAL if depth > 0.
Metric exported as structured log for core-platform observability (D14).

Advisory-lock hash (for graph job reference in Plan A3):
    import zlib
    lock_key = zlib.crc32(f"graph_run:{tenant_id}".encode()) & 0x7FFFFFFF
    # NEVER use Python hash() — PYTHONHASHSEED-randomized (codex BLOCK 7)
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger("reclaimrx.jobs.dlq_monitor")


async def check_dlq_depth(engine: "AsyncEngine") -> dict[str, Any]:
    """Count queued DLQ entries; alert if depth > 0.

    Returns:
        dict: status ('ok'|'alert'), queued_count (int), checked_at (ISO-8601).
    """
    from shared.db.models.events import EventDLQEntry  # noqa: PLC0415

    async with engine.connect() as conn:
        from sqlalchemy.ext.asyncio import AsyncSession  # noqa: PLC0415
        async_session = AsyncSession(bind=conn)
        result = await async_session.execute(
            select(EventDLQEntry).where(EventDLQEntry.status == "queued").limit(1000)
        )
        queued = list(result.scalars().all())

    count = len(queued)
    status = "ok" if count == 0 else "alert"

    log = {
        "svc_dlq_queued_count": count,
        "svc_dlq_status": status,
        "audit_action": "dlq_depth_check",
    }

    if count > 0:
        logger.critical(
            "reclaimrx.dlq.depth_alert",
            extra=log,
        )
    else:
        logger.info("reclaimrx.dlq.depth_ok", extra=log)

    return {
        "status": status,
        "queued_count": count,
        "checked_at": datetime.now(UTC).isoformat(),
    }
```

**Run tests:**

```bash
python -m pytest tests/unit/test_reclaimrx_scheduler.py -v
# All tests must PASS
python -m pytest tests/unit/test_reclaimrx_scheduler.py \
    --cov=src/jobs/reclaimrx_scheduler \
    --cov=src/jobs/audit_chain_job \
    --cov=src/jobs/dlq_monitor \
    --cov-report=term-missing
# 100% on audit_chain_job.py (security/HIPAA path)
# 95%+ on scheduler, dlq_monitor
```

---

## Task 9 — Wire all 6 D14 bindings into create_app() + integration test

**Files:**
- `modules/reclaimrx/src/main.py` — EXTEND (do NOT rewrite; surgical changes only)
- `modules/reclaimrx/tests/integration/test_create_app_bindings.py` (NEW)

### 9a — Integration test (write first)

```python
# modules/reclaimrx/tests/integration/test_create_app_bindings.py
"""Integration test: create_app() D14 6-binding verification (LESSON-006).

Per D14 + spec §Plan A acceptance:
    "Plan A integration test through create_app() confirms all 6 mounted per LESSON-006."

The 6 required bindings:
  1. SecurityHeadersMiddleware
  2. RateLimitMiddleware
  3. DLQ router (build_dlq_router — real repo, not _EmptyDLQRepository)
  4. processed_events cleanup scheduler
  5. DLQ depth monitoring job
  6. Daily audit hash-chain verification job (03:00 UTC)
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestCreateAppD14Bindings:
    """All 6 D14 bindings confirmed through create_app()."""

    def test_security_headers_middleware_mounted(self):
        """Response includes security headers set by SecurityHeadersMiddleware."""
        from src.main import create_app
        app = create_app()
        client = TestClient(app)
        resp = client.get("/health")
        # SecurityHeadersMiddleware sets X-Content-Type-Options
        assert resp.headers.get("x-content-type-options") == "nosniff"

    def test_rate_limit_middleware_mounted(self):
        """RateLimitMiddleware is in the middleware stack."""
        from shared.middleware import RateLimitMiddleware
        from src.main import create_app
        app = create_app()
        middleware_types = [type(m.cls) for m in app.user_middleware
                            if hasattr(m, 'cls')]
        assert RateLimitMiddleware in middleware_types

    def test_dlq_router_uses_real_repository_not_empty_stub(self):
        """DLQ service is backed by ReclaimRxDLQRepository, not _EmptyDLQRepository."""
        from src.main import _get_dlq_service
        import asyncio
        svc = asyncio.get_event_loop().run_until_complete(_get_dlq_service())
        # _EmptyDLQRepository has no _engine attribute
        assert hasattr(svc._repo, '_engine'), (
            "DLQ repo is still _EmptyDLQRepository stub — replace with ReclaimRxDLQRepository"
        )

    def test_scheduler_registered_in_lifespan(self):
        """ReclaimRxScheduler is wired with 3 jobs (cleanup, audit_chain, dlq_depth)."""
        from src.main import create_app
        import asyncio

        app = create_app()
        # The scheduler instance is accessible via app.state after lifespan start.
        # Use a minimal lifespan context to verify registration.
        async def _check():
            async with app.router.lifespan_context(app):
                sched = getattr(app.state, 'scheduler', None)
                assert sched is not None, "scheduler not attached to app.state"
                assert "cleanup_processed_events" in sched._jobs
                assert "verify_audit_hash_chain" in sched._jobs
                assert "check_dlq_depth" in sched._jobs

        asyncio.get_event_loop().run_until_complete(_check())

    def test_processed_events_cleanup_job_registered(self):
        """cleanup_processed_events job is in scheduler._jobs."""
        # Covered by test_scheduler_registered_in_lifespan above — explicit assertion:
        from src.main import create_app
        import asyncio

        app = create_app()

        async def _check():
            async with app.router.lifespan_context(app):
                sched = app.state.scheduler
                assert "cleanup_processed_events" in sched._jobs

        asyncio.get_event_loop().run_until_complete(_check())

    def test_audit_hash_chain_job_registered_at_0300_utc(self):
        """verify_audit_hash_chain job uses 03:00 UTC cron per D14."""
        from src.main import create_app
        import asyncio

        app = create_app()

        async def _check():
            async with app.router.lifespan_context(app):
                sched = app.state.scheduler
                fn, cron, _ = sched._jobs["verify_audit_hash_chain"]
                assert cron == "0 3 * * *", f"Expected '0 3 * * *' got '{cron}'"

        asyncio.get_event_loop().run_until_complete(_check())
```

**Confirm failure:**

```bash
python -m pytest tests/integration/test_create_app_bindings.py -v 2>&1 | head -30
# Expect failures on DLQ real repo, scheduler tests
```

### 9b — Extend main.py (surgical changes only)

Read `modules/reclaimrx/src/main.py` in full before editing. Add the following to `create_app()` and `lifespan()`:

**Changes to lifespan:**

1. After `await wire_consumers(bus)`, instantiate `OutboxDispatcher` and `asyncio.create_task(dispatcher.start())`.
2. Instantiate `ReclaimRxScheduler` and register 3 jobs. Start it. Attach to `app.state.scheduler`.
3. On lifespan teardown (after `yield`), call `await dispatcher.stop()` and `await scheduler.stop()`.

**Changes to create_app():**

1. Replace `_EmptyDLQRepository` with `ReclaimRxDLQRepository(async_engine)`. Keep the same `_get_dlq_service` signature.

**Exact diff (do NOT copy the old lifespan — read the file, apply surgical changes):**

```python
# Add these imports at top of main.py
from src.outbox.outbox_dispatcher import OutboxDispatcher
from src.jobs.reclaimrx_scheduler import ReclaimRxScheduler
from src.jobs.audit_chain_job import verify_audit_hash_chain
from src.jobs.dlq_monitor import check_dlq_depth
from shared.events.jobs.cleanup_processed_events import run_cleanup

# Replace _EmptyDLQRepository import/definition with:
from src.events.dlq_repository import ReclaimRxDLQRepository

# In lifespan, after wire_consumers:
#   1. OutboxDispatcher
dispatcher = OutboxDispatcher(
    session_factory=get_session,   # must be the module's sync session factory
    bus=bus,
)
dispatcher_task = asyncio.create_task(dispatcher.start())
app.state.dispatcher = dispatcher

#   2. Scheduler with 3 required D14 jobs
# Build closed-over callables using the async engine
async_engine = ...  # from shared or module-level engine

async def _cleanup_job() -> None:
    await run_cleanup(async_engine, retention_days=7)

async def _audit_chain_job() -> None:
    from src._shim.db import get_sessionmaker  # noqa: PLC0415
    maker = get_sessionmaker()
    with maker() as session:
        await verify_audit_hash_chain(session)

async def _dlq_depth_job() -> None:
    await check_dlq_depth(async_engine)

scheduler = ReclaimRxScheduler()
scheduler.register("cleanup_processed_events", _cleanup_job, cron="0 1 * * *")
scheduler.register("verify_audit_hash_chain", _audit_chain_job, cron="0 3 * * *")
scheduler.register("check_dlq_depth", _dlq_depth_job, cron="*/15 * * * *")
scheduler_task = asyncio.create_task(scheduler.start())
app.state.scheduler = scheduler

yield  # <-- existing yield

# Teardown (after yield)
await dispatcher.stop()
await scheduler.stop()

# In create_app(): replace _get_dlq_service to use real repo
async def _get_dlq_service() -> DLQService:
    # async_engine injected from module-level engine
    return DLQService(repository=ReclaimRxDLQRepository(async_engine))
```

**IMPORTANT:** The actual async engine reference must be resolved from the existing module's DB setup. Grep `modules/reclaimrx/src/_shim/db.py` to find the engine factory. Do not invent a name. If no async engine exists (the module uses sync SQLAlchemy), use `create_async_engine` wrapping the existing sync URL, initialized once at module level.

**Run integration tests:**

```bash
python -m pytest tests/integration/test_create_app_bindings.py -v
# All 6 binding tests must PASS
```

**Run all Plan A2 tests:**

```bash
python -m pytest \
    tests/unit/test_outbox_service.py \
    tests/unit/test_outbox_dispatcher.py \
    tests/unit/test_dlq_repository.py \
    tests/unit/test_redis_idempotency.py \
    tests/unit/test_reclaimrx_scheduler.py \
    tests/integration/test_create_app_bindings.py \
    -v --tb=short
```

---

## Coverage gate (must pass before marking Plan A2 done)

```bash
python -m pytest \
    tests/unit/test_outbox_service.py \
    tests/unit/test_outbox_dispatcher.py \
    tests/unit/test_dlq_repository.py \
    tests/unit/test_redis_idempotency.py \
    tests/unit/test_reclaimrx_scheduler.py \
    tests/integration/test_create_app_bindings.py \
    --cov=src/outbox \
    --cov=src/jobs/reclaimrx_scheduler \
    --cov=src/jobs/audit_chain_job \
    --cov=src/jobs/dlq_monitor \
    --cov=src/events/dlq_repository \
    --cov=src/events/idempotency_keys \
    --cov-report=term-missing \
    --cov-fail-under=95
# Security/idempotency/audit paths (outbox, dlq_repository, idempotency_keys, audit_chain_job):
# 100% required per .claude/rules/testing.md
```

---

## D14 6-binding checklist (must all be green before Plan A3)

| # | Binding | Status after Plan A2 |
|---|---|---|
| 1 | `SecurityHeadersMiddleware` | Already mounted (main.py:94); no change needed |
| 2 | `RateLimitMiddleware` | Already mounted (main.py:93); no change needed |
| 3 | DLQ router (real repo) | **Plan A2 — replace `_EmptyDLQRepository` with `ReclaimRxDLQRepository`** |
| 4 | `processed_events` cleanup scheduler | **Plan A2 — register in `ReclaimRxScheduler`** |
| 5 | DLQ depth monitoring | **Plan A2 — register in `ReclaimRxScheduler`** |
| 6 | Daily audit hash-chain verification (03:00 UTC) | **Plan A2 — register in `ReclaimRxScheduler`** |

---

## Known constraints (executor must NOT violate)

- **APScheduler is NOT installed** — use `asyncio.create_task + croniter` pattern only (audit §7).
- **Advisory lock key** — `zlib.crc32(f"graph_run:{tenant_id}".encode()) & 0x7FFFFFFF` — NOT Python `hash()` (audit §9, codex BLOCK 7). Referenced in dlq_monitor.py docstring as a reminder for Plan A3.
- **EventEnvelope fields** — `event_type`, `tenant_id` (uuid.UUID), `correlation_id`, `source_module`. NOT `type`, NOT `emitted_at` (audit §2, codex BLOCK 4).
- **Redis idempotency key format** — `tenant:{tenant_id}:reclaimrx:idempotency:{raw_key}` (tenant-isolation.md).
- **No PHI in logs** — `last_error` on OutboxEvent must be sanitized (200-char truncated type+message only).
- **100% coverage** on audit_chain_job, outbox service, dlq_repository, idempotency_keys.
- **Sync SQLAlchemy** — reclaimrx currently uses sync sessions (audit §10 finding: "No async SQLAlchemy"). DLQ repository and cleanup job use async engine; the module-level sync session factory continues for everything else.

---

*End of Plan A2.*
