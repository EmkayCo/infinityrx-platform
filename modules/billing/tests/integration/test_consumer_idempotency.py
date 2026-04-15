"""CR-11: billing consumers must be idempotent under duplicate event delivery.

Drives the real `wire_consumers()` helper against an `InMemoryEventBus` and
asserts that publishing the same EventEnvelope twice causes the underlying
handler to fire exactly once. This protects against double-posting AP/AR
records in the face of broker re-delivery or producer retries.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.events.in_memory_bus import InMemoryEventBus
from shared.events.types import EventEnvelope


@contextmanager
def _fake_session():
    """No-DB session factory for wrapper tests that mock the handler body."""
    yield MagicMock()


@pytest.fixture(autouse=True)
def _reset_idempotency_store() -> None:
    """The wire_consumers helper uses a module-level InMemoryIdempotencyStore
    that persists across tests. Reset it to give each test a clean slate."""
    from src.events import _idempotency_store

    _idempotency_store._store.clear()


@pytest.fixture()
def envelope() -> EventEnvelope:
    return EventEnvelope(
        event_type="claim.adjudicated",
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        correlation_id=uuid.uuid4(),
        source_module="adjudication-engine",
        schema_version="1.0",
        ordering_key="claim-1",
        idempotency_key="claim.adjudicated:claim-1",
        payload={
            "claim_id": "claim-1",
            "auth_number": "AUTH123",
            "tenant_id": "11111111-1111-1111-1111-111111111111",
        },
    )


@pytest.mark.asyncio
async def test_duplicate_claim_adjudicated_invokes_handler_once(envelope: EventEnvelope) -> None:
    bus = InMemoryEventBus()
    await bus.start()

    handler_mock = AsyncMock()
    with patch(
        "modules.billing.src.events.consumers.handle_claim_adjudicated",
        new=handler_mock,
    ):
        from src.events import wire_consumers

        await wire_consumers(bus, session_factory=_fake_session)

        await bus.publish(envelope)
        await bus.publish(envelope)  # same idempotency_key

    assert handler_mock.await_count == 1, (
        f"Expected handler to be called once, got {handler_mock.await_count} — "
        "idempotent_handler wrapper not active"
    )


@pytest.mark.asyncio
async def test_distinct_idempotency_keys_invoke_handler_each_time() -> None:
    bus = InMemoryEventBus()
    await bus.start()

    handler_mock = AsyncMock()
    with patch(
        "modules.billing.src.events.consumers.handle_claim_adjudicated",
        new=handler_mock,
    ):
        from src.events import wire_consumers

        await wire_consumers(bus, session_factory=_fake_session)

        for i in range(3):
            await bus.publish(
                EventEnvelope(
                    event_type="claim.adjudicated",
                    tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
                    correlation_id=uuid.uuid4(),
                    source_module="adjudication-engine",
                    schema_version="1.0",
                    ordering_key=f"claim-{i}",
                    idempotency_key=f"claim.adjudicated:claim-{i}",
                    payload={"claim_id": f"claim-{i}"},
                )
            )

    assert handler_mock.await_count == 3
