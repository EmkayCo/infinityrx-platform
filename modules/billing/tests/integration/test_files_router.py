"""Integration tests for Files router (SP-1 Plan D Task 2).

Covers:
  - Auth gate: no token -> 401 on every endpoint
  - MFA gate: missing X-Tenant-Id -> 422 (dependency chain)
  - RBAC matrix:
      generate -> Approver OK (201), Operator -> 403, Auditor -> 403
      list     -> all roles OK (200)
      detail   -> all roles OK (200); Cache-Control: no-store
      download -> all roles OK (200); Cache-Control: no-store; PHI audit
  - Cross-tenant isolation: Tenant A artifact not visible to Tenant B
  - file_path never present in any JSON response
  - PHI audit fires on download
  - generate returns 400 for unsupported kind
  - generate returns 404 when source_id not found for tenant
"""

from __future__ import annotations

import io
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

TENANT_A = str(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
TENANT_B = str(uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))
USER_APP = uuid.UUID("22222222-2222-2222-2222-222222222222")
USER_OP = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_AUD = uuid.UUID("33333333-3333-3333-3333-333333333333")
USER_B = uuid.UUID("44444444-4444-4444-4444-444444444444")

APPROVER_USER = MagicMock(
    id=USER_APP,
    tenant_id=uuid.UUID(TENANT_A),
    roles=("approver",),
    has_role=lambda r: r == "approver",
)
OPERATOR_USER = MagicMock(
    id=USER_OP,
    tenant_id=uuid.UUID(TENANT_A),
    roles=("operator",),
    has_role=lambda r: r == "operator",
)
AUDITOR_USER = MagicMock(
    id=USER_AUD,
    tenant_id=uuid.UUID(TENANT_A),
    roles=("auditor",),
    has_role=lambda r: r == "auditor",
)
TENANT_B_USER = MagicMock(
    id=USER_B,
    tenant_id=uuid.UUID(TENANT_B),
    roles=("approver",),
    has_role=lambda r: r == "approver",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _engine():
    from src.models.tables import BillingBase
    from src.models.file_artifact import FileArtifact  # ensure registered  # noqa: F401

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
    monkeypatch.setenv("PAYSYNC_FILES_DIR", str(tmp_path / "files"))

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


def _make_batch(
    session: Session,
    tenant_id: str,
    batch_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Insert a minimal PaymentBatch row and return its id."""
    from src.models.tables import PaymentBatch

    bid = batch_id or uuid.uuid4()
    batch = PaymentBatch(
        id=bid,
        tenant_id=uuid.UUID(tenant_id),
        batch_number=f"BATCH-{bid}",
        payment_route="ach",
        total_amount=Decimal("1000.00"),
        payment_count=1,
        ap_count=1,
        status="generated",
        generated_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(batch)
    session.commit()
    return bid


def _make_artifact(
    session: Session,
    tenant_id: str,
    tmp_path: Path,
    kind: str = "nacha",
) -> uuid.UUID:
    """Insert a ready FileArtifact and write a stub file to disk."""
    from src.models.file_artifact import FileArtifact

    artifact_id = uuid.uuid4()
    file_path = tmp_path / "files" / tenant_id / f"{artifact_id}.ach"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("STUB FILE CONTENT")

    artifact = FileArtifact(
        id=artifact_id,
        tenant_id=uuid.UUID(tenant_id),
        kind=kind,
        generated_by=USER_APP,
        generated_at=datetime.now(UTC),
        filename=f"{artifact_id}.ach",
        file_path=str(file_path.resolve()),
        file_size=17,
        sha256="a" * 64,
        status="ready",
    )
    session.add(artifact)
    session.commit()
    return artifact_id


# ---------------------------------------------------------------------------
# Auth gate tests (no token -> 401)
# ---------------------------------------------------------------------------


class TestAuthGate:
    def test_generate_no_auth_401(self, _client):
        resp = _client.post(
            "/api/v1/billing/files/generate",
            headers={"X-Tenant-Id": TENANT_A},
            json={"kind": "nacha", "source_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    def test_list_no_auth_401(self, _client):
        resp = _client.get(
            "/api/v1/billing/files",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 401

    def test_detail_no_auth_401(self, _client):
        resp = _client.get(
            f"/api/v1/billing/files/{uuid.uuid4()}",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 401

    def test_download_no_auth_401(self, _client):
        resp = _client.get(
            f"/api/v1/billing/files/{uuid.uuid4()}/download",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# MFA gate: missing X-Tenant-Id header
# ---------------------------------------------------------------------------


class TestMFAGate:
    def test_list_missing_tenant_header_422(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: APPROVER_USER
        resp = _client.get("/api/v1/billing/files")
        # Missing required header -> FastAPI 422 unprocessable entity
        assert resp.status_code == 422

    def test_detail_missing_tenant_header_422(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: APPROVER_USER
        resp = _client.get(f"/api/v1/billing/files/{uuid.uuid4()}")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# RBAC matrix: generate endpoint
# ---------------------------------------------------------------------------


class TestGenerateRBAC:
    def test_operator_generate_403(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.post(
            "/api/v1/billing/files/generate",
            headers={"X-Tenant-Id": TENANT_A},
            json={"kind": "nacha", "source_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 403

    def test_auditor_generate_403(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: AUDITOR_USER
        resp = _client.post(
            "/api/v1/billing/files/generate",
            headers={"X-Tenant-Id": TENANT_A},
            json={"kind": "nacha", "source_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 403

    def test_approver_generate_404_when_batch_not_found(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: APPROVER_USER
        resp = _client.post(
            "/api/v1/billing/files/generate",
            headers={"X-Tenant-Id": TENANT_A},
            json={"kind": "nacha", "source_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 404

    def test_generate_unsupported_kind_400(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: APPROVER_USER
        resp = _client.post(
            "/api/v1/billing/files/generate",
            headers={"X-Tenant-Id": TENANT_A},
            json={"kind": "csv", "source_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 400

    def test_approver_can_generate_nacha(self, _client, _session_factory, tmp_path):
        """Approver generates NACHA; service is mocked to avoid payment-processing dep."""
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.file_artifact import FileArtifact

        session = _session_factory()
        batch_id = _make_batch(session, TENANT_A)
        session.close()

        app.dependency_overrides[get_current_user] = lambda: APPROVER_USER

        # Mock generate_nacha to avoid needing NachaFileConfig + real payments
        stub_artifact = FileArtifact(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(TENANT_A),
            kind="nacha",
            source_batch_id=batch_id,
            generated_by=USER_APP,
            generated_at=datetime.now(UTC),
            filename="test.ach",
            file_path=str(tmp_path / "test.ach"),
            file_size=100,
            sha256="a" * 64,
            status="ready",
        )
        with patch("src.api.files._generate_nacha_artifact", return_value=stub_artifact):
            resp = _client.post(
                "/api/v1/billing/files/generate",
                headers={"X-Tenant-Id": TENANT_A},
                json={"kind": "nacha", "source_id": str(batch_id)},
            )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["kind"] == "nacha"
        assert "file_path" not in body
        assert resp.headers.get("cache-control") == "no-store"

    def test_approver_can_generate_835(self, _client, _session_factory, tmp_path):
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.file_artifact import FileArtifact

        session = _session_factory()
        batch_id = _make_batch(session, TENANT_A)
        session.close()

        app.dependency_overrides[get_current_user] = lambda: APPROVER_USER

        stub_artifact = FileArtifact(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(TENANT_A),
            kind="835",
            source_payment_run_id=batch_id,
            generated_by=USER_APP,
            generated_at=datetime.now(UTC),
            filename="test.835",
            file_path=str(tmp_path / "test.835"),
            file_size=200,
            sha256="b" * 64,
            status="ready",
        )
        with patch("src.api.files._generate_835_artifact", return_value=stub_artifact):
            resp = _client.post(
                "/api/v1/billing/files/generate",
                headers={"X-Tenant-Id": TENANT_A},
                json={"kind": "835", "source_id": str(batch_id)},
            )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["kind"] == "835"
        assert "file_path" not in body


# ---------------------------------------------------------------------------
# RBAC matrix: read endpoints
# ---------------------------------------------------------------------------


class TestReadRBAC:
    def test_operator_can_list(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get("/api/v1/billing/files", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200

    def test_auditor_can_list(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: AUDITOR_USER
        resp = _client.get("/api/v1/billing/files", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200

    def test_approver_can_list(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: APPROVER_USER
        resp = _client.get("/api/v1/billing/files", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        assert resp.headers.get("cache-control") == "no-store"

    def test_operator_can_get_detail(self, _client, _session_factory, tmp_path):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        session = _session_factory()
        artifact_id = _make_artifact(session, TENANT_A, tmp_path)
        session.close()

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get(
            f"/api/v1/billing/files/{artifact_id}",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        assert resp.headers.get("cache-control") == "no-store"
        assert "file_path" not in resp.json()

    def test_auditor_can_get_detail(self, _client, _session_factory, tmp_path):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        session = _session_factory()
        artifact_id = _make_artifact(session, TENANT_A, tmp_path)
        session.close()

        app.dependency_overrides[get_current_user] = lambda: AUDITOR_USER
        resp = _client.get(
            f"/api/v1/billing/files/{artifact_id}",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Download endpoint
# ---------------------------------------------------------------------------


class TestDownload:
    def test_download_streams_bytes_and_no_store(self, _client, _session_factory, tmp_path):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        session = _session_factory()
        artifact_id = _make_artifact(session, TENANT_A, tmp_path)
        session.close()

        app.dependency_overrides[get_current_user] = lambda: APPROVER_USER
        with patch(
            "src.api.files._emit_phi_audit"
        ) as mock_phi:
            resp = _client.get(
                f"/api/v1/billing/files/{artifact_id}/download",
                headers={"X-Tenant-Id": TENANT_A},
            )
        assert resp.status_code == 200, resp.text
        assert resp.headers.get("cache-control") == "no-store"
        assert "attachment" in resp.headers.get("content-disposition", "")
        assert resp.content == b"STUB FILE CONTENT"
        mock_phi.assert_called_once()

    def test_download_phi_audit_fires(self, _client, _session_factory, tmp_path):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        session = _session_factory()
        artifact_id = _make_artifact(session, TENANT_A, tmp_path)
        session.close()

        app.dependency_overrides[get_current_user] = lambda: AUDITOR_USER
        with patch("src.api.files._emit_phi_audit") as mock_phi:
            resp = _client.get(
                f"/api/v1/billing/files/{artifact_id}/download",
                headers={"X-Tenant-Id": TENANT_A},
            )
        assert resp.status_code == 200
        mock_phi.assert_called_once_with(
            tenant_id=uuid.UUID(TENANT_A),
            user_id=USER_AUD,
            entity_id=artifact_id,
        )

    def test_download_404_when_artifact_not_found(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: APPROVER_USER
        resp = _client.get(
            f"/api/v1/billing/files/{uuid.uuid4()}/download",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 404

    def test_operator_can_download(self, _client, _session_factory, tmp_path):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        session = _session_factory()
        artifact_id = _make_artifact(session, TENANT_A, tmp_path)
        session.close()

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        with patch("src.api.files._emit_phi_audit"):
            resp = _client.get(
                f"/api/v1/billing/files/{artifact_id}/download",
                headers={"X-Tenant-Id": TENANT_A},
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Cross-tenant isolation
# ---------------------------------------------------------------------------


class TestCrossTenantIsolation:
    def test_list_tenant_b_cannot_see_tenant_a_artifacts(
        self, _client, _session_factory, tmp_path
    ):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        session = _session_factory()
        _make_artifact(session, TENANT_A, tmp_path)
        session.close()

        app.dependency_overrides[get_current_user] = lambda: TENANT_B_USER
        resp = _client.get(
            "/api/v1/billing/files",
            headers={"X-Tenant-Id": TENANT_B},
        )
        assert resp.status_code == 200
        # Tenant B should see zero Tenant A artifacts
        body = resp.json()
        assert isinstance(body, list)
        tenant_a_uuids = {str(uuid.UUID(TENANT_A))}
        for item in body:
            assert item["tenant_id"] not in tenant_a_uuids

    def test_detail_tenant_b_cannot_see_tenant_a_artifact(
        self, _client, _session_factory, tmp_path
    ):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        session = _session_factory()
        artifact_id = _make_artifact(session, TENANT_A, tmp_path)
        session.close()

        app.dependency_overrides[get_current_user] = lambda: TENANT_B_USER
        resp = _client.get(
            f"/api/v1/billing/files/{artifact_id}",
            headers={"X-Tenant-Id": TENANT_B},
        )
        assert resp.status_code == 404

    def test_download_tenant_b_cannot_download_tenant_a_artifact(
        self, _client, _session_factory, tmp_path
    ):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        session = _session_factory()
        artifact_id = _make_artifact(session, TENANT_A, tmp_path)
        session.close()

        app.dependency_overrides[get_current_user] = lambda: TENANT_B_USER
        resp = _client.get(
            f"/api/v1/billing/files/{artifact_id}/download",
            headers={"X-Tenant-Id": TENANT_B},
        )
        assert resp.status_code == 404

    def test_generate_tenant_b_cannot_use_tenant_a_batch(
        self, _client, _session_factory
    ):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        session = _session_factory()
        batch_id = _make_batch(session, TENANT_A)
        session.close()

        app.dependency_overrides[get_current_user] = lambda: TENANT_B_USER
        resp = _client.post(
            "/api/v1/billing/files/generate",
            headers={"X-Tenant-Id": TENANT_B},
            json={"kind": "nacha", "source_id": str(batch_id)},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# file_path never in response
# ---------------------------------------------------------------------------


class TestFilePathNeverExposed:
    def test_list_no_file_path(self, _client, _session_factory, tmp_path):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        session = _session_factory()
        _make_artifact(session, TENANT_A, tmp_path)
        session.close()

        app.dependency_overrides[get_current_user] = lambda: APPROVER_USER
        resp = _client.get("/api/v1/billing/files", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        for item in resp.json():
            assert "file_path" not in item

    def test_detail_no_file_path(self, _client, _session_factory, tmp_path):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        session = _session_factory()
        artifact_id = _make_artifact(session, TENANT_A, tmp_path)
        session.close()

        app.dependency_overrides[get_current_user] = lambda: APPROVER_USER
        resp = _client.get(
            f"/api/v1/billing/files/{artifact_id}",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        assert "file_path" not in resp.json()
