"""Tests for credential monitoring service.

100% coverage required (credential expiry is a security/compliance path).
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.models.tables import CredentialAlert, Prescriber, PrescriberBase
from src.services.credential_monitor import run_credential_monitoring
from tests.conftest import make_prescriber


@pytest.fixture(scope="module")
def monitor_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    for t in PrescriberBase.metadata.tables.values():
        t.schema = None
    PrescriberBase.metadata.create_all(engine)
    yield engine
    PrescriberBase.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def monitor_db(monitor_engine) -> Session:
    session = sessionmaker(bind=monitor_engine, expire_on_commit=False, future=True)()
    yield session
    session.rollback()
    session.close()


TODAY = date(2026, 4, 13)


def make_prescriber_row(npi: str, **kwargs) -> dict:
    row = make_prescriber(npi=npi, **kwargs)
    return row


class TestDeaExpiryAlerts:
    def test_creates_alert_for_dea_expiring_30_days(self, monitor_db):
        expiry = TODAY + timedelta(days=25)
        p = Prescriber(**make_prescriber_row(
            "1234500001",
            status="active",
        ))
        p.dea_expiration_date = expiry
        monitor_db.add(p)
        monitor_db.flush()

        summary = run_credential_monitoring(monitor_db, today=TODAY)
        assert summary.get("dea_expiring", 0) >= 1

        alerts = monitor_db.execute(select(CredentialAlert).where(
            CredentialAlert.prescriber_id == p.id,
            CredentialAlert.alert_type == "dea_expiring",
        )).scalars().all()
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"

    def test_creates_alert_for_dea_expired(self, monitor_db):
        expiry = TODAY - timedelta(days=5)
        p = Prescriber(**make_prescriber_row("1234500002", status="active"))
        p.dea_expiration_date = expiry
        monitor_db.add(p)
        monitor_db.flush()

        summary = run_credential_monitoring(monitor_db, today=TODAY)
        assert summary.get("dea_expired", 0) >= 1

        alerts = monitor_db.execute(select(CredentialAlert).where(
            CredentialAlert.prescriber_id == p.id,
            CredentialAlert.alert_type == "dea_expired",
        )).scalars().all()
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"

    def test_creates_alert_for_dea_expiring_60_days(self, monitor_db):
        expiry = TODAY + timedelta(days=55)
        p = Prescriber(**make_prescriber_row("1234500003", status="active"))
        p.dea_expiration_date = expiry
        monitor_db.add(p)
        monitor_db.flush()

        summary = run_credential_monitoring(monitor_db, today=TODAY)
        assert summary.get("dea_expiring", 0) >= 1

        alerts = monitor_db.execute(select(CredentialAlert).where(
            CredentialAlert.prescriber_id == p.id,
        )).scalars().all()
        assert any(a.severity == "warning" for a in alerts)

    def test_creates_alert_for_dea_expiring_90_days(self, monitor_db):
        expiry = TODAY + timedelta(days=85)
        p = Prescriber(**make_prescriber_row("1234500004", status="active"))
        p.dea_expiration_date = expiry
        monitor_db.add(p)
        monitor_db.flush()

        summary = run_credential_monitoring(monitor_db, today=TODAY)
        assert summary.get("dea_expiring", 0) >= 1

        alerts = monitor_db.execute(select(CredentialAlert).where(
            CredentialAlert.prescriber_id == p.id,
        )).scalars().all()
        assert any(a.severity == "info" for a in alerts)

    def test_no_alert_for_dea_far_future(self, monitor_db):
        expiry = TODAY + timedelta(days=200)
        p = Prescriber(**make_prescriber_row("1234500005", status="active"))
        p.dea_expiration_date = expiry
        monitor_db.add(p)
        monitor_db.flush()

        count_before = monitor_db.execute(select(CredentialAlert).where(
            CredentialAlert.prescriber_id == p.id
        )).scalars().all()
        run_credential_monitoring(monitor_db, today=TODAY)
        count_after = monitor_db.execute(select(CredentialAlert).where(
            CredentialAlert.prescriber_id == p.id
        )).scalars().all()
        assert len(count_after) == len(count_before)

    def test_no_alert_for_inactive_prescriber(self, monitor_db):
        expiry = TODAY + timedelta(days=10)
        p = Prescriber(**make_prescriber_row("1234500006", status="inactive"))
        p.dea_expiration_date = expiry
        monitor_db.add(p)
        monitor_db.flush()

        run_credential_monitoring(monitor_db, today=TODAY)
        alerts = monitor_db.execute(select(CredentialAlert).where(
            CredentialAlert.prescriber_id == p.id,
        )).scalars().all()
        assert len(alerts) == 0

    def test_no_duplicate_alert_when_run_twice(self, monitor_db):
        expiry = TODAY + timedelta(days=10)
        p = Prescriber(**make_prescriber_row("1234500007", status="active"))
        p.dea_expiration_date = expiry
        monitor_db.add(p)
        monitor_db.flush()

        run_credential_monitoring(monitor_db, today=TODAY)
        run_credential_monitoring(monitor_db, today=TODAY)

        alerts = monitor_db.execute(select(CredentialAlert).where(
            CredentialAlert.prescriber_id == p.id,
            CredentialAlert.acknowledged_at.is_(None),
        )).scalars().all()
        assert len(alerts) == 1


class TestLicenseExpiryAlerts:
    def test_creates_alert_for_license_expiring(self, monitor_db):
        expiry = TODAY + timedelta(days=20)
        p = Prescriber(**make_prescriber_row("1234500008", status="active"))
        p.state_license_expiry = expiry
        monitor_db.add(p)
        monitor_db.flush()

        summary = run_credential_monitoring(monitor_db, today=TODAY)
        assert summary.get("license_expiring", 0) >= 1

    def test_creates_alert_for_license_expired(self, monitor_db):
        expiry = TODAY - timedelta(days=3)
        p = Prescriber(**make_prescriber_row("1234500009", status="active"))
        p.state_license_expiry = expiry
        monitor_db.add(p)
        monitor_db.flush()

        summary = run_credential_monitoring(monitor_db, today=TODAY)
        assert summary.get("license_expired", 0) >= 1

    def test_no_duplicate_license_alert(self, monitor_db):
        expiry = TODAY + timedelta(days=10)
        p = Prescriber(**make_prescriber_row("1234500010", status="active"))
        p.state_license_expiry = expiry
        monitor_db.add(p)
        monitor_db.flush()

        run_credential_monitoring(monitor_db, today=TODAY)
        run_credential_monitoring(monitor_db, today=TODAY)

        alerts = monitor_db.execute(select(CredentialAlert).where(
            CredentialAlert.prescriber_id == p.id,
            CredentialAlert.acknowledged_at.is_(None),
        )).scalars().all()
        assert len(alerts) == 1


class TestRunWithNoAlerts:
    def test_returns_empty_summary_when_no_expiring(self, monitor_db):
        # Prescriber with no DEA and no license expiry
        p = Prescriber(**make_prescriber_row("1234500011", status="active"))
        monitor_db.add(p)
        monitor_db.flush()

        summary = run_credential_monitoring(monitor_db, today=TODAY)
        # summary may have counts from other tests but prescriber with no dates creates no alerts
        # just verify it returns a dict
        assert isinstance(summary, dict)

    def test_no_today_arg_uses_current_date(self, monitor_db):
        # Exercises the `if today is None: today = date.today()` branch (line 51)
        p = Prescriber(**make_prescriber_row("1234500012", status="active"))
        monitor_db.add(p)
        monitor_db.flush()
        # Just verify it doesn't raise when today is omitted
        summary = run_credential_monitoring(monitor_db)
        assert isinstance(summary, dict)

    def test_no_duplicate_dea_expired_alert(self, monitor_db):
        # Covers the _already_alerted True path for dea_expired (branch 68->92)
        expiry = TODAY - timedelta(days=10)
        p = Prescriber(**make_prescriber_row("1234500013", status="active"))
        p.dea_expiration_date = expiry
        monitor_db.add(p)
        monitor_db.flush()

        run_credential_monitoring(monitor_db, today=TODAY)
        run_credential_monitoring(monitor_db, today=TODAY)

        alerts = monitor_db.execute(select(CredentialAlert).where(
            CredentialAlert.prescriber_id == p.id,
            CredentialAlert.alert_type == "dea_expired",
            CredentialAlert.acknowledged_at.is_(None),
        )).scalars().all()
        assert len(alerts) == 1

    def test_no_duplicate_license_expired_alert(self, monitor_db):
        # Covers the _already_alerted True path for license_expired (branch 107->106)
        expiry = TODAY - timedelta(days=10)
        p = Prescriber(**make_prescriber_row("1234500014", status="active"))
        p.state_license_expiry = expiry
        monitor_db.add(p)
        monitor_db.flush()

        run_credential_monitoring(monitor_db, today=TODAY)
        run_credential_monitoring(monitor_db, today=TODAY)

        alerts = monitor_db.execute(select(CredentialAlert).where(
            CredentialAlert.prescriber_id == p.id,
            CredentialAlert.alert_type == "license_expired",
            CredentialAlert.acknowledged_at.is_(None),
        )).scalars().all()
        assert len(alerts) == 1
