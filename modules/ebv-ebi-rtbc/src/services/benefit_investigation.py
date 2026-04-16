"""Benefit investigation service for deep drug-level coverage analysis.

Determines formulary status, tier, PA/ST/QL requirements, member cost
estimates, therapeutic alternatives, and accumulator/maximizer detection.

Used by hub services and FRMs for pre-prescribing coverage analysis.
All money as Decimal with ROUND_HALF_UP. No floats.
"""
from __future__ import annotations

import logging
import uuid
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from shared.utils.money import ZERO, TWO_PLACES, money

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FormularyStatus(str, Enum):
    FORMULARY = "formulary"
    NON_FORMULARY = "non_formulary"
    EXCLUDED = "excluded"
    BRAND_PREFERRED = "brand_preferred"
    BRAND_NON_PREFERRED = "brand_non_preferred"
    GENERIC = "generic"
    SPECIALTY = "specialty"


class AccumulatorProgram(str, Enum):
    """Type of copay accumulator program in effect."""

    STANDARD = "standard"
    ACCUMULATOR = "accumulator"
    MAXIMIZER = "maximizer"


class QLType(str, Enum):
    """Quantity limit type."""

    PER_FILL = "per_fill"
    PER_MONTH = "per_month"
    PER_YEAR = "per_year"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CoverageRequirements(BaseModel):
    """PA, ST, QL requirement flags for a drug."""

    pa_required: bool = False
    st_required: bool = False
    ql_info: QLInfo | None = None


class QLInfo(BaseModel):
    """Quantity limit details."""

    ql_type: QLType
    max_quantity: Decimal
    days_supply: int


class AlternativeDrug(BaseModel):
    """A therapeutic alternative to the requested drug."""

    ndc: str
    name: str
    tier: str
    cost: Decimal
    savings: Decimal


class CostBreakdown(BaseModel):
    """Member cost estimate breakdown."""

    copay: Decimal = ZERO
    coinsurance: Decimal = ZERO
    deductible_applied: Decimal = ZERO
    total_member_cost: Decimal = ZERO


class BenefitResult(BaseModel):
    """Complete benefit investigation result for a drug/member."""

    member_id: str
    drug_ndc: str
    is_covered: bool
    formulary_status: FormularyStatus | None = None
    tier: str | None = None
    requirements: CoverageRequirements = Field(default_factory=CoverageRequirements)
    cost_breakdown: CostBreakdown = Field(default_factory=CostBreakdown)
    member_cost_estimate: Decimal = ZERO
    alternatives: list[AlternativeDrug] = Field(default_factory=list)
    specialty_pharmacy_required: bool = False
    site_of_care: str | None = None
    accumulator_status: AccumulatorProgram = AccumulatorProgram.STANDARD


# Resolve forward reference for QLInfo in CoverageRequirements
CoverageRequirements.model_rebuild()


# ---------------------------------------------------------------------------
# Data protocol (dependency-injected)
# ---------------------------------------------------------------------------


class DrugFormularyRecord(BaseModel):
    """Drug formulary data fetched from the drug-database module."""

    ndc: str
    drug_name: str
    formulary_status: str
    tier: str
    pa_required: bool = False
    st_required: bool = False
    ql_type: str | None = None
    ql_max_quantity: Decimal | None = None
    ql_days_supply: int | None = None
    is_specialty: bool = False
    specialty_pharmacy_required: bool = False
    site_of_care: str | None = None


class MemberBenefitRecord(BaseModel):
    """Member benefit data for cost calculation."""

    member_id: str
    plan_id: uuid.UUID | None = None
    copay_amount: Decimal = ZERO
    coinsurance_pct: Decimal = ZERO
    deductible_remaining: Decimal = ZERO
    oop_remaining: Decimal = ZERO
    accumulator_type: str = "standard"
    drug_cost: Decimal = ZERO


