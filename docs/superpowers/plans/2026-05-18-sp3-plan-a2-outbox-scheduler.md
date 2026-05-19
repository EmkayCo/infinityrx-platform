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
the event bus. On per-row publish failure the row is reverted to
status='pending' (with attempt_count incremented) and retried on the
NEXT poll cycle. After _MAX_ATTEMPTS failures the row is moved to
status='failed' and an alert is logged. No per-row delay/backoff is
implemented — retry cadence is bounded by the dispatcher's fixed
`poll_interval_seconds` (default 1.0s). Per-row exponential backoff
requires a `next_attempt_at` column on `reclaimrx_outbox_events` and
is deferred to a follow-on wave (R6 BLOCK-20).
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

### 2c — Same-transaction atomicity integration test (R1 CONCERN 2 fix)

OutboxService.write() flushes but does not commit; the caller's surrounding
transaction commits both the domain row and the outbox row atomically.
The unit tests above prove the flush behavior in isolation. R1 CONCERN 2
asks for end-to-end proof that this atomicity holds when invoked from a
real domain flow (rollback → neither persists; commit → both persist).

**File:** `modules/reclaimrx/tests/integration/test_outbox_atomicity.py` (NEW)

```python
"""Integration test: outbox row + domain row commit/rollback atomically.

R1 CONCERN 2 fix: prove single-transaction guarantees in a real domain flow.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from src.models.tables import PaymentHold, OutboxEvent
from src.outbox.event_outbox import OutboxService


def test_rollback_drops_both_rows(db, tenant_a_id):
    """Mutating PaymentHold + writing outbox, then rollback → hold reverts AND
    no outbox row persists.

    R6 WARN-3 fix: the old test seeded the hold inside the rolled-back
    transaction so `refreshed is None` was trivially true regardless of
    OutboxService behavior. Now we commit the seed FIRST (with status
    'active'), then mutate (status → 'released') + write outbox + rollback,
    then assert the hold reverted to 'active' (proving atomicity bound
    the mutation to the outbox write) and no outbox row exists.
    """
    hold = _seed_hold(db, tenant_a_id)
    db.commit()  # seed survives — proves the rollback only undoes the mutation

    # Domain mutation + outbox write, both in the same session/transaction
    hold.status = "released"
    hold.released_at = datetime.now(UTC)
    OutboxService(db).write(
        event_type="payment.hold_released",
        tenant_id=uuid.UUID(tenant_a_id),
        payload={"hold_id": hold.id, "released_at": hold.released_at.isoformat()},
        ordering_key=hold.id,
        idempotency_key=f"hold:release:{hold.id}",
    )

    # ROLLBACK (simulate domain failure AFTER the outbox row was added to the session)
    db.rollback()

    refreshed = db.execute(
        select(PaymentHold).where(PaymentHold.id == hold.id)
    ).scalar_one_or_none()
    outbox_row = db.execute(
        select(OutboxEvent).where(OutboxEvent.idempotency_key == f"hold:release:{hold.id}")
    ).scalar_one_or_none()
    # Hold reverted to its committed (pre-mutation) state.
    assert refreshed is not None
    assert refreshed.status == "active"
    assert refreshed.released_at is None
    # Outbox row never persisted — the rollback discarded it.
    assert outbox_row is None


def test_commit_persists_both_rows(db, tenant_a_id):
    """Updating PaymentHold + writing outbox, then commit → both persist."""
    hold = _seed_hold(db, tenant_a_id)
    db.commit()  # seed the hold first so we can assert mutation

    hold.status = "released"
    OutboxService(db).write(
        event_type="payment.hold_released",
        tenant_id=uuid.UUID(tenant_a_id),
        payload={"hold_id": hold.id},
        ordering_key=hold.id,
        idempotency_key=f"hold:release:{hold.id}",
    )
    db.commit()

    refreshed = db.execute(select(PaymentHold).where(PaymentHold.id == hold.id)).scalar_one()
    assert refreshed.status == "released"

    outbox_row = db.execute(
        select(OutboxEvent).where(OutboxEvent.idempotency_key == f"hold:release:{hold.id}")
    ).scalar_one()
    assert outbox_row.event_type == "payment.hold_released"
    assert outbox_row.status == "pending"


def _seed_hold(db, tenant_id: str) -> PaymentHold:
    h = PaymentHold(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        flagged_claim_id=str(uuid.uuid4()),
        amount_threshold=Decimal("100.00"),
        reason="seeded",
        status="active",  # column added by Plan A1
        is_active=True,
        created_at=datetime.now(UTC),
    )
    db.add(h)
    return h
```

**Run:** `pytest modules/reclaimrx/tests/integration/test_outbox_atomicity.py -x` → expect ALL PASS.

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
        # R5 BLOCK-12 fix: last_error stores exception class label only
        # (module.ClassName), never the raw exception args/message — those
        # may contain PHI from the envelope payload. The mock raised
        # ConnectionError("broker down"); we assert the class label and
        # explicitly verify the message body is NOT present.
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

