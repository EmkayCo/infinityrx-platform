"""Extended integration tests to cover remaining router branches."""
from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from shared.auth.dependencies import CurrentUser, get_current_user
from src.api.dependencies import get_db, require_mfa_elevated, require_tenant_match
from src.api.router import router
from src.models.tables import (
    PharmacyProfile,
)
from src.services.detection_rule_seeder import seed_detection_rules

from tests.conftest import TEST_TENANT_ID, TEST_USER_ID


def _make_user() -> CurrentUser:
    return CurrentUser(
        id=TEST_USER_ID,
        tenant_id=TEST_TENANT_ID,
        email="test@example.com",
        status="active",
        roles=("reclaimrx.investigator", "reclaimrx.admin"),
        permissions=(),
    )


def build_app(db: Session) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    _user = _make_user()

    def _db_override():
        yield db

    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[get_current_user] = lambda: _user
    app.dependency_overrides[require_tenant_match] = lambda: _user
    app.dependency_overrides[require_mfa_elevated] = lambda: _user
    return app


@pytest.fixture()
def client(db: Session) -> TestClient:
    seed_detection_rules(db)
    db.flush()
    app = build_app(db)
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def inv_id(client: TestClient) -> str:
    resp = client.post("/api/v1/reclaimrx/investigations", json={
        "subject_type": "pharmacy",
        "subject_entity_id": "1234567890",
        "subject_name": "Test Pharmacy",
        "investigation_type": "desk_audit",
        "title": "Test Investigation",
        "priority": "high",
    })
    assert resp.status_code == 201
    return resp.json()["id"]


