"""Tests for benefit investigation service.

Covers: covered drug returns tier/cost, non-formulary flagged, PA/ST/QL
requirements, alternatives sorted by savings, accumulator status detection,
specialty pharmacy flag. All costs verified as Decimal.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from src.services.benefit_investigation import (
    AccumulatorProgram,
    AlternativeDrug,
    BenefitDataProvider,
    BenefitInvestigationService,
    BenefitResult,
    CostBreakdown,
    CoverageRequirements,
    DrugFormularyRecord,
    FormularyStatus,
    MemberBenefitRecord,
    QLInfo,
    QLType,
)

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
PLAN_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _formulary(
    *,
    formulary_status: str = "formulary",
    tier: str = "1",
    pa_required: bool = False,
    st_required: bool = False,
    ql_type: str | None = None,
    ql_max_quantity: Decimal | None = None,
    ql_days_supply: int | None = None,
    is_specialty: bool = False,
    specialty_pharmacy_required: bool = False,
    site_of_care: str | None = None,
) -> DrugFormularyRecord:
    return DrugFormularyRecord(
        ndc="12345678901",
        drug_name="Atorvastatin 40mg",
        formulary_status=formulary_status,
        tier=tier,
        pa_required=pa_required,
        st_required=st_required,
        ql_type=ql_type,
        ql_max_quantity=ql_max_quantity,
        ql_days_supply=ql_days_supply,
        is_specialty=is_specialty,
        specialty_pharmacy_required=specialty_pharmacy_required,
        site_of_care=site_of_care,
    )


def _member_benefit(
    *,
    copay_amount: Decimal = Decimal("10.00"),
    coinsurance_pct: Decimal = Decimal("0"),
    deductible_remaining: Decimal = Decimal("0.00"),
    oop_remaining: Decimal = Decimal("3000.00"),
    accumulator_type: str = "standard",
    drug_cost: Decimal = Decimal("150.00"),
) -> MemberBenefitRecord:
    return MemberBenefitRecord(
        member_id="M123456",
        plan_id=PLAN_ID,
        copay_amount=copay_amount,
        coinsurance_pct=coinsurance_pct,
        deductible_remaining=deductible_remaining,
        oop_remaining=oop_remaining,
        accumulator_type=accumulator_type,
        drug_cost=drug_cost,
    )


def _alternatives() -> list[AlternativeDrug]:
    return [
        AlternativeDrug(ndc="99999999901", name="Generic A", tier="1", cost=Decimal("8.00"), savings=Decimal("142.00")),
        AlternativeDrug(ndc="99999999902", name="Generic B", tier="1", cost=Decimal("12.00"), savings=Decimal("138.00")),
        AlternativeDrug(ndc="99999999903", name="Brand Alt", tier="2", cost=Decimal("50.00"), savings=Decimal("100.00")),
    ]


def _mock_provider(
    formulary: DrugFormularyRecord | None = None,
    member_benefit: MemberBenefitRecord | None = None,
    alternatives: list[AlternativeDrug] | None = None,
) -> BenefitDataProvider:
    provider = BenefitDataProvider()
    provider.get_drug_formulary = AsyncMock(return_value=formulary)
    provider.get_member_benefit = AsyncMock(return_value=member_benefit)
    provider.get_alternatives = AsyncMock(return_value=alternatives or [])
    return provider


# ---------------------------------------------------------------------------
# Covered drug returns tier and cost
# ---------------------------------------------------------------------------


class TestCoveredDrug:
    @pytest.mark.asyncio
    async def test_formulary_drug_is_covered(self):
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(),
                member_benefit=_member_benefit(),
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert result.is_covered is True
        assert result.formulary_status == FormularyStatus.FORMULARY
        assert result.tier == "1"

    @pytest.mark.asyncio
    async def test_covered_drug_has_cost_estimate(self):
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(),
                member_benefit=_member_benefit(copay_amount=Decimal("25.00")),
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert result.member_cost_estimate == Decimal("25.00")
        assert result.cost_breakdown.copay == Decimal("25.00")

    @pytest.mark.asyncio
    async def test_brand_preferred_is_covered(self):
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(formulary_status="brand_preferred", tier="2"),
                member_benefit=_member_benefit(),
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert result.is_covered is True
        assert result.formulary_status == FormularyStatus.BRAND_PREFERRED

    @pytest.mark.asyncio
    async def test_generic_drug_tier(self):
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(formulary_status="generic", tier="1"),
                member_benefit=_member_benefit(copay_amount=Decimal("5.00")),
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert result.formulary_status == FormularyStatus.GENERIC
        assert result.member_cost_estimate == Decimal("5.00")


# ---------------------------------------------------------------------------
# Non-formulary drug flagged
# ---------------------------------------------------------------------------


class TestNonFormularyDrug:
    @pytest.mark.asyncio
    async def test_drug_not_in_formulary_returns_not_covered(self):
        """Drug not found in formulary database -> non-formulary."""
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(formulary=None)
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "00000000000")

        assert result.is_covered is False
        assert result.formulary_status == FormularyStatus.NON_FORMULARY

    @pytest.mark.asyncio
    async def test_excluded_drug_not_covered(self):
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(formulary_status="excluded"),
                member_benefit=_member_benefit(),
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert result.is_covered is False
        assert result.formulary_status == FormularyStatus.EXCLUDED

    @pytest.mark.asyncio
    async def test_non_formulary_status_not_covered(self):
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(formulary_status="non_formulary"),
                member_benefit=_member_benefit(),
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert result.is_covered is False
        assert result.formulary_status == FormularyStatus.NON_FORMULARY


# ---------------------------------------------------------------------------
# PA / ST / QL requirements returned
# ---------------------------------------------------------------------------


class TestRequirements:
    @pytest.mark.asyncio
    async def test_pa_required_returned(self):
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(pa_required=True),
                member_benefit=_member_benefit(),
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert result.requirements.pa_required is True

    @pytest.mark.asyncio
    async def test_st_required_returned(self):
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(st_required=True),
                member_benefit=_member_benefit(),
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert result.requirements.st_required is True

    @pytest.mark.asyncio
    async def test_ql_info_returned(self):
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(
                    ql_type="per_fill",
                    ql_max_quantity=Decimal("90"),
                    ql_days_supply=30,
                ),
                member_benefit=_member_benefit(),
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert result.requirements.ql_info is not None
        assert result.requirements.ql_info.ql_type == QLType.PER_FILL
        assert result.requirements.ql_info.max_quantity == Decimal("90.00")
        assert result.requirements.ql_info.days_supply == 30

    @pytest.mark.asyncio
    async def test_no_requirements_when_none_set(self):
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(),
                member_benefit=_member_benefit(),
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert result.requirements.pa_required is False
        assert result.requirements.st_required is False
        assert result.requirements.ql_info is None

    @pytest.mark.asyncio
    async def test_all_requirements_combined(self):
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(
                    pa_required=True,
                    st_required=True,
                    ql_type="per_month",
                    ql_max_quantity=Decimal("60"),
                    ql_days_supply=30,
                ),
                member_benefit=_member_benefit(),
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert result.requirements.pa_required is True
        assert result.requirements.st_required is True
        assert result.requirements.ql_info is not None


# ---------------------------------------------------------------------------
# Alternatives sorted by savings
# ---------------------------------------------------------------------------


class TestAlternatives:
    @pytest.mark.asyncio
    async def test_alternatives_sorted_by_savings_descending(self):
        alts = _alternatives()
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(),
                member_benefit=_member_benefit(),
                alternatives=alts,
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert len(result.alternatives) == 3
        assert result.alternatives[0].savings >= result.alternatives[1].savings
        assert result.alternatives[1].savings >= result.alternatives[2].savings
        assert result.alternatives[0].name == "Generic A"

    @pytest.mark.asyncio
    async def test_no_alternatives_returns_empty_list(self):
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(),
                member_benefit=_member_benefit(),
                alternatives=[],
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert result.alternatives == []


# ---------------------------------------------------------------------------
# Accumulator status correctly detected
# ---------------------------------------------------------------------------


class TestAccumulatorDetection:
    @pytest.mark.asyncio
    async def test_standard_accumulator(self):
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(),
                member_benefit=_member_benefit(accumulator_type="standard"),
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert result.accumulator_status == AccumulatorProgram.STANDARD

    @pytest.mark.asyncio
    async def test_accumulator_program_detected(self):
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(),
                member_benefit=_member_benefit(accumulator_type="accumulator"),
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert result.accumulator_status == AccumulatorProgram.ACCUMULATOR

    @pytest.mark.asyncio
    async def test_maximizer_program_detected(self):
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(),
                member_benefit=_member_benefit(accumulator_type="maximizer"),
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert result.accumulator_status == AccumulatorProgram.MAXIMIZER

    @pytest.mark.asyncio
    async def test_unknown_accumulator_defaults_to_standard(self):
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(),
                member_benefit=_member_benefit(accumulator_type="unknown_program"),
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert result.accumulator_status == AccumulatorProgram.STANDARD

    @pytest.mark.asyncio
    async def test_no_member_benefit_defaults_standard(self):
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(),
                member_benefit=None,
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert result.accumulator_status == AccumulatorProgram.STANDARD


# ---------------------------------------------------------------------------
# Specialty pharmacy required flag
# ---------------------------------------------------------------------------


class TestSpecialtyPharmacy:
    @pytest.mark.asyncio
    async def test_specialty_pharmacy_required(self):
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(
                    specialty_pharmacy_required=True,
                    site_of_care="specialty_pharmacy",
                ),
                member_benefit=_member_benefit(),
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert result.specialty_pharmacy_required is True
        assert result.site_of_care == "specialty_pharmacy"

    @pytest.mark.asyncio
    async def test_non_specialty_drug(self):
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(specialty_pharmacy_required=False),
                member_benefit=_member_benefit(),
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert result.specialty_pharmacy_required is False
        assert result.site_of_care is None


# ---------------------------------------------------------------------------
# All costs are Decimal
# ---------------------------------------------------------------------------


class TestDecimalPrecision:
    @pytest.mark.asyncio
    async def test_all_cost_fields_are_decimal(self):
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(),
                member_benefit=_member_benefit(
                    copay_amount=Decimal("25.00"),
                    deductible_remaining=Decimal("100.00"),
                    drug_cost=Decimal("200.00"),
                ),
                alternatives=_alternatives(),
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert isinstance(result.member_cost_estimate, Decimal)
        assert isinstance(result.cost_breakdown.copay, Decimal)
        assert isinstance(result.cost_breakdown.coinsurance, Decimal)
        assert isinstance(result.cost_breakdown.deductible_applied, Decimal)
        assert isinstance(result.cost_breakdown.total_member_cost, Decimal)

        for alt in result.alternatives:
            assert isinstance(alt.cost, Decimal)
            assert isinstance(alt.savings, Decimal)

    @pytest.mark.asyncio
    async def test_deductible_then_copay_calculation(self):
        """When deductible remaining > 0, deductible applied first, then copay on remainder."""
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(),
                member_benefit=_member_benefit(
                    copay_amount=Decimal("25.00"),
                    deductible_remaining=Decimal("50.00"),
                    drug_cost=Decimal("200.00"),
                ),
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        # $50 deductible + $25 copay (on $150 remainder) = $75
        assert result.cost_breakdown.deductible_applied == Decimal("50.00")
        assert result.cost_breakdown.copay == Decimal("25.00")
        assert result.cost_breakdown.total_member_cost == Decimal("75.00")

    @pytest.mark.asyncio
    async def test_coinsurance_calculation(self):
        """Coinsurance applied on cost after deductible."""
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(),
                member_benefit=_member_benefit(
                    copay_amount=Decimal("0.00"),
                    coinsurance_pct=Decimal("20"),
                    deductible_remaining=Decimal("0.00"),
                    drug_cost=Decimal("100.00"),
                ),
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        # 20% of $100 = $20
        assert result.cost_breakdown.coinsurance == Decimal("20.00")
        assert result.cost_breakdown.total_member_cost == Decimal("20.00")

    @pytest.mark.asyncio
    async def test_no_member_benefit_returns_zero_cost(self):
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(),
                member_benefit=None,
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        assert result.cost_breakdown.total_member_cost == Decimal("0.00")
        assert result.member_cost_estimate == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_deductible_exceeds_drug_cost(self):
        """When deductible remaining > drug cost, member pays full drug cost as deductible."""
        svc = BenefitInvestigationService(
            data_provider=_mock_provider(
                formulary=_formulary(),
                member_benefit=_member_benefit(
                    copay_amount=Decimal("25.00"),
                    deductible_remaining=Decimal("500.00"),
                    drug_cost=Decimal("100.00"),
                ),
            )
        )
        result = await svc.investigate_benefit(TENANT_ID, "M123456", "12345678901")

        # Full $100 goes to deductible, $0 remainder for copay
        assert result.cost_breakdown.deductible_applied == Decimal("100.00")
        assert result.cost_breakdown.copay == Decimal("0.00")
        assert result.cost_breakdown.total_member_cost == Decimal("100.00")