Spec §7.2: dispatcher polls every 1s, retries failed rows on the NEXT
poll cycle (no per-row delay; retry cadence is the dispatcher's
poll_interval), 10 attempts max then status='failed' + alert
(audit §8, D14). R6 BLOCK-20: per-row exponential backoff requires a
`next_attempt_at` column and is deferred to a follow-on wave; the
spec line that originally said "exponential backoff" is reconciled
to "fixed retry on next poll" — both bound mean-time-to-publish and
satisfy the at-least-once delivery requirement.
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

    R6 BLOCK-14 architectural note: this dispatcher is **system-wide**.
    A single dispatcher process drains the `reclaimrx_outbox_events`
    table for ALL tenants. Each row carries its own `tenant_id` (set
    by `OutboxService.write` from the envelope), which is propagated
    through `EventEnvelope.tenant_id` and consumers self-filter
    downstream. The dispatcher must NOT install the tenant loader on
    its session — it intentionally reads across tenants. A cross-tenant
    isolation test (test_dispatcher_publishes_all_tenants) proves this.

    R6 BLOCK-13 orphan recovery: on `start()`, the dispatcher does a
    one-shot reclaim of any rows left in `status='publishing'` by a
    crashed previous run, returning them to `pending` so the new run
    will retry them. THIS MODEL ASSUMES SOLO DEPLOYMENT — one
    dispatcher process per cluster. Scaling out to multiple dispatchers
    requires adding a `claim_expires_at TIMESTAMPTZ` column to
    `reclaimrx_outbox_events` and reclaiming only rows whose lease has
    expired — this is explicitly deferred to a follow-on wave (tracked
    in B12-backlog/outbox-multi-dispatcher).

    Usage (in FastAPI lifespan)::

        dispatcher = OutboxDispatcher(
            session_factory=get_sessionmaker(),   # sessionmaker callable
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
        """Blocking coroutine — run until cancelled.

        R6 BLOCK-13 fix: reclaim orphans (publishing rows from a crashed
        prior run) BEFORE entering the poll loop. Solo-deployment model.
        """
        self._reclaim_orphans()
        self._running = True
        logger.info("reclaimrx.outbox_dispatcher.started",
                    extra={"svc_batch_size": self._batch_size,
                           "svc_poll_interval": self._poll_interval})
        while self._running:
            try:
                await self._poll_once()
            except Exception:
                logger.exception("reclaimrx.outbox_dispatcher.poll_error")
            # R8 BLOCK-25 fix (paired with ReclaimRxScheduler.start): ALWAYS
            # yield to the event loop between polls. Passing 0 to
            # asyncio.sleep still yields control once per iteration; a bare
            # conditional sleep would busy-loop and starve `stop()` /
            # task.cancel() under tick_interval=0 unit tests.
            await asyncio.sleep(self._poll_interval)

    def _reclaim_orphans(self) -> None:
        """Revert any rows stuck in 'publishing' from a prior crashed run.

        R6 BLOCK-13 fix. Runs once at start(). Solo-deployment model: if a
        second dispatcher is running concurrently, this WILL clobber its
        in-flight claims — see class docstring deferral note.

        Increments `attempt_count` so a row that crashed mid-publish does
        not retry forever; once attempt_count >= _MAX_ATTEMPTS the row is
        moved to `failed` by `_dispatch_row` like any other failed row.
        """
        with self._session_factory() as session:
            result = session.execute(
                text(
                    """
                    UPDATE reclaimrx_outbox_events
                    SET status = 'pending',
                        attempt_count = attempt_count + 1
                    WHERE status = 'publishing'
                    """
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
        """Single poll: atomically claim pending batch, publish, update status.

        R1 BLOCK 3 fix: claim rows via UPDATE-with-RETURNING gated by
        WHERE status='pending', so concurrent dispatchers cannot pick
        the same row. The Postgres semantics relied on here are
        equivalent to SELECT FOR UPDATE SKIP LOCKED — a row whose
        status is being transitioned by one transaction is invisible
        to another's WHERE status='pending' predicate at REPEATABLE READ.

        On non-Postgres (SQLite test fixture) we fall back to the
        SELECT-then-flip pattern under SAVEPOINT isolation, which is
        deterministic in single-process test mode.

        R3 BLOCK 12 fix: exceptions propagate to the outer `start()` loop,
        which logs+backs off. No silent swallowing.

        R6 BLOCK-16 fix: session is now owned by THIS poll cycle (created
        + closed inside the `with` block). Long-lived sessions would leak
        connections forever in production. `_session_factory` is a
        sessionmaker callable (see __init__ + R6 BLOCK-15 wiring fix).
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
        """Atomically transition the next batch from 'pending' to 'publishing'
        and return the claimed rows. Two concurrent dispatchers cannot claim
        the same row because the UPDATE-WHERE-status='pending' predicate
        is atomic.
        """
        ids_result = session.execute(
            text(
                """
                WITH claimed AS (
                    SELECT id FROM reclaimrx_outbox_events
                    WHERE status = 'pending'
                    ORDER BY created_at
                    LIMIT :batch_size
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE reclaimrx_outbox_events o
                SET status = 'publishing'
                FROM claimed
                WHERE o.id = claimed.id
                RETURNING o.id
                """
            ),
            {"batch_size": self._batch_size},
        )
        claimed_ids = [row[0] for row in ids_result]
        session.commit()  # release row lock; rows are now status='publishing'
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
        """Fallback claim for non-Postgres backends (SQLite test fixture).
        Uses SAVEPOINT-friendly select-then-flip; safe in single-process tests.
        """
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

        Pre-condition: row.status == 'publishing' (was claimed atomically
        by _claim_postgres or _claim_generic). On success → 'published',
        on retryable failure → back to 'pending' (with attempt_count++),
        on terminal failure (attempt_count >= _MAX_ATTEMPTS) → 'failed'.
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
            # R4 NEW-2 fix: never serialize exception args — they can carry
            # PHI from the original envelope payload (event-bus.md + phi-compliance.md).
            # last_error stores exception class label only.
            #
            # R7 WARN-5 fix: the prior comment claimed `logger.exception()`
            # at the outer OutboxDispatcher loop captured a stack trace,
            # but this except branch swallows the exception (the row is
            # transitioned back to 'pending' and the loop continues), so
            # the outer loop never sees it. We now call `logger.exception()`
            # HERE so the stack trace IS persisted. Stack traces only
            # contain code locations + filenames — no envelope payload
            # data — so they do not leak PHI per phi-compliance.md.
            error_label = f"{exc.__class__.__module__}.{exc.__class__.__name__}"
            row.attempt_count += 1
            row.last_error = error_label
            # Revert claim → pending so another dispatcher can retry on next poll.
            row.status = "pending"
            session.commit()
            logger.exception(
                "reclaimrx.outbox_dispatcher.publish_failed",
                extra={
                    "svc_outbox_id": row.id,
                    "svc_event_type": row.event_type,
                    "svc_attempt_count": row.attempt_count,
                    "svc_error_class": error_label,
                },
            )
```

**Concurrent-dispatcher claim test** (file: `modules/reclaimrx/tests/integration/test_outbox_concurrent_claim.py` — NEW, Postgres-only):

```python
"""Integration test: two concurrent dispatchers cannot publish the same row.

R1 BLOCK 3 fix: proves the atomic claim semantics work end-to-end.
SQLite cannot model FOR UPDATE SKIP LOCKED behavior; this test is
gated on a real Postgres connection.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.outbox.event_outbox import OutboxService  # R6 BLOCK-18 fix: was src.events.outbox_service
from src.outbox.outbox_dispatcher import OutboxDispatcher


pytestmark = pytest.mark.skipif(
    not os.environ.get("RECLAIMRX_TEST_PG_URL"),
    reason="Concurrent claim test requires Postgres (set RECLAIMRX_TEST_PG_URL)",
)


@pytest.mark.asyncio
async def test_two_dispatchers_each_claim_disjoint_rows():
    """Seed 10 pending rows; run 2 dispatchers concurrently.

    Postcondition: every row is published exactly once. The set of rows
    published by dispatcher A and dispatcher B are disjoint and their
    union equals the seeded set.
    """
    pg_url = os.environ["RECLAIMRX_TEST_PG_URL"]
    engine = create_engine(pg_url)
    Session = sessionmaker(bind=engine)

    # Seed 10 pending rows
    tenant_id = uuid.uuid4()
    with Session() as session:
        svc = OutboxService(session)
        for i in range(10):
            svc.write(
                event_type=f"test.event_{i}",
                tenant_id=tenant_id,
                payload={"n": i},
                ordering_key=str(i),
                idempotency_key=f"test:{i}",
            )
        session.commit()

    published_a: list[str] = []
    published_b: list[str] = []

    class CollectingBus:
        def __init__(self, sink: list[str]):
            self._sink = sink

        async def publish(self, envelope):
            self._sink.append(envelope.idempotency_key)

    # R6 BLOCK-18 fix: constructor parameter is `poll_interval_seconds`,
    # not `poll_interval`. Previous kwarg raised TypeError at construction.
    disp_a = OutboxDispatcher(session_factory=Session, bus=CollectingBus(published_a),
                              batch_size=5, poll_interval_seconds=0.01)
    disp_b = OutboxDispatcher(session_factory=Session, bus=CollectingBus(published_b),
                              batch_size=5, poll_interval_seconds=0.01)

    # Race them
    await asyncio.gather(disp_a._poll_once(), disp_b._poll_once())

    seen = set(published_a) | set(published_b)
    assert len(seen) == 10, f"expected 10 distinct rows, got {len(seen)}"
    assert set(published_a).isdisjoint(set(published_b)), (
        f"dispatchers published overlapping rows: A={published_a}, B={published_b}"
    )


@pytest.mark.asyncio
async def test_dispatcher_publishes_all_tenants():
    """R6 BLOCK-14: dispatcher is system-wide; rows from all tenants must be published.

    Seed 3 rows under tenant_a + 3 rows under tenant_b. One dispatcher
    poll publishes ALL 6 rows. The dispatcher does NOT install the
    tenant loader on its session (no tenant filtering). tenant_id is
    preserved on each published envelope so downstream consumers
    self-filter.
    """
    pg_url = os.environ["RECLAIMRX_TEST_PG_URL"]
    engine = create_engine(pg_url)
    Session = sessionmaker(bind=engine)

    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    with Session() as session:
        svc = OutboxService(session)
        for tid in (tenant_a, tenant_b):
            for i in range(3):
                svc.write(
                    event_type="payment.hold_released",
                    tenant_id=tid,
                    payload={"hold_id": f"{tid}:{i}"},
                    ordering_key=f"{tid}:{i}",
                    idempotency_key=f"cross:{tid}:{i}",
                )
        session.commit()

    published_envelopes: list = []

    class CollectingBus:
        async def publish(self, envelope):
            published_envelopes.append(envelope)

    dispatcher = OutboxDispatcher(
        session_factory=Session, bus=CollectingBus(),
        batch_size=10, poll_interval_seconds=0.01,
    )
    await dispatcher._poll_once()

    tenant_ids_published = {env.tenant_id for env in published_envelopes}
    assert len(published_envelopes) == 6, (
        f"expected 6 rows published, got {len(published_envelopes)}"
    )
    assert tenant_ids_published == {tenant_a, tenant_b}, (
        f"expected both tenants represented, got {tenant_ids_published}"
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
    """Redis idempotency keys must be prefixed tenant:{tenant_id}:reclaimrx:idempotency:{key}."""

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

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

from shared.db.models.events import EventDLQEntry

# R7 BLOCK-21 fix: logger + datetime/UTC are referenced in the get()
# tenant-fallback path (warning log) and in replay()/drop()
# (replayed_at = datetime.now(UTC)). Missing imports would NameError
# at first runtime use.
logger = logging.getLogger("reclaimrx.events.dlq_repository")


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
        # R8 BLOCK-26 fix: bind AsyncSession to the engine (not to a
        # connection we own), so SQLAlchemy owns the connection +
        # transaction lifecycle through the session contextmanager. The
        # prior `AsyncSession(bind=conn)` inside `engine.connect()` set
        # up two competing transaction owners and silently corrupted
        # DLQ reads under retry.
        from sqlalchemy.ext.asyncio import AsyncSession  # noqa: PLC0415
        async with AsyncSession(self._engine) as session:
            q = select(EventDLQEntry).where(EventDLQEntry.status == status)
            if tenant_id is not None:
                q = q.where(EventDLQEntry.tenant_id == tenant_id)
            if event_type is not None:
                q = q.where(EventDLQEntry.event_type == event_type)
            q = q.limit(limit)
            result = await session.execute(q)
            return list(result.scalars().all())

    async def get(
        self,
        entry_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID | None = None,
    ) -> EventDLQEntry | None:
        """Fetch one DLQ entry, scoped to a specific tenant.

        R6 BLOCK-17 fix: `tenant_id` is OPTIONAL to satisfy the shared
        `shared.events.dlq.DLQRepository` protocol signature
        (`get(entry_id) -> ... | None`). When the caller is the shared
        `DLQService.replay` or `DLQService.drop` (which both call
        `self._repo.get(entry_id)` with NO tenant_id kwarg), we resolve
        tenant from `shared.db.tenant_context.current_tenant_id()`
        (populated by the tenant middleware at request entry). If neither
        explicit nor contextvar tenant is available we return None — the
        shared service treats None as "not found" and raises KeyError,
        which the FastAPI router maps to 404. Direct callers may still
        pass `tenant_id=` explicitly for clarity / out-of-band tools.

        R2 BLOCK 9 fix + R3 BLOCK 9 / 13 follow-up: tenant filtering is
        unconditional — every query filters by tenant_id regardless of
        whether it was passed in or resolved from the context.
        """
        if tenant_id is None:
            from shared.db.tenant_context import current_tenant_id  # noqa: PLC0415
            resolved = current_tenant_id()
            if resolved is None:
                logger.warning(
                    "reclaimrx.dlq_repository.no_tenant_context",
                    extra={"audit_action": "dlq_get_missing_tenant"},
                )
                return None
            tenant_id = resolved
        # R8 BLOCK-26 fix: AsyncSession bound to the engine (not a
        # caller-owned connection) so SQLAlchemy owns connection +
        # transaction lifecycle.
        from sqlalchemy.ext.asyncio import AsyncSession  # noqa: PLC0415
        async with AsyncSession(self._engine) as session:
            result = await session.execute(
                select(EventDLQEntry).where(
                    EventDLQEntry.id == entry_id,
                    EventDLQEntry.tenant_id == tenant_id,
                )
            )
            return result.scalar_one_or_none()

    async def replay(self, entry_id: uuid.UUID, *, tenant_id: uuid.UUID) -> int:
        """Re-enqueue a DLQ entry. Returns row-count (0 = not-found / wrong tenant).

        R3 BLOCK 9 + 13 fix: execute a single-session, tenant-scoped UPDATE
        instead of `get()` + ORM-mutation on a separate already-closed session.
        The previous pattern mutated a detached object and was never flushed
        through a new session correctly.
        """
        from sqlalchemy import update  # noqa: PLC0415
        async with self._engine.begin() as conn:
            result = await conn.execute(
                update(EventDLQEntry)
                .where(
                    EventDLQEntry.id == entry_id,
                    EventDLQEntry.tenant_id == tenant_id,
                    EventDLQEntry.status == "queued",
                )
                .values(status="replayed", replayed_at=datetime.now(UTC))
            )
            return int(result.rowcount or 0)

    async def drop(self, entry_id: uuid.UUID, *, tenant_id: uuid.UUID) -> int:
        """Permanently discard a DLQ entry. Returns row-count.

        R3 BLOCK 10 fix: EventDLQEntry has NO `dropped_at` column (verified
        against `shared/db/models/events.py:28-73`). We track the drop event
        via `status='dropped'` only (CHECK constraint allows the value);
        timestamping is the audit chain's job.

        R3 BLOCK 9 + 13 fix: tenant-scoped single-session UPDATE.
        """
        from sqlalchemy import update  # noqa: PLC0415
        async with self._engine.begin() as conn:
            result = await conn.execute(
                update(EventDLQEntry)
                .where(
                    EventDLQEntry.id == entry_id,
                    EventDLQEntry.tenant_id == tenant_id,
                )
                .values(status="dropped")
            )
            return int(result.rowcount or 0)

    async def save(self, entry: EventDLQEntry) -> None:
        # R8 BLOCK-26 fix: AsyncSession bound to the engine — NOT to a
        # connection from `engine.begin()`. Binding to an already-owned
        # connection meant both `engine.begin()` and `async_session.commit()`
        # tried to manage the transaction, silently corrupting DLQ writes
        # under concurrent replay. The session contextmanager handles
        # connection acquisition + commit/rollback cleanly.
        from sqlalchemy.ext.asyncio import AsyncSession  # noqa: PLC0415
        async with AsyncSession(self._engine) as session:
            session.add(entry)
            await session.commit()
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

### 6c — Wire PostgresIdempotencyStore in events/__init__.py (R1 BLOCK 6 fix)

The helper above only builds key strings. R1 BLOCK 6 calls out that
`modules/reclaimrx/src/events/__init__.py` currently uses
`InMemoryIdempotencyStore`, which is non-durable and loses idempotency
state across worker restarts. A2 scope explicitly includes wiring the
real durable store; this step makes that wiring explicit.

**File:** `modules/reclaimrx/src/events/__init__.py` (EDIT — full replacement of the idempotency wiring; NOT surgical addition).

This is a deletion-and-replacement, not an addition. The `InMemoryIdempotencyStore`
import on the current file's line 22 and its module-level instantiation on line 29
MUST be removed in the same diff that adds the new wiring. Acceptance: after the
edit, `grep -n InMemoryIdempotencyStore modules/reclaimrx/src/events/__init__.py`
returns ZERO lines.

R2 BLOCK 5 fix — the prior draft read as additive ("replace _idempotency_store"),
which is ambiguous when the file also has subscribe-site uses of the variable.
Executor MUST delete the prior import + instantiation lines AND update every
subscribe call to obtain the store via `get_idempotency_store()` instead of the
module-level singleton.

Replace:

```python
# OLD (current — DELETE these lines):
from shared.events.idempotency import InMemoryIdempotencyStore
_idempotency_store = InMemoryIdempotencyStore()
```

With:

```python
# NEW (A2 — durable):
from shared.events.idempotency import (
    PostgresIdempotencyStore,
    idempotent_handler,
)
from src._shim.db import get_async_engine_for_idempotency

# Module-level singleton — built once from the async engine; consumer
# wiring imports this object and passes it to idempotent_handler.
_idempotency_store: PostgresIdempotencyStore | None = None


def get_idempotency_store() -> PostgresIdempotencyStore:
    """Lazy accessor — wire_consumers() calls this once at startup."""
    global _idempotency_store
    if _idempotency_store is None:
        engine = get_async_engine_for_idempotency()
        _idempotency_store = PostgresIdempotencyStore(engine=engine)
    return _idempotency_store
```

Then in `wire_consumers(bus)` (same file), every `bus.subscribe(...)`
call MUST wrap its handler with `idempotent_handler(get_idempotency_store())`
and pass a tenant-prefixed key built from `build_reclaimrx_idempotency_key`.

The current `modules/reclaimrx/src/_shim/db.py` exposes only `configure_engine(url)`,
`get_engine()`, `get_sessionmaker()`, `get_session()`, `tenant_context()`,
`current_tenant_id()`, `create_all()`, and `drop_all()`. It has NO async
engine factory. A2 MUST add one, building the async URL from the existing
sync engine's `.url` so there is a single source of truth for the
configured database URL.

```python
# modules/reclaimrx/src/_shim/db.py — APPEND (after the existing
# get_sessionmaker / get_session block; do NOT introduce a parallel
# URL-resolution path).
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

_async_engine: AsyncEngine | None = None


def get_async_engine_for_idempotency() -> AsyncEngine:
    """Return the module's async engine, built lazily from the SAME URL
    the existing sync engine was configured with.

    Single source of truth: `configure_engine(url)` (in this same module)
    remains the only place the URL is set; the async engine inherits the
    same URL by reading `get_engine().url`. No parallel URL resolver.

    Used by PostgresIdempotencyStore and the DLQ repository. One instance
    per process.
    """
    global _async_engine
    if _async_engine is None:
        sync_engine = get_engine()
        sync_url = str(sync_engine.url)  # SQLAlchemy URL → str
        # Swap the sync driver tag for asyncpg ONLY for postgresql URLs.
        # SQLite (used in tests) has no async driver — fall back to aiosqlite
        # when the test sets sqlite:///, but tests typically stub
        # PostgresIdempotencyStore so this branch is rarely hit.
        if sync_url.startswith("postgresql://"):
            async_url = sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif sync_url.startswith("postgresql+psycopg2://"):
            async_url = sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
        elif sync_url.startswith("sqlite:///"):
            async_url = sync_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        else:
            raise RuntimeError(
                f"Unsupported sync URL for async wrapping: {sync_url!r}. "
                "Add a branch here when introducing a new dialect."
            )
        _async_engine = create_async_engine(async_url, future=True)
    return _async_engine
```

### 6d — Integration test: real store is wired through create_app() (R1 BLOCK 6 fix)

**File:** `modules/reclaimrx/tests/integration/test_idempotency_wired.py` (NEW)

```python
"""Integration test: PostgresIdempotencyStore is wired through create_app().

R1 BLOCK 6 fix: prove the in-memory store is gone and the durable store
is used by every consumer registered via wire_consumers().
"""
from __future__ import annotations

import pytest
from src.main import create_app


def test_idempotency_store_is_postgres_not_in_memory(monkeypatch):
    """get_idempotency_store() returns PostgresIdempotencyStore, not the
    InMemoryIdempotencyStore stub.

    R8 BLOCK-27 fix: monkeypatch `get_async_engine_for_idempotency` to
    return a fake AsyncEngine. Calling `create_app()` triggers the
    factory, and CI does not have a live Postgres at module load time
    (the idempotency-store wiring is unit-level, not integration-level).
    A real engine-bound integration test lives in
    `test_idempotency_real_postgres.py` and is gated on
    `RECLAIMRX_TEST_PG_URL`.
    """
    from shared.events.idempotency import (
        PostgresIdempotencyStore,
        InMemoryIdempotencyStore,
    )
    from src.events import get_idempotency_store

    # Stub the async engine factory so create_app() does not try to
    # open a real Postgres connection at import-time.
    from unittest.mock import MagicMock  # noqa: PLC0415
    fake_engine = MagicMock(name="FakeAsyncEngine")
    monkeypatch.setattr(
        "src._shim.db.get_async_engine_for_idempotency",
        lambda: fake_engine,
    )

    # Force app initialization so wire_consumers runs
    _ = create_app()

    store = get_idempotency_store()
    assert isinstance(store, PostgresIdempotencyStore), (
        f"expected PostgresIdempotencyStore, got {type(store).__name__}"
    )
    assert not isinstance(store, InMemoryIdempotencyStore)


def test_module_does_not_import_inmemory_store():
    """events/__init__.py must not IMPORT InMemoryIdempotencyStore at module load.

    R7 BLOCK-24 fix: prior version did a substring match on the file source,
    which false-positives on any comment that mentions the class name (e.g.,
    "# replaced InMemoryIdempotencyStore with PostgresIdempotencyStore in
    A2 §6c"). We now do an AST parse and inspect ONLY the import nodes,
    so explanatory comments — which we WANT to keep — are ignored.
    """
    import ast
    import src.events as events_module

    tree = ast.parse(open(events_module.__file__).read())
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported_names.add(alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.name.rsplit(".", 1)[-1])

    assert "InMemoryIdempotencyStore" not in imported_names, (
        "events/__init__.py still IMPORTS InMemoryIdempotencyStore — "
        "replace with PostgresIdempotencyStore per A2 BLOCK 6. "
        f"(Imported names: {sorted(imported_names)})"
    )
```

**Run:** `pytest modules/reclaimrx/tests/integration/test_idempotency_wired.py -x` → expect FAIL until 6c is applied, then PASS.

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
        """stop() sets _running=False; start() exits after current tick.

        R2 CONCERN 10 fix: replace the prior `assert True` no-op with concrete
        assertions on scheduler state and task completion.
        """
        sched = ReclaimRxScheduler(tick_interval_seconds=0)
        mock_fn = AsyncMock()
        sched.register("test_job", mock_fn, cron="0 0 1 1 *")  # Jan 1 only — won't fire
        task = asyncio.create_task(sched.start())
        await asyncio.sleep(0)  # yield
        await sched.stop()
        await asyncio.wait_for(task, timeout=1.0)

        # Real assertions: scheduler stopped cleanly and the task finished.
        assert sched._running is False
        assert task.done()
        assert task.exception() is None

    def test_no_apscheduler_import(self):
        """Verify the scheduler module does not import APScheduler.

        R1 CONCERN 4 fix: replace prior no-op `assert spec is None or True`
        (which is always True regardless of install state) with a real
        source-level assertion against the scheduler module.
        """
        import src.jobs.reclaimrx_scheduler as sched_mod
        module_source = open(sched_mod.__file__).read()
        assert "apscheduler" not in module_source.lower(), (
            "ReclaimRxScheduler must use asyncio + croniter, not APScheduler"
        )
        assert "import apscheduler" not in module_source
        assert "from apscheduler" not in module_source


class TestAuditHashChainJob:
    """Audit hash-chain verification job walks audit table, detects breaks.

    R7 BLOCK-22 fix: verify_audit_hash_chain is plain `def` (WARN-2 from
    R6). Tests call it synchronously — no `@pytest.mark.asyncio` decorator,
    no `await`. The scheduler wrapper in main.py lifespan is what runs it
    in a worker thread via asyncio.to_thread().
    """

    def test_clean_chain_returns_ok(self, db_session):
        """An intact hash chain returns result with status='ok', breaks=0."""
        from src.jobs.audit_chain_job import verify_audit_hash_chain  # FAILS until Task 8
        result = verify_audit_hash_chain(db_session, tenant_id=None)
        assert result["status"] in ("ok", "no_entries")
        assert result["breaks"] == 0

    def test_broken_chain_returns_alert(self, db_session, mocker):
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

        result = verify_audit_hash_chain(db_session, tenant_id=tenant_id)
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
        """Blocking coroutine — run until stop() is called.

        R8 BLOCK-25 fix: ALWAYS yield to the event loop between ticks via
        `asyncio.sleep(...)`. The prior guard `if self._tick_interval > 0:
        await asyncio.sleep(...)` would skip the yield entirely when
        tick_interval_seconds=0 (the value used by unit tests), producing
        an infinite busy-loop that starved the event loop — stop()
        running on the same loop would never get scheduled, so the
        scheduler would never stop and pytest would hang. Passing 0 to
        asyncio.sleep still yields control to the loop once per tick.
        """
        self._running = True
        logger.info("reclaimrx.scheduler.started")
        while self._running:
            await self._tick()
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


def verify_audit_hash_chain(
    session: Session,
    *,
    tenant_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Walk ThresholdConfigAudit entries, verify hash chain integrity.

    R6 WARN-2 fix: this is a plain `def` (not `async def`). The body uses
    sync `session.execute()` / `session.scalars()` against a sync Session,
    which would block the asyncio event loop for the full table-walk
    duration if called directly from a coroutine. The scheduler wrapper
    in `main.py` lifespan calls it via `asyncio.to_thread(...)` so the
    sync work runs in a worker thread and the event loop stays
    responsive during the daily scan.

    Args:
        session: SQLAlchemy Session (sync — reclaimrx uses sync sessions).
        tenant_id: If provided, verify only entries for this tenant.
            If None, verifies all tenants (used in scheduled daily run).

    Returns:
        dict with keys: status ('ok'|'alert'|'no_entries'), breaks (int),
        empty_hashes (int), entries_checked (int), checked_at (ISO-8601).
    """
    from src.models.tables import ThresholdConfigAudit  # noqa: PLC0415 — local import

    # R1 CONCERN 8 fix: deterministic ordering across same-timestamp rows.
    # Without the secondary `id` key, two entries written in the same
    # millisecond can swap order across runs, producing non-deterministic
    # hash-chain verification results.
    q = select(ThresholdConfigAudit).order_by(
        ThresholdConfigAudit.tenant_id,
        ThresholdConfigAudit.changed_at,
        ThresholdConfigAudit.id,
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
                    "svc_expected_prev_prefix16": expected_prev[:16],
                    "svc_actual_prev_prefix16": str(entry.prev_entry_hash)[:16],
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


_DLQ_DURATION_THRESHOLD_MINUTES = 15  # event-bus.md: "> 0 for > 15 minutes"


async def check_dlq_depth(engine: "AsyncEngine") -> dict[str, Any]:
    """Count queued DLQ entries; alert if oldest queued is older than 15 minutes.

    R1 BLOCK 9 fix: event-bus.md says "alert when depth > 0 for > 15 minutes",
    NOT "alert immediately when depth > 0". A queued entry that has only just
    failed is not yet an operational incident — the dispatcher retry loop may
    drain it on its next pass. We must alert only when the OLDEST queued
    entry has persisted past the duration threshold.

    Returns:
        dict: status ('ok' | 'monitoring' | 'alert'),
              queued_count (int),
              oldest_first_failed_at (ISO-8601 or None),
              oldest_age_minutes (float or None),
              threshold_minutes (15),
              checked_at (ISO-8601).
    """
    from datetime import timedelta  # noqa: PLC0415
    from sqlalchemy import func  # noqa: PLC0415

    from shared.db.models.events import EventDLQEntry  # noqa: PLC0415

    now = datetime.now(UTC)

    # R6 BLOCK-19 fix: use `await conn.execute(...)` directly on the
    # AsyncConnection instead of wrapping in an AsyncSession. The
    # AsyncSession+MagicMock combination made unit testing impossible
    # (SQLAlchemy internals tripped on the mock conn). Direct conn.execute
    # is the supported SQLAlchemy idiom for non-ORM read-only aggregates,
    # avoids one layer of session machinery, and lets the test fixture
    # be a plain async mock.
    async with engine.connect() as conn:
        # Aggregate query: count + oldest first_failed_at in a single round-trip.
        result = await conn.execute(
            select(
                func.count(EventDLQEntry.id),
                func.min(EventDLQEntry.first_failed_at),
            ).where(EventDLQEntry.status == "queued")
        )
        count, oldest_first_failed_at = result.one()

    age_minutes: float | None = None
    if oldest_first_failed_at is not None:
        # Defensive: DB may return naive datetime depending on driver — coerce to UTC.
        if oldest_first_failed_at.tzinfo is None:
            oldest_first_failed_at = oldest_first_failed_at.replace(tzinfo=UTC)
        age_minutes = (now - oldest_first_failed_at).total_seconds() / 60.0

    if count == 0:
        status = "ok"
    elif age_minutes is not None and age_minutes > _DLQ_DURATION_THRESHOLD_MINUTES:
        status = "alert"
    else:
        # Depth > 0 but oldest entry is within the 15-minute grace window.
        status = "monitoring"

    log = {
        "svc_dlq_queued_count": count,
        "svc_dlq_status": status,
        "svc_dlq_oldest_age_minutes": age_minutes,
        "svc_dlq_threshold_minutes": _DLQ_DURATION_THRESHOLD_MINUTES,
        "audit_action": "dlq_depth_check",
    }

    if status == "alert":
        logger.critical("reclaimrx.dlq.depth_alert", extra=log)
    elif status == "monitoring":
        logger.warning("reclaimrx.dlq.depth_monitoring", extra=log)
    else:
        logger.info("reclaimrx.dlq.depth_ok", extra=log)

    return {
        "status": status,
        "queued_count": count,
        "oldest_first_failed_at": (
            oldest_first_failed_at.isoformat() if oldest_first_failed_at else None
        ),
        "oldest_age_minutes": age_minutes,
        "threshold_minutes": _DLQ_DURATION_THRESHOLD_MINUTES,
        "checked_at": now.isoformat(),
    }
```

**DLQ duration threshold tests** (file: `modules/reclaimrx/tests/unit/test_dlq_monitor.py` — NEW, complement to existing scheduler tests):

```python
"""Unit tests for check_dlq_depth duration threshold (R1 BLOCK 9 fix)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.jobs.dlq_monitor import check_dlq_depth, _DLQ_DURATION_THRESHOLD_MINUTES


@pytest.mark.asyncio
async def test_ok_when_queue_empty(monkeypatch):
    """Empty queue → status='ok', queued_count=0."""
    engine = _stub_engine(count=0, oldest=None)
    result = await check_dlq_depth(engine)
    assert result["status"] == "ok"
    assert result["queued_count"] == 0
    assert result["oldest_age_minutes"] is None


@pytest.mark.asyncio
async def test_monitoring_when_count_positive_but_age_under_threshold():
    """Depth > 0 but oldest is 5 minutes old → 'monitoring' (NOT 'alert')."""
    oldest = datetime.now(UTC) - timedelta(minutes=5)
    engine = _stub_engine(count=3, oldest=oldest)
    result = await check_dlq_depth(engine)
    assert result["status"] == "monitoring"
    assert result["queued_count"] == 3
    assert result["oldest_age_minutes"] < _DLQ_DURATION_THRESHOLD_MINUTES


@pytest.mark.asyncio
async def test_alert_when_oldest_age_exceeds_threshold():
    """Oldest is 20 minutes old → 'alert'."""
    oldest = datetime.now(UTC) - timedelta(minutes=20)
    engine = _stub_engine(count=1, oldest=oldest)
    result = await check_dlq_depth(engine)
    assert result["status"] == "alert"
    assert result["oldest_age_minutes"] > _DLQ_DURATION_THRESHOLD_MINUTES


@pytest.mark.asyncio
async def test_boundary_exactly_at_threshold():
    """Exactly 15 minutes → still 'monitoring' (rule is `> 15`, not `>= 15`)."""
    oldest = datetime.now(UTC) - timedelta(minutes=15)
    engine = _stub_engine(count=2, oldest=oldest)
    result = await check_dlq_depth(engine)
    assert result["status"] == "monitoring"


def _stub_engine(count: int, oldest: datetime | None):
    """Build a mock AsyncEngine whose connect().__aenter__().execute() returns
    a result whose .one() yields (count, oldest).

    R6 BLOCK-19 fix: paired with the implementation switch from
    `AsyncSession(bind=conn).execute()` to `conn.execute()` directly,
    we now only need to mock `conn.execute()` → result.one() — no
    AsyncSession monkeypatching required. The mock is self-contained
    and the tests above run as written.
    """
    result = MagicMock()
    result.one = MagicMock(return_value=(count, oldest))

    conn = MagicMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value=result)

    engine = MagicMock()
    engine.connect = MagicMock(return_value=conn)
    return engine
```

The mock above is sufficient for unit tests of the duration-threshold
logic. An end-to-end DLQ depth test against a real Postgres / sqlite
DLQ table lives in `tests/integration/test_dlq_monitor_real.py` and
follows the testing.md SAVEPOINT pattern.

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
        """RateLimitMiddleware is in the middleware stack.

        R1 BLOCK 11 fix: `m.cls` is already the class; `type(m.cls)` yields
        the metaclass `type` rather than the middleware class, so the original
        assertion always failed against `RateLimitMiddleware`.
        """
        from shared.middleware import RateLimitMiddleware
        from src.main import create_app
        app = create_app()
        middleware_classes = [m.cls for m in app.user_middleware
                              if hasattr(m, 'cls')]
        assert RateLimitMiddleware in middleware_classes

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
    # R6 BLOCK-15 fix: `get_session` in _shim/db.py is a generator-style
    # FastAPI dependency (`Iterator[Session]`), NOT a Session factory.
    # Passing it directly leaks generators into `session.bind`. We pass
    # the sessionmaker itself (a Callable[[], Session]) which is the
    # callable contract OutboxDispatcher expects.
    session_factory=get_sessionmaker(),
    bus=bus,
)
dispatcher_task = asyncio.create_task(dispatcher.start())
app.state.dispatcher = dispatcher

#   2. Scheduler with 3 required D14 jobs.
# Resolve the async engine via the get_async_engine_for_idempotency() factory
# added to _shim/db.py per A2 §6c (R2 BLOCK 7 fix). No ellipsis placeholder —
# the function above is the SINGLE concrete entry point for the async engine.
from src._shim.db import get_async_engine_for_idempotency  # noqa: PLC0415
async_engine = get_async_engine_for_idempotency()

async def _cleanup_job() -> None:
    await run_cleanup(async_engine, retention_days=7)

async def _audit_chain_job() -> None:
    # R6 WARN-2 fix: verify_audit_hash_chain is plain `def` (sync) so
    # `session.execute()` / `session.scalars()` calls do not block the
    # event loop. Run in worker thread via asyncio.to_thread.
    from src._shim.db import get_sessionmaker  # noqa: PLC0415

    def _run() -> None:
        maker = get_sessionmaker()
        with maker() as session:
            verify_audit_hash_chain(session)

    await asyncio.to_thread(_run)

async def _dlq_depth_job() -> None:
    await check_dlq_depth(async_engine)

scheduler = ReclaimRxScheduler()
scheduler.register("cleanup_processed_events", _cleanup_job, cron="0 1 * * *")
scheduler.register("verify_audit_hash_chain", _audit_chain_job, cron="0 3 * * *")
scheduler.register("check_dlq_depth", _dlq_depth_job, cron="*/15 * * * *")
scheduler_task = asyncio.create_task(scheduler.start())
app.state.scheduler = scheduler

yield  # <-- existing yield

# Teardown (after yield) — R6 WARN-4 fix: stop() flips the running flag but
# the underlying asyncio.Task may still be inside a `sleep(poll_interval)`
# call (dispatcher) or a `sleep(60)` croniter wait (scheduler). Calling
# stop() alone leaves the task running until the next wake-up — under ASGI
# the process can be killed before the scheduler exits. Cancel + gather
# guarantees clean shutdown.
await dispatcher.stop()
await scheduler.stop()
dispatcher_task.cancel()
scheduler_task.cancel()
await asyncio.gather(dispatcher_task, scheduler_task, return_exceptions=True)

# In create_app(): replace _get_dlq_service to use real repo
# R7 BLOCK-23 fix: the prior version referenced `async_engine` which was a
# lifespan-local binding (visible only inside the `async def lifespan` body).
# `_get_dlq_service` is wired as the FastAPI `Depends(...)` provider for the
# DLQ router, called per-request — at request time the lifespan-local
# variable is out of scope and the function would NameError. Resolve the
# engine fresh on each call via `get_async_engine_for_idempotency()` — that
# accessor is module-level + idempotent (returns the same singleton), so
# there is no startup ordering or extra connection cost.
async def _get_dlq_service() -> DLQService:
    from src._shim.db import get_async_engine_for_idempotency  # noqa: PLC0415
    return DLQService(repository=ReclaimRxDLQRepository(get_async_engine_for_idempotency()))
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
- **No PHI in logs** — `last_error` on OutboxEvent stores exception class label only (`exc.__class__.__module__ + "." + exc.__class__.__name__`); NEVER the exception args/message, since those may carry envelope payload contents (R5 BLOCK-12 / R4 NEW-2). Stack traces are logged via `logger.exception(...)` INSIDE `_dispatch_row`'s except branch (R7 WARN-5 / R8 BLOCK-28 fix) — that branch catches+swallows the publish exception, so the outer `OutboxDispatcher.start()` loop never sees it. Stack traces only contain code locations + filenames, no envelope payload data, so logging them at the catch point is PHI-safe.
- **100% coverage** on audit_chain_job, outbox service, dlq_repository, idempotency_keys.
- **Sync SQLAlchemy** — reclaimrx currently uses sync sessions (audit §10 finding: "No async SQLAlchemy"). DLQ repository and cleanup job use async engine; the module-level sync session factory continues for everything else.

---

*End of Plan A2.*
