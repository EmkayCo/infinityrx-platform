"""Accumulator/maximizer detection service.

Three detection methods:
1. Plan database match — check known accumulator BINs
2. First-fill analysis — compare copay assistance vs deductible credit
3. Pattern analysis — after 3+ fills, check if credits aren't accumulating
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from src._shim.events import publish
from src.models.tables import AccumulatorDetection
from src.utils.constants import KNOWN_ACCUMULATOR_BINS
from src.utils.money import money


@dataclass
class DetectionAnalysisResult:
    is_accumulator: bool
    confidence: Decimal
    program_type: str
    evidence: dict


class AccumulatorService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def detect_from_plan_database(
        self,
        *,
        plan_bin: str,
        plan_pcn: str,
        plan_group: str,
    ) -> bool:
        """Check if the plan's BIN matches known accumulator/maximizer plans."""
        return plan_bin in KNOWN_ACCUMULATOR_BINS

    def analyze_first_fill(
        self,
        *,
        copay_assistance_amount: Decimal,
        amount_applied_to_deductible: Decimal,
        member_deductible_met: bool,
    ) -> DetectionAnalysisResult:
        """Analyze first fill for accumulator pattern.

        If copay assistance is applied but deductible credit is $0 (and deductible
        not already met), this is an accumulator plan.
        """
        safe_copay = money(copay_assistance_amount)
        safe_applied = money(amount_applied_to_deductible)

        if safe_copay > Decimal("0.00") and safe_applied == Decimal("0.00") and not member_deductible_met:
            gap = safe_copay - safe_applied
            confidence = Decimal("0.90").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return DetectionAnalysisResult(
                is_accumulator=True,
                confidence=confidence,
                program_type="accumulator",
                evidence={
                    "method": "first_fill_analysis",
                    "copay_assistance": str(safe_copay),
                    "amount_applied": str(safe_applied),
                    "unaccumulated_gap": str(gap),
                },
            )

        return DetectionAnalysisResult(
            is_accumulator=False,
            confidence=Decimal("0.90"),
            program_type="unknown",
            evidence={
                "method": "first_fill_analysis",
                "copay_assistance": str(safe_copay),
                "amount_applied": str(safe_applied),
            },
        )

    def analyze_pattern(
        self,
        fills: list[dict],
    ) -> DetectionAnalysisResult:
        """After 3+ fills, analyze accumulation pattern.

        If copay assistance is consistently applied but deductible credit is $0,
        this confirms an accumulator/maximizer plan.
        """
        if len(fills) < 2:
            return DetectionAnalysisResult(
                is_accumulator=False,
                confidence=Decimal("0.50"),
                program_type="unknown",
                evidence={"method": "pattern_analysis", "fill_count": len(fills)},
            )

        non_accumulating = sum(
            1 for f in fills
            if money(f.get("copay_assistance", Decimal("0"))) > Decimal("0.00")
            and money(f.get("deductible_credit", Decimal("0"))) == Decimal("0.00")
        )
        rate = Decimal(str(non_accumulating)) / Decimal(str(len(fills)))
        is_accumulator = rate >= Decimal("0.80")
        confidence = rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return DetectionAnalysisResult(
            is_accumulator=is_accumulator,
            confidence=confidence,
            program_type="accumulator" if is_accumulator else "unknown",
            evidence={
                "method": "pattern_analysis",
                "fill_count": len(fills),
                "non_accumulating_count": non_accumulating,
                "non_accumulating_rate": str(rate),
            },
        )

    def record_detection(
        self,
        *,
        tenant_id: uuid.UUID,
        member_id: str,
        plan_bin: str | None,
        plan_pcn: str | None,
        plan_group: str | None,
        detection_method: str,
        detection_fill_number: int | None,
        detection_confidence: Decimal,
        program_type: str | None,
        copay_assistance_amount: Decimal | None,
        amount_applied_to_deductible: Decimal | None,
        amount_not_applied: Decimal | None,
        projected_annual_impact: Decimal | None,
        recommended_action: str | None = None,
    ) -> AccumulatorDetection:
        detection = AccumulatorDetection(
            tenant_id=str(tenant_id),
            member_id=member_id,
            plan_bin=plan_bin,
            plan_pcn=plan_pcn,
            plan_group=plan_group,
            detection_method=detection_method,
            detection_fill_number=detection_fill_number,
            detection_confidence=detection_confidence.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
            program_type=program_type,
            copay_assistance_amount=money(copay_assistance_amount) if copay_assistance_amount is not None else None,
            amount_applied_to_deductible=money(amount_applied_to_deductible) if amount_applied_to_deductible is not None else None,
            amount_not_applied=money(amount_not_applied) if amount_not_applied is not None else None,
            projected_annual_impact=money(projected_annual_impact) if projected_annual_impact is not None else None,
            recommended_action=recommended_action,
        )
        self._session.add(detection)
        self._session.flush()

        publish(
            "fwa.accumulator_detected",
            {
                "tenant_id": str(tenant_id),
                "member_id": member_id,
                "detection_id": detection.id,
                "program_type": program_type,
                "detection_method": detection_method,
                "projected_annual_impact": str(projected_annual_impact) if projected_annual_impact else None,
            },
        )
        return detection
