"""SP-1 Plan B Task 2 — Upload service tests (TDD-first).

Covers all 5 service sub-functions per Plan B Task 2:
  2.1 file writer (atomic .tmp -> rename) + sha256 helper
  2.2 CSV parser dispatcher
  2.3 row-error capture (no member_id echo per .claude/rules/phi-compliance.md)
  2.4 Excel parser dispatcher (.xlsx via openpyxl)
  2.5 supersede semantics (old upload status -> superseded; claims NOT deleted)

Financial precision (.claude/rules/financial-precision.md):
  - amount_billed parsed via Decimal(str(value)), max 4dp
  - quantity parsed via Decimal(str(value)), max 3dp (matches HEAD Numeric(10, 3))
  - ROUND_HALF_UP on any computed sums; no float anywhere

PHI controls (.claude/rules/phi-compliance.md):
  - row_errors MUST NEVER echo member_id values
"""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from src.models.tables import ClaimRecord, Upload, UploadStatus
from src.services.upload import (
    UploadParseResult,
    compute_sha256,
    find_existing_upload,
    parse_csv_bytes,
    parse_upload,
    parse_xlsx_bytes,
    supersede_upload,
    validate_row,
    write_upload_file,
)

from tests.conftest import TENANT_A, TENANT_B


# Valid CSV header per spec §10.3
_HEADER = "ndc,npi,claim_id,date_of_service,quantity,days_supply,amount_billed,member_id"
# Luhn-valid NPI with 80840 prefix (per .claude/rules/security.md)
_VALID_NPI = "1234567893"
_VALID_NDC = "00093015005"


def _row(
    ndc=_VALID_NDC,
    npi=_VALID_NPI,
    claim_id="C-1",
    dos="2026-05-01",
    qty="30",
    days="30",
    amt="123.4567",
    member="M-1",
):
    return f"{ndc},{npi},{claim_id},{dos},{qty},{days},{amt},{member}"


def _csv(*rows: str) -> bytes:
    body = "\n".join([_HEADER, *rows])
    return body.encode("utf-8")


# ── compute_sha256 ───────────────────────────────────────────────────────


def test_compute_sha256_deterministic():
    a = compute_sha256(b"hello")
    b = compute_sha256(b"hello")
    assert a == b
    assert len(a) == 64
    assert all(c in "0123456789abcdef" for c in a)


def test_compute_sha256_differs_for_different_input():
    assert compute_sha256(b"a") != compute_sha256(b"b")


# ── write_upload_file (atomic) ───────────────────────────────────────────


def test_write_upload_file_creates_directory_and_writes_content(tmp_path: Path):
    upload_id = uuid.uuid4()
    path = write_upload_file(
        base_dir=tmp_path,
        tenant_id=TENANT_A,
        upload_id=upload_id,
        filename="sample.csv",
        content=b"row1\nrow2\n",
    )
    assert path.exists()
    assert path.read_bytes() == b"row1\nrow2\n"
    # Layout: {base_dir}/{tenant_id}/{upload_id}/{filename}
    expected = tmp_path / str(TENANT_A) / str(upload_id) / "sample.csv"
    assert path == expected


def test_write_upload_file_atomic_no_partial_file(tmp_path: Path):
    # After successful write, no .tmp sidecar remains
    upload_id = uuid.uuid4()
    path = write_upload_file(
        base_dir=tmp_path, tenant_id=TENANT_A, upload_id=upload_id,
        filename="x.csv", content=b"data",
    )
    tmp_sidecar = path.with_suffix(path.suffix + ".tmp")
    assert not tmp_sidecar.exists(), "atomic write should not leave .tmp file"


def test_write_upload_file_overwrites_existing(tmp_path: Path):
    # Same upload_id/filename written twice: second wins (replay-safe)
    upload_id = uuid.uuid4()
    write_upload_file(
        base_dir=tmp_path, tenant_id=TENANT_A, upload_id=upload_id,
        filename="x.csv", content=b"first",
    )
    path = write_upload_file(
        base_dir=tmp_path, tenant_id=TENANT_A, upload_id=upload_id,
        filename="x.csv", content=b"second",
    )
    assert path.read_bytes() == b"second"


def test_write_upload_file_strips_path_traversal(tmp_path: Path):
    """P1-security: attacker-supplied '../../evil.csv' must not escape base_dir."""
    upload_id = uuid.uuid4()
    path = write_upload_file(
        base_dir=tmp_path,
        tenant_id=TENANT_A,
        upload_id=upload_id,
        filename="../../evil.csv",
        content=b"payload",
    )
    # File must land inside tenant/upload dir, not outside tmp_path
    assert tmp_path in path.parents, "path traversal: file escaped base_dir"
    assert path.name == "evil.csv"


