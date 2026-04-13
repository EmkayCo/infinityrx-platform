"""Unit tests for the report engine: definition, execution, and formatting logic."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from src.services.report_engine import (
    apply_calculated_fields,
    apply_phi_masking,
    build_report_filter,
    estimate_output_size,
    format_value,
    validate_report_definition,
)
from src.utils.constants import (
    FORMAT_CSV,
    FORMAT_EXCEL,
    FORMAT_PDF,
    PHI_FULL_DETAIL,
    PHI_PARTIAL,
    PHI_REDACTED,
)


class TestValidateReportDefinition:
    def test_valid_definition_passes(self) -> None:
        defn = {
            "id": str(uuid.uuid4()),
            "name": "Test Report",
            "category": "claims",
            "data_source": "billing",
            "columns": [{"field": "claim_id", "label": "Claim ID", "type": "string"}],
        }
        errors = validate_report_definition(defn)
        assert errors == []

    def test_missing_name_fails(self) -> None:
        defn = {"category": "claims", "data_source": "billing", "columns": []}
        errors = validate_report_definition(defn)
        assert any("name" in e for e in errors)

    def test_empty_columns_fails(self) -> None:
        defn = {"name": "Test", "category": "claims", "data_source": "billing", "columns": []}
        errors = validate_report_definition(defn)
        assert any("columns" in e for e in errors)

    def test_invalid_category_fails(self) -> None:
        defn = {
            "name": "Test",
            "category": "invalid_category",
            "data_source": "billing",
            "columns": [{"field": "x", "label": "X", "type": "string"}],
        }
        errors = validate_report_definition(defn)
        assert any("category" in e for e in errors)

    def test_missing_category_fails(self) -> None:
        defn = {
            "name": "Test",
            "data_source": "billing",
            "columns": [{"field": "x", "label": "X", "type": "string"}],
        }
        errors = validate_report_definition(defn)
        assert any("category" in e for e in errors)


class TestApplyCalculatedFields:
    def test_percentage_calculation(self) -> None:
        rows = [
            {"count": 50, "total": 100},
            {"count": 25, "total": 100},
        ]
        calc_fields = [
            {"name": "pct", "formula": "percentage", "numerator": "count", "denominator": "total"}
        ]
        result = apply_calculated_fields(rows, calc_fields)
        assert result[0]["pct"] == Decimal("50.00")
        assert result[1]["pct"] == Decimal("25.00")

    def test_running_total(self) -> None:
        rows = [
            {"amount": Decimal("100.00")},
            {"amount": Decimal("200.00")},
            {"amount": Decimal("150.00")},
        ]
        calc_fields = [{"name": "running_total", "formula": "running_total", "field": "amount"}]
        result = apply_calculated_fields(rows, calc_fields)
        assert result[0]["running_total"] == Decimal("100.00")
        assert result[1]["running_total"] == Decimal("300.00")
        assert result[2]["running_total"] == Decimal("450.00")

    def test_percentage_with_zero_denominator_returns_zero(self) -> None:
        rows = [{"count": 5, "total": 0}]
        calc_fields = [
            {"name": "pct", "formula": "percentage", "numerator": "count", "denominator": "total"}
        ]
        result = apply_calculated_fields(rows, calc_fields)
        assert result[0]["pct"] == Decimal("0.00")

    def test_empty_rows_returns_empty(self) -> None:
        result = apply_calculated_fields([], [])
        assert result == []

    def test_no_calc_fields_returns_rows_unchanged(self) -> None:
        rows = [{"a": 1}, {"a": 2}]
        result = apply_calculated_fields(rows, [])
        assert result == rows


class TestApplyPhiMasking:
    PHI_FIELDS = ["member_name", "dob", "address", "phone"]

    def test_full_detail_returns_unchanged(self) -> None:
        row = {"member_name": "John Doe", "dob": "1980-01-01", "claim_id": "C001"}
        result = apply_phi_masking(row, PHI_FULL_DETAIL, self.PHI_FIELDS)
        assert result["member_name"] == "John Doe"
        assert result["dob"] == "1980-01-01"

    def test_partial_masks_dob_and_address(self) -> None:
        row = {"member_name": "John Doe", "dob": "1980-01-01", "address": "123 Main St"}
        result = apply_phi_masking(row, PHI_PARTIAL, self.PHI_FIELDS)
        assert result["member_name"] == "John Doe"
        assert result["dob"] == "[MASKED]"
        assert result["address"] == "[MASKED]"

    def test_redacted_masks_all_phi_fields(self) -> None:
        row = {
            "member_name": "John Doe",
            "dob": "1980-01-01",
            "address": "123 Main St",
            "claim_id": "C001",
        }
        result = apply_phi_masking(row, PHI_REDACTED, self.PHI_FIELDS)
        assert result["member_name"] == "[REDACTED]"
        assert result["dob"] == "[REDACTED]"
        assert result["address"] == "[REDACTED]"
        assert result["claim_id"] == "C001"  # non-PHI unchanged

    def test_non_phi_fields_always_preserved(self) -> None:
        row = {"claim_id": "C001", "amount": Decimal("100.00"), "member_name": "Jane"}
        result = apply_phi_masking(row, PHI_REDACTED, self.PHI_FIELDS)
        assert result["claim_id"] == "C001"
        assert result["amount"] == Decimal("100.00")

    def test_invalid_masking_level_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid masking level"):
            apply_phi_masking({}, "invalid_level", self.PHI_FIELDS)


class TestBuildReportFilter:
    def test_date_range_filter(self) -> None:
        filters = {
            "date_from": "2026-01-01",
            "date_to": "2026-12-31",
        }
        result = build_report_filter(filters)
        assert result["date_from"] == date(2026, 1, 1)
        assert result["date_to"] == date(2026, 12, 31)

    def test_invalid_date_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid date"):
            build_report_filter({"date_from": "not-a-date"})

    def test_empty_filters_returns_empty(self) -> None:
        result = build_report_filter({})
        assert result == {}

    def test_tenant_id_always_required_in_filters(self) -> None:
        result = build_report_filter({"tenant_id": "abc-123"})
        assert result.get("tenant_id") == "abc-123"


class TestEstimateOutputSize:
    def test_small_dataset_no_warning(self) -> None:
        result = estimate_output_size(1000, FORMAT_EXCEL)
        assert result["warning"] is False
        assert result["exceeds_limit"] is False

    def test_excel_warn_at_500k(self) -> None:
        result = estimate_output_size(600_000, FORMAT_EXCEL)
        assert result["warning"] is True
        assert result["exceeds_limit"] is False

    def test_excel_exceeds_at_1m(self) -> None:
        result = estimate_output_size(1_100_000, FORMAT_EXCEL)
        assert result["warning"] is True
        assert result["exceeds_limit"] is True

    def test_csv_warn_at_5m(self) -> None:
        result = estimate_output_size(6_000_000, FORMAT_CSV)
        assert result["warning"] is True
        assert result["exceeds_limit"] is False

    def test_csv_exceeds_at_10m(self) -> None:
        result = estimate_output_size(11_000_000, FORMAT_CSV)
        assert result["exceeds_limit"] is True

    def test_zero_rows_no_warning(self) -> None:
        result = estimate_output_size(0, FORMAT_PDF)
        assert result["warning"] is False


class TestFormatValue:
    def test_decimal_formats_with_2_places(self) -> None:
        assert format_value(Decimal("1234.5"), "currency") == "$1,234.50"

    def test_date_formats_as_string(self) -> None:
        assert format_value(date(2026, 1, 15), "date") == "01/15/2026"

    def test_percentage_adds_symbol(self) -> None:
        assert format_value(Decimal("85.50"), "percentage") == "85.50%"

    def test_integer_formats_with_commas(self) -> None:
        assert format_value(1234567, "integer") == "1,234,567"

    def test_none_returns_empty_string(self) -> None:
        assert format_value(None, "string") == ""

    def test_string_returned_as_is(self) -> None:
        assert format_value("hello", "string") == "hello"
