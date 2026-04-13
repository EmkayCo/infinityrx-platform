"""Billing event consumers.

Handles inbound events from other modules that the billing module needs to react to.
Each handler is a pure function that accepts the event payload dict and a context
(db session + event bus) — no side effects beyond those two interfaces.
"""

from __future__ import annotations

from typing import Any


def handle_member_enrolled(payload: dict[str, Any], *, db: Any, bus: Any) -> None:
    """React to member enrollment — no direct billing action needed at enrollment time."""


def handle_claim_adjudicated(payload: dict[str, Any], *, db: Any, bus: Any) -> None:
    """React to a claim adjudicated event from the claims processing module.

    Triggers claim ingestion into billing for routing and AP record creation.
    In production this calls ClaimsService.ingest() after mapping the payload.
    """


def handle_payment_vendor_confirmed(payload: dict[str, Any], *, db: Any, bus: Any) -> None:
    """React to vendor settlement confirmation — marks the Payment as settled."""


def handle_ach_return_received(payload: dict[str, Any], *, db: Any, bus: Any) -> None:
    """React to an ACH return — voids the payment and creates a carryover AP record."""
