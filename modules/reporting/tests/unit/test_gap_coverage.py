"""Targeted tests for remaining coverage gaps."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

# ── api/dependencies.py ──────────────────────────────────────────────────────
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_dependencies_missing_tenant_header() -> None:
    from fastapi import APIRouter
    from src.api.dependencies import get_current_tenant_id

    app = FastAPI()
    router = APIRouter()

    @router.get("/test")
    async def test_route(tid: str = __import__("fastapi").Depends(get_current_tenant_id)) -> dict:
        return {"tid": tid}

    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/test")
    assert resp.status_code == 422  # missing header


def test_dependencies_missing_user_header() -> None:
    from fastapi import APIRouter
    from src.api.dependencies import get_current_user_id

    app = FastAPI()
    router = APIRouter()

    @router.get("/test")
    async def test_route(uid: str = __import__("fastapi").Depends(get_current_user_id)) -> dict:
        return {"uid": uid}

    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/test")
    assert resp.status_code == 422


def test_get_user_permissions_parses_comma_separated() -> None:
    import asyncio

    from src.api.dependencies import get_user_permissions

    result = asyncio.run(get_user_permissions("phi_access,reports,admin"))
    assert "phi_access" in result
    assert "reports" in result
    assert "admin" in result


def test_get_user_permissions_empty_returns_empty_list() -> None:
    import asyncio

    from src.api.dependencies import get_user_permissions

    result = asyncio.run(get_user_permissions(""))
    assert result == []


# ── dashboard_service.py gaps ─────────────────────────────────────────────────

from src.services.dashboard_service import DashboardService


def _mk_db(row: object = None) -> MagicMock:
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    result.scalars.return_value.all.return_value = [row] if row else []
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.delete = AsyncMock()
    return db


class TestDashboardServiceGaps:
    @pytest.mark.asyncio
    async def test_list_dashboards_with_role_filter(self) -> None:
        db = _mk_db(None)
        svc = DashboardService(db)
        result = await svc.list_dashboards("t1", role_target="operator")
        assert db.execute.called

    @pytest.mark.asyncio
    async def test_update_dashboard_name_only(self) -> None:
        from src.models.tables import Dashboard

        dash = MagicMock(spec=Dashboard)
        dash.tenant_id = "t1"
        dash.name = "Old Name"
        dash.layout = []
        dash.id = "d1"
        dash.description = None
        dash.role_target = None
        dash.is_default = False
        dash.is_system = False
        dash.created_at = datetime.now(timezone.utc)
        dash.updated_at = datetime.now(timezone.utc)

        db = _mk_db(dash)
        svc = DashboardService(db)
        result = await svc.update_dashboard("d1", "t1", {"name": "New Name"})
        assert dash.name == "New Name"

    @pytest.mark.asyncio
    async def test_list_filter_presets_no_user(self) -> None:
        db = _mk_db(None)
        svc = DashboardService(db)
        result = await svc.list_filter_presets("t1", user_id=None)
        assert isinstance(result, list)


# ── report_engine.py gaps ─────────────────────────────────────────────────────

from src.services.report_engine import (
    ReportEngine,
    apply_calculated_fields,
)


class TestReportEngineGaps:
    def test_format_row_field_not_in_col_map(self) -> None:
        engine = ReportEngine(MagicMock())
        # Field in row but no column definition — should still be formatted
        columns = [{"field": "known", "label": "Known", "format": "string"}]
        row = {"known": "hello", "unknown": "world"}
        result = engine.format_row(row, columns)
        # unknown field formatted as string by default
        assert result.get("unknown") == "world"

    def test_apply_summary_row_empty_field_returns_zero(self) -> None:
        engine = ReportEngine(MagicMock())
        rows = [{"other": Decimal("1.00")}]  # field "amount" missing from row
        summary = engine.apply_summary_row(rows, {"amount": "sum"})
        assert summary is not None
        assert summary["amount"] == Decimal("0.00")

    def test_apply_calculated_percentage_missing_fields(self) -> None:
        rows = [{"count": 5}]  # missing denominator key
        calc = [
            {
                "name": "pct",
                "formula": "percentage",
                "numerator": "count",
                "denominator": "missing_key",
            }
        ]
        result = apply_calculated_fields(rows, calc)
        # denominator missing → treated as 0 → returns 0.00
        assert result[0]["pct"] == Decimal("0.00")


# ── quality.py gap (line 140-142) ─────────────────────────────────────────────

from src.services.quality import calculate_dstar_measure_rate


class TestQualityGaps:
    def test_dstar_rate_zero_denominator(self) -> None:
        rate = calculate_dstar_measure_rate(100, 0)
        assert rate == Decimal("0.00")

    def test_dstar_rate_normal(self) -> None:
        rate = calculate_dstar_measure_rate(80, 100)
        assert rate == Decimal("0.8000")


# ── phi_controls.py gaps ──────────────────────────────────────────────────────

from src.services.phi_controls import (
    PhiControlsService,
    get_phi_masking_level,
    requires_export_restriction,
)


class TestPhiControlsGaps:
    def test_operator_with_empty_permissions_gets_partial(self) -> None:
        result = get_phi_masking_level("operator", permissions=[])
        assert result == "partial"

    def test_operator_with_none_permissions_gets_partial(self) -> None:
        result = get_phi_masking_level("operator", permissions=None)
        assert result == "partial"

    def test_export_restriction_phi_partial_mask(self) -> None:
        result = requires_export_restriction(True, "partial", "operator")
        assert result is False

    def test_service_should_watermark(self) -> None:
        svc = PhiControlsService()
        assert svc.should_watermark(True, "pdf") is True
        assert svc.should_watermark(False, "pdf") is False
        assert svc.should_watermark(True, "csv") is False

    def test_service_masking_level_client_portal(self) -> None:
        svc = PhiControlsService()
        assert svc.masking_level_for_role("client_portal") == "redacted"


# ── scheduler.py gaps (lines 44-45, 55-56) ───────────────────────────────────

from src.services.scheduler import calculate_next_run


class TestSchedulerGaps:
    def test_monthly_with_day_30_in_february(self) -> None:
        """Day 30 doesn't exist in February — should clamp to 28."""
        last_run = datetime(2026, 1, 30, 6, 0, tzinfo=__import__("datetime").timezone.utc)
        next_run = calculate_next_run("monthly", last_run, day_of_month=30)
        assert next_run.month == 2
        assert next_run.day == 28  # Feb 2026 has 28 days

    def test_quarterly_month_overflow(self) -> None:
        """Q4 + 3 months = month 13 → January next year."""
        last_run = datetime(2026, 10, 1, 6, 0, tzinfo=__import__("datetime").timezone.utc)
        next_run = calculate_next_run("quarterly", last_run)
        assert next_run.month == 1
        assert next_run.year == 2027


# ── regulatory schema gap (line 36) ──────────────────────────────────────────

from src.api.schemas.regulatory import RegulatorySubmissionCreate


class TestRegulatorySchemaGap:
    def test_invalid_report_type_raises(self) -> None:
        from datetime import date

        with pytest.raises(Exception):
            RegulatorySubmissionCreate(
                report_type="invalid_type",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 6, 30),
                due_date=date(2026, 6, 30),
            )
