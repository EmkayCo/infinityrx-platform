"""Tests for the EligibilityService — real-time eligibility checks.

RED tests written before implementation (TDD).
100% coverage required on all eligibility paths.
"""
from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.eligibility_service import (
    COBInfo,
    EligibilityRequest,
    EligibilityResponse,
    EligibilityService,
    EligibilityStatus,
    RejectionReason,
)


TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
MEMBER_UUID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
COVERAGE_UUID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


# ---------------------------------------------------------------------------
# EligibilityRequest validation
# ---------------------------------------------------------------------------

class TestEligibilityRequest:
    def test_valid_request_accepted(self):
        req = EligibilityRequest(
            tenant_id=TENANT_ID,
            member_id="M123456",
            rx_bin="610014",
            rx_pcn="MEDCO",
            rx_group="RX1234",
            date_of_service=date(2026, 4, 13),
            source="adjudication",
        )
        assert req.member_id == "M123456"

    def test_request_with_cardholder_person_code(self):
        req = EligibilityRequest(
            tenant_id=TENANT_ID,
            cardholder_id="M100001",
            person_code="02",
            rx_bin="610014",
            date_of_service=date(2026, 4, 13),
            source="portal",
        )
        assert req.person_code == "02"

    def test_correlation_id_auto_generated(self):
        req = EligibilityRequest(
            tenant_id=TENANT_ID,
            member_id="M123456",
            rx_bin="610014",
            date_of_service=date(2026, 4, 13),
            source="api",
        )
        assert req.correlation_id is not None


# ---------------------------------------------------------------------------
# EligibilityResponse structure
# ---------------------------------------------------------------------------

class TestEligibilityResponse:
    def test_eligible_response_has_plan_info(self):
        resp = EligibilityResponse(
            is_eligible=True,
            status=EligibilityStatus.ELIGIBLE,
            matched_member_id=MEMBER_UUID,
            plan_id=uuid.uuid4(),
            plan_name="Basic Rx Plan",
            coverage_type="pharmacy",
            benefit_year_start=date(2026, 1, 1),
            benefit_year_end=date(2026, 12, 31),
        )
        assert resp.is_eligible is True
        assert resp.rejection_reason is None

    def test_ineligible_response_has_rejection_reason(self):
        resp = EligibilityResponse(
            is_eligible=False,
            status=EligibilityStatus.NOT_ELIGIBLE,
            rejection_reason=RejectionReason.MEMBER_NOT_FOUND,
        )
        assert resp.is_eligible is False
        assert resp.rejection_reason == RejectionReason.MEMBER_NOT_FOUND

    def test_cob_info_attached(self):
        cob = COBInfo(
            payer_sequence="primary",
            other_payer_name="BlueCross",
            other_payer_bin="600428",
            other_payer_type="commercial",
        )
        resp = EligibilityResponse(
            is_eligible=True,
            status=EligibilityStatus.ELIGIBLE,
            matched_member_id=MEMBER_UUID,
            cob_records=[cob],
        )
        assert len(resp.cob_records) == 1
        assert resp.cob_records[0].other_payer_name == "BlueCross"


# ---------------------------------------------------------------------------
# RejectionReason values
# ---------------------------------------------------------------------------

class TestRejectionReason:
    def test_all_reason_values_defined(self):
        reasons = {r.value for r in RejectionReason}
        assert "MEMBER_NOT_FOUND" in reasons
        assert "MEMBER_TERMINATED" in reasons
        assert "NOT_EFFECTIVE" in reasons
        assert "COVERAGE_GAP" in reasons
        assert "WRONG_BIN_PCN_GROUP" in reasons


# ---------------------------------------------------------------------------
# EligibilityService logic (unit — no DB, no Redis)
# ---------------------------------------------------------------------------

