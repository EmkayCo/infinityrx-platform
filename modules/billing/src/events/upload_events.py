"""SP-1 Plan B Task 3b — paysync.upload.parsed event.

Publisher:   publish_upload_parsed (async, called from parse_upload service)
Consumer:    handle_upload_parsed  — cache invalidation handler

Event contract: docs/api-contracts/events/paysync.upload.parsed.md

EventEnvelope fields (all required per shared/events/types.py:20):
  event_type      = "paysync.upload.parsed"
  tenant_id       = upload.tenant_id
  correlation_id  = caller-supplied
  source_module   = "billing"
  ordering_key    = str(upload.id)
  idempotency_key = "paysync:upload:{upload.id}:parsed"
  schema_version  = "1.0"
  payload         = {upload_id, tenant_id, status, row_count, error_count}

Consumer invalidates Redis keys matching:
  paysync:inbox:list:{tenant_id}:*

Forward-compat: consumer ignores unknown payload fields.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from shared.events.bus import EventBus
from shared.events.types import EventEnvelope

logger = logging.getLogger("billing.events.upload")


def _get_redis() -> Any:
    """Return a Redis client.  Lazy import so tests can patch easily."""
    try:
        import redis  # type: ignore[import]
        url = __import__("os").getenv("REDIS_URL", "redis://localhost:6379/0")
        return redis.from_url(url, decode_responses=True)
    except Exception:  # pragma: no cover
        return None


async def publish_upload_parsed(
    bus: EventBus,
    *,
    upload: Any,
    correlation_id: uuid.UUID,
) -> None:
    """Publish paysync.upload.parsed after parse_upload completes (async, R3.2)."""
    envelope = EventEnvelope(
        event_type="paysync.upload.parsed",
        tenant_id=upload.tenant_id,
        correlation_id=correlation_id,
        source_module="billing",
        payload={
            "upload_id": str(upload.id),
            "tenant_id": str(upload.tenant_id),
            "status": upload.status,
            "row_count": upload.row_count,
            "error_count": upload.error_count,
        },
        ordering_key=str(upload.id),
        idempotency_key=f"paysync:upload:{upload.id}:parsed",
        schema_version="1.0",
    )
    await bus.publish(envelope)


async def handle_upload_parsed(envelope: EventEnvelope, **_: object) -> None:
    """Invalidate inbox cache when an upload finishes parsing.

    Forward-compat: unknown payload fields are silently ignored.
    Idempotency: handled by _make_wrapper in events/__init__.py (B5).
    Extra kwargs (db, bus) from _make_wrapper are accepted and ignored.
    """
    tenant_id = envelope.payload.get("tenant_id") or str(envelope.tenant_id)
    redis_client = _get_redis()
    if redis_client is None:  # pragma: no cover
        logger.warning("billing.upload_consumer.redis_unavailable")
        return

    pattern = f"tenant:{tenant_id}:paysync:inbox:list:*"
    keys = list(redis_client.scan_iter(pattern))
    if keys:
        redis_client.delete(*keys)
        logger.info(
            "billing.upload_consumer.cache_invalidated",
            extra={
                "svc_tenant_id": tenant_id,
                "svc_key_count": len(keys),
            },
        )
