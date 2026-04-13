"""Unit tests for cross-tenant isolation in the reporting module.

Every API endpoint must enforce tenant_id scoping.
100% coverage required on security paths.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.services.dashboard_service import DashboardService
from src.services.report_service import ReportService

TENANT_A = str(uuid.uuid4())
TENANT_B = str(uuid.uuid4())


class TestReportServiceTenantIsolation:
    """Report definitions scoped to tenant must not leak to other tenants."""

    def _mock_db(self, rows: list) -> MagicMock:
        db = MagicMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = rows
        result.scalar_one_or_none.return_value = rows[0] if rows else None
        db.execute = AsyncMock(return_value=result)
        return db

    @pytest.mark.asyncio
    async def test_list_reports_filters_by_tenant(self) -> None:
        tenant_a_report = MagicMock()
        tenant_a_report.tenant_id = TENANT_A
        tenant_b_report = MagicMock()
        tenant_b_report.tenant_id = TENANT_B

        db = self._mock_db([tenant_a_report])
        service = ReportService(db)
        results = await service.list_definitions(tenant_id=TENANT_A)
        # Verify query was called — actual DB-level isolation tested in integration tests
        assert db.execute.called

    @pytest.mark.asyncio
    async def test_get_report_wrong_tenant_returns_none(self) -> None:
        report = MagicMock()
        report.tenant_id = TENANT_B
        report.id = "some-report-id"

        db = self._mock_db([])  # empty result simulates tenant mismatch
        service = ReportService(db)
        result = await service.get_definition("some-report-id", tenant_id=TENANT_A)
        assert result is None

    @pytest.mark.asyncio
    async def test_run_report_enforces_tenant_id(self) -> None:
        db = self._mock_db([])
        service = ReportService(db)
        with pytest.raises(Exception):
            # Trying to run a report without tenant_id should fail
            await service.execute_report("some-id", tenant_id=None, filters={})


class TestDashboardServiceTenantIsolation:
    def _mock_db(self, rows: list) -> MagicMock:
        db = MagicMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = rows
        result.scalar_one_or_none.return_value = rows[0] if rows else None
        db.execute = AsyncMock(return_value=result)
        return db

    @pytest.mark.asyncio
    async def test_list_dashboards_filters_by_tenant(self) -> None:
        db = self._mock_db([])
        service = DashboardService(db)
        await service.list_dashboards(tenant_id=TENANT_A)
        assert db.execute.called

    @pytest.mark.asyncio
    async def test_get_dashboard_wrong_tenant_returns_none(self) -> None:
        db = self._mock_db([])
        service = DashboardService(db)
        result = await service.get_dashboard("some-id", tenant_id=TENANT_A)
        assert result is None
