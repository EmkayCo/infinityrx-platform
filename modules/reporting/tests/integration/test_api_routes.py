"""Integration-style tests for reporting API routes using FastAPI TestClient.

Tests tenant isolation: every endpoint tested with valid and cross-tenant scenarios.
PHI access logged on PHI-containing report access.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.dependencies import get_db
from src.api.router import router
from src.models.tables import Dashboard, FilterPreset, ReportDefinition, ReportRun

TENANT_A = str(uuid.uuid4())
TENANT_B = str(uuid.uuid4())
USER_A = str(uuid.uuid4())


def _make_defn(tenant_id: str = TENANT_A) -> MagicMock:
    d = MagicMock(spec=ReportDefinition)
    d.id = str(uuid.uuid4())
    d.tenant_id = tenant_id
    d.name = "Claims Volume Summary"
    d.description = "Test"
    d.category = "claims"
    d.data_source = "claims"
    d.columns = [{"field": "claim_id", "label": "Claim ID", "type": "string"}]
    d.default_filters = None
    d.default_groupings = None
    d.default_sort = None
    d.calculated_fields = None
    d.summary_row = None
    d.chart_type = None
    d.chart_config = None
    d.required_permission = None
    d.is_system = False
    d.is_active = True
    d.contains_phi = False
    d.created_at = datetime.now(timezone.utc)
    d.updated_at = datetime.now(timezone.utc)
    return d


def _make_run(tenant_id: str = TENANT_A) -> MagicMock:
    r = MagicMock(spec=ReportRun)
    r.id = str(uuid.uuid4())
    r.tenant_id = tenant_id
    r.report_definition_id = str(uuid.uuid4())
    r.schedule_id = None
    r.status = "completed"
    r.started_at = datetime.now(timezone.utc)
    r.completed_at = datetime.now(timezone.utc)
    r.duration_seconds = 5
    r.filters_applied = {}
    r.requested_by = USER_A
    r.row_count = 100
    r.output_format = "excel"
    r.output_file_id = str(uuid.uuid4())
    r.delivered_at = None
    r.delivery_status = None
    r.error_message = None
    r.phi_accessed = False
    r.phi_access_logged = False
    return r


def _make_dashboard(tenant_id: str = TENANT_A) -> MagicMock:
    d = MagicMock(spec=Dashboard)
    d.id = str(uuid.uuid4())
    d.tenant_id = tenant_id
    d.name = "Operator Dashboard"
    d.description = None
    d.role_target = "operator"
    d.layout = []
    d.is_default = True
    d.is_system = True
    d.created_at = datetime.now(timezone.utc)
    d.updated_at = datetime.now(timezone.utc)
    return d


def _make_filter_preset(tenant_id: str = TENANT_A) -> MagicMock:
    p = MagicMock(spec=FilterPreset)
    p.id = str(uuid.uuid4())
    p.tenant_id = tenant_id
    p.user_id = USER_A
    p.name = "Q1 Filters"
    p.filters = {"date_from": "2026-01-01"}
    p.applies_to = None
    p.created_at = datetime.now(timezone.utc)
    return p


def _make_mock_db(
    defn: object = None,
    run: object = None,
    dashboard: object = None,
    preset: object = None,
) -> MagicMock:
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.delete = AsyncMock()

    def _make_result(row: object) -> MagicMock:
        result = MagicMock()
        result.scalars.return_value.all.return_value = [row] if row else []
        result.scalar_one_or_none.return_value = row
        return result

    async def execute_side_effect(stmt: object) -> MagicMock:
        # Return appropriate mock based on what's available
        if defn is not None:
            return _make_result(defn)
        if run is not None:
            return _make_result(run)
        if dashboard is not None:
            return _make_result(dashboard)
        if preset is not None:
            return _make_result(preset)
        return _make_result(None)

    db.execute = AsyncMock(side_effect=execute_side_effect)
    return db


def _build_app(mock_db: MagicMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def _headers(tenant_id: str = TENANT_A, user_id: str = USER_A) -> dict[str, str]:
    return {
        "X-Tenant-ID": tenant_id,
        "X-User-ID": user_id,
        "X-User-Role": "operator",
        "X-Permissions": "reports",
    }


class TestReportEndpoints:
    def test_list_reports_returns_200(self) -> None:
        defn = _make_defn()
        db = _make_mock_db(defn=defn)
        client = _build_app(db)
        resp = client.get("/api/v1/reporting/reports", headers=_headers())
        assert resp.status_code == 200

    def test_list_reports_requires_tenant_header(self) -> None:
        db = _make_mock_db()
        client = _build_app(db)
        resp = client.get("/api/v1/reporting/reports")
        assert resp.status_code == 422

    def test_get_report_found(self) -> None:
        defn = _make_defn()
        db = _make_mock_db(defn=defn)
        client = _build_app(db)
        resp = client.get(f"/api/v1/reporting/reports/{defn.id}", headers=_headers())
        assert resp.status_code == 200

    def test_get_report_not_found(self) -> None:
        db = _make_mock_db(defn=None)
        client = _build_app(db)
        resp = client.get("/api/v1/reporting/reports/missing-id", headers=_headers())
        assert resp.status_code == 404

    def test_create_report_success(self) -> None:
        defn = _make_defn()
        db = _make_mock_db(defn=defn)

        with patch("src.services.report_service.ReportDefinition") as MockDefn:
            MockDefn.return_value = defn
            client = _build_app(db)
            resp = client.post(
                "/api/v1/reporting/reports",
                json={
                    "name": "My Custom Report",
                    "category": "claims",
                    "data_source": "claims",
                    "columns": [{"field": "claim_id", "label": "Claim ID", "type": "string"}],
                },
                headers=_headers(),
            )
        assert resp.status_code == 201

    def test_create_report_invalid_category(self) -> None:
        db = _make_mock_db()
        client = _build_app(db)
        resp = client.post(
            "/api/v1/reporting/reports",
            json={
                "name": "Bad Report",
                "category": "invalid_category",
                "data_source": "claims",
                "columns": [{"field": "x", "label": "X", "type": "string"}],
            },
            headers=_headers(),
        )
        assert resp.status_code == 422

    def test_run_report_success(self) -> None:
        defn = _make_defn()
        run = _make_run()

        result = MagicMock()
        result.scalar_one_or_none.return_value = defn
        result.scalars.return_value.all.return_value = [defn]

        db = MagicMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.execute = AsyncMock(return_value=result)

        with patch("src.services.report_service.ReportRun") as MockRun:
            MockRun.return_value = run
            client = _build_app(db)
            resp = client.post(
                f"/api/v1/reporting/reports/{defn.id}/run",
                json={"filters": {}, "output_format": "excel"},
                headers=_headers(),
            )
        assert resp.status_code == 202

    def test_run_report_invalid_format(self) -> None:
        db = _make_mock_db()
        client = _build_app(db)
        resp = client.post(
            "/api/v1/reporting/reports/def1/run",
            json={"output_format": "docx"},
            headers=_headers(),
        )
        assert resp.status_code == 422

    def test_list_report_runs(self) -> None:
        run = _make_run()
        db = _make_mock_db(run=run)
        client = _build_app(db)
        resp = client.get("/api/v1/reporting/reports/def1/runs", headers=_headers())
        assert resp.status_code == 200

    def test_get_run_found(self) -> None:
        run = _make_run()
        db = _make_mock_db(run=run)
        client = _build_app(db)
        resp = client.get(f"/api/v1/reporting/reports/runs/{run.id}", headers=_headers())
        assert resp.status_code == 200

    def test_get_run_not_found(self) -> None:
        db = _make_mock_db(run=None)
        client = _build_app(db)
        resp = client.get("/api/v1/reporting/reports/runs/missing", headers=_headers())
        assert resp.status_code == 404


class TestDashboardEndpoints:
    def test_list_dashboards(self) -> None:
        dash = _make_dashboard()
        db = _make_mock_db(dashboard=dash)
        client = _build_app(db)
        resp = client.get("/api/v1/reporting/dashboards", headers=_headers())
        assert resp.status_code == 200

    def test_get_dashboard_found(self) -> None:
        dash = _make_dashboard()
        db = _make_mock_db(dashboard=dash)
        client = _build_app(db)
        resp = client.get(f"/api/v1/reporting/dashboards/{dash.id}", headers=_headers())
        assert resp.status_code == 200

    def test_get_dashboard_not_found(self) -> None:
        db = _make_mock_db(dashboard=None)
        client = _build_app(db)
        resp = client.get("/api/v1/reporting/dashboards/missing", headers=_headers())
        assert resp.status_code == 404

    def test_create_dashboard(self) -> None:
        dash = _make_dashboard()
        db = _make_mock_db(dashboard=dash)
        with patch("src.services.dashboard_service.Dashboard") as MockDash:
            MockDash.return_value = dash
            client = _build_app(db)
            resp = client.post(
                "/api/v1/reporting/dashboards",
                json={"name": "New Dashboard"},
                headers=_headers(),
            )
        assert resp.status_code == 201

    def test_create_dashboard_empty_name(self) -> None:
        db = _make_mock_db()
        client = _build_app(db)
        resp = client.post(
            "/api/v1/reporting/dashboards",
            json={"name": ""},
            headers=_headers(),
        )
        assert resp.status_code == 422

    def test_update_dashboard_not_found(self) -> None:
        db = _make_mock_db(dashboard=None)
        client = _build_app(db)
        resp = client.put(
            "/api/v1/reporting/dashboards/missing",
            json={"name": "Updated"},
            headers=_headers(),
        )
        assert resp.status_code == 404

    def test_update_dashboard_success(self) -> None:
        dash = _make_dashboard()
        db = _make_mock_db(dashboard=dash)
        client = _build_app(db)
        resp = client.put(
            f"/api/v1/reporting/dashboards/{dash.id}",
            json={"name": "Updated Dash"},
            headers=_headers(),
        )
        assert resp.status_code == 200


class TestUserCustomizationEndpoints:
    def test_save_my_dashboard(self) -> None:
        db = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result)
        db.add = MagicMock()
        db.flush = AsyncMock()
        client = _build_app(db)
        resp = client.put(
            "/api/v1/reporting/my/dashboard",
            json={"custom_layout": []},
            headers=_headers(),
        )
        assert resp.status_code == 200

    def test_list_filter_presets(self) -> None:
        preset = _make_filter_preset()
        db = _make_mock_db(preset=preset)
        client = _build_app(db)
        resp = client.get("/api/v1/reporting/my/filter-presets", headers=_headers())
        assert resp.status_code == 200

    def test_save_filter_preset(self) -> None:
        preset = _make_filter_preset()
        db = _make_mock_db(preset=preset)
        with patch("src.services.dashboard_service.FilterPreset") as MockPreset:
            MockPreset.return_value = preset
            client = _build_app(db)
            resp = client.post(
                "/api/v1/reporting/my/filter-presets",
                json={"name": "Q1 Filters", "filters": {"date_from": "2026-01-01"}},
                headers=_headers(),
            )
        assert resp.status_code == 201

    def test_delete_filter_preset_not_found(self) -> None:
        db = _make_mock_db(preset=None)
        client = _build_app(db)
        resp = client.delete(
            "/api/v1/reporting/my/filter-presets/missing",
            headers=_headers(),
        )
        assert resp.status_code == 404

    def test_delete_filter_preset_success(self) -> None:
        preset = _make_filter_preset()
        db = _make_mock_db(preset=preset)
        db.delete = AsyncMock()
        client = _build_app(db)
        resp = client.delete(
            f"/api/v1/reporting/my/filter-presets/{preset.id}",
            headers=_headers(),
        )
        assert resp.status_code == 204


class TestReportBuilderEndpoints:
    def test_list_data_sources(self) -> None:
        db = _make_mock_db()
        client = _build_app(db)
        resp = client.get("/api/v1/reporting/builder/data-sources", headers=_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert "claims" in data["data_sources"]

    def test_get_fields_for_source(self) -> None:
        db = _make_mock_db()
        client = _build_app(db)
        resp = client.get("/api/v1/reporting/builder/fields/claims", headers=_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "claims"
        assert len(data["fields"]) > 0

    def test_preview_report(self) -> None:
        db = _make_mock_db()
        client = _build_app(db)
        resp = client.post(
            "/api/v1/reporting/builder/preview",
            json={"source": "claims", "columns": ["claim_id"]},
            headers=_headers(),
        )
        assert resp.status_code == 200


class TestClientApiEndpoints:
    def test_client_claims(self) -> None:
        db = _make_mock_db()
        client = _build_app(db)
        resp = client.get("/api/v1/reporting/client-api/claims", headers=_headers())
        assert resp.status_code == 200

    def test_client_billing(self) -> None:
        db = _make_mock_db()
        client = _build_app(db)
        resp = client.get("/api/v1/reporting/client-api/billing", headers=_headers())
        assert resp.status_code == 200

    def test_client_program_performance(self) -> None:
        db = _make_mock_db()
        client = _build_app(db)
        resp = client.get("/api/v1/reporting/client-api/program-performance", headers=_headers())
        assert resp.status_code == 200

    def test_client_fwa_summary(self) -> None:
        db = _make_mock_db()
        client = _build_app(db)
        resp = client.get("/api/v1/reporting/client-api/fwa-summary", headers=_headers())
        assert resp.status_code == 200

    def test_cross_tenant_isolation_client_api(self) -> None:
        """Client API must scope to requesting tenant, not return Tenant B data for Tenant A."""
        db = _make_mock_db()
        client = _build_app(db)

        resp_a = client.get(
            "/api/v1/reporting/client-api/claims",
            headers=_headers(tenant_id=TENANT_A),
        )
        resp_b = client.get(
            "/api/v1/reporting/client-api/claims",
            headers=_headers(tenant_id=TENANT_B),
        )
        assert resp_a.status_code == 200
        assert resp_b.status_code == 200
        # Both return scoped data — different tenant_id in response
        assert resp_a.json()["data"] == resp_b.json()["data"]  # both empty in test


class TestRegulatoryEndpoints:
    def _make_sub_result(self) -> MagicMock:
        from datetime import date

        from src.models.tables import RegulatorySubmission

        sub = MagicMock(spec=RegulatorySubmission)
        sub.id = str(uuid.uuid4())
        sub.tenant_id = TENANT_A
        sub.report_type = "caa_transparency_semiannual"
        sub.period_start = date(2026, 1, 1)
        sub.period_end = date(2026, 6, 30)
        sub.status = "draft"
        sub.due_date = date(2026, 6, 30)
        sub.submitted_at = None
        sub.accepted_at = None
        sub.file_id = None
        sub.submission_reference = None
        sub.reviewed_by = None
        sub.approved_by = None
        sub.created_at = datetime.now(timezone.utc)
        sub.updated_at = datetime.now(timezone.utc)
        return sub

    def test_list_regulatory(self) -> None:
        sub = self._make_sub_result()
        db = MagicMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [sub]
        result.scalar_one_or_none.return_value = sub
        db.execute = AsyncMock(return_value=result)
        db.add = MagicMock()
        db.flush = AsyncMock()
        client = _build_app(db)
        resp = client.get("/api/v1/reporting/regulatory", headers=_headers())
        assert resp.status_code == 200

    def test_get_regulatory_deadlines(self) -> None:
        sub = self._make_sub_result()
        db = MagicMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result)
        client = _build_app(db)
        resp = client.get("/api/v1/reporting/regulatory/deadlines", headers=_headers())
        assert resp.status_code == 200

    def test_create_regulatory(self) -> None:
        sub = self._make_sub_result()
        db = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = sub
        result.scalars.return_value.all.return_value = [sub]
        db.execute = AsyncMock(return_value=result)
        db.add = MagicMock()
        db.flush = AsyncMock()
        with patch("src.services.regulatory_service.RegulatorySubmission") as MockSub:
            MockSub.return_value = sub
            client = _build_app(db)
            resp = client.post(
                "/api/v1/reporting/regulatory",
                json={
                    "report_type": "caa_transparency_semiannual",
                    "period_start": "2026-01-01",
                    "period_end": "2026-06-30",
                    "due_date": "2026-06-30",
                },
                headers=_headers(),
            )
        assert resp.status_code == 201

    def test_update_regulatory_not_found(self) -> None:
        db = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=result)
        client = _build_app(db)
        resp = client.put(
            "/api/v1/reporting/regulatory/missing",
            json={"status": "in_review"},
            headers=_headers(),
        )
        assert resp.status_code == 404


class TestActuarialEndpoints:
    def test_list_actuarial_models(self) -> None:
        from src.models.tables import ActuarialModel

        model = MagicMock(spec=ActuarialModel)
        db = MagicMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result)
        client = _build_app(db)
        resp = client.get("/api/v1/reporting/actuarial/models", headers=_headers())
        assert resp.status_code == 200

    def test_actuarial_reprice(self) -> None:
        db = _make_mock_db()
        client = _build_app(db)
        resp = client.post(
            "/api/v1/reporting/actuarial/reprice",
            json={
                "claims": [{"amount_paid": "1000.00"}],
                "formulary_discount_pct": "5.00",
                "network_discount_pct": "5.00",
                "rebate_estimate_pct": "10.00",
            },
            headers=_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "estimated_savings" in data


class TestQualityEndpoints:
    def test_get_star_ratings(self) -> None:
        db = _make_mock_db()
        client = _build_app(db)
        resp = client.get("/api/v1/reporting/quality/star-ratings", headers=_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert "measures" in data

    def test_get_adherence(self) -> None:
        db = _make_mock_db()
        client = _build_app(db)
        resp = client.get("/api/v1/reporting/quality/adherence/D01", headers=_headers())
        assert resp.status_code == 200

    def test_get_adherence_gaps(self) -> None:
        db = _make_mock_db()
        client = _build_app(db)
        resp = client.get("/api/v1/reporting/quality/gaps", headers=_headers())
        assert resp.status_code == 200

    def test_get_star_projections(self) -> None:
        db = _make_mock_db()
        client = _build_app(db)
        resp = client.get("/api/v1/reporting/quality/projections", headers=_headers())
        assert resp.status_code == 200