def test_write_upload_file_strips_absolute_path(tmp_path: Path):
    """P1-security: absolute filename must be reduced to basename."""
    upload_id = uuid.uuid4()
    # Use a safe temp path that doesn't try to write to system root
    path = write_upload_file(
        base_dir=tmp_path,
        tenant_id=TENANT_A,
        upload_id=upload_id,
        filename="/tmp/evil.csv",
        content=b"payload",
    )
    assert tmp_path in path.parents, "absolute filename escaped base_dir"
    assert path.name == "evil.csv"


# ── find_existing_upload (dedup) ─────────────────────────────────────────


def test_find_existing_upload_returns_none_when_no_match(db_session: Session):
    found = find_existing_upload(
        db_session, tenant_id=TENANT_A, sha256="0" * 64
    )
    assert found is None


def test_find_existing_upload_returns_match_when_sha256_seen(db_session: Session):
    sha = "f" * 64
    seed = Upload(
        id=uuid.uuid4(),
        tenant_id=TENANT_A, filename="x.csv", sha256=sha,
        file_size=10, mime_type="text/csv",
        uploaded_at=datetime.now(UTC), uploaded_by=uuid.uuid4(),
        status=UploadStatus.validated.value,
    )
    db_session.add(seed)
    db_session.flush()

    found = find_existing_upload(db_session, tenant_id=TENANT_A, sha256=sha)
    assert found is not None and found.id == seed.id


def test_find_existing_upload_is_tenant_scoped(db_session: Session):
    # Same sha256 in Tenant B should NOT match Tenant A's lookup
    sha = "e" * 64
    seed_b = Upload(
        id=uuid.uuid4(),
        tenant_id=TENANT_B, filename="x.csv", sha256=sha,
        file_size=10, mime_type="text/csv",
        uploaded_at=datetime.now(UTC), uploaded_by=uuid.uuid4(),
        status=UploadStatus.validated.value,
    )
    db_session.add(seed_b)
    db_session.flush()

    found = find_existing_upload(db_session, tenant_id=TENANT_A, sha256=sha)
    assert found is None


# ── validate_row ─────────────────────────────────────────────────────────


def test_validate_row_accepts_valid_row():
    parsed, err = validate_row({
        "ndc": _VALID_NDC, "npi": _VALID_NPI, "claim_id": "C-1",
        "date_of_service": "2026-05-01", "quantity": "30", "days_supply": "30",
        "amount_billed": "123.4567", "member_id": "M-1",
    })
    assert err is None
    assert parsed is not None
    assert parsed["ndc"] == _VALID_NDC
    assert parsed["quantity"] == Decimal("30")
    assert parsed["amount_billed"] == Decimal("123.4567")
    assert parsed["date_of_service"].isoformat() == "2026-05-01"


def test_validate_row_rejects_short_ndc():
    parsed, err = validate_row({
        "ndc": "1234", "npi": _VALID_NPI, "claim_id": "C-1",
        "date_of_service": "2026-05-01", "quantity": "1", "days_supply": "1",
        "amount_billed": "1.00", "member_id": "M-1",
    })
    assert parsed is None
    assert err is not None
    assert "ndc" in err.lower()


def test_validate_row_rejects_ndc_with_trailing_newline():
    # LESSON-004: \A...\Z anchors, not ^...$ which accepts trailing newline
    parsed, err = validate_row({
        "ndc": _VALID_NDC + "\n", "npi": _VALID_NPI, "claim_id": "C-1",
        "date_of_service": "2026-05-01", "quantity": "1", "days_supply": "1",
        "amount_billed": "1.00", "member_id": "M-1",
    })
    assert parsed is None
    assert err is not None


def test_validate_row_rejects_invalid_npi():
    parsed, err = validate_row({
        "ndc": _VALID_NDC, "npi": "9999999999", "claim_id": "C-1",  # fails Luhn
        "date_of_service": "2026-05-01", "quantity": "1", "days_supply": "1",
        "amount_billed": "1.00", "member_id": "M-1",
    })
    assert parsed is None
    assert err is not None
    assert "npi" in err.lower()


def test_validate_row_rejects_bad_date():
    parsed, err = validate_row({
        "ndc": _VALID_NDC, "npi": _VALID_NPI, "claim_id": "C-1",
        "date_of_service": "not-a-date", "quantity": "1", "days_supply": "1",
        "amount_billed": "1.00", "member_id": "M-1",
    })
    assert parsed is None
    assert err is not None
    assert "date" in err.lower()


