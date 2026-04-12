"""In-memory event bus behaviour: routing, correlation ids, error handling."""

from __future__ import annotations

import uuid

from shared.events import (
    EventEnvelope,
    InMemoryEventBus,
    event_types,
    new_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)
from shared.events.context import _correlation_id
from shared.events.factory import get_event_bus, reset_event_bus, set_event_bus


def _env(event_type: str = event_types.CLAIM_SUBMITTED) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        tenant_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        source_module="unit-test",
        payload={"ok": True},
    )


async def test_publish_roundtrip_to_exact_subscriber():
    bus = InMemoryEventBus()
    await bus.start()
    seen: list[EventEnvelope] = []

    async def handler(env: EventEnvelope) -> None:
        seen.append(env)

    await bus.subscribe(event_types.CLAIM_SUBMITTED, handler)
    env = _env()
    await bus.publish(env)

    assert seen == [env]
    assert bus.published == [env]
    await bus.stop()


async def test_pattern_subscription_matches_wildcards():
    bus = InMemoryEventBus()
    seen: list[str] = []

    async def h(env: EventEnvelope) -> None:
        seen.append(env.event_type)

    await bus.subscribe("claim.*", h)
    await bus.publish(_env(event_types.CLAIM_SUBMITTED))
    await bus.publish(_env(event_types.CLAIM_ADJUDICATED))
    await bus.publish(_env(event_types.JOB_COMPLETED))

    assert seen == [event_types.CLAIM_SUBMITTED, event_types.CLAIM_ADJUDICATED]


async def test_ambient_correlation_id_is_applied_on_publish():
    bus = InMemoryEventBus()
    cid = uuid.uuid4()
    token = set_correlation_id(cid)
    try:
        env = _env()
        assert env.correlation_id != cid
        await bus.publish(env)
        assert bus.published[0].correlation_id == cid
    finally:
        reset_correlation_id(token)


async def test_handler_exceptions_are_captured_not_raised():
    bus = InMemoryEventBus()

    async def boom(env: EventEnvelope) -> None:
        raise RuntimeError("kaboom")

    await bus.subscribe("*", boom)
    await bus.publish(_env())
    assert len(bus.handler_errors) == 1
    assert isinstance(bus.handler_errors[0], RuntimeError)


async def test_reset_and_drain_are_no_ops_for_in_memory():
    bus = InMemoryEventBus()
    await bus.publish(_env())
    assert bus.published
    bus.reset()
    assert bus.published == []
    await bus.drain()


async def test_new_correlation_id_generates_and_binds():
    reset_correlation_id(_correlation_id.set(None))
    cid = new_correlation_id()
    from shared.events import current_correlation_id
    assert current_correlation_id() == cid


def test_factory_returns_singleton_in_memory_by_default(monkeypatch):
    reset_event_bus()
    monkeypatch.delenv("EVENT_BUS_BACKEND", raising=False)
    bus1 = get_event_bus()
    bus2 = get_event_bus()
    assert bus1 is bus2
    assert isinstance(bus1, InMemoryEventBus)


def test_set_event_bus_overrides_singleton():
    fake = InMemoryEventBus()
    set_event_bus(fake)
    assert get_event_bus() is fake
    reset_event_bus()


async def test_publish_before_ambient_matches_envelope_cid_when_same():
    bus = InMemoryEventBus()
    cid = uuid.uuid4()
    token = set_correlation_id(cid)
    try:
        env = EventEnvelope(
            event_type=event_types.JOB_COMPLETED,
            tenant_id=uuid.uuid4(),
            correlation_id=cid,
            source_module="core-platform",
        )
        await bus.publish(env)
        assert bus.published[0].correlation_id == cid
    finally:
        reset_correlation_id(token)
