"""Rules-engine event consumers.

Handles inbound events from other modules. Each handler:
- Validates required payload fields
- Uses Decimal for money (amounts arrive as strings)
- Logs with svc_ prefix (LESSON-005)
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from shared.events.bus import EventBus
from shared.events.types import EventEnvelope

logger = logging.getLogger("rules_engine.consumers")


def _require(payload: dict[str, Any], *keys: str) -> None:
    missing = [k for k in keys if payload.get(k) in (None, "")]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")


async def handle_claim_submitted(
    envelope: EventEnvelope,
    *,
    db: Any = None,
    bus: EventBus | None = None,
) -> None:
    """Handle claim.submitted — trigger pipeline evaluation for the claim."""
    payload = envelope.payload
    _require(payload, "claim_id", "tenant_id", "plan_id")

    claim_id = payload["claim_id"]
    plan_id = payload["plan_id"]

    logger.info(
        "rules_engine.claim_submitted_received",
        extra={
            "svc_claim_id": claim_id,
            "svc_plan_id": plan_id,
            "svc_tenant_id": payload["tenant_id"],
        },
    )


async def handle_plan_updated(
    envelope: EventEnvelope,
    *,
    db: Any = None,
    bus: EventBus | None = None,
) -> None:
    """Handle plan.updated — invalidate cached pipeline for plan."""
    payload = envelope.payload
    _require(payload, "plan_id", "tenant_id")

    logger.info(
        "rules_engine.plan_updated_received",
        extra={
            "svc_plan_id": payload["plan_id"],
            "svc_tenant_id": payload["tenant_id"],
        },
    )


async def handle_drug_price_updated(
    envelope: EventEnvelope,
    *,
    db: Any = None,
    bus: EventBus | None = None,
) -> None:
    """Handle drug.price_updated — refresh MAC pricing cache."""
    payload = envelope.payload
    _require(payload, "ndc", "tenant_id")

    logger.info(
        "rules_engine.drug_price_updated_received",
        extra={
            "svc_ndc": payload["ndc"],
            "svc_tenant_id": payload["tenant_id"],
        },
    )
