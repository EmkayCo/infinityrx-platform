"""Tests for NPPES upsert service."""
from __future__ import annotations

import io

import pytest
from sqlalchemy import select

from src.models.tables import DataRefreshLog, Prescriber
from src.services.nppes_upsert import _BATCH_SIZE, run_nppes_import, upsert_batch
from src.services.nppes_parser import ParsedNpi

from tests.conftest import now_utc


def _make_parsed(npi: str, last_name: str = "DOE", first_name: str = "JANE") -> ParsedNpi:
    return ParsedNpi(
        npi=npi,
        entity_type="1",
        last_name=last_name,
        first_name=first_name,
        middle_name=None,
        prefix=None,
        suffix=None,
        credential="MD",
        display_name=f"{first_name} {last_name} MD",
        organization_name=None,
        authorized_official_name=None,
        authorized_official_title=None,
        primary_taxonomy_code="207Q00000X",
        taxonomy_codes=["207Q00000X"],
        gender="F",
        practice_address_line_1="100 MAIN ST",
        practice_address_line_2=None,
        practice_city="CHICAGO",
        practice_state="IL",
        practice_zip="60601",
        practice_phone="3125550100",
        practice_fax=None,
        mailing_address_line_1=None,
        mailing_address_line_2=None,
        mailing_city=None,
        mailing_state=None,
        mailing_zip=None,
        state_license_number=None,
        state_license_state=None,
        enumeration_date=None,
        last_update_date=None,
        deactivation_date=None,
        deactivation_reason=None,
        reactivation_date=None,
        status="active",
    )


# Valid Luhn NPIs for testing — high-range to avoid collisions with integration test seeds
NPI_1 = "1900000005"
NPI_2 = "1900000013"
NPI_3 = "1900000021"


def test_upsert_batch_adds_new_records(db_session):
    batch = [_make_parsed(NPI_1, "JONES", "ALICE"), _make_parsed(NPI_2, "SMITH", "BOB")]
    added, updated = upsert_batch(db_session, batch)
    assert added == 2
    assert updated == 0
    rows = db_session.execute(select(Prescriber).where(Prescriber.npi.in_([NPI_1, NPI_2]))).scalars().all()
    assert len(rows) == 2


