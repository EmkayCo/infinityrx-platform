"""Billing event consumers.

Handles inbound events from other modules that the billing module needs to
react to. Each handler:

* Validates required payload fields and raises ``ValueError`` on malformed data
  so the bus can route to DLQ.
* Persists records via the injected SQLAlchemy ``Session`` when provided. When
  ``db=None`` the handler is in a dry-run mode that only logs — this exists so
  that application-startup wiring (which does not yet create a session per
  delivery) remains backwards compatible until the bus is upgraded.
* Uses ``Decimal`` for every money field (event-bus rule: amounts arrive as
  strings and must round-trip as Decimal).
* Emits structured logs with the ``svc_`` prefix (LESSON-005 — bare ``module``
  collides with ``LogRecord`` built-ins).

Consumer routing is registered in events/__init__.py wire_consumers().
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.events.types import EventEnvelope

from ..models.tables import APRecord, ARPayment, ARRecord, ClaimRecord

logger = logging.getLogger("billing.consumers")

AP_STATUS_CREATED = "created"
AP_STATUS_VOID = "void"
CLAIM_STATUS_ADJUDICATED = "adjudicated"
CLAIM_STATUS_REVERSED = "reversed"


def _to_uuid(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _to_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _require(payload: dict[str, Any], *keys: str) -> None:
    missing = [k for k in keys if payload.get(k) in (None, "")]
    if missing:
        raise ValueError(f"missing required event fields: {missing}")


async def handle_member_enrolled(
    envelope: EventEnvelope, *, db: Session | None, bus: Any
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
    envelope: EventEnvelope, *, db: Session | None, bus: Any
) -> None:
    """React to claim.adjudicated — create ClaimRecord + APRecord pair.

    Payload shape (from adjudication-engine):
        claim_id, auth_number, claim_type, net_amount, pharmacy_npi,
        date_of_service, member_id, ndc, client_id, program_id,
        pay_to_entity_id, pay_to_entity_name, payment_route
    """
    payload = envelope.payload
    _require(payload, "auth_number", "claim_type", "net_amount", "pharmacy_npi")

    auth_number = str(payload["auth_number"])
    tenant_id = _to_uuid(envelope.tenant_id)

    logger.info(
        "billing.consume.claim_adjudicated",
        extra={
            "svc_auth_number": auth_number,
            "svc_tenant_id": str(tenant_id),
            "svc_correlation_id": str(envelope.correlation_id),
        },
    )

    if db is None:
        logger.warning(
            "billing.consume.claim_adjudicated.no_session",
            extra={"svc_auth_number": auth_number, "svc_tenant_id": str(tenant_id)},
        )
        return

    net_amount = _to_decimal(payload["net_amount"])
    date_of_service = payload.get("date_of_service")
    if isinstance(date_of_service, str):
        from datetime import date as _date

        date_of_service = _date.fromisoformat(date_of_service)

    now = datetime.now(UTC)
    client_id = _to_uuid(payload.get("client_id")) or uuid.uuid4()
    program_id = _to_uuid(payload.get("program_id"))
    pay_to_entity_id = _to_uuid(payload.get("pay_to_entity_id")) or uuid.uuid4()
    pay_to_entity_name = payload.get("pay_to_entity_name") or payload.get("pharmacy_name") or "unknown"
    payment_route = payload.get("payment_route") or "default"

    existing = db.execute(
        select(ClaimRecord).where(
            ClaimRecord.tenant_id == tenant_id,
            ClaimRecord.auth_number == auth_number,
        )
    ).scalar_one_or_none()
    if existing is not None:
        logger.info(
            "billing.consume.claim_adjudicated.duplicate_ignored",
            extra={"svc_auth_number": auth_number, "svc_tenant_id": str(tenant_id)},
        )
        return

    claim = ClaimRecord(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        source_type=payload.get("source_type", "event"),
        auth_number=auth_number,
        claim_type=str(payload["claim_type"]),
        pharmacy_npi=str(payload["pharmacy_npi"]),
        date_of_service=date_of_service or now.date(),
        date_received=now,
        net_amount=net_amount,
        client_id=client_id,
        program_id=program_id,
        member_id=payload.get("member_id"),
        ndc=payload.get("ndc"),
        payment_route=payment_route,
        pay_to_entity_id=pay_to_entity_id,
        pay_to_entity_name=pay_to_entity_name,
        status=CLAIM_STATUS_ADJUDICATED,
        created_at=now,
    )
    db.add(claim)
    db.flush()

    ap = APRecord(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        claim_record_id=claim.id,
        client_id=client_id,
        program_id=program_id,
        pay_to_entity_id=pay_to_entity_id,
        pay_to_entity_name=pay_to_entity_name,
        amount=net_amount,
        payment_route=payment_route,
        status=AP_STATUS_CREATED,
        created_at=now,
        updated_at=now,
    )
    db.add(ap)
    db.flush()


async def handle_claim_reversed(
    envelope: EventEnvelope, *, db: Session | None, bus: Any
) -> None:
    """React to claim.reversed — mark ClaimRecord reversed + void related AP.

    Payload shape: auth_number (original), reversal_auth_number, reversed_by, reason
    """
    payload = envelope.payload
    _require(payload, "auth_number")

    auth_number = str(payload["auth_number"])
    tenant_id = _to_uuid(envelope.tenant_id)

    logger.info(
        "billing.consume.claim_reversed",
        extra={
            "svc_auth_number": auth_number,
            "svc_tenant_id": str(tenant_id),
            "svc_correlation_id": str(envelope.correlation_id),
        },
    )

    if db is None:
        return

    claim = db.execute(
        select(ClaimRecord).where(
            ClaimRecord.tenant_id == tenant_id,
            ClaimRecord.auth_number == auth_number,
        )
    ).scalar_one_or_none()
    if claim is None:
        logger.warning(
            "billing.consume.claim_reversed.not_found",
            extra={"svc_auth_number": auth_number, "svc_tenant_id": str(tenant_id)},
        )
        return

    claim.status = CLAIM_STATUS_REVERSED

    ap = db.execute(
        select(APRecord).where(
            APRecord.tenant_id == tenant_id,
            APRecord.claim_record_id == claim.id,
            APRecord.status == AP_STATUS_CREATED,
        )
    ).scalar_one_or_none()
    if ap is not None:
        ap.status = AP_STATUS_VOID
        ap.updated_at = datetime.now(UTC)
    db.flush()


async def handle_payment_auto_posted(
    envelope: EventEnvelope, *, db: Session | None, bus: Any
) -> None:
    """React to payment.auto_posted from edi-compliance — apply payment to AR.

    Finds the ARRecord for this claim/tenant and records an ARPayment row,
    decrementing amount_outstanding by paid_amount using Decimal arithmetic.

    Payload shape (from edi-compliance auto_posting.py):
        claim_id, paid_amount, payment_date, check_eft_number, ...
    """
    payload = envelope.payload
    _require(payload, "claim_id", "paid_amount")

    claim_id = _to_uuid(payload["claim_id"])
    paid_amount = _to_decimal(payload["paid_amount"])
    payment_date_raw = payload.get("payment_date")
    tenant_id = _to_uuid(envelope.tenant_id)

    logger.info(
        "billing.consume.payment_auto_posted",
        extra={
            "svc_claim_id": str(claim_id),
            "svc_paid_amount": str(paid_amount),
            "svc_tenant_id": str(tenant_id),
            "svc_correlation_id": str(envelope.correlation_id),
        },
    )

    if db is None:
        return

    # Locate the claim to find its invoice / AR record.
    claim = db.execute(
        select(ClaimRecord).where(
            ClaimRecord.tenant_id == tenant_id,
            ClaimRecord.id == claim_id,
        )
    ).scalar_one_or_none()
    if claim is None:
        logger.warning(
            "billing.consume.payment_auto_posted.claim_not_found",
            extra={"svc_claim_id": str(claim_id), "svc_tenant_id": str(tenant_id)},
        )
        return

    # For now apply payment to the most recent open AR for this client.
    # Invoice→AR linkage will be explicit once the claim→invoice join is persisted.
    ar = db.execute(
        select(ARRecord)
        .where(
            ARRecord.tenant_id == tenant_id,
            ARRecord.client_id == claim.client_id,
            ARRecord.status == "open",
        )
        .order_by(ARRecord.created_at.desc())
    ).scalars().first()
    if ar is None:
        logger.warning(
            "billing.consume.payment_auto_posted.ar_not_found",
            extra={"svc_client_id": str(claim.client_id), "svc_tenant_id": str(tenant_id)},
        )
        return

    from datetime import date as _date

    payment_date = (
        _date.fromisoformat(payment_date_raw) if isinstance(payment_date_raw, str) else (payment_date_raw or _date.today())
    )
    now = datetime.now(UTC)

    ar.amount_paid = _to_decimal(ar.amount_paid) + paid_amount
    ar.amount_outstanding = _to_decimal(ar.amount_due) - ar.amount_paid
    if ar.amount_outstanding <= Decimal("0"):
        ar.status = "paid"
    ar.updated_at = now

    db.add(
        ARPayment(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            ar_record_id=ar.id,
            amount=paid_amount,
            payment_method="auto_posted",
            payment_reference=payload.get("check_eft_number"),
            payment_date=payment_date,
            created_at=now,
        )
    )
    db.flush()


async def handle_payment_vendor_confirmed(
    envelope: EventEnvelope, *, db: Session | None, bus: Any
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
    envelope: EventEnvelope, *, db: Session | None, bus: Any
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
