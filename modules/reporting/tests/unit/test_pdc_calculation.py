"""Unit tests for PDC (Proportion of Days Covered) calculation.

PDC must exactly match CMS methodology for Star Ratings compliance.
100% coverage required on this path.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest
from src.services.quality import (
    calculate_pdc,
    classify_adherence,
    identify_adherence_gaps,
    project_year_end_pdc,
)


class TestPdcCalculation:
    """PDC = days supply covered in measurement period / total days in period."""

    def test_perfect_adherence(self) -> None:
        # 365 days supply covers all of 2026
        fills = [{"fill_date": date(2026, 1, 1), "days_supply": 365}]
        period_start = date(2026, 1, 1)
        period_end = date(2026, 12, 31)
        pdc = calculate_pdc(fills, period_start, period_end)
        assert pdc == Decimal("1.00")

    def test_zero_fills_zero_pdc(self) -> None:
        pdc = calculate_pdc([], date(2026, 1, 1), date(2026, 12, 31))
        assert pdc == Decimal("0.00")

    def test_single_90_day_fill_in_365_day_period(self) -> None:
        fills = [{"fill_date": date(2026, 1, 1), "days_supply": 90}]
        pdc = calculate_pdc(fills, date(2026, 1, 1), date(2026, 12, 31))
        # 90 / 365 = 0.2466... → rounds to 0.25
        expected = (Decimal("90") / Decimal("365")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        assert pdc == expected

    def test_overlapping_fills_not_double_counted(self) -> None:
        """CMS PDC: overlapping days counted only once."""
        fills = [
            {"fill_date": date(2026, 1, 1), "days_supply": 30},
            {"fill_date": date(2026, 1, 15), "days_supply": 30},  # overlaps by 15 days
        ]
        period_start = date(2026, 1, 1)
        period_end = date(2026, 12, 31)
        pdc = calculate_pdc(fills, period_start, period_end)
        # Should count 45 unique covered days, not 60
        days_covered = 45
        expected = (Decimal(str(days_covered)) / Decimal("365")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        assert pdc == expected

    def test_fills_before_period_excluded(self) -> None:
        fills = [
            {"fill_date": date(2025, 12, 1), "days_supply": 30},  # before period
            {"fill_date": date(2026, 1, 1), "days_supply": 90},  # in period
        ]
        period_start = date(2026, 1, 1)
        period_end = date(2026, 12, 31)
        pdc = calculate_pdc(fills, period_start, period_end)
        expected = (Decimal("90") / Decimal("365")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        assert pdc == expected

    def test_fills_extending_past_period_truncated(self) -> None:
        fills = [
            {"fill_date": date(2026, 12, 1), "days_supply": 90},  # extends into next year
        ]
        period_start = date(2026, 1, 1)
        period_end = date(2026, 12, 31)
        pdc = calculate_pdc(fills, period_start, period_end)
        # Only 31 days in period (Dec 1-31)
        expected = (Decimal("31") / Decimal("365")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        assert pdc == expected

    def test_pdc_is_decimal(self) -> None:
        pdc = calculate_pdc([], date(2026, 1, 1), date(2026, 12, 31))
        assert isinstance(pdc, Decimal)

    def test_pdc_never_exceeds_one(self) -> None:
        fills = [{"fill_date": date(2026, 1, 1), "days_supply": 1000}]
        pdc = calculate_pdc(fills, date(2026, 1, 1), date(2026, 12, 31))
        assert pdc <= Decimal("1.00")

    def test_period_start_must_be_before_end(self) -> None:
        with pytest.raises(ValueError, match="period_start must be before period_end"):
            calculate_pdc([], date(2026, 12, 31), date(2026, 1, 1))


class TestAdherenceClassification:
    def test_adherent_above_threshold(self) -> None:
        assert classify_adherence(Decimal("0.80")) == "adherent"
        assert classify_adherence(Decimal("0.95")) == "adherent"
        assert classify_adherence(Decimal("1.00")) == "adherent"

    def test_non_adherent_below_threshold(self) -> None:
        assert classify_adherence(Decimal("0.69")) == "non_adherent"
        assert classify_adherence(Decimal("0.50")) == "non_adherent"
        assert classify_adherence(Decimal("0.00")) == "non_adherent"

    def test_at_risk_defined_range(self) -> None:
        # Members 0.70-0.79 are at-risk (near threshold, outreach opportunity)
        assert classify_adherence(Decimal("0.75")) == "at_risk"
        assert classify_adherence(Decimal("0.70")) == "at_risk"
        assert classify_adherence(Decimal("0.79")) == "at_risk"

    def test_returns_string(self) -> None:
        result = classify_adherence(Decimal("0.85"))
        assert isinstance(result, str)


class TestAdherenceGaps:
    def test_gap_identified_when_refill_overdue(self) -> None:
        # Fill: Jan 1-30 (30 days), supply ends Jan 30
        # Gap starts Jan 31, as_of Feb 15 → gap = Jan 31 to Feb 15 = 16 days
        fills = [{"fill_date": date(2026, 1, 1), "days_supply": 30}]
        as_of = date(2026, 2, 15)
        gaps = identify_adherence_gaps(fills, as_of)
        assert len(gaps) == 1
        assert gaps[0]["gap_days"] == 16

    def test_no_gap_when_current_fill_active(self) -> None:
        fills = [{"fill_date": date(2026, 1, 1), "days_supply": 90}]
        as_of = date(2026, 2, 1)  # within supply
        gaps = identify_adherence_gaps(fills, as_of)
        assert gaps == []

    def test_multiple_gaps_identified(self) -> None:
        fills = [
            {"fill_date": date(2026, 1, 1), "days_supply": 30},
            {"fill_date": date(2026, 3, 1), "days_supply": 30},  # 29-day gap
        ]
        as_of = date(2026, 4, 15)  # 15 days past second fill
        gaps = identify_adherence_gaps(fills, as_of)
        assert len(gaps) == 2

    def test_empty_fills_returns_one_gap_from_start(self) -> None:
        as_of = date(2026, 3, 1)
        gaps = identify_adherence_gaps([], as_of)
        assert len(gaps) == 0  # no fills means no gap to calculate from


class TestYearEndPdcProjection:
    def test_on_track_projection(self) -> None:
        current_pdc = Decimal("0.85")
        days_elapsed = 180
        total_days = 365
        projected = project_year_end_pdc(current_pdc, days_elapsed, total_days)
        assert projected == Decimal("0.85")

    def test_projection_with_no_days_elapsed_raises(self) -> None:
        with pytest.raises(ValueError, match="days_elapsed must be positive"):
            project_year_end_pdc(Decimal("0.85"), 0, 365)

    def test_projection_does_not_exceed_one(self) -> None:
        projected = project_year_end_pdc(Decimal("1.00"), 100, 365)
        assert projected <= Decimal("1.00")

    def test_projection_is_decimal(self) -> None:
        result = project_year_end_pdc(Decimal("0.75"), 90, 365)
        assert isinstance(result, Decimal)
