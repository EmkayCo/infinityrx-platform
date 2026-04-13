"""RabbitMQ concrete event bus.

Uses aio-pika with a durable topic exchange.  Every subscriber gets its own
durable queue bound by its topic pattern.  Consumer acknowledges only after
the handler succeeds; failures are retried up to ``max_retries`` times then
routed to a dead-letter exchange AND written to the ``EventDLQEntry`` table
via a ``DLQSink``.

Phase 2 additions
-----------------
- ``dlq_sink`` parameter on the bus and subscribe: persists DLQ entries.
- ``RetryingHandler`` wrapper: handles retry counting and DLQ writes.
  Tested without a broker (pure Python); visible to tests as a public class.
- ``_shard_for_key(ordering_key, n_shards)`` helper: maps an ordering key to
  a consistent shard index so per-entity ordering is preserved.
- ``ordering_key`` support in publish: added to message headers so consumers
  can route to the correct shard queue.

Coverage policy
---------------
The ``RabbitMQEventBus`` class is guarded with ``pragma: no cover`` because
it requires a running broker.  ``RetryingHandler`` and ``_shard_for_key`` are
NOT guarded so their logic is covered by unit tests.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import aio_pika  # type: ignore[import-untyped]

from shared.db.models.events import EventDLQEntry
from shared.events.bus import EventBus, EventHandler
from shared.events.context import current_correlation_id
from shared.events.dlq_sink import DLQSink, InMemoryDLQSink
from shared.events.types import EventEnvelope

if TYPE_CHECKING:
    pass

_logger = logging.getLogger(__name__)

DEFAULT_EXCHANGE = "infinityrx.events"
DEFAULT_DLX = "infinityrx.events.dlx"
DEFAULT_N_SHARDS = 8


def _shard_for_key(ordering_key: str | None, *, n_shards: int = DEFAULT_N_SHARDS) -> int | None:
    """Map *ordering_key* to a consistent shard index in ``[0, n_shards)``.

    Returns ``None`` when *ordering_key* is ``None`` (unordered messages can
    go to any queue).  Uses the first 8 hex digits of the SHA-256 digest so
    distribution is uniform and deterministic.
    """
    if ordering_key is None:
        return None
    digest = hashlib.sha256(ordering_key.encode()).hexdigest()
    return int(digest[:8], 16) % n_shards


class RetryingHandler:
    """Wrap an async handler with retry-then-DLQ semantics.

    This class is intentionally NOT guarded with ``pragma: no cover``; its
    business logic is fully unit-tested without a real broker.

    On each call:
    1. Try the inner handler up to ``max_retries`` times.
    2. On exhaustion: build an ``EventDLQEntry``, write it via ``dlq_sink``,
       and swallow the exception (the caller—on_message—will ack the message).
    3. On success before exhaustion: return normally (caller acks).
    """

    def __init__(
        self,
        *,
        handler: EventHandler,
        dlq_sink: DLQSink | InMemoryDLQSink,
        max_retries: int = 3,
        topic: str,
        n_shards: int = DEFAULT_N_SHARDS,
    ) -> None:
        self._handler = handler
        self._dlq_sink = dlq_sink
        self._max_retries = max_retries
        self._topic = topic
        self._n_shards = n_shards

    async def __call__(self, envelope: EventEnvelope) -> None:
        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                await self._handler(envelope)
                return  # success
            except Exception as exc:
                last_exc = exc
                _logger.warning(
                    "retrying_handler.attempt_failed",
                    extra={
                        "topic": self._topic,
                        "attempt": attempt,
                        "max_retries": self._max_retries,
                        "error": str(exc),
                        "event_id": str(envelope.event_id),
                    },
                )

        # Exhausted retries — write to DLQ
        assert last_exc is not None
        now = datetime.now(UTC)
        entry = EventDLQEntry(
            id=uuid.uuid4(),
            event_id=envelope.event_id,
            tenant_id=envelope.tenant_id,
            event_type=envelope.event_type,
            envelope=envelope.to_wire(),
            failure_reason=str(last_exc),
            attempt_count=self._max_retries,
            first_failed_at=now,
            last_failed_at=now,
            dlq_topic=self._topic,
            status="queued",
        )
        _logger.error(
            "retrying_handler.dead_lettered",
            extra={
                "topic": self._topic,
                "event_id": str(envelope.event_id),
                "failure_reason": str(last_exc),
            },
        )
        await self._dlq_sink.write(entry)


@dataclass
class _Subscription:
    topic_pattern: str
    handler: EventHandler
    queue_name: str


class RabbitMQEventBus(EventBus):  # pragma: no cover - requires running broker
    """Aio-pika topic-exchange event bus with publisher confirms, DLQ, and ordering shards."""

    def __init__(
        self,
        url: str,
        *,
        exchange_name: str = DEFAULT_EXCHANGE,
        dlx_name: str = DEFAULT_DLX,
        max_retries: int = 3,
        dlq_sink: DLQSink | InMemoryDLQSink | None = None,
        n_shards: int = DEFAULT_N_SHARDS,
    ) -> None:
        self._url = url
        self._exchange_name = exchange_name
        self._dlx_name = dlx_name
        self._max_retries = max_retries
        self._dlq_sink: DLQSink | InMemoryDLQSink = dlq_sink or InMemoryDLQSink()
        self._n_shards = n_shards
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractRobustChannel | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None
        self._dlx: aio_pika.abc.AbstractExchange | None = None
        self._subs: list[_Subscription] = []

    async def start(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel(publisher_confirms=True)
        self._exchange = await self._channel.declare_exchange(
            self._exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
        )
        self._dlx = await self._channel.declare_exchange(
            self._dlx_name, aio_pika.ExchangeType.TOPIC, durable=True
        )

    async def stop(self) -> None:
        if self._connection is not None:
            await self._connection.close()
        self._connection = None
        self._channel = None
        self._exchange = None
        self._dlx = None

    async def publish(self, envelope: EventEnvelope) -> None:
        if self._exchange is None:
            raise RuntimeError("RabbitMQEventBus.start() must be called before publish()")
        ctx_cid = current_correlation_id()
        if ctx_cid is not None and envelope.correlation_id != ctx_cid:
            envelope = envelope.model_copy(update={"correlation_id": ctx_cid})

        headers: dict = {"x-source-module": envelope.source_module}
        if envelope.ordering_key is not None:
            headers["x-ordering-key"] = envelope.ordering_key
            shard = _shard_for_key(envelope.ordering_key, n_shards=self._n_shards)
            if shard is not None:
                headers["x-ordering-shard"] = str(shard)

        body = json.dumps(envelope.to_wire()).encode()
        message = aio_pika.Message(
            body=body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            correlation_id=str(envelope.correlation_id),
            headers=headers,
        )
        await self._exchange.publish(message, routing_key=envelope.event_type)

    def _queue_name_for_topic(self, topic_pattern: str, shard: int | None = None) -> str:
        base = f"q.{topic_pattern.replace('*', 'star').replace('.', '_')}"
        if shard is not None:
            return f"{base}.shard{shard}"
        return base

    async def subscribe(self, topic_pattern: str, handler: EventHandler) -> None:
        if self._channel is None or self._exchange is None or self._dlx is None:
            raise RuntimeError("RabbitMQEventBus.start() must be called before subscribe()")

        retrying = RetryingHandler(
            handler=handler,
            dlq_sink=self._dlq_sink,
            max_retries=self._max_retries,
            topic=topic_pattern,
            n_shards=self._n_shards,
        )

        queue_name = self._queue_name_for_topic(topic_pattern)
        dlq_name = f"{queue_name}.dlq"
        await self._channel.declare_queue(
            dlq_name,
            durable=True,
            arguments={"x-dead-letter-exchange": ""},
        )
        queue = await self._channel.declare_queue(
            queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": self._dlx_name,
                "x-dead-letter-routing-key": dlq_name,
            },
        )
        await queue.bind(self._exchange, routing_key=topic_pattern)
        self._subs.append(
            _Subscription(topic_pattern=topic_pattern, handler=handler, queue_name=queue_name)
        )

        async def _on_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
            try:
                envelope = EventEnvelope.from_wire(json.loads(message.body))
                await retrying(envelope)
                await message.ack()
            except Exception as exc:
                _logger.error(
                    "rabbitmq_bus.unhandled_error",
                    extra={"topic": topic_pattern, "error": str(exc)},
                )
                await message.reject(requeue=False)

        await queue.consume(_on_message)
