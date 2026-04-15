"""Integration tests for EligibilityService._query_db with real ORM queries.

Verifies the previously-stub _query_db now resolves member + coverage + COB
data against the members / coverage_periods / cob_records tables, and that
tenant isolation is preserved.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest

from src.models.tables import CobRecord, CoveragePeriod, Member
from src.services.eligibility_service import (
    EligibilityRequest,
    EligibilityService,
    EligibilityStatus,
    RejectionReason,
)
from tests.conftest import TENANT_A, TENANT_B


def _seed_member(
    db,
    tenant_id: uuid.UUID = TENANT_A,
    member_id: str = "M0001",
    rx_bin: str = "610014",
    rx_pcn: str | None = "MEDCO",
    rx_group: str | None = "RX1234",
    status: str = "active",
) -> Member:
    # EncryptedString column takes plaintext and encrypts on bind.
    m = Member(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        member_id=member_id,
        person_code="01",
        first_name_encrypted="Ada",
        last_name_encrypted="Lovelace",
        dob_encrypted="1815-12-10",
        gender="F",
        rx_bin=rx_bin,
        rx_pcn=rx_pcn,
        rx_group=rx_group,
        status=status,
    )
    db.add(m)
    db.flush()
    return m


def _seed_coverage(
    db,
    member: Member,
    effective: date,
    term: date | None = None,
    plan_name: str = "Basic Rx",
) -> CoveragePeriod:
    c = CoveragePeriod(
        id=uuid.uuid4(),
        tenant_id=member.tenant_id,
        member_id=member.id,
        plan_id=uuid.uuid4(),
        plan_name=plan_name,
        coverage_type="pharmacy",
        effective_date=effective,
        termination_date=term,
        benefit_year_start=date(effective.year, 1, 1),
        benefit_year_end=date(effective.year, 12, 31),
        status="active",
    )
    db.add(c)
    db.flush()
    return c


@pytest.mark.asyncio
async def test_active_member_with_coverage_is_eligible(db_session) -> None:
    member = _seed_member(db_session)
    _seed_coverage(db_session, member, effective=date(2026, 1, 1))

    svc = EligibilityService()
    req = EligibilityRequest(
        tenant_id=TENANT_A,
        member_id="M0001",
        rx_bin="610014",
        rx_pcn="MEDCO",
        rx_group="RX1234",
        date_of_service=date(2026, 4, 14),
        source="test",
    )
    resp = await svc.check(db_session, req)
    assert resp.is_eligible is True
    assert resp.status == EligibilityStatus.ELIGIBLE
    assert resp.matched_member_id == member.id
    assert resp.plan_name == "Basic Rx"


@pytest.mark.asyncio
async def test_expired_coverage_returns_not_eligible(db_session) -> None:
    member = _seed_member(db_session, member_id="M-EXP")
    _seed_coverage(db_session, member, effective=date(2025, 1, 1), term=date(2025, 12, 31))

    svc = EligibilityService()
    req = EligibilityRequest(
        tenant_id=TENANT_A,
        member_id="M-EXP",
        rx_bin="610014",
        rx_pcn="MEDCO",
        rx_group="RX1234",
        date_of_service=date(2026, 4, 14),
        source="test",
    )
    resp = await svc.check(db_session, req)
    assert resp.is_eligible is False


@pytest.mark.asyncio
async def test_future_coverage_returns_not_eligible(db_session) -> None:
    member = _seed_member(db_session, member_id="M-FUT")
    _seed_coverage(db_session, member, effective=date(2027, 1, 1))

    svc = EligibilityService()
    req = EligibilityRequest(
        tenant_id=TENANT_A,
        member_id="M-FUT",
        rx_bin="610014",
        rx_pcn="MEDCO",
        rx_group="RX1234",
        date_of_service=date(2026, 4, 14),
        source="test",
    )
    resp = await svc.check(db_session, req)
    assert resp.is_eligible is False


@pytest.mark.asyncio
async def test_missing_member_returns_member_not_found(db_session) -> None:
    svc = EligibilityService()
    req = EligibilityRequest(
        tenant_id=TENANT_A,
        member_id="NOPE",
        rx_bin="610014",
        date_of_service=date(2026, 4, 14),
        source="test",
    )
    resp = await svc.check(db_session, req)
    assert resp.is_eligible is False
    assert resp.rejection_reason == RejectionReason.MEMBER_NOT_FOUND


@pytest.mark.asyncio
async def test_wrong_bin_pcn_group_rejected(db_session) -> None:
    member = _seed_member(db_session, member_id="M-BIN")
    _seed_coverage(db_session, member, effective=date(2026, 1, 1))

    svc = EligibilityService()
    req = EligibilityRequest(
        tenant_id=TENANT_A,
        member_id="M-BIN",
        rx_bin="999999",  # wrong BIN
        date_of_service=date(2026, 4, 14),
        source="test",
    )
    resp = await svc.check(db_session, req)
    assert resp.is_eligible is False
    assert resp.rejection_reason == RejectionReason.WRONG_BIN_PCN_GROUP


@pytest.mark.asyncio
async def test_tenant_isolation_does_not_leak(db_session) -> None:
    """Same member_id in Tenant A and Tenant B — query for Tenant A must not see Tenant B."""
    a = _seed_member(db_session, tenant_id=TENANT_A, member_id="SHARED")
    _seed_coverage(db_session, a, effective=date(2026, 1, 1), plan_name="A-Plan")

    b = _seed_member(db_session, tenant_id=TENANT_B, member_id="SHARED")
    _seed_coverage(db_session, b, effective=date(2026, 1, 1), plan_name="B-Plan")

    svc = EligibilityService()
    req_a = EligibilityRequest(
        tenant_id=TENANT_A,
        member_id="SHARED",
        rx_bin="610014",
        rx_pcn="MEDCO",
        rx_group="RX1234",
        date_of_service=date(2026, 4, 14),
        source="test",
    )
    resp_a = await svc.check(db_session, req_a)
    assert resp_a.plan_name == "A-Plan"


@pytest.mark.asyncio
async def test_cob_records_returned_when_active(db_session) -> None:
    member = _seed_member(db_session, member_id="M-COB")
    _seed_coverage(db_session, member, effective=date(2026, 1, 1))

    db_session.add(
        CobRecord(
            id=uuid.uuid4(),
            tenant_id=TENANT_A,
            member_id=member.id,
            payer_sequence="secondary",
            other_payer_name="Secondary Rx Plan",
            other_payer_bin="999888",
            other_payer_pcn="SEC",
            effective_date=date(2026, 1, 1),
        )
    )
    db_session.flush()

    svc = EligibilityService()
    req = EligibilityRequest(
        tenant_id=TENANT_A,
        member_id="M-COB",
        rx_bin="610014",
        rx_pcn="MEDCO",
        rx_group="RX1234",
        date_of_service=date(2026, 4, 14),
        source="test",
    )
    resp = await svc.check(db_session, req)
    assert resp.is_eligible is True
    assert len(resp.cob_records) == 1
    assert resp.cob_records[0].other_payer_bin == "999888"
