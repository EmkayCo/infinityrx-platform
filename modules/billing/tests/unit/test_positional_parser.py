"""Unit tests for positional (pipe-delimited headerless) upload parser.

Stage 1 requirements:
  - All fields captured including trailing empties (position fidelity)
  - Variable field count per row (no hardcoded 53)
  - Tenant-scoped rows: every ClaimUploadRawRow has tenant_id
  - PHI encryption round-trip: fields stored as EncryptedJSON (ciphertext != plaintext)
  - Row-count fidelity: rows_stored == lines_in_file
  - Existing CSV path unaffected
  - Format detection: pipe-delimited -> positional, comma-CSV-with-header -> CSV
  - Decimal/financial fields stored as captured strings (no coercion)
  - PHI: field values never logged (enforced by not logging in parser; tests verify storage)
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from datetime import UTC, datetime
from unittest.mock import patch, MagicMock

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

_PROJECT_ROOT = _MODULE_ROOT.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.models.tables import BillingBase, ClaimUploadRawRow, Upload, UploadStatus
from src.services.upload import (
    detect_format,
    parse_positional_bytes,
    parse_upload,
)


# ---------------------------------------------------------------------------
# In-memory SQLite engine for isolated tests
# NOTE: EncryptedJSON uses LargeBinary which SQLite stores as BLOB -- compatible.
# We patch the crypto layer to use a test key so encryption is real but testable.
# ---------------------------------------------------------------------------

TENANT_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
USER_A = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


@pytest.fixture(scope="module")
def _engine():
    """SQLite in-memory engine with schema stripped for billing tables."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    # Strip schemas (SQLite has no schema support)
    for table in BillingBase.metadata.tables.values():
        table.schema = None

    BillingBase.metadata.create_all(engine)
    yield engine
    BillingBase.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(_engine):
    """SAVEPOINT-based per-test isolation (LESSON-001)."""
    connection = _engine.connect()
    outer = connection.begin()
    nested = connection.begin_nested()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )

    @event.listens_for(session, "after_transaction_end")
    def _restart(sess, transaction):
        nonlocal nested
        if transaction.nested and not transaction._parent.nested:
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


def _make_upload(tenant_id: uuid.UUID, filename: str = "test.txt") -> Upload:
    return Upload(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        filename=filename,
        sha256="a" * 64,
        file_size=100,
        mime_type="text/plain",
        uploaded_at=datetime.now(UTC),
        uploaded_by=USER_A,
        status=UploadStatus.parsing.value,
    )


# ---------------------------------------------------------------------------
# detect_format tests
# ---------------------------------------------------------------------------


def test_detect_format_pipe_headerless():
    """Pipe-delimited content with no comma header is positional."""
    content = b"A|B|C|D\nE|F|G|H\n"
    assert detect_format(content) == "positional"


def test_detect_format_csv_with_header():
    """CSV with comma header row is csv."""
    content = b"ndc,npi,claim_id,date_of_service,quantity,days_supply,amount_billed,member_id\n00093310305,1234567893,CLM1,2026-01-15,1.000,30,99.99,MBR001\n"
    assert detect_format(content) == "csv"


def test_detect_format_pipe_detected_over_csv():
    """If first non-empty line contains pipe, it is positional even with commas present."""
    # Real export rows contain numeric values with potential commas in amounts
    content = b"123|P|ABC|IFX|01/01/2026|01/01/2026|M01|M01|HISTORY|CLAIM|01/01/1980|01|1234567890|00093310305|12345|1.00|30|1|0|100.0|5.0|105.0|\n"
    assert detect_format(content) == "positional"


# ---------------------------------------------------------------------------
# parse_positional_bytes tests
# ---------------------------------------------------------------------------


def test_parse_positional_bytes_captures_all_fields():
    """Every pipe-delimited field captured, including trailing empties."""
    # 53 fields per real export row; last several are empty
    row = "|".join(["val" + str(i) for i in range(1, 50)] + ["", "", "", "PHXCOM30", ""])
    content = (row + "\n").encode()
    rows = parse_positional_bytes(content)
    assert len(rows) == 1
    fields = rows[0]
    # 53 fields (50 vals + 3 empties + PHXCOM30 + trailing empty)
    assert fields["1"] == "val1"
    assert fields["49"] == "val49"
    # Trailing empty fields preserved
    total = len(fields)
    assert total == 54  # 49 vals + 5 trailing fields


