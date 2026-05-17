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
        # P1-contract: field names match UploadSchema in packages/contract/src/impls/paysync/types.ts
        assert body["status"] == "validated"
        assert body["claim_count"] == 1
        assert body["row_error_count"] == 0
        assert "content_sha256" in body
        assert "uploaded_by_user_id" in body
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
    def test_duplicate_returns_409_with_canonical_envelope(self, _client):
        """B7: 409 duplicate upload must use canonical error envelope.

        Canonical shape per error-handling.md:
          {"error": {"code": "...", "message": "...", "correlation_id": "...",
                     "details": {"existing_upload_id": "..."}}}

        existing_upload_id must NOT appear at error root level.
        """
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
        err = body["error"]
        assert err["code"] == "DUPLICATE_UPLOAD"
        assert err["message"]
        # correlation_id must be present in canonical envelope
        assert "correlation_id" in err, "canonical envelope requires correlation_id"
        # existing_upload_id must be nested inside details, not at error root
        assert "details" in err, "existing_upload_id must be in error.details"
        assert err["details"]["existing_upload_id"] == existing_id
        assert "existing_upload_id" not in err, (
            "existing_upload_id must NOT appear at error root level"
        )
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
        # P2-pagination: list response is { results, total } not a bare array
        data = resp.json()
        assert "results" in data
        ids = [item["id"] for item in data["results"]]
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


# -- Contract compliance (P1-contract fix) ------------------------------------


