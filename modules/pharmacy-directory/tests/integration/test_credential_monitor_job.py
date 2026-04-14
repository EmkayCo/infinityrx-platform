"""Integration tests for credential monitoring job — alert thresholds."""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from shared.events.in_memory_bus import InMemoryEventBus

from src.jobs.credential_monitor import run_credential_monitoring
from src.models.tables import CredentialMonitoring, Pharmacy

TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")


class TestCredentialMonitorJob:
    @pytest.mark.asyncio
    async def test_fires_alert_at_90_days(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy, event_bus: InMemoryEventBus
    ) -> None:
        today = date(2026, 1, 1)
        expiry = today + timedelta(days=90)
        monitoring = CredentialMonitoring(
            tenant_id=TENANT_A,
            pharmacy_id=pharmacy_a.id,
            credential_type="state_license",
            current_status="active",
            expiry_date=expiry,
        )
        db_session.add(monitoring)
        await db_session.flush()

        result = await run_credential_monitoring(db_session, event_bus, TENANT_A, today)
        assert result["alerted"] == 1
        assert len(event_bus.published) == 1
        assert event_bus.published[0].event_type == "pharmacy.credential_expiring"
        assert event_bus.published[0].payload["days_until_expiry"] == 90

    @pytest.mark.asyncio
    async def test_fires_alert_at_30_days(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy, event_bus: InMemoryEventBus
    ) -> None:
        today = date(2026, 2, 1)
        expiry = today + timedelta(days=30)
        monitoring = CredentialMonitoring(
            tenant_id=TENANT_A,
            pharmacy_id=pharmacy_a.id,
            credential_type="dea",
            current_status="active",
            expiry_date=expiry,
        )
        db_session.add(monitoring)
        await db_session.flush()

        result = await run_credential_monitoring(db_session, event_bus, TENANT_A, today)
        assert result["alerted"] == 1
        payload = event_bus.published[0].payload
        assert payload["days_until_expiry"] == 30
        assert payload["credential_type"] == "dea"

    @pytest.mark.asyncio
    async def test_no_duplicate_alerts_on_second_run(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy, event_bus: InMemoryEventBus
    ) -> None:
        today = date(2026, 3, 1)
        expiry = today + timedelta(days=60)
        monitoring = CredentialMonitoring(
            tenant_id=TENANT_A,
            pharmacy_id=pharmacy_a.id,
            credential_type="liability_insurance",
            current_status="active",
            expiry_date=expiry,
        )
        db_session.add(monitoring)
        await db_session.flush()

        result1 = await run_credential_monitoring(db_session, event_bus, TENANT_A, today)
        result2 = await run_credential_monitoring(db_session, event_bus, TENANT_A, today)
        assert result1["alerted"] == 1
        assert result2["already_sent"] == 1
        assert len(event_bus.published) == 1

    @pytest.mark.asyncio
    async def test_no_alert_when_not_at_threshold(
        self, db_session: AsyncSession, pharmacy_a: Pharmacy, event_bus: InMemoryEventBus
    ) -> None:
        today = date(2026, 4, 1)
        expiry = today + timedelta(days=45)  # not at 30/60/90
        monitoring = CredentialMonitoring(
            tenant_id=TENANT_A,
            pharmacy_id=pharmacy_a.id,
            credential_type="state_license",
            current_status="active",
            expiry_date=expiry,
        )
        db_session.add(monitoring)
        await db_session.flush()

        result = await run_credential_monitoring(db_session, event_bus, TENANT_A, today)
        assert result["alerted"] == 0
        assert len(event_bus.published) == 0
