"""Detection rule engine — generic evaluator taking rule definition + claim → flag/no-flag.

Design: stateless evaluator; all state is in the rule definition + claim context.
Supports threshold, pattern, statistical, comparison, and composite rule types.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass
class ClaimContext:
    """Snapshot of a claim's relevant data for rule evaluation."""

    claim_id: str
    tenant_id: str
    auth_number: str
    date_of_service: date
    pharmacy_npi: str
    pharmacy_name: str
    prescriber_npi: str | None
    member_id: str | None
    ndc: str | None
    drug_name: str | None
    quantity: Decimal
    days_supply: int
    billed_amount: Decimal
    paid_amount: Decimal
    wac_per_unit: Decimal
    awp_per_unit: Decimal
    nq: Decimal  # net quantity cost
    dv: Decimal  # dispensing value
    program_type: str
    client_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleDefinition:
    """Definition of a detection rule."""

    rule_code: str
    name: str
    rule_type: str  # threshold, pattern, statistical, comparison, composite
    rule_logic: dict[str, Any]
    default_parameters: dict[str, Any]
    default_action: str
    confidence_scoring: dict[str, Any]
    client_types: list[str]
    detection_mode: str  # real_time, post_adjudication, both


@dataclass
class RuleResult:
    """Result of evaluating a rule against a claim."""

    flagged: bool
    rule_code: str
    action: str | None
    confidence_tier: str | None
    risk_score: int
    evidence: dict[str, Any]
    severity: str | None
    skip_reason: str | None = None


