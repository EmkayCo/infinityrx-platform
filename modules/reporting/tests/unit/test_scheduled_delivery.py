"""Unit tests for scheduled report delivery and alert-triggered reports."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone

import pytest
from src.services.scheduler import (
    build_delivery_payload,
    calculate_next_run,
    deduplicate_alert_report,
    is_report_due,
    validate_schedule_config,
)


class TestCalculateNextRun:
    def test_daily_next_run(self) -> None:
        last_run = datetime(2026, 1, 15, 6, 0, 0, tzinfo=timezone.utc)
        next_run = calculate_next_run("daily", last_run, time_of_day=time(6, 0))
        assert next_run.date() == date(2026, 1, 16)
        assert next_run.hour == 6
        assert next_run.minute == 0

    def test_weekly_next_run(self) -> None:
        # Last run on Monday (weekday=0), next should be next Monday
        last_run = datetime(2026, 1, 5, 6, 0, 0, tzinfo=timezone.utc)  # Monday
        next_run = calculate_next_run("weekly", last_run, time_of_day=time(6, 0), day_of_week=0)
        assert next_run.date() == date(2026, 1, 12)

    def test_monthly_next_run(self) -> None:
        last_run = datetime(2026, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
        next_run = calculate_next_run("monthly", last_run, time_of_day=time(6, 0), day_of_month=1)
        assert next_run.date() == date(2026, 2, 1)

    def test_quarterly_next_run(self) -> None:
        last_run = datetime(2026, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
        next_run = calculate_next_run("quarterly", last_run, time_of_day=time(6, 0))
        assert next_run.month == 4

    def test_annually_next_run(self) -> None:
        last_run = datetime(2026, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
        next_run = calculate_next_run("annually", last_run, time_of_day=time(6, 0))
        assert next_run.year == 2027

    def test_invalid_frequency_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid frequency"):
            calculate_next_run("invalid", datetime.now(timezone.utc))

    def test_next_run_is_timezone_aware(self) -> None:
        last_run = datetime(2026, 1, 1, tzinfo=timezone.utc)
        next_run = calculate_next_run("daily", last_run)
        assert next_run.tzinfo is not None


class TestIsReportDue:
    def test_due_report_returns_true(self) -> None:
        next_run = datetime(2026, 1, 15, 5, 0, tzinfo=timezone.utc)
        now = datetime(2026, 1, 15, 6, 30, tzinfo=timezone.utc)
        assert is_report_due(next_run, now) is True

    def test_future_report_returns_false(self) -> None:
        next_run = datetime(2026, 1, 16, 6, 0, tzinfo=timezone.utc)
        now = datetime(2026, 1, 15, 6, 30, tzinfo=timezone.utc)
        assert is_report_due(next_run, now) is False

    def test_exact_time_is_due(self) -> None:
        t = datetime(2026, 1, 15, 6, 0, tzinfo=timezone.utc)
        assert is_report_due(t, t) is True


class TestBuildDeliveryPayload:
    def test_email_payload_has_recipients(self) -> None:
        payload = build_delivery_payload(
            delivery_method="email",
            recipients={"emails": ["a@example.com", "b@example.com"]},
            report_run_id=str(uuid.uuid4()),
            output_format="excel",
        )
        assert payload["delivery_method"] == "email"
        assert "recipients" in payload
        assert len(payload["recipients"]["emails"]) == 2

    def test_sftp_payload_has_path(self) -> None:
        payload = build_delivery_payload(
            delivery_method="sftp",
            recipients={"sftp_path": "/reports/monthly/"},
            report_run_id=str(uuid.uuid4()),
            output_format="csv",
        )
        assert payload["delivery_method"] == "sftp"
        assert payload["recipients"]["sftp_path"] == "/reports/monthly/"

    def test_webhook_payload_has_url(self) -> None:
        payload = build_delivery_payload(
            delivery_method="api_webhook",
            recipients={"webhook_url": "https://example.com/hook"},
            report_run_id=str(uuid.uuid4()),
            output_format="api",
        )
        assert "webhook_url" in payload["recipients"]

    def test_invalid_delivery_method_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid delivery_method"):
            build_delivery_payload(
                delivery_method="carrier_pigeon",
                recipients={},
                report_run_id="r1",
                output_format="csv",
            )

    def test_payload_includes_run_id(self) -> None:
        run_id = str(uuid.uuid4())
        payload = build_delivery_payload(
            delivery_method="portal",
            recipients={},
            report_run_id=run_id,
            output_format="pdf",
        )
        assert payload["report_run_id"] == run_id


class TestValidateScheduleConfig:
    def test_valid_daily_schedule(self) -> None:
        config = {
            "frequency": "daily",
            "time_of_day": "06:00",
            "output_format": "excel",
            "delivery_method": "email",
        }
        errors = validate_schedule_config(config)
        assert errors == []

    def test_weekly_requires_day_of_week(self) -> None:
        config = {
            "frequency": "weekly",
            "time_of_day": "06:00",
            "output_format": "excel",
            "delivery_method": "email",
        }
        errors = validate_schedule_config(config)
        assert any("day_of_week" in e for e in errors)

    def test_monthly_requires_day_of_month(self) -> None:
        config = {
            "frequency": "monthly",
            "time_of_day": "06:00",
            "output_format": "excel",
            "delivery_method": "email",
        }
        errors = validate_schedule_config(config)
        assert any("day_of_month" in e for e in errors)

    def test_invalid_frequency_fails(self) -> None:
        config = {
            "frequency": "invalid",
            "time_of_day": "06:00",
            "output_format": "excel",
            "delivery_method": "email",
        }
        errors = validate_schedule_config(config)
        assert any("frequency" in e for e in errors)

    def test_invalid_output_format_fails(self) -> None:
        config = {
            "frequency": "daily",
            "time_of_day": "06:00",
            "output_format": "docx",
            "delivery_method": "email",
        }
        errors = validate_schedule_config(config)
        assert any("output_format" in e for e in errors)

    def test_invalid_delivery_method_fails(self) -> None:
        config = {
            "frequency": "daily",
            "time_of_day": "06:00",
            "output_format": "excel",
            "delivery_method": "fax",
        }
        errors = validate_schedule_config(config)
        assert any("delivery_method" in e for e in errors)


class TestDeduplicateAlertReport:
    def test_first_send_allowed(self) -> None:
        sent_log: list[datetime] = []
        window_hours = 24
        now = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
        result = deduplicate_alert_report(sent_log, window_hours, now)
        assert result is True  # allowed

    def test_second_send_within_window_blocked(self) -> None:
        now = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
        last_sent = datetime(2026, 1, 15, 5, 0, tzinfo=timezone.utc)  # 5 hours ago
        sent_log = [last_sent]
        window_hours = 24
        result = deduplicate_alert_report(sent_log, window_hours, now)
        assert result is False  # blocked

    def test_send_after_window_allowed(self) -> None:
        now = datetime(2026, 1, 16, 11, 0, tzinfo=timezone.utc)
        last_sent = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)  # 25 hours ago
        sent_log = [last_sent]
        window_hours = 24
        result = deduplicate_alert_report(sent_log, window_hours, now)
        assert result is True  # allowed
