"""Coverage tests for services that need additional test coverage.

These tests exercise the remaining uncovered code paths in:
- report_service, dashboard_service, regulatory_service, quality_service,
  actuarial_service, report_engine, scheduler, phi_controls, consumers
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.models.tables import ReportDefinition, ReportRun

# ──────────────────────────────────────────────────────────────────────────────
# ReportService
# ──────────────────────────────────────────────────────────────────────────────
from src.services.report_service import ReportService
from src.utils.constants import STATUS_COMPLETED, STATUS_FAILED, STATUS_RUNNING


def _mock_db_with_row(row: object | None) -> MagicMock:
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [row] if row else []
    result.scalar_one_or_none.return_value = row
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.delete = AsyncMock()
    return db


def _make_report_defn(
    tenant_id: str = "t1",
    report_id: str = "def1",
    contains_phi: bool = False,
) -> MagicMock:
    defn = MagicMock(spec=ReportDefinition)
    defn.id = report_id
    defn.tenant_id = tenant_id
    defn.name = "Test Report"
    defn.description = "A test report"
    defn.category = "claims"
    defn.data_source = "claims"
    defn.columns = [{"field": "claim_id", "label": "Claim ID", "type": "string"}]
    defn.default_filters = None
    defn.default_groupings = None
    defn.default_sort = None
    defn.calculated_fields = None
    defn.summary_row = None
    defn.chart_type = None
    defn.chart_config = None
    defn.required_permission = None
    defn.is_system = False
    defn.is_active = True
    defn.contains_phi = contains_phi
    defn.created_at = datetime.now(timezone.utc)
    defn.updated_at = datetime.now(timezone.utc)
    return defn


class TestReportServiceCoverage:
    @pytest.mark.asyncio
    async def test_create_definition_invalid_raises(self) -> None:
        db = _mock_db_with_row(None)
        svc = ReportService(db)
        with pytest.raises(ValueError, match="Invalid report definition"):
            await svc.create_definition(
                "t1",
                {
                    "name": "X",
                    "category": "bad_cat",
                    "data_source": "claims",
                    "columns": [{"field": "x", "label": "X"}],
                },
            )

    @pytest.mark.asyncio
    async def test_create_definition_valid(self) -> None:
        db = _mock_db_with_row(None)
        svc = ReportService(db)
        defn = await svc.create_definition(
            "t1",
            {
                "name": "Valid Report",
                "category": "claims",
                "data_source": "claims",
                "columns": [{"field": "claim_id", "label": "Claim ID", "type": "string"}],
            },
        )
        db.add.assert_called_once()
        db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_report_no_tenant_raises(self) -> None:
        db = _mock_db_with_row(None)
        svc = ReportService(db)
        with pytest.raises(ValueError, match="tenant_id is required"):
            await svc.execute_report("def1", None, {})

    @pytest.mark.asyncio
    async def test_execute_report_not_found_raises(self) -> None:
        db = _mock_db_with_row(None)
        svc = ReportService(db)
        with pytest.raises(ValueError, match="not found"):
            await svc.execute_report("missing_def", "t1", {})

    @pytest.mark.asyncio
    async def test_execute_report_creates_run(self) -> None:
        defn = _make_report_defn()
        db = _mock_db_with_row(defn)
        svc = ReportService(db)
        run = await svc.execute_report(
            "def1", "t1", {"date_from": "2026-01-01"}, requested_by="user1", output_format="csv"
        )
        db.add.assert_called_once()
        db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_run_success(self) -> None:
        db = _mock_db_with_row(None)
        db.flush = AsyncMock()
        svc = ReportService(db)

        run = MagicMock(spec=ReportRun)
        run.started_at = datetime.now(timezone.utc) - timedelta(seconds=30)
        run.status = STATUS_RUNNING
        run.completed_at = None
        run.duration_seconds = None

        result = await svc.complete_run(run, row_count=500, output_file_id="file1")
        assert run.status == STATUS_COMPLETED
        assert run.row_count == 500
        db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_run_with_error(self) -> None:
        db = _mock_db_with_row(None)
        db.flush = AsyncMock()
        svc = ReportService(db)

        run = MagicMock(spec=ReportRun)
        run.started_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        run.status = STATUS_RUNNING
        run.completed_at = None
        run.duration_seconds = None

        result = await svc.complete_run(run, row_count=0, error_message="DB timeout")
        assert run.status == STATUS_FAILED
        assert run.error_message == "DB timeout"

    @pytest.mark.asyncio
    async def test_list_runs_returns_list(self) -> None:
        run = MagicMock()
        db = _mock_db_with_row(run)
        svc = ReportService(db)
        result = await svc.list_runs("t1", report_id="def1")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_run_returns_none_for_wrong_tenant(self) -> None:
        db = _mock_db_with_row(None)
        svc = ReportService(db)
        result = await svc.get_run("run1", "t_wrong")
        assert result is None


# ──────────────────────────────────────────────────────────────────────────────
# DashboardService
# ──────────────────────────────────────────────────────────────────────────────

from src.models.tables import Dashboard, FilterPreset, UserDashboard
from src.services.dashboard_service import DashboardService


def _make_dashboard(tenant_id: str = "t1") -> MagicMock:
    d = MagicMock(spec=Dashboard)
    d.id = "dash1"
    d.tenant_id = tenant_id
    d.name = "Test Dashboard"
    d.description = None
    d.role_target = "operator"
    d.layout = []
    d.is_default = False
    d.is_system = False
    d.created_at = datetime.now(timezone.utc)
    d.updated_at = datetime.now(timezone.utc)
    return d


class TestDashboardServiceCoverage:
    @pytest.mark.asyncio
    async def test_create_dashboard(self) -> None:
        db = _mock_db_with_row(None)
        svc = DashboardService(db)
        dash = await svc.create_dashboard("t1", {"name": "New Dash", "layout": []})
        db.add.assert_called_once()
        db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_dashboard_not_found_returns_none(self) -> None:
        db = _mock_db_with_row(None)
        svc = DashboardService(db)
        result = await svc.update_dashboard("missing", "t1", {"name": "New"})
        assert result is None

    @pytest.mark.asyncio
    async def test_update_dashboard_updates_layout(self) -> None:
        dash = _make_dashboard()
        db = _mock_db_with_row(dash)
        svc = DashboardService(db)
        result = await svc.update_dashboard("dash1", "t1", {"layout": [{"widget": "kpi"}]})
        assert dash.layout == [{"widget": "kpi"}]

    @pytest.mark.asyncio
    async def test_save_user_dashboard_creates_new(self) -> None:
        # First call returns None (no existing), second call for flush
        db = MagicMock()
        result1 = MagicMock()
        result1.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result1)
        db.add = MagicMock()
        db.flush = AsyncMock()

        svc = DashboardService(db)
        ud = await svc.save_user_dashboard(
            "user1",
            "t1",
            "dash1",
            custom_layout=[{"widget": "kpi"}],
            pinned_filters={"date": "2026"},
        )
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_user_dashboard_updates_existing(self) -> None:
        existing = MagicMock(spec=UserDashboard)
        existing.custom_layout = None
        existing.pinned_filters = None

        db = MagicMock()
        result1 = MagicMock()
        result1.scalar_one_or_none.return_value = existing
        db.execute = AsyncMock(return_value=result1)
        db.flush = AsyncMock()

        svc = DashboardService(db)
        ud = await svc.save_user_dashboard(
            "user1",
            "t1",
            "dash1",
            custom_layout=[{"widget": "table"}],
        )
        assert existing.custom_layout == [{"widget": "table"}]

    @pytest.mark.asyncio
    async def test_list_filter_presets_with_user(self) -> None:
        preset = MagicMock()
        db = _mock_db_with_row(preset)
        svc = DashboardService(db)
        presets = await svc.list_filter_presets("t1", user_id="user1")
        assert isinstance(presets, list)

    @pytest.mark.asyncio
    async def test_save_filter_preset(self) -> None:
        db = _mock_db_with_row(None)
        svc = DashboardService(db)
        preset = await svc.save_filter_preset(
            "t1", "user1", "Q1", {"date_from": "2026-01-01"}, None
        )
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_filter_preset_not_found(self) -> None:
        db = _mock_db_with_row(None)
        svc = DashboardService(db)
        result = await svc.delete_filter_preset("missing", "t1", "user1")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_filter_preset_success(self) -> None:
        preset = MagicMock(spec=FilterPreset)
        db = _mock_db_with_row(preset)
        db.delete = AsyncMock()
        db.flush = AsyncMock()
        svc = DashboardService(db)
        result = await svc.delete_filter_preset("p1", "t1", "user1")
        assert result is True
        db.delete.assert_called_once_with(preset)


# ──────────────────────────────────────────────────────────────────────────────
# RegulatoryService
# ──────────────────────────────────────────────────────────────────────────────

from src.models.tables import RegulatorySubmission
from src.services.regulatory_service import RegulatoryService


def _make_submission(tenant_id: str = "t1") -> MagicMock:
    sub = MagicMock(spec=RegulatorySubmission)
    sub.id = "sub1"
    sub.tenant_id = tenant_id
    sub.report_type = "caa_transparency_semiannual"
    sub.period_start = date(2026, 1, 1)
    sub.period_end = date(2026, 6, 30)
    sub.due_date = date(2026, 6, 30)
    sub.status = "draft"
    sub.submitted_at = None
    sub.accepted_at = None
    sub.file_id = None
    sub.submission_reference = None
    sub.reviewed_by = None
    sub.approved_by = None
    sub.created_at = datetime.now(timezone.utc)
    sub.updated_at = datetime.now(timezone.utc)
    return sub


class TestRegulatoryServiceCoverage:
    @pytest.mark.asyncio
    async def test_list_submissions(self) -> None:
        sub = _make_submission()
        db = _mock_db_with_row(sub)
        svc = RegulatoryService(db)
        result = await svc.list_submissions("t1")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_create_submission(self) -> None:
        db = _mock_db_with_row(None)
        svc = RegulatoryService(db)
        sub = await svc.create_submission(
            "t1",
            {
                "report_type": "caa_transparency_semiannual",
                "period_start": date(2026, 1, 1),
                "period_end": date(2026, 6, 30),
                "due_date": date(2026, 6, 30),
            },
        )
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_not_found_returns_none(self) -> None:
        db = _mock_db_with_row(None)
        svc = RegulatoryService(db)
        result = await svc.update_status("missing", "t1", "submitted")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_status_sets_submitted_at(self) -> None:
        sub = _make_submission()
        db = _mock_db_with_row(sub)
        svc = RegulatoryService(db)
        result = await svc.update_status("sub1", "t1", "submitted")
        assert sub.status == "submitted"
        assert sub.submitted_at is not None

    @pytest.mark.asyncio
    async def test_update_status_non_submitted(self) -> None:
        sub = _make_submission()
        db = _mock_db_with_row(sub)
        svc = RegulatoryService(db)
        result = await svc.update_status("sub1", "t1", "in_review")
        assert sub.status == "in_review"
        assert sub.submitted_at is None

    @pytest.mark.asyncio
    async def test_get_upcoming_deadlines(self) -> None:
        sub = _make_submission()
        sub.due_date = date.today() + timedelta(days=10)
        sub.status = "draft"
        db = _mock_db_with_row(sub)
        svc = RegulatoryService(db)
        deadlines = await svc.get_upcoming_deadlines("t1")
        assert isinstance(deadlines, list)

    @pytest.mark.asyncio
    async def test_generate_caa_transparency_report(self) -> None:
        db = _mock_db_with_row(None)
        svc = RegulatoryService(db)
        result = await svc.generate_caa_transparency_report(
            "t1", date(2026, 1, 1), date(2026, 6, 30)
        )
        assert result["report_type"] == "caa_transparency_semiannual"
        assert "net_drug_spending" in result["sections"]
        assert "rebate_disclosure" in result["sections"]
        assert "spread_pricing" in result["sections"]


# ──────────────────────────────────────────────────────────────────────────────
# QualityService
# ──────────────────────────────────────────────────────────────────────────────

from src.services.quality_service import QualityService


class TestQualityServiceCoverage:
    @pytest.mark.asyncio
    async def test_get_star_ratings_dashboard(self) -> None:
        db = _mock_db_with_row(None)
        svc = QualityService(db)
        result = await svc.get_star_ratings_dashboard("t1")
        assert result["tenant_id"] == "t1"
        assert "measures" in result
        assert len(result["measures"]) == 12  # D01-D12

    @pytest.mark.asyncio
    async def test_get_adherence_detail_valid_measure(self) -> None:
        db = _mock_db_with_row(None)
        svc = QualityService(db)
        result = await svc.get_adherence_detail("t1", "D01")
        assert result["measure_id"] == "D01"

    @pytest.mark.asyncio
    async def test_get_adherence_detail_invalid_measure_raises(self) -> None:
        db = _mock_db_with_row(None)
        svc = QualityService(db)
        with pytest.raises(ValueError, match="Invalid measure"):
            await svc.get_adherence_detail("t1", "D99")

    @pytest.mark.asyncio
    async def test_get_gap_members(self) -> None:
        db = _mock_db_with_row(None)
        svc = QualityService(db)
        result = await svc.get_gap_members("t1")
        assert result["tenant_id"] == "t1"
        assert "members_below_threshold" in result

    @pytest.mark.asyncio
    async def test_get_year_end_projections(self) -> None:
        db = _mock_db_with_row(None)
        svc = QualityService(db)
        result = await svc.get_year_end_projections("t1")
        assert "projections" in result
        assert "D01" in result["projections"]


# ──────────────────────────────────────────────────────────────────────────────
# ActuarialService (additional coverage)
# ──────────────────────────────────────────────────────────────────────────────

from src.services.actuarial_service import ActuarialService


class TestActuarialServiceCoverage:
    @pytest.mark.asyncio
    async def test_list_models(self) -> None:
        model = MagicMock()
        db = _mock_db_with_row(model)
        svc = ActuarialService(db)
        result = await svc.list_models("t1")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_model_not_found(self) -> None:
        db = _mock_db_with_row(None)
        svc = ActuarialService(db)
        result = await svc.get_model("missing", "t1")
        assert result is None

    @pytest.mark.asyncio
    async def test_run_scenario_model_not_found_raises(self) -> None:
        db = _mock_db_with_row(None)
        svc = ActuarialService(db)
        with pytest.raises(ValueError, match="not found"):
            await svc.run_scenario("missing_model", "t1", {})

    @pytest.mark.asyncio
    async def test_run_scenario_success(self) -> None:
        model = MagicMock()
        model.id = "m1"
        model.tenant_id = "t1"
        db = _mock_db_with_row(model)
        svc = ActuarialService(db)
        result = await svc.run_scenario(
            "m1",
            "t1",
            {
                "claims": [{"amount_paid": "100.00"}],
            },
        )
        assert "total_original_cost" in result


# ──────────────────────────────────────────────────────────────────────────────
# ReportEngine (additional coverage)
# ──────────────────────────────────────────────────────────────────────────────

from src.services.report_engine import ReportEngine


class TestReportEngineCoverage:
    def _engine(self) -> ReportEngine:
        db = MagicMock()
        return ReportEngine(db)

    def test_format_row_with_phi_masking(self) -> None:
        engine = self._engine()
        columns = [
            {"field": "claim_id", "label": "Claim ID", "format": "string"},
            {"field": "member_name", "label": "Member", "format": "string"},
        ]
        row = {"claim_id": "C001", "member_name": "John Doe"}
        result = engine.format_row(
            row, columns, masking_level="redacted", phi_fields=["member_name"]
        )
        assert result["claim_id"] == "C001"
        assert result["member_name"] == "[REDACTED]"

    def test_format_row_full_detail(self) -> None:
        engine = self._engine()
        columns = [{"field": "amount", "label": "Amount", "format": "currency"}]
        row = {"amount": Decimal("1234.56")}
        result = engine.format_row(row, columns)
        assert "$1,234.56" in result["amount"]

    def test_apply_summary_row_sum(self) -> None:
        engine = self._engine()
        rows = [
            {"amount": Decimal("100.00")},
            {"amount": Decimal("200.00")},
            {"amount": Decimal("300.00")},
        ]
        summary = engine.apply_summary_row(rows, {"amount": "sum"})
        assert summary is not None
        assert summary["amount"] == Decimal("600.00")

    def test_apply_summary_row_avg(self) -> None:
        engine = self._engine()
        rows = [{"score": Decimal("80.00")}, {"score": Decimal("90.00")}]
        summary = engine.apply_summary_row(rows, {"score": "avg"})
        assert summary is not None
        assert summary["score"] == Decimal("85.00")

    def test_apply_summary_row_count(self) -> None:
        engine = self._engine()
        rows = [{"x": Decimal("1.00")}, {"x": Decimal("2.00")}]
        summary = engine.apply_summary_row(rows, {"x": "count"})
        assert summary["x"] == 2

    def test_apply_summary_row_min_max(self) -> None:
        engine = self._engine()
        rows = [{"v": Decimal("5.00")}, {"v": Decimal("10.00")}, {"v": Decimal("3.00")}]
        summary = engine.apply_summary_row(rows, {"v": "min"})
        assert summary["v"] == Decimal("3.00")
        summary2 = engine.apply_summary_row(rows, {"v": "max"})
        assert summary2["v"] == Decimal("10.00")

    def test_apply_summary_row_empty_returns_none(self) -> None:
        engine = self._engine()
        result = engine.apply_summary_row([], {"amount": "sum"})
        assert result is None

    def test_apply_summary_row_no_config_returns_none(self) -> None:
        engine = self._engine()
        rows = [{"x": Decimal("1.00")}]
        result = engine.apply_summary_row(rows, None)
        assert result is None

    def test_engine_uses_replica_if_provided(self) -> None:
        db = MagicMock()
        replica = MagicMock()
        engine = ReportEngine(db, replica)
        assert engine._replica is replica

    def test_engine_uses_primary_as_replica_if_not_provided(self) -> None:
        db = MagicMock()
        engine = ReportEngine(db)
        assert engine._replica is db


# ──────────────────────────────────────────────────────────────────────────────
# Scheduler (additional coverage)
# ──────────────────────────────────────────────────────────────────────────────

from src.services.scheduler import calculate_next_run


class TestSchedulerCoverage:
    def test_biweekly_next_run(self) -> None:
        last_run = datetime(2026, 1, 1, 6, 0, tzinfo=timezone.utc)
        next_run = calculate_next_run("biweekly", last_run)
        assert next_run.date() == date(2026, 1, 15)

    def test_on_demand_next_run_far_future(self) -> None:
        last_run = datetime(2026, 1, 1, tzinfo=timezone.utc)
        next_run = calculate_next_run("on_demand", last_run)
        assert (next_run.date() - date(2026, 1, 1)).days > 365


# ──────────────────────────────────────────────────────────────────────────────
# PHI controls additional paths
# ──────────────────────────────────────────────────────────────────────────────

from src.services.phi_controls import (
    apply_phi_masking,
    get_phi_masking_level,
    requires_export_restriction,
)


class TestPhiControlsAdditional:
    def test_partial_masking_keeps_name(self) -> None:
        row = {"member_name": "Jane", "dob": "1990-01-01", "claim_id": "C1"}
        phi_fields = ["member_name", "dob"]
        result = apply_phi_masking(row, "partial", phi_fields)
        assert result["member_name"] == "Jane"
        assert result["dob"] == "[MASKED]"

    def test_superadmin_gets_full_detail(self) -> None:
        assert get_phi_masking_level("superadmin") == "full_detail"

    def test_export_restriction_phi_full_detail_not_restricted(self) -> None:
        result = requires_export_restriction(True, "full_detail", "operator")
        assert result is False

    def test_phi_field_not_in_row_skipped(self) -> None:
        row = {"claim_id": "C1"}
        result = apply_phi_masking(row, "redacted", ["member_name", "dob"])
        assert "member_name" not in result
        assert result["claim_id"] == "C1"


# ──────────────────────────────────────────────────────────────────────────────
# Event consumers
# ──────────────────────────────────────────────────────────────────────────────

from src.events.consumers import (
    EVENT_HANDLERS,
    handle_billing_journal_entry,
    handle_fwa_claim_flagged,
    handle_fwa_investigation_opened,
    handle_fwa_investigation_resolved,
    handle_prefund_critical,
    handle_quality_measure_at_risk,
)


class TestEventConsumers:
    @pytest.mark.asyncio
    async def test_handle_billing_journal_entry(self) -> None:
        await handle_billing_journal_entry({"correlation_id": "c1", "journal_entry_id": "e1"}, "t1")

    @pytest.mark.asyncio
    async def test_handle_fwa_claim_flagged(self) -> None:
        await handle_fwa_claim_flagged({"entity_id": "pharm1", "severity": "high"}, "t1")

    @pytest.mark.asyncio
    async def test_handle_fwa_investigation_opened(self) -> None:
        await handle_fwa_investigation_opened({"investigation_id": "inv1"}, "t1")

    @pytest.mark.asyncio
    async def test_handle_fwa_investigation_resolved(self) -> None:
        await handle_fwa_investigation_resolved({"investigation_id": "inv1"}, "t1")

    @pytest.mark.asyncio
    async def test_handle_prefund_critical_no_service(self) -> None:
        await handle_prefund_critical({"client_id": "c1"}, "t1", alert_service=None)

    @pytest.mark.asyncio
    async def test_handle_prefund_critical_with_service(self) -> None:
        alert_svc = MagicMock()
        alert_svc.trigger_alert_report = AsyncMock()
        await handle_prefund_critical({"client_id": "c1"}, "t1", alert_service=alert_svc)
        alert_svc.trigger_alert_report.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_quality_measure_at_risk(self) -> None:
        await handle_quality_measure_at_risk({"measure_id": "D01", "current_rate": "0.75"}, "t1")

    def test_event_handlers_registry(self) -> None:
        assert "billing.journal_entries" in EVENT_HANDLERS
        assert "fwa.claim_flagged" in EVENT_HANDLERS
        assert "prefund.critical" in EVENT_HANDLERS
        assert "quality.measure_at_risk" in EVENT_HANDLERS


# ──────────────────────────────────────────────────────────────────────────────
# Jobs (scheduled)
# ──────────────────────────────────────────────────────────────────────────────

from src.jobs.scheduled import (
    check_regulatory_deadlines,
    purge_expired_report_files,
    refresh_claims_materialized_view,
    refresh_financial_materialized_view,
    run_due_scheduled_reports,
    seed_prebuilt_reports,
)


class TestScheduledJobs:
    @pytest.mark.asyncio
    async def test_run_due_scheduled_reports(self) -> None:
        db = MagicMock()
        # The job now awaits db.execute to query due schedules; return empty result set.
        empty_result = MagicMock()
        empty_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=empty_result)
        result = await run_due_scheduled_reports(db)
        assert "triggered" in result
        assert "skipped" in result

    @pytest.mark.asyncio
    async def test_refresh_claims_mv(self) -> None:
        db = MagicMock()
        await refresh_claims_materialized_view(db)

    @pytest.mark.asyncio
    async def test_refresh_financial_mv(self) -> None:
        db = MagicMock()
        await refresh_financial_materialized_view(db)

    @pytest.mark.asyncio
    async def test_check_regulatory_deadlines(self) -> None:
        db = MagicMock()
        bus = MagicMock()
        await check_regulatory_deadlines(db, bus)

    @pytest.mark.asyncio
    async def test_purge_expired_report_files(self) -> None:
        db = MagicMock()
        count = await purge_expired_report_files(db)
        assert count == 0

    @pytest.mark.asyncio
    async def test_seed_prebuilt_reports_creates_all(self) -> None:
        # Mock: no existing reports/dashboards
        db = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        result_mock.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=result_mock)
        db.add = MagicMock()
        db.flush = AsyncMock()

        result = await seed_prebuilt_reports(db)
        assert result["reports_created"] >= 50
        assert result["dashboards_created"] == 5

    @pytest.mark.asyncio
    async def test_seed_prebuilt_reports_skips_existing(self) -> None:
        # Mock: all reports already exist
        existing = MagicMock()
        db = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        db.execute = AsyncMock(return_value=result_mock)
        db.add = MagicMock()
        db.flush = AsyncMock()

        result = await seed_prebuilt_reports(db)
        assert result["reports_skipped"] >= 50
        assert result["reports_created"] == 0
        db.add.assert_not_called()