def test_parse_positional_bytes_variable_field_count():
    """Different rows may have different field counts; each captured faithfully."""
    line1 = "A|B|C"
    line2 = "X|Y"
    content = (line1 + "\n" + line2 + "\n").encode()
    rows = parse_positional_bytes(content)
    assert len(rows) == 2
    assert rows[0] == {"1": "A", "2": "B", "3": "C"}
    assert rows[1] == {"1": "X", "2": "Y"}


def test_parse_positional_bytes_preserves_trailing_empties():
    """Trailing empty fields are NOT dropped -- position fidelity required."""
    content = b"A|B||||\n"
    rows = parse_positional_bytes(content)
    assert rows[0] == {"1": "A", "2": "B", "3": "", "4": "", "5": "", "6": ""}


def test_parse_positional_bytes_skips_blank_lines():
    """Blank lines in file are skipped; only data lines produce rows."""
    content = b"A|B|C\n\n\nD|E|F\n"
    rows = parse_positional_bytes(content)
    assert len(rows) == 2


def test_parse_positional_bytes_real_sample():
    """Spot-check against a representative real-format row (53 fields)."""
    row = (
        "20260315842652919980|P|025706|IFX|03/15/2026|06/12/2025|IC47103004|IC47103004"
        "|HISTORY|CLAIM|01/01/1980|01|1013998913|78206018701|16474215|1.60|28|1|0"
        "|4359.6|5.0|4364.6|4364.6|0.0|1427113760|0.0|0.0|||591.91|2167.34|0.0|0.0"
        "|2167.34|0.0|0.0|591.91|2|03/15/2026 23:24:25|14||||0||||||||PHXCOM30|"
    )
    content = (row + "\n").encode()
    rows = parse_positional_bytes(content)
    assert len(rows) == 1
    fields = rows[0]
    # pos01 = claim id
    assert fields["1"] == "20260315842652919980"
    # pos11 = DOB (PHI)
    assert fields["11"] == "01/01/1980"
    # pos13 = NPI
    assert fields["13"] == "1013998913"
    # pos14 = NDC
    assert fields["14"] == "78206018701"
    # pos16 = qty
    assert fields["16"] == "1.60"
    # pos17 = days
    assert fields["17"] == "28"
    # pos20 = first dollar amount
    assert fields["20"] == "4359.6"
    # Last field (trailing after PHXCOM30) preserved as empty
    field_count = len(fields)
    assert field_count == 53


# ---------------------------------------------------------------------------
# parse_upload positional path tests (with DB)
# ---------------------------------------------------------------------------


def _pipe_content(n_rows: int = 3) -> bytes:
    """Generate n_rows of synthetic pipe-delimited data (53 fields each)."""
    base = (
        "20260315{n:012d}|P|025706|IFX|03/15/2026|06/12/2025|IC47103004|IC47103004"
        "|HISTORY|CLAIM|01/01/1980|01|1013998913|78206018701|16474215|1.60|28|1|0"
        "|4359.6|5.0|4364.6|4364.6|0.0|1427113760|0.0|0.0|||591.91|2167.34|0.0|0.0"
        "|2167.34|0.0|0.0|591.91|2|03/15/2026 23:24:25|14||||0||||||||PHXCOM30|"
    )
    lines = [base.format(n=i) for i in range(n_rows)]
    return "\n".join(lines).encode()


def test_parse_upload_positional_row_count_fidelity(db):
    """rows_stored == lines_in_file for pipe-delimited content."""
    upload = _make_upload(TENANT_A, filename="test.txt")
    db.add(upload)
    db.flush()

    content = _pipe_content(n_rows=5)
    result = parse_upload(db, upload=upload, file_bytes=content)

    assert result.raw_rows_written == 5
    assert upload.status == UploadStatus.captured.value
    assert upload.row_count == 5

    stored = db.execute(
        select(ClaimUploadRawRow).where(
            ClaimUploadRawRow.upload_id == upload.id,
            ClaimUploadRawRow.tenant_id == TENANT_A,
        )
    ).scalars().all()
    assert len(stored) == 5


