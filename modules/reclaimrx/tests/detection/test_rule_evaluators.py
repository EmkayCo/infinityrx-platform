"""TDD tests for Task 3.2: World-B rule evaluators ported to the batch engine.

Pure-function evaluators operating on pre-derived fields dicts (output of
derive_fields()) + rule_params dicts.  No I/O, no DB, no side effects.

Financial precision: Decimal only, never float.

World-B mirror:
- _compare: gt/gte/lt/lte/eq/ne operators on Decimal values.
- _compute_confidence: high/medium/low tiers from confidence_scoring thresholds.
- _confidence_to_risk_score: high=85, medium=60, low=40 base; min(100, base).
- _risk_score_to_severity: >75 critical, >50 high, >25 medium, else low.
- evaluate_threshold: reads rule_params["field"]/["operator"]/["threshold"];
  resolves field from combined fields dict (derive_fields output + raw row);
  Decimal compares; None field -> not fired.
- evaluate_statistical: same logic as threshold (mirrors World-B exactly).
- evaluate_comparison: delegates to evaluate_threshold (mirrors World-B).
- evaluate_composite: OR-fires across sub_rules; fixed risk_score=60,
  confidence="medium", severity="high" on fire.
- evaluate_pattern: only "duplicate_claim" has inline logic in World-B
  (checks metadata/fields["is_duplicate"]).  Grouping-based patterns
  (duplicate, BRR) are handled in Task 3.5, not here.

RuleResult dataclass fields: fired, risk_score, severity, confidence, evidence.
NOTE: "confidence" in RuleResult corresponds to "confidence_tier" in World-B.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from src.detection.rule_evaluators import (
    RuleResult,
    _compare,
    _compute_confidence,
    _confidence_to_risk_score,
    _risk_score_to_severity,
    evaluate_comparison,
    evaluate_composite,
    evaluate_pattern,
    evaluate_statistical,
    evaluate_threshold,
)


# ---------------------------------------------------------------------------
# _compare operator tests
# ---------------------------------------------------------------------------

class TestCompare:
    def test_gt_true(self):
        assert _compare(Decimal("1.2"), "gt", Decimal("1.1")) is True

    def test_gt_false_equal(self):
        assert _compare(Decimal("1.1"), "gt", Decimal("1.1")) is False

    def test_gt_false_less(self):
        assert _compare(Decimal("1.0"), "gt", Decimal("1.1")) is False

    def test_gte_true_equal(self):
        assert _compare(Decimal("1.1"), "gte", Decimal("1.1")) is True

    def test_gte_true_greater(self):
        assert _compare(Decimal("1.2"), "gte", Decimal("1.1")) is True

    def test_gte_false(self):
        assert _compare(Decimal("1.09"), "gte", Decimal("1.1")) is False

    def test_lt_true(self):
        assert _compare(Decimal("1.0"), "lt", Decimal("1.1")) is True

    def test_lt_false_equal(self):
        assert _compare(Decimal("1.1"), "lt", Decimal("1.1")) is False

    def test_lte_true_equal(self):
        assert _compare(Decimal("1.1"), "lte", Decimal("1.1")) is True

    def test_lte_true_less(self):
        assert _compare(Decimal("1.0"), "lte", Decimal("1.1")) is True

    def test_lte_false(self):
        assert _compare(Decimal("1.2"), "lte", Decimal("1.1")) is False

    def test_eq_true(self):
        assert _compare(Decimal("1.10"), "eq", Decimal("1.10")) is True

    def test_eq_false(self):
        assert _compare(Decimal("1.11"), "eq", Decimal("1.10")) is False

    def test_ne_true(self):
        assert _compare(Decimal("1.11"), "ne", Decimal("1.10")) is True

    def test_ne_false(self):
        assert _compare(Decimal("1.10"), "ne", Decimal("1.10")) is False

    def test_unknown_operator_returns_false(self):
        assert _compare(Decimal("99"), "xor", Decimal("1")) is False


# ---------------------------------------------------------------------------
# _compute_confidence tests
# ---------------------------------------------------------------------------

class TestComputeConfidence:
    """Mirrors World-B _compute_confidence: high threshold >= high, medium >= medium, else low."""

    _SCORING = {"high": 1.50, "medium": 1.20, "low": 1.10}

    def test_high_at_exact_boundary(self):
        assert _compute_confidence(Decimal("1.50"), self._SCORING) == "high"

    def test_high_above_boundary(self):
        assert _compute_confidence(Decimal("2.00"), self._SCORING) == "high"

    def test_medium_at_exact_boundary(self):
        assert _compute_confidence(Decimal("1.20"), self._SCORING) == "medium"

    def test_medium_below_high(self):
        assert _compute_confidence(Decimal("1.49"), self._SCORING) == "medium"

    def test_low_below_medium(self):
        assert _compute_confidence(Decimal("1.10"), self._SCORING) == "low"

    def test_low_just_below_medium_threshold(self):
        assert _compute_confidence(Decimal("1.19"), self._SCORING) == "low"

    def test_empty_scoring_returns_medium(self):
        assert _compute_confidence(Decimal("999"), {}) == "medium"

    def test_no_high_key_only_medium(self):
        scoring = {"medium": 1.20}
        # Above medium but no high key => medium
        assert _compute_confidence(Decimal("1.50"), scoring) == "medium"

    def test_no_medium_key_only_high(self):
        scoring = {"high": 1.50}
        # Below high => low (no medium key)
        assert _compute_confidence(Decimal("1.20"), scoring) == "low"
        assert _compute_confidence(Decimal("1.50"), scoring) == "high"


# ---------------------------------------------------------------------------
# _confidence_to_risk_score tests
# ---------------------------------------------------------------------------

class TestConfidenceToRiskScore:
    """high=85, medium=60, low=40 base; min(100, base) — mirrors World-B."""

    def test_high_returns_85(self):
        assert _confidence_to_risk_score("high") == 85

    def test_medium_returns_60(self):
        assert _confidence_to_risk_score("medium") == 60

    def test_low_returns_40(self):
        assert _confidence_to_risk_score("low") == 40

    def test_unknown_tier_returns_40(self):
        assert _confidence_to_risk_score("unknown_tier") == 40


# ---------------------------------------------------------------------------
# _risk_score_to_severity tests (boundary values)
# ---------------------------------------------------------------------------

class TestRiskScoreToSeverity:
    """>75 critical, >50 high, >25 medium, else low — mirrors World-B."""

    def test_76_is_critical(self):
        assert _risk_score_to_severity(76) == "critical"

    def test_85_is_critical(self):
        assert _risk_score_to_severity(85) == "critical"

    def test_100_is_critical(self):
        assert _risk_score_to_severity(100) == "critical"

    def test_75_is_high(self):
        # 75 is NOT > 75, so it falls to "high" (>50)
        assert _risk_score_to_severity(75) == "high"

    def test_51_is_high(self):
        assert _risk_score_to_severity(51) == "high"

    def test_60_is_high(self):
        assert _risk_score_to_severity(60) == "high"

    def test_50_is_medium(self):
        # 50 is NOT > 50, so falls to "medium" (>25)
        assert _risk_score_to_severity(50) == "medium"

    def test_26_is_medium(self):
        assert _risk_score_to_severity(26) == "medium"

    def test_25_is_low(self):
        # 25 is NOT > 25
        assert _risk_score_to_severity(25) == "low"

    def test_0_is_low(self):
        assert _risk_score_to_severity(0) == "low"


# ---------------------------------------------------------------------------
# evaluate_threshold — MFR-001 NQ inflation rule
# ---------------------------------------------------------------------------

class TestEvaluateThreshold:
    """
    MFR-001 rule_params:
      field: nq_to_wac_ratio
      operator: gt
      threshold: 1.10
      confidence_scoring: {high: 1.50, medium: 1.20, low: 1.10}

    Golden row 1: ratio = 1.1637 (215.17 + 1.5) / 186.19 → fires, confidence=medium
    Golden row 2: ratio = 1.0875 (186.5 + 0.0) / 171.50 → not fires
    """

    _MFR001_PARAMS = {
        "field": "nq_to_wac_ratio",
        "operator": "gt",
        "threshold": 1.10,
        "confidence_scoring": {"high": 1.50, "medium": 1.20, "low": 1.10},
    }

    def test_mfr001_fires_at_1_1637(self):
        """ratio 1.1637 > 1.10 -> fired=True."""
        fields = {"nq_to_wac_ratio": Decimal("1.1637")}
        result = evaluate_threshold(fields, self._MFR001_PARAMS)
        assert isinstance(result, RuleResult)
        assert result.fired is True

    def test_mfr001_risk_score_low_confidence_band(self):
        """1.1637 < 1.20 (medium threshold) -> low confidence -> risk 40.
        World-B: _compute_confidence checks >= high then >= medium then low.
        1.1637 is below medium(1.20) so returns low."""
        fields = {"nq_to_wac_ratio": Decimal("1.1637")}
        result = evaluate_threshold(fields, self._MFR001_PARAMS)
        assert result.confidence == "low"
        assert result.risk_score == 40

    def test_mfr001_severity_medium_for_risk_40(self):
        """risk_score=40 (low confidence) -> >25 but not >50 -> severity=medium."""
        fields = {"nq_to_wac_ratio": Decimal("1.1637")}
        result = evaluate_threshold(fields, self._MFR001_PARAMS)
        assert result.severity == "medium"

    def test_mfr001_not_fired_at_1_0875(self):
        """ratio 1.0875 <= 1.10 (operator gt) -> not fired."""
        fields = {"nq_to_wac_ratio": Decimal("1.0875")}
        result = evaluate_threshold(fields, self._MFR001_PARAMS)
        assert result.fired is False
        assert result.risk_score == 0
        assert result.severity is None

    def test_mfr001_not_fired_exact_threshold(self):
        """ratio == 1.10, operator gt -> not fired (strict greater-than)."""
        fields = {"nq_to_wac_ratio": Decimal("1.10")}
        result = evaluate_threshold(fields, self._MFR001_PARAMS)
        assert result.fired is False

    def test_mfr001_fires_at_high_confidence_band(self):
        """ratio >= 1.50 -> high confidence -> risk_score=85 -> severity=critical."""
        fields = {"nq_to_wac_ratio": Decimal("1.50")}
        result = evaluate_threshold(fields, self._MFR001_PARAMS)
        assert result.fired is True
        assert result.confidence == "high"
        assert result.risk_score == 85
        assert result.severity == "critical"

    def test_mfr001_fires_at_low_confidence_band(self):
        """ratio 1.11 is > 1.10 threshold (fires) but < 1.20 medium -> low confidence -> risk 40."""
        fields = {"nq_to_wac_ratio": Decimal("1.11")}
        result = evaluate_threshold(fields, self._MFR001_PARAMS)
        assert result.fired is True
        assert result.confidence == "low"
        assert result.risk_score == 40
        assert result.severity == "medium"  # 40 > 25 -> medium

    def test_none_field_not_fired(self):
        """When field value is None, returns not-fired with no exception."""
        fields = {"nq_to_wac_ratio": None}
        result = evaluate_threshold(fields, self._MFR001_PARAMS)
        assert result.fired is False

    def test_missing_field_not_fired(self):
        """When field is absent from fields dict, returns not-fired."""
        result = evaluate_threshold({}, self._MFR001_PARAMS)
        assert result.fired is False

    def test_evidence_contains_field_and_value(self):
        """Fired result evidence contains field name and computed_value."""
        fields = {"nq_to_wac_ratio": Decimal("1.1637")}
        result = evaluate_threshold(fields, self._MFR001_PARAMS)
        assert result.evidence["field"] == "nq_to_wac_ratio"
        assert "computed_value" in result.evidence

    def test_threshold_read_from_rule_params(self):
        """Different threshold in rule_params is respected."""
        params = {
            "field": "nq_to_wac_ratio",
            "operator": "gt",
            "threshold": 1.20,  # higher threshold
            "confidence_scoring": {"high": 1.50, "medium": 1.30, "low": 1.20},
        }
        # ratio 1.1637 is below the new threshold (1.20) -> not fired
        fields = {"nq_to_wac_ratio": Decimal("1.1637")}
        result = evaluate_threshold(fields, params)
        assert result.fired is False

    def test_decimal_field_from_raw_row_values(self):
        """evaluate_threshold resolves fields from combined dict including raw row values."""
        # Simulate a raw row field (not a derived field)
        params = {
            "field": "total_paid_amt",
            "operator": "gt",
            "threshold": 1000.00,
            "confidence_scoring": {"high": 5000.0, "medium": 2000.0},
        }
        fields = {"total_paid_amt": Decimal("1500.00")}
        result = evaluate_threshold(fields, params)
        assert result.fired is True

    def test_return_type_is_rule_result(self):
        fields = {"nq_to_wac_ratio": Decimal("1.2")}
        result = evaluate_threshold(fields, self._MFR001_PARAMS)
        assert isinstance(result, RuleResult)


# ---------------------------------------------------------------------------
# evaluate_statistical — volume vs average style
# ---------------------------------------------------------------------------

class TestEvaluateStatistical:
    """Statistical rule mirrors evaluate_threshold in World-B (same logic)."""

    _PARAMS = {
        "field": "volume_vs_avg_ratio",
        "operator": "gt",
        "threshold": 2.0,
        "confidence_scoring": {"high": 5.0, "medium": 3.0},
    }

    def test_fires_above_threshold(self):
        fields = {"volume_vs_avg_ratio": Decimal("3.5")}
        result = evaluate_statistical(fields, self._PARAMS)
        assert result.fired is True
        assert result.confidence == "medium"
        assert result.risk_score == 60

    def test_not_fired_below_threshold(self):
        fields = {"volume_vs_avg_ratio": Decimal("1.5")}
        result = evaluate_statistical(fields, self._PARAMS)
        assert result.fired is False

    def test_fires_high_confidence(self):
        fields = {"volume_vs_avg_ratio": Decimal("5.5")}
        result = evaluate_statistical(fields, self._PARAMS)
        assert result.fired is True
        assert result.confidence == "high"
        assert result.risk_score == 85
        assert result.severity == "critical"

    def test_none_field_not_fired(self):
        fields = {"volume_vs_avg_ratio": None}
        result = evaluate_statistical(fields, self._PARAMS)
        assert result.fired is False

    def test_evidence_has_threshold(self):
        fields = {"volume_vs_avg_ratio": Decimal("3.5")}
        result = evaluate_statistical(fields, self._PARAMS)
        assert "threshold" in result.evidence

    def test_with_baseline_kwarg_accepted(self):
        """evaluate_statistical accepts optional baseline kwarg without raising."""
        fields = {"volume_vs_avg_ratio": Decimal("3.5")}
        result = evaluate_statistical(fields, self._PARAMS, baseline=Decimal("1.0"))
        assert result.fired is True

    def test_return_type_is_rule_result(self):
        fields = {"volume_vs_avg_ratio": Decimal("3.5")}
        assert isinstance(evaluate_statistical(fields, self._PARAMS), RuleResult)


# ---------------------------------------------------------------------------
# evaluate_comparison — delegates to threshold
# ---------------------------------------------------------------------------

class TestEvaluateComparison:
    """evaluate_comparison delegates to evaluate_threshold per World-B."""

    _PARAMS = {
        "field": "dv_to_awp_ratio",
        "operator": "gt",
        "threshold": 0.10,
        "confidence_scoring": {"high": 0.50, "medium": 0.20},
    }

    def test_delegates_fires(self):
        fields = {"dv_to_awp_ratio": Decimal("0.25")}
        result = evaluate_comparison(fields, self._PARAMS)
        assert result.fired is True

    def test_delegates_not_fired(self):
        fields = {"dv_to_awp_ratio": Decimal("0.05")}
        result = evaluate_comparison(fields, self._PARAMS)
        assert result.fired is False

    def test_same_result_as_threshold(self):
        """evaluate_comparison must produce identical result to evaluate_threshold."""
        fields = {"dv_to_awp_ratio": Decimal("0.25")}
        r_comp = evaluate_comparison(fields, self._PARAMS)
        r_thresh = evaluate_threshold(fields, self._PARAMS)
        assert r_comp.fired == r_thresh.fired
        assert r_comp.risk_score == r_thresh.risk_score
        assert r_comp.severity == r_thresh.severity
        assert r_comp.confidence == r_thresh.confidence

    def test_return_type_is_rule_result(self):
        fields = {"dv_to_awp_ratio": Decimal("0.25")}
        assert isinstance(evaluate_comparison(fields, self._PARAMS), RuleResult)


# ---------------------------------------------------------------------------
# evaluate_composite — ALL-008-style OR-fire across sub_rules
# ---------------------------------------------------------------------------

class TestEvaluateComposite:
    """
    Composite fires if ANY sub-rule fires (OR logic per World-B).
    When fired: risk_score=60, confidence="medium", severity="high".
    """

    def _params_or_two_thresholds(self, field1_val, field2_val) -> dict:
        """Helper: two threshold sub_rules on different fields."""
        return {
            "sub_rules": [
                {
                    "rule_type": "threshold",
                    "field": "nq_to_wac_ratio",
                    "operator": "gt",
                    "threshold": 1.10,
                    "confidence_scoring": {"high": 1.50, "medium": 1.20},
                },
                {
                    "rule_type": "threshold",
                    "field": "dv_to_awp_ratio",
                    "operator": "gt",
                    "threshold": 0.10,
                    "confidence_scoring": {"high": 0.50, "medium": 0.20},
                },
            ]
        }

    def test_fires_when_first_sub_rule_fires(self):
        """First sub-rule fires (nq_to_wac_ratio > 1.10), second doesn't."""
        fields = {
            "nq_to_wac_ratio": Decimal("1.20"),
            "dv_to_awp_ratio": Decimal("0.05"),  # below threshold
        }
        result = evaluate_composite(fields, self._params_or_two_thresholds(None, None))
        assert result.fired is True

    def test_fires_when_second_sub_rule_fires(self):
        """Second sub-rule fires (dv_to_awp_ratio > 0.10), first doesn't."""
        fields = {
            "nq_to_wac_ratio": Decimal("1.05"),  # below threshold
            "dv_to_awp_ratio": Decimal("0.25"),
        }
        result = evaluate_composite(fields, self._params_or_two_thresholds(None, None))
        assert result.fired is True

    def test_fires_when_both_sub_rules_fire(self):
        """Both sub-rules fire -> composite still fires."""
        fields = {
            "nq_to_wac_ratio": Decimal("1.50"),
            "dv_to_awp_ratio": Decimal("0.30"),
        }
        result = evaluate_composite(fields, self._params_or_two_thresholds(None, None))
        assert result.fired is True

    def test_not_fired_when_no_sub_rule_fires(self):
        """No sub-rule fires -> composite not fired."""
        fields = {
            "nq_to_wac_ratio": Decimal("1.05"),
            "dv_to_awp_ratio": Decimal("0.05"),
        }
        result = evaluate_composite(fields, self._params_or_two_thresholds(None, None))
        assert result.fired is False
        assert result.risk_score == 0

    def test_fired_risk_score_is_60(self):
        """World-B hardcodes risk_score=60 on composite fire."""
        fields = {"nq_to_wac_ratio": Decimal("1.50"), "dv_to_awp_ratio": Decimal("0.05")}
        result = evaluate_composite(fields, self._params_or_two_thresholds(None, None))
        assert result.risk_score == 60

    def test_fired_confidence_is_medium(self):
        """World-B hardcodes confidence='medium' on composite fire."""
        fields = {"nq_to_wac_ratio": Decimal("1.50"), "dv_to_awp_ratio": Decimal("0.05")}
        result = evaluate_composite(fields, self._params_or_two_thresholds(None, None))
        assert result.confidence == "medium"

    def test_fired_severity_is_high(self):
        """World-B hardcodes severity='high' on composite fire."""
        fields = {"nq_to_wac_ratio": Decimal("1.50"), "dv_to_awp_ratio": Decimal("0.05")}
        result = evaluate_composite(fields, self._params_or_two_thresholds(None, None))
        assert result.severity == "high"

    def test_empty_sub_rules_not_fired(self):
        """No sub_rules at all -> not fired."""
        result = evaluate_composite({}, {"sub_rules": []})
        assert result.fired is False

    def test_evidence_contains_sub_results(self):
        """Evidence must include sub_results list."""
        fields = {"nq_to_wac_ratio": Decimal("1.50"), "dv_to_awp_ratio": Decimal("0.05")}
        result = evaluate_composite(fields, self._params_or_two_thresholds(None, None))
        assert "sub_results" in result.evidence

    def test_return_type_is_rule_result(self):
        fields = {"nq_to_wac_ratio": Decimal("1.50"), "dv_to_awp_ratio": Decimal("0.05")}
        assert isinstance(
            evaluate_composite(fields, self._params_or_two_thresholds(None, None)),
            RuleResult,
        )


