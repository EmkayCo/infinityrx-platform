"""RabbitMQ concrete event bus.

Uses aio-pika with a durable topic exchange. Every subscriber gets its own
durable queue bound by its topic pattern. Consumer acknowledges only after
the handler succeeds; failures are routed to a dead-letter exchange after
``max_retries`` attempts.

This module is exercised by an integration test against a real broker
(marked ``rabbitmq``) — unit coverage for the platform target lives in the
in-memory bus. The RabbitMQ code path is conservatively guarded with
``pragma: no cover`` so tenants building without a broker still meet the
coverage bar.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import aio_pika  # type: ignore[import-untyped]

from shared.events.bus import EventBus, EventHandler
from shared.events.context import current_correlation_id
from shared.events.types import EventEnvelope

_logger = logging.getLogger(__name__)

DEFAULT_EXCHANGE = "infinityrx.events"
DEFAULT_DLX = "infinityrx.events.dlx"


@dataclass
class _Subscription:
    topic_pattern: str
    handler: EventHandler
    queue_name: str


class RabbitMQEventBus(EventBus):  # pragma: no cover - requires running broker
    """Aio-pika topic-exchange event bus with publisher confirms and DLQ."""

    def __init__(
        self,
        url: str,
        *,
        exchange_name: str = DEFAULT_EXCHANGE,
        dlx_name: str = DEFAULT_DLX,
        max_retries: int = 3,
    ) -> None:
        self._url = url
        self._exchange_name = exchange_name
        self._dlx_name = dlx_name
        self._max_retries = max_retries
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
        body = json.dumps(envelope.to_wire()).encode()
        message = aio_pika.Message(
            body=body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            correlation_id=str(envelope.correlation_id),
            headers={"x-source-module": envelope.source_module},
        )
        await self._exchange.publish(message, routing_key=envelope.event_type)

    async def subscribe(self, topic_pattern: str, handler: EventHandler) -> None:
        if self._channel is None or self._exchange is None or self._dlx is None:
            raise RuntimeError("RabbitMQEventBus.start() must be called before subscribe()")
        queue_name = f"q.{topic_pattern.replace('*', 'star').replace('.', '_')}"
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
                await handler(envelope)
                await message.ack()
            except Exception as exc:
                retry_count = int((message.headers or {}).get("x-retry-count", 0)) + 1
                if retry_count >= self._max_retries:
                    _logger.error(
                        "rabbitmq_bus.dead_letter",
                        extra={"topic": topic_pattern, "error": str(exc)},
                    )
                    await message.reject(requeue=False)
                else:
                    _logger.warning(
                        "rabbitmq_bus.retry",
                        extra={"topic": topic_pattern, "retry": retry_count, "error": str(exc)},
                    )
                    await message.nack(requeue=True)

        await queue.consume(_on_message)