class TestEligibilityServiceCheckCoverageActive:
    def setup_method(self):
        self.svc = EligibilityService.__new__(EligibilityService)

    def test_active_coverage_on_dos_is_eligible(self):
        """Coverage period includes DOS."""
        result = self.svc._check_coverage_active(
            effective_date=date(2026, 1, 1),
            termination_date=None,
            coverage_status="active",
            date_of_service=date(2026, 4, 13),
        )
        assert result is True

    def test_terminated_coverage_is_ineligible(self):
        """status=terminated → not eligible."""
        result = self.svc._check_coverage_active(
            effective_date=date(2026, 1, 1),
            termination_date=date(2026, 3, 31),
            coverage_status="terminated",
            date_of_service=date(2026, 4, 13),
        )
        assert result is False

    def test_future_effective_date_is_ineligible(self):
        """Coverage starts in the future."""
        result = self.svc._check_coverage_active(
            effective_date=date(2026, 5, 1),
            termination_date=None,
            coverage_status="active",
            date_of_service=date(2026, 4, 13),
        )
        assert result is False

    def test_dos_exactly_on_effective_date_is_eligible(self):
        """DOS = effective_date boundary — eligible."""
        result = self.svc._check_coverage_active(
            effective_date=date(2026, 4, 13),
            termination_date=None,
            coverage_status="active",
            date_of_service=date(2026, 4, 13),
        )
        assert result is True

    def test_dos_exactly_on_termination_date_is_eligible(self):
        """DOS = termination_date — still covered (inclusive end)."""
        result = self.svc._check_coverage_active(
            effective_date=date(2026, 1, 1),
            termination_date=date(2026, 4, 13),
            coverage_status="active",
            date_of_service=date(2026, 4, 13),
        )
        assert result is True

    def test_dos_after_termination_date_is_ineligible(self):
        result = self.svc._check_coverage_active(
            effective_date=date(2026, 1, 1),
            termination_date=date(2026, 4, 12),
            coverage_status="active",
            date_of_service=date(2026, 4, 13),
        )
        assert result is False

    def test_coverage_status_inactive_is_ineligible(self):
        result = self.svc._check_coverage_active(
            effective_date=date(2026, 1, 1),
            termination_date=None,
            coverage_status="inactive",
            date_of_service=date(2026, 4, 13),
        )
        assert result is False

    def test_no_coverage_period_means_coverage_gap(self):
        """No coverage period at all → COVERAGE_GAP."""
        result = self.svc._check_coverage_active(
            effective_date=None,
            termination_date=None,
            coverage_status=None,
            date_of_service=date(2026, 4, 13),
        )
        assert result is False


# ---------------------------------------------------------------------------
# Rejection reason selection
# ---------------------------------------------------------------------------

class TestEligibilityServiceRejectionReason:
    def setup_method(self):
        self.svc = EligibilityService.__new__(EligibilityService)

    def test_member_not_found_reason(self):
        reason = self.svc._determine_rejection_reason(
            member_found=False,
            coverage_found=False,
            member_status=None,
            coverage_includes_dos=False,
            bin_pcn_group_match=False,
        )
        assert reason == RejectionReason.MEMBER_NOT_FOUND

    def test_terminated_member_reason(self):
        reason = self.svc._determine_rejection_reason(
            member_found=True,
            coverage_found=True,
            member_status="terminated",
            coverage_includes_dos=False,
            bin_pcn_group_match=True,
        )
        assert reason == RejectionReason.MEMBER_TERMINATED

    def test_not_effective_yet_reason(self):
        reason = self.svc._determine_rejection_reason(
            member_found=True,
            coverage_found=True,
            member_status="active",
            coverage_includes_dos=False,
            bin_pcn_group_match=True,
        )
        assert reason == RejectionReason.NOT_EFFECTIVE

    def test_wrong_bin_pcn_group_reason(self):
        reason = self.svc._determine_rejection_reason(
            member_found=True,
            coverage_found=False,
            member_status="active",
            coverage_includes_dos=False,
            bin_pcn_group_match=False,
        )
        assert reason == RejectionReason.WRONG_BIN_PCN_GROUP

    def test_coverage_gap_reason_no_coverage(self):
        reason = self.svc._determine_rejection_reason(
            member_found=True,
            coverage_found=False,
            member_status="active",
            coverage_includes_dos=False,
            bin_pcn_group_match=True,
        )
        assert reason == RejectionReason.COVERAGE_GAP