# ---------------------------------------------------------------------------
# evaluate_pattern — mirrors World-B exactly
# ---------------------------------------------------------------------------

class TestEvaluatePattern:
    """
    Only "duplicate_claim" has inline logic in World-B.
    Other grouping-based patterns (BRR, etc.) are handled in Task 3.5.
    """

    def test_duplicate_claim_fires_when_is_duplicate_true(self):
        """is_duplicate=True in fields -> pattern fires."""
        fields = {"is_duplicate": True, "original_auth": "AUTH-123"}
        result = evaluate_pattern(fields, {"pattern": "duplicate_claim"})
        assert result.fired is True

    def test_duplicate_claim_fires_risk_85_critical(self):
        """World-B sets risk_score=85, severity='critical' on duplicate_claim fire."""
        fields = {"is_duplicate": True}
        result = evaluate_pattern(fields, {"pattern": "duplicate_claim"})
        assert result.risk_score == 85
        assert result.severity == "critical"
        assert result.confidence == "high"

    def test_duplicate_claim_not_fired_when_false(self):
        """is_duplicate=False -> not fired."""
        fields = {"is_duplicate": False}
        result = evaluate_pattern(fields, {"pattern": "duplicate_claim"})
        assert result.fired is False

    def test_duplicate_claim_not_fired_when_missing(self):
        """is_duplicate absent -> not fired."""
        result = evaluate_pattern({}, {"pattern": "duplicate_claim"})
        assert result.fired is False

    def test_unknown_pattern_not_fired(self):
        """Unknown patterns (grouping-based, Task 3.5 territory) return not-fired."""
        result = evaluate_pattern({}, {"pattern": "brr_excess_reversal"})
        assert result.fired is False

    def test_return_type_is_rule_result(self):
        assert isinstance(evaluate_pattern({}, {"pattern": "duplicate_claim"}), RuleResult)


# ---------------------------------------------------------------------------
# RuleResult dataclass structure
# ---------------------------------------------------------------------------

class TestRuleResultDataclass:
    def test_has_fired_field(self):
        r = RuleResult(
            fired=True,
            risk_score=85,
            severity="critical",
            confidence="high",
            evidence={"test": "value"},
        )
        assert r.fired is True
        assert r.risk_score == 85
        assert r.severity == "critical"
        assert r.confidence == "high"
        assert r.evidence == {"test": "value"}

    def test_not_fired_zero_risk(self):
        r = RuleResult(fired=False, risk_score=0, severity=None, confidence=None, evidence={})
        assert not r.fired
        assert r.risk_score == 0
        assert r.severity is None