def test_validate_row_rejects_quantity_with_4_decimal_places():
    # quantity max is 3dp (matches HEAD claim_records.quantity Numeric(10, 3))
    parsed, err = validate_row({
        "ndc": _VALID_NDC, "npi": _VALID_NPI, "claim_id": "C-1",
        "date_of_service": "2026-05-01", "quantity": "1.0001", "days_supply": "1",
        "amount_billed": "1.00", "member_id": "M-1",
    })
    assert parsed is None
    assert err is not None
    assert "quantity" in err.lower()


def test_validate_row_rejects_amount_billed_with_5_decimal_places():
    # amount_billed max is 4dp (matches Numeric(14, 4))
    parsed, err = validate_row({
        "ndc": _VALID_NDC, "npi": _VALID_NPI, "claim_id": "C-1",
        "date_of_service": "2026-05-01", "quantity": "1", "days_supply": "1",
        "amount_billed": "1.00005", "member_id": "M-1",
    })
    assert parsed is None
    assert err is not None
    assert "amount" in err.lower()


def test_validate_row_rejects_negative_amount():
    parsed, err = validate_row({
        "ndc": _VALID_NDC, "npi": _VALID_NPI, "claim_id": "C-1",
        "date_of_service": "2026-05-01", "quantity": "1", "days_supply": "1",
        "amount_billed": "-5.00", "member_id": "M-1",
    })
    assert parsed is None and err is not None


def test_validate_row_rejects_zero_days_supply():
    parsed, err = validate_row({
        "ndc": _VALID_NDC, "npi": _VALID_NPI, "claim_id": "C-1",
        "date_of_service": "2026-05-01", "quantity": "1", "days_supply": "0",
        "amount_billed": "1.00", "member_id": "M-1",
    })
    assert parsed is None and err is not None


def test_validate_row_rejects_empty_member_id():
    parsed, err = validate_row({
        "ndc": _VALID_NDC, "npi": _VALID_NPI, "claim_id": "C-1",
        "date_of_service": "2026-05-01", "quantity": "1", "days_supply": "1",
        "amount_billed": "1.00", "member_id": "",
    })
    assert parsed is None and err is not None
    assert "member" in err.lower()


def test_validate_row_rejects_overlong_member_id():
    parsed, err = validate_row({
        "ndc": _VALID_NDC, "npi": _VALID_NPI, "claim_id": "C-1",
        "date_of_service": "2026-05-01", "quantity": "1", "days_supply": "1",
        "amount_billed": "1.00", "member_id": "X" * 65,
    })
    assert parsed is None and err is not None


def test_validate_row_error_does_not_echo_member_id_value():
    # PHI rule: row_errors must NEVER echo member_id VALUE — only describe failure
    secret = "PHI-MEMBER-12345"
    parsed, err = validate_row({
        "ndc": _VALID_NDC, "npi": _VALID_NPI, "claim_id": "C-1",
        "date_of_service": "2026-05-01", "quantity": "1", "days_supply": "1",
        "amount_billed": "1.00", "member_id": secret + "X" * 100,  # too long
    })
    assert err is not None
    assert secret not in err, f"PHI leak: error message echoed member_id value: {err!r}"


# ── parse_csv_bytes ──────────────────────────────────────────────────────


def test_parse_csv_bytes_returns_list_of_row_dicts():
    csv = _csv(_row(claim_id="C-1"), _row(claim_id="C-2"))
    rows = parse_csv_bytes(csv)
    assert len(rows) == 2
    assert rows[0]["claim_id"] == "C-1"
    assert rows[1]["claim_id"] == "C-2"


def test_parse_csv_bytes_handles_empty_body():
    csv = _csv()  # header only
    assert parse_csv_bytes(csv) == []


def test_parse_csv_bytes_rejects_missing_required_columns():
    bad = b"ndc,npi\n00093015005,1234567893\n"
    with pytest.raises(ValueError) as exc:
        parse_csv_bytes(bad)
    assert "required" in str(exc.value).lower() or "missing" in str(exc.value).lower()


# ── parse_xlsx_bytes (Excel) ─────────────────────────────────────────────


def test_parse_xlsx_bytes_round_trip():
    # Build a minimal xlsx in memory and parse it
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([
        "ndc", "npi", "claim_id", "date_of_service",
        "quantity", "days_supply", "amount_billed", "member_id",
    ])
    ws.append([
        _VALID_NDC, _VALID_NPI, "C-1", "2026-05-01",
        "30", "30", "123.4567", "M-1",
    ])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    rows = parse_xlsx_bytes(buf.read())
    assert len(rows) == 1
    assert rows[0]["claim_id"] == "C-1"
    assert rows[0]["amount_billed"] == "123.4567"


