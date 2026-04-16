"""Tests for member tools service.

Covers: cost estimate matches benefit investigation, pharmacy comparison
returns sorted results, benefit progress percentages correct, digital ID
card has all required fields.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.benefit_investigation import (
    AccumulatorProgram,
    AlternativeDrug,
    BenefitDataProvider,
    BenefitInvestigationService,
    BenefitResult,
    CostBreakdown,
    CoverageRequirements,
    FormularyStatus,
)
from src.services.eligibility import (
    AccumulatorProgress,
    BenefitPhase,
    EligibilityResult,
    EligibilityService,
    EligibilityStatus,
    MemberDataProvider,
    MemberRecord,
)
from src.services.member_tools import (
    AlternativeOption,
    BenefitProgressResult,
    DigitalIDCardData,
    DrugCostEstimate,
    IDCardDataProvider,
    MemberToolsService,
    PharmacyCostResult,
    PharmacyDataProvider,
    PharmacyOption,
)

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _benefit_result(
    member_cost: Decimal = Decimal("25.00"),
    alternatives: list[AlternativeDrug] | None = None,
) -> BenefitResult:
    return BenefitResult(
        member_id="M123456",
        drug_ndc="12345678901",
        is_covered=True,
        formulary_status=FormularyStatus.FORMULARY,
        tier="1",
        requirements=CoverageRequirements(),
        cost_breakdown=CostBreakdown(
            copay=member_cost,
            total_member_cost=member_cost,
        ),
        member_cost_estimate=member_cost,
        alternatives=alternatives or [],
    )


def _eligibility_result(
    status: EligibilityStatus = EligibilityStatus.ACTIVE,
    deductible: AccumulatorProgress | None = None,
    oop: AccumulatorProgress | None = None,
) -> EligibilityResult:
    return EligibilityResult(
        member_id="M123456",
        status=status,
        plan_id=uuid.uuid4(),
        plan_name="Basic Rx",
        coverage_start=date(2026, 1, 1),
        coverage_end=date(2026, 12, 31),
        benefit_phase=BenefitPhase.INITIAL_COVERAGE if status == EligibilityStatus.ACTIVE else None,
        deductible=deductible,
        oop=oop,
    )


def _make_service(
    benefit_result: BenefitResult | None = None,
    eligibility_result: EligibilityResult | None = None,
    pharmacies: list[PharmacyOption] | None = None,
    card_data: DigitalIDCardData | None = None,
) -> MemberToolsService:
    # Eligibility service mock
    elig_provider = MemberDataProvider()
    elig_svc = EligibilityService(data_provider=elig_provider)
    elig_svc.verify_eligibility = AsyncMock(
        return_value=eligibility_result or _eligibility_result()
    )

    # Benefit investigation service mock
    ben_provider = BenefitDataProvider()
    ben_svc = BenefitInvestigationService(data_provider=ben_provider)
    ben_svc.investigate_benefit = AsyncMock(
        return_value=benefit_result or _benefit_result()
    )

    # Pharmacy provider mock
    pharm_provider = PharmacyDataProvider()
    pharm_provider.get_nearby_pharmacies = AsyncMock(return_value=pharmacies or [])

    # ID card provider mock
    card_provider = IDCardDataProvider()
    card_provider.get_card_data = AsyncMock(return_value=card_data)

    return MemberToolsService(
        eligibility_service=elig_svc,
        benefit_service=ben_svc,
        pharmacy_provider=pharm_provider,
        id_card_provider=card_provider,
    )


# ---------------------------------------------------------------------------
# Cost estimate matches benefit investigation
# ---------------------------------------------------------------------------


class TestDrugCostEstimate:
    @pytest.mark.asyncio
    async def test_cost_estimate_matches_benefit_cost(self):
        """drug_cost_estimate returns the same cost as investigate_benefit."""
        ben_result = _benefit_result(member_cost=Decimal("35.00"))
        svc = _make_service(benefit_result=ben_result)

        estimate = await svc.drug_cost_estimate(TENANT_ID, "M123456", "12345678901")

        assert estimate.estimated_cost == Decimal("35.00")
        assert estimate.member_id == "M123456"
        assert estimate.drug_ndc == "12345678901"

    @pytest.mark.asyncio
    async def test_cost_estimate_includes_tier_and_status(self):
        svc = _make_service(benefit_result=_benefit_result())
        estimate = await svc.drug_cost_estimate(TENANT_ID, "M123456", "12345678901")

        assert estimate.tier == "1"
        assert estimate.formulary_status == "formulary"

    @pytest.mark.asyncio
    async def test_cost_estimate_includes_alternatives(self):
        alts = [
            AlternativeDrug(ndc="99999999901", name="Generic A", tier="1", cost=Decimal("8.00"), savings=Decimal("17.00")),
            AlternativeDrug(ndc="99999999902", name="Generic B", tier="1", cost=Decimal("12.00"), savings=Decimal("13.00")),
        ]
        ben_result = _benefit_result(alternatives=alts)
        svc = _make_service(benefit_result=ben_result)

        estimate = await svc.drug_cost_estimate(TENANT_ID, "M123456", "12345678901")

        assert len(estimate.alternatives) == 2
        assert estimate.alternatives[0].ndc == "99999999901"
        assert isinstance(estimate.alternatives[0].cost, Decimal)
        assert isinstance(estimate.alternatives[0].savings, Decimal)

    @pytest.mark.asyncio
    async def test_cost_estimate_all_money_is_decimal(self):
        svc = _make_service()
        estimate = await svc.drug_cost_estimate(TENANT_ID, "M123456", "12345678901")

        assert isinstance(estimate.estimated_cost, Decimal)


# ---------------------------------------------------------------------------
# Pharmacy comparison returns sorted results
# ---------------------------------------------------------------------------


class TestPharmacyCostComparison:
    @pytest.mark.asyncio
    async def test_pharmacies_sorted_by_distance(self):
        pharmacies = [
            PharmacyOption(npi="1234567890", name="Far Pharmacy", distance_mi=Decimal("10.5"), cost=Decimal("25.00"), in_network=True, preferred=False),
            PharmacyOption(npi="0987654321", name="Near Pharmacy", distance_mi=Decimal("1.2"), cost=Decimal("30.00"), in_network=True, preferred=True),
            PharmacyOption(npi="5555555555", name="Mid Pharmacy", distance_mi=Decimal("5.0"), cost=Decimal("22.00"), in_network=True, preferred=False),
        ]
        svc = _make_service(pharmacies=pharmacies)
        result = await svc.pharmacy_cost_comparison(
            TENANT_ID, "M123456", "12345678901",
            lat=Decimal("40.7128"), lng=Decimal("-74.0060"),
        )

        assert len(result.pharmacies) == 3
        assert result.pharmacies[0].name == "Near Pharmacy"
        assert result.pharmacies[1].name == "Mid Pharmacy"
        assert result.pharmacies[2].name == "Far Pharmacy"

    @pytest.mark.asyncio
    async def test_pharmacy_result_has_member_and_ndc(self):
        svc = _make_service(pharmacies=[])
        result = await svc.pharmacy_cost_comparison(
            TENANT_ID, "M123456", "12345678901",
            lat=Decimal("40.7128"), lng=Decimal("-74.0060"),
        )

        assert result.member_id == "M123456"
        assert result.drug_ndc == "12345678901"

    @pytest.mark.asyncio
    async def test_pharmacy_empty_results(self):
        svc = _make_service(pharmacies=[])
        result = await svc.pharmacy_cost_comparison(
            TENANT_ID, "M123456", "12345678901",
            lat=Decimal("40.7128"), lng=Decimal("-74.0060"),
        )

        assert result.pharmacies == []

    @pytest.mark.asyncio
    async def test_pharmacy_cost_is_decimal(self):
        pharmacies = [
            PharmacyOption(npi="1234567890", name="Test Pharmacy", distance_mi=Decimal("2.0"), cost=Decimal("45.50"), in_network=True, preferred=True),
        ]
        svc = _make_service(pharmacies=pharmacies)
        result = await svc.pharmacy_cost_comparison(
            TENANT_ID, "M123456", "12345678901",
            lat=Decimal("40.7128"), lng=Decimal("-74.0060"),
        )

        assert isinstance(result.pharmacies[0].cost, Decimal)
        assert isinstance(result.pharmacies[0].distance_mi, Decimal)


# ---------------------------------------------------------------------------
# Benefit progress percentages calculated correctly
# ---------------------------------------------------------------------------


class TestBenefitProgress:
    @pytest.mark.asyncio
    async def test_progress_returns_deductible_and_oop(self):
        elig = _eligibility_result(
            deductible=AccumulatorProgress(
                limit=Decimal("500.00"),
                met=Decimal("200.00"),
                remaining=Decimal("300.00"),
                pct_met=Decimal("40.00"),
            ),
            oop=AccumulatorProgress(
                limit=Decimal("5000.00"),
                met=Decimal("1200.00"),
                remaining=Decimal("3800.00"),
                pct_met=Decimal("24.00"),
            ),
        )
        svc = _make_service(eligibility_result=elig)
        result = await svc.benefit_progress(TENANT_ID, "M123456")

        assert result.deductible is not None
        assert result.deductible.pct_met == Decimal("40.00")
        assert result.oop is not None
        assert result.oop.pct_met == Decimal("24.00")

    @pytest.mark.asyncio
    async def test_progress_includes_benefit_year_dates(self):
        elig = _eligibility_result()
        svc = _make_service(eligibility_result=elig)
        result = await svc.benefit_progress(TENANT_ID, "M123456")

        assert result.benefit_year_start == date(2026, 1, 1)
        assert result.benefit_year_end == date(2026, 12, 31)

    @pytest.mark.asyncio
    async def test_inactive_member_returns_empty_progress(self):
        elig = _eligibility_result(status=EligibilityStatus.INACTIVE)
        svc = _make_service(eligibility_result=elig)
        result = await svc.benefit_progress(TENANT_ID, "M123456")

        assert result.deductible is None
        assert result.oop is None

    @pytest.mark.asyncio
    async def test_progress_values_are_decimal(self):
        elig = _eligibility_result(
            deductible=AccumulatorProgress(
                limit=Decimal("500.00"),
                met=Decimal("250.00"),
                remaining=Decimal("250.00"),
                pct_met=Decimal("50.00"),
            ),
        )
        svc = _make_service(eligibility_result=elig)
        result = await svc.benefit_progress(TENANT_ID, "M123456")

        assert isinstance(result.deductible.pct_met, Decimal)
        assert isinstance(result.deductible.limit, Decimal)
        assert isinstance(result.deductible.met, Decimal)
        assert isinstance(result.deductible.remaining, Decimal)


# ---------------------------------------------------------------------------
# Digital ID card has all required fields
# ---------------------------------------------------------------------------


class TestDigitalIDCard:
    @pytest.mark.asyncio
    async def test_card_has_all_required_fields(self):
        card = DigitalIDCardData(
            member_id="M123456",
            member_name="John Doe",
            group="ACME-001",
            bin="610014",
            pcn="MEDCO",
            rxbin="610014",
            copays={"tier1": Decimal("10.00"), "tier2": Decimal("35.00")},
            pharmacy_help_phone="1-800-555-0100",
            version=2,
        )
        svc = _make_service(card_data=card)
        result = await svc.digital_id_card(TENANT_ID, "M123456")

        assert result is not None
        assert result.member_id == "M123456"
        assert result.member_name == "John Doe"
        assert result.group == "ACME-001"
        assert result.bin == "610014"
        assert result.pcn == "MEDCO"
        assert result.rxbin == "610014"
        assert result.pharmacy_help_phone == "1-800-555-0100"
        assert result.version == 2

    @pytest.mark.asyncio
    async def test_card_copays_are_decimal(self):
        card = DigitalIDCardData(
            member_id="M123456",
            member_name="John Doe",
            group="ACME-001",
            bin="610014",
            pcn="MEDCO",
            rxbin="610014",
            copays={"tier1": Decimal("10.00"), "tier2": Decimal("35.50")},
            pharmacy_help_phone="1-800-555-0100",
        )
        svc = _make_service(card_data=card)
        result = await svc.digital_id_card(TENANT_ID, "M123456")

        assert isinstance(result.copays["tier1"], Decimal)
        assert isinstance(result.copays["tier2"], Decimal)

    @pytest.mark.asyncio
    async def test_card_not_found_returns_none(self):
        svc = _make_service(card_data=None)
        result = await svc.digital_id_card(TENANT_ID, "MISSING")

        assert result is None

    @pytest.mark.asyncio
    async def test_card_default_version_is_one(self):
        card = DigitalIDCardData(
            member_id="M123456",
            member_name="Jane Doe",
            group="ACME-001",
            bin="610014",
            pcn="MEDCO",
            rxbin="610014",
            copays={},
            pharmacy_help_phone="1-800-555-0100",
        )
        svc = _make_service(card_data=card)
        result = await svc.digital_id_card(TENANT_ID, "M123456")

        assert result.version == 1
