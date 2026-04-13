"""Unit tests for Pydantic schema validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from src.api.schemas.dashboards import DashboardCreate, FilterPresetCreate
from src.api.schemas.regulatory import (
    RegulatoryStatusUpdate,
)
from src.api.schemas.reports import (
    ColumnDefinition,
    ReportDefinitionCreate,
    ReportRunRequest,
    ReportScheduleCreate,
)


class TestReportDefinitionCreateSchema:
    def test_valid_schema(self) -> None:
        schema = ReportDefinitionCreate(
            name="Test Report",
            category="claims",
            data_source="claims",
            columns=[ColumnDefinition(field="claim_id", label="Claim ID")],
        )
        assert schema.name == "Test Report"

    def test_invalid_category_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReportDefinitionCreate(
                name="Test",
                category="invalid",
                data_source="claims",
                columns=[ColumnDefinition(field="x", label="X")],
            )

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReportDefinitionCreate(
                name="",
                category="claims",
                data_source="claims",
                columns=[ColumnDefinition(field="x", label="X")],
            )

    def test_contains_phi_defaults_false(self) -> None:
        schema = ReportDefinitionCreate(
            name="Test",
            category="claims",
            data_source="claims",
            columns=[ColumnDefinition(field="x", label="X")],
        )
        assert schema.contains_phi is False


class TestReportRunRequestSchema:
    def test_valid_format(self) -> None:
        req = ReportRunRequest(output_format="excel")
        assert req.output_format == "excel"

    def test_invalid_format_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReportRunRequest(output_format="docx")

    def test_default_format_is_excel(self) -> None:
        req = ReportRunRequest()
        assert req.output_format == "excel"


class TestReportScheduleCreateSchema:
    def test_valid_daily_schedule(self) -> None:
        schema = ReportScheduleCreate(
            report_definition_id="def1",
            name="Daily Claims",
            frequency="daily",
            output_format="excel",
            delivery_method="email",
        )
        assert schema.frequency == "daily"

    def test_weekly_without_dow_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReportScheduleCreate(
                report_definition_id="def1",
                name="Weekly",
                frequency="weekly",
                output_format="excel",
                delivery_method="email",
            )

    def test_monthly_without_dom_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReportScheduleCreate(
                report_definition_id="def1",
                name="Monthly",
                frequency="monthly",
                output_format="excel",
                delivery_method="email",
            )

    def test_invalid_frequency_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReportScheduleCreate(
                report_definition_id="def1",
                name="Bad Freq",
                frequency="hourly",
                output_format="excel",
                delivery_method="email",
            )

    def test_invalid_output_format_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReportScheduleCreate(
                report_definition_id="def1",
                name="Test",
                frequency="daily",
                output_format="docx",
                delivery_method="email",
            )

    def test_invalid_delivery_method_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReportScheduleCreate(
                report_definition_id="def1",
                name="Test",
                frequency="daily",
                output_format="excel",
                delivery_method="fax",
            )


class TestDashboardCreateSchema:
    def test_valid_dashboard(self) -> None:
        dash = DashboardCreate(name="My Dashboard")
        assert dash.name == "My Dashboard"
        assert dash.layout == []

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            DashboardCreate(name="")


class TestFilterPresetCreateSchema:
    def test_valid_preset(self) -> None:
        preset = FilterPresetCreate(
            name="Q1 Filters",
            filters={"date_from": "2026-01-01", "date_to": "2026-03-31"},
        )
        assert preset.name == "Q1 Filters"

    def test_shared_defaults_false(self) -> None:
        preset = FilterPresetCreate(name="Test", filters={})
        assert preset.shared is False


class TestRegulatoryStatusUpdateSchema:
    def test_valid_status(self) -> None:
        update = RegulatoryStatusUpdate(status="submitted")
        assert update.status == "submitted"

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(Exception):
            RegulatoryStatusUpdate(status="bogus_status")