# ---------------------------------------------------------------------------
# Cache key generation
# ---------------------------------------------------------------------------

class TestEligibilityServiceCacheKey:
    def setup_method(self):
        self.svc = EligibilityService.__new__(EligibilityService)

    def test_cache_key_uses_tenant_prefix(self):
        key = self.svc._cache_key(TENANT_ID, "M123456", "610014", "MEDCO", "RX1234")
        assert key.startswith(f"tenant:{TENANT_ID}:eligibility:")

    def test_cache_key_includes_member_and_bin(self):
        key = self.svc._cache_key(TENANT_ID, "M123456", "610014", "MEDCO", "RX1234")
        assert "M123456" in key
        assert "610014" in key

    def test_cache_key_tenant_scoped_differently_for_different_tenants(self):
        key_a = self.svc._cache_key(TENANT_ID, "M123456", "610014", "MEDCO", "RX1234")
        other = uuid.UUID("22222222-2222-2222-2222-222222222222")
        key_b = self.svc._cache_key(other, "M123456", "610014", "MEDCO", "RX1234")
        assert key_a != key_b

    def test_cache_key_none_pcn_and_group_handled(self):
        key = self.svc._cache_key(TENANT_ID, "M123456", "610014", None, None)
        assert "M123456" in key


# ---------------------------------------------------------------------------
# EligibilityService async methods (mocked DB + Redis)
# ---------------------------------------------------------------------------

