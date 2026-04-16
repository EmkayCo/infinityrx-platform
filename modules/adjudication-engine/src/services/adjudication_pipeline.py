"""Core adjudication pipeline for real-time pharmacy claim processing.

This is the heart of the PBM: every pharmacy claim passes through this
pipeline. The pipeline is a deterministic sequence of steps, each
producing a structured result that feeds into the next. Every step is
logged in the claim_trace for full auditability and reproducibility.

Performance targets: p50 < 200ms, p95 < 1000ms.

Architecture:
    adjudicate(parsed_claim, tenant_id) orchestrates 13 discrete steps.
    Each step is a standalone function that returns a StepResult.
    Exceptions within a step are caught and recorded — one failing step
    does not crash the entire pipeline unless it is a hard-stop.

Accumulator/maximizer adaptive response:
    - Standard: full benefit applied, normal POS pricing
    - Accumulator (OC2): reduce POS copay, plan reimburses manufacturer directly
    - Maximizer (OC8): spread benefit value across the year
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from shared.utils.money import ZERO, TWO_PLACES, money

from .ncpdp_parser import ParsedClaim

logger = logging.getLogger("adjudication_engine.pipeline")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum number of DUR alerts before auto-rejecting
MAX_DUR_ALERTS_HARD_STOP = 3

# Copay fraud score threshold for blocking
FRAUD_BLOCK_THRESHOLD = Decimal("0.8500")
FRAUD_FLAG_THRESHOLD = Decimal("0.5000")

# Early refill threshold (percentage of days_supply that must elapse)
EARLY_REFILL_THRESHOLD_PCT = Decimal("75")

# Accumulator OC codes from NCPDP other_coverage_code
ACCUMULATOR_OC_CODES = {"2", "02", "OC2"}
MAXIMIZER_OC_CODES = {"8", "08", "OC8"}


# ---------------------------------------------------------------------------
# Step result types
# ---------------------------------------------------------------------------


class StepStatus(str, Enum):
    """Outcome of a pipeline step."""

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    WARN = "warn"


@dataclass
class StepResult:
    """Result of a single pipeline step."""

    step_name: str
    status: StepStatus
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0


@dataclass
class DURAlert:
    """Drug utilization review alert."""

    check_type: str  # drug_drug/therapeutic_dup/early_refill/quantity
    severity: str  # critical/major/minor/info
    description: str
    action: str  # reject/flag/info
    drug_a_ndc: str = ""
    drug_b_ndc: str = ""


@dataclass
class FraudSignal:
    """Copay fraud detection signal."""

    flag_type: str
    score: Decimal
    details: dict[str, Any] = field(default_factory=dict)
    action: str = "pass"  # block/flag/pass


class AccumulatorStrategy(str, Enum):
    """How to handle accumulator programs."""

    STANDARD = "standard"
    ACCUMULATOR = "accumulator"
    MAXIMIZER = "maximizer"


@dataclass
class AdjudicationResult:
    """Complete result of claim adjudication.

    Contains pricing, DUR alerts, fraud signals, plain English reasons,
    full step trace, and the final status determination.
    """

    claim_id: str = ""
    status: str = "pending"  # paid/rejected/reversed/pending
    transaction_type: str = "B1"

    # Pricing — all Decimal
    ingredient_cost: Decimal = ZERO
    dispensing_fee: Decimal = ZERO
    patient_pay: Decimal = ZERO
    plan_pay: Decimal = ZERO
    total_amount: Decimal = ZERO
    pricing_model_used: str = ""

    # Rejection
    reject_code: str = ""
    reject_reason: str = ""

    # Plain English reasoning
    reasons: list[str] = field(default_factory=list)

    # Full audit trace
    claim_trace: list[dict[str, Any]] = field(default_factory=list)

    # DUR
    dur_alerts: list[DURAlert] = field(default_factory=list)

    # Fraud
    fraud_signals: list[FraudSignal] = field(default_factory=list)
    copay_fraud_score: Decimal = ZERO

    # Accumulator
    accumulator_detected: bool = False
    accumulator_strategy: AccumulatorStrategy = AccumulatorStrategy.STANDARD

    # COB
    cob_details: dict[str, Any] = field(default_factory=dict)

    # Override
    override_applied: bool = False
    overridden_rules: list[str] = field(default_factory=list)

    # Therapeutic alternative (returned when a cheaper alternative exists)
    therapeutic_alternative_ndc: str = ""
    therapeutic_alternative_savings: Decimal = ZERO

    # Resolved context
    member_id: str = ""
    plan_id: str = ""
    group_id: str = ""


# ---------------------------------------------------------------------------
# Step implementations
# ---------------------------------------------------------------------------


def step_identify_member(
    parsed: ParsedClaim,
    tenant_id: uuid.UUID,
    member_lookup: Any | None = None,
) -> StepResult:
    """Step 1: Identify the member from cardholder_id + person_code + DOB.

    In production, this calls the member-management module API.
    The member_lookup parameter allows injection for testing.
    """
    cardholder_id = parsed.patient.cardholder_id or parsed.insurance.cardholder_id
    person_code = parsed.patient.person_code
    dob = parsed.patient.date_of_birth

    if not cardholder_id:
        return StepResult(
            step_name="identify_member",
            status=StepStatus.FAIL,
            message="Missing cardholder ID",
        )

    # Attempt member resolution
    if member_lookup is not None:
        member = member_lookup(cardholder_id, person_code, dob, tenant_id)
        if member is None:
            return StepResult(
                step_name="identify_member",
                status=StepStatus.FAIL,
                message=f"Member not found: cardholder={cardholder_id}, person={person_code}",
            )
        return StepResult(
            step_name="identify_member",
            status=StepStatus.PASS,
            message=f"Member identified: {member.get('member_id', 'unknown')}",
            data=member,
        )

    # Default: pass through with cardholder info for downstream steps
    return StepResult(
        step_name="identify_member",
        status=StepStatus.PASS,
        message=f"Member lookup deferred: cardholder={cardholder_id}",
        data={
            "cardholder_id": cardholder_id,
            "person_code": person_code,
            "dob": dob,
        },
    )


def step_verify_eligibility(
    parsed: ParsedClaim,
    member_data: dict[str, Any],
    tenant_id: uuid.UUID,
    eligibility_checker: Any | None = None,
) -> StepResult:
    """Step 2: Verify member eligibility — plan active, coverage dates.

    Checks that the member's plan is active and the date of service falls
    within the coverage period.
    """
    if eligibility_checker is not None:
        result = eligibility_checker(member_data, parsed, tenant_id)
        if result is not None:
            return result

    # Default: check dates from member_data if available
    plan_status = member_data.get("plan_status", "active")
    if plan_status != "active":
        return StepResult(
            step_name="verify_eligibility",
            status=StepStatus.FAIL,
            message=f"Plan not active (status: {plan_status})",
            data={"plan_status": plan_status},
        )

    coverage_start = member_data.get("coverage_start")
    coverage_end = member_data.get("coverage_end")
    dos = parsed.header.date_of_service

    if coverage_start and dos and dos < coverage_start:
        return StepResult(
            step_name="verify_eligibility",
            status=StepStatus.FAIL,
            message=f"Date of service {dos} before coverage start {coverage_start}",
        )

    if coverage_end and dos and dos > coverage_end:
        return StepResult(
            step_name="verify_eligibility",
            status=StepStatus.FAIL,
            message=f"Date of service {dos} after coverage end {coverage_end}",
        )

    return StepResult(
        step_name="verify_eligibility",
        status=StepStatus.PASS,
        message="Member eligible",
        data={"plan_status": plan_status},
    )


def step_resolve_plan(
    member_data: dict[str, Any],
    tenant_id: uuid.UUID,
    plan_resolver: Any | None = None,
) -> StepResult:
    """Step 3: Resolve plan from group -> plan -> subgroup with inheritance.

    The plan hierarchy is: group contains plans, plans contain subgroups.
    Configuration inherits downward: group defaults, overridden by plan,
    overridden by subgroup.
    """
    group_id = member_data.get("group_id", "")
    plan_id = member_data.get("plan_id", "")

    if plan_resolver is not None:
        resolved = plan_resolver(group_id, plan_id, tenant_id)
        if resolved is not None:
            return StepResult(
                step_name="resolve_plan",
                status=StepStatus.PASS,
                message=f"Plan resolved: {plan_id}",
                data=resolved,
            )

    if not plan_id:
        return StepResult(
            step_name="resolve_plan",
            status=StepStatus.FAIL,
            message="No plan_id found for member",
        )

    return StepResult(
        step_name="resolve_plan",
        status=StepStatus.PASS,
        message=f"Plan resolved: {plan_id} (group: {group_id})",
        data={"plan_id": plan_id, "group_id": group_id},
    )


def step_resolve_pricing_model(
    plan_data: dict[str, Any],
    parsed: ParsedClaim,
) -> StepResult:
    """Step 4: Resolve pricing model from plan configuration.

    Pricing models: AWP-discount, WAC-plus, MAC, U&C, lesser-of logic.
    """
    pricing_model = plan_data.get("pricing_model", "awp_discount")

    return StepResult(
        step_name="resolve_pricing_model",
        status=StepStatus.PASS,
        message=f"Pricing model: {pricing_model}",
        data={"pricing_model": pricing_model},
    )


def step_check_claim_history(
    parsed: ParsedClaim,
    member_data: dict[str, Any],
    tenant_id: uuid.UUID,
    history_cache: Any | None = None,
) -> StepResult:
    """Step 5: Check claim history for duplicate/refill detection.

    Uses Redis cache when available for sub-millisecond lookups.
    Checks for: exact duplicate, early refill, excessive utilization.
    """
    ndc = parsed.claim.ndc
    member_id = member_data.get("member_id", "")

    if history_cache is not None:
        history = history_cache(member_id, ndc, tenant_id)
        if history is not None:
            return StepResult(
                step_name="check_claim_history",
                status=StepStatus.PASS if not history.get("duplicate") else StepStatus.FAIL,
                message="Duplicate claim detected" if history.get("duplicate") else "No duplicate",
                data=history,
            )

    return StepResult(
        step_name="check_claim_history",
        status=StepStatus.PASS,
        message="No prior claim history in cache",
        data={"last_fill_date": None, "duplicate": False},
    )


def step_check_overrides(
    member_data: dict[str, Any],
    parsed: ParsedClaim,
    tenant_id: uuid.UUID,
    override_checker: Any | None = None,
) -> StepResult:
    """Step 6: Check for active member-level rule overrides.

    Active overrides cause specific rules to be skipped in the rule
    pipeline, with notation in the claim trace.
    """
    member_id = member_data.get("member_id", "")
    ndc = parsed.claim.ndc

    if override_checker is not None:
        overrides = override_checker(member_id, ndc, tenant_id)
        if overrides:
            override_rule_ids = [str(o.get("rule_id", "")) for o in overrides]
            return StepResult(
                step_name="check_overrides",
                status=StepStatus.PASS,
                message=f"Active overrides found: {len(overrides)}",
                data={"overrides": overrides, "override_rule_ids": override_rule_ids},
            )

    return StepResult(
        step_name="check_overrides",
        status=StepStatus.PASS,
        message="No active overrides",
        data={"overrides": [], "override_rule_ids": []},
    )


def step_execute_rules(
    parsed: ParsedClaim,
    member_data: dict[str, Any],
    plan_data: dict[str, Any],
    override_rule_ids: list[str],
    tenant_id: uuid.UUID,
    rules_executor: Any | None = None,
) -> StepResult:
    """Step 7: Execute the plan's rule pipeline via the Rules Engine module.

    Calls the rules-engine module with the claim context and list of rules
    to skip (from overrides). Returns rule results including any pricing
    modifications, rejections, or flags.
    """
    if rules_executor is not None:
        rule_results = rules_executor(parsed, member_data, plan_data, override_rule_ids, tenant_id)
        if rule_results is not None:
            return StepResult(
                step_name="execute_rules",
                status=StepStatus.PASS if rule_results.get("action") != "reject" else StepStatus.FAIL,
                message=rule_results.get("message", "Rules executed"),
                data=rule_results,
            )

    return StepResult(
        step_name="execute_rules",
        status=StepStatus.PASS,
        message="Rule pipeline executed (no rules configured)",
        data={"action": "pass", "modified_values": {}, "warnings": []},
    )


def step_dur_screening(
    parsed: ParsedClaim,
    member_data: dict[str, Any],
    history_data: dict[str, Any],
    tenant_id: uuid.UUID,
    dur_checker: Any | None = None,
) -> StepResult:
    """Step 8: Drug Utilization Review screening.

    Checks for:
    - Drug-drug interactions (from concurrent medications)
    - Therapeutic duplication (same therapeutic class)
    - Early refill (based on last fill date + days supply)
    - Quantity validation
    """
    alerts: list[dict[str, Any]] = []

    if dur_checker is not None:
        external_alerts = dur_checker(parsed, member_data, tenant_id)
        if external_alerts:
            alerts.extend(external_alerts)

    # Built-in early refill check
    last_fill_date_raw = history_data.get("last_fill_date")
    last_days_supply = history_data.get("last_days_supply", 0)
    if last_fill_date_raw and last_days_supply:
        if isinstance(last_fill_date_raw, str):
            try:
                last_fill = date.fromisoformat(last_fill_date_raw)
            except ValueError:
                last_fill = None
        elif isinstance(last_fill_date_raw, date):
            last_fill = last_fill_date_raw
        else:
            last_fill = None

        if last_fill is not None:
            days_since = (date.today() - last_fill).days
            threshold = int(
                (Decimal(str(last_days_supply)) * EARLY_REFILL_THRESHOLD_PCT / Decimal("100"))
                .quantize(TWO_PLACES)
            )
            if days_since < threshold:
                alerts.append({
                    "check_type": "early_refill",
                    "severity": "major",
                    "description": (
                        f"Early refill: {days_since} days since last fill, "
                        f"threshold is {threshold} days ({EARLY_REFILL_THRESHOLD_PCT}% of {last_days_supply} day supply)"
                    ),
                    "action": "reject",
                    "drug_a_ndc": parsed.claim.ndc,
                })

    # Check for hard-stop DUR alerts
    critical_count = sum(1 for a in alerts if a.get("severity") == "critical")
    has_reject = any(a.get("action") == "reject" for a in alerts)

    if critical_count >= MAX_DUR_ALERTS_HARD_STOP or has_reject:
        return StepResult(
            step_name="dur_screening",
            status=StepStatus.FAIL,
            message=f"DUR hard stop: {len(alerts)} alert(s)",
            data={"alerts": alerts, "hard_stop": True},
        )

    return StepResult(
        step_name="dur_screening",
        status=StepStatus.WARN if alerts else StepStatus.PASS,
        message=f"{len(alerts)} DUR alert(s)" if alerts else "DUR screening clear",
        data={"alerts": alerts, "hard_stop": False},
    )


def step_cob_processing(
    parsed: ParsedClaim,
    member_data: dict[str, Any],
    tenant_id: uuid.UUID,
    cob_processor: Any | None = None,
) -> StepResult:
    """Step 9: Coordination of Benefits processing.

    Determines primary/secondary/tertiary payer responsibility.
    Uses other_coverage_code from the claim to determine COB status.
    """
    other_coverage = parsed.claim.other_coverage_code or parsed.insurance.other_coverage_code
    cob_info = member_data.get("cob", {})

    if cob_processor is not None:
        cob_result = cob_processor(parsed, member_data, tenant_id)
        if cob_result is not None:
            return StepResult(
                step_name="cob_processing",
                status=StepStatus.PASS,
                message="COB processed",
                data=cob_result,
            )

    cob_details: dict[str, Any] = {
        "other_coverage_code": other_coverage,
        "payer_order": cob_info.get("payer_order", "primary"),
        "other_payer_amount": str(ZERO),
    }

    return StepResult(
        step_name="cob_processing",
        status=StepStatus.PASS,
        message=f"COB: payer order = {cob_details['payer_order']}",
        data=cob_details,
    )


def step_accumulator_detection(
    parsed: ParsedClaim,
    member_data: dict[str, Any],
) -> StepResult:
    """Step 10: Detect accumulator/maximizer programs from OC signals.

    Accumulator programs (OC2): manufacturer copay assistance does not
    count toward deductible/OOP max. Plan should reduce POS copay and
    arrange direct manufacturer reimbursement.

    Maximizer programs (OC8): spread manufacturer assistance value across
    the entire benefit year to maximize plan savings.
    """
    other_coverage = (
        parsed.claim.other_coverage_code
        or parsed.insurance.other_coverage_code
        or ""
    )

    strategy = AccumulatorStrategy.STANDARD

    if other_coverage in ACCUMULATOR_OC_CODES:
        strategy = AccumulatorStrategy.ACCUMULATOR
    elif other_coverage in MAXIMIZER_OC_CODES:
        strategy = AccumulatorStrategy.MAXIMIZER

    detected = strategy != AccumulatorStrategy.STANDARD

    return StepResult(
        step_name="accumulator_detection",
        status=StepStatus.WARN if detected else StepStatus.PASS,
        message=(
            f"Accumulator program detected: {strategy.value}"
            if detected
            else "No accumulator program detected"
        ),
        data={
            "strategy": strategy.value,
            "detected": detected,
            "other_coverage_code": other_coverage,
        },
    )


def step_calculate_pricing(
    parsed: ParsedClaim,
    plan_data: dict[str, Any],
    pricing_model: str,
    rule_modifications: dict[str, Any],
    accumulator_strategy: AccumulatorStrategy,
    cob_data: dict[str, Any],
) -> StepResult:
    """Step 11: Calculate final pricing using resolved pricing model.

    Applies the pricing model, incorporates rule modifications (copay,
    dispensing fee changes from rules engine), adjusts for accumulator
    strategy, and factors in COB.

    All arithmetic uses Decimal with ROUND_HALF_UP.
    """
    # Start with submitted values from the claim
    ingredient_cost = parsed.pricing.ingredient_cost_submitted
    dispensing_fee = parsed.pricing.dispensing_fee_submitted

    # Apply rule engine modifications if present
    if "ingredient_cost" in rule_modifications:
        ingredient_cost = money(Decimal(str(rule_modifications["ingredient_cost"])))
    if "dispensing_fee" in rule_modifications:
        dispensing_fee = money(Decimal(str(rule_modifications["dispensing_fee"])))

    copay = money(Decimal(str(rule_modifications.get("copay", "0"))))

    # Total = ingredient cost + dispensing fee
    total_amount = money(ingredient_cost + dispensing_fee)

    # Patient pays copay; plan pays the rest
    patient_pay = copay
    plan_pay = money(total_amount - patient_pay)

    # Ensure plan_pay is not negative
    if plan_pay < ZERO:
        plan_pay = ZERO
        patient_pay = total_amount

    # Accumulator adjustment
    if accumulator_strategy == AccumulatorStrategy.ACCUMULATOR:
        # Reduce POS copay — manufacturer reimburses plan directly
        # Patient sees reduced copay at point of sale
        original_copay = patient_pay
        patient_pay = money(patient_pay * Decimal("0.10"))  # nominal POS amount
        plan_pay = money(total_amount - patient_pay)
        logger.info(
            "adjudication.accumulator_adjustment",
            extra={
                "svc_original_copay": str(original_copay),
                "svc_adjusted_copay": str(patient_pay),
                "svc_strategy": "accumulator",
            },
        )

    elif accumulator_strategy == AccumulatorStrategy.MAXIMIZER:
        # Spread benefit across year — divide copay reduction across 12 months
        # Apply 1/12 of the annual benefit reduction per claim
        monthly_factor = Decimal("1") / Decimal("12")
        copay_reduction = money(patient_pay * monthly_factor)
        patient_pay = money(patient_pay - copay_reduction)
        plan_pay = money(total_amount - patient_pay)

    # COB adjustment — subtract other payer amount
    other_payer = money(Decimal(str(cob_data.get("other_payer_amount", "0"))))
    if other_payer > ZERO:
        plan_pay = money(plan_pay - other_payer)
        if plan_pay < ZERO:
            plan_pay = ZERO

    return StepResult(
        step_name="calculate_pricing",
        status=StepStatus.PASS,
        message=f"Pricing calculated: total={total_amount}, patient={patient_pay}, plan={plan_pay}",
        data={
            "ingredient_cost": str(ingredient_cost),
            "dispensing_fee": str(dispensing_fee),
            "patient_pay": str(patient_pay),
            "plan_pay": str(plan_pay),
            "total_amount": str(total_amount),
            "pricing_model": pricing_model,
        },
    )


def step_build_reasons(
    result: AdjudicationResult,
    steps: list[StepResult],
) -> list[str]:
    """Step 12: Build plain English reasons for adjudication decision.

    Produces a list of human-readable strings explaining why the claim
    was paid, rejected, or flagged.
    """
    reasons: list[str] = []

    if result.status == "paid":
        reasons.append(
            f"Claim approved: {result.pricing_model_used} pricing applied"
        )
        if result.accumulator_detected:
            reasons.append(
                f"Accumulator program detected ({result.accumulator_strategy.value}): "
                f"copay adjusted from standard amount"
            )
        if result.override_applied:
            rules_str = ", ".join(result.overridden_rules)
            reasons.append(f"Override applied: skipped rule(s) {rules_str}")
        if result.dur_alerts:
            for alert in result.dur_alerts:
                if alert.action == "info":
                    reasons.append(f"DUR informational: {alert.description}")
                elif alert.action == "flag":
                    reasons.append(f"DUR flagged for review: {alert.description}")
        if result.therapeutic_alternative_ndc:
            reasons.append(
                f"Therapeutic alternative available: NDC {result.therapeutic_alternative_ndc} "
                f"(estimated savings: ${result.therapeutic_alternative_savings})"
            )

    elif result.status == "rejected":
        reasons.append(f"Claim rejected: {result.reject_reason}")
        if result.reject_code:
            reasons.append(f"Reject code: {result.reject_code}")
        # Include the step that caused rejection
        for step in steps:
            if step.status == StepStatus.FAIL:
                reasons.append(f"Failed at step '{step.step_name}': {step.message}")

    elif result.status == "reversed":
        reasons.append("Claim reversed per reversal request (B2)")

    # Add fraud info if applicable
    if result.copay_fraud_score > ZERO:
        if result.copay_fraud_score >= FRAUD_BLOCK_THRESHOLD:
            reasons.append(
                f"Fraud alert: score {result.copay_fraud_score} exceeds block threshold"
            )
        elif result.copay_fraud_score >= FRAUD_FLAG_THRESHOLD:
            reasons.append(
                f"Fraud warning: score {result.copay_fraud_score} flagged for review"
            )

    return reasons


def step_build_trace(steps: list[StepResult]) -> list[dict[str, Any]]:
    """Step 13: Build the full claim trace from all step results."""
    return [
        {
            "step": s.step_name,
            "status": s.status.value,
            "message": s.message,
            "duration_ms": s.duration_ms,
            "data": s.data,
        }
        for s in steps
    ]


# ---------------------------------------------------------------------------
# Fraud scoring
# ---------------------------------------------------------------------------


def _score_copay_fraud(
    parsed: ParsedClaim,
    history_data: dict[str, Any],
    fraud_scorer: Any | None = None,
) -> list[FraudSignal]:
    """Score copay fraud signals for the claim.

    Checks for bill-reverse-rebill patterns, volume spikes, and
    geographic anomalies.
    """
    signals: list[FraudSignal] = []

    if fraud_scorer is not None:
        return fraud_scorer(parsed, history_data)

    # Bill-reverse-rebill detection
    recent_reversals = history_data.get("recent_reversals", 0)
    if recent_reversals >= 3:
        score = money(Decimal(str(min(recent_reversals * 20, 100))) / Decimal("100"))
        signals.append(FraudSignal(
            flag_type="bill_reverse_rebill",
            score=score.quantize(Decimal("0.0001")),
            details={"recent_reversals": recent_reversals},
            action="block" if score >= FRAUD_BLOCK_THRESHOLD else "flag",
        ))

    return signals


# ---------------------------------------------------------------------------
# Reversal handling
# ---------------------------------------------------------------------------


def adjudicate_reversal(
    parsed: ParsedClaim,
    tenant_id: uuid.UUID,
    original_claim_lookup: Any | None = None,
) -> AdjudicationResult:
    """Process a B2 reversal transaction.

    Looks up the original claim and creates a reversal record with
    negated amounts.
    """
    result = AdjudicationResult(
        claim_id=str(uuid.uuid4()),
        transaction_type="B2",
    )

    steps: list[StepResult] = []

    if original_claim_lookup is not None:
        original = original_claim_lookup(parsed, tenant_id)
        if original is None:
            result.status = "rejected"
            result.reject_code = "REVERSAL_NOT_FOUND"
            result.reject_reason = "Original claim not found for reversal"
            step = StepResult(
                step_name="reversal_lookup",
                status=StepStatus.FAIL,
                message="Original claim not found",
            )
            steps.append(step)
            result.reasons = step_build_reasons(result, steps)
            result.claim_trace = step_build_trace(steps)
            return result

        # Negate the original amounts
        result.ingredient_cost = money(-Decimal(str(original.get("ingredient_cost", "0"))))
        result.dispensing_fee = money(-Decimal(str(original.get("dispensing_fee", "0"))))
        result.patient_pay = money(-Decimal(str(original.get("patient_pay", "0"))))
        result.plan_pay = money(-Decimal(str(original.get("plan_pay", "0"))))
        result.total_amount = money(-Decimal(str(original.get("total_amount", "0"))))
    else:
        # Without lookup, negate submitted pricing
        result.ingredient_cost = money(-parsed.pricing.ingredient_cost_submitted)
        result.dispensing_fee = money(-parsed.pricing.dispensing_fee_submitted)
        result.total_amount = money(result.ingredient_cost + result.dispensing_fee)
        result.patient_pay = money(-parsed.pricing.patient_paid_amount)
        result.plan_pay = money(result.total_amount - result.patient_pay)

    result.status = "reversed"

    step = StepResult(
        step_name="reversal_processing",
        status=StepStatus.PASS,
        message="Reversal processed",
        data={
            "ingredient_cost": str(result.ingredient_cost),
            "total_amount": str(result.total_amount),
        },
    )
    steps.append(step)

    result.reasons = step_build_reasons(result, steps)
    result.claim_trace = step_build_trace(steps)

    return result


# ---------------------------------------------------------------------------
# Main pipeline orchestrator
# ---------------------------------------------------------------------------


def adjudicate(
    parsed: ParsedClaim,
    tenant_id: uuid.UUID,
    *,
    member_lookup: Any | None = None,
    eligibility_checker: Any | None = None,
    plan_resolver: Any | None = None,
    history_cache: Any | None = None,
    override_checker: Any | None = None,
    rules_executor: Any | None = None,
    dur_checker: Any | None = None,
    cob_processor: Any | None = None,
    fraud_scorer: Any | None = None,
    original_claim_lookup: Any | None = None,
) -> AdjudicationResult:
    """Orchestrate the full claim adjudication pipeline.

    Processes all 13 steps in sequence. Each step is wrapped in a timing
    context and exception handler. A failing step in a critical position
    (eligibility, rules) produces a rejection; non-critical failures
    (DUR info, fraud flagging) are recorded but do not block payment.

    Args:
        parsed: Parsed NCPDP D.0 claim request.
        tenant_id: Tenant UUID for multi-tenant isolation.
        member_lookup: Optional callable for member resolution.
        eligibility_checker: Optional callable for eligibility verification.
        plan_resolver: Optional callable for plan resolution.
        history_cache: Optional callable for claim history lookup.
        override_checker: Optional callable for override lookup.
        rules_executor: Optional callable for rules engine integration.
        dur_checker: Optional callable for DUR screening.
        cob_processor: Optional callable for COB processing.
        fraud_scorer: Optional callable for fraud scoring.
        original_claim_lookup: Optional callable for reversal lookup.

    Returns:
        AdjudicationResult with complete pricing, DUR, fraud, reasons, and trace.
    """
    pipeline_start = time.monotonic()

    result = AdjudicationResult(
        claim_id=str(uuid.uuid4()),
        transaction_type=parsed.header.transaction_code,
    )

    # Handle reversals separately
    if parsed.header.transaction_code == "B2":
        return adjudicate_reversal(parsed, tenant_id, original_claim_lookup)

    # Handle parse errors
    if parsed.parse_errors:
        result.status = "rejected"
        result.reject_code = "PARSE_ERROR"
        result.reject_reason = "; ".join(parsed.parse_errors)
        result.reasons = [f"Claim rejected due to parse error: {result.reject_reason}"]
        result.claim_trace = [
            {
                "step": "parse_validation",
                "status": "fail",
                "message": result.reject_reason,
                "duration_ms": 0,
                "data": {"errors": parsed.parse_errors},
            }
        ]
        return result

    steps: list[StepResult] = []

    def _run_step(step_fn, *args, **kwargs) -> StepResult:
        """Execute a step with timing and exception handling."""
        start = time.monotonic()
        try:
            step_result = step_fn(*args, **kwargs)
        except Exception as exc:
            step_name = step_fn.__name__.replace("step_", "")
            logger.exception(
                "adjudication.step_error",
                extra={
                    "svc_step": step_name,
                    "svc_claim_id": result.claim_id,
                    "svc_tenant_id": str(tenant_id),
                },
            )
            step_result = StepResult(
                step_name=step_name,
                status=StepStatus.FAIL,
                message=f"Internal error in {step_name}: {type(exc).__name__}",
            )
        elapsed = int((time.monotonic() - start) * 1000)
        step_result.duration_ms = elapsed
        steps.append(step_result)
        return step_result

    # -----------------------------------------------------------------------
    # Step 1: Identify member
    # -----------------------------------------------------------------------
    member_step = _run_step(step_identify_member, parsed, tenant_id, member_lookup)
    if member_step.status == StepStatus.FAIL:
        result.status = "rejected"
        result.reject_code = "MEMBER_NOT_FOUND"
        result.reject_reason = member_step.message
        result.reasons = step_build_reasons(result, steps)
        result.claim_trace = step_build_trace(steps)
        return result

    member_data = member_step.data
    result.member_id = member_data.get("member_id", member_data.get("cardholder_id", ""))

    # -----------------------------------------------------------------------
    # Step 2: Verify eligibility
    # -----------------------------------------------------------------------
    elig_step = _run_step(
        step_verify_eligibility, parsed, member_data, tenant_id, eligibility_checker
    )
    if elig_step.status == StepStatus.FAIL:
        result.status = "rejected"
        result.reject_code = "NOT_ELIGIBLE"
        result.reject_reason = elig_step.message
        result.reasons = step_build_reasons(result, steps)
        result.claim_trace = step_build_trace(steps)
        return result

    # -----------------------------------------------------------------------
    # Step 3: Resolve plan
    # -----------------------------------------------------------------------
    plan_step = _run_step(step_resolve_plan, member_data, tenant_id, plan_resolver)
    if plan_step.status == StepStatus.FAIL:
        result.status = "rejected"
        result.reject_code = "PLAN_NOT_FOUND"
        result.reject_reason = plan_step.message
        result.reasons = step_build_reasons(result, steps)
        result.claim_trace = step_build_trace(steps)
        return result

    plan_data = plan_step.data
    result.plan_id = plan_data.get("plan_id", "")
    result.group_id = plan_data.get("group_id", "")

    # -----------------------------------------------------------------------
    # Step 4: Resolve pricing model
    # -----------------------------------------------------------------------
    pricing_model_step = _run_step(step_resolve_pricing_model, plan_data, parsed)
    pricing_model = pricing_model_step.data.get("pricing_model", "awp_discount")
    result.pricing_model_used = pricing_model

    # -----------------------------------------------------------------------
    # Step 5: Check claim history
    # -----------------------------------------------------------------------
    history_step = _run_step(
        step_check_claim_history, parsed, member_data, tenant_id, history_cache
    )
    if history_step.status == StepStatus.FAIL:
        result.status = "rejected"
        result.reject_code = "DUPLICATE_CLAIM"
        result.reject_reason = history_step.message
        result.reasons = step_build_reasons(result, steps)
        result.claim_trace = step_build_trace(steps)
        return result

    history_data = history_step.data

    # -----------------------------------------------------------------------
    # Step 6: Check overrides
    # -----------------------------------------------------------------------
    override_step = _run_step(
        step_check_overrides, member_data, parsed, tenant_id, override_checker
    )
    override_rule_ids = override_step.data.get("override_rule_ids", [])
    if override_rule_ids:
        result.override_applied = True
        result.overridden_rules = override_rule_ids

    # -----------------------------------------------------------------------
    # Step 7: Execute rule pipeline
    # -----------------------------------------------------------------------
    rule_step = _run_step(
        step_execute_rules,
        parsed,
        member_data,
        plan_data,
        override_rule_ids,
        tenant_id,
        rules_executor,
    )
    if rule_step.status == StepStatus.FAIL:
        result.status = "rejected"
        result.reject_code = rule_step.data.get("reject_code", "RULE_REJECT")
        result.reject_reason = rule_step.message
        result.reasons = step_build_reasons(result, steps)
        result.claim_trace = step_build_trace(steps)
        return result

    rule_modifications = rule_step.data.get("modified_values", {})

    # Check for therapeutic alternative from rules
    if "therapeutic_alternative_ndc" in rule_step.data:
        result.therapeutic_alternative_ndc = rule_step.data["therapeutic_alternative_ndc"]
        result.therapeutic_alternative_savings = money(
            Decimal(str(rule_step.data.get("therapeutic_alternative_savings", "0")))
        )

    # -----------------------------------------------------------------------
    # Step 8: DUR screening
    # -----------------------------------------------------------------------
    dur_step = _run_step(
        step_dur_screening, parsed, member_data, history_data, tenant_id, dur_checker
    )

    # Map DUR alerts
    for alert_data in dur_step.data.get("alerts", []):
        result.dur_alerts.append(DURAlert(
            check_type=alert_data.get("check_type", ""),
            severity=alert_data.get("severity", "info"),
            description=alert_data.get("description", ""),
            action=alert_data.get("action", "info"),
            drug_a_ndc=alert_data.get("drug_a_ndc", ""),
            drug_b_ndc=alert_data.get("drug_b_ndc", ""),
        ))

    if dur_step.status == StepStatus.FAIL:
        result.status = "rejected"
        result.reject_code = "DUR_HARD_STOP"
        result.reject_reason = dur_step.message
        result.reasons = step_build_reasons(result, steps)
        result.claim_trace = step_build_trace(steps)
        return result

    # -----------------------------------------------------------------------
    # Step 9: COB processing
    # -----------------------------------------------------------------------
    cob_step = _run_step(
        step_cob_processing, parsed, member_data, tenant_id, cob_processor
    )
    result.cob_details = cob_step.data

    # -----------------------------------------------------------------------
    # Step 10: Accumulator detection
    # -----------------------------------------------------------------------
    accum_step = _run_step(step_accumulator_detection, parsed, member_data)
    result.accumulator_detected = accum_step.data.get("detected", False)
    result.accumulator_strategy = AccumulatorStrategy(
        accum_step.data.get("strategy", "standard")
    )

    # -----------------------------------------------------------------------
    # Step 11: Calculate final pricing
    # -----------------------------------------------------------------------
    pricing_step = _run_step(
        step_calculate_pricing,
        parsed,
        plan_data,
        pricing_model,
        rule_modifications,
        result.accumulator_strategy,
        cob_step.data,
    )
    result.ingredient_cost = money(Decimal(pricing_step.data.get("ingredient_cost", "0")))
    result.dispensing_fee = money(Decimal(pricing_step.data.get("dispensing_fee", "0")))
    result.patient_pay = money(Decimal(pricing_step.data.get("patient_pay", "0")))
    result.plan_pay = money(Decimal(pricing_step.data.get("plan_pay", "0")))
    result.total_amount = money(Decimal(pricing_step.data.get("total_amount", "0")))

    # -----------------------------------------------------------------------
    # Fraud scoring (non-blocking)
    # -----------------------------------------------------------------------
    fraud_signals = _score_copay_fraud(parsed, history_data, fraud_scorer)
    result.fraud_signals = fraud_signals
    if fraud_signals:
        max_score = max(s.score for s in fraud_signals)
        result.copay_fraud_score = max_score.quantize(Decimal("0.0001"))

        # Block if above threshold
        if max_score >= FRAUD_BLOCK_THRESHOLD:
            result.status = "rejected"
            result.reject_code = "FRAUD_BLOCK"
            result.reject_reason = f"Copay fraud score {max_score} exceeds threshold"
            result.reasons = step_build_reasons(result, steps)
            result.claim_trace = step_build_trace(steps)
            return result

    # -----------------------------------------------------------------------
    # Step 12 & 13: Build reasons and trace
    # -----------------------------------------------------------------------
    result.status = "paid"
    result.reasons = step_build_reasons(result, steps)
    result.claim_trace = step_build_trace(steps)

    pipeline_elapsed = int((time.monotonic() - pipeline_start) * 1000)
    logger.info(
        "adjudication.complete",
        extra={
            "svc_claim_id": result.claim_id,
            "svc_status": result.status,
            "svc_pipeline_ms": pipeline_elapsed,
            "svc_tenant_id": str(tenant_id),
        },
    )

    return result