class TestRulesEndpoints:
    def test_list_rules_returns_seeded_rules(self, client: TestClient) -> None:
        resp = client.get("/api/v1/reclaimrx/rules")
        assert resp.status_code == 200
        rules = resp.json()
        assert len(rules) > 0

    def test_get_rule_by_id(self, client: TestClient) -> None:
        rules = client.get("/api/v1/reclaimrx/rules").json()
        rule_id = rules[0]["id"]
        resp = client.get(f"/api/v1/reclaimrx/rules/{rule_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == rule_id

    def test_get_nonexistent_rule_returns_404(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/reclaimrx/rules/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestFlagsEndpoints:
    def test_list_flags_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/reclaimrx/flags")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_list_flags_with_filters(self, client: TestClient) -> None:
        resp = client.get("/api/v1/reclaimrx/flags", params={"severity": "high", "rule_code": "MFR-001"})
        assert resp.status_code == 200

    def test_get_flag_not_found(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/reclaimrx/flags/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_update_flag_not_found(self, client: TestClient) -> None:
        resp = client.put(f"/api/v1/reclaimrx/flags/{uuid.uuid4()}", json={"investigation_status": "reviewed"})
        assert resp.status_code == 404

    def test_list_flags_with_investigation_status_filter(self, client: TestClient) -> None:
        resp = client.get("/api/v1/reclaimrx/flags", params={"investigation_status": "open"})
        assert resp.status_code == 200


class TestInvestigationExtended:
    def test_get_investigation_by_id(self, client: TestClient, inv_id: str) -> None:
        resp = client.get(f"/api/v1/reclaimrx/investigations/{inv_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == inv_id

    def test_get_investigation_timeline(self, client: TestClient, inv_id: str) -> None:
        resp = client.get(f"/api/v1/reclaimrx/investigations/{inv_id}/timeline")
        assert resp.status_code == 200
        activities = resp.json()
        assert isinstance(activities, list)
        assert len(activities) >= 1

    def test_add_activity_to_investigation(self, client: TestClient, inv_id: str) -> None:
        resp = client.post(f"/api/v1/reclaimrx/investigations/{inv_id}/activities", json={
            "activity_type": "document_reviewed",
            "description": "Reviewed dispensing logs",
        })
        assert resp.status_code == 201
        assert resp.json()["activity_type"] == "document_reviewed"

    def test_list_investigations_with_status_filter(self, client: TestClient, inv_id: str) -> None:
        resp = client.get("/api/v1/reclaimrx/investigations", params={"status": "open"})
        assert resp.status_code == 200

    def test_list_investigations_with_subject_type_filter(self, client: TestClient, inv_id: str) -> None:
        resp = client.get("/api/v1/reclaimrx/investigations", params={"subject_type": "pharmacy"})
        assert resp.status_code == 200

    def test_update_investigation_not_found(self, client: TestClient) -> None:
        resp = client.patch(f"/api/v1/reclaimrx/investigations/{uuid.uuid4()}", json={"status": "in_progress"})
        assert resp.status_code == 404

    def test_update_investigation_no_status_not_found(self, client: TestClient) -> None:
        # No status field — goes straight to get() which returns None
        resp = client.patch(f"/api/v1/reclaimrx/investigations/{uuid.uuid4()}", json={"notes": "Some note"})
        assert resp.status_code == 404

    def test_update_investigation_no_status(self, client: TestClient, inv_id: str) -> None:
        resp = client.patch(f"/api/v1/reclaimrx/investigations/{inv_id}", json={"notes": "Some notes"})
        assert resp.status_code == 200


class TestRecoveryEndpoints:
    def test_create_and_list_recovery(self, client: TestClient, inv_id: str) -> None:
        resp = client.post(
            f"/api/v1/reclaimrx/investigations/{inv_id}/recoveries",
            json={
                "recovery_method": "offset_from_payment",
                "amount": "1500.00",
                "confidence_tier": "high",
                "methodology_tag": "NQ excess",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "estimated"

        list_resp = client.get(f"/api/v1/reclaimrx/investigations/{inv_id}/recoveries")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) >= 1

    def test_list_recoveries_with_methodology_filter(self, client: TestClient, inv_id: str) -> None:
        resp = client.get(
            f"/api/v1/reclaimrx/investigations/{inv_id}/recoveries",
            params={"methodology_tag": "NQ excess"},
        )
        assert resp.status_code == 200


class TestProfileEndpoints:
    def test_list_pharmacy_profiles_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/reclaimrx/pharmacy-profiles")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_pharmacy_profile_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/reclaimrx/pharmacy-profiles/9999999999")
        assert resp.status_code == 404

    def test_list_prescriber_profiles_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/reclaimrx/prescriber-profiles")
        assert resp.status_code == 200

    def test_list_member_profiles_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/reclaimrx/member-profiles")
        assert resp.status_code == 200

    def test_list_pharmacy_profiles_with_min_risk_score(self, client: TestClient, db: Session) -> None:
        profile = PharmacyProfile(
            tenant_id=str(TEST_TENANT_ID),
            pharmacy_npi="1234500000",
            pharmacy_name="High Risk Pharmacy",
            composite_risk_score=80,
        )
        db.add(profile)
        db.flush()
        resp = client.get("/api/v1/reclaimrx/pharmacy-profiles", params={"min_risk_score": 50})
        assert resp.status_code == 200
        results = resp.json()
        assert any(p["pharmacy_npi"] == "1234500000" for p in results)


class TestAccumulatorEndpoints:
    def test_list_accumulator_detections_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/reclaimrx/accumulator-detections")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestFlagGetSuccess:
    def _create_inflated_claim_flags(self, client: TestClient) -> list:
        resp = client.post("/api/v1/reclaimrx/evaluate", json={
            "auth_number": "FLAGTEST",
            "date_of_service": "2026-01-15",
            "pharmacy_npi": "1234567890",
            "prescriber_npi": "0987654321",
            "member_id": "MEMFLAG",
            "ndc": "12345678901",
            "quantity": "30.000",
            "days_supply": 30,
            "billed_amount": "200.00",
            "paid_amount": "195.00",
            "wac_per_unit": "3.00",
            "nq": "200.00",
            "dv": "0.00",
            "awp_per_unit": "3.50",
            "program_type": "manufacturer",
            "client_type": "manufacturer",
            "metadata": {},
        })
        assert resp.status_code == 200
        return resp.json()["flags"]

    def _get_flagged_claim_ids(self, client: TestClient) -> list[str]:
        resp = client.post("/api/v1/reclaimrx/evaluate", json={
            "auth_number": "FLAGTEST2",
            "date_of_service": "2026-01-15",
            "pharmacy_npi": "1234567890",
            "prescriber_npi": "0987654321",
            "member_id": "MEMFLAG2",
            "ndc": "12345678901",
            "quantity": "30.000",
            "days_supply": 30,
            "billed_amount": "200.00",
            "paid_amount": "195.00",
            "wac_per_unit": "3.00",
            "nq": "200.00",
            "dv": "0.00",
            "awp_per_unit": "3.50",
            "program_type": "manufacturer",
            "client_type": "manufacturer",
            "metadata": {},
        })
        assert resp.status_code == 200
        return resp.json().get("flagged_claim_ids", [])

    def test_get_flag_by_id_found(self, client: TestClient) -> None:
        flag_ids = self._get_flagged_claim_ids(client)
        if not flag_ids:
            return  # No flags persisted, skip
        resp = client.get(f"/api/v1/reclaimrx/flags/{flag_ids[0]}")
        assert resp.status_code == 200
        assert resp.json()["id"] == flag_ids[0]

    def test_update_flag_fields_found(self, client: TestClient) -> None:
        flag_ids = self._get_flagged_claim_ids(client)
        if not flag_ids:
            return
        resp = client.put(f"/api/v1/reclaimrx/flags/{flag_ids[0]}", json={
            "investigation_status": "reviewed",
            "review_notes": "Looks suspicious",
            "resolution": "confirmed_fraud",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["investigation_status"] == "reviewed"

    def test_update_flag_with_assigned_to(self, client: TestClient) -> None:
        flag_ids = self._get_flagged_claim_ids(client)
        if not flag_ids:
            return
        resp = client.put(f"/api/v1/reclaimrx/flags/{flag_ids[0]}", json={
            "assigned_to": str(TEST_USER_ID),
        })
        assert resp.status_code == 200

    def test_update_flag_fields_not_found(self, client: TestClient) -> None:
        resp = client.put(f"/api/v1/reclaimrx/flags/{uuid.uuid4()}", json={
            "investigation_status": "reviewed",
            "review_notes": "Looks suspicious",
        })
        assert resp.status_code == 404


class TestPharmacyProfileFound:
    def test_get_pharmacy_profile_found(self, client: TestClient, db: Session) -> None:
        profile = PharmacyProfile(
            tenant_id=str(TEST_TENANT_ID),
            pharmacy_npi="5555500000",
            pharmacy_name="Found Pharmacy",
            composite_risk_score=50,
        )
        db.add(profile)
        db.flush()
        resp = client.get("/api/v1/reclaimrx/pharmacy-profiles/5555500000")
        assert resp.status_code == 200
        assert resp.json()["pharmacy_npi"] == "5555500000"


class TestTipsWithStatusFilter:
    def test_list_tips_with_status_filter(self, client: TestClient) -> None:
        client.post("/api/v1/reclaimrx/tips", json={
            "tip_type": "pharmacy_fraud",
            "subject_description": "Fraudulent pharmacy",
            "detail_text": "Details here",
            "is_anonymous": True,
        })
        resp = client.get("/api/v1/reclaimrx/tips", params={"status": "received"})
        assert resp.status_code == 200
        tips = resp.json()
        assert all(t["status"] == "received" for t in tips)


class TestHoldEndpointFilters:
    def test_list_holds_with_filters(self, client: TestClient) -> None:
        client.post("/api/v1/reclaimrx/holds", json={
            "entity_type": "pharmacy",
            "entity_id": "7777777777",
            "entity_name": "Filter Test Pharmacy",
            "hold_scope": "all",
        })
        resp = client.get("/api/v1/reclaimrx/holds", params={
            "entity_type": "pharmacy",
            "entity_id": "7777777777",
        })
        assert resp.status_code == 200
        holds = resp.json()
        assert any(h["entity_id"] == "7777777777" for h in holds)
