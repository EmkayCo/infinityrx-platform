"""Report definition CRUD and execution service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import ReportDefinition, ReportRun
from src.services.report_engine import validate_report_definition
from src.utils.constants import STATUS_COMPLETED, STATUS_FAILED, STATUS_RUNNING


class ReportService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_definitions(
        self,
        tenant_id: str,
        category: str | None = None,
        is_active: bool = True,
    ) -> list[ReportDefinition]:
        """List report definitions available to a tenant (tenant-scoped + system)."""
        stmt = (
            select(ReportDefinition)
            .where(
                ReportDefinition.is_active == is_active,
            )
            .where(
                (ReportDefinition.tenant_id == tenant_id) | (ReportDefinition.tenant_id.is_(None))
            )
        )
        if category:
            stmt = stmt.where(ReportDefinition.category == category)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_definition(self, report_id: str, tenant_id: str) -> ReportDefinition | None:
        """Get a report definition, enforcing tenant isolation."""
        stmt = (
            select(ReportDefinition)
            .where(
                ReportDefinition.id == report_id,
            )
            .where(
                (ReportDefinition.tenant_id == tenant_id) | (ReportDefinition.tenant_id.is_(None))
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_definition(
        self,
        tenant_id: str,
        data: dict[str, Any],
    ) -> ReportDefinition:
        """Create a custom report definition for a tenant."""
        errors = validate_report_definition(data)
        if errors:
            raise ValueError(f"Invalid report definition: {errors}")

        defn = ReportDefinition(
            tenant_id=tenant_id,
            name=data["name"],
            description=data.get("description"),
            category=data["category"],
            data_source=data["data_source"],
            base_query=data.get("base_query"),
            columns=data["columns"],
            default_filters=data.get("default_filters"),
            default_groupings=data.get("default_groupings"),
            default_sort=data.get("default_sort"),
            calculated_fields=data.get("calculated_fields"),
            summary_row=data.get("summary_row"),
            chart_type=data.get("chart_type"),
            chart_config=data.get("chart_config"),
            required_permission=data.get("required_permission"),
            contains_phi=data.get("contains_phi", False),
        )
        self._db.add(defn)
        await self._db.flush()
        return defn

    async def execute_report(
        self,
        report_id: str,
        tenant_id: str | None,
        filters: dict[str, Any],
        requested_by: str | None = None,
        output_format: str = "excel",
        schedule_id: str | None = None,
    ) -> ReportRun:
        """Create a report run record and initiate execution."""
        if tenant_id is None:
            raise ValueError("tenant_id is required for report execution")

        defn = await self.get_definition(report_id, tenant_id)
        if defn is None:
            raise ValueError(f"Report {report_id} not found for tenant {tenant_id}")

        run = ReportRun(
            tenant_id=tenant_id,
            report_definition_id=report_id,
            schedule_id=schedule_id,
            status=STATUS_RUNNING,
            filters_applied=filters,
            requested_by=requested_by,
            output_format=output_format,
            phi_accessed=defn.contains_phi,
        )
        self._db.add(run)
        await self._db.flush()
        return run

    async def complete_run(
        self,
        run: ReportRun,
        row_count: int,
        output_file_id: str | None = None,
        error_message: str | None = None,
    ) -> ReportRun:
        """Mark a run as completed or failed."""
        now = datetime.now(UTC)
        run.completed_at = now
        if run.started_at:
            run.duration_seconds = int((now - run.started_at).total_seconds())

        if error_message:
            run.status = STATUS_FAILED
            run.error_message = error_message
        else:
            run.status = STATUS_COMPLETED
            run.row_count = row_count
            run.output_file_id = output_file_id

        await self._db.flush()
        return run

    async def list_runs(self, tenant_id: str, report_id: str | None = None) -> list[ReportRun]:
        """List report runs for a tenant."""
        stmt = select(ReportRun).where(ReportRun.tenant_id == tenant_id)
        if report_id:
            stmt = stmt.where(ReportRun.report_definition_id == report_id)
        stmt = stmt.order_by(ReportRun.started_at.desc())
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_run(self, run_id: str, tenant_id: str) -> ReportRun | None:
        """Get a specific run, tenant-scoped."""
        stmt = select(ReportRun).where(
            ReportRun.id == run_id,
            ReportRun.tenant_id == tenant_id,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()
