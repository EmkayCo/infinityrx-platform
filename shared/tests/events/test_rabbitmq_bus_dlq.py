"""Tests for DLQ-aware RabbitMQ bus and per-entity ordering.

Most tests use InMemoryEventBus + InMemoryDLQSink for speed and isolation.
One integration test uses a real RabbitMQ broker (marked rabbitmq) and is
skipped when the broker is unavailable.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from shared.events.dlq_sink import DLQSink, InMemoryDLQSink
from shared.events.in_memory_bus import InMemoryEventBus
from shared.events.types import EventEnvelope
from shared.events import event_types


def _env(
    event_type: str = event_types.PAYMENT_GENERATED,
    ordering_key: str | None = None,
    idempotency_key: str | None = None,
) -> EventEnvelope:
    kwargs: dict[str, Any] = dict(
        event_type=event_type,
        tenant_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        source_module="test-module",
    )
    if ordering_key:
        kwargs["ordering_key"] = ordering_key
    if idempotency_key:
        kwargs["idempotency_key"] = idempotency_key
    return EventEnvelope(**kwargs)


# ---------------------------------------------------------------------------
# InMemoryDLQSink
# ---------------------------------------------------------------------------


async def test_in_memory_dlq_sink_write_stores_entry():
    from shared.db.models.events import EventDLQEntry
    sink = InMemoryDLQSink()
    entry = EventDLQEntry(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        event_type="payment.generated",
        envelope={},
        failure_reason="timeout",
        attempt_count=1,
        first_failed_at=datetime.now(UTC),
        last_failed_at=datetime.now(UTC),
        dlq_topic="payment.generated",
        status="queued",
    )
    await sink.write(entry)
    assert len(sink.entries) == 1
    assert sink.entries[0].failure_reason == "timeout"


async def test_in_memory_dlq_sink_reset_clears_entries():
    from shared.db.models.events import EventDLQEntry
    sink = InMemoryDLQSink()
    entry = EventDLQEntry(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        event_type="payment.generated",
        envelope={},
        failure_reason="x",
        attempt_count=1,
        first_failed_at=datetime.now(UTC),
        last_failed_at=datetime.now(UTC),
        dlq_topic="payment.generated",
        status="queued",
    )
    await sink.write(entry)
    sink.reset()
    assert sink.entries == []


# ---------------------------------------------------------------------------
# DLQ sink Protocol
# ---------------------------------------------------------------------------


def test_in_memory_dlq_sink_implements_protocol():
    sink = InMemoryDLQSink()
    assert isinstance(sink, DLQSink)


# ---------------------------------------------------------------------------
# ordering_key → shard computation
# ---------------------------------------------------------------------------


def test_ordering_shard_same_key_same_shard():
    from shared.events.rabbitmq_bus import _shard_for_key
    shard1 = _shard_for_key("batch-123", n_shards=8)
    shard2 = _shard_for_key("batch-123", n_shards=8)
    assert shard1 == shard2


def test_ordering_shard_different_keys_can_differ():
    from shared.events.rabbitmq_bus import _shard_for_key
    # With 8 shards, 100 different keys should not all map to the same shard
    shards = {_shard_for_key(f"key-{i}", n_shards=8) for i in range(100)}
    assert len(shards) > 1


def test_ordering_shard_within_bounds():
    from shared.events.rabbitmq_bus import _shard_for_key
    for i in range(50):
        shard = _shard_for_key(f"key-{i}", n_shards=8)
        assert 0 <= shard < 8


def test_ordering_shard_none_key_returns_none():
    from shared.events.rabbitmq_bus import _shard_for_key
    assert _shard_for_key(None, n_shards=8) is None


# ---------------------------------------------------------------------------
# Retry / DLQ logic via retrying wrapper
# ---------------------------------------------------------------------------


async def test_retry_wrapper_success_on_first_call_no_dlq():
    """Handler succeeds on first attempt → no DLQ entry."""
    from shared.events.rabbitmq_bus import RetryingHandler

    sink = InMemoryDLQSink()
    calls: list[EventEnvelope] = []

    async def good_handler(env: EventEnvelope) -> None:
        calls.append(env)

    env = _env()
    handler = RetryingHandler(
        handler=good_handler,
        dlq_sink=sink,
        max_retries=3,
        topic="payment.generated",
    )
    await handler(env)
    assert len(calls) == 1
    assert len(sink.entries) == 0


async def test_retry_wrapper_retries_up_to_max_then_dlq():
    """Handler always fails → retries max_retries times → DLQ entry created."""
    from shared.events.rabbitmq_bus import RetryingHandler

    sink = InMemoryDLQSink()
    call_count = 0

    async def always_fails(env: EventEnvelope) -> None:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("permanent failure")

    env = _env()
    handler = RetryingHandler(
        handler=always_fails,
        dlq_sink=sink,
        max_retries=3,
        topic="payment.generated",
    )
    await handler(env)

    # Attempted max_retries times
    assert call_count == 3
    # DLQ entry written
    assert len(sink.entries) == 1
    dlq_entry = sink.entries[0]
    assert dlq_entry.failure_reason == "permanent failure"
    assert dlq_entry.attempt_count == 3
    assert dlq_entry.dlq_topic == "payment.generated"
    assert dlq_entry.status == "queued"
    # Full envelope preserved
    assert dlq_entry.envelope["event_type"] == env.event_type


async def test_retry_wrapper_success_on_retry_prevents_dlq():
    """Handler fails twice then succeeds → no DLQ entry."""
    from shared.events.rabbitmq_bus import RetryingHandler

    sink = InMemoryDLQSink()
    call_count = 0

    async def flaky(env: EventEnvelope) -> None:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("transient error")

    env = _env()
    handler = RetryingHandler(
        handler=flaky,
        dlq_sink=sink,
        max_retries=3,
        topic="payment.generated",
    )
    await handler(env)

    assert call_count == 3
    assert len(sink.entries) == 0  # no DLQ — eventually succeeded


async def test_dlq_entry_contains_full_envelope():
    """Verify the full wire envelope is stored in the DLQ entry."""
    from shared.events.rabbitmq_bus import RetryingHandler

    sink = InMemoryDLQSink()
    env = _env(ordering_key="batch-789", idempotency_key="custom-idem-key")

    async def always_fails(e: EventEnvelope) -> None:
        raise ValueError("bad message")

    handler = RetryingHandler(
        handler=always_fails,
        dlq_sink=sink,
        max_retries=1,
        topic="payment.generated",
    )
    await handler(env)

    assert len(sink.entries) == 1
    stored_envelope = sink.entries[0].envelope
    assert stored_envelope["ordering_key"] == "batch-789"
    assert stored_envelope["idempotency_key"] == "custom-idem-key"
    assert stored_envelope["event_id"] == str(env.event_id)


# ---------------------------------------------------------------------------
# Ordering: same ordering_key → same shard queue; different keys → parallel
# ---------------------------------------------------------------------------


async def test_ordering_two_events_same_key_processed_in_order():
    """Two events with the same ordering_key should go to the same shard."""
    from shared.events.rabbitmq_bus import _shard_for_key

    ordering_key = "batch-999"
    env1 = _env(ordering_key=ordering_key)
    env2 = _env(ordering_key=ordering_key)

    shard1 = _shard_for_key(env1.ordering_key, n_shards=8)
    shard2 = _shard_for_key(env2.ordering_key, n_shards=8)
    assert shard1 == shard2


async def test_ordering_events_with_no_ordering_key_return_none_shard():
    from shared.events.rabbitmq_bus import _shard_for_key

    env = _env()  # no ordering_key
    assert _shard_for_key(env.ordering_key, n_shards=8) is None


# ---------------------------------------------------------------------------
# InMemoryEventBus integration: publish → handler → verify
# ---------------------------------------------------------------------------


async def test_in_memory_bus_publishes_and_routes():
    """Basic in-memory bus smoke-test to ensure new envelope fields flow through."""
    bus = InMemoryEventBus()
    await bus.start()
    received: list[EventEnvelope] = []

    async def handler(env: EventEnvelope) -> None:
        received.append(env)

    await bus.subscribe(event_types.PAYMENT_GENERATED, handler)
    env = _env(ordering_key="entity-1", idempotency_key="pay:batch-1")
    await bus.publish(env)

    assert len(received) == 1
    assert received[0].ordering_key == "entity-1"
    assert received[0].idempotency_key == "pay:batch-1"
    await bus.stop()


# ---------------------------------------------------------------------------
# RabbitMQ integration test (skipped if broker unavailable)
# ---------------------------------------------------------------------------


@pytest.mark.rabbitmq
async def test_rabbitmq_publish_consume_ack():
    """Publish a message to RabbitMQ, consume it, verify ack via round-trip."""
    import os

    try:
        import aio_pika  # noqa: F401
    except ImportError:
        pytest.skip("aio_pika not installed")

    rabbitmq_url = os.getenv(
        "RABBITMQ_URL", "amqp://infinityrx:infinityrx_dev@localhost:5672/"
    )

    from shared.events.rabbitmq_bus import RabbitMQEventBus

    sink = InMemoryDLQSink()
    bus = RabbitMQEventBus(url=rabbitmq_url, max_retries=3, dlq_sink=sink)

    try:
        await bus.start()
    except Exception:
        pytest.skip("RabbitMQ broker not reachable")

    received: list[EventEnvelope] = []

    async def handler(env: EventEnvelope) -> None:
        received.append(env)

    topic = "test.event_bus_reliability"
    await bus.subscribe(topic, handler)

    env = EventEnvelope(
        event_type=topic,
        tenant_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        source_module="integration-test",
        payload={"test": True},
    )
    await bus.publish(env)
    await asyncio.sleep(0.5)

    await bus.stop()

    assert len(received) == 1
    assert received[0].event_id == env.event_id
