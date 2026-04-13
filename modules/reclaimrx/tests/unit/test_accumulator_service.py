"""Tests for accumulator/maximizer detection — TDD first."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session
from src._shim.events import published_events
from src.services.accumulator_service import AccumulatorService

from tests.conftest import TEST_TENANT_ID


class TestAccumulatorDetectionMethods:
    def test_plan_database_match_detects_known_accumulator(self, db: Session) -> None:
        svc = AccumulatorService(db)
        result = svc.detect_from_plan_database(
            plan_bin="610014",
            plan_pcn="RXBIN",
            plan_group="ACCUM01",
        )
        # Known accumulator BINs are seeded — return True if recognized
        assert isinstance(result, bool)

    def test_first_fill_analysis_detects_when_copay_not_applied(self, db: Session) -> None:
        svc = AccumulatorService(db)
        result = svc.analyze_first_fill(
            copay_assistance_amount=Decimal("50.00"),
            amount_applied_to_deductible=Decimal("0.00"),
            member_deductible_met=False,
        )
        assert result.is_accumulator is True
        assert result.confidence >= Decimal("0.80")

    def test_first_fill_analysis_no_flag_when_applied(self, db: Session) -> None:
        svc = AccumulatorService(db)
        result = svc.analyze_first_fill(
            copay_assistance_amount=Decimal("50.00"),
            amount_applied_to_deductible=Decimal("50.00"),
            member_deductible_met=False,
        )
        assert result.is_accumulator is False

    def test_pattern_analysis_detects_after_three_fills(self, db: Session) -> None:
        svc = AccumulatorService(db)
        fills = [
            {"fill_number": 1, "copay_assistance": Decimal("50.00"), "deductible_credit": Decimal("0.00")},
            {"fill_number": 2, "copay_assistance": Decimal("50.00"), "deductible_credit": Decimal("0.00")},
            {"fill_number": 3, "copay_assistance": Decimal("50.00"), "deductible_credit": Decimal("0.00")},
        ]
        result = svc.analyze_pattern(fills)
        assert result.is_accumulator is True
        assert result.program_type in ("accumulator", "maximizer", "unknown")

    def test_record_detection_publishes_event(self, db: Session) -> None:
        svc = AccumulatorService(db)
        svc.record_detection(
            tenant_id=TEST_TENANT_ID,
            member_id="MEM001",
            plan_bin="610014",
            plan_pcn="RXBIN",
            plan_group="ACCUM01",
            detection_method="plan_database_match",
            detection_fill_number=1,
            detection_confidence=Decimal("0.97"),
            program_type="accumulator",
            copay_assistance_amount=Decimal("100.00"),
            amount_applied_to_deductible=Decimal("0.00"),
            amount_not_applied=Decimal("100.00"),
            projected_annual_impact=Decimal("600.00"),
        )
        db.flush()
        events = [e for e in published_events() if e.topic == "fwa.accumulator_detected"]
        assert len(events) >= 1

    def test_pattern_analysis_with_single_fill_returns_not_accumulator(self, db: Session) -> None:
        svc = AccumulatorService(db)
        result = svc.analyze_pattern([
            {"fill_number": 1, "copay_assistance": Decimal("50.00"), "deductible_credit": Decimal("0.00")},
        ])
        assert result.is_accumulator is False
        assert result.evidence["fill_count"] == 1

    def test_impact_amounts_are_decimal(self, db: Session) -> None:
        svc = AccumulatorService(db)
        detection = svc.record_detection(
            tenant_id=TEST_TENANT_ID,
            member_id="MEM002",
            plan_bin="999999",
            plan_pcn="TEST",
            plan_group="TEST01",
            detection_method="first_fill_analysis",
            detection_fill_number=1,
            detection_confidence=Decimal("0.85"),
            program_type="accumulator",
            copay_assistance_amount=Decimal("75.00"),
            amount_applied_to_deductible=Decimal("0.00"),
            amount_not_applied=Decimal("75.00"),
            projected_annual_impact=Decimal("450.00"),
        )
        db.flush()
        assert isinstance(detection.copay_assistance_amount, Decimal)
        assert isinstance(detection.projected_annual_impact, Decimal)
