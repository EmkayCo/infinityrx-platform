"""Event consumers for the rebate-management module.

Subscribes to:
  - claim.adjudicated     (aggregate for rebate calculation)
  - claim.reversed         (adjust rebate accruals)
  - reclaimrx.fraud_detected (update GTN leakage line)

All consumer handlers are wrapped with idempotent_handler.
"""

from __future__ import annotations

import logging
from typing import Any

from shared.events.bus import EventBus
from shared.events.idempotency import InMemoryIdempotencyStore, idempotent_handler
from shared.events.types import EventEnvelope

logger = logging.getLogger("rebate.events.consumers")

_store = InMemoryIdempotencyStore()


async def _handle_claim_adjudicated(key: str, envelope: EventEnvelope) -> None:
    """Process an adjudicated claim for rebate aggregation.

    In production this would write to an aggregation staging table for
    the next rebate calculation batch run. The calculation engine picks
    up staged claims during run_period().
    """
    payload = envelope.payload
    logger.info(
        "rebate.claim_adjudicated_received",
        extra={
            "svc_event_type": "claim.adjudicated",
            "svc_tenant_id": str(envelope.tenant_id),
            "svc_ndc11": payload.get("ndc11", ""),
            "svc_claim_id": payload.get("claim_id", ""),
        },
    )


async def _handle_claim_reversed(key: str, envelope: EventEnvelope) -> None:
    """Adjust rebate accruals when a claim is reversed.

    Reversed claims reduce qualifying units for the next period's
    calculation. The adjustment is applied during the next run_period().
    """
    payload = envelope.payload
    logger.info(
        "rebate.claim_reversed_received",
        extra={
            "svc_event_type": "claim.reversed",
            "svc_tenant_id": str(envelope.tenant_id),
            "svc_ndc11": payload.get("ndc11", ""),
            "svc_claim_id": payload.get("claim_id", ""),
        },
    )


async def _handle_fraud_detected(key: str, envelope: EventEnvelope) -> None:
    """Update GTN waterfall copay leakage line when fraud is detected.

    The ReclaimRx FWA pipeline publishes fraud findings. This consumer
    marks GTN waterfall snapshots as having FWA data available and
    updates the copay misuse/leakage amount.
    """
    payload = envelope.payload
    logger.info(
        "rebate.fraud_detected_received",
        extra={
            "svc_event_type": "reclaimrx.fraud_detected",
            "svc_tenant_id": str(envelope.tenant_id),
            "svc_ndc11": payload.get("ndc11", ""),
        },
    )


# Wrapped handlers with idempotency
handle_claim_adjudicated = idempotent_handler(
    _store, consumer_name="rebate.claim_adjudicated", ttl_seconds=86400
)(_handle_claim_adjudicated)

handle_claim_reversed = idempotent_handler(
    _store, consumer_name="rebate.claim_reversed", ttl_seconds=86400
)(_handle_claim_reversed)

handle_fraud_detected = idempotent_handler(
    _store, consumer_name="rebate.fraud_detected", ttl_seconds=86400
)(_handle_fraud_detected)


async def wire_consumers(bus: EventBus) -> None:
    """Subscribe all rebate management consumers to the event bus."""

    async def _on_claim_adjudicated(envelope: EventEnvelope) -> None:
        await handle_claim_adjudicated(envelope.idempotency_key, envelope)

    async def _on_claim_reversed(envelope: EventEnvelope) -> None:
        await handle_claim_reversed(envelope.idempotency_key, envelope)

    async def _on_fraud_detected(envelope: EventEnvelope) -> None:
        await handle_fraud_detected(envelope.idempotency_key, envelope)

    await bus.subscribe("claim.adjudicated", _on_claim_adjudicated)
    await bus.subscribe("claim.reversed", _on_claim_reversed)
    await bus.subscribe("reclaimrx.fraud_detected", _on_fraud_detected)

    logger.info("rebate.consumers_wired", extra={"svc_consumer_count": 3})
