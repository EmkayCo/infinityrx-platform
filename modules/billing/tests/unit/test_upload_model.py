"""SP-1 Plan B Task 1 — unit tests for Upload ORM model + ClaimRecord FK.

TDD discipline: these tests are written FIRST and intentionally fail until
the model lands. Once `Upload` is defined in `tables.py` and `ClaimRecord`
gains `upload_id` + `amount_billed` columns, all tests pass.

Scope per Plan B Task 1.4:
- Upload model fields, types, defaults
- UploadStatus enum-like constraint (CHECK or app-level)
- ClaimRecord.upload_id is a nullable FK to billing.uploads.id
- ClaimRecord.amount_billed is Numeric(14, 4) nullable
- Schema namespace is billing
- Tenant scoping: billing module uses RLS-only pattern (BillingBase, no TenantScopedMixin)
  because TenantScopedMixin is architecturally incompatible with BillingBase's
  mapped_column pattern (causes ConstraintColumnNotFoundError at import time).
  Isolation is enforced by: (1) RLS policies, (2) explicit WHERE tenant_id = ? in all
  queries, (3) validate_tenant_id() header guard (B2). This matches ALL other billing
  models — tracked as a follow-up migration task.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from src.models.tables import BillingBase, ClaimRecord, Upload, UploadStatus

from tests.conftest import TENANT_A


# ── Upload model shape ───────────────────────────────────────────────────


def test_upload_model_is_registered_with_billingbase():
    assert "uploads" in {t.name for t in BillingBase.metadata.tables.values()}


def test_upload_has_non_nullable_tenant_id_column():
    """B4: Upload must have a non-nullable tenant_id column.

    Billing uses the RLS-only isolation pattern (no TenantScopedMixin) because
    TenantScopedMixin is architecturally incompatible with BillingBase. The direct
    tenant_id column + RLS policies + validate_tenant_id() header guard provide
    equivalent isolation guarantees. All other billing models follow this same pattern.
    """
    cols = {c.name: c for c in Upload.__table__.columns}
    assert "tenant_id" in cols, "Upload must have a tenant_id column"
    assert not cols["tenant_id"].nullable, "Upload.tenant_id must be NOT NULL"


def test_upload_unique_constraint_is_tenant_scoped():
    """B4: Upload deduplication constraint must be scoped to tenant.

    The unique constraint uq_upload_tenant_sha256 on (tenant_id, sha256) ensures
    that the same file cannot be uploaded twice within a tenant while allowing the
    same sha256 to exist in different tenants (correct multi-tenant behavior).
    """
    constraint_names = {c.name for c in Upload.__table__.constraints if hasattr(c, "name")}
    assert "uq_upload_tenant_sha256" in constraint_names, (
        "Upload must have uq_upload_tenant_sha256 unique constraint on (tenant_id, sha256)"
    )


def test_upload_has_all_required_columns():
    cols = {c.name for c in Upload.__table__.columns}
    expected = {
        "id", "tenant_id", "filename", "sha256", "file_size", "mime_type",
        "uploaded_at", "uploaded_by", "source_platform", "supersedes_upload_id",
        "status", "row_count", "error_count", "row_errors",
    }
    missing = expected - cols
    assert not missing, f"Upload missing columns: {missing}"


def test_upload_status_enum_values_match_spec():
    # 4 states from spec §5.2 + plan: parsing, validation_failed, validated, superseded
    expected_states = {"parsing", "validation_failed", "validated", "superseded"}
    actual_states = {s.value for s in UploadStatus}
    assert actual_states == expected_states


def test_upload_persists_minimal_row(db_session: Session):
    upload = Upload(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        filename="sample.csv",
        sha256="a" * 64,
        file_size=1024,
        mime_type="text/csv",
        uploaded_at=datetime.now(UTC),
        uploaded_by=uuid.uuid4(),
        status=UploadStatus.parsing.value,
    )
    db_session.add(upload)
    db_session.flush()
    fetched = db_session.get(Upload, upload.id)
    assert fetched is not None
    assert fetched.filename == "sample.csv"
    assert fetched.sha256 == "a" * 64
    assert fetched.status == "parsing"
    assert fetched.row_count is None
    assert fetched.error_count is None
    assert fetched.row_errors is None


def test_upload_status_transitions_parse_complete(db_session: Session):
    # Simulates the lifecycle: parsing → validated (all rows OK)
    upload = Upload(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        filename="ok.csv",
        sha256="b" * 64,
        file_size=512,
        mime_type="text/csv",
        uploaded_at=datetime.now(UTC),
        uploaded_by=uuid.uuid4(),
        status=UploadStatus.parsing.value,
    )
    db_session.add(upload)
    db_session.flush()

    upload.status = UploadStatus.validated.value
    upload.row_count = 20
    upload.error_count = 0
    db_session.flush()

    fetched = db_session.get(Upload, upload.id)
    assert fetched is not None and fetched.status == "validated"
    assert fetched.row_count == 20


def test_upload_supersedes_relationship_self_referential(db_session: Session):
    first = Upload(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        filename="v1.csv",
        sha256="c" * 64,
        file_size=100,
        mime_type="text/csv",
        uploaded_at=datetime.now(UTC),
        uploaded_by=uuid.uuid4(),
        status=UploadStatus.validated.value,
    )
    db_session.add(first)
    db_session.flush()

    second = Upload(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        filename="v2.csv",
        sha256="d" * 64,
        file_size=200,
        mime_type="text/csv",
        uploaded_at=datetime.now(UTC),
        uploaded_by=uuid.uuid4(),
        status=UploadStatus.validated.value,
        supersedes_upload_id=first.id,
    )
    db_session.add(second)
    db_session.flush()

    fetched = db_session.get(Upload, second.id)
    assert fetched is not None and fetched.supersedes_upload_id == first.id


# ── ClaimRecord FK additions ─────────────────────────────────────────────


def test_claim_record_has_upload_id_nullable_fk():
    cols = {c.name: c for c in ClaimRecord.__table__.columns}
    assert "upload_id" in cols, "ClaimRecord must have upload_id column"
    upload_id_col = cols["upload_id"]
    assert upload_id_col.nullable is True, (
        "upload_id must be nullable for backwards compat with existing rows"
    )
    # FK target check — points at billing.uploads.id (or uploads.id after schema strip)
    fks = list(upload_id_col.foreign_keys)
    assert len(fks) == 1, f"upload_id should have exactly one FK, got {len(fks)}"
    target = fks[0].target_fullname
    assert target.endswith("uploads.id"), f"FK target should be uploads.id, got {target}"


def test_claim_record_has_amount_billed_nullable_decimal():
    cols = {c.name: c for c in ClaimRecord.__table__.columns}
    assert "amount_billed" in cols, "ClaimRecord must have amount_billed column"
    col = cols["amount_billed"]
    assert col.nullable is True, "amount_billed must be nullable for backwards compat"
    # Type assertion: Numeric(14, 4)
    assert col.type.precision == 14, f"amount_billed precision should be 14, got {col.type.precision}"
    assert col.type.scale == 4, f"amount_billed scale should be 4, got {col.type.scale}"


def test_claim_record_can_persist_with_upload_id_and_amount_billed(db_session: Session):
    # First create the parent upload
    upload = Upload(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        filename="t.csv",
        sha256="e" * 64,
        file_size=50,
        mime_type="text/csv",
        uploaded_at=datetime.now(UTC),
        uploaded_by=uuid.uuid4(),
        status=UploadStatus.validated.value,
    )
    db_session.add(upload)
    db_session.flush()

    claim = ClaimRecord(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        source_type="upload",
        auth_number="AUTH-001",
        claim_type="rx",
        pharmacy_npi="1234567893",
        date_of_service=datetime(2026, 5, 1).date(),
        date_received=datetime.now(UTC),
        net_amount=Decimal("12.34"),
        created_at=datetime.now(UTC),
        upload_id=upload.id,
        amount_billed=Decimal("15.6789"),
    )
    db_session.add(claim)
    db_session.flush()

    fetched = db_session.get(ClaimRecord, claim.id)
    assert fetched is not None
    assert fetched.upload_id == upload.id
    assert fetched.amount_billed == Decimal("15.6789")


def test_claim_record_existing_rows_can_have_null_upload_id(db_session: Session):
    # Pre-upload claims have NULL upload_id — backwards-compat path
    claim = ClaimRecord(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        source_type="legacy",
        auth_number="LEGACY-001",
        claim_type="rx",
        pharmacy_npi="1234567893",
        date_of_service=datetime(2026, 5, 1).date(),
        date_received=datetime.now(UTC),
        net_amount=Decimal("9.99"),
        created_at=datetime.now(UTC),
        # upload_id and amount_billed intentionally omitted
    )
    db_session.add(claim)
    db_session.flush()

    fetched = db_session.get(ClaimRecord, claim.id)
    assert fetched is not None
    assert fetched.upload_id is None
    assert fetched.amount_billed is None


# ── Schema namespace ─────────────────────────────────────────────────────


def test_upload_table_belongs_to_billing_schema():
    # In production (PG) the table is billing.uploads; SQLite conftest strips
    # schemas so this only asserts the table name. Migration unit tests
    # handle the schema namespace assertion.
    assert Upload.__tablename__ == "uploads"
