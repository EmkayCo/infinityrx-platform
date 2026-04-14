"""Payment-processing event consumers.

Handles:
- payment_batch.submitted  → trigger file generation and submission
- fwa.payment_hold_placed  → hold payments for entity
- fwa.payment_hold_released → release hold
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from ..utils.constants import (
    EVENT_FWA_HOLD_PLACED,
    EVENT_FWA_HOLD_RELEASED,
    EVENT_PAYMENT_BATCH_SUBMITTED,
)

logger = logging.getLogger("payment.consumers")

# Registry: topic -> handler function
_HANDLERS: dict[str, Callable[[dict[str, Any]], None]] = {}


def register_handler(topic: str, handler: Callable[[dict[str, Any]], None]) -> None:
    _HANDLERS[topic] = handler


def dispatch(topic: str, payload: dict[str, Any]) -> None:
    """Route an incoming event to the registered handler."""
    handler = _HANDLERS.get(topic)
    if handler is None:
        logger.debug("No handler registered for topic %s", topic)
        return
    try:
        handler(payload)
    except Exception:
        logger.exception("Error handling event %s: %s", topic, payload)
        raise


def handle_payment_batch_submitted(payload: dict[str, Any]) -> None:
    """Consume payment_batch.submitted from Billing.

    Real implementation: look up vendor adapter, build instructions from payload,
    call SubmissionService.submit_batch(). Here we log the intent for contract testing.
    """
    logger.info(
        "payment_batch.submitted received: batch=%s tenant=%s",
        payload.get("batch_id"),
        payload.get("tenant_id"),
    )


def handle_fwa_hold_placed(payload: dict[str, Any]) -> None:
    """Consume fwa.payment_hold_placed from ReclaimRx."""
    logger.info(
        "fwa.payment_hold_placed: entity=%s tenant=%s reason=%s",
        payload.get("entity_id"),
        payload.get("tenant_id"),
        payload.get("reason"),
    )


def handle_fwa_hold_released(payload: dict[str, Any]) -> None:
    """Consume fwa.payment_hold_released from ReclaimRx."""
    logger.info(
        "fwa.payment_hold_released: entity=%s tenant=%s",
        payload.get("entity_id"),
        payload.get("tenant_id"),
    )


# Auto-register handlers
register_handler(EVENT_PAYMENT_BATCH_SUBMITTED, handle_payment_batch_submitted)
register_handler(EVENT_FWA_HOLD_PLACED, handle_fwa_hold_placed)
register_handler(EVENT_FWA_HOLD_RELEASED, handle_fwa_hold_released)