class BenefitDataProvider:
    """Abstract data provider for benefit investigation data.

    Concrete implementations call drug-database and member-management
    modules via API. Unit tests inject mocks.
    """

    async def get_drug_formulary(
        self, tenant_id: uuid.UUID, drug_ndc: str, plan_id: uuid.UUID | None
    ) -> DrugFormularyRecord | None:
        raise NotImplementedError  # pragma: no cover

    async def get_member_benefit(
        self, tenant_id: uuid.UUID, member_id: str, drug_ndc: str
    ) -> MemberBenefitRecord | None:
        raise NotImplementedError  # pragma: no cover

    async def get_alternatives(
        self, tenant_id: uuid.UUID, drug_ndc: str, plan_id: uuid.UUID | None
    ) -> list[AlternativeDrug]:
        raise NotImplementedError  # pragma: no cover


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class BenefitInvestigationService:
    """Deep benefit analysis for a drug/member combination.

    Determines coverage, cost, requirements, and alternatives.
    """

    def __init__(self, data_provider: BenefitDataProvider) -> None:
        self._data = data_provider

    async def investigate_benefit(
        self,
        tenant_id: uuid.UUID,
        member_id: str,
        drug_ndc: str,
        plan_id: uuid.UUID | None = None,
    ) -> BenefitResult:
        """Perform a full benefit investigation for a drug/member.

        Args:
            tenant_id: Tenant context.
            member_id: Member identifier.
            drug_ndc: 11-digit NDC.
            plan_id: Optional plan override.

        Returns:
            BenefitResult with coverage, cost, requirements, alternatives.
        """
        formulary = await self._data.get_drug_formulary(tenant_id, drug_ndc, plan_id)
        if formulary is None:
            return BenefitResult(
                member_id=member_id,
                drug_ndc=drug_ndc,
                is_covered=False,
                formulary_status=FormularyStatus.NON_FORMULARY,
            )

        member_benefit = await self._data.get_member_benefit(tenant_id, member_id, drug_ndc)
        alternatives = await self._data.get_alternatives(tenant_id, drug_ndc, plan_id)

        is_covered = self._is_drug_covered(formulary)
        formulary_status = self._map_formulary_status(formulary.formulary_status)
        requirements = self._build_requirements(formulary)
        cost_breakdown = self._calculate_cost(formulary, member_benefit)
        accumulator_status = self._detect_accumulator(member_benefit)

        # Sort alternatives by savings descending
        sorted_alternatives = sorted(alternatives, key=lambda a: a.savings, reverse=True)

        return BenefitResult(
            member_id=member_id,
            drug_ndc=drug_ndc,
            is_covered=is_covered,
            formulary_status=formulary_status,
            tier=formulary.tier,
            requirements=requirements,
            cost_breakdown=cost_breakdown,
            member_cost_estimate=cost_breakdown.total_member_cost,
            alternatives=sorted_alternatives,
            specialty_pharmacy_required=formulary.specialty_pharmacy_required,
            site_of_care=formulary.site_of_care,
            accumulator_status=accumulator_status,
        )

    @staticmethod
    def _is_drug_covered(formulary: DrugFormularyRecord) -> bool:
        """Determine if drug is covered based on formulary status."""
        excluded = {"excluded", "non_formulary"}
        return formulary.formulary_status.lower() not in excluded

    @staticmethod
    def _map_formulary_status(raw: str) -> FormularyStatus:
        """Map raw formulary status string to enum."""
        mapping = {
            "formulary": FormularyStatus.FORMULARY,
            "non_formulary": FormularyStatus.NON_FORMULARY,
            "excluded": FormularyStatus.EXCLUDED,
            "brand_preferred": FormularyStatus.BRAND_PREFERRED,
            "brand_non_preferred": FormularyStatus.BRAND_NON_PREFERRED,
            "generic": FormularyStatus.GENERIC,
            "specialty": FormularyStatus.SPECIALTY,
        }
        return mapping.get(raw.lower(), FormularyStatus.NON_FORMULARY)

    @staticmethod
    def _build_requirements(formulary: DrugFormularyRecord) -> CoverageRequirements:
        """Build coverage requirements from formulary record."""
        ql_info = None
        if formulary.ql_type and formulary.ql_max_quantity is not None and formulary.ql_days_supply is not None:
            ql_info = QLInfo(
                ql_type=QLType(formulary.ql_type),
                max_quantity=money(formulary.ql_max_quantity),
                days_supply=formulary.ql_days_supply,
            )

        return CoverageRequirements(
            pa_required=formulary.pa_required,
            st_required=formulary.st_required,
            ql_info=ql_info,
        )

    @staticmethod
    def _calculate_cost(
        formulary: DrugFormularyRecord,
        member_benefit: MemberBenefitRecord | None,
    ) -> CostBreakdown:
        """Calculate member cost breakdown.

        Applies deductible first, then copay or coinsurance (whichever applies).
        All arithmetic uses Decimal with ROUND_HALF_UP.
        """
        if member_benefit is None:
            return CostBreakdown()

        drug_cost = money(member_benefit.drug_cost)
        deductible_remaining = money(member_benefit.deductible_remaining)
        copay_amount = money(member_benefit.copay_amount)
        coinsurance_pct = member_benefit.coinsurance_pct

        # Apply deductible first
        deductible_applied = ZERO
        cost_after_deductible = drug_cost

        if deductible_remaining > ZERO:
            deductible_applied = min(drug_cost, deductible_remaining)
            deductible_applied = money(deductible_applied)
            cost_after_deductible = money(drug_cost - deductible_applied)

        # Apply copay or coinsurance on remaining
        copay = ZERO
        coinsurance = ZERO

        if copay_amount > ZERO:
            copay = min(copay_amount, cost_after_deductible)
            copay = money(copay)
        elif coinsurance_pct > ZERO:
            coinsurance = money(
                cost_after_deductible * coinsurance_pct / Decimal("100")
            )

        total = money(deductible_applied + copay + coinsurance)

        return CostBreakdown(
            copay=copay,
            coinsurance=coinsurance,
            deductible_applied=deductible_applied,
            total_member_cost=total,
        )

    @staticmethod
    def _detect_accumulator(member_benefit: MemberBenefitRecord | None) -> AccumulatorProgram:
        """Detect accumulator/maximizer program status."""
        if member_benefit is None:
            return AccumulatorProgram.STANDARD

        mapping = {
            "standard": AccumulatorProgram.STANDARD,
            "accumulator": AccumulatorProgram.ACCUMULATOR,
            "maximizer": AccumulatorProgram.MAXIMIZER,
        }
        return mapping.get(
            member_benefit.accumulator_type.lower(),
            AccumulatorProgram.STANDARD,
        )
