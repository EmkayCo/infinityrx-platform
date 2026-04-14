"""Daily credential monitoring job — fires expiry alerts at 90/60/30 days."""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime, timedelta

from shared.events.bus import EventBus
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.events.publisher import publish_credential_expiring
from src.models.tables import CredentialMonitoring, Pharmacy

logger = logging.getLogger("pharmacy-directory.jobs.credential_monitor")

_ALERT_THRESHOLDS = [90, 60, 30]


async def run_credential_monitoring(
    db: AsyncSession,
    bus: EventBus,
    tenant_id: uuid.UUID,
    as_of_date: date | None = None,
) -> dict[str, int]:
    """Run daily check for expiring credentials. Returns alert counts."""
    today = as_of_date or date.today()
    alerted = 0
    already_sent = 0

    for threshold in _ALERT_THRESHOLDS:
        target_date = today + timedelta(days=threshold)
        stmt = (
            select(CredentialMonitoring, Pharmacy)
            .join(Pharmacy, Pharmacy.id == CredentialMonitoring.pharmacy_id)
            .where(
                CredentialMonitoring.tenant_id == tenant_id,
                CredentialMonitoring.expiry_date == target_date,
                CredentialMonitoring.current_status == "active",
            )
        )
        result = await db.execute(stmt)
        rows = result.all()

        for monitoring, pharmacy in rows:
            if monitoring.alert_sent_at is not None:
                already_sent += 1
                continue

            await publish_credential_expiring(
                bus=bus,
                tenant_id=tenant_id,
                correlation_id=uuid.uuid4(),
                pharmacy_id=str(monitoring.pharmacy_id),
                npi=pharmacy.npi,
                credential_type=monitoring.credential_type,
                days_until_expiry=threshold,
            )
            monitoring.alert_sent_at = datetime.now(UTC)
            alerted += 1

    await db.flush()
    logger.info(
        "credential_monitor.run_complete",
        extra={
            "svc_name": "credential_monitor",
            "alerts_sent": alerted,
            "already_sent": already_sent,
        },
    )
    return {"alerted": alerted, "already_sent": already_sent}
