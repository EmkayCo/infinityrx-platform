"""Integration tests for Upload router (SP-1 Plan B Task 3).

Covers:
  - Auth gate (no token -> 401) for every endpoint
  - RBAC: Operator + Approver may create/supersede; Auditor -> 403
  - Real parse path end-to-end (no mocked parse_upload) -- proves router
    invokes the real service contract, not just a mock
  - Duplicate SHA-256 -> 409 with existing upload id and Cache-Control: no-store
  - Cross-tenant isolation: Tenant A cannot see/read/supersede Tenant B
  - PHI controls: _emit_phi_audit called on GET /{id} and GET /{id}/claims;
    Cache-Control: no-store on every detail response
"""

from __future__ import annotations

import datetime
import io
import uuid
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

TENANT_A = str(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
TENANT_B = str(uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))
USER_OP = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_APP = uuid.UUID("22222222-2222-2222-2222-222222222222")
USER_AUD = uuid.UUID("33333333-3333-3333-3333-333333333333")

OPERATOR_USER = MagicMock(
    id=USER_OP,
    tenant_id=uuid.UUID(TENANT_A),
    roles=("operator",),
    has_role=lambda r: r == "operator",
)
APPROVER_USER = MagicMock(
    id=USER_APP,
    tenant_id=uuid.UUID(TENANT_A),
    roles=("approver",),
    has_role=lambda r: r == "approver",
)
AUDITOR_USER = MagicMock(
    id=USER_AUD,
    tenant_id=uuid.UUID(TENANT_A),
    roles=("auditor",),
    has_role=lambda r: r == "auditor",
)


