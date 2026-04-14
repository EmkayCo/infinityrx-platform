"""Tests for the NCPDP DataQ v3.1 ingestion pipeline.

Covers:
- mas.txt: all fields extracted correctly (calibration record)
- Copyright header skipping (first record starting with '9999999')
- Calibration record NCPDP 0100052 verified against known values
- Upsert idempotency (load twice, count stays the same)
- Each child table: semantics verified
- Batch size = 1000 rows
- Date parsing (MMDDYYYY, '00000000' → None)
- Service code flag parsing
- SVC code parsing edge cases

SQLAlchemy isolation: SAVEPOINT-based per LESSON-001.
_UUIDString TypeDecorator per LESSON-007.

LESSON-011: Global reference data — no TenantScopedMixin.
LESSON-005: Log extra keys prefixed with 'ingest_'.
"""

from __future__ import annotations

import os
import sys
import uuid
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import JSON, String, create_engine, event, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import TypeDecorator

# ---------------------------------------------------------------------------
# Environment + path setup
# ---------------------------------------------------------------------------

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost/")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")
os.environ.setdefault(
    "ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM="
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PHARM_ROOT = _REPO_ROOT / "modules" / "pharmacy-directory"

for _p in (str(_REPO_ROOT), str(_PHARM_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# SQLite compatibility — LESSON-007
# ---------------------------------------------------------------------------

from shared.data_ingestion.models import IngestionRun, IngestionSchedule  # noqa: E402
from shared.db.base import Base  # noqa: E402


class _UUIDString(TypeDecorator):
    """SQLite-compatible UUID stored as VARCHAR(36) (LESSON-007)."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        return str(value) if value is not None else None

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:
        return uuid.UUID(str(value)) if value is not None else None


def _patch_for_sqlite(tables: list[Any]) -> None:
    for table in tables:
        if getattr(table, "_sqlite_patched", False):
            continue
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
            elif isinstance(col.type, PG_UUID):
                col.type = _UUIDString()
            if col.server_default is not None and "gen_random_uuid" in str(
                col.server_default
            ):
                col.server_default = None
        table._sqlite_patched = True


# Import all NCPDP ORM models so their metadata is registered
from src.models.ncpdp_tables import (  # noqa: E402
    NCPDPPharmacy,
    NCPDPPharmacyAdditionalInfo,
    NCPDPPharmacyCoordinate,
    NCPDPPharmacyErxCapability,
    NCPDPPharmacyFwaAction,
    NCPDPPharmacyMedicaid,
    NCPDPPharmacyPatientCare,
    NCPDPPharmacyProgram,
    NCPDPPharmacyRecertification,
    NCPDPPharmacyRemittance,
    NCPDPPharmacyService,
    NCPDPPharmacyStateLicense,
    NCPDPPharmacyTaxonomy,
)
from src.models.base import PharmacyBase

# Patch all tables for SQLite
_NCPDP_TABLES = [
    NCPDPPharmacy.__table__,
    NCPDPPharmacyTaxonomy.__table__,
    NCPDPPharmacyStateLicense.__table__,
    NCPDPPharmacyService.__table__,
    NCPDPPharmacyRemittance.__table__,
    NCPDPPharmacyErxCapability.__table__,
    NCPDPPharmacyMedicaid.__table__,
    NCPDPPharmacyFwaAction.__table__,
    NCPDPPharmacyCoordinate.__table__,
    NCPDPPharmacyAdditionalInfo.__table__,
    NCPDPPharmacyPatientCare.__table__,
    NCPDPPharmacyProgram.__table__,
    NCPDPPharmacyRecertification.__table__,
]
_patch_for_sqlite(
    [IngestionRun.__table__, IngestionSchedule.__table__] + _NCPDP_TABLES
)

# Import parsers under test
from shared.data_ingestion.sources.ncpdp_dataq import (  # noqa: E402
    _parse_file,
    _parse_mas_af_record,
    _parse_mas_coo_record,
    _parse_mas_erx_record,
    _parse_mas_fwa_record,
    _parse_mas_md_record,
    _parse_mas_pc_record,
    _parse_mas_pr_record,
    _parse_mas_rec_record,
    _parse_mas_record,
    _parse_mas_rr_record,
    _parse_mas_stl_record,
    _parse_mas_svc_record,
    _parse_mas_tx_record,
)
from shared.data_ingestion.date_parsers import parse_mmddyyyy  # noqa: E402
from src.services.ncpdp_ingestion import NCPDPIngestionService  # noqa: E402

# Sample data directory
_SAMPLE_DIR = Path(__file__).parent / "sample_data" / "ncpdp"


# ---------------------------------------------------------------------------
# SQLite engine + SAVEPOINT session fixtures  (LESSON-001 + LESSON-007)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _engine():
    raw_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(raw_engine, "connect")
    def _set_pragma(dbapi_conn: Any, _: Any) -> None:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.close()

    # Map pharmacy_dir schema → None (SQLite has no named schemas)
    engine = raw_engine.execution_options(
        schema_translate_map={"pharmacy_dir": None, "shared": None}
    )

    # Create all tables
    PharmacyBase.metadata.create_all(engine, tables=_NCPDP_TABLES)
    Base.metadata.create_all(
        engine, tables=[IngestionRun.__table__, IngestionSchedule.__table__]
    )

    yield engine

    PharmacyBase.metadata.drop_all(engine, tables=_NCPDP_TABLES)
    Base.metadata.drop_all(
        engine, tables=[IngestionRun.__table__, IngestionSchedule.__table__]
    )
    raw_engine.dispose()


@pytest.fixture
def db_session(_engine) -> Iterator[Session]:
    """SAVEPOINT-based isolated session (LESSON-001)."""
    connection = _engine.connect()
    outer = connection.begin()
    nested = connection.begin_nested()
    factory = sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    session = factory()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess: Session, transaction: Any) -> None:
        nonlocal nested
        if transaction.nested and not transaction._parent.nested:
            nested = connection.begin_nested()

    yield session

    session.close()
    outer.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _read_sample_file(filename: str) -> list[str]:
    """Read all non-header records from a sample file."""
    path = _SAMPLE_DIR / filename
    records = []
    with open(path, "rb") as f:
        first = True
        for line in f:
            rec = line.decode("latin-1").rstrip("\r\n")
            if first:
                first = False
                if rec.startswith("9999999"):
                    continue
            if rec.strip() and not rec.startswith("9999999"):
                records.append(rec)
    return records


# ---------------------------------------------------------------------------
# Date parser tests
# ---------------------------------------------------------------------------


def test_parse_mmddyyyy_valid() -> None:
    """MMDDYYYY parses correctly."""
    assert parse_mmddyyyy("08011988") == date(1988, 8, 1)
    assert parse_mmddyyyy("12312024") == date(2024, 12, 31)
    assert parse_mmddyyyy("01012000") == date(2000, 1, 1)


def test_parse_mmddyyyy_zero_returns_none() -> None:
    """'00000000' (no date) returns None."""
    assert parse_mmddyyyy("00000000") is None


def test_parse_mmddyyyy_blank_returns_none() -> None:
    """Empty / whitespace returns None."""
    assert parse_mmddyyyy("") is None
    assert parse_mmddyyyy("   ") is None
    assert parse_mmddyyyy(None) is None  # type: ignore[arg-type]


def test_parse_mmddyyyy_invalid_returns_none() -> None:
    """Invalid dates (month 13, day 32) return None gracefully."""
    assert parse_mmddyyyy("13012024") is None
    assert parse_mmddyyyy("01322024") is None
    assert parse_mmddyyyy("ABCD1234") is None


# ---------------------------------------------------------------------------
# Copyright header skip test
# ---------------------------------------------------------------------------


def test_parse_skips_copyright_header() -> None:
    """First record starting with '9999999' must be skipped."""
    records = _read_sample_file("mas.txt")
    # If header was skipped, no record should start with 9999999
    assert all(not r.startswith("9999999") for r in records), (
        "Copyright header was not skipped"
    )
    # Should have 5 data records
    assert len(records) == 5


# ---------------------------------------------------------------------------
# mas.txt — all fields extracted
# ---------------------------------------------------------------------------


def test_parse_mas_extracts_all_fields() -> None:
    """Parse the synthetic mas.txt and verify all key fields are populated."""
    records = _read_sample_file("mas.txt")
    assert len(records) == 5

    # Parse first record (NCPDP 0100052 = Smithermans Pharmacy)
    row = _parse_mas_record(records[0])

    assert row["ncpdp_provider_id"] == "0100052"
    assert row["legal_name"] == "MEDICINE FOR LESS INC"
    assert row["dba_name"] == "SMITHERMANS PHARMACY"
    assert row["address_line_1"] == "703 MAIN ST"
    assert row["city"] == "MONTEVALLO"
    assert row["state"] == "AL"
    assert row["zip5"] == "35115"
    assert row["phone"] == "2056652575"
    assert row["fax"] == "2056650940"
    assert row["npi"] == "1457492183"
    assert row["dea_number"] == "AS0479611"
    assert row["federal_tax_id"] == "630984272"

    # Verify all expected keys exist in row dict
    expected_keys = {
        "ncpdp_provider_id", "legal_name", "dba_name", "store_number",
        "nabp_number", "pharmacy_type_code", "npi", "dea_number",
        "dea_expiration_date", "federal_tax_id",
        "address_line_1", "address_line_2", "city", "state", "zip5",
        "zip_plus4", "cross_street", "phone", "phone_extension", "fax", "email",
        "mailing_address_line_1", "mailing_address_line_2", "mailing_city",
        "mailing_state", "mailing_zip5", "mailing_zip_plus4",
        "auth_official_last_name", "auth_official_first_name",
        "auth_official_title", "auth_official_phone", "auth_official_email",
        "store_open_date", "store_close_date", "deactivation_date",
        "raw_field_127", "raw_field_483", "raw_field_489", "raw_field_834",
        "raw_field_839", "raw_field_843", "raw_field_876", "raw_field_896",
        "raw_field_908", "raw_field_929",
    }
    assert expected_keys.issubset(set(row.keys())), (
        f"Missing keys: {expected_keys - set(row.keys())}"
    )


def test_parse_mas_store_open_date() -> None:
    """Store open date MMDDYYYY parses to date object."""
    records = _read_sample_file("mas.txt")
    row = _parse_mas_record(records[0])
    # 0100052 store open date = 08011988 = August 1, 1988
    assert row["store_open_date"] == date(1988, 8, 1)


def test_parse_mas_deactivation_date_zero() -> None:
    """'00000000' deactivation date returns None (active pharmacy)."""
    records = _read_sample_file("mas.txt")
    row = _parse_mas_record(records[0])
    assert row["deactivation_date"] is None


def test_parse_mas_empty_fields_are_none() -> None:
    """Empty strings after strip → None."""
    records = _read_sample_file("mas.txt")
    row = _parse_mas_record(records[0])
    # address_line_2 is typically blank for this record
    assert row["address_line_2"] is None


# ---------------------------------------------------------------------------
# Calibration record test — NCPDP 0100052
# ---------------------------------------------------------------------------


def test_parse_calibration_record_NCPDP_0100052() -> None:
    """Calibration record NCPDP 0100052 must match all known values exactly.

    Calibration: MEDICINE FOR LESS INC, DBA SMITHERMANS PHARMACY,
    703 MAIN ST, MONTEVALLO, AL 35115, phone 2056652575, fax 2056650940.
    """
    path = _SAMPLE_DIR / "mas_calibration.txt"
    records = []
    with open(path, "rb") as f:
        first = True
        for line in f:
            rec = line.decode("latin-1").rstrip("\r\n")
            if first:
                first = False
                if rec.startswith("9999999"):
                    continue
            if rec.strip():
                records.append(rec)

    assert len(records) == 1, f"Expected 1 calibration record, got {len(records)}"

    row = _parse_mas_record(records[0])

    # Hard-coded calibration assertions
    assert row["ncpdp_provider_id"] == "0100052"
    assert row["legal_name"] == "MEDICINE FOR LESS INC"
    assert row["dba_name"] == "SMITHERMANS PHARMACY"
    assert row["address_line_1"] == "703 MAIN ST"
    assert row["city"] == "MONTEVALLO"
    assert row["state"] == "AL"
    assert row["zip5"] == "35115"
    assert row["phone"] == "2056652575"
    assert row["fax"] == "2056650940"
    assert row["email"] == "SMITHERMANSPHARM@BELLSOUTH.NET"
    assert row["npi"] == "1457492183"
    assert row["dea_number"] == "AS0479611"
    assert row["federal_tax_id"] == "630984272"


# ---------------------------------------------------------------------------
# Child table parsing tests
# ---------------------------------------------------------------------------


def test_parse_mas_tx_taxonomy() -> None:
    """mas_tx.txt: taxonomy_code extracted, primary_indicator set."""
    records = _read_sample_file("mas_tx.txt")
    assert len(records) == 5

    row = _parse_mas_tx_record(records[0])
    assert row["ncpdp_provider_id"] == "0100052"
    assert row["taxonomy_code"] is not None
    assert len(row["taxonomy_code"]) <= 10
    # primary_indicator should be a single char or None
    if row["primary_indicator"] is not None:
        assert len(row["primary_indicator"]) == 1


def test_parse_mas_stl_state_license() -> None:
    """mas_stl.txt: state abbreviation and license number extracted."""
    records = _read_sample_file("mas_stl.txt")
    assert len(records) == 5

    row = _parse_mas_stl_record(records[0])
    assert row["ncpdp_provider_id"] == "0100052"
    assert row["state"] == "AL"
    assert row["license_number"] is not None
    assert "108930" in row["license_number"]
    # expiration date = 12/31/2024
    assert row["expiration_date"] == date(2024, 12, 31)


def test_parse_mas_svc_service_flags() -> None:
    """mas_svc.txt: Y/N flags parsed into boolean columns."""
    records = _read_sample_file("mas_svc.txt")
    assert len(records) == 5

    row = _parse_mas_svc_record(records[0])
    assert row["ncpdp_provider_id"] == "0100052"
    # services_raw should be set
    assert row["services_raw"] is not None
    # svc_retail (code 02) for 0100052 = Y
    assert row["svc_retail"] is True
    # svc_long_term_care (code 05) for 0100052 = Y
    assert row["svc_long_term_care"] is True
    # Each flag must be bool or None
    bool_cols = [
        "svc_retail", "svc_mail_order", "svc_specialty", "svc_long_term_care",
        "svc_home_infusion", "svc_compounding",
    ]
    for col in bool_cols:
        assert row[col] is None or isinstance(row[col], bool), (
            f"{col} must be bool or None, got {type(row[col])}"
        )


def test_parse_mas_rr_remittance() -> None:
    """mas_rr.txt: routing number, electronic flag, effective date."""
    records = _read_sample_file("mas_rr.txt")
    assert len(records) == 5

    row = _parse_mas_rr_record(records[0])
    assert row["ncpdp_provider_id"] == "0100052"
    assert row["aba_routing_number"] is not None
    # electronic_payment_flag = Y or N
    if row["electronic_payment_flag"] is not None:
        assert row["electronic_payment_flag"] in ("Y", "N")
    # effective_date should be a date object
    assert isinstance(row["effective_date"], date)


def test_parse_mas_erx_erx_capability() -> None:
    """mas_erx.txt: software vendor code, capability flag, transaction types."""
    records = _read_sample_file("mas_erx.txt")
    assert len(records) == 5

    row = _parse_mas_erx_record(records[0])
    assert row["ncpdp_provider_id"] == "0100052"
    assert row["software_vendor_code"] == "SS"
    assert row["erx_capable_flag"] == "X"
    assert row["transaction_types"] is not None
    assert "NEW" in row["transaction_types"]


def test_parse_mas_md_medicaid() -> None:
    """mas_md.txt: state and medicaid provider ID extracted."""
    records = _read_sample_file("mas_md.txt")
    assert len(records) == 5

    row = _parse_mas_md_record(records[0])
    assert row["ncpdp_provider_id"] == "0100052"
    assert row["state"] == "AL"
    assert row["medicaid_provider_id"] is not None


def test_parse_mas_fwa_fwa_action() -> None:
    """mas_fwa.txt: review year, flags, effective date."""
    records = _read_sample_file("mas_fwa.txt")
    assert len(records) == 5

    row = _parse_mas_fwa_record(records[0])
    assert row["ncpdp_provider_id"] == "0100052"
    assert row["review_year"] is not None
    assert 2000 <= row["review_year"] <= 2030  # sanity check
    assert row["fwa_flag_1"] in ("Y", "N", None)
    assert row["fwa_flag_2"] in ("Y", "N", None)


def test_parse_mas_coo_coordinates() -> None:
    """mas_coo.txt: location_id and geocoding dates extracted."""
    records = _read_sample_file("mas_coo.txt")
    assert len(records) == 5

    row = _parse_mas_coo_record(records[0])
    assert row["ncpdp_provider_id"] is not None
    assert row["location_id"] is not None
    # Geocoding dates should be date objects
    assert isinstance(row["geocode_start_date"], date)
    assert isinstance(row["geocode_end_date"], date)
    # lat/lon must be None in v3.1 dataset
    assert row["latitude"] is None
    assert row["longitude"] is None


def test_parse_mas_af_additional_info() -> None:
    """mas_af.txt: chain_entity_id (5-char) and raw_content."""
    records = _read_sample_file("mas_af.txt")
    assert len(records) == 5

    row = _parse_mas_af_record(records[0])
    assert row["chain_entity_id"] is not None
    assert len(row["chain_entity_id"]) <= 5
    assert row["raw_content"] is not None


def test_parse_mas_pc_patient_care() -> None:
    """mas_pc.txt: chain_entity_id (6-char) and raw_content."""
    records = _read_sample_file("mas_pc.txt")
    assert len(records) == 5

    row = _parse_mas_pc_record(records[0])
    assert row["chain_entity_id"] is not None
    assert len(row["chain_entity_id"]) <= 6
    assert row["raw_content"] is not None


def test_parse_mas_pr_programs() -> None:
    """mas_pr.txt: chain_entity_id and raw_content."""
    records = _read_sample_file("mas_pr.txt")
    assert len(records) == 5

    row = _parse_mas_pr_record(records[0])
    assert row["chain_entity_id"] is not None
    assert row["raw_content"] is not None


def test_parse_mas_rec_recertification() -> None:
    """mas_rec.txt: chain_entity_id and raw_content."""
    records = _read_sample_file("mas_rec.txt")
    assert len(records) == 5

    row = _parse_mas_rec_record(records[0])
    assert row["chain_entity_id"] is not None
    assert row["raw_content"] is not None


# ---------------------------------------------------------------------------
# Upsert idempotency test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_idempotent(db_session: Session) -> None:
    """Loading the same records twice must not duplicate rows."""
    service = NCPDPIngestionService(db_session=db_session)

    # Prepare one pharmacy row
    ncpdp_id = "9990001"
    row = {
        "ncpdp_provider_id": ncpdp_id,
        "legal_name": "TEST PHARMACY INC",
        "dba_name": "TEST RX",
        "city": "TESTVILLE",
        "state": "TX",
        "zip5": "75001",
    }

    def _make_records() -> Iterator[dict[str, Any]]:
        yield {"table": "ncpdp_pharmacies", "row": row}

    # Load once
    await service.load_records(_make_records(), source_name="ncpdp_test")
    db_session.flush()

    count_after_first = db_session.execute(
        select(NCPDPPharmacy).where(NCPDPPharmacy.ncpdp_provider_id == ncpdp_id)
    ).scalars().all()
    assert len(count_after_first) == 1

    # Load again (upsert — no duplicate)
    await service.load_records(_make_records(), source_name="ncpdp_test")
    db_session.flush()

    count_after_second = db_session.execute(
        select(NCPDPPharmacy).where(NCPDPPharmacy.ncpdp_provider_id == ncpdp_id)
    ).scalars().all()
    assert len(count_after_second) == 1, (
        f"Upsert should not create duplicate: got {len(count_after_second)} rows"
    )


# ---------------------------------------------------------------------------
# Child table delete-then-insert semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_child_table_delete_then_insert(db_session: Session) -> None:
    """Child tables (taxonomies) use delete-then-insert so stale rows are purged."""
    service = NCPDPIngestionService(db_session=db_session)
    ncpdp_id = "9990002"

    # Load 2 taxonomy rows
    def _make_tx(codes: list[str]) -> Iterator[dict[str, Any]]:
        for code in codes:
            yield {
                "table": "ncpdp_pharmacy_taxonomies",
                "row": {"ncpdp_provider_id": ncpdp_id, "taxonomy_code": code},
            }

    await service.load_records(_make_tx(["3336C0003X", "333600000X"]), source_name="ncpdp_test")
    db_session.flush()

    count_first = db_session.execute(
        select(NCPDPPharmacyTaxonomy).where(
            NCPDPPharmacyTaxonomy.ncpdp_provider_id == ncpdp_id
        )
    ).scalars().all()
    assert len(count_first) == 2

    # Second load with only 1 code — stale row should be purged
    await service.load_records(_make_tx(["3336C0003X"]), source_name="ncpdp_test")
    db_session.flush()

    count_second = db_session.execute(
        select(NCPDPPharmacyTaxonomy).where(
            NCPDPPharmacyTaxonomy.ncpdp_provider_id == ncpdp_id
        )
    ).scalars().all()
    assert len(count_second) == 1, (
        f"Delete-then-insert should purge stale rows; got {len(count_second)}"
    )


# ---------------------------------------------------------------------------
# Batch size test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_size_1000_rows(db_session: Session) -> None:
    """1000-row batch loads without error and all rows are present."""
    service = NCPDPIngestionService(db_session=db_session)

    def _make_1000_rows() -> Iterator[dict[str, Any]]:
        for i in range(1000):
            ncpdp_id = f"8{i:06d}"
            yield {
                "table": "ncpdp_pharmacies",
                "row": {
                    "ncpdp_provider_id": ncpdp_id,
                    "legal_name": f"PHARMACY {i}",
                    "state": "TX",
                    "zip5": "75001",
                },
            }

    result = await service.load_records(_make_1000_rows(), source_name="ncpdp_test")
    db_session.flush()

    assert result.records_processed == 1000
    assert result.records_errored == 0

    # Spot check first and last row
    first_row = db_session.execute(
        select(NCPDPPharmacy).where(NCPDPPharmacy.ncpdp_provider_id == "8000000")
    ).scalar_one_or_none()
    assert first_row is not None
    assert first_row.legal_name == "PHARMACY 0"

    last_row = db_session.execute(
        select(NCPDPPharmacy).where(NCPDPPharmacy.ncpdp_provider_id == "8000999")
    ).scalar_one_or_none()
    assert last_row is not None


# ---------------------------------------------------------------------------
# Service code parsing edge cases
# ---------------------------------------------------------------------------


def test_parse_svc_all_flags_false() -> None:
    """A record with all N flags has all booleans set to False."""
    # Construct a synthetic record: ncpdp_id + all-N service codes
    ncpdp_id = "0000001"
    # Build services string with all codes = N
    codes = ["02", "03", "04", "05", "06", "07", "10", "11", "12",
             "13", "14", "16", "18", "19", "23", "26", "28", "29",
             "30", "32", "33", "35", "36", "37", "40"]
    services = "".join(f"N{code}" for code in codes)
    # Pad to 143 chars total
    rec = ncpdp_id + services.ljust(143)

    row = _parse_mas_svc_record(rec)
    assert row["svc_retail"] is False
    assert row["svc_specialty"] is False
    assert row["svc_340b"] is False


def test_parse_svc_partial_record() -> None:
    """A record with only a few service codes still parses other flags as None."""
    ncpdp_id = "0000002"
    services = "Y02N03"  # only 2 codes
    rec = ncpdp_id + services.ljust(143)

    row = _parse_mas_svc_record(rec)
    assert row["svc_retail"] is True
    assert row["svc_mail_order"] is False
    assert row["svc_specialty"] is None  # not present in record
