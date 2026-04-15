"""CR-01: reclaimrx lifespan must wire all 8 CONSUMER_ROUTING handlers.

Publishes one event per routed topic through an InMemoryEventBus and asserts
each handler fires exactly once. Also verifies duplicate envelopes do not
re-invoke the handler (idempotency).
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from shared.events.in_memory_bus import InMemoryEventBus
from shared.events.types import EventEnvelope


TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _envelope(event_type: str, ordering: str = "1") -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        tenant_id=TENANT,
        correlation_id=uuid.uuid4(),
        source_module="test",
        schema_version="1.0",
        ordering_key=ordering,
        idempotency_key=f"{event_type}:{ordering}",
        payload={"tenant_id": str(TENANT)},
    )


@pytest.fixture(autouse=True)
def _reset_idempotency_store() -> None:
    from src.events import _idempotency_store
    _idempotency_store._store.clear()


@pytest.mark.asyncio
async def test_wire_consumers_subscribes_all_routing_keys() -> None:
    bus = InMemoryEventBus()
    await bus.start()

    from src.events import wire_consumers
    from src.events.consumers import CONSUMER_ROUTING

    await wire_consumers(bus)

    # Every topic in CONSUMER_ROUTING must have a subscriber
    subscribed = {pat for pat, _ in bus._subs}
    missing = set(CONSUMER_ROUTING.keys()) - subscribed
    assert not missing, f"topics not wired: {missing}"


@pytest.mark.asyncio
async def test_each_topic_invokes_its_handler() -> None:
    bus = InMemoryEventBus()
    await bus.start()

    import src.events.consumers as _consumers
    mocks: dict[str, MagicMock] = {}
    patchers = []
    for topic, original in list(_consumers.CONSUMER_ROUTING.items()):
        mock = MagicMock()
        mocks[topic] = mock
        _consumers.CONSUMER_ROUTING[topic] = mock  # type: ignore[assignment]
        patchers.append((topic, original))

    try:
        from src.events import wire_consumers
        await wire_consumers(bus)

        for topic in mocks:
            await bus.publish(_envelope(topic, ordering=topic))

        for topic, mock in mocks.items():
            assert mock.call_count == 1, f"{topic} not invoked"
    finally:
        for topic, original in patchers:
            _consumers.CONSUMER_ROUTING[topic] = original  # type: ignore[assignment]


@pytest.mark.asyncio
async def test_duplicate_delivery_is_idempotent() -> None:
    bus = InMemoryEventBus()
    await bus.start()

    mock_handler = MagicMock()
    with patch.dict(
        "src.events.consumers.CONSUMER_ROUTING",
        {"exclusion.match_found": mock_handler},
        clear=False,
    ):
        from src.events import wire_consumers
        await wire_consumers(bus)

        env = _envelope("exclusion.match_found", ordering="dup-1")
        await bus.publish(env)
        await bus.publish(env)

    assert mock_handler.call_count == 1
