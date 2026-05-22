"""Hook-visible test file for modules/billing/src/models/tables.py.

All upload_id propagation assertions live in test_upload_id_propagation.py.
This file satisfies the Werkbench test-first gate (which matches on stem
'tables' -> 'test_tables.py') and re-exports those tests so pytest discovers
them from either entry point.

Stage 1 additions: ClaimUploadRawRow model assertions (positional capture).
"""
from modules.billing.tests.unit.test_upload_id_propagation import (  # noqa: F401
    test_carryover_has_amount_column,
    test_carryover_has_ap_record_id_column,
    test_carryover_has_created_at_column,
    test_carryover_has_id_column,
    test_carryover_has_reason_column,
    test_carryover_has_tenant_id_column,
    test_carryover_has_upload_id_column,
    test_carryover_model_exists,
    test_carryover_schema_is_billing,
    test_carryover_upload_id_fk_to_uploads,
    test_carryover_upload_id_is_nullable,
    test_invoice_line_item_has_upload_id_column,
    test_invoice_line_item_upload_id_fk_to_uploads,
    test_invoice_line_item_upload_id_is_nullable,
    test_invoice_line_item_upload_id_is_uuid_type,
    test_payment_batch_has_upload_id_column,
    test_payment_batch_upload_id_fk_to_uploads,
    test_payment_batch_upload_id_is_nullable,
    test_payment_batch_upload_id_is_uuid_type,
)


# ---------------------------------------------------------------------------
# ClaimUploadRawRow model assertions (Stage 1 positional capture)
# ---------------------------------------------------------------------------

def test_claim_upload_raw_row_model_importable():
    """ClaimUploadRawRow is importable from tables."""
    from src.models.tables import ClaimUploadRawRow  # noqa: F401
    assert ClaimUploadRawRow is not None


def test_claim_upload_raw_row_tablename():
    """Table name is claim_upload_raw_rows."""
    from src.models.tables import ClaimUploadRawRow
    assert ClaimUploadRawRow.__tablename__ == "claim_upload_raw_rows"


def test_claim_upload_raw_row_schema():
    """Table lives in the billing schema."""
    from src.models.tables import ClaimUploadRawRow
    args = ClaimUploadRawRow.__table_args__
    schema_dict = next((a for a in args if isinstance(a, dict)), {})
    assert schema_dict.get("schema") == "billing"


def test_claim_upload_raw_row_has_tenant_id():
    """tenant_id column present and not nullable."""
    from src.models.tables import ClaimUploadRawRow
    col = ClaimUploadRawRow.__table__.c["tenant_id"]
    assert not col.nullable


def test_claim_upload_raw_row_has_upload_id():
    """upload_id column present with FK to billing.uploads."""
    from src.models.tables import ClaimUploadRawRow
    col = ClaimUploadRawRow.__table__.c["upload_id"]
    assert col is not None
    fk_targets = [fk.target_fullname for fk in col.foreign_keys]
    assert any("uploads.id" in t for t in fk_targets)


def test_claim_upload_raw_row_has_row_number():
    """row_number column present and not nullable."""
    from src.models.tables import ClaimUploadRawRow
    col = ClaimUploadRawRow.__table__.c["row_number"]
    assert not col.nullable


def test_claim_upload_raw_row_has_field_count():
    """field_count column present and not nullable."""
    from src.models.tables import ClaimUploadRawRow
    col = ClaimUploadRawRow.__table__.c["field_count"]
    assert not col.nullable


def test_claim_upload_raw_row_has_fields_blob():
    """fields_blob column present (tenant-AAD-encrypted LargeBinary for PHI).

    Renamed from 'fields' (EncryptedJSON) to 'fields_blob' (LargeBinary with
    per-row tenant AAD) so that cross-tenant ciphertext attacks are prevented.
    """
    from src.models.tables import ClaimUploadRawRow
    col = ClaimUploadRawRow.__table__.c["fields_blob"]
    assert col is not None


def test_claim_upload_raw_row_has_captured_status():
    """UploadStatus.captured enum value exists."""
    from src.models.tables import UploadStatus
    assert UploadStatus.captured.value == "captured"


def test_claim_upload_raw_row_unique_constraint():
    """(upload_id, row_number) unique constraint exists."""
    from src.models.tables import ClaimUploadRawRow
    constraints = ClaimUploadRawRow.__table__.constraints
    uq_names = {c.name for c in constraints if hasattr(c, "columns")}
    assert "uq_raw_row_upload_rownum" in uq_names


def test_claim_upload_raw_row_has_captured_at():
    """captured_at column present (audit timestamp)."""
    from src.models.tables import ClaimUploadRawRow
    col = ClaimUploadRawRow.__table__.c["captured_at"]
    assert not col.nullable


def test_claim_upload_raw_row_index_exists():
    """idx_raw_rows_tenant_upload index defined on ClaimUploadRawRow."""
    from src.models.tables import ClaimUploadRawRow
    index_names = {i.name for i in ClaimUploadRawRow.__table__.indexes}
    assert "idx_raw_rows_tenant_upload" in index_names


def test_claim_upload_raw_row_upload_id_cascade():
    """upload_id FK has CASCADE delete so rows clean up with their upload."""
    from src.models.tables import ClaimUploadRawRow
    col = ClaimUploadRawRow.__table__.c["upload_id"]
    fk = next(iter(col.foreign_keys))
    assert fk.ondelete == "CASCADE"


def test_upload_status_captured_not_duplicated():
    """UploadStatus.captured is defined exactly once."""
    from src.models.tables import UploadStatus
    values = [m.value for m in UploadStatus]
    assert values.count("captured") == 1
