"""Rule evaluators for CSV-based FWA detection.

Pure functions -- no I/O, no DB, no side effects.
Financial precision: Decimal only, never float. ROUND_HALF_UP on every quantize.

Task 3.2 -- World-B port. Only "duplicate_claim" inline; grouping in Task 3.5.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

from src.detection.parsing import parse_money

_ZERO = Decimal("0")


@dataclass
class RuleResult:
    fired: bool
    risk_score: int
    severity: Optional[str]
    confidence: Optional[str]
    evidence: dict[str, Any] = field(default_factory=dict)


def _compare(value: Decimal, operator: str, threshold: Decimal) -> bool:
    ops: dict[str, bool] = {
        "gt": value > threshold,
        "gte": value >= threshold,
        "lt": value < threshold,
        "lte": value <= threshold,
        "eq": value == threshold,
        "ne": value != threshold,
    }
    return ops.get(operator, False)


def _compute_confidence(computed: Decimal, scoring: dict[str, Any]) -> str:
    if not scoring:
        return "medium"
    high = Decimal(str(scoring["high"])) if "high" in scoring else None
    medium = Decimal(str(scoring["medium"])) if "medium" in scoring else None
    if high is not None and computed >= high:
        return "high"
    if medium is not None and computed >= medium:
        return "medium"
    return "low"


def _confidence_to_risk_score(tier: str) -> int:
    base = {"high": 85, "medium": 60, "low": 40}.get(tier, 40)
    return min(100, base)


def _risk_score_to_severity(score: int) -> str:
    if score > 75:
        return "critical"
    if score > 50:
        return "high"
    if score > 25:
        return "medium"
    return "low"


def _resolve_field(fields: dict[str, Any], field_name: str) -> Optional[Decimal]:
    val = fields.get(field_name)
    if val is None:
        return None
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def evaluate_threshold(fields: dict[str, Any], rule_params: dict[str, Any]) -> RuleResult:
    field_name: str = rule_params["field"]
    operator: str = rule_params["operator"]
    threshold = Decimal(str(rule_params["threshold"]))
    confidence_scoring: dict[str, Any] = rule_params.get("confidence_scoring", {})
    computed = _resolve_field(fields, field_name)
    if computed is None:
        return RuleResult(
            fired=False, risk_score=0, severity=None, confidence=None,
            evidence={"field": field_name, "value": None},
        )
    flagged = _compare(computed, operator, threshold)
    if not flagged:
        return RuleResult(
            fired=False, risk_score=0, severity=None, confidence=None,
            evidence={
                "field": field_name,
                "computed_value": str(computed),
                "threshold": str(threshold),
                "operator": operator,
            },
        )
    confidence_tier = _compute_confidence(computed, confidence_scoring)
    risk_score = _confidence_to_risk_score(confidence_tier)
    severity = _risk_score_to_severity(risk_score)
    return RuleResult(
        fired=True, risk_score=risk_score, severity=severity, confidence=confidence_tier,
        evidence={
            "field": field_name,
            "computed_value": str(computed),
            "threshold": str(threshold),
            "operator": operator,
        },
    )


def evaluate_statistical(
    fields: dict[str, Any],
    rule_params: dict[str, Any],
    baseline: Optional[Decimal] = None,
) -> RuleResult:
    return evaluate_threshold(fields, rule_params)


def evaluate_comparison(fields: dict[str, Any], rule_params: dict[str, Any]) -> RuleResult:
    return evaluate_threshold(fields, rule_params)


def evaluate_pattern(fields: dict[str, Any], rule_params: dict[str, Any]) -> RuleResult:
    pattern: str = rule_params.get("pattern", "")
    evidence: dict[str, Any] = {"pattern": pattern}
    if pattern == "duplicate_claim":
        flagged = bool(fields.get("is_duplicate", False))
        if flagged:
            original = fields.get("original_auth")
            if original is not None:
                evidence["original_auth"] = original
            return RuleResult(
                fired=True, risk_score=85, severity="critical", confidence="high",
                evidence=evidence,
            )
    return RuleResult(fired=False, risk_score=0, severity=None, confidence=None, evidence=evidence)


def evaluate_composite(fields: dict[str, Any], rule_params: dict[str, Any]) -> RuleResult:
    sub_rules: list[dict[str, Any]] = rule_params.get("sub_rules", [])
    any_flagged = False
    sub_results: list[dict[str, Any]] = []
    for sub in sub_rules:
        rule_type = sub.get("rule_type", "threshold")
        if rule_type == "statistical":
            sub_result = evaluate_statistical(fields, sub)
        elif rule_type == "comparison":
            sub_result = evaluate_comparison(fields, sub)
        elif rule_type == "pattern":
            sub_result = evaluate_pattern(fields, sub)
        else:
            sub_result = evaluate_threshold(fields, sub)
        sub_results.append({"fired": sub_result.fired, "field": sub.get("field")})
        if sub_result.fired:
            any_flagged = True
    evidence: dict[str, Any] = {"sub_results": sub_results}
    if not any_flagged:
        return RuleResult(fired=False, risk_score=0, severity=None, confidence=None, evidence=evidence)
    return RuleResult(fired=True, risk_score=60, severity="high", confidence="medium", evidence=evidence)


def derive_fields(row: dict[str, Any]) -> dict[str, Any]:
    is_reversal = str(row.get("transaction_code", "")).strip().upper() == "B2"

    def _parse(key: str) -> Decimal:
        raw = row.get(key)
        result = parse_money(raw)
        return result if result is not None else _ZERO

    nq: Decimal = _parse("ingredient_cost_paid")
    dv: Decimal = _parse("dispensing_fee_paid")
    extended_wac: Decimal = _parse("extended_wac")
    drug_awp: Decimal = _parse("drug_awp")

    if is_reversal:
        nq = abs(nq)
        dv = abs(dv)
        extended_wac = abs(extended_wac)
        drug_awp = abs(drug_awp)

    nq_to_wac_ratio: Optional[Decimal]
    if extended_wac == _ZERO:
        nq_to_wac_ratio = None
    else:
        nq_to_wac_ratio = (dv + nq) / extended_wac

    dv_to_awp_ratio: Optional[Decimal]
    if drug_awp == _ZERO:
        dv_to_awp_ratio = None
    else:
        dv_to_awp_ratio = dv / drug_awp

    return {
        "nq": nq,
        "dv": dv,
        "nq_to_wac_ratio": nq_to_wac_ratio,
        "dv_to_awp_ratio": dv_to_awp_ratio,
    }
