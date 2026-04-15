"""Eight pluggable pricing calculators — PRD §4.

Each calculator implements PricingCalculator ABC.
Registry pattern: adding a new model is a config row + one class.

All calculations use Decimal with ROUND_HALF_UP.
"""

from __future__ import annotations

import abc
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from shared.utils.money import money, TWO_PLACES, ZERO


class PricingContext:
    """Input data for a pricing calculation."""

    def __init__(
        self,
        *,
        awp: Decimal | None = None,
        mac: Decimal | None = None,
        nadac: Decimal | None = None,
        acquisition_cost: Decimal | None = None,
        manufacturer_price: Decimal | None = None,
        cash_price: Decimal | None = None,
        dispensing_fee: Decimal = ZERO,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        self.awp = awp
        self.mac = mac
        self.nadac = nadac
        self.acquisition_cost = acquisition_cost
        self.manufacturer_price = manufacturer_price
        self.cash_price = cash_price
        self.dispensing_fee = dispensing_fee
        self.parameters = parameters or {}


class PricingResult:
    """Output of a pricing calculation."""

    def __init__(self, *, ingredient_cost: Decimal, dispensing_fee: Decimal, total: Decimal) -> None:
        self.ingredient_cost = money(ingredient_cost)
        self.dispensing_fee = money(dispensing_fee)
        self.total = money(total)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PricingResult):
            return False
        return (
            self.ingredient_cost == other.ingredient_cost
            and self.dispensing_fee == other.dispensing_fee
            and self.total == other.total
        )


class PricingCalculator(abc.ABC):
    """Abstract base for all pricing calculators."""

    code: str  # Matches pricing_models.code in DB

    @abc.abstractmethod
    def calculate(self, ctx: PricingContext) -> PricingResult:
        """Compute ingredient cost + dispensing fee, return PricingResult."""


# ---------------------------------------------------------------------------
# AWP Discount — formula: AWP - X% + dispensing fee
# ---------------------------------------------------------------------------


class AWPDiscountCalculator(PricingCalculator):
    """AWP - discount_pct% + dispensing_fee. Traditional PBM contracts."""

    code = "awp_discount"

    def calculate(self, ctx: PricingContext) -> PricingResult:
        if ctx.awp is None:
            raise ValueError("AWP is required for AWPDiscount pricing")
        discount_pct = Decimal(str(ctx.parameters.get("discount_pct", "0")))
        ingredient = (ctx.awp * (1 - discount_pct / 100)).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
        total = money(ingredient + ctx.dispensing_fee)
        return PricingResult(
            ingredient_cost=ingredient,
            dispensing_fee=ctx.dispensing_fee,
            total=total,
        )


# ---------------------------------------------------------------------------
# MAC — Maximum Allowable Cost per drug list
# ---------------------------------------------------------------------------


class MACCalculator(PricingCalculator):
    """MAC price + dispensing fee. Generic pricing."""

    code = "mac"

    def calculate(self, ctx: PricingContext) -> PricingResult:
        if ctx.mac is None:
            raise ValueError("MAC price is required for MAC pricing")
        ingredient = money(ctx.mac)
        total = money(ingredient + ctx.dispensing_fee)
        return PricingResult(
            ingredient_cost=ingredient,
            dispensing_fee=ctx.dispensing_fee,
            total=total,
        )


# ---------------------------------------------------------------------------
# Cost-Plus — acquisition cost + % markup + dispensing fee
# ---------------------------------------------------------------------------


