"""End-to-end integration tests for the FWA detection pipeline.

Each test drives an async handler directly against the SAVEPOINT-isolated
``db`` session fixture. This mirrors how ``wire_consumers`` will invoke the
handlers in production (same signatures, same DB ops) without spinning the
InMemoryEventBus round-trip — that layer is already covered in
test_consumer_wiring.py.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from shared.events.types import EventEnvelope
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.events.consumers import (
    handle_claim_adjudicated,
    handle_claim_reversed,
    handle_exclusion_match_found,
    handle_pharmacy_ownership_changed,
)
from src.models.tables import (
    FlaggedClaim,
    Investigation,
    PaymentHold,
    PharmacyProfile,
)

from tests.conftest import OTHER_TENANT_ID, TEST_TENANT_ID


def _env(
    event_type: str,
    payload: dict,
    tenant_id: uuid.UUID = TEST_TENANT_ID,
    ordering: str | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        tenant_id=tenant_id,
        correlation_id=uuid.uuid4(),
        source_module="test",
        schema_version="1.0",
        ordering_key=ordering or payload.get("auth_number") or str(uuid.uuid4()),
        idempotency_key=f"{event_type}:{uuid.uuid4()}",
        payload=payload,
    )


def _claim_payload(
    auth: str,
    pharm: str = "1234567890",
    amount: str = "100.00",
    member: str = "M100",
    ndc: str = "12345678901",
    prescr: str = "9876543210",
) -> dict:
    return {
        "claim_id": str(uuid.uuid4()),
        "auth_number": auth,
        "pharmacy_npi": pharm,
        "pharmacy_name": f"Pharmacy {pharm}",
        "prescriber_npi": prescr,
        "member_id": member,
        "ndc": ndc,
        "drug_name": "TestDrug",
        "quantity": "30",
        "days_supply": 30,
        "billed_amount": amount,
        "paid_amount": amount,
        "net_amount": amount,
        "wac_per_unit": "1.00",
        "awp_per_unit": "1.20",
        "date_of_service": date.today().isoformat(),
        "client_type": "all",
        "program_type": "commercial",
    }


@pytest.mark.asyncio
async def test_bill_reverse_rebill_detection_flags_claim(db: Session) -> None:
    """Three submissions on the same auth_number at escalating amounts fire BRR."""
    await handle_claim_adjudicated(
        _env("claim.adjudicated", _claim_payload("AUTH-BRR", amount="50.00")),
        db=db,
        bus=None,
    )
    # Second (the "rebill at escalated amount") should trigger BRR rule.
    await handle_claim_adjudicated(
        _env("claim.adjudicated", _claim_payload("AUTH-BRR", amount="350.00")),
        db=db,
        bus=None,
    )

    flags = db.execute(
        select(FlaggedClaim).where(
            FlaggedClaim.tenant_id == str(TEST_TENANT_ID),
            FlaggedClaim.auth_number == "AUTH-BRR",
        )
    ).scalars().all()
    # The second submission fires BRR against the first.
    assert any(f.rule_code == "BILL_REVERSE_REBILL" for f in flags)
    # BRR should be marked high-confidence / high risk
    brr = next(f for f in flags if f.rule_code == "BILL_REVERSE_REBILL")
    assert brr.risk_score >= 80
    assert brr.confidence_tier == "high"


@pytest.mark.asyncio
async def test_ml_score_attached_to_flagged_claim(db: Session) -> None:
    """Every flagged claim carries the ml_score in its evidence payload."""
    await handle_claim_adjudicated(
        _env("claim.adjudicated", _claim_payload("AUTH-ML", amount="100.00")),
        db=db,
        bus=None,
    )
    # Trigger a flag via BRR on second submission
    await handle_claim_adjudicated(
        _env("claim.adjudicated", _claim_payload("AUTH-ML", amount="500.00")),
        db=db,
        bus=None,
    )

    flag = db.execute(
        select(FlaggedClaim).where(
            FlaggedClaim.tenant_id == str(TEST_TENANT_ID),
            FlaggedClaim.auth_number == "AUTH-ML",
        )
    ).scalars().first()
    assert flag is not None
    assert "ml_score" in flag.evidence
    assert isinstance(flag.evidence["ml_score"], int)
    assert 0 <= flag.evidence["ml_score"] <= 100


@pytest.mark.asyncio
async def test_payment_hold_placed_when_risk_exceeds_threshold(db: Session) -> None:
    """Risk >= 70 triggers a PaymentHold row with scope=flagged_only."""
    await handle_claim_adjudicated(
        _env("claim.adjudicated", _claim_payload("AUTH-HOLD", amount="100.00")),
        db=db,
        bus=None,
    )
    await handle_claim_adjudicated(
        _env("claim.adjudicated", _claim_payload("AUTH-HOLD", amount="999.00")),
        db=db,
        bus=None,
    )

    holds = db.execute(
        select(PaymentHold).where(
            PaymentHold.tenant_id == str(TEST_TENANT_ID),
            PaymentHold.entity_type == "pharmacy",
            PaymentHold.entity_id == "1234567890",
        )
    ).scalars().all()
    assert len(holds) >= 1
    assert any(h.is_active for h in holds)


@pytest.mark.asyncio
async def test_investigation_auto_opens_for_high_risk_claim(db: Session) -> None:
    """Risk >= 80 auto-opens a pharmacy investigation and links the flag."""
    await handle_claim_adjudicated(
        _env("claim.adjudicated", _claim_payload("AUTH-INV", amount="100.00")),
        db=db,
        bus=None,
    )
    await handle_claim_adjudicated(
        _env("claim.adjudicated", _claim_payload("AUTH-INV", amount="1000.00")),
        db=db,
        bus=None,
    )

    inv = db.execute(
        select(Investigation).where(
            Investigation.tenant_id == str(TEST_TENANT_ID),
            Investigation.subject_type == "pharmacy",
            Investigation.subject_entity_id == "1234567890",
        )
    ).scalar_one_or_none()
    assert inv is not None
    assert inv.status == "open"
    assert (inv.flagged_claim_count or 0) >= 1

    flag = db.execute(
        select(FlaggedClaim).where(
            FlaggedClaim.tenant_id == str(TEST_TENANT_ID),
            FlaggedClaim.auth_number == "AUTH-INV",
        )
    ).scalars().first()
    assert flag is not None
    assert flag.investigation_id == inv.id


@pytest.mark.asyncio
async def test_exclusion_match_opens_investigation_and_places_hold(db: Session) -> None:
    """OIG/SAM match cascades into global hold + investigation."""
    await handle_exclusion_match_found(
        _env(
            "exclusion.match_found",
            {
                "entity_type": "pharmacy",
                "entity_id": "5555555555",
                "entity_name": "Sanctioned Pharmacy Inc",
            },
        ),
        db=db,
        bus=None,
    )

    hold = db.execute(
        select(PaymentHold).where(
            PaymentHold.tenant_id == str(TEST_TENANT_ID),
            PaymentHold.entity_id == "5555555555",
        )
    ).scalar_one_or_none()
    assert hold is not None
    assert hold.hold_scope == "all"
    assert hold.is_active

    inv = db.execute(
        select(Investigation).where(
            Investigation.tenant_id == str(TEST_TENANT_ID),
            Investigation.subject_entity_id == "5555555555",
        )
    ).scalar_one_or_none()
    assert inv is not None
    assert inv.investigation_type == "exclusion_match"
    assert inv.priority == "critical"

    pharm = db.execute(
        select(PharmacyProfile).where(
            PharmacyProfile.tenant_id == str(TEST_TENANT_ID),
            PharmacyProfile.pharmacy_npi == "5555555555",
        )
    ).scalar_one_or_none()
    assert pharm is not None
    assert pharm.is_flagged


@pytest.mark.asyncio
async def test_reversal_escalates_prior_flag(db: Session) -> None:
    """A reversal on a previously-flagged claim bumps confidence and risk."""
    # Seed two BRR submissions so the flag exists
    await handle_claim_adjudicated(
        _env("claim.adjudicated", _claim_payload("AUTH-REV", amount="100.00")),
        db=db, bus=None,
    )
    await handle_claim_adjudicated(
        _env("claim.adjudicated", _claim_payload("AUTH-REV", amount="900.00")),
        db=db, bus=None,
    )
    flag = db.execute(
        select(FlaggedClaim).where(
            FlaggedClaim.tenant_id == str(TEST_TENANT_ID),
            FlaggedClaim.auth_number == "AUTH-REV",
        )
    ).scalars().first()
    assert flag is not None
    risk_before = flag.risk_score

    await handle_claim_reversed(
        _env("claim.reversed", {"auth_number": "AUTH-REV"}),
        db=db, bus=None,
    )

    db.refresh(flag)
    assert flag.risk_score >= risk_before
    assert flag.evidence.get("reversal_observed") is True
    assert flag.confidence_tier == "high"


@pytest.mark.asyncio
async def test_ownership_change_boosts_risk_and_opens_investigation(db: Session) -> None:
    """Ownership change is a high-risk event: boost profile + investigation."""
    await handle_pharmacy_ownership_changed(
        _env(
            "pharmacy.ownership_changed",
            {"pharmacy_npi": "7777777777", "pharmacy_name": "Changed Pharmacy"},
        ),
        db=db, bus=None,
    )

    pharm = db.execute(
        select(PharmacyProfile).where(
            PharmacyProfile.tenant_id == str(TEST_TENANT_ID),
            PharmacyProfile.pharmacy_npi == "7777777777",
        )
    ).scalar_one_or_none()
    assert pharm is not None
    assert pharm.composite_risk_score >= 50
    assert pharm.risk_trend == "increasing"

    inv = db.execute(
        select(Investigation).where(
            Investigation.tenant_id == str(TEST_TENANT_ID),
            Investigation.subject_entity_id == "7777777777",
        )
    ).scalar_one_or_none()
    assert inv is not None
    assert inv.investigation_type == "ownership_change_review"


@pytest.mark.asyncio
async def test_tenant_isolation_flagged_claims_do_not_leak(db: Session) -> None:
    """Claims flagged under Tenant A must never appear in Tenant B queries."""
    await handle_claim_adjudicated(
        _env("claim.adjudicated", _claim_payload("AUTH-T-A", amount="50.00"),
             tenant_id=TEST_TENANT_ID),
        db=db, bus=None,
    )
    await handle_claim_adjudicated(
        _env("claim.adjudicated", _claim_payload("AUTH-T-A", amount="950.00"),
             tenant_id=TEST_TENANT_ID),
        db=db, bus=None,
    )
    await handle_claim_adjudicated(
        _env("claim.adjudicated", _claim_payload("AUTH-T-B", amount="50.00"),
             tenant_id=OTHER_TENANT_ID),
        db=db, bus=None,
    )
    await handle_claim_adjudicated(
        _env("claim.adjudicated", _claim_payload("AUTH-T-B", amount="950.00"),
             tenant_id=OTHER_TENANT_ID),
        db=db, bus=None,
    )

    a_flags = db.execute(
        select(FlaggedClaim).where(FlaggedClaim.tenant_id == str(TEST_TENANT_ID))
    ).scalars().all()
    b_flags = db.execute(
        select(FlaggedClaim).where(FlaggedClaim.tenant_id == str(OTHER_TENANT_ID))
    ).scalars().all()

    assert all(f.auth_number != "AUTH-T-B" for f in a_flags)
    assert all(f.auth_number != "AUTH-T-A" for f in b_flags)
    assert len(a_flags) >= 1
    assert len(b_flags) >= 1
