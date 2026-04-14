"""CR-11: payment-processing consumers must be idempotent under duplicate delivery.

Wires the real `wire_consumers()` helper against an `InMemoryEventBus` and
asserts that publishing the same `payment_batch.submitted` envelope twice
causes the sync handler to fire exactly once — the only protection against
double-submitting an ACH file or vendor instruction.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from shared.events.in_memory_bus import InMemoryEventBus
from shared.events.types import EventEnvelope


@pytest.fixture(autouse=True)
def _reset_idempotency_store() -> None:
    from src.events import _idempotency_store

    _idempotency_store._store.clear()


@pytest.fixture()
def patched_consumers(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    """Replace the real sync handlers with mocks before wire_consumers runs.

    wire_consumers() does `from .consumers import handle_X` so the function
    references are captured at wire time — patching after subscription has
    no effect. Patch the module attribute first, then call wire_consumers.
    """
    from src.events import consumers

    mocks = {
        "handle_payment_batch_submitted": MagicMock(),
        "handle_fwa_hold_placed": MagicMock(),
        "handle_fwa_hold_released": MagicMock(),
    }
    for name, mock in mocks.items():
        monkeypatch.setattr(consumers, name, mock)
    return mocks


@pytest.mark.asyncio
async def test_duplicate_payment_batch_submitted_invokes_handler_once(
    patched_consumers: dict[str, MagicMock],
) -> None:
    bus = InMemoryEventBus()
    await bus.start()

    from src.events import wire_consumers
    await wire_consumers(bus)

    envelope = EventEnvelope(
        event_type="payment_batch.submitted",
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        correlation_id=uuid.uuid4(),
        source_module="billing",
        schema_version="1.0",
        ordering_key="batch-1",
        idempotency_key="payment_batch.submitted:batch-1",
        payload={"batch_id": "batch-1"},
    )
    await bus.publish(envelope)
    await bus.publish(envelope)

    assert patched_consumers["handle_payment_batch_submitted"].call_count == 1, (
        f"Expected handler to fire once, got "
        f"{patched_consumers['handle_payment_batch_submitted'].call_count}"
    )


@pytest.mark.asyncio
async def test_fwa_hold_placed_idempotent(
    patched_consumers: dict[str, MagicMock],
) -> None:
    bus = InMemoryEventBus()
    await bus.start()

    from src.events import wire_consumers
    await wire_consumers(bus)

    envelope = EventEnvelope(
        event_type="fwa.payment_hold_placed",
        tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        correlation_id=uuid.uuid4(),
        source_module="reclaimrx",
        schema_version="1.0",
        ordering_key="entity-7",
        idempotency_key="fwa.payment_hold_placed:entity-7",
        payload={"entity_id": "entity-7", "reason": "FWA-flag"},
    )
    await bus.publish(envelope)
    await bus.publish(envelope)

    assert patched_consumers["handle_fwa_hold_placed"].call_count == 1
