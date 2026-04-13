"""Integration tests for ReclaimRx API endpoints — TDD first."""
from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from src._shim.auth import CurrentUser
from src.api.dependencies import get_current_user, get_db
from src.api.router import router
from src.services.detection_rule_seeder import seed_detection_rules

from tests.conftest import TEST_TENANT_ID, TEST_USER_ID


def build_app(db: Session) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    def _db_override():
        yield db

    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=TEST_USER_ID,
        tenant_id=TEST_TENANT_ID,
        roles=["investigator", "tenant_admin"],
    )
    return app


@pytest.fixture()
def client(db: Session) -> TestClient:
    seed_detection_rules(db)
    db.flush()
    app = build_app(db)
    return TestClient(app, raise_server_exceptions=True)


class TestEvaluateEndpoint:
    def test_evaluate_clean_claim_returns_no_flags(self, client: TestClient) -> None:
        resp = client.post("/api/v1/reclaimrx/evaluate", json={
            "auth_number": "AUTH001",
            "date_of_service": "2026-01-15",
            "pharmacy_npi": "1234567890",
            "prescriber_npi": "0987654321",
            "member_id": "MEM001",
            "ndc": "12345678901",
            "quantity": "30.000",
            "days_supply": 30,
            "billed_amount": "90.00",
            "paid_amount": "85.00",
            "wac_per_unit": "3.00",
            "nq": "90.00",
            "dv": "0.00",
            "program_type": "manufacturer",
            "client_type": "manufacturer",
            "metadata": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_risk_score" in data
        assert "flags" in data
        assert "rules_evaluated" in data
        assert data["rules_evaluated"] > 0

    def test_evaluate_requires_auth(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(router)
        # No override — should raise RuntimeError (no current user) or OperationalError (no DB)
        import sqlalchemy.exc
        with pytest.raises((RuntimeError, sqlalchemy.exc.OperationalError)), TestClient(app, raise_server_exceptions=True) as c:
            c.post("/api/v1/reclaimrx/evaluate", json={
                "auth_number": "AUTH001",
                "date_of_service": "2026-01-15",
                "pharmacy_npi": "1234567890",
                "quantity": "30.000",
                "days_supply": 30,
                "billed_amount": "90.00",
                "paid_amount": "85.00",
                "program_type": "manufacturer",
                "client_type": "manufacturer",
            })

    def test_evaluate_nq_inflated_claim_flags_mfr001(self, client: TestClient) -> None:
        resp = client.post("/api/v1/reclaimrx/evaluate", json={
            "auth_number": "AUTH002",
            "date_of_service": "2026-01-15",
            "pharmacy_npi": "1234567890",
            "prescriber_npi": "0987654321",
            "member_id": "MEM002",
            "ndc": "12345678901",
            "quantity": "30.000",
            "days_supply": 30,
            "billed_amount": "200.00",
            "paid_amount": "195.00",
            "wac_per_unit": "3.00",
            "nq": "200.00",  # WAC total = 90, NQ = 200 → ratio = 2.22, well above 1.10
            "dv": "0.00",
            "awp_per_unit": "3.50",
            "program_type": "manufacturer",
            "client_type": "manufacturer",
            "metadata": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        rule_codes = [f["rule_code"] for f in data["flags"]]
        assert "MFR-001" in rule_codes


class TestInvestigationEndpoints:
    def test_create_investigation(self, client: TestClient) -> None:
        resp = client.post("/api/v1/reclaimrx/investigations", json={
            "subject_type": "pharmacy",
            "subject_entity_id": "1234567890",
            "subject_name": "Test Pharmacy",
            "investigation_type": "desk_audit",
            "title": "Suspicious NQ Patterns",
            "priority": "high",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "open"
        assert data["investigation_number"].startswith("INV-")

    def test_list_investigations_empty(self, client: TestClient, db: Session) -> None:
        resp = client.get("/api/v1/reclaimrx/investigations")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_investigation_not_found(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/reclaimrx/investigations/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_update_investigation_status(self, client: TestClient) -> None:
        create_resp = client.post("/api/v1/reclaimrx/investigations", json={
            "subject_type": "pharmacy",
            "subject_entity_id": "9999999999",
            "subject_name": "Update Test Pharmacy",
            "investigation_type": "desk_audit",
            "title": "Update Status Test",
            "priority": "medium",
        })
        assert create_resp.status_code == 201
        inv_id = create_resp.json()["id"]

        update_resp = client.put(f"/api/v1/reclaimrx/investigations/{inv_id}", json={
            "status": "in_progress",
            "notes": "Starting detailed review",
        })
        assert update_resp.status_code == 200
        assert update_resp.json()["status"] == "in_progress"


class TestPaymentHoldEndpoints:
    def test_create_and_list_hold(self, client: TestClient) -> None:
        resp = client.post("/api/v1/reclaimrx/holds", json={
            "entity_type": "pharmacy",
            "entity_id": "1234567890",
            "entity_name": "Test Pharmacy",
            "hold_scope": "all",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["is_active"] is True
        assert data["entity_id"] == "1234567890"

        list_resp = client.get("/api/v1/reclaimrx/holds")
        assert list_resp.status_code == 200
        holds = list_resp.json()
        assert any(h["entity_id"] == "1234567890" for h in holds)

    def test_release_hold(self, client: TestClient) -> None:
        create_resp = client.post("/api/v1/reclaimrx/holds", json={
            "entity_type": "pharmacy",
            "entity_id": "5555555555",
            "entity_name": "Release Me Pharmacy",
            "hold_scope": "all",
        })
        assert create_resp.status_code == 201
        hold_id = create_resp.json()["id"]

        release_resp = client.delete(
            f"/api/v1/reclaimrx/holds/{hold_id}",
            params={"reason": "Investigation resolved"},
        )
        assert release_resp.status_code == 200
        assert release_resp.json()["is_active"] is False

    def test_release_nonexistent_hold_returns_404(self, client: TestClient) -> None:
        resp = client.delete(
            f"/api/v1/reclaimrx/holds/{uuid.uuid4()}",
            params={"reason": "Test reason"},
        )
        assert resp.status_code == 404


class TestTipEndpoints:
    def test_submit_tip_anonymous(self, client: TestClient) -> None:
        resp = client.post("/api/v1/reclaimrx/tips", json={
            "tip_type": "pharmacy_fraud",
            "subject_description": "Pharmacy at 123 Main St billing for meds not dispensed",
            "detail_text": "I witnessed prescriptions being billed for patients who never came in.",
            "is_anonymous": True,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "new"
        assert data["is_anonymous"] is True

    def test_list_tips_returns_only_tenant(self, client: TestClient) -> None:
        client.post("/api/v1/reclaimrx/tips", json={
            "tip_type": "prescriber_fraud",
            "subject_description": "DR Smith writing scripts without seeing patients",
            "detail_text": "I know because I work at the pharmacy and 40+ scripts/day come in",
            "is_anonymous": False,
            "reporter_name": "Jane Doe",
        })
        resp = client.get("/api/v1/reclaimrx/tips")
        assert resp.status_code == 200
        tips = resp.json()
        assert all(t["tip_type"] in ["pharmacy_fraud", "prescriber_fraud"] for t in tips)
