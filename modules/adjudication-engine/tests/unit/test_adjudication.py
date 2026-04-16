"""Critical path tests for the adjudication pipeline.

Tests cover: B1 adjudication with pricing, B2 reversal, B3 rebill,
DUR drug-drug interaction, accumulator detection from OC signals,
override skips rule and logs in trace, cannot override DUR critical
hard stop, plain English reasons, all pricing Decimal, claim trace
contains all steps, copay fraud scoring, therapeutic alternative.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.services.adjudication_pipeline import (
    FRAUD_BLOCK_THRESHOLD,
    FRAUD_FLAG_THRESHOLD,
    AccumulatorStrategy,
    AdjudicationResult,
    DURAlert,
    FraudSignal,
    StepResult,
    StepStatus,
    adjudicate,
    adjudicate_reversal,
    step_accumulator_detection,
    step_build_reasons,
    step_build_trace,
    step_calculate_pricing,
    step_check_claim_history,
    step_check_overrides,
    step_dur_screening,
    step_execute_rules,
    step_identify_member,
    step_verify_eligibility,
)
from src.services.ncpdp_parser import (
    ClaimSegment,
    HeaderSegment,
    InsuranceSegment,
    ParsedClaim,
    PatientSegment,
    PricingSegment,
)
from src.services.override_service import (
    ALL_NON_OVERRIDABLE,
    OverrideError,
    check_overrides,
    create_override,
    is_overridable,
)

TENANT_ID = uuid.uuid4()
MEMBER_ID = uuid.uuid4()


def _make_parsed_claim(
    transaction_code: str = "B1",
    ndc: str = "00000000001",
    quantity: Decimal = Decimal("30.0000"),
    days_supply: int = 30,
    ingredient_cost: Decimal = Decimal("100.00"),
    dispensing_fee: Decimal = Decimal("5.00"),
    other_coverage_code: str = "",
    cardholder_id: str = "CARD001",
    person_code: str = "01",
    dob: str = "19800101",
) -> ParsedClaim:
    """Build a ParsedClaim with sensible defaults for testing."""
    return ParsedClaim(
        header=HeaderSegment(
            version="D0",
            transaction_code=transaction_code,
            bin_number="999999",
            pcn="TEST",
        ),
        patient=PatientSegment(
            cardholder_id=cardholder_id,
            date_of_birth=dob,
            person_code=person_code,
        ),
        insurance=InsuranceSegment(
            cardholder_id=cardholder_id,
            group_id="GRP001",
            plan_id="PLAN001",
            other_coverage_code=other_coverage_code,
        ),
        claim=ClaimSegment(
            ndc=ndc,
            quantity_dispensed=quantity,
            days_supply=days_supply,
            other_coverage_code=other_coverage_code,
        ),
        pricing=PricingSegment(
            ingredient_cost_submitted=ingredient_cost,
            dispensing_fee_submitted=dispensing_fee,
        ),
    )


def _member_lookup(cardholder_id, person_code, dob, tenant_id):
    """Mock member lookup that always finds a member."""
    return {
        "member_id": str(MEMBER_ID),
        "cardholder_id": cardholder_id,
        "person_code": person_code,
        "plan_status": "active",
        "plan_id": "PLAN001",
        "group_id": "GRP001",
    }


def _plan_resolver(group_id, plan_id, tenant_id):
    """Mock plan resolver."""
    return {
        "plan_id": plan_id,
        "group_id": group_id,
        "pricing_model": "awp_discount",
    }


# ---------------------------------------------------------------------------
# Test: Standard B1 adjudication with pricing
# ---------------------------------------------------------------------------


class TestB1Adjudication:
    """Tests for standard B1 (new billing) claim adjudication."""

    def test_standard_b1_adjudication_produces_paid_status(self):
        parsed = _make_parsed_claim()
        result = adjudicate(
            parsed,
            TENANT_ID,
            member_lookup=_member_lookup,
            plan_resolver=_plan_resolver,
        )
        assert result.status == "paid"
        assert result.transaction_type == "B1"

    def test_b1_pricing_uses_submitted_values(self):
        parsed = _make_parsed_claim(
            ingredient_cost=Decimal("250.00"),
            dispensing_fee=Decimal("10.00"),
        )
        result = adjudicate(
            parsed,
            TENANT_ID,
            member_lookup=_member_lookup,
            plan_resolver=_plan_resolver,
        )
        assert result.ingredient_cost == Decimal("250.00")
        assert result.dispensing_fee == Decimal("10.00")
        assert result.total_amount == Decimal("260.00")

    def test_b1_with_copay_from_rules(self):
        """When rules engine sets copay, patient_pay and plan_pay are calculated."""

        def rules_executor(parsed, member, plan, overrides, tid):
            return {
                "action": "pass",
                "modified_values": {"copay": Decimal("25.00")},
                "warnings": [],
            }

        parsed = _make_parsed_claim(
            ingredient_cost=Decimal("100.00"),
            dispensing_fee=Decimal("5.00"),
        )
        result = adjudicate(
            parsed,
            TENANT_ID,
            member_lookup=_member_lookup,
            plan_resolver=_plan_resolver,
            rules_executor=rules_executor,
        )
        assert result.status == "paid"
        assert result.patient_pay == Decimal("25.00")
        assert result.plan_pay == Decimal("80.00")
        assert result.total_amount == Decimal("105.00")

    def test_b1_rejected_when_member_not_found(self):
        def no_member(cardholder_id, person_code, dob, tenant_id):
            return None

        parsed = _make_parsed_claim()
        result = adjudicate(parsed, TENANT_ID, member_lookup=no_member)
        assert result.status == "rejected"
        assert result.reject_code == "MEMBER_NOT_FOUND"

    def test_b1_rejected_when_not_eligible(self):
        def ineligible_member(cardholder_id, person_code, dob, tenant_id):
            return {
                "member_id": str(MEMBER_ID),
                "plan_status": "terminated",
                "plan_id": "PLAN001",
                "group_id": "GRP001",
            }

        parsed = _make_parsed_claim()
        result = adjudicate(parsed, TENANT_ID, member_lookup=ineligible_member)
        assert result.status == "rejected"
        assert result.reject_code == "NOT_ELIGIBLE"


# ---------------------------------------------------------------------------
# Test: B2 reversal
# ---------------------------------------------------------------------------


class TestB2Reversal:
    """Tests for B2 (reversal) transaction processing."""

    def test_b2_reversal_negates_amounts(self):
        parsed = _make_parsed_claim(
            transaction_code="B2",
            ingredient_cost=Decimal("100.00"),
            dispensing_fee=Decimal("5.00"),
        )
        result = adjudicate(parsed, TENANT_ID)
        assert result.status == "reversed"
        assert result.transaction_type == "B2"
        assert result.ingredient_cost == Decimal("-100.00")
        assert result.dispensing_fee == Decimal("-5.00")
        assert result.total_amount == Decimal("-105.00")

    def test_b2_reversal_with_original_claim_lookup(self):
        def original_lookup(parsed, tenant_id):
            return {
                "ingredient_cost": "200.00",
                "dispensing_fee": "10.00",
                "patient_pay": "25.00",
                "plan_pay": "185.00",
                "total_amount": "210.00",
            }

        parsed = _make_parsed_claim(transaction_code="B2")
        result = adjudicate(
            parsed,
            TENANT_ID,
            original_claim_lookup=original_lookup,
        )
        assert result.status == "reversed"
        assert result.ingredient_cost == Decimal("-200.00")
        assert result.patient_pay == Decimal("-25.00")
        assert result.plan_pay == Decimal("-185.00")

    def test_b2_reversal_not_found_rejects(self):
        def no_original(parsed, tenant_id):
            return None

        parsed = _make_parsed_claim(transaction_code="B2")
        result = adjudicate(
            parsed,
            TENANT_ID,
            original_claim_lookup=no_original,
        )
        assert result.status == "rejected"
        assert result.reject_code == "REVERSAL_NOT_FOUND"

    def test_b2_reversal_has_reasons_and_trace(self):
        parsed = _make_parsed_claim(transaction_code="B2")
        result = adjudicate(parsed, TENANT_ID)
        assert result.status == "reversed"
        assert any("reversed" in r.lower() for r in result.reasons)
        assert len(result.claim_trace) > 0


# ---------------------------------------------------------------------------
# Test: B3 rebill
# ---------------------------------------------------------------------------


class TestB3Rebill:
    """Tests for B3 (rebill) transactions — processed like B1."""

    def test_b3_rebill_adjudicates_like_b1(self):
        parsed = _make_parsed_claim(transaction_code="B3")
        result = adjudicate(
            parsed,
            TENANT_ID,
            member_lookup=_member_lookup,
            plan_resolver=_plan_resolver,
        )
        assert result.status == "paid"
        assert result.transaction_type == "B3"


# ---------------------------------------------------------------------------
# Test: DUR catches drug-drug interaction
# ---------------------------------------------------------------------------


class TestDURScreening:
    """Tests for DUR screening step."""

    def test_dur_catches_drug_drug_interaction(self):
        def dur_checker(parsed, member, tid):
            return [
                {
                    "check_type": "drug_drug",
                    "severity": "critical",
                    "description": "Warfarin + Aspirin: increased bleeding risk",
                    "action": "reject",
                    "drug_a_ndc": "00000000001",
                    "drug_b_ndc": "00000000002",
                }
            ]

        parsed = _make_parsed_claim()
        result = adjudicate(
            parsed,
            TENANT_ID,
            member_lookup=_member_lookup,
            plan_resolver=_plan_resolver,
            dur_checker=dur_checker,
        )
        assert result.status == "rejected"
        assert result.reject_code == "DUR_HARD_STOP"
        assert len(result.dur_alerts) == 1
        assert result.dur_alerts[0].check_type == "drug_drug"
        assert result.dur_alerts[0].severity == "critical"

    def test_dur_info_alert_does_not_reject(self):
        def dur_checker(parsed, member, tid):
            return [
                {
                    "check_type": "therapeutic_dup",
                    "severity": "info",
                    "description": "Multiple SSRIs on profile",
                    "action": "info",
                }
            ]

        parsed = _make_parsed_claim()
        result = adjudicate(
            parsed,
            TENANT_ID,
            member_lookup=_member_lookup,
            plan_resolver=_plan_resolver,
            dur_checker=dur_checker,
        )
        assert result.status == "paid"
        assert len(result.dur_alerts) == 1


# ---------------------------------------------------------------------------
# Test: Accumulator detection from OC signals
# ---------------------------------------------------------------------------


class TestAccumulatorDetection:
    """Tests for accumulator/maximizer detection."""

    def test_accumulator_detected_from_oc2(self):
        parsed = _make_parsed_claim(other_coverage_code="2")
        result = step_accumulator_detection(parsed, {})
        assert result.data["detected"] is True
        assert result.data["strategy"] == "accumulator"

    def test_maximizer_detected_from_oc8(self):
        parsed = _make_parsed_claim(other_coverage_code="8")
        result = step_accumulator_detection(parsed, {})
        assert result.data["detected"] is True
        assert result.data["strategy"] == "maximizer"

    def test_no_accumulator_for_standard_claim(self):
        parsed = _make_parsed_claim(other_coverage_code="")
        result = step_accumulator_detection(parsed, {})
        assert result.data["detected"] is False
        assert result.data["strategy"] == "standard"

    def test_accumulator_adjusts_copay_in_pipeline(self):
        """Full pipeline with accumulator adjusts copay downward."""

        def rules_executor(parsed, member, plan, overrides, tid):
            return {
                "action": "pass",
                "modified_values": {"copay": Decimal("100.00")},
                "warnings": [],
            }

        parsed = _make_parsed_claim(
            ingredient_cost=Decimal("500.00"),
            dispensing_fee=Decimal("10.00"),
            other_coverage_code="2",
        )
        result = adjudicate(
            parsed,
            TENANT_ID,
            member_lookup=_member_lookup,
            plan_resolver=_plan_resolver,
            rules_executor=rules_executor,
        )
        assert result.status == "paid"
        assert result.accumulator_detected is True
        # Accumulator reduces copay to 10% of normal
        assert result.patient_pay == Decimal("10.00")
        assert result.plan_pay == Decimal("500.00")


# ---------------------------------------------------------------------------
# Test: Override skips rule and logs in trace
# ---------------------------------------------------------------------------


class TestOverrideInPipeline:
    """Tests for override integration with the pipeline."""

    def test_override_skips_rule_and_appears_in_trace(self):
        rule_id = uuid.uuid4()

        def override_checker(member_id, ndc, tid):
            return [{"rule_id": str(rule_id), "rule_type": "quantity_limit_rule"}]

        parsed = _make_parsed_claim()
        result = adjudicate(
            parsed,
            TENANT_ID,
            member_lookup=_member_lookup,
            plan_resolver=_plan_resolver,
            override_checker=override_checker,
        )
        assert result.status == "paid"
        assert result.override_applied is True
        assert str(rule_id) in result.overridden_rules

        # Verify trace contains override step
        trace_steps = [t["step"] for t in result.claim_trace]
        assert "check_overrides" in trace_steps
        override_trace = next(
            t for t in result.claim_trace if t["step"] == "check_overrides"
        )
        assert "Active overrides found" in override_trace["message"]


# ---------------------------------------------------------------------------
# Test: Cannot override DUR critical hard stop
# ---------------------------------------------------------------------------


class TestOverrideSafety:
    """Tests for override safety guardrails."""

    def test_cannot_override_dur_critical_drug_drug(self):
        with pytest.raises(OverrideError, match="DUR critical hard stop"):
            create_override(
                tenant_id=TENANT_ID,
                member_id=MEMBER_ID,
                rule_id=uuid.uuid4(),
                rule_type="dur_critical_drug_drug",
                scope="member_rule_any",
                reason_code="CLINICAL",
                reason_text="Override requested",
                duration_type="one_time",
                created_by="user123",
            )

    def test_cannot_override_government_exclusion(self):
        with pytest.raises(OverrideError, match="government exclusion rule"):
            create_override(
                tenant_id=TENANT_ID,
                member_id=MEMBER_ID,
                rule_id=uuid.uuid4(),
                rule_type="govt_excluded_drug",
                scope="member_rule_any",
                reason_code="BUSINESS",
                reason_text="Override requested",
                duration_type="one_time",
                created_by="user123",
            )

    def test_all_non_overridable_types_rejected(self):
        for rule_type in ALL_NON_OVERRIDABLE:
            with pytest.raises(OverrideError):
                create_override(
                    tenant_id=TENANT_ID,
                    member_id=MEMBER_ID,
                    rule_id=uuid.uuid4(),
                    rule_type=rule_type,
                    scope="member_rule_any",
                    reason_code="TEST",
                    reason_text="Test",
                    duration_type="one_time",
                    created_by="user123",
                )

    def test_is_overridable_returns_false_for_non_overridable(self):
        for rule_type in ALL_NON_OVERRIDABLE:
            assert is_overridable(rule_type) is False

    def test_is_overridable_returns_true_for_standard_rules(self):
        assert is_overridable("copay_rule") is True
        assert is_overridable("quantity_limit_rule") is True


# ---------------------------------------------------------------------------
# Test: Reasons for adjudication in plain English
# ---------------------------------------------------------------------------


class TestPlainEnglishReasons:
    """Tests for human-readable adjudication reasons."""

    def test_paid_claim_has_pricing_reason(self):
        parsed = _make_parsed_claim()
        result = adjudicate(
            parsed,
            TENANT_ID,
            member_lookup=_member_lookup,
            plan_resolver=_plan_resolver,
        )
        assert result.status == "paid"
        assert len(result.reasons) > 0
        assert any("approved" in r.lower() or "pricing" in r.lower() for r in result.reasons)

    def test_rejected_claim_explains_reason(self):
        def no_member(cid, pc, dob, tid):
            return None

        parsed = _make_parsed_claim()
        result = adjudicate(parsed, TENANT_ID, member_lookup=no_member)
        assert result.status == "rejected"
        assert any("rejected" in r.lower() or "not found" in r.lower() for r in result.reasons)

    def test_accumulator_claim_mentions_accumulator(self):
        parsed = _make_parsed_claim(other_coverage_code="2")
        result = adjudicate(
            parsed,
            TENANT_ID,
            member_lookup=_member_lookup,
            plan_resolver=_plan_resolver,
        )
        assert any("accumulator" in r.lower() for r in result.reasons)

    def test_override_claim_mentions_override(self):
        def override_checker(member_id, ndc, tid):
            return [{"rule_id": "R001", "rule_type": "quantity_limit_rule"}]

        parsed = _make_parsed_claim()
        result = adjudicate(
            parsed,
            TENANT_ID,
            member_lookup=_member_lookup,
            plan_resolver=_plan_resolver,
            override_checker=override_checker,
        )
        assert any("override" in r.lower() for r in result.reasons)


# ---------------------------------------------------------------------------
# Test: All pricing results are Decimal, never float
# ---------------------------------------------------------------------------


class TestDecimalPrecision:
    """Tests ensuring all money values are Decimal, never float."""

    def test_all_pricing_fields_are_decimal(self):
        parsed = _make_parsed_claim(
            ingredient_cost=Decimal("123.456"),
            dispensing_fee=Decimal("7.89"),
        )
        result = adjudicate(
            parsed,
            TENANT_ID,
            member_lookup=_member_lookup,
            plan_resolver=_plan_resolver,
        )
        assert isinstance(result.ingredient_cost, Decimal)
        assert isinstance(result.dispensing_fee, Decimal)
        assert isinstance(result.patient_pay, Decimal)
        assert isinstance(result.plan_pay, Decimal)
        assert isinstance(result.total_amount, Decimal)

    def test_pricing_rounded_to_two_decimal_places(self):
        parsed = _make_parsed_claim(
            ingredient_cost=Decimal("123.456"),
            dispensing_fee=Decimal("7.894"),
        )
        result = adjudicate(
            parsed,
            TENANT_ID,
            member_lookup=_member_lookup,
            plan_resolver=_plan_resolver,
        )
        # All money values should be 2 decimal places
        assert result.ingredient_cost == Decimal("123.46")  # rounded up
        assert result.dispensing_fee == Decimal("7.89")

    def test_reversal_amounts_are_decimal(self):
        parsed = _make_parsed_claim(
            transaction_code="B2",
            ingredient_cost=Decimal("100.00"),
        )
        result = adjudicate(parsed, TENANT_ID)
        assert isinstance(result.ingredient_cost, Decimal)
        assert isinstance(result.total_amount, Decimal)

    def test_copay_fraud_score_is_decimal(self):
        def fraud_scorer(parsed, history):
            return [FraudSignal(
                flag_type="volume_spike",
                score=Decimal("0.6500"),
                action="flag",
            )]

        parsed = _make_parsed_claim()
        result = adjudicate(
            parsed,
            TENANT_ID,
            member_lookup=_member_lookup,
            plan_resolver=_plan_resolver,
            fraud_scorer=fraud_scorer,
        )
        assert isinstance(result.copay_fraud_score, Decimal)
        assert result.copay_fraud_score == Decimal("0.6500")


# ---------------------------------------------------------------------------
# Test: Claim trace contains all steps
# ---------------------------------------------------------------------------


class TestClaimTrace:
    """Tests for claim trace completeness."""

    def test_paid_claim_trace_contains_all_steps(self):
        parsed = _make_parsed_claim()
        result = adjudicate(
            parsed,
            TENANT_ID,
            member_lookup=_member_lookup,
            plan_resolver=_plan_resolver,
        )
        assert result.status == "paid"
        trace_steps = [t["step"] for t in result.claim_trace]

        expected_steps = [
            "identify_member",
            "verify_eligibility",
            "resolve_plan",
            "resolve_pricing_model",
            "check_claim_history",
            "check_overrides",
            "execute_rules",
            "dur_screening",
            "cob_processing",
            "accumulator_detection",
            "calculate_pricing",
        ]
        for step in expected_steps:
            assert step in trace_steps, f"Missing step in trace: {step}"

    def test_each_trace_entry_has_required_fields(self):
        parsed = _make_parsed_claim()
        result = adjudicate(
            parsed,
            TENANT_ID,
            member_lookup=_member_lookup,
            plan_resolver=_plan_resolver,
        )
        for entry in result.claim_trace:
            assert "step" in entry
            assert "status" in entry
            assert "message" in entry
            assert "duration_ms" in entry
            assert "data" in entry

    def test_rejected_claim_trace_stops_at_failure(self):
        def no_member(cid, pc, dob, tid):
            return None

        parsed = _make_parsed_claim()
        result = adjudicate(parsed, TENANT_ID, member_lookup=no_member)
        assert result.status == "rejected"
        trace_steps = [t["step"] for t in result.claim_trace]
        assert "identify_member" in trace_steps
        # Should not have steps after the failure
        assert "calculate_pricing" not in trace_steps


# ---------------------------------------------------------------------------
# Test: Copay fraud scoring
# ---------------------------------------------------------------------------


class TestCopayFraudScoring:
    """Tests for copay fraud detection and scoring."""

    def test_fraud_score_above_block_threshold_rejects(self):
        def fraud_scorer(parsed, history):
            return [FraudSignal(
                flag_type="bill_reverse_rebill",
                score=Decimal("0.9500"),
                details={"recent_reversals": 5},
                action="block",
            )]

        parsed = _make_parsed_claim()
        result = adjudicate(
            parsed,
            TENANT_ID,
            member_lookup=_member_lookup,
            plan_resolver=_plan_resolver,
            fraud_scorer=fraud_scorer,
        )
        assert result.status == "rejected"
        assert result.reject_code == "FRAUD_BLOCK"

    def test_fraud_score_below_threshold_passes(self):
        def fraud_scorer(parsed, history):
            return [FraudSignal(
                flag_type="volume_spike",
                score=Decimal("0.3000"),
                action="pass",
            )]

        parsed = _make_parsed_claim()
        result = adjudicate(
            parsed,
            TENANT_ID,
            member_lookup=_member_lookup,
            plan_resolver=_plan_resolver,
            fraud_scorer=fraud_scorer,
        )
        assert result.status == "paid"
        assert result.copay_fraud_score == Decimal("0.3000")

    def test_fraud_reasons_included_when_flagged(self):
        def fraud_scorer(parsed, history):
            return [FraudSignal(
                flag_type="collusion",
                score=Decimal("0.6000"),
                action="flag",
            )]

        parsed = _make_parsed_claim()
        result = adjudicate(
            parsed,
            TENANT_ID,
            member_lookup=_member_lookup,
            plan_resolver=_plan_resolver,
            fraud_scorer=fraud_scorer,
        )
        assert result.status == "paid"
        assert any("fraud" in r.lower() for r in result.reasons)


# ---------------------------------------------------------------------------
# Test: Therapeutic alternative returned
# ---------------------------------------------------------------------------


class TestTherapeuticAlternative:
    """Tests for therapeutic alternative suggestions."""

    def test_therapeutic_alternative_from_rules_engine(self):
        def rules_executor(parsed, member, plan, overrides, tid):
            return {
                "action": "pass",
                "modified_values": {},
                "warnings": [],
                "therapeutic_alternative_ndc": "99999999999",
                "therapeutic_alternative_savings": "45.00",
            }

        parsed = _make_parsed_claim()
        result = adjudicate(
            parsed,
            TENANT_ID,
            member_lookup=_member_lookup,
            plan_resolver=_plan_resolver,
            rules_executor=rules_executor,
        )
        assert result.status == "paid"
        assert result.therapeutic_alternative_ndc == "99999999999"
        assert result.therapeutic_alternative_savings == Decimal("45.00")
        assert any("alternative" in r.lower() for r in result.reasons)


# ---------------------------------------------------------------------------
# Test: Parse error handling
# ---------------------------------------------------------------------------


class TestParseErrorHandling:
    """Tests for claims with parse errors."""

    def test_parse_errors_produce_rejection(self):
        parsed = ParsedClaim(parse_errors=["Invalid transaction code: 'XX'"])
        result = adjudicate(parsed, TENANT_ID)
        assert result.status == "rejected"
        assert result.reject_code == "PARSE_ERROR"
        assert "Invalid transaction code" in result.reject_reason


# ---------------------------------------------------------------------------
# Test: Override service unit tests
# ---------------------------------------------------------------------------


class TestOverrideService:
    """Tests for the override service create/check/approve workflow."""

    def test_create_override_auto_approves_low_risk(self):
        override = create_override(
            tenant_id=TENANT_ID,
            member_id=MEMBER_ID,
            rule_id=uuid.uuid4(),
            rule_type="quantity_limit_rule",
            scope="member_rule_any",
            reason_code="CLINICAL",
            reason_text="Doctor requested higher quantity",
            duration_type="fixed_period",
            created_by="user123",
        )
        assert override["status"] == "active"
        assert override["approved_by"] == "user123"

    def test_create_override_requires_approval_for_financial(self):
        override = create_override(
            tenant_id=TENANT_ID,
            member_id=MEMBER_ID,
            rule_id=uuid.uuid4(),
            rule_type="copay_rule",
            scope="member_rule_any",
            reason_code="HARDSHIP",
            reason_text="Financial hardship",
            duration_type="benefit_year",
            created_by="user123",
        )
        assert override["status"] == "pending_approval"
        assert override["approved_by"] is None

    def test_check_overrides_finds_active_matching(self):
        rule_id = uuid.uuid4()
        overrides = [
            {
                "id": str(uuid.uuid4()),
                "tenant_id": str(TENANT_ID),
                "member_id": str(MEMBER_ID),
                "rule_id": str(rule_id),
                "rule_type": "quantity_limit_rule",
                "ndc": None,
                "scope": "member_rule_any",
                "status": "active",
                "expires_at": None,
            }
        ]
        result = check_overrides(
            member_id=MEMBER_ID,
            rule_id=rule_id,
            drug_ndc=None,
            tenant_id=TENANT_ID,
            overrides_store=overrides,
        )
        assert len(result) == 1

    def test_check_overrides_ignores_expired(self):
        from datetime import UTC, datetime, timedelta

        rule_id = uuid.uuid4()
        overrides = [
            {
                "id": str(uuid.uuid4()),
                "tenant_id": str(TENANT_ID),
                "member_id": str(MEMBER_ID),
                "rule_id": str(rule_id),
                "rule_type": "quantity_limit_rule",
                "ndc": None,
                "scope": "member_rule_any",
                "status": "active",
                "expires_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            }
        ]
        result = check_overrides(
            member_id=MEMBER_ID,
            rule_id=rule_id,
            drug_ndc=None,
            tenant_id=TENANT_ID,
            overrides_store=overrides,
        )
        assert len(result) == 0

    def test_check_overrides_drug_scope_requires_ndc_match(self):
        rule_id = uuid.uuid4()
        overrides = [
            {
                "id": str(uuid.uuid4()),
                "tenant_id": str(TENANT_ID),
                "member_id": str(MEMBER_ID),
                "rule_id": str(rule_id),
                "rule_type": "quantity_limit_rule",
                "ndc": "11111111111",
                "scope": "member_rule_drug",
                "status": "active",
                "expires_at": None,
            }
        ]
        # Matching NDC
        result = check_overrides(
            member_id=MEMBER_ID,
            rule_id=rule_id,
            drug_ndc="11111111111",
            tenant_id=TENANT_ID,
            overrides_store=overrides,
        )
        assert len(result) == 1

        # Non-matching NDC
        result = check_overrides(
            member_id=MEMBER_ID,
            rule_id=rule_id,
            drug_ndc="99999999999",
            tenant_id=TENANT_ID,
            overrides_store=overrides,
        )
        assert len(result) == 0

    def test_create_override_requires_ndc_for_drug_scope(self):
        with pytest.raises(OverrideError, match="requires an NDC"):
            create_override(
                tenant_id=TENANT_ID,
                member_id=MEMBER_ID,
                rule_id=uuid.uuid4(),
                rule_type="quantity_limit_rule",
                scope="member_rule_drug",
                reason_code="CLINICAL",
                reason_text="Test",
                duration_type="one_time",
                created_by="user123",
                ndc=None,
            )

    def test_create_override_invalid_scope_raises(self):
        with pytest.raises(OverrideError, match="Invalid scope"):
            create_override(
                tenant_id=TENANT_ID,
                member_id=MEMBER_ID,
                rule_id=uuid.uuid4(),
                rule_type="quantity_limit_rule",
                scope="invalid_scope",
                reason_code="CLINICAL",
                reason_text="Test",
                duration_type="one_time",
                created_by="user123",
            )
