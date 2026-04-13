"""Scheduled report delivery and alert-triggered report logic."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from src.utils.constants import ALL_DELIVERY_METHODS, ALL_FORMATS, ALL_FREQUENCIES


def calculate_next_run(
    frequency: str,
    last_run: datetime,
    time_of_day: time | None = None,
    day_of_week: int | None = None,
    day_of_month: int | None = None,
) -> datetime:
    """Calculate the next scheduled run datetime for a given frequency."""
    if frequency not in ALL_FREQUENCIES:
        raise ValueError(f"Invalid frequency: {frequency!r}. Must be one of {ALL_FREQUENCIES}")

    run_time = time_of_day or time(6, 0)
    tz = last_run.tzinfo or UTC

    if frequency == "daily":
        next_date = last_run.date() + timedelta(days=1)
        return datetime.combine(next_date, run_time, tzinfo=tz)

    if frequency == "weekly":
        target_dow = day_of_week if day_of_week is not None else last_run.weekday()
        days_ahead = (target_dow - last_run.weekday() - 1) % 7 + 1
        next_date = last_run.date() + timedelta(days=days_ahead)
        return datetime.combine(next_date, run_time, tzinfo=tz)

    if frequency == "biweekly":
        next_date = last_run.date() + timedelta(weeks=2)
        return datetime.combine(next_date, run_time, tzinfo=tz)

    if frequency == "monthly":
        dom = day_of_month or last_run.day
        year = last_run.year
        month = last_run.month + 1
        if month > 12:
            month = 1
            year += 1
        import calendar

        dom_clamped = min(dom, calendar.monthrange(year, month)[1])
        next_date = date(year, month, dom_clamped)
        return datetime.combine(next_date, run_time, tzinfo=tz)

    if frequency == "quarterly":
        month = last_run.month + 3
        year = last_run.year
        if month > 12:
            month -= 12
            year += 1
        import calendar

        dom = min(last_run.day, calendar.monthrange(year, month)[1])
        next_date = date(year, month, dom)
        return datetime.combine(next_date, run_time, tzinfo=tz)

    if frequency == "annually":
        import calendar

        year = last_run.year + 1
        month = last_run.month
        dom = min(last_run.day, calendar.monthrange(year, month)[1])
        next_date = date(year, month, dom)
        return datetime.combine(next_date, run_time, tzinfo=tz)

    # on_demand: never auto-scheduled
    next_date = last_run.date() + timedelta(days=9999)
    return datetime.combine(next_date, run_time, tzinfo=tz)


def is_report_due(next_run: datetime, now: datetime) -> bool:
    """Return True if the scheduled run time has arrived."""
    return now >= next_run


def build_delivery_payload(
    delivery_method: str,
    recipients: dict[str, Any],
    report_run_id: str,
    output_format: str,
) -> dict[str, Any]:
    """Build the delivery task payload for a report."""
    if delivery_method not in ALL_DELIVERY_METHODS:
        raise ValueError(f"Invalid delivery_method: {delivery_method!r}")

    return {
        "delivery_method": delivery_method,
        "recipients": recipients,
        "report_run_id": report_run_id,
        "output_format": output_format,
    }


def validate_schedule_config(config: dict[str, Any]) -> list[str]:
    """Validate a report schedule configuration; return list of error strings."""
    errors: list[str] = []

    frequency = config.get("frequency")
    if not frequency or frequency not in ALL_FREQUENCIES:
        errors.append(f"frequency: must be one of {ALL_FREQUENCIES}")

    if frequency == "weekly" and config.get("day_of_week") is None:
        errors.append("day_of_week: required for weekly frequency")

    if frequency == "monthly" and config.get("day_of_month") is None:
        errors.append("day_of_month: required for monthly frequency")

    output_format = config.get("output_format")
    if not output_format or output_format not in ALL_FORMATS:
        errors.append(f"output_format: must be one of {ALL_FORMATS}")

    delivery_method = config.get("delivery_method")
    if not delivery_method or delivery_method not in ALL_DELIVERY_METHODS:
        errors.append(f"delivery_method: must be one of {ALL_DELIVERY_METHODS}")

    return errors


def deduplicate_alert_report(
    sent_log: list[datetime],
    window_hours: int,
    now: datetime,
) -> bool:
    """Return True if sending is allowed (not a duplicate within window)."""
    if not sent_log:
        return True

    most_recent = max(sent_log)
    elapsed = now - most_recent
    return elapsed.total_seconds() > window_hours * 3600
