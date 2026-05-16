"""Tests for modules/core-platform/scripts/aggregate_exclusion_list.py.

Coverage:
  Unit:
    - OIG row → ExclusionListEntry mapping (_normalize_oig)
    - SAM row → ExclusionListEntry mapping (_normalize_sam)
    - NPI vs name-key lookup path in _upsert
    - _normalize_oig: npi sanitization (bad length, non-digit)
    - _normalize_sam: last/first name split on comma vs no-comma
    - _normalize_sam: state_province truncation (len != 2 → None)

  Integration:
    - full aggregation with fixture OIG + SAM data → correct row count
    - idempotent rerun: inserted=0, updated=N on second call
    - delisting: NPI removed from source table → reinstate_date set
    - empty sources: aggregation with 0 source rows runs without error
    - SAM-only run: OIG empty, SAM has rows
    - OIG-only run: SAM empty, OIG has rows

Fixture strategy:
  The aggregator uses two ORM bases:
    - shared.db.base.Base  (OigLeieExclusion, SamExclusion)
    - src._shim.db.Base    (ExclusionListEntry)
  Both are bound to the same in-memory SQLite engine in `agg_session`.

  IMPORTANT: OigLeieExclusion and SamExclusion have schema="shared" in
  their __table_args__, which SQLite does not support. To avoid touching
  the global metadata, source rows are inserted via raw SQL rather than
  through the ORM. Unit tests that call _normalize_oig/_normalize_sam
  use types.SimpleNamespace objects rather than ORM instances to avoid
  SQLAlchemy instrumentation errors.

LESSON-001: SAVEPOINT-based isolation not needed here because
  run_aggregation() does NOT commit — caller commits. The agg_session
  fixture uses a plain session; SAVEPOINT complexity is not needed.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Wire sys.path so we can import both src.* and shared.* from this test file.
_MODULE_ROOT = Path(__file__).resolve().parents[3]
_REPO_ROOT = _MODULE_ROOT.parent.parent
for _p in (_REPO_ROOT, _MODULE_ROOT):
    sp = str(_p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import types  # noqa: E402

from src.models import ExclusionListEntry  # noqa: E402
from src._shim import db as db_shim  # noqa: E402

from scripts.aggregate_exclusion_list import (  # noqa: E402
    _normalize_oig,
    _normalize_sam,
    run_aggregation,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def agg_engine(tmp_path):
    """SQLite engine with all tables needed for aggregation tests.

    Creates source tables (OIG/SAM) and the target table (ExclusionListEntry)
    all on the same SQLite engine so run_aggregation can work in a single session.

    We create the source tables via raw DDL rather than via SharedBase.metadata
    to avoid mutating the global schema= attributes (which are 'shared' for
    Postgres but must be absent for SQLite).
    """
    db_path = tmp_path / "agg_test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    # Create source tables via raw DDL — keeps SharedBase.metadata schema=None
    # mutation out of the global state.
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS oig_leie_exclusions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lastname TEXT,
                firstname TEXT,
                midname TEXT,
                busname TEXT,
                general TEXT,
                specialty TEXT,
                upin TEXT,
                npi TEXT,
                dob TEXT,
                address TEXT,
                city TEXT,
                state TEXT,
                zip TEXT,
                excltype TEXT,
                excldate TEXT,
                reindate TEXT,
                waiverdate TEXT,
                waiverstate TEXT,
                raw_payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sam_exclusions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                classification_type TEXT,
                name TEXT,
                address_line_1 TEXT,
                address_line_2 TEXT,
                city TEXT,
                state_province TEXT,
                zip_postal_code TEXT,
                country_code TEXT,
                duns_number TEXT,
                uei_sam TEXT,
                cage_code TEXT,
                npi TEXT,
                exclusion_type TEXT,
                exclusion_program TEXT,
                agency TEXT,
                active_date TEXT,
                termination_date TEXT,
                ct_code TEXT,
                additional_comments TEXT,
                affiliations TEXT,
                raw_payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
    # Create target table via shim (ExclusionListEntry lives in shim Base)
    db_shim.configure_engine(f"sqlite:///{db_path}")
    db_shim.create_all()
    yield engine
    try:
        db_shim.drop_all()
    except Exception:
        pass
    engine.dispose()


@pytest.fixture()
def agg_session(agg_engine):
    """Session bound to the aggregation test engine."""
    s = Session(agg_engine)
    try:
        yield s
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Helper factories for synthetic test data
#
# Unit-test factories: construct in-memory ORM objects (NOT persisted).
# Integration-test helpers: insert via raw SQL (bypasses schema= attribute).
#
# NPI convention: use clearly fake 10-digit NPIs (no Luhn check for reference data).
# Names use "TEST-" prefix to make fixture origin unambiguous.
# ---------------------------------------------------------------------------

def _oig_obj(
    *,
    npi: str | None = None,
    lastname: str = "TEST-SMITH",
    firstname: str | None = "TEST-JOHN",
    busname: str | None = None,
    state: str | None = "NY",
    excltype: str | None = "1128a1",
    excldate: date | None = None,
    reindate: date | None = None,
) -> object:
    """Create an in-memory OIG row as SimpleNamespace (unit tests only — not persisted)."""
    return types.SimpleNamespace(
        id=None,
        npi=npi,
        lastname=lastname,
        firstname=firstname,
        busname=busname,
        state=state,
        excltype=excltype,
        excldate=excldate or date(2020, 1, 1),
        reindate=reindate,
        midname=None,
        general=None,
        specialty=None,
        upin=None,
        dob=None,
        address=None,
        city=None,
        zip=None,
        waiverdate=None,
        waiverstate=None,
        raw_payload=None,
    )


def _sam_obj(
    *,
    npi: str | None = None,
    name: str = "TEST-SAM ENTITY",
    classification_type: str = "Firm",
    exclusion_type: str | None = "Ineligible (Proceedings Completed)",
    active_date: date | None = None,
    termination_date: date | None = None,
    state_province: str | None = "TX",
) -> object:
    """Create an in-memory SAM row as SimpleNamespace (unit tests only — not persisted)."""
    return types.SimpleNamespace(
        id=None,
        npi=npi,
        name=name,
        classification_type=classification_type,
        exclusion_type=exclusion_type,
        active_date=active_date or date(2021, 6, 15),
        termination_date=termination_date,
        state_province=state_province,
        address_line_1=None,
        address_line_2=None,
        city=None,
        zip_postal_code=None,
        country_code=None,
        duns_number=None,
        uei_sam=None,
        cage_code=None,
        exclusion_program=None,
        agency=None,
        ct_code=None,
        additional_comments=None,
        affiliations=None,
        raw_payload=None,
    )


def _insert_oig(session: Session, *, npi=None, lastname="TEST-SMITH",
                firstname="TEST-JOHN", busname=None, state="NY",
                excltype="1128a1", excldate=None, reindate=None) -> int:
    """Insert an OIG row via raw SQL. Returns the new rowid."""
    result = session.execute(text("""
        INSERT INTO oig_leie_exclusions
            (npi, lastname, firstname, busname, state, excltype, excldate, reindate)
        VALUES
            (:npi, :lastname, :firstname, :busname, :state, :excltype, :excldate, :reindate)
    """), {
        "npi": npi,
        "lastname": lastname,
        "firstname": firstname,
        "busname": busname,
        "state": state,
        "excltype": excltype,
        "excldate": str(excldate or date(2020, 1, 1)),
        "reindate": str(reindate) if reindate else None,
    })
    return result.lastrowid


def _insert_sam(session: Session, *, npi=None, name="TEST-SAM ENTITY",
                classification_type="Firm",
                exclusion_type="Ineligible (Proceedings Completed)",
                active_date=None, termination_date=None,
                state_province="TX") -> int:
    """Insert a SAM row via raw SQL. Returns the new rowid."""
    result = session.execute(text("""
        INSERT INTO sam_exclusions
            (npi, name, classification_type, exclusion_type, active_date,
             termination_date, state_province)
        VALUES
            (:npi, :name, :classification_type, :exclusion_type, :active_date,
             :termination_date, :state_province)
    """), {
        "npi": npi,
        "name": name,
        "classification_type": classification_type,
        "exclusion_type": exclusion_type,
        "active_date": str(active_date or date(2021, 6, 15)),
        "termination_date": str(termination_date) if termination_date else None,
        "state_province": state_province,
    })
    return result.lastrowid


def _delete_oig_by_id(session: Session, rowid: int) -> None:
    session.execute(text("DELETE FROM oig_leie_exclusions WHERE id = :id"), {"id": rowid})


# ---------------------------------------------------------------------------
# Unit: _normalize_oig
# ---------------------------------------------------------------------------

def test_normalize_oig_individual_with_npi():
    row = _oig_obj(npi="1234567890", lastname="TEST-DOE", firstname="TEST-JANE")
    data = _normalize_oig(row)
    assert data["source"] == "OIG"
    assert data["entity_type"] == "individual"
    assert data["npi"] == "1234567890"
    assert data["last_name"] == "TEST-DOE"
    assert data["first_name"] == "TEST-JANE"
    assert data["organization_name"] is None


def test_normalize_oig_organization_busname():
    row = _oig_obj(lastname=None, firstname=None, busname="TEST-PHARMA INC", npi=None)
    data = _normalize_oig(row)
    assert data["entity_type"] == "organization"
    assert data["organization_name"] == "TEST-PHARMA INC"
    assert data["npi"] is None


def test_normalize_oig_bad_npi_too_short():
    row = _oig_obj(npi="12345")  # 5 chars — too short
    data = _normalize_oig(row)
    assert data["npi"] is None


def test_normalize_oig_bad_npi_non_digit():
    row = _oig_obj(npi="12345ABC90")
    data = _normalize_oig(row)
    assert data["npi"] is None


def test_normalize_oig_reinstate_date_mapped():
    row = _oig_obj(reindate=date(2023, 3, 15))
    data = _normalize_oig(row)
    assert data["reinstate_date"] is not None
    assert data["reinstate_date"].year == 2023


def test_normalize_oig_no_excl_date():
    row = _oig_obj(excldate=None)
    # excldate=None → _normalize_oig must handle None excldate
    row.excldate = None
    data = _normalize_oig(row)
    assert data["exclusion_date"] is None


def test_normalize_oig_invalid_state_length():
    row = _oig_obj(state="NEW YORK")
    data = _normalize_oig(row)
    assert data["state"] is None


# ---------------------------------------------------------------------------
# Unit: _normalize_sam
# ---------------------------------------------------------------------------

def test_normalize_sam_organization():
    row = _sam_obj(name="TEST-ACME LLC", classification_type="Firm")
    data = _normalize_sam(row)
    assert data["source"] == "SAM"
    assert data["entity_type"] == "organization"
    assert data["organization_name"] == "TEST-ACME LLC"
    assert data["first_name"] is None
    assert data["last_name"] is None


def test_normalize_sam_individual_comma_name():
    row = _sam_obj(name="TEST-DOE, TEST-JANE", classification_type="Individual")
    data = _normalize_sam(row)
    assert data["entity_type"] == "individual"
    assert data["last_name"] == "TEST-DOE"
    assert data["first_name"] == "TEST-JANE"


def test_normalize_sam_individual_no_comma():
    row = _sam_obj(name="TEST-JOHNDOE", classification_type="Individual")
    data = _normalize_sam(row)
    assert data["entity_type"] == "individual"
    assert data["last_name"] == "TEST-JOHNDOE"
    assert data["first_name"] is None


def test_normalize_sam_state_province_too_long():
    row = _sam_obj(state_province="Texas")
    data = _normalize_sam(row)
    assert data["state"] is None


def test_normalize_sam_state_province_two_char():
    row = _sam_obj(state_province="CA")
    data = _normalize_sam(row)
    assert data["state"] == "CA"


def test_normalize_sam_npi_valid():
    row = _sam_obj(npi="9876543210")
    data = _normalize_sam(row)
    assert data["npi"] == "9876543210"


def test_normalize_sam_npi_invalid():
    row = _sam_obj(npi="ABCD")
    data = _normalize_sam(row)
    assert data["npi"] is None


def test_normalize_sam_termination_date_mapped():
    row = _sam_obj(termination_date=date(2024, 12, 31))
    data = _normalize_sam(row)
    assert data["reinstate_date"] is not None
    assert data["reinstate_date"].year == 2024


# ---------------------------------------------------------------------------
# Integration: full aggregation
# ---------------------------------------------------------------------------

def test_full_aggregation_oig_only(agg_session):
    """Three OIG rows → three exclusion_list rows inserted."""
    _insert_oig(agg_session, npi="1111111111", lastname="TEST-ALPHA")
    _insert_oig(agg_session, npi="2222222222", lastname="TEST-BETA")
    _insert_oig(agg_session, npi=None, lastname="TEST-GAMMA", busname="TEST-ORG A")
    agg_session.commit()

    result = run_aggregation(agg_session, oig_table="oig_leie_exclusions", sam_table="sam_exclusions", excl_table="core_exclusion_list")
    agg_session.commit()

    assert result.oig_seen == 3
    assert result.oig_inserted == 3
    assert result.oig_updated == 0
    assert result.sam_seen == 0
    assert result.total_errors == 0

    rows = agg_session.query(ExclusionListEntry).all()
    assert len(rows) == 3
    sources = {r.source for r in rows}
    assert sources == {"OIG"}


def test_full_aggregation_sam_only(agg_session):
    """Two SAM rows → two exclusion_list rows inserted."""
    _insert_sam(agg_session, npi="3333333333", name="TEST-DELTA",
                classification_type="Individual")
    _insert_sam(agg_session, npi=None, name="TEST-PHARMA EVIL INC")
    agg_session.commit()

    result = run_aggregation(agg_session, oig_table="oig_leie_exclusions", sam_table="sam_exclusions", excl_table="core_exclusion_list")
    agg_session.commit()

    assert result.sam_seen == 2
    assert result.sam_inserted == 2
    assert result.total_errors == 0
    rows = agg_session.query(ExclusionListEntry).all()
    assert len(rows) == 2
    assert all(r.source == "SAM" for r in rows)


def test_full_aggregation_oig_and_sam(agg_session):
    """OIG + SAM rows both aggregated — no cross-source dedup (different source field)."""
    # Same NPI in both OIG and SAM — should produce 2 rows (one per source)
    shared_npi = "5555555555"
    _insert_oig(agg_session, npi=shared_npi, lastname="TEST-BOTH-OIG")
    _insert_sam(agg_session, npi=shared_npi, name="TEST-BOTH-SAM")
    agg_session.commit()

    result = run_aggregation(agg_session, oig_table="oig_leie_exclusions", sam_table="sam_exclusions", excl_table="core_exclusion_list")
    agg_session.commit()

    assert result.oig_inserted == 1
    assert result.sam_inserted == 1
    rows = agg_session.query(ExclusionListEntry).all()
    assert len(rows) == 2
    assert {r.source for r in rows} == {"OIG", "SAM"}


def test_idempotent_rerun(agg_session):
    """Second call produces 0 inserts, N updates — no duplicates."""
    _insert_oig(agg_session, npi="6666666666", lastname="TEST-IDEM")
    _insert_sam(agg_session, npi="7777777777", name="TEST-IDEM SAM")
    agg_session.commit()

    # First run
    r1 = run_aggregation(agg_session, oig_table="oig_leie_exclusions", sam_table="sam_exclusions", excl_table="core_exclusion_list")
    agg_session.commit()
    assert r1.total_inserted == 2
    assert r1.total_updated == 0

    # Second run — same source data
    r2 = run_aggregation(agg_session, oig_table="oig_leie_exclusions", sam_table="sam_exclusions", excl_table="core_exclusion_list")
    agg_session.commit()
    assert r2.total_inserted == 0
    assert r2.total_updated == 2

    # Still only 2 rows in exclusion_list
    count = agg_session.query(ExclusionListEntry).count()
    assert count == 2


def test_delisting_npi_removed_from_source(agg_session):
    """OIG row with NPI removed from source → reinstate_date set on aggregation rerun."""
    npi = "8888888888"
    rowid = _insert_oig(agg_session, npi=npi, lastname="TEST-DELIST")
    agg_session.commit()

    # First run — populates exclusion_list with the NPI row.
    # Pass oig_min_rows=0 to bypass the CONCERN-1 completeness guard in tests
    # (production guard needs 60k+ rows; unit tests legitimately have 1 row).
    r1 = run_aggregation(agg_session, oig_table="oig_leie_exclusions", sam_table="sam_exclusions", excl_table="core_exclusion_list", oig_min_rows=0, sam_min_rows=0)
    agg_session.commit()
    assert r1.oig_inserted == 1

    # Simulate delisting: delete the OIG source row
    _delete_oig_by_id(agg_session, rowid)
    agg_session.commit()

    # Second run — NPI no longer in source → must be delisted
    r2 = run_aggregation(agg_session, oig_table="oig_leie_exclusions", sam_table="sam_exclusions", excl_table="core_exclusion_list", oig_min_rows=0, sam_min_rows=0)
    agg_session.commit()
    assert r2.delisted == 1

    entry = agg_session.query(ExclusionListEntry).filter_by(source="OIG", npi=npi).one()
    assert entry.reinstate_date is not None


def test_delisting_does_not_re_delist_already_terminated(agg_session):
    """Rows already terminated (reinstate_date set) are left unchanged on rerun."""
    npi = "9999999999"
    terminated_at = datetime(2022, 1, 1, tzinfo=timezone.utc)
    # Insert a row directly with reinstate_date already set
    entry = ExclusionListEntry(
        source="OIG",
        entity_type="individual",
        npi=npi,
        last_name="TEST-ALREADY-GONE",
        reinstate_date=terminated_at,
    )
    agg_session.add(entry)
    agg_session.commit()

    # Run with empty source — the terminated row should stay unchanged.
    # Pass oig_min_rows=0 so the completeness guard doesn't suppress delisting;
    # the result must be 0 because the row already has reinstate_date, not
    # because the guard fired.
    r = run_aggregation(agg_session, oig_table="oig_leie_exclusions", sam_table="sam_exclusions", excl_table="core_exclusion_list", oig_min_rows=0, sam_min_rows=0)
    agg_session.commit()

    # delisted count should be 0 since the row already has reinstate_date
    assert r.delisted == 0
    # reinstate_date unchanged — strip tzinfo for comparison since SQLite
    # returns timezone-naive datetimes when reading back stored values.
    refreshed = agg_session.query(ExclusionListEntry).filter_by(npi=npi).one()
    assert refreshed.reinstate_date.replace(tzinfo=None) == terminated_at.replace(tzinfo=None)


def test_empty_sources_no_error(agg_session):
    """Both source tables empty → aggregation succeeds with 0 counts."""
    result = run_aggregation(agg_session, oig_table="oig_leie_exclusions", sam_table="sam_exclusions", excl_table="core_exclusion_list")
    agg_session.commit()

    assert result.oig_seen == 0
    assert result.sam_seen == 0
    assert result.total_errors == 0
    assert result.total_inserted == 0
    assert result.delisted == 0


# ---------------------------------------------------------------------------
# CONCERN-2: NPI merge — no-NPI row upgraded when NPI arrives later
# ---------------------------------------------------------------------------

def test_no_npi_row_upgraded_when_npi_arrives(agg_session):
    """A no-NPI name-key row is upgraded (not duplicated) when the source
    later delivers a row for the same entity that includes an NPI.

    CONCERN-2 fix (P0a v2): v1 inserted a new row in this scenario,
    creating duplicate entries and breaking downstream screens.
    """
    # Pre-seed a no-NPI OIG row for "TEST-UPGRADE, TEST-FIRST" in NY
    _insert_oig(agg_session, npi=None, lastname="TEST-UPGRADE",
                firstname="TEST-FIRST", state="NY", excltype="1128a1")
    agg_session.commit()

    # First aggregation run — inserts the name-key row (no NPI)
    r1 = run_aggregation(agg_session, oig_table="oig_leie_exclusions", sam_table="sam_exclusions", excl_table="core_exclusion_list")
    agg_session.commit()
    assert r1.oig_inserted == 1

    # Simulate source gaining an NPI for the same entity
    agg_session.execute(text("""
        UPDATE oig_leie_exclusions
        SET npi = '1234567899'
        WHERE lastname = 'TEST-UPGRADE' AND firstname = 'TEST-FIRST'
    """))
    agg_session.commit()

    # Second aggregation run — must UPGRADE the existing row, not insert
    r2 = run_aggregation(agg_session, oig_table="oig_leie_exclusions", sam_table="sam_exclusions", excl_table="core_exclusion_list")
    agg_session.commit()
    assert r2.oig_inserted == 0, "NPI arrival must not create a duplicate row"
    assert r2.oig_updated == 1, "existing row must be updated with the NPI"

    # Only one row in the list — no duplicate
    rows = agg_session.query(ExclusionListEntry).filter_by(source="OIG").all()
    assert len(rows) == 1
    assert rows[0].npi == "1234567899"


# ---------------------------------------------------------------------------
# CONCERN-1: Completeness guard — delisting suppressed on partial source load
# ---------------------------------------------------------------------------

def test_delisting_suppressed_when_source_below_threshold(agg_session):
    """Delisting is suppressed when the source row count is below the minimum.

    CONCERN-1 fix (P0a v2): without the completeness guard, a partial
    source load (e.g., ingestion failure after 1k rows) would falsely
    reinstate all exclusions not in the incomplete slice.

    This test verifies that passing a high min_rows threshold prevents
    delisting even when rows are absent from the source.
    """
    npi = "2222222222"
    rowid = _insert_oig(agg_session, npi=npi, lastname="TEST-GUARD")
    agg_session.commit()

    # First run with guard disabled — populates the row
    r1 = run_aggregation(
        agg_session,
        oig_table="oig_leie_exclusions",
        sam_table="sam_exclusions",
        excl_table="core_exclusion_list",
        oig_min_rows=0,
        sam_min_rows=0,
    )
    agg_session.commit()
    assert r1.oig_inserted == 1

    # Delete the source row to simulate removal
    _delete_oig_by_id(agg_session, rowid)
    agg_session.commit()

    # Second run with high min_rows threshold — guard must suppress delisting
    r2 = run_aggregation(
        agg_session,
        oig_table="oig_leie_exclusions",
        sam_table="sam_exclusions",
        excl_table="core_exclusion_list",
        oig_min_rows=99999,   # impossible to reach with test data
        sam_min_rows=99999,
    )
    agg_session.commit()
    assert r2.delisted == 0, "completeness guard must suppress delisting when source is below threshold"

    entry = agg_session.query(ExclusionListEntry).filter_by(source="OIG", npi=npi).one()
    assert entry.reinstate_date is None, "reinstate_date must remain NULL when guard suppresses delisting"
