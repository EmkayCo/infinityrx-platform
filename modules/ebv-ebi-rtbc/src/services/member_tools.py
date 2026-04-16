"""Consumer-facing member tools: cost estimates, pharmacy comparison, benefit progress, digital ID card.

All money as Decimal with ROUND_HALF_UP. No floats.
"""
from __future__ import annotations

import math
import uuid
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, Field

from shared.utils.money import ZERO, TWO_PLACES, money

from .benefit_investigation import (
    BenefitDataProvider,
    BenefitInvestigationService,
    BenefitResult,
)
from .eligibility import (
    AccumulatorProgress,
    EligibilityService,
    EligibilityStatus,
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class DrugCostEstimate(BaseModel):
    """Cost estimate for a drug under a member's plan, with alternatives."""

    member_id: str
    drug_ndc: str
    estimated_cost: Decimal = ZERO
    tier: str | None = None
    formulary_status: str | None = None
    alternatives: list[AlternativeOption] = Field(default_factory=list)


class AlternativeOption(BaseModel):
    """Lower-cost alternative drug option."""

    ndc: str
    name: str
    tier: str
    cost: Decimal
    savings: Decimal


# Rebuild for forward ref
DrugCostEstimate.model_rebuild()


class PharmacyOption(BaseModel):
    """A pharmacy with pricing for a specific drug."""

    npi: str
    name: str
    distance_mi: Decimal
    cost: Decimal
    in_network: bool
    preferred: bool


class PharmacyCostResult(BaseModel):
    """Pharmacy cost comparison sorted by distance."""

    member_id: str
    drug_ndc: str
    pharmacies: list[PharmacyOption] = Field(default_factory=list)


class BenefitProgressResult(BaseModel):
    """Member's deductible and OOP progress with projected trajectory."""

    member_id: str
    deductible: AccumulatorProgress | None = None
    oop: AccumulatorProgress | None = None
    benefit_year_start: date | None = None
    benefit_year_end: date | None = None
    projected_deductible_met_date: date | None = None
    projected_oop_met_date: date | None = None


class DigitalIDCardData(BaseModel):
    """Digital ID card fields for display."""

    member_id: str
    member_name: str
    group: str
    bin: str
    pcn: str
    rxbin: str
    copays: dict[str, Decimal] = Field(default_factory=dict)
    pharmacy_help_phone: str
    version: int = 1


# ---------------------------------------------------------------------------
# Data providers
# ---------------------------------------------------------------------------


class PharmacyDataProvider:
    """Abstract provider for pharmacy location and pricing data."""

    async def get_nearby_pharmacies(
        self,
        tenant_id: uuid.UUID,
        drug_ndc: str,
        member_id: str,
        lat: Decimal,
        lng: Decimal,
        radius_mi: Decimal = Decimal("25"),
    ) -> list[PharmacyOption]:
        raise NotImplementedError  # pragma: no cover


class IDCardDataProvider:
    """Abstract provider for digital ID card data."""

    async def get_card_data(
        self,
        tenant_id: uuid.UUID,
        member_id: str,
    ) -> DigitalIDCardData | None:
        raise NotImplementedError  # pragma: no cover


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class MemberToolsService:
    """Consumer-facing tools for members: cost, pharmacy compare, progress, ID card."""

    def __init__(
        self,
        eligibility_service: EligibilityService,
        benefit_service: BenefitInvestigationService,
        pharmacy_provider: PharmacyDataProvider,
        id_card_provider: IDCardDataProvider,
    ) -> None:
        self._eligibility = eligibility_service
        self._benefit = benefit_service
        self._pharmacy = pharmacy_provider
        self._id_card = id_card_provider

    async def drug_cost_estimate(
        self,
        tenant_id: uuid.UUID,
        member_id: str,
        drug_ndc: str,
    ) -> DrugCostEstimate:
        """Estimate a member's cost for a drug under their plan.

        Delegates to BenefitInvestigationService for the heavy lifting,
        then formats the result for consumer display.
        """
        result: BenefitResult = await self._benefit.investigate_benefit(
            tenant_id=tenant_id,
            member_id=member_id,
            drug_ndc=drug_ndc,
        )

        alternatives = [
            AlternativeOption(
                ndc=alt.ndc,
                name=alt.name,
                tier=alt.tier,
                cost=money(alt.cost),
                savings=money(alt.savings),
            )
            for alt in result.alternatives
        ]

        return DrugCostEstimate(
            member_id=member_id,
            drug_ndc=drug_ndc,
            estimated_cost=money(result.member_cost_estimate),
            tier=result.tier,
            formulary_status=result.formulary_status.value if result.formulary_status else None,
            alternatives=alternatives,
        )

    async def pharmacy_cost_comparison(
        self,
        tenant_id: uuid.UUID,
        member_id: str,
        drug_ndc: str,
        lat: Decimal,
        lng: Decimal,
    ) -> PharmacyCostResult:
        """Compare drug cost across nearby pharmacies, sorted by distance."""
        pharmacies = await self._pharmacy.get_nearby_pharmacies(
            tenant_id=tenant_id,
            drug_ndc=drug_ndc,
            member_id=member_id,
            lat=lat,
            lng=lng,
        )

        sorted_pharmacies = sorted(pharmacies, key=lambda p: p.distance_mi)

        return PharmacyCostResult(
            member_id=member_id,
            drug_ndc=drug_ndc,
            pharmacies=sorted_pharmacies,
        )

    async def benefit_progress(
        self,
        tenant_id: uuid.UUID,
        member_id: str,
    ) -> BenefitProgressResult:
        """Get deductible/OOP progress bars and projected trajectory."""
        elig = await self._eligibility.verify_eligibility(
            tenant_id=tenant_id,
            member_id=member_id,
        )

        if elig.status != EligibilityStatus.ACTIVE:
            return BenefitProgressResult(member_id=member_id)

        projected_ded_date = _project_met_date(elig.deductible, elig.coverage_start, elig.coverage_end)
        projected_oop_date = _project_met_date(elig.oop, elig.coverage_start, elig.coverage_end)

        return BenefitProgressResult(
            member_id=member_id,
            deductible=elig.deductible,
            oop=elig.oop,
            benefit_year_start=elig.coverage_start,
            benefit_year_end=elig.coverage_end,
            projected_deductible_met_date=projected_ded_date,
            projected_oop_met_date=projected_oop_date,
        )

    async def digital_id_card(
        self,
        tenant_id: uuid.UUID,
        member_id: str,
    ) -> DigitalIDCardData | None:
        """Retrieve digital ID card data for a member."""
        return await self._id_card.get_card_data(tenant_id, member_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _project_met_date(
    progress: AccumulatorProgress | None,
    coverage_start: date | None,
    coverage_end: date | None,
) -> date | None:
    """Project when an accumulator will be fully met based on current pace.

    Uses linear projection from coverage_start to today, extended to the
    full limit. Returns None if already met or insufficient data.
    """
    if progress is None or coverage_start is None or coverage_end is None:
        return None

    if progress.remaining <= ZERO:
        return None  # Already met

    if progress.met <= ZERO:
        return None  # No data to project from

    today = date.today()
    days_elapsed = (today - coverage_start).days
    if days_elapsed <= 0:
        return None

    # Daily rate of accumulation
    daily_rate = progress.met / Decimal(str(days_elapsed))
    if daily_rate <= ZERO:
        return None

    days_to_meet = int(
        (progress.remaining / daily_rate).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )

    from datetime import timedelta

    projected = today + timedelta(days=days_to_meet)

    # Cap at benefit year end
    if projected > coverage_end:
        return None

    return projected
