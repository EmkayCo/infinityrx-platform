"""Integration tests for payment-processing API endpoints."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.models.tables import (
    PayeeEnrollment,
    Settlement,
    Submission,
    VendorAdapter,
)

# Reuse fixtures from tests/conftest.py: db_session, default_user, reset_shims
TENANT_ID = "aaaaaaaa-0000-0000-0000-000000000001"


@pytest.fixture
def client(db_session: Session) -> TestClient:
    from src.app import app

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def vendor(db_session: Session) -> VendorAdapter:
    v = VendorAdapter(
        tenant_id=TENANT_ID,
        vendor_type="direct_ach",
        name="ACH Test Bank",
        connection_type="sftp",
        settlement_method="file_upload",
        supports_ach=True,
    )
    db_session.add(v)
    db_session.flush()
    return v


class TestHealthEndpoint:
    def test_health_is_reachable(self, client: TestClient):
        """Health endpoint must be mounted and return the contract schema."""
        resp = client.get("/health")
        # 200 = healthy/degraded, 503 = unhealthy (DB down in test env).
        assert resp.status_code in (200, 503)
        assert resp.json()["module"] == "payment-processing"
        assert resp.json()["status"] in ("healthy", "degraded", "unhealthy")


class TestVendorEndpoints:
    def test_list_vendors_empty(self, client: TestClient):
        resp = client.get("/api/v1/payments/vendors")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_vendor(self, client: TestClient):
        resp = client.post(
            "/api/v1/payments/vendors",
            json={
                "vendor_type": "direct_ach",
                "name": "Test ACH Vendor",
                "connection_type": "sftp",
                "settlement_method": "file_upload",
                "supports_ach": True,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["vendor_type"] == "direct_ach"
        assert data["tenant_id"] == TENANT_ID

    def test_create_vendor_required_fields(self, client: TestClient):
        resp = client.post(
            "/api/v1/payments/vendors",
            json={"vendor_type": "echo"},
        )
        assert resp.status_code == 422

    def test_update_vendor(self, client: TestClient, vendor: VendorAdapter):
        resp = client.put(
            f"/api/v1/payments/vendors/{vendor.id}",
            json={"name": "Updated ACH Bank"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated ACH Bank"

    def test_update_vendor_not_found(self, client: TestClient):
        resp = client.put(
            f"/api/v1/payments/vendors/{uuid.uuid4()}",
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404

    def test_vendor_health_empty(self, client: TestClient, vendor: VendorAdapter):
        resp = client.get(f"/api/v1/payments/vendors/{vendor.id}/health")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_vendor_response_has_tenant_id(self, client: TestClient, vendor: VendorAdapter):
        resp = client.get("/api/v1/payments/vendors")
        vendors = resp.json()
        for v in vendors:
            assert v["tenant_id"] == TENANT_ID


class TestSubmissionEndpoints:
    def _create_submission(self, db_session: Session, vendor: VendorAdapter) -> Submission:
        sub = Submission(
            tenant_id=TENANT_ID,
            vendor_adapter_id=vendor.id,
            billing_payment_batch_id=str(uuid.uuid4()),
            idempotency_key=str(uuid.uuid4()),
            submission_type="file",
            payment_count=5,
            total_amount=Decimal("500.00"),
            status="submitted",
        )
        db_session.add(sub)
        db_session.flush()
        return sub

    def test_list_submissions_empty(self, client: TestClient):
        resp = client.get("/api/v1/payments/submissions")
        assert resp.status_code == 200

    def test_get_submission_by_id(self, client: TestClient, db_session: Session, vendor: VendorAdapter):
        sub = self._create_submission(db_session, vendor)
        resp = client.get(f"/api/v1/payments/submissions/{sub.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == sub.id
        assert data["tenant_id"] == TENANT_ID

    def test_get_submission_not_found(self, client: TestClient):
        resp = client.get(f"/api/v1/payments/submissions/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_retry_failed_submission(self, client: TestClient, db_session: Session, vendor: VendorAdapter):
        sub = Submission(
            tenant_id=TENANT_ID,
            vendor_adapter_id=vendor.id,
            billing_payment_batch_id=str(uuid.uuid4()),
            idempotency_key=str(uuid.uuid4()),
            submission_type="file",
            payment_count=1,
            total_amount=Decimal("100.00"),
            status="failed",
            retry_count=0,
            max_retries=3,
        )
        db_session.add(sub)
        db_session.flush()
        resp = client.post(f"/api/v1/payments/submissions/{sub.id}/retry")
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    def test_retry_non_failed_submission_422(self, client: TestClient, db_session: Session, vendor: VendorAdapter):
        sub = self._create_submission(db_session, vendor)
        resp = client.post(f"/api/v1/payments/submissions/{sub.id}/retry")
        assert resp.status_code == 422

    def test_submission_amounts_are_decimal_strings(
        self, client: TestClient, db_session: Session, vendor: VendorAdapter
    ):
        self._create_submission(db_session, vendor)
        resp = client.get("/api/v1/payments/submissions")
        data = resp.json()
        if data:
            assert isinstance(data[0]["total_amount"], str)


class TestSettlementEndpoints:
    def _create_settlement(self, db_session: Session, vendor: VendorAdapter) -> Settlement:
        sub = Submission(
            tenant_id=TENANT_ID,
            vendor_adapter_id=vendor.id,
            billing_payment_batch_id=str(uuid.uuid4()),
            idempotency_key=str(uuid.uuid4()),
            submission_type="file",
            payment_count=1,
            total_amount=Decimal("100.00"),
            status="submitted",
        )
        db_session.add(sub)
        db_session.flush()

        settle = Settlement(
            tenant_id=TENANT_ID,
            submission_id=sub.id,
            billing_payment_id=str(uuid.uuid4()),
            pay_to_entity_id=str(uuid.uuid4()),
            amount=Decimal("100.00"),
            status="pending",
        )
        db_session.add(settle)
        db_session.flush()
        return settle

    def test_list_settlements(self, client: TestClient):
        resp = client.get("/api/v1/payments/settlements")
        assert resp.status_code == 200

    def test_pending_settlements(self, client: TestClient, db_session: Session, vendor: VendorAdapter):
        self._create_settlement(db_session, vendor)
        resp = client.get("/api/v1/payments/settlements/pending")
        assert resp.status_code == 200
        data = resp.json()
        assert all(s["status"] == "pending" for s in data)

    def test_manual_settlement(self, client: TestClient, db_session: Session, vendor: VendorAdapter):
        settle = self._create_settlement(db_session, vendor)
        resp = client.post(
            f"/api/v1/payments/settlements/{settle.id}/manual",
            json={
                "settlement_date": "2026-04-15",
                "settlement_reference": "MANUAL-REF-001",
                "payment_method_used": "check",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "settled"

    def test_manual_settlement_not_found(self, client: TestClient):
        resp = client.post(
            f"/api/v1/payments/settlements/{uuid.uuid4()}/manual",
            json={
                "settlement_date": "2026-04-15",
                "settlement_reference": "REF",
                "payment_method_used": "ach",
            },
        )
        assert resp.status_code == 404


class TestReturnEndpoints:
    def test_list_returns_empty(self, client: TestClient):
        resp = client.get("/api/v1/payments/returns")
        assert resp.status_code == 200

    def test_get_return_codes(self, client: TestClient):
        resp = client.get("/api/v1/payments/returns/codes")
        assert resp.status_code == 200
        codes = resp.json()
        assert len(codes) >= 50
        r01 = next(c for c in codes if c["code"] == "R01")
        assert r01["is_retryable"] is True

    def test_record_manual_return(self, client: TestClient):
        resp = client.post(
            "/api/v1/payments/returns",
            json={
                "billing_payment_id": str(uuid.uuid4()),
                "return_code": "R02",
                "return_date": "2026-04-16",
                "amount": "250.00",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["return_code"] == "R02"
        assert data["status"] == "returned"

    def test_record_return_invalid_code(self, client: TestClient):
        resp = client.post(
            "/api/v1/payments/returns",
            json={
                "billing_payment_id": str(uuid.uuid4()),
                "return_code": "R99",
                "return_date": "2026-04-16",
                "amount": "100.00",
            },
        )
        assert resp.status_code == 422


class TestEnrollmentEndpoints:
    def test_list_enrollments_empty(self, client: TestClient):
        resp = client.get("/api/v1/payments/enrollments")
        assert resp.status_code == 200

    def test_initiate_enrollment(self, client: TestClient, vendor: VendorAdapter):
        entity_id = str(uuid.uuid4())
        resp = client.post(
            f"/api/v1/payments/enrollments/{entity_id}/enroll",
            params={"vendor_adapter_id": vendor.id},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["enrollment_status"] == "pending"
        assert data["pay_to_entity_id"] == entity_id

    def test_unenrolled_pharmacies(self, client: TestClient, db_session: Session, vendor: VendorAdapter):
        enroll = PayeeEnrollment(
            tenant_id=TENANT_ID,
            vendor_adapter_id=vendor.id,
            pay_to_entity_id=str(uuid.uuid4()),
            enrollment_status="not_enrolled",
        )
        db_session.add(enroll)
        db_session.flush()
        resp = client.get("/api/v1/payments/enrollments/unenrolled")
        assert resp.status_code == 200
        assert any(e["enrollment_status"] == "not_enrolled" for e in resp.json())


class TestDashboardEndpoints:
    def test_dashboard_returns_summary(self, client: TestClient):
        resp = client.get("/api/v1/payments/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_submitted_30d" in data
        assert "vendor_statuses" in data

    def test_reconciliation_returns_list(self, client: TestClient):
        resp = client.get("/api/v1/payments/dashboard/reconciliation")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestRouterCoveragePaths:
    """Tests for previously uncovered router branches."""

    def test_update_vendor_with_failover_chain(self, client: TestClient, vendor: VendorAdapter):
        resp = client.put(
            f"/api/v1/payments/vendors/{vendor.id}",
            json={"failover_chain": ["vendor-id-2", "vendor-id-3"]},
        )
        assert resp.status_code == 200

    def test_list_submissions_with_status_filter(self, client: TestClient, db_session: Session, vendor: VendorAdapter):
        sub = Submission(
            tenant_id=TENANT_ID,
            vendor_adapter_id=vendor.id,
            billing_payment_batch_id=str(uuid.uuid4()),
            idempotency_key=str(uuid.uuid4()),
            submission_type="file",
            payment_count=1,
            total_amount="100.00",
            status="submitted",
        )
        db_session.add(sub)
        db_session.flush()
        resp = client.get("/api/v1/payments/submissions?status_filter=submitted")
        assert resp.status_code == 200
        data = resp.json()
        assert all(s["status"] == "submitted" for s in data)

    def test_retry_submission_not_found(self, client: TestClient):
        resp = client.post(f"/api/v1/payments/submissions/{uuid.uuid4()}/retry")
        assert resp.status_code == 404

    def test_retry_submission_max_retries_exhausted(self, client: TestClient, db_session: Session, vendor: VendorAdapter):
        sub = Submission(
            tenant_id=TENANT_ID,
            vendor_adapter_id=vendor.id,
            billing_payment_batch_id=str(uuid.uuid4()),
            idempotency_key=str(uuid.uuid4()),
            submission_type="file",
            payment_count=1,
            total_amount="100.00",
            status="failed",
            retry_count=3,
            max_retries=3,
        )
        db_session.add(sub)
        db_session.flush()
        resp = client.post(f"/api/v1/payments/submissions/{sub.id}/retry")
        assert resp.status_code == 422

    def test_list_settlements_with_status_filter(self, client: TestClient, db_session: Session, vendor: VendorAdapter):
        sub = Submission(
            tenant_id=TENANT_ID,
            vendor_adapter_id=vendor.id,
            billing_payment_batch_id=str(uuid.uuid4()),
            idempotency_key=str(uuid.uuid4()),
            submission_type="file",
            payment_count=1,
            total_amount="100.00",
            status="submitted",
        )
        db_session.add(sub)
        db_session.flush()
        from decimal import Decimal as D
        settle = Settlement(
            tenant_id=TENANT_ID,
            submission_id=sub.id,
            billing_payment_id=str(uuid.uuid4()),
            pay_to_entity_id=str(uuid.uuid4()),
            amount=D("100.00"),
            status="settled",
        )
        db_session.add(settle)
        db_session.flush()
        resp = client.get("/api/v1/payments/settlements?status_filter=settled")
        assert resp.status_code == 200
        data = resp.json()
        assert all(s["status"] == "settled" for s in data)

    def test_record_return_for_existing_settlement(self, client: TestClient, db_session: Session, vendor: VendorAdapter):
        billing_id = str(uuid.uuid4())
        sub = Submission(
            tenant_id=TENANT_ID,
            vendor_adapter_id=vendor.id,
            billing_payment_batch_id=str(uuid.uuid4()),
            idempotency_key=str(uuid.uuid4()),
            submission_type="file",
            payment_count=1,
            total_amount="100.00",
            status="submitted",
        )
        db_session.add(sub)
        db_session.flush()
        from decimal import Decimal as D
        settle = Settlement(
            tenant_id=TENANT_ID,
            submission_id=sub.id,
            billing_payment_id=billing_id,
            pay_to_entity_id=str(uuid.uuid4()),
            amount=D("100.00"),
            status="pending",
        )
        db_session.add(settle)
        db_session.flush()
        resp = client.post(
            "/api/v1/payments/returns",
            json={
                "billing_payment_id": billing_id,
                "return_code": "R01",
                "return_date": "2026-04-16",
                "amount": "100.00",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "returned"

    def test_return_codes_from_db(self, client: TestClient, db_session: Session):
        from src.models.tables import AchReturnCode
        db_session.add(AchReturnCode(
            code="R01",
            description="Insufficient Funds",
            category="admin",
            is_retryable=True,
            default_action="retry",
            retry_delay_days=3,
            triggers_fwa_alert=False,
        ))
        db_session.flush()
        resp = client.get("/api/v1/payments/returns/codes")
        assert resp.status_code == 200

    def test_re_enroll_existing_entity(self, client: TestClient, db_session: Session, vendor: VendorAdapter):
        entity_id = str(uuid.uuid4())
        from src.models.tables import PayeeEnrollment
        enroll = PayeeEnrollment(
            tenant_id=TENANT_ID,
            vendor_adapter_id=vendor.id,
            pay_to_entity_id=entity_id,
            enrollment_status="not_enrolled",
        )
        db_session.add(enroll)
        db_session.flush()
        resp = client.post(
            f"/api/v1/payments/enrollments/{entity_id}/enroll",
            params={"vendor_adapter_id": vendor.id},
        )
        assert resp.status_code == 201
        assert resp.json()["enrollment_status"] == "pending"
