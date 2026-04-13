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