class TestEligibilityServiceCheck:
    @pytest.fixture
    def mock_redis(self):
        r = AsyncMock()
        r.get = AsyncMock(return_value=None)
        r.setex = AsyncMock()
        return r

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_cache_miss_then_db_hit_eligible(self, mock_redis, mock_db):
        """Cache miss → DB query → eligible member returned."""
        svc = EligibilityService(redis=mock_redis)

        db_result = MagicMock()
        db_result.member_found = True
        db_result.member_status = "active"
        db_result.coverage_found = True
        db_result.coverage_status = "active"
        db_result.effective_date = date(2026, 1, 1)
        db_result.termination_date = None
        db_result.bin_pcn_group_match = True
        db_result.member_uuid = MEMBER_UUID
        db_result.plan_id = uuid.uuid4()
        db_result.plan_name = "Basic Rx"
        db_result.coverage_type = "pharmacy"
        db_result.benefit_year_start = date(2026, 1, 1)
        db_result.benefit_year_end = date(2026, 12, 31)
        db_result.cob_records = []

        svc._query_db = AsyncMock(return_value=db_result)

        req = EligibilityRequest(
            tenant_id=TENANT_ID,
            member_id="M123456",
            rx_bin="610014",
            date_of_service=date(2026, 4, 13),
            source="adjudication",
        )
        resp = await svc.check(mock_db, req)

        assert resp.is_eligible is True
        assert resp.status == EligibilityStatus.ELIGIBLE
        mock_redis.setex.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_result(self, mock_redis, mock_db):
        """Cache hit → no DB query, returns cached eligible response."""
        import json
        cached_data = {
            "is_eligible": True,
            "status": "eligible",
            "rejection_reason": None,
            "matched_member_id": str(MEMBER_UUID),
            "plan_id": None,
            "plan_name": "Basic Rx",
            "coverage_type": "pharmacy",
            "benefit_year_start": "2026-01-01",
            "benefit_year_end": "2026-12-31",
            "cob_records": [],
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data).encode())

        svc = EligibilityService(redis=mock_redis)
        svc._query_db = AsyncMock()

        req = EligibilityRequest(
            tenant_id=TENANT_ID,
            member_id="M123456",
            rx_bin="610014",
            date_of_service=date(2026, 4, 13),
            source="adjudication",
        )
        resp = await svc.check(mock_db, req)

        assert resp.is_eligible is True
        svc._query_db.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_member_not_found_returns_ineligible(self, mock_redis, mock_db):
        svc = EligibilityService(redis=mock_redis)

        db_result = MagicMock()
        db_result.member_found = False
        db_result.member_status = None
        db_result.coverage_found = False
        db_result.coverage_status = None
        db_result.effective_date = None
        db_result.termination_date = None
        db_result.bin_pcn_group_match = False
        db_result.member_uuid = None
        db_result.plan_id = None
        db_result.plan_name = None
        db_result.coverage_type = None
        db_result.benefit_year_start = None
        db_result.benefit_year_end = None
        db_result.cob_records = []

        svc._query_db = AsyncMock(return_value=db_result)

        req = EligibilityRequest(
            tenant_id=TENANT_ID,
            member_id="MISSING",
            rx_bin="610014",
            date_of_service=date(2026, 4, 13),
            source="adjudication",
        )
        resp = await svc.check(mock_db, req)

        assert resp.is_eligible is False
        assert resp.rejection_reason == RejectionReason.MEMBER_NOT_FOUND

    @pytest.mark.asyncio
    async def test_terminated_member_returns_ineligible(self, mock_redis, mock_db):
        svc = EligibilityService(redis=mock_redis)

        db_result = MagicMock()
        db_result.member_found = True
        db_result.member_status = "terminated"
        db_result.coverage_found = True
        db_result.coverage_status = "terminated"
        db_result.effective_date = date(2026, 1, 1)
        db_result.termination_date = date(2026, 3, 31)
        db_result.bin_pcn_group_match = True
        db_result.member_uuid = MEMBER_UUID
        db_result.plan_id = None
        db_result.plan_name = None
        db_result.coverage_type = None
        db_result.benefit_year_start = None
        db_result.benefit_year_end = None
        db_result.cob_records = []

        svc._query_db = AsyncMock(return_value=db_result)

        req = EligibilityRequest(
            tenant_id=TENANT_ID,
            member_id="M123456",
            rx_bin="610014",
            date_of_service=date(2026, 4, 13),
            source="adjudication",
        )
        resp = await svc.check(mock_db, req)

        assert resp.is_eligible is False
        assert resp.rejection_reason == RejectionReason.MEMBER_TERMINATED

    @pytest.mark.asyncio
    async def test_check_without_redis_goes_direct_to_db(self, mock_db):
        """When redis=None, no cache attempted."""
        svc = EligibilityService(redis=None)

        db_result = MagicMock()
        db_result.member_found = True
        db_result.member_status = "active"
        db_result.coverage_found = True
        db_result.coverage_status = "active"
        db_result.effective_date = date(2026, 1, 1)
        db_result.termination_date = None
        db_result.bin_pcn_group_match = True
        db_result.member_uuid = MEMBER_UUID
        db_result.plan_id = None
        db_result.plan_name = "Plan A"
        db_result.coverage_type = "pharmacy"
        db_result.benefit_year_start = date(2026, 1, 1)
        db_result.benefit_year_end = date(2026, 12, 31)
        db_result.cob_records = []

        svc._query_db = AsyncMock(return_value=db_result)

        req = EligibilityRequest(
            tenant_id=TENANT_ID,
            member_id="M123456",
            rx_bin="610014",
            date_of_service=date(2026, 4, 13),
            source="api",
        )
        resp = await svc.check(mock_db, req)
        assert resp.is_eligible is True

    @pytest.mark.asyncio
    async def test_cache_invalidate_calls_delete(self, mock_redis):
        mock_redis.delete = AsyncMock()
        svc = EligibilityService(redis=mock_redis)
        await svc.invalidate_cache(TENANT_ID, "M123456", "610014", None, None)
        mock_redis.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cache_invalidate_without_redis_is_noop(self):
        svc = EligibilityService(redis=None)
        # Should not raise
        await svc.invalidate_cache(TENANT_ID, "M123456", "610014", None, None)
