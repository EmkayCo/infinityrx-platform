"""Tests for prescriber-directory event consumers."""
from __future__ import annotations


import pytest
from sqlalchemy import select

from src.events.consumer import handle_claim_ingested, handle_exclusion_match_found
from src.models.tables import Prescriber, PrescriberPharmacyRelationship

from tests.conftest import now_utc


def _add_prescriber(db, npi: str, status: str = "active") -> Prescriber:
    p = Prescriber(
        npi=npi,
        entity_type="1",
        last_name="TEST",
        first_name="USER",
        display_name="TEST USER MD",
        status=status,
        offers_telehealth=False,
        medicare_opt_out=False,
        taxonomy_codes=[],
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(p)
    db.flush()
    return p


# ── handle_claim_ingested ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_claim_ingested_creates_new_relationship(db_session):
    payload = {
        "prescriber_npi": "1111111111",
        "pharmacy_npi": "2222222222",
        "date_of_service": "2026-03-15",
    }
    await handle_claim_ingested(payload, db_session)
    row = db_session.execute(
        select(PrescriberPharmacyRelationship).where(
            PrescriberPharmacyRelationship.prescriber_npi == "1111111111",
            PrescriberPharmacyRelationship.pharmacy_npi == "2222222222",
            PrescriberPharmacyRelationship.period_month == "2026-03",
        )
    ).scalar_one_or_none()
    assert row is not None
    assert row.claim_count == 1


@pytest.mark.asyncio
async def test_claim_ingested_increments_existing_relationship(db_session):
    existing = PrescriberPharmacyRelationship(
        prescriber_npi="3333333333",
        pharmacy_npi="4444444444",
        period_month="2026-01",
        claim_count=5,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db_session.add(existing)
    db_session.flush()

    payload = {
        "prescriber_npi": "3333333333",
        "pharmacy_npi": "4444444444",
        "date_of_service": "2026-01-20",
    }
    await handle_claim_ingested(payload, db_session)

    row = db_session.execute(
        select(PrescriberPharmacyRelationship).where(
            PrescriberPharmacyRelationship.prescriber_npi == "3333333333",
            PrescriberPharmacyRelationship.pharmacy_npi == "4444444444",
            PrescriberPharmacyRelationship.period_month == "2026-01",
        )
    ).scalar_one()
    assert row.claim_count == 6


@pytest.mark.asyncio
async def test_claim_ingested_missing_prescriber_npi_returns_early(db_session):
    payload = {"pharmacy_npi": "9999999999", "date_of_service": "2026-01-01"}
    # Should not raise, should return without creating a row
    await handle_claim_ingested(payload, db_session)
    rows = db_session.execute(
        select(PrescriberPharmacyRelationship).where(
            PrescriberPharmacyRelationship.pharmacy_npi == "9999999999"
        )
    ).scalars().all()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_claim_ingested_missing_pharmacy_npi_returns_early(db_session):
    payload = {"prescriber_npi": "8888888888", "date_of_service": "2026-01-01"}
    await handle_claim_ingested(payload, db_session)
    rows = db_session.execute(
        select(PrescriberPharmacyRelationship).where(
            PrescriberPharmacyRelationship.prescriber_npi == "8888888888"
        )
    ).scalars().all()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_claim_ingested_empty_date_uses_current_month(db_session):
    payload = {
        "prescriber_npi": "5555555555",
        "pharmacy_npi": "6666666666",
        "date_of_service": "",
    }
    await handle_claim_ingested(payload, db_session)
    row = db_session.execute(
        select(PrescriberPharmacyRelationship).where(
            PrescriberPharmacyRelationship.prescriber_npi == "5555555555",
        )
    ).scalar_one_or_none()
    assert row is not None
    # period_month should be current year-month format
    from datetime import datetime, timezone
    expected_prefix = datetime.now(timezone.utc).strftime("%Y-%m")
    assert row.period_month == expected_prefix


@pytest.mark.asyncio
async def test_claim_ingested_short_date_uses_current_month(db_session):
    payload = {
        "prescriber_npi": "7777777777",
        "pharmacy_npi": "8888888880",
        "date_of_service": "20",  # too short to extract period
    }
    await handle_claim_ingested(payload, db_session)
    row = db_session.execute(
        select(PrescriberPharmacyRelationship).where(
            PrescriberPharmacyRelationship.prescriber_npi == "7777777777",
        )
    ).scalar_one_or_none()
    assert row is not None


# ── handle_exclusion_match_found ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_exclusion_match_marks_prescriber_excluded(db_session):
    _add_prescriber(db_session, "1100000000", status="active")
    payload = {"entity_npi": "1100000000", "exclusion_type": "OIG"}
    await handle_exclusion_match_found(payload, db_session)

    row = db_session.execute(
        select(Prescriber).where(Prescriber.npi == "1100000000")
    ).scalar_one()
    assert row.status == "excluded"


@pytest.mark.asyncio
async def test_exclusion_match_not_found_returns_early(db_session):
    payload = {"entity_npi": "9900000000", "exclusion_type": "SAM"}
    # Should not raise even if prescriber doesn't exist
    await handle_exclusion_match_found(payload, db_session)


@pytest.mark.asyncio
async def test_exclusion_match_missing_npi_returns_early(db_session):
    payload = {"exclusion_type": "OFAC"}
    await handle_exclusion_match_found(payload, db_session)
