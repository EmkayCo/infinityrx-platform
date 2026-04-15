"""Integration tests for billing event consumers with real DB persistence.

Verifies that when a SQLAlchemy ``Session`` is injected into each handler:

* ``claim.adjudicated`` creates a ClaimRecord + APRecord pair.
* ``claim.reversed`` marks the ClaimRecord reversed and voids the open AP row.
* ``payment.auto_posted`` records an ARPayment and decrements outstanding.
* Tenant isolation — events for tenant A do not affect tenant B records.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from shared.events.types import EventEnvelope
from src.events.consumers import (
    handle_claim_adjudicated,
    handle_claim_reversed,
    handle_payment_auto_posted,
)
from src.models.tables import APRecord, ARPayment, ARRecord, ClaimRecord, Invoice
from tests.conftest import CLIENT_A, CLIENT_B, PROGRAM_A, TENANT_A, TENANT_B


def _envelope(event_type: str, payload: dict, tenant_id: uuid.UUID = TENANT_A) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        tenant_id=tenant_id,
        correlation_id=uuid.uuid4(),
        source_module="test",
        schema_version="1.0",
        ordering_key=str(payload.get("auth_number") or payload.get("claim_id") or "x"),
        idempotency_key=f"{event_type}:{uuid.uuid4()}",
        payload=payload,
    )


@pytest.mark.asyncio
async def test_claim_adjudicated_creates_claim_and_ap(db_session) -> None:
    env = _envelope(
        "claim.adjudicated",
        {
            "auth_number": "AUTH-1001",
            "claim_type": "new",
            "net_amount": "123.45",
            "pharmacy_npi": "1234567890",
            "date_of_service": "2026-04-01",
            "client_id": str(CLIENT_A),
            "program_id": str(PROGRAM_A),
            "pay_to_entity_id": str(uuid.uuid4()),
            "pay_to_entity_name": "Main St Pharmacy",
            "payment_route": "ach",
        },
    )
    await handle_claim_adjudicated(env, db=db_session, bus=None)

    claim = db_session.query(ClaimRecord).filter_by(auth_number="AUTH-1001").one()
    assert claim.tenant_id == TENANT_A
    assert claim.net_amount == Decimal("123.45")
    assert claim.status == "adjudicated"

    ap = db_session.query(APRecord).filter_by(claim_record_id=claim.id).one()
    assert ap.amount == Decimal("123.45")
    assert ap.status == "created"
    assert ap.tenant_id == TENANT_A


@pytest.mark.asyncio
async def test_claim_adjudicated_idempotent_on_duplicate_auth(db_session) -> None:
    payload = {
        "auth_number": "AUTH-DUPE",
        "claim_type": "new",
        "net_amount": "10.00",
        "pharmacy_npi": "1234567890",
    }
    await handle_claim_adjudicated(_envelope("claim.adjudicated", payload), db=db_session, bus=None)
    await handle_claim_adjudicated(_envelope("claim.adjudicated", payload), db=db_session, bus=None)
    rows = db_session.query(ClaimRecord).filter_by(auth_number="AUTH-DUPE").all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_claim_adjudicated_rejects_missing_fields(db_session) -> None:
    env = _envelope("claim.adjudicated", {"auth_number": "AUTH-X"})
    with pytest.raises(ValueError, match="missing required event fields"):
        await handle_claim_adjudicated(env, db=db_session, bus=None)


@pytest.mark.asyncio
async def test_claim_reversed_marks_claim_and_voids_ap(db_session) -> None:
    # Seed a claim + open AP
    await handle_claim_adjudicated(
        _envelope(
            "claim.adjudicated",
            {
                "auth_number": "AUTH-REV",
                "claim_type": "new",
                "net_amount": "50.00",
                "pharmacy_npi": "1234567890",
            },
        ),
        db=db_session,
        bus=None,
    )

    await handle_claim_reversed(
        _envelope("claim.reversed", {"auth_number": "AUTH-REV"}),
        db=db_session,
        bus=None,
    )

    claim = db_session.query(ClaimRecord).filter_by(auth_number="AUTH-REV").one()
    assert claim.status == "reversed"
    ap = db_session.query(APRecord).filter_by(claim_record_id=claim.id).one()
    assert ap.status == "void"


@pytest.mark.asyncio
async def test_claim_reversed_missing_claim_logs_but_does_not_raise(db_session) -> None:
    await handle_claim_reversed(
        _envelope("claim.reversed", {"auth_number": "AUTH-NOPE"}),
        db=db_session,
        bus=None,
    )  # should not raise


@pytest.mark.asyncio
async def test_payment_auto_posted_applies_to_ar(db_session) -> None:
    # Seed claim to obtain a claim_id
    await handle_claim_adjudicated(
        _envelope(
            "claim.adjudicated",
            {
                "auth_number": "AUTH-AR-1",
                "claim_type": "new",
                "net_amount": "500.00",
                "pharmacy_npi": "1234567890",
                "client_id": str(CLIENT_A),
            },
        ),
        db=db_session,
        bus=None,
    )
    claim = db_session.query(ClaimRecord).filter_by(auth_number="AUTH-AR-1").one()

    # Seed an invoice + AR for that client so the consumer has a target.
    now = datetime.now(UTC)
    invoice = Invoice(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        invoice_number="INV-1",
        invoice_type="ar",
        client_id=CLIENT_A,
        client_name="Test Client",
        period_start=date.today(),
        period_end=date.today(),
        total=Decimal("500.00"),
        status="issued",
        due_date=date.today(),
        created_at=now,
        updated_at=now,
    )
    db_session.add(invoice)
    db_session.flush()
    ar = ARRecord(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        invoice_id=invoice.id,
        client_id=CLIENT_A,
        amount_due=Decimal("500.00"),
        amount_paid=Decimal("0.00"),
        amount_outstanding=Decimal("500.00"),
        status="open",
        due_date=date.today(),
        created_at=now,
        updated_at=now,
    )
    db_session.add(ar)
    db_session.flush()

    await handle_payment_auto_posted(
        _envelope(
            "payment.auto_posted",
            {
                "claim_id": str(claim.id),
                "paid_amount": "200.00",
                "payment_date": "2026-04-14",
                "check_eft_number": "CHK-999",
            },
        ),
        db=db_session,
        bus=None,
    )

    db_session.refresh(ar)
    assert ar.amount_paid == Decimal("200.00")
    assert ar.amount_outstanding == Decimal("300.00")
    assert ar.status == "open"

    payments = db_session.query(ARPayment).filter_by(ar_record_id=ar.id).all()
    assert len(payments) == 1
    assert payments[0].amount == Decimal("200.00")
    assert payments[0].payment_reference == "CHK-999"


@pytest.mark.asyncio
async def test_tenant_isolation_adjudicated(db_session) -> None:
    """Event for Tenant A must not touch Tenant B records."""
    await handle_claim_adjudicated(
        _envelope(
            "claim.adjudicated",
            {
                "auth_number": "AUTH-T-A",
                "claim_type": "new",
                "net_amount": "10.00",
                "pharmacy_npi": "1234567890",
                "client_id": str(CLIENT_A),
            },
            tenant_id=TENANT_A,
        ),
        db=db_session,
        bus=None,
    )
    await handle_claim_adjudicated(
        _envelope(
            "claim.adjudicated",
            {
                "auth_number": "AUTH-T-B",
                "claim_type": "new",
                "net_amount": "20.00",
                "pharmacy_npi": "1234567890",
                "client_id": str(CLIENT_B),
            },
            tenant_id=TENANT_B,
        ),
        db=db_session,
        bus=None,
    )

    t_a_rows = db_session.query(ClaimRecord).filter_by(tenant_id=TENANT_A).all()
    t_b_rows = db_session.query(ClaimRecord).filter_by(tenant_id=TENANT_B).all()
    assert [r.auth_number for r in t_a_rows] == ["AUTH-T-A"]
    assert [r.auth_number for r in t_b_rows] == ["AUTH-T-B"]
