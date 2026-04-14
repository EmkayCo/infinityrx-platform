"""Credential monitoring service — DEA expiry, license expiry, NPI deactivation alerts.

Runs daily via a scheduled job. Checks all active prescribers and creates
CredentialAlert records for any approaching or expired credentials.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.tables import CredentialAlert, Prescriber

logger = logging.getLogger("prescriber-directory.credential-monitor")

# Alert thresholds in days
_DEA_EXPIRY_THRESHOLDS = [90, 60, 30]
_LICENSE_EXPIRY_THRESHOLDS = [90, 60, 30]


def _severity_for_days(days_remaining: int) -> str:
    if days_remaining <= 30:
        return "critical"
    if days_remaining <= 60:
        return "warning"
    return "info"


def _already_alerted(db: Session, prescriber_id: Any, alert_type: str, cutoff_date: date) -> bool:
    from datetime import datetime, timezone
    cutoff_dt = datetime.combine(cutoff_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    stmt = select(CredentialAlert).where(
        CredentialAlert.prescriber_id == prescriber_id,
        CredentialAlert.alert_type == alert_type,
        CredentialAlert.created_at >= cutoff_dt,
        CredentialAlert.acknowledged_at.is_(None),
    )
    return db.execute(stmt).scalar_one_or_none() is not None


def run_credential_monitoring(db: Session, today: date | None = None) -> dict[str, int]:
    """Check all active prescribers for expiring/expired credentials.

    Returns a summary of alerts created: {alert_type: count}.
    """
    if today is None:
        today = date.today()

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    summary: dict[str, int] = {}
    alerts_to_add = []

    stmt = select(Prescriber).where(Prescriber.status == "active")
    prescribers = db.execute(stmt).scalars().all()

    for prescriber in prescribers:
        # DEA expiry checks
        if prescriber.dea_expiration_date:
            days_remaining = (prescriber.dea_expiration_date - today).days
            if days_remaining < 0:
                alert_type = "dea_expired"
                if not _already_alerted(db, prescriber.id, alert_type, today - timedelta(days=1)):
                    alerts_to_add.append(CredentialAlert(
                        prescriber_id=prescriber.id,
                        alert_type=alert_type,
                        severity="critical",
                        message=f"DEA registration expired on {prescriber.dea_expiration_date}",
                        created_at=now,
                    ))
                    summary[alert_type] = summary.get(alert_type, 0) + 1
            else:
                for threshold in _DEA_EXPIRY_THRESHOLDS:
                    if days_remaining <= threshold:
                        if not _already_alerted(db, prescriber.id, "dea_expiring", today - timedelta(days=1)):
                            alerts_to_add.append(CredentialAlert(
                                prescriber_id=prescriber.id,
                                alert_type="dea_expiring",
                                severity=_severity_for_days(days_remaining),
                                message=f"DEA expires in {days_remaining} days ({prescriber.dea_expiration_date})",
                                created_at=now,
                            ))
                            summary["dea_expiring"] = summary.get("dea_expiring", 0) + 1
                        break  # only create one alert per prescriber (most urgent threshold)

        # State license expiry checks
        if prescriber.state_license_expiry:
            days_remaining = (prescriber.state_license_expiry - today).days
            if days_remaining < 0:
                alert_type = "license_expired"
                if not _already_alerted(db, prescriber.id, alert_type, today - timedelta(days=1)):
                    alerts_to_add.append(CredentialAlert(
                        prescriber_id=prescriber.id,
                        alert_type=alert_type,
                        severity="critical",
                        message=f"State license expired on {prescriber.state_license_expiry}",
                        created_at=now,
                    ))
                    summary[alert_type] = summary.get(alert_type, 0) + 1
            else:
                for threshold in _LICENSE_EXPIRY_THRESHOLDS:
                    if days_remaining <= threshold:
                        if not _already_alerted(db, prescriber.id, "license_expiring", today - timedelta(days=1)):
                            alerts_to_add.append(CredentialAlert(
                                prescriber_id=prescriber.id,
                                alert_type="license_expiring",
                                severity=_severity_for_days(days_remaining),
                                message=f"State license expires in {days_remaining} days ({prescriber.state_license_expiry})",
                                created_at=now,
                            ))
                            summary["license_expiring"] = summary.get("license_expiring", 0) + 1
                        break

    if alerts_to_add:
        db.add_all(alerts_to_add)
        db.flush()
        logger.info(
            "credential_monitoring_complete",
            extra={"svc_alerts_created": len(alerts_to_add), "svc_summary": str(summary)},
        )

    return summary
