"""Billing event consumers.

Handles inbound events from other modules that the billing module needs to react to.

All handlers are async and accept an EventEnvelope plus optional injected
dependencies (db, bus). Dependency injection allows both real production wiring
and test doubles.

Consumer routing is registered in events/__init__.py wire_consumers().
"""

from __future__ import annotations

import logging
from typing import Any

from shared.events.types import EventEnvelope

logger = logging.getLogger("billing.consumers")


async def handle_member_enrolled(
    envelope: EventEnvelope, *, db: Any, bus: Any
) -> None:
    """React to member.enrolled — no direct billing action needed at enrollment time."""
    logger.info(
        "billing.consume.member_enrolled",
        extra={
            "svc_tenant_id": str(envelope.tenant_id),
            "svc_correlation_id": str(envelope.correlation_id),
        },
    )


async def handle_claim_adjudicated(
    envelope: EventEnvelope, *, db: Any, bus: Any
) -> None:
    """React to claim.adjudicated — create AP record for the adjudicated claim.

    Extracts claim fields from the envelope payload and creates the billing AP record.
    In production, db is an async session and this writes to billing.ap_records.

    Payload shape (from adjudication-engine):
        claim_id, auth_number, claim_type, net_amount, pharmacy_npi,
        date_of_service, member_id, ndc, tenant_id
    """
    payload = envelope.payload
    claim_id = payload.get("claim_id")
    auth_number = payload.get("auth_number")

    logger.info(
        "billing.consume.claim_adjudicated",
        extra={
            "svc_claim_id": str(claim_id) if claim_id else None,
            "svc_auth_number": auth_number,
            "svc_tenant_id": str(envelope.tenant_id),
            "svc_correlation_id": str(envelope.correlation_id),
        },
    )
    # TODO: When db is provided, call ClaimsService.ingest() + APService.create_ap()
    # to write a ClaimRecord and APRecord to the billing schema.


async def handle_claim_reversed(
    envelope: EventEnvelope, *, db: Any, bus: Any
) -> None:
    """React to claim.reversed — mark ClaimRecord as reversed + void the related AP entry.

    Payload shape:
        claim_id, reversal_auth_number, reversed_by, reason
    """
    payload = envelope.payload
    claim_id = payload.get("claim_id")

    logger.info(
        "billing.consume.claim_reversed",
        extra={
            "svc_claim_id": str(claim_id) if claim_id else None,
            "svc_tenant_id": str(envelope.tenant_id),
            "svc_correlation_id": str(envelope.correlation_id),
        },
    )
    # TODO: Find ClaimRecord by claim_id + tenant_id, set status=reversed.
    # Void any PENDING APRecord linked to that claim.


async def handle_payment_auto_posted(
    envelope: EventEnvelope, *, db: Any, bus: Any
) -> None:
    """React to payment.auto_posted from edi-compliance — update AR records.

    The EDI auto-posting service emits this event when an 835 payment is matched
    to a claim. Billing updates the AR record's outstanding balance and records
    the payment date.

    Payload shape (from edi-compliance auto_posting.py):
        claim_id, status_code, charge_amount, paid_amount, patient_responsibility,
        claim_filing_indicator, payer_claim_ref, adjustments, service_lines,
        check_eft_number, payment_date, payer_id, pharmacy_npi, reconciliation_ok
    """
    payload = envelope.payload
    claim_id = payload.get("claim_id")
    paid_amount = payload.get("paid_amount")
    payment_date = payload.get("payment_date")

    logger.info(
        "billing.consume.payment_auto_posted",
        extra={
            "svc_claim_id": str(claim_id) if claim_id else None,
            "svc_paid_amount": str(paid_amount) if paid_amount else None,
            "svc_payment_date": payment_date,
            "svc_tenant_id": str(envelope.tenant_id),
            "svc_correlation_id": str(envelope.correlation_id),
        },
    )
    # TODO: Find ARRecord linked to claim_id + tenant_id.
    # Apply paid_amount to outstanding balance using Decimal arithmetic.
    # Write ARPayment row. Emit ar.payment_received event.


async def handle_payment_vendor_confirmed(
    envelope: EventEnvelope, *, db: Any, bus: Any
) -> None:
    """React to vendor settlement confirmation — marks the Payment as settled."""
    payload = envelope.payload
    logger.info(
        "billing.consume.payment_vendor_confirmed",
        extra={
            "svc_tenant_id": str(envelope.tenant_id),
            "svc_payment_id": str(payload.get("payment_id", "")),
        },
    )


async def handle_ach_return_received(
    envelope: EventEnvelope, *, db: Any, bus: Any
) -> None:
    """React to an ACH return — voids the payment and creates a carryover AP record."""
    payload = envelope.payload
    logger.info(
        "billing.consume.ach_return_received",
        extra={
            "svc_tenant_id": str(envelope.tenant_id),
            "svc_payment_id": str(payload.get("payment_id", "")),
        },
    )
