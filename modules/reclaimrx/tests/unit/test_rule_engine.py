"""Tests for the detection rule engine — TDD first."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.services.rule_engine import (
    ClaimContext,
    RuleDefinition,
    RuleEvaluator,
    RuleResult,
)


def make_claim(**kwargs) -> ClaimContext:
    defaults = {
        "claim_id": "claim-001",
        "tenant_id": "tenant-001",
        "auth_number": "AUTH123",
        "date_of_service": date(2026, 1, 15),
        "pharmacy_npi": "1234567890",
        "pharmacy_name": "Test Pharmacy",
        "prescriber_npi": "0987654321",
        "member_id": "MEM001",
        "ndc": "12345678901",
        "drug_name": "TestDrug",
        "quantity": Decimal("30.000"),
        "days_supply": 30,
        "billed_amount": Decimal("100.00"),
        "paid_amount": Decimal("95.00"),
        "wac_per_unit": Decimal("3.00"),
        "awp_per_unit": Decimal("3.50"),
        "nq": Decimal("90.00"),
        "dv": Decimal("5.00"),
        "program_type": "manufacturer",
        "client_type": "manufacturer",
        "metadata": {},
    }
    defaults.update(kwargs)
    return ClaimContext(**defaults)


class TestRuleEvaluatorThreshold:
    """Test threshold-type rules (e.g., NQ inflation MFR-001)."""

    def test_nq_inflation_no_flag_when_within_threshold(self) -> None:
        rule = RuleDefinition(
            rule_code="MFR-001",
            name="NQ Inflation",
            rule_type="threshold",
            rule_logic={"field": "nq_to_wac_ratio", "operator": "gt", "threshold": 1.10},
            default_parameters={"threshold": 1.10},
            default_action="flag",
            confidence_scoring={"high": 1.50, "medium": 1.20, "low": 1.10},
            client_types=["manufacturer"],
            detection_mode="both",
        )
        # NQ=90, WAC=3.00x30=90.00 -> ratio=1.00, below threshold
        claim = make_claim(nq=Decimal("90.00"), wac_per_unit=Decimal("3.00"), quantity=Decimal("30.000"))
        evaluator = RuleEvaluator()
        result = evaluator.evaluate(rule, claim)
        assert result.flagged is False

    def test_nq_inflation_flags_when_above_threshold(self) -> None:
        rule = RuleDefinition(
            rule_code="MFR-001",
            name="NQ Inflation",
            rule_type="threshold",
            rule_logic={"field": "nq_to_wac_ratio", "operator": "gt", "threshold": 1.10},
            default_parameters={"threshold": 1.10},
            default_action="flag",
            confidence_scoring={"high": 1.50, "medium": 1.20, "low": 1.10},
            client_types=["manufacturer"],
            detection_mode="both",
        )
        # NQ=100, WAC=3.00x30=90.00 -> ratio=1.111, above 1.10 threshold
        claim = make_claim(nq=Decimal("100.00"), wac_per_unit=Decimal("3.00"), quantity=Decimal("30.000"))
        evaluator = RuleEvaluator()
        result = evaluator.evaluate(rule, claim)
        assert result.flagged is True
        assert result.action == "flag"
        assert result.confidence_tier == "low"

    def test_nq_inflation_high_confidence_at_150pct(self) -> None:
        rule = RuleDefinition(
            rule_code="MFR-001",
            name="NQ Inflation",
            rule_type="threshold",
            rule_logic={"field": "nq_to_wac_ratio", "operator": "gt", "threshold": 1.10},
            default_parameters={"threshold": 1.10},
            default_action="flag",
            confidence_scoring={"high": 1.50, "medium": 1.20, "low": 1.10},
            client_types=["manufacturer"],
            detection_mode="both",
        )
        # NQ=135+, WAC=90 → ratio>=1.50
        claim = make_claim(nq=Decimal("135.00"), wac_per_unit=Decimal("3.00"), quantity=Decimal("30.000"))
        evaluator = RuleEvaluator()
        result = evaluator.evaluate(rule, claim)
        assert result.flagged is True
        assert result.confidence_tier == "high"

    def test_rule_not_applicable_for_wrong_client_type(self) -> None:
        rule = RuleDefinition(
            rule_code="MFR-001",
            name="NQ Inflation",
            rule_type="threshold",
            rule_logic={"field": "nq_to_wac_ratio", "operator": "gt", "threshold": 1.10},
            default_parameters={"threshold": 1.10},
            default_action="flag",
            confidence_scoring={"high": 1.50, "medium": 1.20, "low": 1.10},
            client_types=["manufacturer"],
            detection_mode="both",
        )
        claim = make_claim(
            client_type="health_plan",
            nq=Decimal("200.00"),  # Way above threshold
            wac_per_unit=Decimal("3.00"),
            quantity=Decimal("30.000"),
        )
        evaluator = RuleEvaluator()
        result = evaluator.evaluate(rule, claim)
        assert result.flagged is False
        assert result.skip_reason == "client_type_mismatch"

    def test_universal_rule_applies_to_all_client_types(self) -> None:
        rule = RuleDefinition(
            rule_code="ALL-005",
            name="Early Refill",
            rule_type="threshold",
            rule_logic={"field": "refill_pct", "operator": "lt", "threshold": 0.75},
            default_parameters={"threshold": 0.75},
            default_action="flag",
            confidence_scoring={"medium": 0.75},
            client_types=["all"],
            detection_mode="both",
        )
        for client_type in ["manufacturer", "health_plan", "tpa", "340b", "workers_comp"]:
            claim = make_claim(client_type=client_type, metadata={"refill_pct": Decimal("0.50")})
            evaluator = RuleEvaluator()
            result = evaluator.evaluate(rule, claim)
            assert result.flagged is True, f"Should flag for {client_type}"


class TestRuleEvaluatorDuplicate:
    """Test duplicate detection rule (ALL-001)."""

    def test_duplicate_claim_flagged(self) -> None:
        rule = RuleDefinition(
            rule_code="ALL-001",
            name="Duplicate Claim",
            rule_type="pattern",
            rule_logic={"pattern": "duplicate_claim"},
            default_parameters={},
            default_action="block",
            confidence_scoring={"high": 1.0},
            client_types=["all"],
            detection_mode="both",
        )
        claim = make_claim(metadata={"is_duplicate": True, "original_auth": "AUTH001"})
        evaluator = RuleEvaluator()
        result = evaluator.evaluate(rule, claim)
        assert result.flagged is True
        assert result.action == "block"
        assert result.confidence_tier == "high"

    def test_non_duplicate_not_flagged(self) -> None:
        rule = RuleDefinition(
            rule_code="ALL-001",
            name="Duplicate Claim",
            rule_type="pattern",
            rule_logic={"pattern": "duplicate_claim"},
            default_parameters={},
            default_action="block",
            confidence_scoring={"high": 1.0},
            client_types=["all"],
            detection_mode="both",
        )
        claim = make_claim(metadata={"is_duplicate": False})
        evaluator = RuleEvaluator()
        result = evaluator.evaluate(rule, claim)
        assert result.flagged is False


class TestRuleEvaluatorStatistical:
    """Test statistical/comparison rules."""

    def test_volume_spike_flagged_above_threshold(self) -> None:
        rule = RuleDefinition(
            rule_code="MFR-004",
            name="Volume Spike",
            rule_type="statistical",
            rule_logic={"field": "volume_vs_avg_ratio", "operator": "gt", "threshold": 2.0},
            default_parameters={"threshold": 2.0},
            default_action="alert",
            confidence_scoring={"medium": 2.0},
            client_types=["manufacturer"],
            detection_mode="post_adjudication",
        )
        claim = make_claim(metadata={"volume_vs_avg_ratio": Decimal("2.5")})
        evaluator = RuleEvaluator()
        result = evaluator.evaluate(rule, claim)
        assert result.flagged is True

    def test_risk_score_in_range(self) -> None:
        rule = RuleDefinition(
            rule_code="MFR-001",
            name="NQ Inflation",
            rule_type="threshold",
            rule_logic={"field": "nq_to_wac_ratio", "operator": "gt", "threshold": 1.10},
            default_parameters={"threshold": 1.10},
            default_action="flag",
            confidence_scoring={"high": 1.50, "medium": 1.20, "low": 1.10},
            client_types=["manufacturer"],
            detection_mode="both",
        )
        claim = make_claim(nq=Decimal("110.00"), wac_per_unit=Decimal("3.00"), quantity=Decimal("30.000"))
        evaluator = RuleEvaluator()
        result = evaluator.evaluate(rule, claim)
        assert 0 <= result.risk_score <= 100

    def test_evidence_contains_relevant_fields(self) -> None:
        rule = RuleDefinition(
            rule_code="MFR-001",
            name="NQ Inflation",
            rule_type="threshold",
            rule_logic={"field": "nq_to_wac_ratio", "operator": "gt", "threshold": 1.10},
            default_parameters={"threshold": 1.10},
            default_action="flag",
            confidence_scoring={"high": 1.50, "medium": 1.20, "low": 1.10},
            client_types=["manufacturer"],
            detection_mode="both",
        )
        claim = make_claim(nq=Decimal("135.00"), wac_per_unit=Decimal("3.00"), quantity=Decimal("30.000"))
        evaluator = RuleEvaluator()
        result = evaluator.evaluate(rule, claim)
        assert "rule_code" in result.evidence
        assert "computed_value" in result.evidence
        assert "threshold" in result.evidence


class TestRuleEvaluatorStatisticalNotFlagged:
    def test_statistical_not_flagged_below_threshold(self) -> None:
        rule = RuleDefinition(
            rule_code="MFR-004",
            name="Volume Spike",
            rule_type="statistical",
            rule_logic={"field": "volume_vs_avg_ratio", "operator": "gt", "threshold": 2.0},
            default_parameters={"threshold": 2.0},
            default_action="alert",
            confidence_scoring={"medium": 2.0},
            client_types=["manufacturer"],
            detection_mode="post_adjudication",
        )
        claim = make_claim(metadata={"volume_vs_avg_ratio": Decimal("1.5")})
        evaluator = RuleEvaluator()
        result = evaluator.evaluate(rule, claim)
        assert result.flagged is False

    def test_statistical_field_not_available(self) -> None:
        rule = RuleDefinition(
            rule_code="MFR-004",
            name="Volume Spike",
            rule_type="statistical",
            rule_logic={"field": "volume_vs_avg_ratio", "operator": "gt", "threshold": 2.0},
            default_parameters={"threshold": 2.0},
            default_action="alert",
            confidence_scoring={"medium": 2.0},
            client_types=["manufacturer"],
            detection_mode="post_adjudication",
        )
        claim = make_claim()  # no volume_vs_avg_ratio in metadata
        evaluator = RuleEvaluator()
        result = evaluator.evaluate(rule, claim)
        assert result.flagged is False
        assert result.skip_reason == "field_not_available"


class TestRuleEvaluatorComposite:
    def _make_sub_rule_logic(self) -> dict:
        return {
            "sub_rules": [
                {
                    "field": "nq_to_wac_ratio",
                    "operator": "gt",
                    "threshold": 1.10,
                    "rule_type": "threshold",
                },
            ]
        }

    def test_composite_flagged_when_sub_rule_flags(self) -> None:
        rule = RuleDefinition(
            rule_code="ALL-COMP",
            name="Composite Rule",
            rule_type="composite",
            rule_logic=self._make_sub_rule_logic(),
            default_parameters={},
            default_action="flag",
            confidence_scoring={"high": 1.50},
            client_types=["all"],
            detection_mode="both",
        )
        claim = make_claim(nq=Decimal("200.00"), wac_per_unit=Decimal("3.00"), quantity=Decimal("30.000"))
        evaluator = RuleEvaluator()
        result = evaluator.evaluate(rule, claim)
        assert result.flagged is True
        assert result.rule_code == "ALL-COMP"

    def test_composite_not_flagged_when_no_sub_rules_flag(self) -> None:
        rule = RuleDefinition(
            rule_code="ALL-COMP",
            name="Composite Rule",
            rule_type="composite",
            rule_logic={"sub_rules": []},
            default_parameters={},
            default_action="flag",
            confidence_scoring={},
            client_types=["all"],
            detection_mode="both",
        )
        claim = make_claim()
        evaluator = RuleEvaluator()
        result = evaluator.evaluate(rule, claim)
        assert result.flagged is False


class TestRuleEvaluatorUnknownType:
    def test_unknown_rule_type_returns_unflagged(self) -> None:
        rule = RuleDefinition(
            rule_code="TST-999",
            name="Unknown Type",
            rule_type="magic",
            rule_logic={},
            default_parameters={},
            default_action="flag",
            confidence_scoring={},
            client_types=["all"],
            detection_mode="both",
        )
        claim = make_claim()
        evaluator = RuleEvaluator()
        result = evaluator.evaluate(rule, claim)
        assert result.flagged is False
        assert result.skip_reason == "unknown_rule_type"


class TestRuleEvaluatorFieldValues:
    def test_nq_to_wac_ratio_zero_wac_returns_none(self) -> None:
        rule = RuleDefinition(
            rule_code="MFR-001",
            name="NQ Inflation",
            rule_type="threshold",
            rule_logic={"field": "nq_to_wac_ratio", "operator": "gt", "threshold": 1.10},
            default_parameters={},
            default_action="flag",
            confidence_scoring={"high": 1.50},
            client_types=["manufacturer"],
            detection_mode="both",
        )
        claim = make_claim(wac_per_unit=Decimal("0.00"), nq=Decimal("100.00"))
        evaluator = RuleEvaluator()
        result = evaluator.evaluate(rule, claim)
        assert result.flagged is False
        assert result.skip_reason == "field_not_available"

    def test_dv_to_awp_ratio_zero_awp_returns_none(self) -> None:
        rule = RuleDefinition(
            rule_code="HP-001",
            name="DV Ratio",
            rule_type="threshold",
            rule_logic={"field": "dv_to_awp_ratio", "operator": "gt", "threshold": 0.10},
            default_parameters={},
            default_action="flag",
            confidence_scoring={},
            client_types=["all"],
            detection_mode="both",
        )
        claim = make_claim(awp_per_unit=Decimal("0.00"), dv=Decimal("5.00"))
        evaluator = RuleEvaluator()
        result = evaluator.evaluate(rule, claim)
        assert result.flagged is False
        assert result.skip_reason == "field_not_available"

    def test_dv_to_awp_ratio_flagged(self) -> None:
        rule = RuleDefinition(
            rule_code="HP-001",
            name="DV Ratio",
            rule_type="threshold",
            rule_logic={"field": "dv_to_awp_ratio", "operator": "gt", "threshold": 0.10},
            default_parameters={},
            default_action="flag",
            confidence_scoring={"high": 0.30},
            client_types=["all"],
            detection_mode="both",
        )
        claim = make_claim(awp_per_unit=Decimal("3.50"), quantity=Decimal("30.000"), dv=Decimal("50.00"))
        evaluator = RuleEvaluator()
        result = evaluator.evaluate(rule, claim)
        assert result.flagged is True

    def test_metadata_field_fallback_claim_attribute(self) -> None:
        rule = RuleDefinition(
            rule_code="TST-001",
            name="Billed Amount Check",
            rule_type="threshold",
            rule_logic={"field": "billed_amount", "operator": "gt", "threshold": 50.0},
            default_parameters={},
            default_action="flag",
            confidence_scoring={},
            client_types=["all"],
            detection_mode="both",
        )
        claim = make_claim(billed_amount=Decimal("100.00"))
        evaluator = RuleEvaluator()
        result = evaluator.evaluate(rule, claim)
        assert result.flagged is True

    def test_comparison_rule_delegates_to_threshold(self) -> None:
        rule = RuleDefinition(
            rule_code="ALL-CMP",
            name="Comparison Rule",
            rule_type="comparison",
            rule_logic={"field": "nq_to_wac_ratio", "operator": "gt", "threshold": 1.10},
            default_parameters={},
            default_action="flag",
            confidence_scoring={"high": 1.50},
            client_types=["all"],
            detection_mode="both",
        )
        claim = make_claim(nq=Decimal("200.00"), wac_per_unit=Decimal("3.00"), quantity=Decimal("30.000"))
        evaluator = RuleEvaluator()
        result = evaluator.evaluate(rule, claim)
        assert result.flagged is True


class TestRuleEngineAdditionalCoverage:
    def test_metadata_generic_field_returned_as_decimal(self) -> None:
        rule = RuleDefinition(
            rule_code="TST-META",
            name="Metadata Field Test",
            rule_type="threshold",
            rule_logic={"field": "custom_score", "operator": "gt", "threshold": 0.5},
            default_parameters={},
            default_action="flag",
            confidence_scoring={},
            client_types=["all"],
            detection_mode="both",
        )
        claim = make_claim(metadata={"custom_score": 0.75})
        evaluator = RuleEvaluator()
        result = evaluator.evaluate(rule, claim)
        assert result.flagged is True

    def test_risk_score_to_severity_low(self) -> None:
        assert RuleEvaluator._risk_score_to_severity(10) == "low"
        assert RuleEvaluator._risk_score_to_severity(25) == "low"
        assert RuleEvaluator._risk_score_to_severity(26) == "medium"

    def test_composite_multiple_sub_rules_second_flags(self) -> None:
        rule = RuleDefinition(
            rule_code="ALL-COMP2",
            name="Composite Multi Rule",
            rule_type="composite",
            rule_logic={
                "sub_rules": [
                    # First sub-rule: will NOT flag (nq_to_wac < threshold)
                    {"field": "nq_to_wac_ratio", "operator": "gt", "threshold": 5.0, "rule_type": "threshold"},
                    # Second sub-rule: WILL flag (nq_to_wac > 1.1)
                    {"field": "nq_to_wac_ratio", "operator": "gt", "threshold": 1.10, "rule_type": "threshold"},
                ],
            },
            default_parameters={},
            default_action="flag",
            confidence_scoring={"high": 1.50},
            client_types=["all"],
            detection_mode="both",
        )
        claim = make_claim(nq=Decimal("200.00"), wac_per_unit=Decimal("3.00"), quantity=Decimal("30.000"))
        evaluator = RuleEvaluator()
        result = evaluator.evaluate(rule, claim)
        assert result.flagged is True


class TestConstantsAndSeverity:
    def test_risk_score_to_severity_all_tiers(self) -> None:
        from src.utils.constants import risk_score_to_severity
        assert risk_score_to_severity(90) == "critical"
        assert risk_score_to_severity(60) == "high"
        assert risk_score_to_severity(30) == "medium"
        assert risk_score_to_severity(10) == "low"

    def test_known_accumulator_bins_not_empty(self) -> None:
        from src.utils.constants import KNOWN_ACCUMULATOR_BINS
        assert len(KNOWN_ACCUMULATOR_BINS) > 0


class TestRuleResult:
    def test_no_flag_has_zero_risk_score(self) -> None:
        result = RuleResult(
            flagged=False,
            rule_code="MFR-001",
            action=None,
            confidence_tier=None,
            risk_score=0,
            evidence={},
            severity=None,
        )
        assert result.risk_score == 0
        assert not result.flagged
