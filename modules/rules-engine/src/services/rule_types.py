"""Rule type executors for the rules-engine module.

Each rule type is an ABC subclass with execute(claim_context, parameters)
returning a RuleResult(action, modified_values, message).

All monetary calculations use Decimal with ROUND_HALF_UP.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from shared.utils.money import ZERO, money

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class RuleAction(str, enum.Enum):
    """Possible outcomes of a rule execution."""

    PASS = "pass"
    REJECT = "reject"
    MODIFY = "modify"
    FLAG = "flag"


@dataclass(frozen=True)
class RuleResult:
    """Outcome of a single rule execution."""

    action: RuleAction
    modified_values: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    reject_code: str = ""


# ---------------------------------------------------------------------------
# Claim context passed to each rule
# ---------------------------------------------------------------------------


@dataclass
class ClaimContext:
    """Snapshot of claim data available to rule executors.

    All monetary fields are Decimal. The context is mutable so that
    MODIFY rules can update pricing fields for downstream rules.
    """

    claim_id: str = ""
    tenant_id: str = ""
    member_id: str = ""
    member_age: int = 0
    member_state: str = ""
    ndc: str = ""
    drug_name: str = ""
    drug_type: str = ""  # generic/brand/specialty/biosimilar
    quantity: Decimal = ZERO
    days_supply: int = 0
    pharmacy_npi: str = ""
    pharmacy_type: str = ""  # retail/mail/specialty
    prescriber_npi: str = ""
    plan_id: str = ""
    program_id: str = ""
    network_tier: str = ""

    # NCPDP wire fields — populated by build_context and referenced by
    # shared.utils.ncpdp_field_lookup (NCPDP_FIELD_TO_CTX_ATTR). When the
    # lookup mapping registers a field code, the corresponding attribute
    # must exist here (test_every_mapping_targets_existing_attr enforces).
    bin: str = ""                # 101-A1
    pcn: str = ""                # 104-A4
    group_number: str = ""       # 301-C1
    occ_code: str = ""           # 308-C8 — Other Coverage Code
    patient_dob: date | None = None              # 304-C4
    date_of_service: date | None = None          # 401-D1
    submission_clarification_codes: list[str] = field(default_factory=list)  # 420-DK

    # Pricing fields (mutated by MODIFY rules)
    ingredient_cost: Decimal = ZERO
    dispensing_fee: Decimal = ZERO
    copay: Decimal = ZERO
    total_price: Decimal = ZERO

    # Prior authorization
    pa_on_file: bool = False
    pa_approved: bool = False

    # Refill tracking
    last_fill_date: date | None = None
    fills_in_period: int = 0

    # Step therapy / prior drug history
    prior_drug_trials: list[str] = field(default_factory=list)

    # State regulatory context
    state_allows_biosimilar_sub: bool = True
    prescriber_daw: str = ""  # dispense-as-written code

    # Accumulator values
    deductible_met: Decimal = ZERO
    oop_met: Decimal = ZERO


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class BaseRuleExecutor(ABC):
    """Abstract base for all rule type executors."""

    @abstractmethod
    def execute(self, ctx: ClaimContext, parameters: dict[str, Any]) -> RuleResult:
        """Evaluate the rule against the claim context and return a result."""


# ---------------------------------------------------------------------------
# CORE RULE TYPES
# ---------------------------------------------------------------------------


class BillCostCalculator(BaseRuleExecutor):
    """Calculate ingredient cost from pricing source and quantity.

    Parameters:
        pricing_source: str — "awp", "wac", "mac", "uc"
        awp_unit_price: str (Decimal)
        wac_unit_price: str (Decimal)
        mac_unit_price: str (Decimal)
        uc_unit_price: str (Decimal)
        discount_pct: str (Decimal) — percentage discount off pricing source
        tier_rules: list[dict] — optional tiered pricing by quantity or cost
            Each tier: {"min_quantity": str, "max_quantity": str, "discount_pct": str}
    """

    def execute(self, ctx: ClaimContext, parameters: dict[str, Any]) -> RuleResult:
        pricing_source = parameters.get("pricing_source", "awp")
        unit_price_key = f"{pricing_source}_unit_price"
        raw_unit_price = parameters.get(unit_price_key, "0")
        unit_price = money(Decimal(str(raw_unit_price)))

        # Base ingredient cost
        ingredient_cost = money(unit_price * ctx.quantity)

        # Apply flat discount if present
        discount_pct = Decimal(str(parameters.get("discount_pct", "0")))
        if discount_pct > ZERO:
            discount_amount = money(ingredient_cost * discount_pct / Decimal("100"))
            ingredient_cost = money(ingredient_cost - discount_amount)

        # Apply tiered pricing if present
        tier_rules = parameters.get("tier_rules", [])
        for tier in tier_rules:
            min_qty = Decimal(str(tier.get("min_quantity", "0")))
            max_qty = Decimal(str(tier.get("max_quantity", "999999")))
            if min_qty <= ctx.quantity <= max_qty:
                tier_discount = Decimal(str(tier.get("discount_pct", "0")))
                if tier_discount > ZERO:
                    tier_discount_amount = money(ingredient_cost * tier_discount / Decimal("100"))
                    ingredient_cost = money(ingredient_cost - tier_discount_amount)
                break

        return RuleResult(
            action=RuleAction.MODIFY,
            modified_values={"ingredient_cost": ingredient_cost},
            message=f"Ingredient cost calculated: {ingredient_cost} ({pricing_source})",
        )


class CopayRule(BaseRuleExecutor):
    """Calculate copay: flat, percentage, tiered by drug type, or step-based.

    Parameters:
        copay_type: str — "flat", "percentage", "tiered", "step"
        flat_amount: str (Decimal) — used when copay_type is "flat"
        percentage: str (Decimal) — percentage of ingredient_cost
        tier_map: dict — maps drug_type to flat copay amount
            e.g. {"generic": "10.00", "brand": "35.00", "specialty": "100.00"}
        step_tiers: list[dict] — step-based copay tiers
            Each: {"max_cost": str, "copay": str}
        min_copay: str (Decimal) — floor
        max_copay: str (Decimal) — ceiling
    """

    def execute(self, ctx: ClaimContext, parameters: dict[str, Any]) -> RuleResult:
        copay_type = parameters.get("copay_type", "flat")
        copay = ZERO

        if copay_type == "flat":
            copay = money(Decimal(str(parameters.get("flat_amount", "0"))))

        elif copay_type == "percentage":
            pct = Decimal(str(parameters.get("percentage", "0")))
            copay = money(ctx.ingredient_cost * pct / Decimal("100"))

        elif copay_type == "tiered":
            tier_map = parameters.get("tier_map", {})
            raw = tier_map.get(ctx.drug_type, tier_map.get("default", "0"))
            copay = money(Decimal(str(raw)))

        elif copay_type == "step":
            step_tiers = parameters.get("step_tiers", [])
            for tier in step_tiers:
                max_cost = Decimal(str(tier.get("max_cost", "999999")))
                if ctx.ingredient_cost <= max_cost:
                    copay = money(Decimal(str(tier.get("copay", "0"))))
                    break

        # Apply min/max bounds
        min_copay_raw = parameters.get("min_copay")
        max_copay_raw = parameters.get("max_copay")
        if min_copay_raw is not None:
            min_copay = money(Decimal(str(min_copay_raw)))
            if copay < min_copay:
                copay = min_copay
        if max_copay_raw is not None:
            max_copay = money(Decimal(str(max_copay_raw)))
            if copay > max_copay:
                copay = max_copay

        return RuleResult(
            action=RuleAction.MODIFY,
            modified_values={"copay": copay},
            message=f"Copay calculated: {copay} ({copay_type})",
        )


class DispenseFeeRule(BaseRuleExecutor):
    """Calculate dispensing fee: flat or variable by pharmacy/drug/network.

    Parameters:
        fee_type: str — "flat", "variable"
        flat_fee: str (Decimal)
        pharmacy_fee_map: dict — maps pharmacy_type to fee
        network_fee_map: dict — maps network_tier to fee
        drug_type_fee_map: dict — maps drug_type to fee
    """

    def execute(self, ctx: ClaimContext, parameters: dict[str, Any]) -> RuleResult:
        fee_type = parameters.get("fee_type", "flat")

        if fee_type == "flat":
            fee = money(Decimal(str(parameters.get("flat_fee", "0"))))
        else:
            # Variable: check pharmacy type, then network, then drug type, then default
            pharmacy_map = parameters.get("pharmacy_fee_map", {})
            network_map = parameters.get("network_fee_map", {})
            drug_map = parameters.get("drug_type_fee_map", {})

            raw_fee = pharmacy_map.get(
                ctx.pharmacy_type,
                network_map.get(
                    ctx.network_tier,
                    drug_map.get(
                        ctx.drug_type,
                        parameters.get("flat_fee", "0"),
                    ),
                ),
            )
            fee = money(Decimal(str(raw_fee)))

        return RuleResult(
            action=RuleAction.MODIFY,
            modified_values={"dispensing_fee": fee},
            message=f"Dispensing fee: {fee} ({fee_type})",
        )


class QuantityLimitRule(BaseRuleExecutor):
    """Enforce quantity limits per fill, per day supply, or per time period.

    Parameters:
        max_quantity: str (Decimal) — max per fill
        max_days_supply: int — max days supply per fill
        max_quantity_per_period: str (Decimal) — max quantity in a period
        period_days: int — number of days in the period
        fills_in_period: int — current fills used (from accumulator)
    """

    def execute(self, ctx: ClaimContext, parameters: dict[str, Any]) -> RuleResult:
        # Check per-fill quantity limit
        max_qty_raw = parameters.get("max_quantity")
        if max_qty_raw is not None:
            max_qty = Decimal(str(max_qty_raw))
            if ctx.quantity > max_qty:
                return RuleResult(
                    action=RuleAction.REJECT,
                    reject_code="QL_EXCEEDED",
                    message=f"Quantity {ctx.quantity} exceeds max {max_qty} per fill",
                )

        # Check days supply limit
        max_days = parameters.get("max_days_supply")
        if max_days is not None and ctx.days_supply > int(max_days):
            return RuleResult(
                action=RuleAction.REJECT,
                reject_code="DS_EXCEEDED",
                message=f"Days supply {ctx.days_supply} exceeds max {max_days}",
            )

        # Check per-period quantity limit
        max_per_period_raw = parameters.get("max_quantity_per_period")
        if max_per_period_raw is not None:
            max_per_period = Decimal(str(max_per_period_raw))
            period_fills = parameters.get("fills_in_period", ctx.fills_in_period)
            if ctx.quantity + Decimal(str(period_fills)) > max_per_period:
                return RuleResult(
                    action=RuleAction.REJECT,
                    reject_code="PERIOD_QL_EXCEEDED",
                    message=f"Quantity would exceed period limit of {max_per_period}",
                )

        return RuleResult(action=RuleAction.PASS, message="Quantity within limits")


class RefillRule(BaseRuleExecutor):
    """Enforce early refill threshold.

    Parameters:
        threshold_pct: str (Decimal) — percentage of days supply that must elapse
        threshold_days: int — alternative: minimum days between fills
        allow_vacation_override: bool — whether to allow vacation supply exception
    """

    def execute(self, ctx: ClaimContext, parameters: dict[str, Any]) -> RuleResult:
        if ctx.last_fill_date is None:
            return RuleResult(action=RuleAction.PASS, message="No prior fill on record")

        today = date.today()
        days_since_last = (today - ctx.last_fill_date).days

        # Threshold by percentage of days supply
        threshold_pct_raw = parameters.get("threshold_pct")
        if threshold_pct_raw is not None:
            pct = Decimal(str(threshold_pct_raw))
            threshold_days = int(money(Decimal(str(ctx.days_supply)) * pct / Decimal("100")))
        else:
            threshold_days = int(parameters.get("threshold_days", 0))

        if days_since_last < threshold_days:
            # Check vacation override
            allow_vacation = parameters.get("allow_vacation_override", False)
            if allow_vacation:
                return RuleResult(
                    action=RuleAction.FLAG,
                    message=f"Early refill ({days_since_last}d < {threshold_days}d threshold) — vacation override eligible",
                )
            return RuleResult(
                action=RuleAction.REJECT,
                reject_code="EARLY_REFILL",
                message=f"Early refill: {days_since_last} days since last fill, threshold is {threshold_days} days",
            )

        return RuleResult(action=RuleAction.PASS, message="Refill timing acceptable")


class AgeRule(BaseRuleExecutor):
    """Enforce min/max age limits for a drug.

    Parameters:
        min_age: int or None
        max_age: int or None
    """

    def execute(self, ctx: ClaimContext, parameters: dict[str, Any]) -> RuleResult:
        min_age = parameters.get("min_age")
        max_age = parameters.get("max_age")

        if min_age is not None and ctx.member_age < int(min_age):
            return RuleResult(
                action=RuleAction.REJECT,
                reject_code="AGE_MIN",
                message=f"Member age {ctx.member_age} below minimum {min_age}",
            )

        if max_age is not None and ctx.member_age > int(max_age):
            return RuleResult(
                action=RuleAction.REJECT,
                reject_code="AGE_MAX",
                message=f"Member age {ctx.member_age} above maximum {max_age}",
            )

        return RuleResult(action=RuleAction.PASS, message="Age within range")


class StepTherapyRule(BaseRuleExecutor):
    """Require trial of preferred drug before allowing target drug.

    Parameters:
        required_prior_drugs: list[str] — NDCs or drug names that must have been tried
        lookback_days: int — how far back to check for prior trials
        min_trial_days: int — minimum duration of prior trial
    """

    def execute(self, ctx: ClaimContext, parameters: dict[str, Any]) -> RuleResult:
        required = parameters.get("required_prior_drugs", [])
        if not required:
            return RuleResult(action=RuleAction.PASS, message="No step therapy required")

        trials = set(ctx.prior_drug_trials)
        met = any(drug in trials for drug in required)

        if not met:
            return RuleResult(
                action=RuleAction.REJECT,
                reject_code="STEP_THERAPY",
                message=f"Step therapy not met: requires trial of {required}",
            )

        return RuleResult(action=RuleAction.PASS, message="Step therapy requirement satisfied")


class PARequiredRule(BaseRuleExecutor):
    """Check if prior authorization is required and whether one is on file.

    Parameters:
        pa_required: bool — whether this drug requires PA
        pa_trigger_codes: list[str] — codes that trigger PA requirement
    """

    def execute(self, ctx: ClaimContext, parameters: dict[str, Any]) -> RuleResult:
        pa_required = parameters.get("pa_required", False)
        if not pa_required:
            return RuleResult(action=RuleAction.PASS, message="PA not required")

        if ctx.pa_on_file and ctx.pa_approved:
            return RuleResult(action=RuleAction.PASS, message="PA on file and approved")

        trigger_codes = parameters.get("pa_trigger_codes", [])
        return RuleResult(
            action=RuleAction.REJECT,
            reject_code="PA_REQUIRED",
            message=f"Prior authorization required (triggers: {trigger_codes})",
        )


class BiosimilarSubstitutionRule(BaseRuleExecutor):
    """Auto-substitute biosimilar with 50-state law compliance check.

    Parameters:
        alternative_ndc: str — the biosimilar NDC to substitute
        interchangeable: bool — FDA interchangeable designation
        state_law_overrides: dict — state_code -> bool (allows substitution)
    """

    def execute(self, ctx: ClaimContext, parameters: dict[str, Any]) -> RuleResult:
        alternative_ndc = parameters.get("alternative_ndc", "")
        if not alternative_ndc:
            return RuleResult(action=RuleAction.PASS, message="No biosimilar alternative configured")

        interchangeable = parameters.get("interchangeable", False)

        # Check state law compliance
        state_overrides = parameters.get("state_law_overrides", {})
        state_allows = state_overrides.get(ctx.member_state, ctx.state_allows_biosimilar_sub)

        if not state_allows:
            return RuleResult(
                action=RuleAction.FLAG,
                message=f"State {ctx.member_state} does not allow biosimilar substitution",
            )

        # Check DAW (dispense-as-written) code
        if ctx.prescriber_daw in ("1", "9"):
            return RuleResult(
                action=RuleAction.FLAG,
                message=f"Prescriber DAW code {ctx.prescriber_daw} prevents substitution",
            )

        if not interchangeable:
            return RuleResult(
                action=RuleAction.FLAG,
                message=f"Biosimilar {alternative_ndc} not FDA-interchangeable — manual review",
            )

        return RuleResult(
            action=RuleAction.MODIFY,
            modified_values={"ndc": alternative_ndc},
            message=f"Biosimilar substitution: {ctx.ndc} -> {alternative_ndc}",
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


RULE_TYPE_REGISTRY: dict[str, type[BaseRuleExecutor]] = {
    "bill_cost_calculator": BillCostCalculator,
    "copay_rule": CopayRule,
    "dispense_fee_rule": DispenseFeeRule,
    "quantity_limit_rule": QuantityLimitRule,
    "refill_rule": RefillRule,
    "age_rule": AgeRule,
    "step_therapy_rule": StepTherapyRule,
    "pa_required_rule": PARequiredRule,
    "biosimilar_substitution_rule": BiosimilarSubstitutionRule,
}


def get_executor(rule_type_code: str) -> BaseRuleExecutor:
    """Instantiate and return the executor for a given rule type code."""
    cls = RULE_TYPE_REGISTRY.get(rule_type_code)
    if cls is None:
        raise ValueError(f"Unknown rule type code: {rule_type_code}")
    return cls()
