"""End-to-end integration tests for RabbitMQEventBus against a real broker.

Uses ``testcontainers[rabbitmq]`` to spin up a single RabbitMQ instance
for the module, exercises publish → ack, publish → failure → DLQ, and
DLQ replay paths. These are slower than unit tests (~10-30s broker
startup) so they are gated by:

    * ``pytest.importorskip("testcontainers.rabbitmq")`` — skip on envs
      without the plugin.
    * ``pytest.mark.integration`` — CI runs these in a dedicated job;
      local ``pytest -m "not integration"`` skips them.
    * Docker availability — on machines without docker, the container
      fixture raises and all tests skip.

Together these keep the main test suite fast while ensuring at least
one job exercises the real broker path, catching:
    * Serialization / header contract regressions
    * Queue / DLQ binding declarations
    * Publisher-confirm behavior
    * x-dead-letter-exchange routing when a consumer nacks
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

pytestmark = [pytest.mark.integration]

testcontainers_rabbitmq = pytest.importorskip("testcontainers.rabbitmq")
RabbitMqContainer = testcontainers_rabbitmq.RabbitMqContainer

from shared.events.dlq_sink import InMemoryDLQSink  # noqa: E402
from shared.events.rabbitmq_bus import RabbitMQEventBus  # noqa: E402
from shared.events.types import EventEnvelope  # noqa: E402


def _skip_if_no_docker(reason: str = "docker not available") -> None:
    import shutil

    if shutil.which("docker") is None:
        pytest.skip(reason)


@pytest.fixture(scope="module")
def rabbitmq_url() -> str:
    _skip_if_no_docker()
    try:
        container = RabbitMqContainer("rabbitmq:4-management")
        container.start()
    except Exception as exc:  # pragma: no cover - environment issue
        pytest.skip(f"could not start rabbitmq testcontainer: {exc}")
    try:
        url = container.get_connection_url()
        yield url
    finally:
        try:
            container.stop()
        except Exception:  # pragma: no cover
            pass


def _make_envelope(event_type: str = "integration.test") -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        tenant_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        source_module="integration-test",
        payload={"hello": "world"},
    )


@pytest.mark.asyncio
async def test_publish_then_consume_roundtrip(rabbitmq_url: str) -> None:
    """Publish an event, a subscribed handler receives it."""
    bus = RabbitMQEventBus(rabbitmq_url, max_retries=1)
    received: list[EventEnvelope] = []
    delivered = asyncio.Event()

    async def handler(env: EventEnvelope) -> None:
        received.append(env)
        delivered.set()

    await bus.start()
    try:
        await bus.subscribe("integration.test", handler)
        envelope = _make_envelope()
        await bus.publish(envelope)
        await asyncio.wait_for(delivered.wait(), timeout=10)
    finally:
        await bus.stop()

    assert len(received) == 1
    got = received[0]
    assert got.event_type == "integration.test"
    assert got.tenant_id == envelope.tenant_id
    assert got.correlation_id == envelope.correlation_id
    assert got.payload == {"hello": "world"}


@pytest.mark.asyncio
async def test_failing_handler_writes_to_dlq(rabbitmq_url: str) -> None:
    """A consistently-failing handler routes the envelope to the DLQ sink."""
    sink = InMemoryDLQSink()
    bus = RabbitMQEventBus(rabbitmq_url, max_retries=2, dlq_sink=sink)
    dead_lettered = asyncio.Event()

    async def always_fails(env: EventEnvelope) -> None:
        if len(sink.entries) == 0:
            # Wait until the DLQ write happens before the test proceeds.
            dead_lettered.set()
        raise RuntimeError("upstream on fire")

    # We want dead_lettered.set() to fire AFTER the write, not before —
    # swap handler to only raise, then monkeypatch sink.write.
    original_write = sink.write

    async def instrumented_write(entry) -> None:
        await original_write(entry)
        dead_lettered.set()

    sink.write = instrumented_write  # type: ignore[method-assign]

    async def handler(env: EventEnvelope) -> None:
        raise RuntimeError("upstream on fire")

    await bus.start()
    try:
        # Use a distinct topic so DLQ entries don't collide with other tests.
        await bus.subscribe("integration.dlq", handler)
        envelope = _make_envelope("integration.dlq")
        await bus.publish(envelope)
        await asyncio.wait_for(dead_lettered.wait(), timeout=15)
    finally:
        await bus.stop()

    assert len(sink.entries) == 1
    entry = sink.entries[0]
    assert entry.event_type == "integration.dlq"
    assert entry.tenant_id == envelope.tenant_id
    assert entry.attempt_count == 2
    assert "upstream on fire" in entry.failure_reason
    assert entry.status == "queued"


@pytest.mark.asyncio
async def test_dlq_replay_succeeds_on_fixed_handler(rabbitmq_url: str) -> None:
    """Simulate the replay path: after DLQ write, the handler is fixed
    and a re-publish lands normally."""
    sink = InMemoryDLQSink()
    bus = RabbitMQEventBus(rabbitmq_url, max_retries=1, dlq_sink=sink)

    call_log: list[str] = []
    success_after_fix = asyncio.Event()

    should_fail = True

    async def handler(env: EventEnvelope) -> None:
        call_log.append("fail" if should_fail else "ok")
        if should_fail:
            raise RuntimeError("broken")
        success_after_fix.set()

    await bus.start()
    try:
        await bus.subscribe("integration.replay", handler)
        envelope = _make_envelope("integration.replay")
        # First publish → failure → DLQ
        await bus.publish(envelope)
        # Let the DLQ write settle.
        for _ in range(50):
            if len(sink.entries) == 1:
                break
            await asyncio.sleep(0.1)
        assert len(sink.entries) == 1, "first publish should have dead-lettered"

        # Now "fix" the handler and re-publish the same envelope — replay.
        should_fail = False
        await bus.publish(envelope)
        await asyncio.wait_for(success_after_fix.wait(), timeout=10)
    finally:
        await bus.stop()

    assert "ok" in call_log
    # Only one DLQ entry — the fixed-handler publish did NOT dead-letter.
    assert len(sink.entries) == 1