def test_parse_upload_positional_row_numbers(db):
    """row_number is 1-based and sequential."""
    upload = _make_upload(TENANT_A, filename="file.txt")
    db.add(upload)
    db.flush()

    content = _pipe_content(n_rows=3)
    parse_upload(db, upload=upload, file_bytes=content)

    rows = db.execute(
        select(ClaimUploadRawRow)
        .where(
            ClaimUploadRawRow.upload_id == upload.id,
            ClaimUploadRawRow.tenant_id == TENANT_A,
        )
        .order_by(ClaimUploadRawRow.row_number)
    ).scalars().all()

    assert [r.row_number for r in rows] == [1, 2, 3]


def test_parse_upload_positional_field_count_stored(db):
    """field_count column reflects actual field count from the source row."""
    upload = _make_upload(TENANT_A, filename="export.txt")
    db.add(upload)
    db.flush()

    content = _pipe_content(n_rows=1)
    parse_upload(db, upload=upload, file_bytes=content)

    row = db.execute(
        select(ClaimUploadRawRow).where(
            ClaimUploadRawRow.upload_id == upload.id,
        )
    ).scalar_one()

    # The synthetic row has 53 fields
    assert row.field_count == 53


def test_parse_upload_positional_tenant_scoped(db):
    """Every stored raw row carries the correct tenant_id."""
    upload = _make_upload(TENANT_A, filename="export.txt")
    db.add(upload)
    db.flush()

    content = _pipe_content(n_rows=4)
    parse_upload(db, upload=upload, file_bytes=content)

    rows = db.execute(
        select(ClaimUploadRawRow).where(
            ClaimUploadRawRow.upload_id == upload.id,
        )
    ).scalars().all()

    for row in rows:
        assert row.tenant_id == TENANT_A


def test_parse_upload_positional_phi_encrypted_round_trip(db):
    """fields column encrypts on write and decrypts transparently on read."""
    upload = _make_upload(TENANT_A, filename="export.txt")
    db.add(upload)
    db.flush()

    # Single row with known DOB at position 11
    row_line = (
        "CLM001|P|025706|IFX|03/15/2026|06/12/2025|IC47103004|IC47103004"
        "|HISTORY|CLAIM|01/01/1980|01|1013998913|78206018701|16474215"
        "|1.60|28|1|0|4359.6|5.0|4364.6|4364.6|0.0|1427113760|0.0|0.0"
        "|||591.91|2167.34|0.0|0.0|2167.34|0.0|0.0|591.91|2"
        "|03/15/2026 23:24:25|14||||0||||||||PHXCOM30|"
    )
    content = row_line.encode()
    parse_upload(db, upload=upload, file_bytes=content)

    # Read back via ORM -- EncryptedJSON decrypts transparently
    stored = db.execute(
        select(ClaimUploadRawRow).where(
            ClaimUploadRawRow.upload_id == upload.id,
        )
    ).scalar_one()

    fields = stored.fields  # decrypted dict
    assert isinstance(fields, dict)
    # pos01 = claim id
    assert fields["1"] == "CLM001"
    # pos11 = DOB (PHI) -- round-trips correctly
    assert fields["11"] == "01/01/1980"
    # pos14 = NDC
    assert fields["14"] == "78206018701"


def test_parse_upload_positional_ciphertext_not_plaintext():
    """Raw DB bytes for fields column do NOT contain plaintext DOB or NDC.

    Encryption is verified by inspecting the raw bind-param bytes that
    EncryptedJSON produces at write time. We use the TypeDecorator's
    process_bind_param directly -- this is exactly what SQLAlchemy sends to
    the DB, so it faithfully represents what is stored at rest.

    No DB fixture needed: this tests the crypto layer directly, which is the
    authoritative source of what is stored in the LargeBinary column.
    """
    from shared.crypto.sqlalchemy_types import EncryptedJSON  # noqa: PLC0415

    row_line = (
        "CLM_PHI|P|025706|IFX|03/15/2026|06/12/2025|IC47103004|IC47103004"
        "|HISTORY|CLAIM|01/01/1980|01|1013998913|78206018701|16474215"
        "|1.60|28|1|0|100.0|5.0|105.0|105.0|0.0|9999999999|0.0|0.0"
        "|||50.0|100.0|0.0|0.0|100.0|0.0|0.0|50.0|1"
        "|03/15/2026 23:24:25|14||||0||||||||PHXCOM30|"
    )
    # Build the positional dict directly (same as parse_positional_bytes)
    fields = {str(i + 1): v for i, v in enumerate(row_line.split("|"))}

    # pos11 = DOB, pos14 = NDC -- must not appear in ciphertext
    assert fields["11"] == "01/01/1980"
    assert fields["14"] == "78206018701"

    # Encrypt via the type decorator (same path as ORM flush)
    enc_type = EncryptedJSON()
    raw_bytes = enc_type.process_bind_param(fields, dialect=None)

    assert raw_bytes is not None, "EncryptedJSON.process_bind_param returned None"
    assert isinstance(raw_bytes, bytes), "Expected bytes from process_bind_param"

    # Ciphertext must not contain plaintext PHI
    assert b"01/01/1980" not in raw_bytes, "DOB found in plaintext ciphertext -- NOT ENCRYPTED"
    assert b"78206018701" not in raw_bytes, "NDC found in plaintext ciphertext -- NOT ENCRYPTED"

    # Round-trip: decrypt must recover original dict
    recovered = enc_type.process_result_value(raw_bytes, dialect=None)
    assert recovered["11"] == "01/01/1980"
    assert recovered["14"] == "78206018701"


