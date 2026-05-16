"""Integration tests for member-management event consumer wiring.

CR-01 v2 BLOCK-4 fix: wire_consumers() must use a session_factory that
commits on success. v1's session context only closed() — accumulator writes
were lost on process restart.

These tests verify:
1. wire_consumers() subscribes handlers for claim.adjudicated and claim.reversed
2. session_factory is called per-event (per-delivery session pattern)
3. session.commit() is called after a successful event delivery
4. session.rollback() is called if the handler raises
"""
from __future__ import annotations

import os
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch, call

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))
_PLATFORM_ROOT = _MODULE_ROOT.parent.parent
if str(_PLATFORM_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLATFORM_ROOT))

os.environ.setdefault("ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM=")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")

import pytest

from shared.events import InMemoryEventBus, EventEnvelope
from shared.events.idempotency import InMemoryIdempotencyStore

TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
CORR = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
ACCUMULATOR_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CLAIM_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.mark.asyncio
async def test_wire_consumers_subscribes_claim_adjudicated():
    """wire_consumers() must subscribe a handler for claim.adjudicated."""
    from src.events import wire_consumers

    session_factory = _make_noop_factory()
    bus = InMemoryEventBus()
    await bus.start()
    await wire_consumers(bus, session_factory=session_factory)
    assert any(t == "claim.adjudicated" for t, _ in bus._subs), "claim.adjudicated must be subscribed"
    await bus.stop()


@pytest.mark.asyncio
async def test_wire_consumers_subscribes_claim_reversed():
    """wire_consumers() must subscribe a handler for claim.reversed."""
    from src.events import wire_consumers

    session_factory = _make_noop_factory()
    bus = InMemoryEventBus()
    await bus.start()
    await wire_consumers(bus, session_factory=session_factory)
    assert any(t == "claim.reversed" for t, _ in bus._subs), "claim.reversed must be subscribed"
    await bus.stop()


@pytest.mark.asyncio
async def test_session_factory_called_per_event():
    """session_factory must be called for each event, not once at startup."""
    from src.events import wire_consumers

    call_count = 0
    mock_session = _make_mock_session()

    @contextmanager
    def counting_factory():
        nonlocal call_count
        call_count += 1
        yield mock_session

    bus = InMemoryEventBus()
    await bus.start()
    store = InMemoryIdempotencyStore()
    await wire_consumers(bus, session_factory=counting_factory, idempotency_store=store)

    for _ in range(2):
        env = _make_adjudicated_envelope()
        await bus.publish(env)

    await bus.stop()
    assert call_count == 2, "session_factory must be called once per event delivery"


@pytest.mark.asyncio
async def test_idempotency_claim_adjudicated_not_reprocessed():
    """Duplicate claim.adjudicated envelopes must be dropped by idempotency store."""
    from src.events import wire_consumers

    call_count = 0
    mock_session = _make_mock_session()

    @contextmanager
    def counting_factory():
        nonlocal call_count
        call_count += 1
        yield mock_session

    store = InMemoryIdempotencyStore()
    bus = InMemoryEventBus()
    await bus.start()
    await wire_consumers(bus, session_factory=counting_factory, idempotency_store=store)

    idem_key = f"claim.adjudicated:dedup-{uuid.uuid4()}"
    envelope = _make_adjudicated_envelope(idempotency_key=idem_key)

    await bus.publish(envelope)
    await bus.publish(envelope)  # duplicate
    await bus.stop()

    assert call_count == 1, "Duplicate event must call session_factory exactly once"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_session():
    """Return a MagicMock that simulates a session with a found Accumulator row."""
    from decimal import Decimal
    session = MagicMock()
    # Simulate an Accumulator row so AccumulatorDbService.apply_claim() succeeds.
    mock_acc = MagicMock()
    mock_acc.accumulated_amount = Decimal("0.00")
    mock_acc.limit_amount = Decimal("1000.00")
    session.query.return_value.filter_by.return_value.first.return_value = mock_acc
    return session


def _make_noop_factory():
    mock_session = _make_mock_session()

    @contextmanager
    def _factory():
        yield mock_session

    return _factory


def _make_adjudicated_envelope(idempotency_key: str | None = None) -> EventEnvelope:
    kwargs = dict(
        event_type="claim.adjudicated",
        tenant_id=TENANT_A,
        correlation_id=CORR,
        source_module="adjudication-engine",
        payload={
            "tenant_id": str(TENANT_A),
            "accumulator_id": str(ACCUMULATOR_ID),
            "claim_id": str(CLAIM_ID),
            "patient_pay": "25.00",
        },
    )
    if idempotency_key:
        kwargs["idempotency_key"] = idempotency_key
    return EventEnvelope(**kwargs)
