"""Integration tests for claim API endpoints via create_app().

Tests run against the real application factory with an in-memory SQLite DB.
Tenant isolation tested per endpoint with two tenants.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from shared.auth.dependencies import get_current_user
from src.main import create_app
from tests.conftest import _FAKE_USER_FOR_TESTS

# Reuse the SAVEPOINT engine pattern from conftest
TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")

_CLAIM_PAYLOAD = {
    "claim_number": "API-001",
    "claim_line_number": 1,
    "claim_type": "professional",
    "patient_member_id": "MBR-API-1",
    "rendering_provider_npi": "1234567890",
    "date_of_service": "2026-01-15",
    "procedure_code": "J0135",
    "billed_amount": "250.00",
}


@pytest.fixture(scope="module")
def app_and_db(_engine):
    """Create app with the session-scoped SQLite engine injected via middleware.

    Reuses the _engine fixture from conftest which already cleared schemas and
    applied _UUIDString, so tables are already created.
    """
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)

    app = create_app()

    # CR-03: bypass JWT auth so these integration tests focus on business logic
    app.dependency_overrides[get_current_user] = lambda: _FAKE_USER_FOR_TESTS

    @app.middleware("http")
    async def inject_db(request, call_next):
        session = SessionLocal()
        request.state.db = session
        try:
            response = await call_next(request)
        finally:
            session.close()
        return response

    client = TestClient(app)
    yield client, _engine


@pytest.fixture
def client(app_and_db):
    client, _ = app_and_db
    return client


class TestClaimCRUD:
    def test_create_claim_returns_201(self, client):
        resp = client.post(
            "/api/v1/medical-claims/claims",
            json=_CLAIM_PAYLOAD,
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["claim_number"] == "API-001"
        assert data["status"] == "received"

    def test_get_claim_returns_200(self, client):
        create_resp = client.post(
            "/api/v1/medical-claims/claims",
            json={**_CLAIM_PAYLOAD, "claim_number": "API-GET-001"},
            headers={"x-tenant-id": str(TENANT_A)},
        )
        claim_id = create_resp.json()["id"]

        resp = client.get(
            f"/api/v1/medical-claims/claims/{claim_id}",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == claim_id

    def test_get_claim_wrong_tenant_returns_404(self, client):
        create_resp = client.post(
            "/api/v1/medical-claims/claims",
            json={**_CLAIM_PAYLOAD, "claim_number": "API-ISO-001"},
            headers={"x-tenant-id": str(TENANT_A)},
        )
        claim_id = create_resp.json()["id"]

        # Tenant B must NOT see Tenant A's claim
        resp = client.get(
            f"/api/v1/medical-claims/claims/{claim_id}",
            headers={"x-tenant-id": str(TENANT_B)},
        )
        assert resp.status_code == 404

    def test_list_claims_tenant_isolation(self, client):
        # Create one claim for each tenant
        client.post(
            "/api/v1/medical-claims/claims",
            json={**_CLAIM_PAYLOAD, "claim_number": "T1-LIST-001"},
            headers={"x-tenant-id": str(TENANT_A)},
        )
        client.post(
            "/api/v1/medical-claims/claims",
            json={**_CLAIM_PAYLOAD, "claim_number": "T2-LIST-001"},
            headers={"x-tenant-id": str(TENANT_B)},
        )

        resp = client.get(
            "/api/v1/medical-claims/claims",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        claim_numbers = {c["claim_number"] for c in resp.json()["items"]}
        # Tenant A must NOT see Tenant B claims
        assert "T2-LIST-001" not in claim_numbers

    def test_missing_tenant_header_returns_401(self, client):
        resp = client.post("/api/v1/medical-claims/claims", json=_CLAIM_PAYLOAD)
        assert resp.status_code in (401, 422)

    def test_invalid_npi_returns_422(self, client):
        bad_payload = {**_CLAIM_PAYLOAD, "rendering_provider_npi": "BADNPI"}
        resp = client.post(
            "/api/v1/medical-claims/claims",
            json=bad_payload,
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert resp.status_code == 422

    def test_phi_response_has_no_store_header(self, client):
        create_resp = client.post(
            "/api/v1/medical-claims/claims",
            json={**_CLAIM_PAYLOAD, "claim_number": "API-PHI-001"},
            headers={"x-tenant-id": str(TENANT_A)},
        )
        claim_id = create_resp.json()["id"]
        resp = client.get(
            f"/api/v1/medical-claims/claims/{claim_id}",
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert "no-store" in resp.headers.get("cache-control", "")


class TestStatusTransitions:
    def test_status_transition_via_api(self, client):
        resp = client.post(
            "/api/v1/medical-claims/claims",
            json={**_CLAIM_PAYLOAD, "claim_number": "ST-API-001"},
            headers={"x-tenant-id": str(TENANT_A)},
        )
        claim_id = resp.json()["id"]

        update = client.post(
            f"/api/v1/medical-claims/claims/{claim_id}/status",
            json={"status": "validated"},
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert update.status_code == 200
        assert update.json()["status"] == "validated"

    def test_invalid_transition_returns_422(self, client):
        resp = client.post(
            "/api/v1/medical-claims/claims",
            json={**_CLAIM_PAYLOAD, "claim_number": "ST-API-002"},
            headers={"x-tenant-id": str(TENANT_A)},
        )
        claim_id = resp.json()["id"]

        update = client.post(
            f"/api/v1/medical-claims/claims/{claim_id}/status",
            json={"status": "paid"},  # invalid from 'received'
            headers={"x-tenant-id": str(TENANT_A)},
        )
        assert update.status_code == 422
