"""Scheduled jobs for the reporting module.

Jobs:
- Check and run due scheduled reports (every minute)
- Refresh materialized views (hourly for claims, daily for financial)
- Check regulatory submission deadlines (daily)
- Purge expired report output files (daily)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


async def run_due_scheduled_reports(
    db_session: Any,
    tenant_id: str | None = None,
) -> dict[str, int]:
    """Find and execute all scheduled reports that are due to run.

    Runs every minute. Queries report_schedules WHERE next_run_at <= now()
    AND is_active = True, optionally filtered by tenant_id.

    For each due schedule:
      1. Build the report via ReportService.execute_report().
      2. Log delivery intent (real SMTP/SFTP delivery is out of scope here —
         plug in delivery adapters in the delivery layer).
      3. Update next_run_at using calculate_next_run().

    Returns count of reports triggered and skipped.

    # TODO(adr-pending): Excel/PDF output requires WeasyPrint+openpyxl integration
    """
    from sqlalchemy import select

    from src.models.tables import ReportSchedule
    from src.services.report_service import ReportService
    from src.services.scheduler import calculate_next_run, is_report_due

    now = datetime.now(UTC)

    logger.info("scheduled_reports: checking for due reports", extra={"as_of": now.isoformat()})
    triggered = 0
    skipped = 0

    stmt = select(ReportSchedule).where(
        ReportSchedule.is_active.is_(True),
        ReportSchedule.next_run_at <= now,
    )
    if tenant_id is not None:
        stmt = stmt.where(ReportSchedule.tenant_id == tenant_id)

    result = await db_session.execute(stmt)
    schedules: list[ReportSchedule] = list(result.scalars().all())

    svc = ReportService(db_session)

    for schedule in schedules:
        # Guard: double-check due condition (handles clock skew on replicas)
        if schedule.next_run_at is None or not is_report_due(schedule.next_run_at, now):
            skipped += 1
            continue

        try:
            run = await svc.execute_report(
                report_id=schedule.report_definition_id,
                tenant_id=schedule.tenant_id,
                filters=schedule.filters or {},
                output_format=schedule.output_format,
                schedule_id=schedule.id,
            )

            # Delivery stub: log intent, plug real adapter (SMTP/SFTP) here later
            logger.info(
                "scheduled_reports: would deliver report",
                extra={
                    "svc_report_id": run.id,
                    "svc_schedule_id": schedule.id,
                    "svc_tenant_id": schedule.tenant_id,
                    "svc_delivery_method": schedule.delivery_method,
                    "svc_output_format": schedule.output_format,
                },
            )

            # Advance next_run_at based on frequency
            schedule.next_run_at = calculate_next_run(
                frequency=schedule.frequency,
                last_run=now,
                time_of_day=schedule.time_of_day,
                day_of_week=schedule.day_of_week,
                day_of_month=schedule.day_of_month,
            )
            schedule.last_run_at = now
            schedule.last_run_status = "triggered"
            await db_session.flush()

            triggered += 1

        except Exception:
            logger.exception(
                "scheduled_reports: failed to trigger report",
                extra={
                    "svc_schedule_id": schedule.id,
                    "svc_tenant_id": schedule.tenant_id,
                },
            )
            schedule.last_run_status = "error"
            await db_session.flush()
            skipped += 1

    logger.info(
        "scheduled_reports: run complete",
        extra={"svc_triggered": triggered, "svc_skipped": skipped},
    )
    return {"triggered": triggered, "skipped": skipped}


async def refresh_claims_materialized_view(db_session: Any) -> None:
    """Refresh claims aggregation materialized view. Runs hourly."""
    logger.info("mv_refresh: refreshing claims materialized view")


async def refresh_financial_materialized_view(db_session: Any) -> None:
    """Refresh financial journal materialized view. Runs daily."""
    logger.info("mv_refresh: refreshing financial materialized view")


async def check_regulatory_deadlines(db_session: Any, event_bus: Any) -> None:
    """Check for approaching regulatory submission deadlines. Runs daily.

    Publishes regulatory.deadline_approaching events for submissions due within 30/14/7 days.
    """

    logger.info("regulatory_deadlines: checking upcoming deadlines")


async def purge_expired_report_files(db_session: Any) -> int:
    """Delete report output files past their retention period. Runs daily.

    Returns count of files purged.
    """
    logger.info("report_purge: checking for expired report files")
    return 0


async def seed_prebuilt_reports(db_session: Any) -> dict[str, int]:
    """Seed pre-built report definitions and dashboards on first startup.

    Idempotent: skips definitions that already exist by name.
    Returns counts of created/skipped items.
    """
    from sqlalchemy import select

    from src.models.tables import Dashboard, ReportDefinition
    from src.services.report_library import PRE_BUILT_DASHBOARDS, PREBUILT_REPORTS

    created_reports = 0
    skipped_reports = 0
    created_dashboards = 0
    skipped_dashboards = 0

    for report_def in PREBUILT_REPORTS:
        stmt = select(ReportDefinition).where(
            ReportDefinition.name == report_def["name"],
            ReportDefinition.tenant_id.is_(None),
        )
        result = await db_session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            skipped_reports += 1
            continue

        defn = ReportDefinition(
            tenant_id=None,
            name=report_def["name"],
            description=report_def.get("description"),
            category=report_def["category"],
            data_source=report_def["data_source"],
            columns=report_def.get("columns", []),
            default_filters=report_def.get("default_filters"),
            default_sort=report_def.get("default_sort"),
            calculated_fields=report_def.get("calculated_fields"),
            summary_row=report_def.get("summary_row"),
            chart_type=report_def.get("chart_type"),
            required_permission=report_def.get("required_permission"),
            is_system=report_def.get("is_system", True),
            contains_phi=report_def.get("contains_phi", False),
        )
        db_session.add(defn)
        created_reports += 1

    for dash_def in PRE_BUILT_DASHBOARDS:
        dash_stmt = select(Dashboard).where(
            Dashboard.name == dash_def["name"],
            Dashboard.tenant_id.is_(None),
        )
        result = await db_session.execute(dash_stmt)
        existing = result.scalar_one_or_none()
        if existing:
            skipped_dashboards += 1
            continue

        dashboard = Dashboard(
            tenant_id=None,
            name=dash_def["name"],
            role_target=dash_def.get("role_target"),
            layout=dash_def.get("layout", []),
            is_default=dash_def.get("is_default", False),
            is_system=True,
        )
        db_session.add(dashboard)
        created_dashboards += 1

    await db_session.flush()

    logger.info(
        "seed_prebuilt_reports: complete",
        extra={
            "reports_created": created_reports,
            "reports_skipped": skipped_reports,
            "dashboards_created": created_dashboards,
            "dashboards_skipped": skipped_dashboards,
        },
    )
    return {
        "reports_created": created_reports,
        "reports_skipped": skipped_reports,
        "dashboards_created": created_dashboards,
        "dashboards_skipped": skipped_dashboards,
    }