def test_parse_upload_positional_no_required_column_enforcement(db):
    """Positional capture mode accepts any content -- no _REQUIRED_COLUMNS check."""
    upload = _make_upload(TENANT_A, filename="partial.txt")
    db.add(upload)
    db.flush()

    # Only 5 fields -- would fail CSV validation; must succeed in capture mode
    content = b"A|B|C|D|E\nF|G|H\n"
    result = parse_upload(db, upload=upload, file_bytes=content)

    assert result.raw_rows_written == 2
    assert upload.status == UploadStatus.captured.value


def test_parse_upload_positional_decimal_stored_as_string(db):
    """Financial/decimal fields are stored as captured strings, not coerced."""
    upload = _make_upload(TENANT_A, filename="amounts.txt")
    db.add(upload)
    db.flush()

    # pos20 = 4359.6 (dollar amount -- NOT coerced to Decimal)
    content = _pipe_content(n_rows=1)
    parse_upload(db, upload=upload, file_bytes=content)

    row = db.execute(
        select(ClaimUploadRawRow).where(ClaimUploadRawRow.upload_id == upload.id)
    ).scalar_one()

    # fields["20"] must be a string, not Decimal or float
    assert isinstance(row.fields["20"], str)
    assert row.fields["20"] == "4359.6"


def test_parse_upload_cross_tenant_isolation(db):
    """Raw rows for Tenant A are not visible when querying as Tenant B."""
    upload_a = _make_upload(TENANT_A, filename="ta.txt")
    db.add(upload_a)
    db.flush()

    content = _pipe_content(n_rows=3)
    parse_upload(db, upload=upload_a, file_bytes=content)

    # Query with Tenant B filter -- must return zero rows
    rows_b = db.execute(
        select(ClaimUploadRawRow).where(
            ClaimUploadRawRow.tenant_id == TENANT_B,
        )
    ).scalars().all()

    assert len(rows_b) == 0


# ---------------------------------------------------------------------------
# CSV path unaffected by positional addition
# ---------------------------------------------------------------------------


def test_existing_csv_path_unaffected(db):
    """CSV-with-header files still route to the existing parse_csv_bytes path."""
    upload = _make_upload(TENANT_A, filename="claims.csv")
    upload.mime_type = "text/csv"
    db.add(upload)
    db.flush()

    csv_content = (
        b"ndc,npi,claim_id,date_of_service,quantity,days_supply,amount_billed,member_id\n"
        b"00093310305,1234567893,CLM001,2026-01-15,1.000,30,99.9900,MBR001\n"
    )
    result = parse_upload(db, upload=upload, file_bytes=csv_content)

    # CSV path writes ClaimRecord rows, not raw rows
    assert result.claims_written == 1
    # No raw rows created
    raw_count = db.execute(
        select(ClaimUploadRawRow).where(ClaimUploadRawRow.upload_id == upload.id)
    ).scalars().all()
    assert len(raw_count) == 0


def test_detect_format_txt_extension_with_pipe_content():
    """A .txt file with pipe content is detected as positional."""
    content = b"1|2|3|4|5\n6|7|8|9|10\n"
    assert detect_format(content) == "positional"
