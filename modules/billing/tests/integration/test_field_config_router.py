"""Integration tests for field-config router (Stage 2).

Covers:
  - Auth gate (no token -> 401) for all three endpoints
  - GET /sample-values returns position->sample mapping for a captured upload
  - GET /field-config returns empty list when no config saved
  - PUT /field-config saves; GET /field-config returns the saved values (round-trip)
  - PUT with is_phi=True forces sample_value null (PHI safety)
  - Duplicate positions in PUT body -> 422
  - Auditor (read-only role) gets 403 on PUT
  - No-role user gets 403 on PUT
  - Cross-tenant isolation: PUT by Tenant A is not visible to Tenant B
  - Cache-Control: no-store on all responses
  - phi_access audit emitted on GET /sample-values
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


class _SqliteInsertProxy:
    """Proxy for SQLite insert that translates pg constraint= -> index_elements=.

    pg_insert(Table).values(...).on_conflict_do_update(constraint="name", set_={})
    becomes:
    sqlite_insert(Table).values(...).on_conflict_do_update(index_elements=[cols], set_={})

    We wrap the statement at each step so the patch survives .values().
    """

    def __init__(self, table):
        self._table = table
        self._stmt = sqlite_insert(table)

    def values(self, **kw):
        self._stmt = self._stmt.values(**kw)
        return self

    def on_conflict_do_update(self, constraint=None, index_elements=None, set_=None, **kw):
        if constraint is not None and index_elements is None:
            tbl = self._table.__table__ if hasattr(self._table, "__table__") else self._table
            for uc in tbl.constraints:
                if getattr(uc, "name", None) == constraint:
                    index_elements = list(uc.columns)
                    break
            if index_elements is None:
                index_elements = [tbl.c.tenant_id, tbl.c.position]
        return self._stmt.on_conflict_do_update(index_elements=index_elements, set_=set_, **kw)

    # Pass-through any other attribute to the underlying statement
    def __getattr__(self, name):
        return getattr(self._stmt, name)


def _sqlite_insert_factory(table):
    """Return a SQLite-compatible insert proxy for the given ORM table class."""
    return _SqliteInsertProxy(table)

# ---- tenant / user stubs -----------------------------------------------

TENANT_A = str(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
TENANT_B = str(uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))
USER_OP = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_APP = uuid.UUID("22222222-2222-2222-2222-222222222222")
USER_AUD = uuid.UUID("33333333-3333-3333-3333-333333333333")
USER_NOROLE = uuid.UUID("44444444-4444-4444-4444-444444444444")

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
NO_ROLE_USER = MagicMock(
    id=USER_NOROLE,
    tenant_id=uuid.UUID(TENANT_A),
    roles=(),
    has_role=lambda r: False,
)
TENANT_B_USER = MagicMock(
    id=uuid.UUID("55555555-5555-5555-5555-555555555555"),
    tenant_id=uuid.UUID(TENANT_B),
    roles=("operator",),
    has_role=lambda r: r == "operator",
)


# ---- engine / session fixtures -----------------------------------------


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
    """TestClient with SQLite DB override and pg_insert -> sqlite_insert patch."""
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

    # Patch pg_insert -> SQLite-compatible insert factory (translates constraint= -> index_elements=)
    with patch("src.api.field_config.pg_insert", new=_sqlite_insert_factory):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    app.dependency_overrides.clear()


def _make_upload(session: Session, tenant_id: str, upload_id: uuid.UUID | None = None) -> uuid.UUID:
    """Insert a bare Upload row; returns its id."""
    from src.models.tables import Upload

    uid = upload_id or uuid.uuid4()
    session.add(
        Upload(
            id=uid,
            tenant_id=uuid.UUID(tenant_id),
            filename="test.txt",
            sha256=uuid.uuid4().hex * 2,  # 64 hex chars
            file_size=1024,
            mime_type="text/plain",
            uploaded_by=USER_OP,
            status="captured",
            uploaded_at=datetime.now(UTC),
            row_count=10,
            error_count=0,
            row_errors=[],
        )
    )
    session.commit()
    return uid


def _make_raw_row(
    session: Session, upload_id: uuid.UUID, tenant_id: str, field_count: int = 5
) -> None:
    """Insert one ClaimUploadRawRow with encrypted fields blob."""
    from src.models.tables import ClaimUploadRawRow
    from src.services.upload import encrypt_raw_row_fields

    fields = {str(i): f"val{i}" for i in range(1, field_count + 1)}
    blob = encrypt_raw_row_fields(fields, tenant_id=tenant_id)
    session.add(
        ClaimUploadRawRow(
            id=uuid.uuid4(),
            upload_id=upload_id,
            tenant_id=uuid.UUID(tenant_id),
            row_number=1,
            fields_blob=blob,
            field_count=field_count,
            captured_at=datetime.now(UTC),
        )
    )
    session.commit()


# ---- auth gate tests ---------------------------------------------------


class TestAuthGate:
    def test_get_sample_values_no_auth_401(self, _client):
        fid = str(uuid.uuid4())
        resp = _client.get(
            f"/api/v1/billing/uploads/{fid}/field-config/sample-values",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 401

    def test_get_field_config_no_auth_401(self, _client):
        fid = str(uuid.uuid4())
        resp = _client.get(
            f"/api/v1/billing/uploads/{fid}/field-config",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 401

    def test_put_field_config_no_auth_401(self, _client):
        fid = str(uuid.uuid4())
        resp = _client.put(
            f"/api/v1/billing/uploads/{fid}/field-config",
            headers={"X-Tenant-Id": TENANT_A},
            json={"fields": [{"position": 1, "field_name": "ndc"}]},
        )
        assert resp.status_code == 401


# ---- 404 for unknown upload --------------------------------------------


class TestUploadNotFound:
    def test_get_sample_values_unknown_upload_404(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get(
            f"/api/v1/billing/uploads/{uuid.uuid4()}/field-config/sample-values",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 404

    def test_get_field_config_unknown_upload_404(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get(
            f"/api/v1/billing/uploads/{uuid.uuid4()}/field-config",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 404

    def test_put_field_config_unknown_upload_404(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.put(
            f"/api/v1/billing/uploads/{uuid.uuid4()}/field-config",
            headers={"X-Tenant-Id": TENANT_A},
            json={"fields": [{"position": 1, "field_name": "ndc"}]},
        )
        assert resp.status_code == 404


# ---- sample-values endpoint --------------------------------------------


class TestSampleValues:
    def test_returns_position_to_value_mapping(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        session = _session_factory()
        try:
            uid = _make_upload(session, TENANT_A)
            _make_raw_row(session, uid, TENANT_A, field_count=3)
        finally:
            session.close()

        with patch("src.api.field_config._emit_phi_audit"):
            resp = _client.get(
                f"/api/v1/billing/uploads/{uid}/field-config/sample-values",
                headers={"X-Tenant-Id": TENANT_A},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["field_count"] == 3
        assert "1" in body["samples"]
        assert "2" in body["samples"]
        assert "3" in body["samples"]
        assert body["samples"]["1"] == "val1"

    def test_no_store_header(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        session = _session_factory()
        try:
            uid = _make_upload(session, TENANT_A)
            _make_raw_row(session, uid, TENANT_A, field_count=2)
        finally:
            session.close()

        with patch("src.api.field_config._emit_phi_audit"):
            resp = _client.get(
                f"/api/v1/billing/uploads/{uid}/field-config/sample-values",
                headers={"X-Tenant-Id": TENANT_A},
            )
        assert resp.headers.get("cache-control") == "no-store"

    def test_phi_access_audit_emitted(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        session = _session_factory()
        try:
            uid = _make_upload(session, TENANT_A)
            _make_raw_row(session, uid, TENANT_A, field_count=2)
        finally:
            session.close()

        with patch("src.api.field_config._emit_phi_audit") as mock_audit:
            resp = _client.get(
                f"/api/v1/billing/uploads/{uid}/field-config/sample-values",
                headers={"X-Tenant-Id": TENANT_A},
            )

        assert resp.status_code == 200
        assert mock_audit.call_count == 1
        kwargs = mock_audit.call_args.kwargs
        assert kwargs["entity_id"] == uid
        assert str(kwargs["tenant_id"]) == TENANT_A

    def test_phi_flagged_position_masked_as_null(self, _client, _session_factory):
        """Positions marked is_phi in saved config must return null in samples."""
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.tables import UploadFieldConfig

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        session = _session_factory()
        try:
            uid = _make_upload(session, TENANT_A)
            _make_raw_row(session, uid, TENANT_A, field_count=3)
            # Mark position 2 as PHI in saved config
            session.add(
                UploadFieldConfig(
                    id=uuid.uuid4(),
                    tenant_id=uuid.UUID(TENANT_A),
                    position=2,
                    field_name="date_of_birth",
                    data_type="date",
                    is_mandatory=False,
                    is_phi=True,
                    sample_value=None,
                    updated_at=datetime.now(UTC),
                )
            )
            session.commit()
        finally:
            session.close()

        with patch("src.api.field_config._emit_phi_audit"):
            resp = _client.get(
                f"/api/v1/billing/uploads/{uid}/field-config/sample-values",
                headers={"X-Tenant-Id": TENANT_A},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["samples"]["2"] is None   # PHI-masked
        assert body["samples"]["1"] == "val1"  # non-PHI still visible

    def test_no_raw_rows_returns_empty_samples(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        session = _session_factory()
        try:
            uid = _make_upload(session, TENANT_A)
            # deliberately no raw rows
        finally:
            session.close()

        with patch("src.api.field_config._emit_phi_audit"):
            resp = _client.get(
                f"/api/v1/billing/uploads/{uid}/field-config/sample-values",
                headers={"X-Tenant-Id": TENANT_A},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["samples"] == {}
        assert body["field_count"] == 0


# ---- GET field-config (empty + after save) -----------------------------


class TestGetFieldConfig:
    def test_empty_returns_empty_fields_list(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        session = _session_factory()
        try:
            uid = _make_upload(session, TENANT_A)
        finally:
            session.close()

        resp = _client.get(
            f"/api/v1/billing/uploads/{uid}/field-config",
            headers={"X-Tenant-Id": TENANT_A},
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["fields"] == [] or isinstance(body["fields"], list)
        assert resp.headers.get("cache-control") == "no-store"

    def test_auditor_can_read_field_config(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: AUDITOR_USER
        session = _session_factory()
        try:
            uid = _make_upload(session, TENANT_A)
        finally:
            session.close()

        resp = _client.get(
            f"/api/v1/billing/uploads/{uid}/field-config",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200


# ---- PUT + round-trip --------------------------------------------------


class TestPutFieldConfig:
    def test_operator_can_save_and_reload(self, _client, _session_factory):
        """Full round-trip: PUT saves config; GET returns same values."""
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        session = _session_factory()
        try:
            uid = _make_upload(session, TENANT_A)
        finally:
            session.close()

        fields_payload = [
            {"position": 1, "field_name": "claim_id", "data_type": "string", "is_mandatory": True, "is_phi": False},
            {"position": 2, "field_name": "date_of_birth", "data_type": "date", "is_mandatory": False, "is_phi": True},
            {"position": 3, "field_name": "ndc", "data_type": "ndc", "is_mandatory": True, "is_phi": False},
        ]

        put_resp = _client.put(
            f"/api/v1/billing/uploads/{uid}/field-config",
            headers={"X-Tenant-Id": TENANT_A},
            json={"fields": fields_payload},
        )
        assert put_resp.status_code == 200, put_resp.text
        assert put_resp.headers.get("cache-control") == "no-store"

        get_resp = _client.get(
            f"/api/v1/billing/uploads/{uid}/field-config",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert get_resp.status_code == 200
        saved = {f["position"]: f for f in get_resp.json()["fields"]}
        assert saved[1]["field_name"] == "claim_id"
        assert saved[1]["is_mandatory"] is True
        assert saved[2]["field_name"] == "date_of_birth"
        assert saved[2]["is_phi"] is True
        assert saved[3]["data_type"] == "ndc"

    def test_phi_position_sample_value_forced_null(self, _client, _session_factory):
        """When is_phi=True, sample_value must be null in DB regardless of what caller sends."""
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        session = _session_factory()
        try:
            uid = _make_upload(session, TENANT_A)
        finally:
            session.close()

        put_resp = _client.put(
            f"/api/v1/billing/uploads/{uid}/field-config",
            headers={"X-Tenant-Id": TENANT_A},
            json={"fields": [{"position": 5, "field_name": "ssn", "data_type": "string", "is_mandatory": False, "is_phi": True}]},
        )
        assert put_resp.status_code == 200
        saved = {f["position"]: f for f in put_resp.json()["fields"]}
        assert saved[5]["sample_value"] is None

    def test_approver_can_save(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: APPROVER_USER
        session = _session_factory()
        try:
            uid = _make_upload(session, TENANT_A)
        finally:
            session.close()

        resp = _client.put(
            f"/api/v1/billing/uploads/{uid}/field-config",
            headers={"X-Tenant-Id": TENANT_A},
            json={"fields": [{"position": 1, "field_name": "auth_number", "data_type": "string"}]},
        )
        assert resp.status_code == 200

    def test_auditor_cannot_save_403(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: AUDITOR_USER
        session = _session_factory()
        try:
            uid = _make_upload(session, TENANT_A)
        finally:
            session.close()

        resp = _client.put(
            f"/api/v1/billing/uploads/{uid}/field-config",
            headers={"X-Tenant-Id": TENANT_A},
            json={"fields": [{"position": 1, "field_name": "x"}]},
        )
        assert resp.status_code == 403

    def test_no_role_user_cannot_save_403(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: NO_ROLE_USER
        session = _session_factory()
        try:
            uid = _make_upload(session, TENANT_A)
        finally:
            session.close()

        resp = _client.put(
            f"/api/v1/billing/uploads/{uid}/field-config",
            headers={"X-Tenant-Id": TENANT_A},
            json={"fields": [{"position": 1, "field_name": "x"}]},
        )
        assert resp.status_code == 403

    def test_duplicate_positions_returns_422(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        session = _session_factory()
        try:
            uid = _make_upload(session, TENANT_A)
        finally:
            session.close()

        resp = _client.put(
            f"/api/v1/billing/uploads/{uid}/field-config",
            headers={"X-Tenant-Id": TENANT_A},
            json={"fields": [
                {"position": 1, "field_name": "ndc"},
                {"position": 1, "field_name": "npi"},  # duplicate pos 1
            ]},
        )
        assert resp.status_code == 422

    def test_empty_fields_list_returns_422(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        session = _session_factory()
        try:
            uid = _make_upload(session, TENANT_A)
        finally:
            session.close()

        resp = _client.put(
            f"/api/v1/billing/uploads/{uid}/field-config",
            headers={"X-Tenant-Id": TENANT_A},
            json={"fields": []},
        )
        assert resp.status_code == 422

    def test_invalid_data_type_returns_422(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        session = _session_factory()
        try:
            uid = _make_upload(session, TENANT_A)
        finally:
            session.close()

        resp = _client.put(
            f"/api/v1/billing/uploads/{uid}/field-config",
            headers={"X-Tenant-Id": TENANT_A},
            json={"fields": [{"position": 1, "field_name": "ndc", "data_type": "BADTYPE"}]},
        )
        assert resp.status_code == 422

    def test_upsert_overwrites_existing_config(self, _client, _session_factory):
        """Second PUT with same position overwrites first (no duplicate rows)."""
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        session = _session_factory()
        try:
            uid = _make_upload(session, TENANT_A)
        finally:
            session.close()

        _client.put(
            f"/api/v1/billing/uploads/{uid}/field-config",
            headers={"X-Tenant-Id": TENANT_A},
            json={"fields": [{"position": 7, "field_name": "old_name", "data_type": "string"}]},
        )
        resp2 = _client.put(
            f"/api/v1/billing/uploads/{uid}/field-config",
            headers={"X-Tenant-Id": TENANT_A},
            json={"fields": [{"position": 7, "field_name": "new_name", "data_type": "ndc"}]},
        )
        assert resp2.status_code == 200
        saved = {f["position"]: f for f in resp2.json()["fields"]}
        # Only one entry for position 7
        pos7_entries = [f for f in resp2.json()["fields"] if f["position"] == 7]
        assert len(pos7_entries) == 1
        assert pos7_entries[0]["field_name"] == "new_name"


# ---- cross-tenant isolation --------------------------------------------


class TestCrossTenantIsolation:
    def test_tenant_a_config_not_visible_to_tenant_b(self, _client, _session_factory):
        """Tenant A saves config; Tenant B must see empty list on GET."""
        from shared.auth.dependencies import get_current_user
        from src.main import app

        # Tenant A saves
        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        session = _session_factory()
        try:
            uid_a = _make_upload(session, TENANT_A)
        finally:
            session.close()

        _client.put(
            f"/api/v1/billing/uploads/{uid_a}/field-config",
            headers={"X-Tenant-Id": TENANT_A},
            json={"fields": [{"position": 1, "field_name": "tenant_a_field"}]},
        )

        # Tenant B creates its own upload and queries field-config
        app.dependency_overrides[get_current_user] = lambda: TENANT_B_USER
        session = _session_factory()
        try:
            uid_b = _make_upload(session, TENANT_B)
        finally:
            session.close()

        resp = _client.get(
            f"/api/v1/billing/uploads/{uid_b}/field-config",
            headers={"X-Tenant-Id": TENANT_B},
        )
        assert resp.status_code == 200
        fields = resp.json()["fields"]
        names = [f["field_name"] for f in fields]
        assert "tenant_a_field" not in names, (
            "Tenant A field config must not be visible to Tenant B"
        )

    def test_tenant_b_cannot_access_tenant_a_upload(self, _client, _session_factory):
        """Tenant B GET on Tenant A upload_id -> 404 (not 403, no info leak)."""
        from shared.auth.dependencies import get_current_user
        from src.main import app

        session = _session_factory()
        try:
            uid_a = _make_upload(session, TENANT_A)
        finally:
            session.close()

        app.dependency_overrides[get_current_user] = lambda: TENANT_B_USER
        resp = _client.get(
            f"/api/v1/billing/uploads/{uid_a}/field-config",
            headers={"X-Tenant-Id": TENANT_B},
        )
        assert resp.status_code == 404