class CostPlusCalculator(PricingCalculator):
    """Acquisition cost + markup_pct% + dispensing fee.

    If acquisition_cost is missing, falls back to AWP at a default discount.
    """

    code = "cost_plus"

    def calculate(self, ctx: PricingContext) -> PricingResult:
        markup_pct = Decimal(str(ctx.parameters.get("markup_pct", "0")))
        if ctx.acquisition_cost is not None:
            base = ctx.acquisition_cost
        elif ctx.awp is not None:
            # Fallback: AWP at 15% discount (industry standard fallback)
            fallback_discount = Decimal(str(ctx.parameters.get("awp_fallback_discount_pct", "15")))
            base = (ctx.awp * (1 - fallback_discount / 100)).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
        else:
            raise ValueError(
                "CostPlus pricing requires acquisition_cost (or awp as fallback)"
            )
        ingredient = (base * (1 + markup_pct / 100)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        total = money(ingredient + ctx.dispensing_fee)
        return PricingResult(
            ingredient_cost=ingredient,
            dispensing_fee=ctx.dispensing_fee,
            total=total,
        )


# ---------------------------------------------------------------------------
# NADAC-Based — NADAC + markup + fee
# ---------------------------------------------------------------------------


class NADACBasedCalculator(PricingCalculator):
    """NADAC + markup_pct% + dispensing fee."""

    code = "nadac_based"

    def calculate(self, ctx: PricingContext) -> PricingResult:
        if ctx.nadac is None:
            raise ValueError("NADAC price is required for NADAC-Based pricing")
        markup_pct = Decimal(str(ctx.parameters.get("markup_pct", "0")))
        ingredient = (ctx.nadac * (1 + markup_pct / 100)).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
        total = money(ingredient + ctx.dispensing_fee)
        return PricingResult(
            ingredient_cost=ingredient,
            dispensing_fee=ctx.dispensing_fee,
            total=total,
        )


# ---------------------------------------------------------------------------
# Net-Cost — actual net drug cost after rebates + admin fee
# ---------------------------------------------------------------------------


class NetCostCalculator(PricingCalculator):
    """Net drug cost (post-rebate acquisition) + admin fee.

    admin_fee is passed via parameters rather than dispensing_fee
    to distinguish the two line items conceptually.
    """

    code = "net_cost"

    def calculate(self, ctx: PricingContext) -> PricingResult:
        if ctx.acquisition_cost is None:
            raise ValueError("Net acquisition cost is required for NetCost pricing")
        admin_fee = Decimal(str(ctx.parameters.get("admin_fee", "0")))
        ingredient = money(ctx.acquisition_cost)
        total = money(ingredient + admin_fee + ctx.dispensing_fee)
        return PricingResult(
            ingredient_cost=ingredient,
            dispensing_fee=money(admin_fee + ctx.dispensing_fee),
            total=total,
        )


# ---------------------------------------------------------------------------
# Cost-Plus Specialty — drug cost + patient management fee
# ---------------------------------------------------------------------------


class CostPlusSpecialtyCalculator(PricingCalculator):
    """Drug cost + patient_mgmt_fee for specialty pharmacy programs."""

    code = "cost_plus_specialty"

    def calculate(self, ctx: PricingContext) -> PricingResult:
        if ctx.acquisition_cost is None:
            raise ValueError("Acquisition cost required for CostPlusSpecialty pricing")
        markup_pct = Decimal(str(ctx.parameters.get("markup_pct", "0")))
        patient_mgmt_fee = Decimal(str(ctx.parameters.get("patient_mgmt_fee", "0")))
        ingredient = (ctx.acquisition_cost * (1 + markup_pct / 100)).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
        combined_fee = money(patient_mgmt_fee + ctx.dispensing_fee)
        total = money(ingredient + combined_fee)
        return PricingResult(
            ingredient_cost=ingredient,
            dispensing_fee=combined_fee,
            total=total,
        )


# ---------------------------------------------------------------------------
# Direct Manufacturer — manufacturer-set price (bypasses PBM spread)
# ---------------------------------------------------------------------------


class DirectManufacturerCalculator(PricingCalculator):
    """Manufacturer-set price — used for direct-to-patient programs."""

    code = "direct_manufacturer"

    def calculate(self, ctx: PricingContext) -> PricingResult:
        if ctx.manufacturer_price is None:
            raise ValueError("Manufacturer price required for DirectManufacturer pricing")
        ingredient = money(ctx.manufacturer_price)
        total = money(ingredient + ctx.dispensing_fee)
        return PricingResult(
            ingredient_cost=ingredient,
            dispensing_fee=ctx.dispensing_fee,
            total=total,
        )


# ---------------------------------------------------------------------------
# Cash/Discount Card — discounted cash price
# ---------------------------------------------------------------------------


class CashDiscountCardCalculator(PricingCalculator):
    """Discounted cash price — used for cash-pay / discount card programs."""

    code = "cash_discount_card"

    def calculate(self, ctx: PricingContext) -> PricingResult:
        if ctx.cash_price is None:
            raise ValueError("Cash price required for CashDiscountCard pricing")
        ingredient = money(ctx.cash_price)
        total = money(ingredient + ctx.dispensing_fee)
        return PricingResult(
            ingredient_cost=ingredient,
            dispensing_fee=ctx.dispensing_fee,
            total=total,
        )


# ---------------------------------------------------------------------------
# Registry — adding a new calculator is one config row + one class above
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[PricingCalculator]] = {
    cls.code: cls  # type: ignore[type-abstract]
    for cls in [
        AWPDiscountCalculator,
        MACCalculator,
        CostPlusCalculator,
        NADACBasedCalculator,
        NetCostCalculator,
        CostPlusSpecialtyCalculator,
        DirectManufacturerCalculator,
        CashDiscountCardCalculator,
    ]
}


def get_calculator(code: str) -> PricingCalculator:
    """Return a calculator instance for the given code.

    Raises KeyError if the code is not registered.
    """
    cls = _REGISTRY.get(code)
    if cls is None:
        raise KeyError(f"No pricing calculator registered for code: {code!r}")
    return cls()


def calculate_cash_pay_comparison(
    insurance_result: PricingResult,
    cash_ctx: PricingContext,
) -> PricingResult:
    """Return lower of insurance price vs cash/discount price (PRD §4).

    Used when cash_pay_comparison_enabled is True on the plan.
    """
    if cash_ctx.cash_price is None:
        return insurance_result
    cash_result = CashDiscountCardCalculator().calculate(cash_ctx)
    if cash_result.total < insurance_result.total:
        return cash_result
    return insurance_result


__all__ = [
    "PricingContext",
    "PricingResult",
    "PricingCalculator",
    "AWPDiscountCalculator",
    "MACCalculator",
    "CostPlusCalculator",
    "NADACBasedCalculator",
    "NetCostCalculator",
    "CostPlusSpecialtyCalculator",
    "DirectManufacturerCalculator",
    "CashDiscountCardCalculator",
    "get_calculator",
    "calculate_cash_pay_comparison",
]
