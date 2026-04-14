"""Session 4 — cert lifecycle and SLA monitoring tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from src.services.cert_lifecycle import (
    CertRecord,
    CertStatus,
    CertUsage,
    build_cert_alerts,
    compute_days_until_expiry,
    evaluate_cert_status,
    generate_lifecycle_report,
    parse_cert_metadata,
    renew_cert,
    revoke_cert,
)
from src.services.sla_monitoring import (
    SlaConfig,
    SlaStatus,
    SubmissionEvent,
    TransactionDirection,
    build_partner_sla_report,
    compute_elapsed_minutes,
    detect_breaches,
    evaluate_submission_status,
    record_acknowledgment,
    summarize_sla_dashboard,
)

_NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Cert lifecycle helpers
# ---------------------------------------------------------------------------

def _make_cert(
    days_until_expiry: int = 90,
    status: CertStatus = CertStatus.ACTIVE,
    usage: CertUsage = CertUsage.AS2_SIGNING,
    cert_id: str = "CERT001",
) -> CertRecord:
    not_before = _NOW - timedelta(days=10)
    not_after = _NOW + timedelta(days=days_until_expiry)
    return CertRecord(
        cert_id=cert_id,
        trading_partner_id="TP001",
        subject="CN=partner.example.com",
        issuer="CN=MyCA",
        serial_number="0123456789",
        not_before=not_before,
        not_after=not_after,
        usage=usage,
        status=status,
    )


# ---------------------------------------------------------------------------
# evaluate_cert_status
# ---------------------------------------------------------------------------

class TestEvaluateCertStatus:
    def test_active_cert(self):
        cert = _make_cert(days_until_expiry=90)
        assert evaluate_cert_status(cert, now=_NOW) == CertStatus.ACTIVE

    def test_expiring_soon_at_warn_boundary(self):
        cert = _make_cert(days_until_expiry=29)
        assert evaluate_cert_status(cert, now=_NOW, warn_days=30) == CertStatus.EXPIRING_SOON

    def test_expiring_soon_at_warn_days(self):
        cert = _make_cert(days_until_expiry=30)
        assert evaluate_cert_status(cert, now=_NOW, warn_days=30) == CertStatus.EXPIRING_SOON

    def test_expired(self):
        cert = _make_cert(days_until_expiry=-1)
        assert evaluate_cert_status(cert, now=_NOW) == CertStatus.EXPIRED

    def test_revoked_status_preserved(self):
        cert = _make_cert(days_until_expiry=90, status=CertStatus.REVOKED)
        assert evaluate_cert_status(cert, now=_NOW) == CertStatus.REVOKED

    def test_pending_before_not_before(self):
        cert = _make_cert(days_until_expiry=90)
        cert.not_before = _NOW + timedelta(days=5)
        assert evaluate_cert_status(cert, now=_NOW) == CertStatus.PENDING

    def test_default_now(self):
        cert = _make_cert(days_until_expiry=365)
        # Should not raise
        result = evaluate_cert_status(cert)
        assert result in CertStatus.__members__.values()


class TestComputeDaysUntilExpiry:
    def test_future_cert(self):
        cert = _make_cert(days_until_expiry=45)
        days = compute_days_until_expiry(cert, now=_NOW)
        assert days == 45

    def test_expired_cert_negative(self):
        cert = _make_cert(days_until_expiry=-5)
        days = compute_days_until_expiry(cert, now=_NOW)
        assert days == -5

    def test_default_now(self):
        cert = _make_cert(days_until_expiry=10)
        days = compute_days_until_expiry(cert)
        assert isinstance(days, int)


class TestBuildCertAlerts:
    def test_expiring_cert_generates_alert(self):
        cert = _make_cert(days_until_expiry=15, cert_id="C1")
        alerts = build_cert_alerts([cert], now=_NOW, warn_days=30)
        assert len(alerts) == 1
        assert alerts[0].cert_id == "C1"

    def test_active_cert_no_alert(self):
        cert = _make_cert(days_until_expiry=90)
        alerts = build_cert_alerts([cert], now=_NOW, warn_days=30)
        assert len(alerts) == 0

    def test_critical_level_under_critical_days(self):
        cert = _make_cert(days_until_expiry=5)
        alerts = build_cert_alerts([cert], now=_NOW, warn_days=30, critical_days=7)
        assert alerts[0].alert_level == "critical"

    def test_warning_level_above_critical_days(self):
        cert = _make_cert(days_until_expiry=20)
        alerts = build_cert_alerts([cert], now=_NOW, warn_days=30, critical_days=7)
        assert alerts[0].alert_level == "warning"

    def test_revoked_cert_no_alert(self):
        cert = _make_cert(days_until_expiry=5, status=CertStatus.REVOKED)
        alerts = build_cert_alerts([cert], now=_NOW, warn_days=30)
        assert len(alerts) == 0

    def test_sorted_by_days_ascending(self):
        c1 = _make_cert(days_until_expiry=25, cert_id="C1")
        c2 = _make_cert(days_until_expiry=10, cert_id="C2")
        alerts = build_cert_alerts([c1, c2], now=_NOW, warn_days=30)
        assert alerts[0].cert_id == "C2"
        assert alerts[1].cert_id == "C1"

    def test_expired_cert_generates_alert(self):
        cert = _make_cert(days_until_expiry=-3)
        alerts = build_cert_alerts([cert], now=_NOW, warn_days=30)
        assert len(alerts) == 1
        assert alerts[0].days_until_expiry == -3

    def test_default_now(self):
        cert = _make_cert(days_until_expiry=10)
        alerts = build_cert_alerts([cert])
        assert len(alerts) >= 0


class TestGenerateLifecycleReport:
    def test_counts_correct(self):
        certs = [
            _make_cert(days_until_expiry=90, cert_id="C1"),
            _make_cert(days_until_expiry=15, cert_id="C2"),
            _make_cert(days_until_expiry=-1, cert_id="C3"),
            _make_cert(days_until_expiry=90, status=CertStatus.REVOKED, cert_id="C4"),
        ]
        report = generate_lifecycle_report(certs, now=_NOW, warn_days=30)
        assert report.total_certs == 4
        assert report.active_count == 1
        assert report.expiring_soon_count == 1
        assert report.expired_count == 1
        assert report.revoked_count == 1

    def test_alerts_in_report(self):
        certs = [_make_cert(days_until_expiry=5, cert_id="C1")]
        report = generate_lifecycle_report(certs, now=_NOW, warn_days=30)
        assert len(report.alerts) == 1

    def test_generated_at_timestamp(self):
        report = generate_lifecycle_report([], now=_NOW)
        assert report.generated_at == "20260115T120000Z"

    def test_default_now(self):
        report = generate_lifecycle_report([])
        assert report.total_certs == 0


class TestRevokeCert:
    def test_status_set_to_revoked(self):
        cert = _make_cert()
        revoke_cert(cert, reason="compromised key")
        assert cert.status == CertStatus.REVOKED

    def test_notes_set_when_reason_provided(self):
        cert = _make_cert()
        revoke_cert(cert, reason="expired")
        assert "REVOKED" in cert.notes

    def test_no_notes_when_no_reason(self):
        cert = _make_cert()
        original_notes = cert.notes
        revoke_cert(cert, reason="")
        assert cert.notes == original_notes


class TestRenewCert:
    def test_new_cert_record(self):
        old = _make_cert()
        new_before = _NOW + timedelta(days=1)
        new_after = _NOW + timedelta(days=366)
        new_cert = renew_cert(old, "CERT_NEW", new_before, new_after, new_fingerprint="abc")
        assert new_cert.cert_id == "CERT_NEW"
        assert new_cert.not_before == new_before
        assert new_cert.not_after == new_after
        assert new_cert.status == CertStatus.PENDING

    def test_old_cert_linked_to_new(self):
        old = _make_cert()
        renew_cert(old, "NEW_ID", _NOW, _NOW + timedelta(days=365))
        assert old.renewed_by_cert_id == "NEW_ID"

    def test_trading_partner_preserved(self):
        old = _make_cert()
        new_cert = renew_cert(old, "NEW", _NOW, _NOW + timedelta(days=365))
        assert new_cert.trading_partner_id == old.trading_partner_id

    def test_usage_preserved(self):
        old = _make_cert(usage=CertUsage.AS2_ENCRYPTION)
        new_cert = renew_cert(old, "NEW", _NOW, _NOW + timedelta(days=365))
        assert new_cert.usage == CertUsage.AS2_ENCRYPTION


class TestParseCertMetadata:
    def test_basic_parse(self):
        data = {
            "cert_id": "C1",
            "trading_partner_id": "TP1",
            "subject": "CN=example.com",
            "issuer": "CN=CA",
            "serial_number": "123",
            "not_before": "2025-01-01T00:00:00",
            "not_after": "2026-01-01T00:00:00",
            "usage": "as2_signing",
        }
        cert = parse_cert_metadata(data)
        assert cert.cert_id == "C1"
        assert cert.usage == CertUsage.AS2_SIGNING

    def test_datetime_objects_accepted(self):
        data = {
            "cert_id": "C2",
            "trading_partner_id": "TP2",
            "subject": "CN=x",
            "issuer": "CN=ca",
            "serial_number": "1",
            "not_before": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "not_after": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "usage": "as2_encryption",
        }
        cert = parse_cert_metadata(data)
        assert cert.usage == CertUsage.AS2_ENCRYPTION

    def test_unknown_usage_defaults_to_as2_signing(self):
        data = {
            "not_before": "2025-01-01T00:00:00",
            "not_after": "2026-01-01T00:00:00",
            "usage": "unknown_usage",
        }
        cert = parse_cert_metadata(data)
        assert cert.usage == CertUsage.AS2_SIGNING

    def test_naive_datetime_gets_utc(self):
        data = {
            "not_before": datetime(2025, 1, 1),
            "not_after": datetime(2026, 1, 1),
        }
        cert = parse_cert_metadata(data)
        assert cert.not_before.tzinfo is not None

    def test_fingerprint_set(self):
        data = {
            "not_before": "2025-01-01T00:00:00",
            "not_after": "2026-01-01T00:00:00",
            "fingerprint_sha256": "DEADBEEF",
        }
        cert = parse_cert_metadata(data)
        assert cert.fingerprint_sha256 == "DEADBEEF"


# ---------------------------------------------------------------------------
# SLA monitoring
# ---------------------------------------------------------------------------

def _make_event(
    submission_id: str = "SUB001",
    tp_id: str = "TP001",
    tx_type: str = "837",
    submitted_minutes_ago: int = 30,
    acknowledged_minutes_after: int = None,
    responded_minutes_after: int = None,
) -> SubmissionEvent:
    submitted_at = _NOW - timedelta(minutes=submitted_minutes_ago)
    ack_at = None
    if acknowledged_minutes_after is not None:
        ack_at = submitted_at + timedelta(minutes=acknowledged_minutes_after)
    resp_at = None
    if responded_minutes_after is not None:
        resp_at = submitted_at + timedelta(minutes=responded_minutes_after)
    return SubmissionEvent(
        submission_id=submission_id,
        trading_partner_id=tp_id,
        transaction_type=tx_type,
        direction=TransactionDirection.OUTBOUND,
        submitted_at=submitted_at,
        acknowledged_at=ack_at,
        responded_at=resp_at,
    )


_DEFAULT_SLA = SlaConfig(trading_partner_id="TP001", acknowledgment_sla_minutes=60, response_sla_minutes=1440)


class TestComputeElapsedMinutes:
    def test_zero_elapsed(self):
        assert compute_elapsed_minutes(_NOW, _NOW) == 0.0

    def test_sixty_minutes(self):
        end = _NOW + timedelta(minutes=60)
        assert compute_elapsed_minutes(_NOW, end) == 60.0

    def test_fractional(self):
        end = _NOW + timedelta(seconds=90)
        assert compute_elapsed_minutes(_NOW, end) == 1.5


class TestEvaluateSubmissionStatus:
    def test_within_sla(self):
        event = _make_event(submitted_minutes_ago=30)
        status = evaluate_submission_status(event, _DEFAULT_SLA, now=_NOW)
        assert status == SlaStatus.WITHIN_SLA

    def test_at_risk_above_75pct(self):
        event = _make_event(submitted_minutes_ago=50)  # 50/60 = 83%
        status = evaluate_submission_status(event, _DEFAULT_SLA, now=_NOW)
        assert status == SlaStatus.AT_RISK

    def test_breached(self):
        event = _make_event(submitted_minutes_ago=90)  # 90 > 60
        status = evaluate_submission_status(event, _DEFAULT_SLA, now=_NOW)
        assert status == SlaStatus.BREACHED

    def test_acknowledged_within_sla(self):
        event = _make_event(submitted_minutes_ago=90, acknowledged_minutes_after=30)
        status = evaluate_submission_status(event, _DEFAULT_SLA, now=_NOW)
        assert status == SlaStatus.ACKNOWLEDGED

    def test_acknowledged_but_late(self):
        event = _make_event(submitted_minutes_ago=90, acknowledged_minutes_after=90)
        status = evaluate_submission_status(event, _DEFAULT_SLA, now=_NOW)
        assert status == SlaStatus.BREACHED

    def test_default_now(self):
        event = SubmissionEvent(
            submission_id="X",
            trading_partner_id="TP001",
            transaction_type="837",
            direction=TransactionDirection.OUTBOUND,
            submitted_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        status = evaluate_submission_status(event, _DEFAULT_SLA)
        assert status in SlaStatus.__members__.values()


class TestDetectBreaches:
    def test_no_breach_within_sla(self):
        events = [_make_event(submitted_minutes_ago=30)]
        configs = {"TP001": _DEFAULT_SLA}
        breaches = detect_breaches(events, configs, now=_NOW)
        assert breaches == []

    def test_breach_detected(self):
        events = [_make_event(submitted_minutes_ago=90)]
        configs = {"TP001": _DEFAULT_SLA}
        breaches = detect_breaches(events, configs, now=_NOW)
        assert len(breaches) == 1
        assert breaches[0].sla_type == "acknowledgment"

    def test_acknowledged_not_breached(self):
        events = [_make_event(submitted_minutes_ago=90, acknowledged_minutes_after=30)]
        configs = {"TP001": _DEFAULT_SLA}
        breaches = detect_breaches(events, configs, now=_NOW)
        assert breaches == []

    def test_default_config_used_for_unknown_partner(self):
        events = [_make_event(tp_id="UNKNOWN_TP", submitted_minutes_ago=500)]
        breaches = detect_breaches(events, {}, now=_NOW)
        assert len(breaches) == 1

    def test_default_now(self):
        events = []
        breaches = detect_breaches(events, {})
        assert breaches == []


class TestBuildPartnerSlaReport:
    def test_basic_report(self):
        period_start = _NOW - timedelta(days=7)
        period_end = _NOW
        events = [_make_event("S1", acknowledged_minutes_after=30)]
        report = build_partner_sla_report("TP001", events, _DEFAULT_SLA, period_start, period_end)
        assert report.trading_partner_id == "TP001"
        assert report.total_submissions == 1
        assert report.acknowledged_within_sla == 1

    def test_breach_counted(self):
        period_start = _NOW - timedelta(days=7)
        period_end = _NOW
        events = [_make_event("S1", submitted_minutes_ago=90, acknowledged_minutes_after=90)]
        report = build_partner_sla_report("TP001", events, _DEFAULT_SLA, period_start, period_end)
        assert report.acknowledged_within_sla == 0
        assert len(report.breaches) == 1

    def test_response_compliance(self):
        period_start = _NOW - timedelta(days=7)
        period_end = _NOW
        events = [_make_event("S1", responded_minutes_after=60)]
        report = build_partner_sla_report("TP001", events, _DEFAULT_SLA, period_start, period_end)
        assert report.responded_within_sla == 1
        assert report.response_compliance_pct == 100.0

    def test_zero_submissions_zero_pct(self):
        period_start = _NOW - timedelta(days=7)
        period_end = _NOW
        report = build_partner_sla_report("TP001", [], _DEFAULT_SLA, period_start, period_end)
        assert report.total_submissions == 0
        assert report.acknowledgment_compliance_pct == 0.0

    def test_filters_by_partner_id(self):
        period_start = _NOW - timedelta(days=7)
        period_end = _NOW
        events = [
            _make_event("S1", tp_id="TP001"),
            _make_event("S2", tp_id="TP002"),
        ]
        report = build_partner_sla_report("TP001", events, _DEFAULT_SLA, period_start, period_end)
        assert report.total_submissions == 1

    def test_filters_by_period(self):
        period_start = _NOW - timedelta(days=1)
        period_end = _NOW
        events = [
            _make_event("S1", submitted_minutes_ago=30),           # in window
            _make_event("S2", submitted_minutes_ago=60 * 24 + 30), # outside window
        ]
        report = build_partner_sla_report("TP001", events, _DEFAULT_SLA, period_start, period_end)
        assert report.total_submissions == 1

    def test_no_responses_zero_response_compliance(self):
        period_start = _NOW - timedelta(days=7)
        period_end = _NOW
        events = [_make_event("S1")]
        report = build_partner_sla_report("TP001", events, _DEFAULT_SLA, period_start, period_end)
        assert report.response_compliance_pct == 0.0


class TestRecordAcknowledgment:
    def test_within_sla_sets_acknowledged(self):
        event = _make_event(submitted_minutes_ago=90)
        ack_time = event.submitted_at + timedelta(minutes=30)
        updated = record_acknowledgment(event, ack_time, _DEFAULT_SLA)
        assert updated.status == SlaStatus.ACKNOWLEDGED
        assert updated.acknowledged_at == ack_time

    def test_late_ack_sets_breached(self):
        event = _make_event(submitted_minutes_ago=90)
        ack_time = event.submitted_at + timedelta(minutes=120)
        updated = record_acknowledgment(event, ack_time, _DEFAULT_SLA)
        assert updated.status == SlaStatus.BREACHED


class TestSummarizeSLADashboard:
    def test_all_within_sla(self):
        events = [_make_event(f"S{i}", submitted_minutes_ago=10) for i in range(3)]
        result = summarize_sla_dashboard(events, {"TP001": _DEFAULT_SLA}, now=_NOW)
        assert result["within_sla"] == 3
        assert result["breached"] == 0

    def test_breach_counted_in_dashboard(self):
        events = [_make_event("S1", submitted_minutes_ago=120)]
        result = summarize_sla_dashboard(events, {"TP001": _DEFAULT_SLA}, now=_NOW)
        assert result["breached"] == 1

    def test_at_risk_counted(self):
        events = [_make_event("S1", submitted_minutes_ago=50)]
        result = summarize_sla_dashboard(events, {"TP001": _DEFAULT_SLA}, now=_NOW)
        assert result["at_risk"] == 1

    def test_acknowledged_counted(self):
        events = [_make_event("S1", submitted_minutes_ago=90, acknowledged_minutes_after=30)]
        result = summarize_sla_dashboard(events, {"TP001": _DEFAULT_SLA}, now=_NOW)
        assert result["acknowledged"] == 1

    def test_breach_rate_pct(self):
        events = [
            _make_event("S1", submitted_minutes_ago=10),  # within
            _make_event("S2", submitted_minutes_ago=120), # breach
        ]
        result = summarize_sla_dashboard(events, {"TP001": _DEFAULT_SLA}, now=_NOW)
        assert result["breach_rate_pct"] == 50.0

    def test_empty_events(self):
        result = summarize_sla_dashboard([], {}, now=_NOW)
        assert result["total_submissions"] == 0
        assert result["breach_rate_pct"] == 0.0

    def test_as_of_timestamp(self):
        result = summarize_sla_dashboard([], {}, now=_NOW)
        assert result["as_of"] == "20260115T120000Z"

    def test_default_now(self):
        result = summarize_sla_dashboard([], {})
        assert "as_of" in result