def _csv(claim_id: str = "CLM001") -> bytes:
    """Generate a VALID single-row CSV. Vary claim_id to get a unique sha256."""
    return (
        b"ndc,npi,claim_id,date_of_service,quantity,days_supply,amount_billed,member_id\n"
        + f"00093310305,1234567893,{claim_id},2026-01-15,1.000,30,99.9900,MBR001\n".encode()
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
def _client(_engine, _session_factory, tmp_path, monkeypatch):
    from src.api.dependencies import get_db
    from src.db.session import set_engine
    from src.main import app

    set_engine(_engine)
    monkeypatch.setenv("PAYSYNC_UPLOAD_DIR", str(tmp_path / "uploads"))

    def override_db() -> Iterator[Session]:
        session = _session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _multipart_file(content: bytes | None = None, filename: str = "test.csv"):
    return {"file": (filename, io.BytesIO(content if content is not None else _csv()), "text/csv")}


# -- Auth gate tests (no token -> 401) ------------------------------------


class TestAuthGate:
    def test_post_uploads_no_auth_401(self, _client):
        resp = _client.post(
            "/api/v1/billing/uploads",
            headers={"X-Tenant-Id": TENANT_A},
            files=_multipart_file(),
        )
        assert resp.status_code == 401

    def test_get_uploads_no_auth_401(self, _client):
        resp = _client.get(
            "/api/v1/billing/uploads", headers={"X-Tenant-Id": TENANT_A}
        )
        assert resp.status_code == 401

    def test_get_upload_by_id_no_auth_401(self, _client):
        fake_id = str(uuid.uuid4())
        resp = _client.get(
            f"/api/v1/billing/uploads/{fake_id}",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 401

    def test_get_upload_claims_no_auth_401(self, _client):
        fake_id = str(uuid.uuid4())
        resp = _client.get(
            f"/api/v1/billing/uploads/{fake_id}/claims",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 401

    def test_post_supersede_no_auth_401(self, _client):
        fake_id = str(uuid.uuid4())
        resp = _client.post(
            f"/api/v1/billing/uploads/{fake_id}/supersede",
            headers={"X-Tenant-Id": TENANT_A},
            files=_multipart_file(),
        )
        assert resp.status_code == 401


# -- RBAC tests, real parse path ------------------------------------------


class TestRBACUploadPost:
    """POST /uploads -- Operator + Approver allowed; Auditor -> 403.

    These hit the REAL parse_upload service (no mock). A signature mismatch
    in the router would surface as a 500 here.
    """

    def test_operator_can_upload_real_parse(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.post(
            "/api/v1/billing/uploads",
            headers={"X-Tenant-Id": TENANT_A},
            files=_multipart_file(_csv("CLM-OP-1")),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "validated"
        assert body["row_count"] == 1
        assert body["error_count"] == 0
        assert resp.headers.get("cache-control") == "no-store"

    def test_approver_can_upload_real_parse(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: APPROVER_USER
        resp = _client.post(
            "/api/v1/billing/uploads",
            headers={"X-Tenant-Id": TENANT_A},
            files=_multipart_file(_csv("CLM-APP-1")),
        )
        assert resp.status_code == 201, resp.text

    def test_auditor_cannot_upload_returns_403(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: AUDITOR_USER
        resp = _client.post(
            "/api/v1/billing/uploads",
            headers={"X-Tenant-Id": TENANT_A},
            files=_multipart_file(_csv("CLM-AUD-1")),
        )
        assert resp.status_code == 403


class TestRBACSupersede:
    def test_auditor_cannot_supersede(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: AUDITOR_USER
        fake_id = str(uuid.uuid4())
        resp = _client.post(
            f"/api/v1/billing/uploads/{fake_id}/supersede",
            headers={"X-Tenant-Id": TENANT_A},
            files=_multipart_file(),
        )
        assert resp.status_code == 403


# -- Duplicate SHA-256 (real find_existing_upload) -> 409 -----------------


class TestDuplicateUpload:
    def test_duplicate_returns_409_with_existing_id(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        csv = _csv("CLM-DUP-1")

        first = _client.post(
            "/api/v1/billing/uploads",
            headers={"X-Tenant-Id": TENANT_A},
            files=_multipart_file(csv),
        )
        assert first.status_code == 201, first.text
        existing_id = first.json()["id"]

        second = _client.post(
            "/api/v1/billing/uploads",
            headers={"X-Tenant-Id": TENANT_A},
            files=_multipart_file(csv),
        )
        assert second.status_code == 409
        body = second.json()
        assert body["error"]["code"] == "DUPLICATE_UPLOAD"
        assert body["error"]["existing_upload_id"] == existing_id
        assert second.headers.get("cache-control") == "no-store"


# -- PHI audit + Cache-Control ---------------------------------------------


class TestPhiAudit:
    def test_get_upload_by_id_emits_phi_audit_and_no_store(
        self, _client, _session_factory
    ):
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.tables import Upload, UploadStatus

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        upload_id = uuid.uuid4()

        session = _session_factory()
        try:
            session.add(
                Upload(
                    id=upload_id,
                    tenant_id=uuid.UUID(TENANT_A),
                    filename="phi.csv",
                    sha256="f" * 64,
                    file_size=100,
                    mime_type="text/csv",
                    uploaded_by=USER_OP,
                    status=UploadStatus.validated.value,
                    uploaded_at=datetime.datetime.now(datetime.timezone.utc),
                    row_count=1,
                    error_count=0,
                    row_errors=[],
                )
            )
            session.commit()
        finally:
            session.close()

        with patch("src.api.uploads._emit_phi_audit") as mock_emit:
            resp = _client.get(
                f"/api/v1/billing/uploads/{upload_id}",
                headers={"X-Tenant-Id": TENANT_A},
            )

        assert resp.status_code == 200
        assert resp.headers.get("cache-control") == "no-store"
        assert mock_emit.call_count == 1
        kwargs = mock_emit.call_args.kwargs
        assert kwargs["entity_id"] == upload_id
        assert str(kwargs["tenant_id"]) == TENANT_A
        assert kwargs["user_id"] == USER_OP

    def test_get_upload_claims_emits_phi_audit(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.tables import Upload, UploadStatus

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        upload_id = uuid.uuid4()

        session = _session_factory()
        try:
            session.add(
                Upload(
                    id=upload_id,
                    tenant_id=uuid.UUID(TENANT_A),
                    filename="phi2.csv",
                    sha256="9" * 64,
                    file_size=100,
                    mime_type="text/csv",
                    uploaded_by=USER_OP,
                    status=UploadStatus.validated.value,
                    uploaded_at=datetime.datetime.now(datetime.timezone.utc),
                    row_count=0,
                    error_count=0,
                )
            )
            session.commit()
        finally:
            session.close()

        with patch("src.api.uploads._emit_phi_audit") as mock_emit:
            resp = _client.get(
                f"/api/v1/billing/uploads/{upload_id}/claims",
                headers={"X-Tenant-Id": TENANT_A},
            )

        assert resp.status_code == 200
        assert resp.headers.get("cache-control") == "no-store"
        assert mock_emit.call_count == 1


# -- Cross-tenant isolation ------------------------------------------------


class TestCrossTenantIsolationListUploads:
    def test_tenant_a_cannot_see_tenant_b_uploads(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.tables import Upload, UploadStatus

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER

        b_upload_id = uuid.uuid4()
        session = _session_factory()
        try:
            session.add(
                Upload(
                    id=b_upload_id,
                    tenant_id=uuid.UUID(TENANT_B),
                    filename="tenant_b.csv",
                    sha256="b" * 64,
                    file_size=50,
                    mime_type="text/csv",
                    uploaded_by=uuid.uuid4(),
                    status=UploadStatus.validated.value,
                    uploaded_at=datetime.datetime.now(datetime.timezone.utc),
                    row_count=1,
                    error_count=0,
                )
            )
            session.commit()
        finally:
            session.close()

        resp = _client.get(
            "/api/v1/billing/uploads", headers={"X-Tenant-Id": TENANT_A}
        )
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()]
        assert str(b_upload_id) not in ids


class TestCrossTenantIsolationGetById:
    def test_tenant_a_cannot_read_tenant_b_upload_by_id(
        self, _client, _session_factory
    ):
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.tables import Upload, UploadStatus

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER

        b_upload_id = uuid.uuid4()
        session = _session_factory()
        try:
            session.add(
                Upload(
                    id=b_upload_id,
                    tenant_id=uuid.UUID(TENANT_B),
                    filename="tb_secret.csv",
                    sha256="c" * 64,
                    file_size=50,
                    mime_type="text/csv",
                    uploaded_by=uuid.uuid4(),
                    status=UploadStatus.validated.value,
                    uploaded_at=datetime.datetime.now(datetime.timezone.utc),
                    row_count=0,
                    error_count=0,
                )
            )
            session.commit()
        finally:
            session.close()

        resp = _client.get(
            f"/api/v1/billing/uploads/{b_upload_id}",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 404


class TestCrossTenantIsolationGetClaims:
    def test_tenant_a_cannot_read_tenant_b_upload_claims(
        self, _client, _session_factory
    ):
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.tables import Upload, UploadStatus

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER

        b_upload_id = uuid.uuid4()
        session = _session_factory()
        try:
            session.add(
                Upload(
                    id=b_upload_id,
                    tenant_id=uuid.UUID(TENANT_B),
                    filename="tb_claims.csv",
                    sha256="d" * 64,
                    file_size=50,
                    mime_type="text/csv",
                    uploaded_by=uuid.uuid4(),
                    status=UploadStatus.validated.value,
                    uploaded_at=datetime.datetime.now(datetime.timezone.utc),
                    row_count=0,
                    error_count=0,
                )
            )
            session.commit()
        finally:
            session.close()

        resp = _client.get(
            f"/api/v1/billing/uploads/{b_upload_id}/claims",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 404


class TestCrossTenantIsolationSupersede:
    def test_tenant_a_cannot_supersede_tenant_b_upload(
        self, _client, _session_factory
    ):
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.tables import Upload, UploadStatus

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER

        b_upload_id = uuid.uuid4()
        session = _session_factory()
        try:
            session.add(
                Upload(
                    id=b_upload_id,
                    tenant_id=uuid.UUID(TENANT_B),
                    filename="tb_supersede.csv",
                    sha256="e" * 64,
                    file_size=50,
                    mime_type="text/csv",
                    uploaded_by=uuid.uuid4(),
                    status=UploadStatus.validated.value,
                    uploaded_at=datetime.datetime.now(datetime.timezone.utc),
                    row_count=0,
                    error_count=0,
                )
            )
            session.commit()
        finally:
            session.close()

        resp = _client.post(
            f"/api/v1/billing/uploads/{b_upload_id}/supersede",
            headers={"X-Tenant-Id": TENANT_A},
            files=_multipart_file(_csv("CLM-XT-1")),
        )
        assert resp.status_code == 404