class RuleEvaluator:
    """Stateless rule evaluator. Takes a rule definition and claim, returns flag/no-flag."""

    def evaluate(self, rule: RuleDefinition, claim: ClaimContext) -> RuleResult:
        if not self._is_applicable(rule, claim):
            return RuleResult(
                flagged=False,
                rule_code=rule.rule_code,
                action=None,
                confidence_tier=None,
                risk_score=0,
                evidence={},
                severity=None,
                skip_reason="client_type_mismatch",
            )

        handler = {
            "threshold": self._evaluate_threshold,
            "pattern": self._evaluate_pattern,
            "statistical": self._evaluate_statistical,
            "comparison": self._evaluate_comparison,
            "composite": self._evaluate_composite,
        }.get(rule.rule_type)

        if handler is None:
            return RuleResult(
                flagged=False,
                rule_code=rule.rule_code,
                action=None,
                confidence_tier=None,
                risk_score=0,
                evidence={"error": f"Unknown rule_type: {rule.rule_type}"},
                severity=None,
                skip_reason="unknown_rule_type",
            )

        return handler(rule, claim)

    def _is_applicable(self, rule: RuleDefinition, claim: ClaimContext) -> bool:
        if "all" in rule.client_types:
            return True
        return claim.client_type in rule.client_types

    def _evaluate_threshold(self, rule: RuleDefinition, claim: ClaimContext) -> RuleResult:
        logic = rule.rule_logic
        field_name = logic["field"]
        operator = logic["operator"]
        threshold = Decimal(str(logic["threshold"]))

        computed = self._get_field_value(field_name, claim)
        if computed is None:
            return RuleResult(
                flagged=False,
                rule_code=rule.rule_code,
                action=None,
                confidence_tier=None,
                risk_score=0,
                evidence={"field": field_name, "value": None},
                severity=None,
                skip_reason="field_not_available",
            )

        computed_decimal = Decimal(str(computed))
        flagged = self._compare(computed_decimal, operator, threshold)

        if not flagged:
            return RuleResult(
                flagged=False,
                rule_code=rule.rule_code,
                action=None,
                confidence_tier=None,
                risk_score=0,
                evidence={
                    "rule_code": rule.rule_code,
                    "field": field_name,
                    "computed_value": str(computed_decimal),
                    "threshold": str(threshold),
                    "operator": operator,
                },
                severity=None,
            )

        confidence_tier = self._compute_confidence(computed_decimal, rule.confidence_scoring)
        risk_score = self._confidence_to_risk_score(confidence_tier, computed_decimal, threshold)
        severity = self._risk_score_to_severity(risk_score)

        return RuleResult(
            flagged=True,
            rule_code=rule.rule_code,
            action=rule.default_action,
            confidence_tier=confidence_tier,
            risk_score=risk_score,
            evidence={
                "rule_code": rule.rule_code,
                "field": field_name,
                "computed_value": str(computed_decimal),
                "threshold": str(threshold),
                "operator": operator,
            },
            severity=severity,
        )

    def _evaluate_pattern(self, rule: RuleDefinition, claim: ClaimContext) -> RuleResult:
        pattern = rule.rule_logic.get("pattern")

        flagged = False
        evidence: dict[str, Any] = {"rule_code": rule.rule_code, "pattern": pattern}

        if pattern == "duplicate_claim":
            flagged = bool(claim.metadata.get("is_duplicate", False))
            if flagged:
                evidence["original_auth"] = claim.metadata.get("original_auth")

        if not flagged:
            return RuleResult(
                flagged=False,
                rule_code=rule.rule_code,
                action=None,
                confidence_tier=None,
                risk_score=0,
                evidence=evidence,
                severity=None,
            )

        confidence_tier = "high"
        risk_score = 85
        return RuleResult(
            flagged=True,
            rule_code=rule.rule_code,
            action=rule.default_action,
            confidence_tier=confidence_tier,
            risk_score=risk_score,
            evidence=evidence,
            severity="critical",
        )

    def _evaluate_statistical(self, rule: RuleDefinition, claim: ClaimContext) -> RuleResult:
        logic = rule.rule_logic
        field_name = logic["field"]
        operator = logic["operator"]
        threshold = Decimal(str(logic["threshold"]))

        computed = self._get_field_value(field_name, claim)
        if computed is None:
            return RuleResult(
                flagged=False,
                rule_code=rule.rule_code,
                action=None,
                confidence_tier=None,
                risk_score=0,
                evidence={"field": field_name, "value": None},
                severity=None,
                skip_reason="field_not_available",
            )

        computed_decimal = Decimal(str(computed))
        flagged = self._compare(computed_decimal, operator, threshold)

        if not flagged:
            return RuleResult(
                flagged=False,
                rule_code=rule.rule_code,
                action=None,
                confidence_tier=None,
                risk_score=0,
                evidence={
                    "rule_code": rule.rule_code,
                    "field": field_name,
                    "computed_value": str(computed_decimal),
                    "threshold": str(threshold),
                },
                severity=None,
            )

        confidence_tier = self._compute_confidence(computed_decimal, rule.confidence_scoring)
        risk_score = self._confidence_to_risk_score(confidence_tier, computed_decimal, threshold)
        severity = self._risk_score_to_severity(risk_score)

        return RuleResult(
            flagged=True,
            rule_code=rule.rule_code,
            action=rule.default_action,
            confidence_tier=confidence_tier,
            risk_score=risk_score,
            evidence={
                "rule_code": rule.rule_code,
                "field": field_name,
                "computed_value": str(computed_decimal),
                "threshold": str(threshold),
            },
            severity=severity,
        )

    def _evaluate_comparison(self, rule: RuleDefinition, claim: ClaimContext) -> RuleResult:
        # Comparison rules compare two fields within the claim
        return self._evaluate_threshold(rule, claim)

    def _evaluate_composite(self, rule: RuleDefinition, claim: ClaimContext) -> RuleResult:
        # Composite rules combine multiple sub-rules (simplified: evaluate each sub-condition)
        sub_rules = rule.rule_logic.get("sub_rules", [])
        any_flagged = False
        evidence: dict[str, Any] = {"rule_code": rule.rule_code, "sub_results": []}

        for sub in sub_rules:
            sub_rule = RuleDefinition(
                rule_code=rule.rule_code + "_sub",
                name=rule.name,
                rule_type=sub.get("rule_type", "threshold"),
                rule_logic=sub,
                default_parameters=rule.default_parameters,
                default_action=rule.default_action,
                confidence_scoring=rule.confidence_scoring,
                client_types=rule.client_types,
                detection_mode=rule.detection_mode,
            )
            sub_result = self.evaluate(sub_rule, claim)
            evidence["sub_results"].append({"flagged": sub_result.flagged, "rule_code": sub_rule.rule_code})
            if sub_result.flagged:
                any_flagged = True

        if not any_flagged:
            return RuleResult(
                flagged=False,
                rule_code=rule.rule_code,
                action=None,
                confidence_tier=None,
                risk_score=0,
                evidence=evidence,
                severity=None,
            )

        return RuleResult(
            flagged=True,
            rule_code=rule.rule_code,
            action=rule.default_action,
            confidence_tier="medium",
            risk_score=60,
            evidence=evidence,
            severity="high",
        )

    def _get_field_value(self, field_name: str, claim: ClaimContext) -> Decimal | None:
        """Compute derived fields or read from claim/metadata."""
        if field_name == "nq_to_wac_ratio":
            wac_total = claim.wac_per_unit * claim.quantity
            if wac_total == 0:
                return None
            return claim.nq / wac_total

        if field_name == "dv_to_awp_ratio":
            awp_total = claim.awp_per_unit * claim.quantity
            if awp_total == 0:
                return None
            return claim.dv / awp_total

        if field_name == "refill_pct":
            val = claim.metadata.get("refill_pct")
            return Decimal(str(val)) if val is not None else None

        if field_name == "volume_vs_avg_ratio":
            val = claim.metadata.get("volume_vs_avg_ratio")
            return Decimal(str(val)) if val is not None else None

        # Try metadata first, then claim attributes
        val = claim.metadata.get(field_name)
        if val is not None:
            return Decimal(str(val))

        attr = getattr(claim, field_name, None)
        return Decimal(str(attr)) if attr is not None else None

    def _compare(self, value: Decimal, operator: str, threshold: Decimal) -> bool:
        ops = {
            "gt": value > threshold,
            "gte": value >= threshold,
            "lt": value < threshold,
            "lte": value <= threshold,
            "eq": value == threshold,
            "ne": value != threshold,
        }
        return ops.get(operator, False)

    def _compute_confidence(self, computed: Decimal, scoring: dict[str, Any]) -> str:
        """Determine confidence tier based on how far computed exceeds thresholds."""
        if not scoring:
            return "medium"
        high = Decimal(str(scoring["high"])) if "high" in scoring else None
        medium = Decimal(str(scoring["medium"])) if "medium" in scoring else None

        if high is not None and computed >= high:
            return "high"
        if medium is not None and computed >= medium:
            return "medium"
        return "low"

    def _confidence_to_risk_score(self, tier: str, computed: Decimal, threshold: Decimal) -> int:
        base = {"high": 85, "medium": 60, "low": 40}.get(tier, 40)
        return min(100, base)

    @staticmethod
    def _risk_score_to_severity(score: int) -> str:
        if score > 75:
            return "critical"
        if score > 50:
            return "high"
        if score > 25:
            return "medium"
        return "low"