class TestContractFieldNames:
    """Upload responses must use TS contract field names from UploadSchema."""

    def test_create_response_uses_contract_field_names(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.post(
            "/api/v1/billing/uploads",
            headers={"X-Tenant-Id": TENANT_A},
            files=_multipart_file(_csv("CLM-CONTRACT-1")),
        )
        assert resp.status_code == 201
        body = resp.json()
        # Contract fields present
        assert "content_sha256" in body, "must use content_sha256 not sha256"
        assert "uploaded_by_user_id" in body, "must use uploaded_by_user_id not uploaded_by"
        assert "claim_count" in body, "must use claim_count not row_count"
        assert "row_error_count" in body, "must use row_error_count not error_count"
        assert "total_billed_amount" in body
        # Legacy field names must NOT appear
        assert "sha256" not in body
        assert "uploaded_by" not in body
        assert "row_count" not in body
        assert "error_count" not in body

    def test_list_response_is_paginated_envelope(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get("/api/v1/billing/uploads", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        body = resp.json()
        assert "results" in body, "list must be { results, total } not bare array"
        assert "total" in body
        assert isinstance(body["results"], list)
        assert isinstance(body["total"], int)

    def test_claims_response_is_paginated_envelope(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.tables import Upload, UploadStatus

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        upload_id = uuid.uuid4()
        session = _session_factory()
        try:
            session.add(Upload(
                id=upload_id, tenant_id=uuid.UUID(TENANT_A), filename="claims_shape.csv",
                sha256="8" * 64, file_size=50, mime_type="text/csv",
                uploaded_by=USER_OP, uploaded_at=datetime.datetime.now(datetime.timezone.utc),
                status=UploadStatus.validated.value, row_count=0, error_count=0,
            ))
            session.commit()
        finally:
            session.close()

        with patch("src.api.uploads._emit_phi_audit"):
            resp = _client.get(
                f"/api/v1/billing/uploads/{upload_id}/claims",
                headers={"X-Tenant-Id": TENANT_A},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "results" in body, "claims must be { results, total } not bare array"
        assert "total" in body


# -- Supersede fixes (P2-supersede) ------------------------------------------


class TestSupersede:
    """Supersede with overlapping claim_ids must not raise IntegrityError."""

    def test_supersede_invalid_replacement_preserves_old_claims(self, _client, _session_factory):
        """B10: If replacement file is fully invalid, old upload and its claims must be preserved.

        The supersede endpoint deletes old ClaimRecord rows before parsing the
        replacement. If replacement parse fails (validation_failed), the old claims
        must NOT be committed as deleted -- the transaction must be rolled back.
        """
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.tables import ClaimRecord

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER

        # Upload original with one valid claim
        original_csv = _csv("CLM-SUP-PRESERVE-1")
        resp1 = _client.post(
            "/api/v1/billing/uploads",
            headers={"X-Tenant-Id": TENANT_A},
            files=_multipart_file(original_csv, "original.csv"),
        )
        assert resp1.status_code == 201, resp1.text
        upload_id = resp1.json()["id"]

        # Wait for parsing to complete then verify claim exists
        with _session_factory() as session:
            claim_count_before = session.query(ClaimRecord).filter(
                ClaimRecord.upload_id == uuid.UUID(upload_id)
            ).count()
        assert claim_count_before > 0, "original upload must have parsed claims"

        # Supersede with a file that has rows but ALL fail validation (bad NPI, bad date)
        # This triggers parse_upload → validation_failed status.
        all_invalid_csv = (
            b"claim_id,member_id,npi,ndc,date_of_service,quantity,days_supply,amount_billed\n"
            b"BAD-1,M001,NOT_AN_NPI,12345678901,NOT_A_DATE,1,30,10.00\n"
        )
        resp2 = _client.post(
            f"/api/v1/billing/uploads/{upload_id}/supersede",
            headers={"X-Tenant-Id": TENANT_A},
            files=[("file", ("invalid.csv", all_invalid_csv, "text/csv"))],
        )
        # An all-invalid replacement → parse_upload sets validation_failed.
        # The router must rollback the entire txn and return 422.
        # B10 bug: supersede committed with old claims deleted even when parse fails.
        assert resp2.status_code == 422, (
            f"B10: all-invalid replacement must be rejected with 422 (validation_failed), "
            f"got {resp2.status_code}: {resp2.text}"
        )
        # Old claims must be preserved after the failed supersede
        with _session_factory() as session:
            claim_count_after = session.query(ClaimRecord).filter(
                ClaimRecord.upload_id == uuid.UUID(upload_id)
            ).count()
        assert claim_count_after == claim_count_before, (
            f"B10: invalid replacement must not delete old claims. "
            f"Before: {claim_count_before}, after: {claim_count_after}"
        )

    def test_supersede_with_same_claim_ids_succeeds(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        # Upload original
        original_csv = _csv("CLM-SUP-SAME-1")
        resp1 = _client.post(
            "/api/v1/billing/uploads",
            headers={"X-Tenant-Id": TENANT_A},
            files=_multipart_file(original_csv, "original.csv"),
        )
        assert resp1.status_code == 201, resp1.text
        upload_id = resp1.json()["id"]

        # Supersede with same claim_id — must not raise IntegrityError/500
        replacement_csv = _csv("CLM-SUP-SAME-1")  # same claim_id
        resp2 = _client.post(
            f"/api/v1/billing/uploads/{upload_id}/supersede",
            headers={"X-Tenant-Id": TENANT_A},
            files=_multipart_file(replacement_csv, "replacement.csv"),
        )
        # 201 = success; 409 = dedup (same SHA if content identical); anything else is a bug
        assert resp2.status_code in (201, 409), f"unexpected: {resp2.status_code} {resp2.text}"


# -- B2: Header tenant vs JWT tenant mismatch -> 403 -----------------------


class TestTenantHeaderAuthorizationB2:
    """B2 fix: X-Tenant-Id header must be checked against JWT tenant_id.

    A Tenant-A JWT presenting X-Tenant-Id: <Tenant-B> must receive 403
    on every endpoint, not silently query Tenant-B data.
    """

    def test_post_upload_wrong_tenant_header_returns_403(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        # JWT is for TENANT_A but header claims TENANT_B
        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.post(
            "/api/v1/billing/uploads",
            headers={"X-Tenant-Id": TENANT_B},
            files=_multipart_file(_csv("CLM-B2-POST-1")),
        )
        assert resp.status_code == 403

    def test_get_uploads_wrong_tenant_header_returns_403(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get(
            "/api/v1/billing/uploads",
            headers={"X-Tenant-Id": TENANT_B},
        )
        assert resp.status_code == 403

    def test_get_upload_by_id_wrong_tenant_header_returns_403(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get(
            f"/api/v1/billing/uploads/{uuid.uuid4()}",
            headers={"X-Tenant-Id": TENANT_B},
        )
        assert resp.status_code == 403

    def test_get_upload_claims_wrong_tenant_header_returns_403(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get(
            f"/api/v1/billing/uploads/{uuid.uuid4()}/claims",
            headers={"X-Tenant-Id": TENANT_B},
        )
        assert resp.status_code == 403

    def test_supersede_wrong_tenant_header_returns_403(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.post(
            f"/api/v1/billing/uploads/{uuid.uuid4()}/supersede",
            headers={"X-Tenant-Id": TENANT_B},
            files=_multipart_file(_csv("CLM-B2-SUP-1")),
        )
        assert resp.status_code == 403


class TestListPaginationAndTotalBilledAmount:
    """Concerns from codex R3: list ignores status/limit/cursor; total_billed_amount always None."""

    def test_list_respects_limit(self, _client):
        """List endpoint must honour ?limit= query param."""
        from shared.auth.dependencies import get_current_user
        from src.main import app
        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER

        # Upload two distinct files
        for cid in ("CLM-LIMIT-1", "CLM-LIMIT-2", "CLM-LIMIT-3"):
            _client.post(
                "/api/v1/billing/uploads",
                headers={"X-Tenant-Id": TENANT_A},
                files=_multipart_file(_csv(cid), f"{cid}.csv"),
            )

        resp = _client.get(
            "/api/v1/billing/uploads",
            headers={"X-Tenant-Id": TENANT_A},
            params={"limit": 1},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body["results"]) <= 1, (
            f"limit=1 must return at most 1 result, got {len(body['results'])}"
        )

    def test_list_respects_status_filter(self, _client):
        """List endpoint must filter by ?status= query param."""
        from shared.auth.dependencies import get_current_user
        from src.main import app
        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER

        resp = _client.get(
            "/api/v1/billing/uploads",
            headers={"X-Tenant-Id": TENANT_A},
            params={"status": "validated"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        for item in body["results"]:
            assert item["status"] == "validated", (
                f"All results must have status=validated, got {item['status']}"
            )

    def test_total_billed_amount_computed_from_claims(self, _client):
        """total_billed_amount must be a Decimal string sum of claim amount_billed values."""
        from shared.auth.dependencies import get_current_user
        from src.main import app
        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER

        # Upload a file with one claim (amount_billed = 99.9900 from _csv helper)
        resp = _client.post(
            "/api/v1/billing/uploads",
            headers={"X-Tenant-Id": TENANT_A},
            files=_multipart_file(_csv("CLM-TBA-1"), "tba.csv"),
        )
        assert resp.status_code == 201, resp.text
        upload_id = resp.json()["id"]

        # Fetch the upload and check total_billed_amount is not None
        detail_resp = _client.get(
            f"/api/v1/billing/uploads/{upload_id}",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert detail_resp.status_code == 200, detail_resp.text
        body = detail_resp.json()
        assert body["total_billed_amount"] is not None, (
            "total_billed_amount must be computed from claim amount_billed values, not always None"
        )
        # The CSV helper uses amount_billed=99.9900
        from decimal import Decimal
        assert Decimal(body["total_billed_amount"]) > 0, (
            f"total_billed_amount must be > 0, got {body['total_billed_amount']}"
        )