def test_upsert_batch_updates_existing_records(db_session):
    # Seed one prescriber first
    p = Prescriber(
        npi=NPI_3,
        entity_type="1",
        last_name="OLD",
        first_name="NAME",
        display_name="OLD NAME MD",
        status="active",
        offers_telehealth=False,
        medicare_opt_out=False,
        taxonomy_codes=[],
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db_session.add(p)
    db_session.flush()

    parsed = _make_parsed(NPI_3, "NEWLAST", "NEWFIRST")
    added, updated = upsert_batch(db_session, [parsed])
    assert added == 0
    assert updated == 1
    row = db_session.execute(select(Prescriber).where(Prescriber.npi == NPI_3)).scalar_one()
    assert row.last_name == "NEWLAST"
    assert row.first_name == "NEWFIRST"


def test_upsert_batch_empty(db_session):
    added, updated = upsert_batch(db_session, [])
    assert added == 0
    assert updated == 0


_MINIMAL_HEADER = (
    "NPI,Entity Type Code,Provider Last Name (Legal Name),Provider First Name,"
    "Provider Middle Name,Provider Name Prefix Text,Provider Name Suffix Text,"
    "Provider Credential Text,Provider Other Organization Name,"
    "Provider Other Organization Name Type Code,"
    "Provider Other Last Name,Provider Other First Name,Provider Other Middle Name,"
    "Provider Other Name Prefix Text,Provider Other Name Suffix Text,"
    "Provider Other Credential Text,Provider Other Last Name Type Code,"
    "Provider First Line Business Mailing Address,"
    "Provider Second Line Business Mailing Address,"
    "Provider Business Mailing Address City Name,"
    "Provider Business Mailing Address State Name,"
    "Provider Business Mailing Address Postal Code,"
    "Provider Business Mailing Address Country Code (If outside U.S.),"
    "Provider Business Mailing Address Telephone Number,"
    "Provider Business Mailing Address Fax Number,"
    "Provider First Line Business Practice Location Address,"
    "Provider Second Line Business Practice Location Address,"
    "Provider Business Practice Location Address City Name,"
    "Provider Business Practice Location Address State Name,"
    "Provider Business Practice Location Address Postal Code,"
    "Provider Business Practice Location Address Country Code (If outside U.S.),"
    "Provider Business Practice Location Address Telephone Number,"
    "Provider Business Practice Location Address Fax Number,"
    "Provider Enumeration Date,Last Update Date,NPI Deactivation Reason Code,"
    "NPI Deactivation Date,NPI Reactivation Date,Provider Gender Code,"
    "Authorized Official Last Name,Authorized Official First Name,"
    "Authorized Official Middle Name,Authorized Official Title or Position,"
    "Authorized Official Telephone Number,Healthcare Provider Taxonomy Code_1,"
    "Provider License Number_1,Provider License Number State Code_1,"
    "Healthcare Provider Primary Taxonomy Switch_1"
)


def _make_csv_row(npi: str, entity_type: str = "1", last_name: str = "DOE", first_name: str = "JANE") -> str:
    # Build a minimal CSV row with enough columns (pad to avoid IndexError)
    # The parser uses specific column indices; pad with commas
    fields = [""] * 330
    fields[0] = npi          # NPI
    fields[1] = entity_type  # Entity Type Code
    fields[2] = last_name    # Last Name
    fields[3] = first_name   # First Name
    fields[44] = "207Q00000X"  # Taxonomy Code_1
    fields[47] = "Y"           # Primary Taxonomy Switch_1
    return ",".join(fields)


def _make_csv(rows: list[tuple]) -> io.StringIO:
    lines = [_MINIMAL_HEADER]
    for row in rows:
        lines.append(_make_csv_row(*row))
    return io.StringIO("\n".join(lines))


NPI_VALID_1 = "1900000039"
NPI_VALID_2 = "1900000047"


def test_run_nppes_import_completes_successfully(db_session):
    csv_data = _make_csv([(NPI_VALID_1, "1", "ALPHA", "BETA"), (NPI_VALID_2, "1", "GAMMA", "DELTA")])
    log = run_nppes_import(db_session, csv_data)
    assert log.status == "completed"
    assert log.records_processed == 2
    assert log.records_added == 2
    assert log.records_updated == 0
    assert log.completed_at is not None


def test_run_nppes_import_skips_invalid_npi(db_session):
    csv_data = _make_csv([("0000000000", "1", "INVALID", "NPI")])
    log = run_nppes_import(db_session, csv_data)
    assert log.status == "completed"
    assert log.records_processed == 0


def test_run_nppes_import_creates_refresh_log_on_failure(db_session):
    # Pass an object that raises on iteration
    class BrokenSource:
        def read(self):
            raise RuntimeError("disk error")

    # The parser uses csv.DictReader on the source; pass a broken iterable
    class BrokenIterable:
        def __iter__(self):
            raise RuntimeError("disk error")
        def read(self):
            return ""

    with pytest.raises(RuntimeError):
        run_nppes_import(db_session, BrokenIterable())

    log = db_session.execute(
        select(DataRefreshLog).order_by(DataRefreshLog.created_at.desc())
    ).scalars().first()
    assert log is not None
    assert log.status == "failed"
    assert "disk error" in log.error_message


NPI_VALID_BATCH = [
    "1000000061",
    "1000000079",
    "1000000087",
    "1000000095",
    "1000000103",
]


def _generate_valid_npi() -> list[str]:
    """Return pre-computed valid NPIs for batch size test."""
    # We need _BATCH_SIZE + 1 valid NPIs — use sequential ones
    # NPI Luhn: prepend 80840, run Luhn, check digit
    valid = []
    candidate = 1000000000
    while len(valid) < _BATCH_SIZE + 2:
        npi_str = str(candidate).zfill(10)
        prefix = "80840" + npi_str
        digits = [int(d) for d in prefix]
        total = 0
        for i, d in enumerate(reversed(digits)):
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        if total % 10 == 0:
            valid.append(npi_str)
        candidate += 1
    return valid


def test_run_nppes_import_processes_multiple_batches(db_session):
    valid_npis = _generate_valid_npi()
    rows = [(npi, "1", f"LAST{i}", f"FIRST{i}") for i, npi in enumerate(valid_npis)]
    csv_data = _make_csv(rows)
    log = run_nppes_import(db_session, csv_data)
    assert log.status == "completed"
    assert log.records_processed == len(valid_npis)
