"""Integration tests for Inbox router (Task 3 — Plan B).

Covers:
- Inbox returns items derived from DB state (uploads + batches)
- Auth gate: no token → 401
- Cross-tenant isolation
"""

from __future__ import annotations

import datetime
import uuid
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

TENANT_A = str(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1"))
TENANT_B = str(uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1"))
USER_OP = uuid.UUID("11111111-1111-1111-1111-111111111112")

OPERATOR_USER = MagicMock(
    id=USER_OP,
    tenant_id=uuid.UUID(TENANT_A),
    roles=("operator",),
    has_role=lambda r: r == "operator",
)


@pytest.fixture(scope="module")
def _engine():
    from src.models.tables import BillingBase

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in BillingBase.metadata.tables.values():
        table.schema = None
    BillingBase.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def _session_factory(_engine):
    return sessionmaker(bind=_engine, expire_on_commit=False)


@pytest.fixture()
def _client(_engine, _session_factory):
    from src.api.dependencies import get_db
    from src.db.session import set_engine
    from src.main import app

    set_engine(_engine)

    def override_db() -> Iterator[Session]:
        session = _session_factory()
        try:
            yield session
            session.rollback()
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# ── Auth gate ─────────────────────────────────────────────────────────────────

class TestInboxAuthGate:
    def test_inbox_no_auth_returns_401(self, _client):
        resp = _client.get("/api/v1/billing/inbox", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 401


# ── Inbox item derivation ─────────────────────────────────────────────────────

class TestInboxItems:
    def test_inbox_returns_upload_pending_review_for_validation_failed(
        self, _client, _engine, _session_factory
    ):
        """Upload with status=validation_failed → upload_pending_review item in inbox."""
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.tables import Upload, UploadStatus

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER

        session = _session_factory()
        upload_id = uuid.uuid4()
        try:
            u = Upload(
                id=upload_id,
                tenant_id=uuid.UUID(TENANT_A),
                filename="fail.csv",
                sha256="f" * 64,
                file_size=50,
                mime_type="text/csv",
                uploaded_by=USER_OP,
                uploaded_at=datetime.datetime.now(datetime.timezone.utc),
                status=UploadStatus.validation_failed.value,
                row_count=5,
                error_count=5,
                row_errors=[{"row": 1, "field": "ndc", "message": "invalid NDC"}],
            )
            session.add(u)
            session.commit()
        finally:
            session.close()

        resp = _client.get(
            "/api/v1/billing/inbox",
            params={"role": "operator"},
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        items = resp.json()
        kinds = [i["kind"] for i in items]
        assert "upload_pending_review" in kinds

    def test_inbox_returns_upload_validated_for_validated_status(
        self, _client, _engine, _session_factory
    ):
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.tables import Upload, UploadStatus

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER

        session = _session_factory()
        upload_id = uuid.uuid4()
        try:
            u = Upload(
                id=upload_id,
                tenant_id=uuid.UUID(TENANT_A),
                filename="good.csv",
                sha256="a" * 63 + "2",
                file_size=50,
                mime_type="text/csv",
                uploaded_by=USER_OP,
                uploaded_at=datetime.datetime.now(datetime.timezone.utc),
                status=UploadStatus.validated.value,
                row_count=10,
                error_count=0,
                row_errors=[],
            )
            session.add(u)
            session.commit()
        finally:
            session.close()

        resp = _client.get(
            "/api/v1/billing/inbox",
            params={"role": "operator"},
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        items = resp.json()
        kinds = [i["kind"] for i in items]
        assert "upload_validated_awaiting_batching" in kinds


# ── Cross-tenant isolation ────────────────────────────────────────────────────

class TestInboxCrossTenant:
    def test_inbox_does_not_return_tenant_b_items(self, _client, _engine, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.tables import Upload, UploadStatus

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER

        session = _session_factory()
        b_upload_id = uuid.uuid4()
        try:
            u = Upload(
                id=b_upload_id,
                tenant_id=uuid.UUID(TENANT_B),
                filename="b_secret.csv",
                sha256="9" * 64,
                file_size=50,
                mime_type="text/csv",
                uploaded_by=uuid.uuid4(),
                uploaded_at=datetime.datetime.now(datetime.timezone.utc),
                status=UploadStatus.validation_failed.value,
                row_count=1,
                error_count=1,
            )
            session.add(u)
            session.commit()
        finally:
            session.close()

        resp = _client.get(
            "/api/v1/billing/inbox",
            params={"role": "operator"},
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        upload_ids = [i.get("upload_id") for i in resp.json()]
        assert str(b_upload_id) not in upload_ids


# ── Inbox envelope contract (P2-inbox-envelope fix) ───────────────────────────


class TestInboxEnvelope:
    """InboxItemSchema requires id, tenant_id, rbac_required, created_at, payload."""

    def test_inbox_item_has_required_contract_fields(
        self, _client, _engine, _session_factory
    ):
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.tables import Upload, UploadStatus

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER

        session = _session_factory()
        upload_id = uuid.uuid4()
        try:
            u = Upload(
                id=upload_id,
                tenant_id=uuid.UUID(TENANT_A),
                filename="envelope_test.csv",
                sha256="e" * 63 + "3",
                file_size=50,
                mime_type="text/csv",
                uploaded_by=USER_OP,
                uploaded_at=datetime.datetime.now(datetime.timezone.utc),
                status=UploadStatus.validation_failed.value,
                row_count=1,
                error_count=1,
                row_errors=[],
            )
            session.add(u)
            session.commit()
        finally:
            session.close()

        resp = _client.get(
            "/api/v1/billing/inbox",
            params={"role": "operator"},
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        assert resp.headers.get("cache-control") == "no-store"

        items = resp.json()
        matching = [i for i in items if i.get("upload_id") == str(upload_id)]
        assert matching, "expected inbox item for this upload"
        item = matching[0]

        # P2-inbox-envelope: InboxItemSchema required fields
        assert "id" in item, "missing id"
        assert "tenant_id" in item, "missing tenant_id"
        assert "rbac_required" in item, "missing rbac_required — items disappear from UI"
        assert "created_at" in item, "missing created_at"
        assert "payload" in item, "missing payload object"
        assert isinstance(item["payload"], dict)
        assert item["rbac_required"] in ("operator", "approver", "auditor")
        assert item["kind"] == "upload_pending_review"


class TestInboxCycleQueryErrorLogging:
    """C4: bare except: pass in cycle query must log the exception."""

    def test_cycle_query_exception_is_logged_not_swallowed(self, _client):
        """C4: When the PaymentBatch query raises, inbox must log the exception
        at ERROR level (logger.exception) and still return a 200 with the
        upload items collected before the error -- not silently drop the error.
        """
        from unittest.mock import MagicMock, patch

        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER

        with patch("src.api.inbox.logger") as mock_logger:
            # Patch db.execute inside the route to raise on the third call
            # (first two are for Upload queries; third is PaymentBatch pending_close)
            original_execute_calls = []

            def _failing_execute(stmt, *args, **kwargs):
                # Let the first two Upload selects through; raise on PaymentBatch
                import sqlalchemy
                compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
                if "payment_batch" in compiled.lower():
                    raise RuntimeError("simulated PaymentBatch query failure")
                # Fall through — but we need the real session here.
                # This test just verifies logger.exception is called, not the
                # full data path, so return an empty result for upload queries.
                mock_result = MagicMock()
                mock_result.scalars.return_value.all.return_value = []
                return mock_result

            with patch("sqlalchemy.orm.Session.execute", side_effect=_failing_execute):
                resp = _client.get(
                    "/api/v1/billing/inbox",
                    headers={"X-Tenant-Id": TENANT_A},
                    params={"role": "operator"},
                )

            # Must still return 200 (best-effort degraded response)
            assert resp.status_code == 200, resp.text
            # Must have logged the exception
            # Plan C adds multiple try/except blocks hitting payment_batch tables;
            # at least one billing.inbox.* exception log is required.
            assert mock_logger.exception.call_count >= 1, "logger.exception was never called"
            all_msgs = [c[0][0] for c in mock_logger.exception.call_args_list]
            assert any("billing.inbox." in m for m in all_msgs), f"No billing.inbox.* log found: {all_msgs}"

# -- Plan C Task 7: 6 new inbox kinds -----------------------------------------


class TestInboxPlanCKinds:
    def test_inbox_returns_batch_drafted_for_generated_batch(
        self, _client, _engine, _session_factory
    ):
        import decimal
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.tables import PaymentBatch

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        session = _session_factory()
        batch_id = uuid.uuid4()
        try:
            b = PaymentBatch(
                id=batch_id,
                tenant_id=uuid.UUID(TENANT_A),
                batch_number="BATCH-DRAFT-T7",
                payment_route="ach",
                total_amount=decimal.Decimal("1000.00"),
                payment_count=5,
                ap_count=5,
                status="generated",
                generated_at=datetime.datetime.now(datetime.timezone.utc),
                created_at=datetime.datetime.now(datetime.timezone.utc),
                updated_at=datetime.datetime.now(datetime.timezone.utc),
            )
            session.add(b)
            session.commit()
        finally:
            session.close()
        resp = _client.get("/api/v1/billing/inbox", params={"role": "approver"}, headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        assert "batch_drafted" in [i["kind"] for i in resp.json()]

    def test_inbox_returns_ar_invoice_draft_for_draft_invoice(
        self, _client, _engine, _session_factory
    ):
        import decimal
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.tables import Invoice

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        session = _session_factory()
        inv_id = uuid.uuid4()
        now = datetime.datetime.now(datetime.timezone.utc)
        try:
            inv = Invoice(
                id=inv_id,
                tenant_id=uuid.UUID(TENANT_A),
                invoice_number="INV-DRAFT-T7",
                invoice_type="client_billing",
                client_id=uuid.uuid4(),
                client_name="Test Client",
                period_start=datetime.date(2026, 5, 1),
                period_end=datetime.date(2026, 5, 31),
                claims_subtotal=decimal.Decimal("10000.00"),
                fees_subtotal=decimal.Decimal("500.00"),
                adjustments=decimal.Decimal("0.00"),
                late_fees=decimal.Decimal("0.00"),
                total=decimal.Decimal("10500.00"),
                paid_amount=decimal.Decimal("0.00"),
                claim_count=100,
                status="draft",
                payment_terms_days=30,
                created_at=now,
                updated_at=now,
            )
            session.add(inv)
            session.commit()
        finally:
            session.close()
        resp = _client.get("/api/v1/billing/inbox", params={"role": "approver"}, headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        assert "ar_invoice_draft" in [i["kind"] for i in resp.json()]

    def test_inbox_returns_carryover_open_for_unresolved_carryover(
        self, _client, _engine, _session_factory
    ):
        import decimal
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.tables import APRecord, Carryover, ClaimRecord

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        session = _session_factory()
        claim_id = uuid.uuid4()
        ap_id = uuid.uuid4()
        co_id = uuid.uuid4()
        now = datetime.datetime.now(datetime.timezone.utc)
        try:
            claim = ClaimRecord(
                id=claim_id,
                tenant_id=uuid.UUID(TENANT_A),
                source_type="upload",
                auth_number="AUTH-T7-" + claim_id.hex[:8],
                claim_type="pharmacy",
                pharmacy_npi="1234567890",
                date_of_service=datetime.date(2026, 5, 1),
                date_received=now,
                net_amount=decimal.Decimal("100.00"),
                created_at=now,
            )
            session.add(claim)
            session.flush()
            ap = APRecord(
                id=ap_id,
                tenant_id=uuid.UUID(TENANT_A),
                claim_record_id=claim_id,
                client_id=uuid.uuid4(),
                pay_to_entity_id=uuid.uuid4(),
                pay_to_entity_name="Test Pharmacy",
                amount=decimal.Decimal("100.00"),
                payment_route="ach",
                created_at=now,
                updated_at=now,
            )
            session.add(ap)
            session.flush()
            co = Carryover(
                id=co_id,
                tenant_id=uuid.UUID(TENANT_A),
                ap_record_id=ap_id,
                amount=decimal.Decimal("100.00"),
                reason="vendor_hold",
                resolved=False,
                created_at=now,
                updated_at=now,
            )
            session.add(co)
            session.commit()
        finally:
            session.close()
        resp = _client.get("/api/v1/billing/inbox", params={"role": "operator"}, headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        assert "carryover_open" in [i["kind"] for i in resp.json()]

    def test_inbox_batch_drafted_has_required_envelope_fields(self, _client, _engine, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get("/api/v1/billing/inbox", params={"role": "approver"}, headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        items = resp.json()
        drafted = [i for i in items if i.get("kind") == "batch_drafted"]
        assert drafted, "expected at least one batch_drafted item"
        item = drafted[0]
        for field in ["id", "tenant_id", "rbac_required", "created_at", "payload"]:
            assert field in item, f"missing {field}"
        assert item["rbac_required"] == "approver"
        assert isinstance(item["payload"], dict)

    def test_inbox_plan_c_returns_200(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get("/api/v1/billing/inbox", params={"role": "approver"}, headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200

    def test_inbox_carryover_open_cross_tenant_isolation(self, _client, _engine, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get("/api/v1/billing/inbox", params={"role": "operator"}, headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        for item in resp.json():
            if item.get("kind") == "carryover_open":
                assert item["tenant_id"] == TENANT_A


# -- Plan B5: 3 remaining inbox kinds (ap_payment_run_held, banking_discrepancy, reconciliation_pending) --


class TestInboxPlanB5Kinds:
    def test_inbox_returns_ap_payment_run_held_for_held_batch(
        self, _client, _engine, _session_factory
    ):
        """PaymentBatch status=held -> ap_payment_run_held inbox item."""
        import decimal
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.tables import PaymentBatch

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        session = _session_factory()
        batch_id = uuid.uuid4()
        now = datetime.datetime.now(datetime.timezone.utc)
        try:
            b = PaymentBatch(
                id=batch_id,
                tenant_id=uuid.UUID(TENANT_A),
                batch_number="BATCH-HELD-B5",
                payment_route="ach",
                total_amount=decimal.Decimal("5000.00"),
                payment_count=10,
                ap_count=10,
                status="held",
                generated_at=now,
                created_at=now,
                updated_at=now,
            )
            session.add(b)
            session.commit()
        finally:
            session.close()
        resp = _client.get("/api/v1/billing/inbox", params={"role": "approver"}, headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        kinds = [i["kind"] for i in resp.json()]
        assert "ap_payment_run_held" in kinds, f"expected ap_payment_run_held, got kinds: {kinds}"

    def test_inbox_ap_payment_run_held_has_required_envelope_fields(
        self, _client, _engine, _session_factory
    ):
        """ap_payment_run_held item must carry the full InboxItemSchema envelope."""
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get("/api/v1/billing/inbox", params={"role": "approver"}, headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        items = resp.json()
        held = [i for i in items if i.get("kind") == "ap_payment_run_held"]
        assert held, "expected at least one ap_payment_run_held item"
        item = held[0]
        for field in ["id", "kind", "tenant_id", "upload_id", "rbac_required", "created_at", "priority", "payload"]:
            assert field in item, f"missing envelope field: {field}"
        assert item["rbac_required"] == "approver"
        assert isinstance(item["payload"], dict)
        assert "batch_id" in item["payload"]

    def test_inbox_ap_payment_run_held_cross_tenant_isolation(
        self, _client, _engine, _session_factory
    ):
        """ap_payment_run_held items must never leak across tenants."""
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get("/api/v1/billing/inbox", params={"role": "approver"}, headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        for item in resp.json():
            if item.get("kind") == "ap_payment_run_held":
                assert item["tenant_id"] == TENANT_A

    def test_inbox_banking_discrepancy_deferred_not_present(self, _client):
        """banking_discrepancy is deferred (no BankSettlement ORM); must not appear."""
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get("/api/v1/billing/inbox", params={"role": "approver"}, headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        kinds = [i["kind"] for i in resp.json()]
        assert "banking_discrepancy" not in kinds, (
            "banking_discrepancy must be deferred until BankSettlement ORM is added in Plan D"
        )

    def test_inbox_reconciliation_pending_deferred_not_present(self, _client):
        """reconciliation_pending is deferred (no Reconciliation ORM); must not appear."""
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get("/api/v1/billing/inbox", params={"role": "approver"}, headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        kinds = [i["kind"] for i in resp.json()]
        assert "reconciliation_pending" not in kinds, (
            "reconciliation_pending must be deferred until Reconciliation ORM is added in Plan D"
        )

