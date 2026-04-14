"""Tests covering remaining router validation branches."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_db
from src.main import create_app
from src.models.tables import CredentialAlert, Prescriber
from tests.conftest import make_prescriber, now_utc, TENANT_A


@pytest.fixture(scope="module")
def app(_engine):
    application = create_app()

    def override_get_db():
        from sqlalchemy.orm import sessionmaker as _sm
        factory = _sm(bind=_engine, expire_on_commit=False, future=True)
        session = factory()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_db] = override_get_db
    return application


@pytest.fixture(scope="module")
def client(app):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def branch_seed(_engine):
    from sqlalchemy.orm import sessionmaker as _sm
    factory = _sm(bind=_engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        # Inactive prescriber
        p1 = Prescriber(**make_prescriber(
            npi="1000000053",
            display_name="INACTIVE PROVIDER",
            status="inactive",
        ))
        # Prescriber with DEA but inactive DEA
        p2 = Prescriber(**make_prescriber(
            npi="1000000061",
            display_name="EXPIRED DEA PROVIDER MD",
            status="active",
            dea_number="AC1234561",
            dea_status="expired",
            dea_schedules=["2", "3"],
        ))
        # Prescriber with active DEA but schedule 1 not in authorized list
        p3 = Prescriber(**make_prescriber(
            npi="1000000079",
            display_name="LIMITED SCHEDULE PROVIDER MD",
            status="active",
            dea_number="AD1234569",
            dea_status="active",
            dea_schedules=["4", "5"],  # only 4 and 5
        ))
        # Acknowledged alert
        p4 = Prescriber(**make_prescriber(
            npi="1000000087",
            display_name="ACK ALERT PROVIDER",
            status="active",
        ))
        session.add_all([p1, p2, p3, p4])
        session.flush()

        alert = CredentialAlert(
            id=uuid.uuid4(),
            prescriber_id=p4.id,
            alert_type="dea_expiring",
            severity="info",
            message="Already acknowledged",
            acknowledged_at=now_utc(),
            created_at=now_utc(),
        )
        session.add(alert)
        session.commit()
    finally:
        session.close()


class TestValidationBranches:
    def test_validate_inactive_prescriber(self, client, branch_seed):
        resp = client.get(
            "/api/v1/prescribers/validate/1000000053",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert data["reason_code"] == "INACTIVE"

    def test_controlled_substance_dea_not_active(self, client, branch_seed):
        resp = client.get(
            "/api/v1/prescribers/validate/1000000061/controlled/2",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["authorized"] is False
        assert data["reason_code"] == "DEA_NOT_ACTIVE"

    def test_controlled_substance_schedule_not_authorized(self, client, branch_seed):
        resp = client.get(
            "/api/v1/prescribers/validate/1000000079/controlled/2",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["authorized"] is False
        assert data["reason_code"] == "SCHEDULE_NOT_AUTHORIZED"

    def test_controlled_substance_npi_not_found(self, client, branch_seed):
        resp = client.get(
            "/api/v1/prescribers/validate/1000000004/controlled/2",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["authorized"] is False
        assert data["reason_code"] == "NPI_NOT_FOUND"

    def test_controlled_substance_invalid_npi(self, client, branch_seed):
        resp = client.get(
            "/api/v1/prescribers/validate/BADNPI/controlled/2",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["authorized"] is False
        assert data["reason_code"] == "INVALID_NPI_FORMAT"


class TestAlertsAcknowledgedFilter:
    def test_list_acknowledged_alerts(self, client, branch_seed):
        resp = client.get(
            "/api/v1/prescribers/monitoring/alerts?acknowledged=true",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        alerts = resp.json()
        assert isinstance(alerts, list)
        # All returned should be acknowledged
        for a in alerts:
            assert a["acknowledged_at"] is not None
