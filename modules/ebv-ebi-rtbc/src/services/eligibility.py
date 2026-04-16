"""Eligibility verification service for the EBV/EBI/RTBC module.

Verifies member active status, plan coverage dates, benefit phase,
deductible/OOP progress. Sub-500ms real-time target.

All money as Decimal with ROUND_HALF_UP. No floats.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from shared.utils.money import ZERO, TWO_PLACES, money

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RESPONSE_TIME_WARNING_MS = 500


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BenefitPhase(str, Enum):
    """Standard Part D / commercial benefit phases."""

    DEDUCTIBLE = "deductible"
    INITIAL_COVERAGE = "initial_coverage"
    COVERAGE_GAP = "coverage_gap"
    CATASTROPHIC = "catastrophic"
    POST_DEDUCTIBLE = "post_deductible"


class EligibilityStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TERMINATED = "terminated"
    FUTURE_EFFECTIVE = "future_effective"


# ---------------------------------------------------------------------------
# Schemas (Pydantic)
# ---------------------------------------------------------------------------


class CopayTier(BaseModel):
    """Copay amount for a specific drug tier."""

    tier: str
    copay: Decimal
    coinsurance_pct: Decimal | None = None


class AccumulatorProgress(BaseModel):
    """Deductible or OOP accumulator progress snapshot."""

    limit: Decimal
    met: Decimal
    remaining: Decimal
    pct_met: Decimal


class EligibilityResult(BaseModel):
    """Full eligibility verification result."""

    member_id: str
    status: EligibilityStatus
    plan_id: uuid.UUID | None = None
    plan_name: str | None = None
    group_id: uuid.UUID | None = None
    group_name: str | None = None
    coverage_start: date | None = None
    coverage_end: date | None = None
    copay_summary: list[CopayTier] = Field(default_factory=list)
    benefit_phase: BenefitPhase | None = None
    deductible: AccumulatorProgress | None = None
    oop: AccumulatorProgress | None = None
    response_time_ms: int = 0
    checked_at: datetime | None = None


# ---------------------------------------------------------------------------
# Data protocol (dependency-injected)
# ---------------------------------------------------------------------------


class MemberRecord(BaseModel):
    """Represents the data fetched from the member store for eligibility."""

    member_id: str
    status: str
    plan_id: uuid.UUID | None = None
    plan_name: str | None = None
    group_id: uuid.UUID | None = None
    group_name: str | None = None
    coverage_start: date | None = None
    coverage_end: date | None = None
    copay_tiers: list[dict[str, Any]] = Field(default_factory=list)
    deductible_limit: Decimal = ZERO
    deductible_met: Decimal = ZERO
    oop_limit: Decimal = ZERO
    oop_met: Decimal = ZERO


class MemberDataProvider:
    """Abstract data provider for member eligibility data.

    Concrete implementations query the member-management module via API
    or shared DB access. In unit tests, callers inject a mock.
    """

    async def get_member(self, tenant_id: uuid.UUID, member_id: str) -> MemberRecord | None:
        raise NotImplementedError  # pragma: no cover

    async def get_members(self, tenant_id: uuid.UUID, member_ids: list[str]) -> list[MemberRecord]:
        raise NotImplementedError  # pragma: no cover


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class EligibilityService:
    """Verifies member eligibility and returns benefit summary.

    Performance target: sub-500ms for single verification.
    """

    def __init__(self, data_provider: MemberDataProvider) -> None:
        self._data = data_provider

    async def verify_eligibility(
        self,
        tenant_id: uuid.UUID,
        member_id: str,
        as_of_date: date | None = None,
    ) -> EligibilityResult:
        """Verify a single member's eligibility as of a given date.

        Args:
            tenant_id: Tenant context for data isolation.
            member_id: Member identifier string.
            as_of_date: Date to check against. Defaults to today.

        Returns:
            EligibilityResult with status, coverage, and accumulator data.
        """
        check_date = as_of_date or date.today()
        start_ns = time.monotonic_ns()

        member = await self._data.get_member(tenant_id, member_id)
        if member is None:
            elapsed_ms = _elapsed_ms(start_ns)
            return EligibilityResult(
                member_id=member_id,
                status=EligibilityStatus.INACTIVE,
                response_time_ms=elapsed_ms,
            )

        result = self._evaluate(member, check_date)
        result.response_time_ms = _elapsed_ms(start_ns)

        if result.response_time_ms > RESPONSE_TIME_WARNING_MS:
            logger.warning(
                "Eligibility check exceeded %dms target",
                RESPONSE_TIME_WARNING_MS,
                extra={
                    "svc_name": "ebv.eligibility",
                    "ebv_member_id": member_id,
                    "ebv_response_ms": result.response_time_ms,
                },
            )

        return result

    async def batch_verify(
        self,
        tenant_id: uuid.UUID,
        member_ids: list[str],
        as_of_date: date | None = None,
    ) -> list[EligibilityResult]:
        """Verify eligibility for a batch of members.

        Fetches all members in one call to the data provider,
        then evaluates each individually.
        """
        check_date = as_of_date or date.today()
        start_ns = time.monotonic_ns()

        records = await self._data.get_members(tenant_id, member_ids)
        records_by_id = {r.member_id: r for r in records}

        results: list[EligibilityResult] = []
        for mid in member_ids:
            member = records_by_id.get(mid)
            if member is None:
                results.append(EligibilityResult(
                    member_id=mid,
                    status=EligibilityStatus.INACTIVE,
                ))
            else:
                results.append(self._evaluate(member, check_date))

        elapsed = _elapsed_ms(start_ns)
        for r in results:
            r.response_time_ms = elapsed

        return results

    def _evaluate(self, member: MemberRecord, check_date: date) -> EligibilityResult:
        """Core eligibility evaluation logic (pure, no I/O)."""
        status = self._determine_status(member, check_date)
        benefit_phase = self._detect_benefit_phase(member) if status == EligibilityStatus.ACTIVE else None
        deductible = self._build_accumulator_progress(member.deductible_limit, member.deductible_met)
        oop = self._build_accumulator_progress(member.oop_limit, member.oop_met)
        copay_summary = [
            CopayTier(
                tier=t.get("tier", ""),
                copay=money(t.get("copay", 0)),
                coinsurance_pct=money(t["coinsurance_pct"]) if t.get("coinsurance_pct") is not None else None,
            )
            for t in member.copay_tiers
        ]

        return EligibilityResult(
            member_id=member.member_id,
            status=status,
            plan_id=member.plan_id,
            plan_name=member.plan_name,
            group_id=member.group_id,
            group_name=member.group_name,
            coverage_start=member.coverage_start,
            coverage_end=member.coverage_end,
            copay_summary=copay_summary,
            benefit_phase=benefit_phase,
            deductible=deductible,
            oop=oop,
        )

    @staticmethod
    def _determine_status(member: MemberRecord, check_date: date) -> EligibilityStatus:
        """Determine member eligibility status as of check_date."""
        if member.status == "terminated":
            return EligibilityStatus.TERMINATED

        if member.status != "active":
            return EligibilityStatus.INACTIVE

        # Active member -- check coverage dates
        if member.coverage_start is not None and check_date < member.coverage_start:
            return EligibilityStatus.FUTURE_EFFECTIVE

        if member.coverage_end is not None and check_date > member.coverage_end:
            return EligibilityStatus.INACTIVE

        return EligibilityStatus.ACTIVE

    @staticmethod
    def _detect_benefit_phase(member: MemberRecord) -> BenefitPhase:
        """Detect benefit phase based on accumulator progress.

        Simple heuristic: if deductible not met -> DEDUCTIBLE phase,
        otherwise -> INITIAL_COVERAGE for commercial plans.
        Full Part D phase logic (gap/catastrophic) uses OOP thresholds.
        """
        deductible_limit = money(member.deductible_limit)
        deductible_met = money(member.deductible_met)
        oop_limit = money(member.oop_limit)
        oop_met = money(member.oop_met)

        if deductible_limit > ZERO and deductible_met < deductible_limit:
            return BenefitPhase.DEDUCTIBLE

        if oop_limit > ZERO and oop_met >= oop_limit:
            return BenefitPhase.CATASTROPHIC

        # Part D gap detection: OOP met > 75% of limit (simplified)
        if oop_limit > ZERO:
            gap_threshold = money(oop_limit * Decimal("0.75"))
            if oop_met >= gap_threshold:
                return BenefitPhase.COVERAGE_GAP

        return BenefitPhase.INITIAL_COVERAGE

    @staticmethod
    def _build_accumulator_progress(
        limit: Decimal,
        met: Decimal,
    ) -> AccumulatorProgress | None:
        """Build accumulator progress from limit/met values.

        Returns None if limit is zero (no accumulator configured).
        """
        limit_d = money(limit)
        met_d = money(met)

        if limit_d <= ZERO:
            return None

        remaining = money(limit_d - met_d)
        if remaining < ZERO:
            remaining = ZERO

        pct = (met_d / limit_d * Decimal("100")).quantize(
            TWO_PLACES, rounding=__import__("decimal").ROUND_HALF_UP
        )
        if pct > Decimal("100.00"):
            pct = Decimal("100.00")

        return AccumulatorProgress(
            limit=limit_d,
            met=met_d,
            remaining=remaining,
            pct_met=pct,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _elapsed_ms(start_ns: int) -> int:
    return (time.monotonic_ns() - start_ns) // 1_000_000
