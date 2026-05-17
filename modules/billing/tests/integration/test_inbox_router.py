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
            mock_logger.exception.assert_called_once()
            call_args = mock_logger.exception.call_args
            assert "billing.inbox.cycle_query_failed" in call_args[0][0], (
                f"Expected 'billing.inbox.cycle_query_failed' in log message, got: {call_args}"
            )
