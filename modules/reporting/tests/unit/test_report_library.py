"""Unit tests for the pre-built report library."""

from __future__ import annotations

from src.services.report_library import (
    PRE_BUILT_DASHBOARDS,
    PREBUILT_REPORTS,
    get_prebuilt_report_count,
    get_prebuilt_reports_by_category,
)
from src.utils.constants import ALL_CATEGORIES


class TestPrebuiltReportLibrary:
    def test_has_at_least_50_prebuilt_reports(self) -> None:
        assert len(PREBUILT_REPORTS) >= 50

    def test_get_count_matches_list(self) -> None:
        assert get_prebuilt_report_count() == len(PREBUILT_REPORTS)

    def test_all_reports_have_required_fields(self) -> None:
        required = {"name", "category", "data_source", "columns"}
        for report in PREBUILT_REPORTS:
            missing = required - set(report.keys())
            assert not missing, f"Report '{report.get('name')}' missing: {missing}"

    def test_all_categories_represented(self) -> None:
        report_categories = {r["category"] for r in PREBUILT_REPORTS}
        for cat in ALL_CATEGORIES:
            assert cat in report_categories, f"Category {cat!r} has no pre-built reports"

    def test_all_reports_have_valid_category(self) -> None:
        for report in PREBUILT_REPORTS:
            assert report["category"] in ALL_CATEGORIES, (
                f"Report '{report['name']}' has invalid category: {report['category']}"
            )

    def test_all_reports_have_at_least_one_column(self) -> None:
        for report in PREBUILT_REPORTS:
            assert len(report["columns"]) >= 1, f"Report '{report['name']}' has no columns"

    def test_all_columns_have_required_fields(self) -> None:
        for report in PREBUILT_REPORTS:
            for col in report["columns"]:
                assert "field" in col, f"Column in '{report['name']}' missing 'field'"
                assert "label" in col, f"Column in '{report['name']}' missing 'label'"

    def test_get_by_category_returns_correct_reports(self) -> None:
        claims_reports = get_prebuilt_reports_by_category("claims")
        assert all(r["category"] == "claims" for r in claims_reports)
        assert len(claims_reports) >= 6  # PRD specifies 8

    def test_claims_category_has_8_reports(self) -> None:
        assert len(get_prebuilt_reports_by_category("claims")) >= 8

    def test_billing_ap_has_7_reports(self) -> None:
        assert len(get_prebuilt_reports_by_category("billing_ap")) >= 7

    def test_billing_ar_has_6_reports(self) -> None:
        assert len(get_prebuilt_reports_by_category("billing_ar")) >= 6

    def test_financial_has_8_reports(self) -> None:
        assert len(get_prebuilt_reports_by_category("financial")) >= 8

    def test_fwa_has_7_reports(self) -> None:
        assert len(get_prebuilt_reports_by_category("fwa")) >= 7

    def test_phi_flag_is_boolean(self) -> None:
        for report in PREBUILT_REPORTS:
            if "contains_phi" in report:
                assert isinstance(report["contains_phi"], bool)

    def test_no_float_in_column_values(self) -> None:
        """Financial column values must not use float type annotation."""
        for report in PREBUILT_REPORTS:
            for col in report["columns"]:
                assert col.get("type") != "float", (
                    f"Report '{report['name']}', column '{col['field']}' uses float — use decimal"
                )


class TestPrebuiltDashboards:
    def test_has_5_prebuilt_dashboards(self) -> None:
        assert len(PRE_BUILT_DASHBOARDS) == 5

    def test_all_dashboards_have_required_fields(self) -> None:
        required = {"name", "role_target", "layout"}
        for dash in PRE_BUILT_DASHBOARDS:
            missing = required - set(dash.keys())
            assert not missing, f"Dashboard '{dash.get('name')}' missing: {missing}"

    def test_all_dashboards_have_widgets(self) -> None:
        for dash in PRE_BUILT_DASHBOARDS:
            assert len(dash["layout"]) >= 1, f"Dashboard '{dash['name']}' has no widgets"

    def test_operator_dashboard_exists(self) -> None:
        roles = {d["role_target"] for d in PRE_BUILT_DASHBOARDS}
        assert "operator" in roles

    def test_fwa_analyst_dashboard_exists(self) -> None:
        roles = {d["role_target"] for d in PRE_BUILT_DASHBOARDS}
        assert "fwa_analyst" in roles

    def test_quality_manager_dashboard_exists(self) -> None:
        roles = {d["role_target"] for d in PRE_BUILT_DASHBOARDS}
        assert "quality_manager" in roles
