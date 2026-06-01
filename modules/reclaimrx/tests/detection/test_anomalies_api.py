"""TDD tests for GET /api/v1/reclaimrx/anomalies endpoint.

Uses lazy imports to avoid `shared.auth.dependencies` (requires PyJWT) at
collection time. All auth/tenant deps are overridden via FastAPI
dependency_overrides using the `src._shim.auth.CurrentUser` dataclass.

Tests cover:
- Pagination (page/page_size params, default=50, max=200)
- Each filter dimension (finding_code, severity, status, entity_type,
  pharmacy_npi, prescriber_npi, ndc, data_source_run_id, min_amount,
  date_from/date_to)
- entity_type derivation (pharmacy/prescriber/unknown)
- Cross-tenant isolation (2 tenants, query A, assert zero B rows)
- Cache-Control: no-store header on every response
- Empty-DB returns []
- AnomalyRead response shape (all required fields, amounts as str)
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Use the shim CurrentUser — avoids importing shared.auth.dependencies at module
# level which triggers PyJWT import failure in this environment.
from src._shim.auth import CurrentUser

from src.api.dependencies import get_db, require_mfa_elevated, require_tenant_match
from src.api.router import router
from src.models.detection_run_models import Anomaly, DetectionRun

from tests.conftest import OTHER_TENANT_ID, TEST_TENANT_ID, TEST_USER_ID


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(tenant_id: uuid.UUID = TEST_TENANT_ID) -> CurrentUser:
    return CurrentUser(
        id=TEST_USER_ID,
        tenant_id=tenant_id,
        email="test@example.com",
        roles=["reclaimrx.investigator", "reclaimrx.admin"],
    )


def build_app(db: Session, tenant_id: uuid.UUID = TEST_TENANT_ID) -> FastAPI:
    """Build test FastAPI app with all auth dependencies overridden."""
    # Lazy import to avoid top-level PyJWT dependency
    from shared.auth.dependencies import get_current_user  # noqa: PLC0415

    app = FastAPI()
    app.include_router(router)
    _user = _make_user(tenant_id)

    def _db_override():
        yield db

    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[get_current_user] = lambda: _user
    app.dependency_overrides[require_tenant_match] = lambda: _user
    app.dependency_overrides[require_mfa_elevated] = lambda: _user
    return app


def _make_run(db: Session, tenant_id: uuid.UUID) -> DetectionRun:
    run = DetectionRun(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        data_source="csv_upload",
        run_label="test-run",
        status="completed",
        record_count=10,
        anomaly_count=0,
        resolution_stats={"data_quality": {"missing_pharmacy_npi": 0}},
        created_by=TEST_USER_ID,
    )
    db.add(run)
    db.flush()
    return run


def _make_anomaly(
    db: Session,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    *,
    finding_code: str = "MFR-001",
    severity: str = "high",
    status: str = "open",
    pharmacy_npi: str | None = "1234567890",
    prescriber_npi: str | None = None,
    ndc: str | None = "12345678901",
    amount_paid: Decimal = Decimal("100.00"),
    amount_billed: Decimal = Decimal("110.00"),
    recovery_amount: Decimal | None = Decimal("10.00"),
    date_of_service: date | None = date(2024, 1, 15),
    confidence: Decimal = Decimal("0.9000"),
    finding_summary: str = "Test finding",
) -> Anomaly:
    a = Anomaly(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        data_source="csv_upload",
        data_source_run_id=run_id,
        source_table="csv_upload_rows",
        source_row_id=uuid.uuid4(),
        detection_kind="rule",
        severity=severity,
        confidence=confidence,
        finding_code=finding_code,
        finding_summary=finding_summary,
        finding_details={},
        status=status,
        pharmacy_npi=pharmacy_npi,
        prescriber_npi=prescriber_npi,
        ndc=ndc,
        amount_paid=amount_paid,
        amount_billed=amount_billed,
        recovery_amount=recovery_amount,
        date_of_service=date_of_service,
    )
    db.add(a)
    db.flush()
    return a


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(db: Session) -> TestClient:
    app = build_app(db)
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def run(db: Session) -> DetectionRun:
    return _make_run(db, TEST_TENANT_ID)


# ---------------------------------------------------------------------------
# Tests: empty DB
# ---------------------------------------------------------------------------


class TestAnomaliesEmptyDb:
    def test_empty_returns_empty_list(self, client: TestClient) -> None:
        resp = client.get("/api/v1/reclaimrx/anomalies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_cache_control_no_store_on_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/reclaimrx/anomalies")
        assert resp.headers.get("cache-control") == "no-store"


# ---------------------------------------------------------------------------
# Tests: response shape
# ---------------------------------------------------------------------------


class TestAnomaliesResponseShape:
    def test_anomaly_read_fields_present(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(db, TEST_TENANT_ID, run.id, finding_code="MFR-001", severity="high")
        resp = client.get("/api/v1/reclaimrx/anomalies")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        item = items[0]
        required_fields = [
            "id",
            "finding_code",
            "finding_summary",
            "severity",
            "confidence",
            "status",
            "entity_type",
            "pharmacy_npi",
            "pharmacy_name",
            "prescriber_npi",
            "prescriber_name",
            "ndc",
            "amount_paid",
            "amount_billed",
            "recovery_amount",
            "date_of_service",
            "data_source_run_id",
            "created_at",
        ]
        for f in required_fields:
            assert f in item, f"Missing field: {f}"

    def test_amounts_serialized_as_str_not_float(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(
            db,
            TEST_TENANT_ID,
            run.id,
            amount_paid=Decimal("123.45"),
            amount_billed=Decimal("130.00"),
            recovery_amount=Decimal("6.55"),
        )
        resp = client.get("/api/v1/reclaimrx/anomalies")
        item = resp.json()["items"][0]
        # Must be strings (Decimal-safe), never raw floats
        assert isinstance(item["amount_paid"], str), "amount_paid must be str"
        assert isinstance(item["amount_billed"], str), "amount_billed must be str"
        assert isinstance(item["recovery_amount"], str), "recovery_amount must be str"
        assert item["amount_paid"] == "123.45"
        assert item["amount_billed"] == "130.00"
        assert item["recovery_amount"] == "6.55"

    def test_confidence_serialized_as_str(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(db, TEST_TENANT_ID, run.id, confidence=Decimal("0.9500"))
        resp = client.get("/api/v1/reclaimrx/anomalies")
        item = resp.json()["items"][0]
        assert isinstance(item["confidence"], str)

    def test_cache_control_no_store(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(db, TEST_TENANT_ID, run.id)
        resp = client.get("/api/v1/reclaimrx/anomalies")
        assert resp.headers.get("cache-control") == "no-store"


# ---------------------------------------------------------------------------
# Tests: entity_type derivation
# ---------------------------------------------------------------------------


class TestEntityTypeDerivation:
    def test_pharmacy_entity_when_pharmacy_npi_set(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(db, TEST_TENANT_ID, run.id, pharmacy_npi="1234567890", prescriber_npi=None)
        resp = client.get("/api/v1/reclaimrx/anomalies")
        assert resp.json()["items"][0]["entity_type"] == "pharmacy"

    def test_prescriber_entity_when_only_prescriber_npi(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(db, TEST_TENANT_ID, run.id, pharmacy_npi=None, prescriber_npi="9876543210")
        resp = client.get("/api/v1/reclaimrx/anomalies")
        assert resp.json()["items"][0]["entity_type"] == "prescriber"

    def test_unknown_entity_when_both_null(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(db, TEST_TENANT_ID, run.id, pharmacy_npi=None, prescriber_npi=None)
        resp = client.get("/api/v1/reclaimrx/anomalies")
        assert resp.json()["items"][0]["entity_type"] == "unknown"

    def test_pharmacy_entity_when_both_npis_set(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        # pharmacy_npi not null → entity_type = pharmacy (pharmacy takes priority)
        _make_anomaly(
            db, TEST_TENANT_ID, run.id, pharmacy_npi="1234567890", prescriber_npi="9876543210"
        )
        resp = client.get("/api/v1/reclaimrx/anomalies")
        assert resp.json()["items"][0]["entity_type"] == "pharmacy"


# ---------------------------------------------------------------------------
# Tests: filters
# ---------------------------------------------------------------------------


class TestAnomaliesFilters:
    def test_filter_finding_code(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(db, TEST_TENANT_ID, run.id, finding_code="MFR-001")
        _make_anomaly(db, TEST_TENANT_ID, run.id, finding_code="HP-005")
        resp = client.get("/api/v1/reclaimrx/anomalies?finding_code=MFR-001")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["finding_code"] == "MFR-001"

    def test_filter_finding_code_repeatable(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(db, TEST_TENANT_ID, run.id, finding_code="MFR-001")
        _make_anomaly(db, TEST_TENANT_ID, run.id, finding_code="HP-005")
        _make_anomaly(db, TEST_TENANT_ID, run.id, finding_code="ALL-001")
        resp = client.get("/api/v1/reclaimrx/anomalies?finding_code=MFR-001&finding_code=HP-005")
        data = resp.json()
        assert data["total"] == 2
        codes = {item["finding_code"] for item in data["items"]}
        assert codes == {"MFR-001", "HP-005"}

    def test_filter_severity(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(db, TEST_TENANT_ID, run.id, severity="high")
        _make_anomaly(db, TEST_TENANT_ID, run.id, severity="low")
        resp = client.get("/api/v1/reclaimrx/anomalies?severity=high")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["severity"] == "high"

    def test_filter_status(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(db, TEST_TENANT_ID, run.id, status="open")
        _make_anomaly(db, TEST_TENANT_ID, run.id, status="closed")
        resp = client.get("/api/v1/reclaimrx/anomalies?status=open")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "open"

    def test_filter_entity_type_pharmacy(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(db, TEST_TENANT_ID, run.id, pharmacy_npi="1234567890", prescriber_npi=None)
        _make_anomaly(db, TEST_TENANT_ID, run.id, pharmacy_npi=None, prescriber_npi="9876543210")
        resp = client.get("/api/v1/reclaimrx/anomalies?entity_type=pharmacy")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["entity_type"] == "pharmacy"

    def test_filter_entity_type_prescriber(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(db, TEST_TENANT_ID, run.id, pharmacy_npi="1234567890", prescriber_npi=None)
        _make_anomaly(db, TEST_TENANT_ID, run.id, pharmacy_npi=None, prescriber_npi="9876543210")
        resp = client.get("/api/v1/reclaimrx/anomalies?entity_type=prescriber")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["entity_type"] == "prescriber"

    def test_filter_entity_type_unknown(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(db, TEST_TENANT_ID, run.id, pharmacy_npi=None, prescriber_npi=None)
        _make_anomaly(db, TEST_TENANT_ID, run.id, pharmacy_npi="1234567890")
        resp = client.get("/api/v1/reclaimrx/anomalies?entity_type=unknown")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["entity_type"] == "unknown"

    def test_filter_pharmacy_npi(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(db, TEST_TENANT_ID, run.id, pharmacy_npi="1234567890")
        _make_anomaly(db, TEST_TENANT_ID, run.id, pharmacy_npi="9999999999")
        resp = client.get("/api/v1/reclaimrx/anomalies?pharmacy_npi=1234567890")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["pharmacy_npi"] == "1234567890"

    def test_filter_prescriber_npi(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(db, TEST_TENANT_ID, run.id, prescriber_npi="1111111111")
        _make_anomaly(db, TEST_TENANT_ID, run.id, prescriber_npi="2222222222")
        resp = client.get("/api/v1/reclaimrx/anomalies?prescriber_npi=1111111111")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["prescriber_npi"] == "1111111111"

    def test_filter_ndc(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(db, TEST_TENANT_ID, run.id, ndc="12345678901")
        _make_anomaly(db, TEST_TENANT_ID, run.id, ndc="99999999999")
        resp = client.get("/api/v1/reclaimrx/anomalies?ndc=12345678901")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["ndc"] == "12345678901"

    def test_filter_data_source_run_id(self, client: TestClient, db: Session) -> None:
        run1 = _make_run(db, TEST_TENANT_ID)
        run2 = _make_run(db, TEST_TENANT_ID)
        _make_anomaly(db, TEST_TENANT_ID, run1.id)
        _make_anomaly(db, TEST_TENANT_ID, run2.id)
        resp = client.get(f"/api/v1/reclaimrx/anomalies?data_source_run_id={run1.id}")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["data_source_run_id"] == str(run1.id)

    def test_filter_min_amount(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(db, TEST_TENANT_ID, run.id, amount_paid=Decimal("50.00"))
        _make_anomaly(db, TEST_TENANT_ID, run.id, amount_paid=Decimal("200.00"))
        resp = client.get("/api/v1/reclaimrx/anomalies?min_amount=100")
        data = resp.json()
        assert data["total"] == 1
        assert Decimal(data["items"][0]["amount_paid"]) >= Decimal("100")

    def test_filter_date_from(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(db, TEST_TENANT_ID, run.id, date_of_service=date(2024, 1, 1))
        _make_anomaly(db, TEST_TENANT_ID, run.id, date_of_service=date(2024, 6, 1))
        resp = client.get("/api/v1/reclaimrx/anomalies?date_from=2024-03-01")
        data = resp.json()
        assert data["total"] == 1

    def test_filter_date_to(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(db, TEST_TENANT_ID, run.id, date_of_service=date(2024, 1, 1))
        _make_anomaly(db, TEST_TENANT_ID, run.id, date_of_service=date(2024, 6, 1))
        resp = client.get("/api/v1/reclaimrx/anomalies?date_to=2024-03-01")
        data = resp.json()
        assert data["total"] == 1

    def test_filter_date_from_and_to(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(db, TEST_TENANT_ID, run.id, date_of_service=date(2024, 1, 1))
        _make_anomaly(db, TEST_TENANT_ID, run.id, date_of_service=date(2024, 4, 1))
        _make_anomaly(db, TEST_TENANT_ID, run.id, date_of_service=date(2024, 8, 1))
        resp = client.get(
            "/api/v1/reclaimrx/anomalies?date_from=2024-02-01&date_to=2024-06-01"
        )
        data = resp.json()
        assert data["total"] == 1

    def test_multiple_filters_and_combined(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        _make_anomaly(db, TEST_TENANT_ID, run.id, finding_code="MFR-001", severity="high")
        _make_anomaly(db, TEST_TENANT_ID, run.id, finding_code="MFR-001", severity="low")
        _make_anomaly(db, TEST_TENANT_ID, run.id, finding_code="HP-005", severity="high")
        resp = client.get("/api/v1/reclaimrx/anomalies?finding_code=MFR-001&severity=high")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["finding_code"] == "MFR-001"
        assert data["items"][0]["severity"] == "high"


# ---------------------------------------------------------------------------
# Tests: pagination
# ---------------------------------------------------------------------------


class TestAnomaliesPagination:
    def test_default_page_size_50(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        for i in range(60):
            _make_anomaly(db, TEST_TENANT_ID, run.id, finding_code=f"CODE-{i:03}")
        resp = client.get("/api/v1/reclaimrx/anomalies")
        data = resp.json()
        assert data["total"] == 60
        assert len(data["items"]) == 50

    def test_page_size_param(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        for i in range(10):
            _make_anomaly(db, TEST_TENANT_ID, run.id, finding_code=f"CODE-{i:03}")
        resp = client.get("/api/v1/reclaimrx/anomalies?page_size=5")
        data = resp.json()
        assert len(data["items"]) == 5
        assert data["total"] == 10

    def test_page_2(self, client: TestClient, db: Session, run: DetectionRun) -> None:
        for i in range(10):
            _make_anomaly(db, TEST_TENANT_ID, run.id, finding_code=f"CODE-{i:03}")
        resp = client.get("/api/v1/reclaimrx/anomalies?page=2&page_size=5")
        data = resp.json()
        assert len(data["items"]) == 5
        assert data["total"] == 10

    def test_page_size_max_200(self, client: TestClient) -> None:
        resp = client.get("/api/v1/reclaimrx/anomalies?page_size=201")
        assert resp.status_code == 422

    def test_page_size_zero_rejected(self, client: TestClient) -> None:
        resp = client.get("/api/v1/reclaimrx/anomalies?page_size=0")
        assert resp.status_code == 422

    def test_sort_created_at_desc(
        self, client: TestClient, db: Session, run: DetectionRun
    ) -> None:
        for i in range(3):
            _make_anomaly(db, TEST_TENANT_ID, run.id, finding_code=f"CODE-{i:03}")
        resp = client.get("/api/v1/reclaimrx/anomalies")
        items = resp.json()["items"]
        timestamps = [item["created_at"] for item in items]
        assert timestamps == sorted(timestamps, reverse=True)


# ---------------------------------------------------------------------------
# Tests: cross-tenant isolation
# ---------------------------------------------------------------------------


class TestAnomaliesCrossTenantIsolation:
    def test_zero_other_tenant_rows_returned(self, db: Session) -> None:
        """Query as tenant A; assert zero tenant B anomalies in response."""
        run_a = _make_run(db, TEST_TENANT_ID)
        run_b = _make_run(db, OTHER_TENANT_ID)

        for _ in range(3):
            _make_anomaly(db, TEST_TENANT_ID, run_a.id)
        for _ in range(5):
            _make_anomaly(db, OTHER_TENANT_ID, run_b.id)

        app = build_app(db, tenant_id=TEST_TENANT_ID)
        with TestClient(app, raise_server_exceptions=True) as c:
            resp = c.get("/api/v1/reclaimrx/anomalies")

        data = resp.json()
        assert data["total"] == 3, "Should only see tenant A rows"
        for item in data["items"]:
            assert item["data_source_run_id"] == str(run_a.id)

    def test_filter_by_run_id_cannot_leak_other_tenant(self, db: Session) -> None:
        """Passing another tenant's run_id returns 0 results (not a data leak)."""
        run_a = _make_run(db, TEST_TENANT_ID)
        run_b = _make_run(db, OTHER_TENANT_ID)
        _make_anomaly(db, TEST_TENANT_ID, run_a.id)
        _make_anomaly(db, OTHER_TENANT_ID, run_b.id)

        app = build_app(db, tenant_id=TEST_TENANT_ID)
        with TestClient(app, raise_server_exceptions=True) as c:
            resp = c.get(f"/api/v1/reclaimrx/anomalies?data_source_run_id={run_b.id}")

        assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# Tests: auth
# ---------------------------------------------------------------------------


class TestAnomaliesAuth:
    def test_requires_auth(self) -> None:
        app = FastAPI()
        app.include_router(router)
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/v1/reclaimrx/anomalies")
        assert resp.status_code in (401, 422)
