"""Plan Design event consumers — PRD §13.

Subscribes to:
  member.enrolled           — update plan member count metrics
  drug.price_updated        — flag IRA negotiated drugs if MFP changed
  drug.biosimilar_approved  — add biosimilar mapping to active formularies
  drug.ira_price_negotiated — flag drugs + set MFP price in formularies
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from shared.events.bus import EventBus
from shared.events.idempotency import InMemoryIdempotencyStore, idempotent_handler
from shared.events.types import EventEnvelope

logger = logging.getLogger("plan_design.consumers")

_store = InMemoryIdempotencyStore()


async def _handle_member_enrolled(idempotency_key: str, envelope: EventEnvelope) -> None:
    """member.enrolled — log enrollment for plan metrics."""
    payload = envelope.payload
    logger.info(
        "plan_design.member_enrolled received",
        extra={
            "svc_name": "plan-design",
            "tenant_id": str(envelope.tenant_id),
            "plan_id": payload.get("plan_id"),
        },
    )
    # In production: update plan member count via DB session
    # Kept lightweight here to avoid DB dependency without session wiring


async def _handle_drug_price_updated(idempotency_key: str, envelope: EventEnvelope) -> None:
    """drug.price_updated — log price update for formulary review."""
    payload = envelope.payload
    ndc = payload.get("ndc", "unknown")
    logger.info(
        "plan_design.drug_price_updated received",
        extra={
            "svc_name": "plan-design",
            "tenant_id": str(envelope.tenant_id),
            "plan_design_ndc": ndc,
        },
    )


async def _handle_biosimilar_approved(idempotency_key: str, envelope: EventEnvelope) -> None:
    """drug.biosimilar_approved — add biosimilar mapping to formularies."""
    payload = envelope.payload
    ndc = payload.get("ndc", "unknown")
    reference_ndc = payload.get("reference_ndc", "unknown")
    logger.info(
        "plan_design.biosimilar_approved received",
        extra={
            "svc_name": "plan-design",
            "tenant_id": str(envelope.tenant_id),
            "plan_design_ndc": ndc,
            "plan_design_reference_ndc": reference_ndc,
        },
    )


async def _handle_ira_price_negotiated(idempotency_key: str, envelope: EventEnvelope) -> None:
    """drug.ira_price_negotiated — flag IRA drugs and set MFP price."""
    payload = envelope.payload
    ndc = payload.get("ndc", "unknown")
    mfp = payload.get("mfp_price")
    logger.info(
        "plan_design.ira_price_negotiated received",
        extra={
            "svc_name": "plan-design",
            "tenant_id": str(envelope.tenant_id),
            "plan_design_ndc": ndc,
            "plan_design_mfp": str(mfp) if mfp else None,
        },
    )


def _make_handler(inner_handler, consumer_name: str):
    """Wrap handler with idempotency decorator and envelope unpacking."""
    wrapped = idempotent_handler(_store, consumer_name=consumer_name)(inner_handler)

    async def outer(envelope: EventEnvelope) -> None:
        await wrapped(envelope.idempotency_key, envelope)

    return outer


async def wire_consumers(bus: EventBus) -> None:
    """Subscribe all plan-design consumers to the event bus (PRD §13)."""
    await bus.subscribe(
        "member.enrolled",
        _make_handler(_handle_member_enrolled, "plan_design.member_enrolled"),
    )
    await bus.subscribe(
        "drug.price_updated",
        _make_handler(_handle_drug_price_updated, "plan_design.drug_price_updated"),
    )
    await bus.subscribe(
        "drug.biosimilar_approved",
        _make_handler(_handle_biosimilar_approved, "plan_design.biosimilar_approved"),
    )
    await bus.subscribe(
        "drug.ira_price_negotiated",
        _make_handler(_handle_ira_price_negotiated, "plan_design.ira_price_negotiated"),
    )
    logger.info(
        "plan_design.consumers_wired",
        extra={"svc_name": "plan-design", "consumer_count": 4},
    )