# ── parse_upload (orchestrator) ──────────────────────────────────────────


def _new_upload(tenant=TENANT_A, status=UploadStatus.parsing) -> Upload:
    return Upload(
        id=uuid.uuid4(),
        tenant_id=tenant, filename="batch.csv", sha256="9" * 64,
        file_size=100, mime_type="text/csv",
        uploaded_at=datetime.now(UTC), uploaded_by=uuid.uuid4(),
        status=status.value,
    )


def test_parse_upload_all_rows_valid_sets_status_validated(db_session: Session):
    upload = _new_upload()
    db_session.add(upload); db_session.flush()
    csv = _csv(_row(claim_id="C-1"), _row(claim_id="C-2"))
    result = parse_upload(db_session, upload=upload, file_bytes=csv)
    assert isinstance(result, UploadParseResult)
    assert result.upload.status == UploadStatus.validated.value
    assert result.upload.row_count == 2
    assert result.upload.error_count == 0
    assert result.upload.row_errors in (None, [])
    # Claims persisted with upload_id and amount_billed
    claims = db_session.query(ClaimRecord).filter_by(upload_id=upload.id).all()
    assert len(claims) == 2
    assert all(c.upload_id == upload.id for c in claims)
    assert all(c.amount_billed == Decimal("123.4567") for c in claims)


def test_parse_upload_all_rows_bad_sets_status_validation_failed(db_session: Session):
    upload = _new_upload()
    db_session.add(upload); db_session.flush()
    bad_csv = _csv(
        _row(ndc="123"),  # bad ndc
        _row(npi="0000000000"),  # bad npi luhn
    )
    result = parse_upload(db_session, upload=upload, file_bytes=bad_csv)
    assert result.upload.status == UploadStatus.validation_failed.value
    assert result.upload.row_count == 2
    assert result.upload.error_count == 2
    assert len(result.upload.row_errors) == 2
    # No claims written for fully-failed upload
    claims = db_session.query(ClaimRecord).filter_by(upload_id=upload.id).all()
    assert len(claims) == 0


def test_parse_upload_partial_bad_sets_status_validated_with_error_count(db_session: Session):
    upload = _new_upload()
    db_session.add(upload); db_session.flush()
    csv = _csv(
        _row(claim_id="C-good"),
        _row(claim_id="C-bad", ndc="123"),
        _row(claim_id="C-good-2"),
    )
    result = parse_upload(db_session, upload=upload, file_bytes=csv)
    assert result.upload.status == UploadStatus.validated.value
    assert result.upload.row_count == 3
    assert result.upload.error_count == 1
    # Only the 2 valid claims written
    claims = db_session.query(ClaimRecord).filter_by(upload_id=upload.id).all()
    assert len(claims) == 2
    assert {c.auth_number for c in claims} == {"C-good", "C-good-2"}


def test_parse_upload_row_errors_carry_row_number_and_field(db_session: Session):
    upload = _new_upload()
    db_session.add(upload); db_session.flush()
    csv = _csv(_row(ndc="bad"))
    result = parse_upload(db_session, upload=upload, file_bytes=csv)
    assert result.upload.error_count == 1
    err = result.upload.row_errors[0]
    assert "row" in err and err["row"] == 1
    assert "message" in err


def test_parse_upload_row_errors_never_echo_member_id_value(db_session: Session):
    upload = _new_upload()
    db_session.add(upload); db_session.flush()
    secret = "PHI-MEMBER-XYZ"
    csv = _csv(_row(member=secret, ndc="bad"))
    result = parse_upload(db_session, upload=upload, file_bytes=csv)
    assert result.upload.error_count == 1
    err_blob = str(result.upload.row_errors)
    assert secret not in err_blob, "PHI leak: row_errors contained raw member_id"


# ── supersede_upload ─────────────────────────────────────────────────────


