"""DataIQ event consumers.

Consumes events from other modules to update Redis KPI counters in real-time.
Consumers increment counters via INCRBY (never from API handlers).

Consumed events:
  claim.ingested, claim.classified  — update claim volume counters
  payment.settled                   — update payment counters
  fwa.claim_flagged                 — update FWA counters
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any

from shared.events.idempotency import InMemoryIdempotencyStore, idempotent_handler
from shared.events.types import EventEnvelope
from src.services.kpi import KPIGranularity, increment_counter, increment_financial_counter

logger = logging.getLogger("dataiq.consumers")


def _current_minute_bucket() -> int:
    return int(time.time()) // 60 * 60


def _current_hour_bucket() -> int:
    return int(time.time()) // 3600 * 3600


def _current_day_bucket() -> int:
    return int(time.time()) // 86400 * 86400


def make_claim_ingested_handler(
    redis: Any,
    store: InMemoryIdempotencyStore | None = None,
) -> Any:
    """Return an idempotent handler for claim.ingested events.

    The returned function signature: handler(idempotency_key, envelope).
    The idempotent_handler decorator uses the first arg as the dedup key.
    """
    _store = store or InMemoryIdempotencyStore()

    @idempotent_handler(_store, consumer_name="dataiq.claim_ingested")
    async def handle_claim_ingested(idempotency_key: str, envelope: EventEnvelope) -> None:
        tenant_id = envelope.tenant_id
        bucket_minute = _current_minute_bucket()
        bucket_hour = _current_hour_bucket()
        bucket_day = _current_day_bucket()

        await increment_counter(
            redis=redis,
            tenant_id=tenant_id,
            metric="claim_count",
            bucket_ts=bucket_minute,
            amount=1,
            granularity=KPIGranularity.MINUTE,
        )
        await increment_counter(
            redis=redis,
            tenant_id=tenant_id,
            metric="claim_count",
            bucket_ts=bucket_hour,
            amount=1,
            granularity=KPIGranularity.HOUR,
        )
        await increment_counter(
            redis=redis,
            tenant_id=tenant_id,
            metric="claim_count",
            bucket_ts=bucket_day,
            amount=1,
            granularity=KPIGranularity.DAY,
        )

        payload = envelope.payload
        if "amount" in payload:
            amount = Decimal(payload["amount"])
            await increment_financial_counter(
                redis=redis,
                tenant_id=tenant_id,
                metric="total_spend",
                bucket_ts=bucket_hour,
                amount=amount,
                granularity=KPIGranularity.HOUR,
            )

        logger.info(
            "claim_ingested_kpi_updated",
            extra={
                "svc_tenant_id": str(tenant_id),
                "svc_event_id": str(envelope.event_id),
            },
        )

    return handle_claim_ingested


def make_fwa_flagged_handler(
    redis: Any,
    store: InMemoryIdempotencyStore | None = None,
) -> Any:
    """Return an idempotent handler for fwa.claim_flagged events."""
    _store = store or InMemoryIdempotencyStore()

    @idempotent_handler(_store, consumer_name="dataiq.fwa_flagged")
    async def handle_fwa_flagged(idempotency_key: str, envelope: EventEnvelope) -> None:
        tenant_id = envelope.tenant_id
        bucket_hour = _current_hour_bucket()

        await increment_counter(
            redis=redis,
            tenant_id=tenant_id,
            metric="fwa_flag_count",
            bucket_ts=bucket_hour,
            amount=1,
            granularity=KPIGranularity.HOUR,
        )

        logger.info(
            "fwa_flagged_kpi_updated",
            extra={
                "svc_tenant_id": str(tenant_id),
                "svc_event_id": str(envelope.event_id),
            },
        )

    return handle_fwa_flagged


def make_payment_settled_handler(
    redis: Any,
    store: InMemoryIdempotencyStore | None = None,
) -> Any:
    """Return an idempotent handler for payment.settled events."""
    _store = store or InMemoryIdempotencyStore()

    @idempotent_handler(_store, consumer_name="dataiq.payment_settled")
    async def handle_payment_settled(idempotency_key: str, envelope: EventEnvelope) -> None:
        tenant_id = envelope.tenant_id
        bucket_hour = _current_hour_bucket()

        payload = envelope.payload
        if "amount" in payload:
            amount = Decimal(payload["amount"])
            await increment_financial_counter(
                redis=redis,
                tenant_id=tenant_id,
                metric="payments_settled",
                bucket_ts=bucket_hour,
                amount=amount,
                granularity=KPIGranularity.HOUR,
            )

        logger.info(
            "payment_settled_kpi_updated",
            extra={
                "svc_tenant_id": str(tenant_id),
                "svc_event_id": str(envelope.event_id),
            },
        )

    return handle_payment_settled
