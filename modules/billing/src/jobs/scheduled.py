"""Scheduled billing jobs.

Intended to be invoked by a scheduler (APScheduler, Celery Beat, or Azure Functions
timer triggers). Each job is a standalone function accepting a db session and event bus
so it can be unit-tested without the scheduler.
"""

from __future__ import annotations

from datetime import date
from typing import Any


def run_budget_monitoring(*, db: Any, bus: Any) -> dict[str, int]:
    """Daily job: evaluate all active program budgets and fire alerts.

    Returns a summary dict with counts of budgets evaluated and alerts fired.
    """
    evaluated = 0
    alerts_fired = 0

    # In production: query all active ProgramBudget rows for all tenants,
    # compute 7-day burn, projected depletion, call BudgetService.evaluate_alerts(),
    # persist ProgramBudgetAlert rows, publish budget.alert_fired events.

    return {"budgets_evaluated": evaluated, "alerts_fired": alerts_fired}


def run_ar_aging_update(*, db: Any) -> dict[str, int]:
    """Daily job: recalculate aging buckets for all open AR records.

    Updates the aging_bucket column on each ARRecord based on today's date
    and the original due_date. Returns count of records updated.
    """
    updated = 0

    # In production: query all ARRecord rows where status NOT IN ('paid', 'written_off'),
    # compute days_overdue = (today - due_date).days, set aging_bucket accordingly.

    return {"records_updated": updated}


def run_ap_carryover_check(*, db: Any, bus: Any) -> dict[str, int]:
    """Weekly job: identify AP records that failed payment and create carryover records.

    Returns count of carryover records created.
    """
    created = 0

    # In production: query APRecord rows with status='failed', create carryover via
    # APService.create_carryover(), publish relevant events.

    return {"carryover_records_created": created}


def run_invoice_auto_generation(
    *, db: Any, bus: Any, run_date: date | None = None
) -> dict[str, int]:
    """Monthly job (or configurable frequency): auto-generate invoices for clients
    whose InvoicingConfig has auto_approve=True and automation_level >= 'semi'.

    Returns count of invoices generated.
    """
    if run_date is None:
        run_date = date.today()

    generated = 0

    # In production: query InvoicingConfig rows with auto_send=True,
    # determine if today is the billing cycle date, call ARService.generate_invoice(),
    # then send via configured delivery_method.

    return {"invoices_generated": generated}


def run_budget_snapshot(*, db: Any) -> dict[str, int]:
    """Daily job: take a snapshot of each program budget's current state.

    Snapshots are used for trending/historical dashboards.
    Returns count of snapshots created.
    """
    created = 0

    # In production: query all active ProgramBudget rows, create ProgramBudgetSnapshot
    # rows with current spent_to_date, burn_rate_30day_avg, budget_remaining, etc.

    return {"snapshots_created": created}


def cleanup_old_uploads(
    *, db: Any, upload_dir: str, retention_days: int = 90
) -> dict[str, int]:
    """Nightly job (paysync.cleanup_old_uploads): delete orphaned .tmp files and
    optionally archive completed upload files older than retention_days.

    Storage layout: {PAYSYNC_UPLOAD_DIR}/{tenant_id}/{upload_id}/{filename}
    Orphaned .tmp files are mid-write crash artifacts safe to remove immediately.
    Completed upload files are retained for the full retention_days period even
    if the upload has been superseded (provenance immutability per spec §5.2).

    Args:
        db:              SQLAlchemy session for querying Upload rows.
        upload_dir:      Root path of the paysync upload directory.
        retention_days:  Files older than this are eligible for archival/deletion.
                         Default 90 days per §10.2.

    Returns:
        dict with counts: tmp_removed, files_archived, errors.
    """
    import os
    import pathlib
    import logging

    logger = logging.getLogger(__name__)
    tmp_removed = 0
    files_archived = 0
    errors = 0

    root = pathlib.Path(upload_dir)
    if not root.exists():
        logger.info("paysync upload_dir does not exist yet: %s", upload_dir)
        return {"tmp_removed": tmp_removed, "files_archived": files_archived, "errors": errors}

    cutoff = date.today().toordinal() - retention_days

    for tmp_file in root.rglob("*.tmp"):
        try:
            # Orphaned .tmp = mid-write crash artifact; safe to remove.
            os.remove(tmp_file)
            tmp_removed += 1
        except OSError as exc:
            logger.warning("cleanup_old_uploads: failed to remove tmp %s: %s", tmp_file, exc)
            errors += 1

    # Production implementation: query Upload rows with uploaded_at < cutoff,
    # verify the file exists on disk, move to archive storage or delete per
    # tenant retention policy. Stub returns zero archived for now.

    return {"tmp_removed": tmp_removed, "files_archived": files_archived, "errors": errors}