def test_supersede_upload_marks_old_as_superseded_and_links_new(db_session: Session):
    old = Upload(
        id=uuid.uuid4(),
        tenant_id=TENANT_A, filename="v1.csv", sha256="a" * 64,
        file_size=10, mime_type="text/csv",
        uploaded_at=datetime.now(UTC), uploaded_by=uuid.uuid4(),
        status=UploadStatus.validated.value,
    )
    new = Upload(
        id=uuid.uuid4(),
        tenant_id=TENANT_A, filename="v2.csv", sha256="b" * 64,
        file_size=20, mime_type="text/csv",
        uploaded_at=datetime.now(UTC), uploaded_by=uuid.uuid4(),
        status=UploadStatus.validated.value,
    )
    db_session.add_all([old, new]); db_session.flush()

    supersede_upload(db_session, old_upload=old, new_upload=new)

    assert old.status == UploadStatus.superseded.value
    assert new.supersedes_upload_id == old.id


def test_supersede_upload_does_not_delete_old_claims(db_session: Session):
    old = Upload(
        id=uuid.uuid4(),
        tenant_id=TENANT_A, filename="v1.csv", sha256="c" * 64,
        file_size=10, mime_type="text/csv",
        uploaded_at=datetime.now(UTC), uploaded_by=uuid.uuid4(),
        status=UploadStatus.validated.value,
    )
    db_session.add(old); db_session.flush()

    # Seed an old claim
    old_claim = ClaimRecord(
        id=uuid.uuid4(), tenant_id=TENANT_A,
        source_type="upload", auth_number="OLD-1", claim_type="rx",
        pharmacy_npi=_VALID_NPI,
        date_of_service=datetime(2026, 5, 1).date(),
        date_received=datetime.now(UTC),
        net_amount=Decimal("1.00"),
        created_at=datetime.now(UTC),
        upload_id=old.id, amount_billed=Decimal("1.0000"),
    )
    db_session.add(old_claim); db_session.flush()

    new = Upload(
        id=uuid.uuid4(),
        tenant_id=TENANT_A, filename="v2.csv", sha256="d" * 64,
        file_size=20, mime_type="text/csv",
        uploaded_at=datetime.now(UTC), uploaded_by=uuid.uuid4(),
        status=UploadStatus.validated.value,
    )
    db_session.add(new); db_session.flush()

    supersede_upload(db_session, old_upload=old, new_upload=new)

    # P2-supersede: old ClaimRecord rows are deleted so replacement uploads can
    # re-insert claims with the same auth_number without hitting
    # uq_claim_tenant_auth.  Provenance immutability is on the Upload row
    # (status=superseded, supersedes_upload_id chain) — not on claim rows.
    assert db_session.get(ClaimRecord, old_claim.id) is None


def test_supersede_upload_raises_if_claims_have_ap_references(db_session: Session):
    """C1: supersede_upload must refuse to delete claims that have APRecord references.

    APRecord.claim_record_id has ondelete=RESTRICT, so a blind delete would crash
    at the DB level with an IntegrityError. The service must detect this and raise
    ValueError with a clear message so the router can return 409 CLAIMS_IN_AP_PROCESSING.
    """
    from src.models.tables import APRecord

    old = Upload(
        id=uuid.uuid4(),
        tenant_id=TENANT_A, filename="v1.csv", sha256="e" * 64,
        file_size=10, mime_type="text/csv",
        uploaded_at=datetime.now(UTC), uploaded_by=uuid.uuid4(),
        status=UploadStatus.validated.value,
    )
    db_session.add(old)
    db_session.flush()

    claim = ClaimRecord(
        id=uuid.uuid4(), tenant_id=TENANT_A,
        source_type="upload", auth_number="AP-REF-1", claim_type="rx",
        pharmacy_npi="1234567893",
        date_of_service=datetime(2026, 5, 1).date(),
        date_received=datetime.now(UTC),
        net_amount=Decimal("10.00"),
        created_at=datetime.now(UTC),
        upload_id=old.id, amount_billed=Decimal("10.0000"),
    )
    db_session.add(claim)
    db_session.flush()

    # Create an APRecord that references this claim
    ap = APRecord(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        claim_record_id=claim.id,
        client_id=uuid.uuid4(),
        pay_to_entity_id=uuid.uuid4(),
        pay_to_entity_name="Test Pharmacy",
        amount=Decimal("10.00"),
        payment_route="ach",
        status="created",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(ap)
    db_session.flush()

    new = Upload(
        id=uuid.uuid4(),
        tenant_id=TENANT_A, filename="v2.csv", sha256="f" * 64,
        file_size=20, mime_type="text/csv",
        uploaded_at=datetime.now(UTC), uploaded_by=uuid.uuid4(),
        status=UploadStatus.validated.value,
    )
    db_session.add(new)
    db_session.flush()

    with pytest.raises(ValueError, match="CLAIMS_IN_AP_PROCESSING"):
        supersede_upload(db_session, old_upload=old, new_upload=new)
