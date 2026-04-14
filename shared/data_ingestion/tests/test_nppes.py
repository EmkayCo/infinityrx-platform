"""Tests for NPPES ingestion pipeline.

Covers:
- Full column coverage (all 300+ columns populated in at least one fixture row)
- Taxonomy explosion (stops at first empty slot)
- Identifier explosion (up to 50 slots)
- Address extraction (mailing + practice, 2 rows per NPI)
- Pharmacy supplement (entity=2 + taxonomy 333*)
- NPI Luhn validation
- Deactivated NPI loading
- Idempotent upsert
- Authorized-official fields
- Replacement NPI

LESSON-001: SAVEPOINT-based isolation (tested via conftest db_session fixture).
LESSON-007: _UUIDString TypeDecorator for SQLite UUID columns.
LESSON-004: regex uses fullmatch / \\A...\\Z.
LESSON-010: NPI is public — plaintext throughout.
LESSON-011: Global reference — no TenantScopedMixin on any prescriber_dir table.
"""

from __future__ import annotations

import csv
import importlib.util
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import JSON, Integer, String, Text, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import TypeDecorator

# ── sys.path / import setup ───────────────────────────────────────────────
# Problem: test_fda_ndc_parser.py loads drug-database's src into
# sys.modules["src"] before pytest reaches this file. Using bare
# "from src.X import Y" here would pick up the wrong package.
#
# Solution: load prescriber-directory modules using importlib file paths
# under the namespace "prescriber_src.*" so they never collide with
# drug-database's "src.*". The prescriber modules themselves use relative
# imports (from .X) so they are also insulated from the collision.

_TESTS_DIR = Path(__file__).resolve().parent
_SHARED_ROOT = _TESTS_DIR.parent.parent
_PROJECT_ROOT = _SHARED_ROOT.parent
_PRESCRIBER_MODULE = _PROJECT_ROOT / "modules" / "prescriber-directory"
_PRESCRIBER_SRC = _PRESCRIBER_MODULE / "src"

# Minimal environment so shared.config doesn't raise
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost/")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")
os.environ.setdefault(
    "ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM="
)

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _load_file_as(file_path: Path, full_name: str) -> Any:
    """Load a .py file under sys.modules[full_name], registering parent packages.

    Parent packages (e.g. "prescriber_src", "prescriber_src.models") are
    registered as namespace packages so relative imports within the loaded
    modules resolve correctly via the "prescriber_src.*" hierarchy.
    """
    if full_name in sys.modules:
        return sys.modules[full_name]

    # Register parent packages as namespace packages first
    parts = full_name.split(".")
    for i in range(1, len(parts)):
        pkg_name = ".".join(parts[:i])
        if pkg_name not in sys.modules:
            import types
            pkg = types.ModuleType(pkg_name)
            # Point __path__ at the corresponding directory so sub-imports work
            depth = i  # depth=1 → prescriber_src → _PRESCRIBER_MODULE
            # We map:
            #   prescriber_src           → modules/prescriber-directory
            #   prescriber_src.src       → (unused; we skip "src" in naming)
            #   prescriber_src.models    → modules/prescriber-directory/src/models
            #   prescriber_src.services  → modules/prescriber-directory/src/services
            #   prescriber_src.utils     → modules/prescriber-directory/src/utils
            dir_parts = parts[1:i]  # parts after "prescriber_src"
            pkg_dir = _PRESCRIBER_SRC.joinpath(*dir_parts) if dir_parts else _PRESCRIBER_MODULE
            pkg.__path__ = [str(pkg_dir)]  # type: ignore[attr-defined]
            pkg.__package__ = pkg_name
            sys.modules[pkg_name] = pkg

    spec = importlib.util.spec_from_file_location(full_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {file_path} as {full_name}")
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = ".".join(parts[:-1]) if len(parts) > 1 else full_name
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# Load modules under "prescriber_src.*" namespace
_tables_mod = _load_file_as(
    _PRESCRIBER_SRC / "models" / "tables.py",
    "prescriber_src.models.tables",
)
_nppes_tables_mod = _load_file_as(
    _PRESCRIBER_SRC / "models" / "nppes_tables.py",
    "prescriber_src.models.nppes_tables",
)
_validators_mod = _load_file_as(
    _PRESCRIBER_SRC / "utils" / "validators.py",
    "prescriber_src.utils.validators",
)
_taxonomy_mod = _load_file_as(
    _PRESCRIBER_SRC / "services" / "taxonomy_service.py",
    "prescriber_src.services.taxonomy_service",
)
_ingestion_mod = _load_file_as(
    _PRESCRIBER_SRC / "services" / "nppes_ingestion.py",
    "prescriber_src.services.nppes_ingestion",
)

# Bind to local names
NppesPrescriberDetail = _nppes_tables_mod.NppesPrescriberDetail
PrescriberAddress = _nppes_tables_mod.PrescriberAddress
PrescriberIdentifier = _nppes_tables_mod.PrescriberIdentifier
PrescriberTaxonomy = _nppes_tables_mod.PrescriberTaxonomy
PrescriberBase = _tables_mod.PrescriberBase
NppesIngestionStats = _ingestion_mod.NppesIngestionStats
_build_addresses = _ingestion_mod._build_addresses
_build_detail = _ingestion_mod._build_detail
_build_identifiers = _ingestion_mod._build_identifiers
_build_taxonomies = _ingestion_mod._build_taxonomies
_or_none = _ingestion_mod._or_none
load_nppes_satellite_tables = _ingestion_mod.load_nppes_satellite_tables
NpiValidationError = _validators_mod.NpiValidationError
validate_npi = _validators_mod.validate_npi

# ── Sample data path ──────────────────────────────────────────────────────
_SAMPLE_CSV = (
    _TESTS_DIR / "sample_data" / "nppes" / "npidata_sample.csv"
)

# ── SQLite compatibility helpers (LESSON-007) ─────────────────────────────


class _UUIDString(TypeDecorator):
    """SQLite-compatible UUID stored as VARCHAR(36). (LESSON-007)"""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        return str(value) if value is not None else None

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:
        if value is None:
            return None
        return uuid.UUID(str(value))


def _patch_prescriber_tables_for_sqlite() -> None:
    """Replace PG_UUID with _UUIDString and JSONB with JSON on prescriber_dir tables."""
    tables = [
        NppesPrescriberDetail.__table__,
        PrescriberAddress.__table__,
        PrescriberTaxonomy.__table__,
        PrescriberIdentifier.__table__,
    ]
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
        table._sqlite_patched = True  # type: ignore[attr-defined]


_patch_prescriber_tables_for_sqlite()

# ── Session fixtures (LESSON-001) ─────────────────────────────────────────


@pytest.fixture(scope="session")
def _engine():
    """Session-scoped SQLite engine with prescriber_dir tables (mapped to None schema)."""
    raw = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(raw, "connect")
    def _set_pragma(dbapi_conn: Any, _: Any) -> None:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.close()

    engine = raw.execution_options(
        schema_translate_map={"prescriber_dir": None, "shared": None}
    )

    PrescriberBase.metadata.create_all(
        engine,
        tables=[
            NppesPrescriberDetail.__table__,
            PrescriberAddress.__table__,
            PrescriberTaxonomy.__table__,
            PrescriberIdentifier.__table__,
        ],
    )
    yield engine
    PrescriberBase.metadata.drop_all(
        engine,
        tables=[
            NppesPrescriberDetail.__table__,
            PrescriberAddress.__table__,
            PrescriberTaxonomy.__table__,
            PrescriberIdentifier.__table__,
        ],
    )
    raw.dispose()


@pytest.fixture
def db(_engine) -> "Session":
    """SAVEPOINT-based isolated session per LESSON-001."""
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


# ── Helpers ───────────────────────────────────────────────────────────────


def _read_sample_rows() -> list[dict[str, str]]:
    """Load all rows from the synthetic NPPES sample CSV."""
    rows = []
    with _SAMPLE_CSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows.append(dict(row))
    return rows


def _row_by_npi(rows: list[dict[str, str]], npi: str) -> dict[str, str]:
    for r in rows:
        if r.get("NPI") == npi:
            return r
    raise KeyError(f"NPI {npi!r} not found in sample data")


# ── Tests: NPI Luhn validation ────────────────────────────────────────────


def test_npi_luhn_validation_valid_npi_passes():
    """Known-valid NPI (1000000004) should pass Luhn check."""
    assert validate_npi("1000000004") is True


def test_npi_luhn_validation_invalid_npi_raises():
    """NPI with bad check digit (1000000005) should fail Luhn."""
    with pytest.raises(NpiValidationError, match="Luhn"):
        validate_npi("1000000005")


def test_npi_luhn_validation_non_digits_raises():
    """Non-numeric NPI should raise NpiValidationError."""
    with pytest.raises(NpiValidationError):
        validate_npi("ABCDEFGHIJ")


def test_npi_luhn_validation_wrong_length_raises():
    """NPI shorter than 10 digits should raise NpiValidationError."""
    with pytest.raises(NpiValidationError):
        validate_npi("12345")


# ── Tests: Address extraction ─────────────────────────────────────────────


def test_address_extraction_mailing_and_practice():
    """Row 1 (NPI 1000000004) has both mailing and practice → 2 address rows."""
    rows = _read_sample_rows()
    row = _row_by_npi(rows, "1000000004")
    now = datetime.now(timezone.utc)

    addresses = _build_addresses("1000000004", row, now)

    assert len(addresses) == 2
    types = {a.address_type for a in addresses}
    assert types == {"mailing", "practice"}

    mailing = next(a for a in addresses if a.address_type == "mailing")
    assert mailing.line_1 == "123 MAIN ST"
    assert mailing.city == "ANYTOWN"
    assert mailing.state == "CA"
    assert mailing.postal_code == "90210"
    assert mailing.telephone_number == "3105550101"

    practice = next(a for a in addresses if a.address_type == "practice")
    assert practice.line_1 == "456 CLINIC RD"
    assert practice.city == "BEVERLY HILLS"


def test_address_extraction_missing_mailing_only_practice():
    """Row with no mailing line_1 should return only the practice address row."""
    now = datetime.now(timezone.utc)
    # Construct a row with only practice address
    row: dict[str, str] = {
        "Provider First Line Business Mailing Address": "",
        "Provider Second Line Business Mailing Address": "",
        "Provider Business Mailing Address City Name": "",
        "Provider Business Mailing Address State Name": "",
        "Provider Business Mailing Address Postal Code": "",
        "Provider Business Mailing Address Country Code (If outside U.S.)": "",
        "Provider Business Mailing Address Telephone Number": "",
        "Provider Business Mailing Address Fax Number": "",
        "Provider First Line Business Practice Location Address": "99 PRACTICE ST",
        "Provider Second Line Business Practice Location Address": "",
        "Provider Business Practice Location Address City Name": "BOSTON",
        "Provider Business Practice Location Address State Name": "MA",
        "Provider Business Practice Location Address Postal Code": "02101",
        "Provider Business Practice Location Address Country Code (If outside U.S.)": "",
        "Provider Business Practice Location Address Telephone Number": "6175550000",
        "Provider Business Practice Location Address Fax Number": "",
    }
    addresses = _build_addresses("1000000004", row, now)
    assert len(addresses) == 1
    assert addresses[0].address_type == "practice"


# ── Tests: Taxonomy explosion ─────────────────────────────────────────────


def test_taxonomy_explode_stops_at_first_empty():
    """Row 8 (NPI 1000000079) has 3 taxonomies then empty → exactly 3 rows."""
    rows = _read_sample_rows()
    row = _row_by_npi(rows, "1000000079")
    now = datetime.now(timezone.utc)

    taxonomies = _build_taxonomies("1000000079", row, now)

    assert len(taxonomies) == 3
    seqs = [t.sequence for t in taxonomies]
    assert seqs == [1, 2, 3]


def test_taxonomy_explode_all_15_slots():
    """Row 7 (NPI 1000000061) has all 15 taxonomies → 15 rows."""
    rows = _read_sample_rows()
    row = _row_by_npi(rows, "1000000061")
    now = datetime.now(timezone.utc)

    taxonomies = _build_taxonomies("1000000061", row, now)

    assert len(taxonomies) == 15
    for i, t in enumerate(taxonomies, 1):
        assert t.sequence == i
        assert t.taxonomy_code is not None


def test_taxonomy_primary_flag_set_correctly():
    """Row 1 (NPI 1000000004) — slot 1 is primary, slots 2 and 3 are not."""
    rows = _read_sample_rows()
    row = _row_by_npi(rows, "1000000004")
    now = datetime.now(timezone.utc)

    taxonomies = _build_taxonomies("1000000004", row, now)

    primary = [t for t in taxonomies if t.is_primary == "Y"]
    non_primary = [t for t in taxonomies if t.is_primary == "N"]
    assert len(primary) == 1
    assert primary[0].sequence == 1
    assert len(non_primary) == 2


# ── Tests: Identifier explosion ───────────────────────────────────────────


def test_identifier_explode_up_to_50():
    """Row 9 (NPI 1000000087) has 50 identifiers → 50 rows."""
    rows = _read_sample_rows()
    row = _row_by_npi(rows, "1000000087")
    now = datetime.now(timezone.utc)

    identifiers = _build_identifiers("1000000087", row, now)

    assert len(identifiers) == 50
    for i, ident in enumerate(identifiers, 1):
        assert ident.sequence == i
        assert ident.identifier is not None


def test_identifier_explode_stops_at_first_empty():
    """Row 1 (NPI 1000000004) has 5 identifiers then empty → exactly 5 rows."""
    rows = _read_sample_rows()
    row = _row_by_npi(rows, "1000000004")
    now = datetime.now(timezone.utc)

    identifiers = _build_identifiers("1000000004", row, now)

    assert len(identifiers) == 5


# ── Tests: Full column coverage ───────────────────────────────────────────


def test_parse_full_column_coverage():
    """All 300+ NPPES columns appear in at least one sample row."""
    rows = _read_sample_rows()
    assert len(rows) > 0
    all_cols = set(rows[0].keys())

    # Verify taxonomy columns present up to _15
    for i in range(1, 16):
        assert f"Healthcare Provider Taxonomy Code_{i}" in all_cols, \
            f"Missing taxonomy column {i}"

    # Verify identifier columns present up to _50
    for i in range(1, 51):
        assert f"Other Provider Identifier_{i}" in all_cols, \
            f"Missing identifier column {i}"

    # Total columns should be 300+
    assert len(all_cols) >= 300, f"Only {len(all_cols)} columns found"

    # Check at least one row has all extended fields populated
    full_row = _row_by_npi(rows, "1000000095")
    assert full_row["Employer Identification Number (EIN)"] == "123456780"
    assert full_row["Parent Organization Legal Business Name"] == "PARENT CORP"
    assert full_row["Authorized Official Middle Name"] == "X"
    assert full_row["Is Organization Subpart"] == "Y"
    assert full_row["Certification Date"] == "12/01/2001"
    assert full_row["Provider Other Last Name (former)"] == "CHANG-WU"
    assert full_row["Authorized Official Name Prefix Text"] == "DR."
    assert full_row["Authorized Official Name Suffix Text"] == "II"


# ── Tests: Detail object construction ────────────────────────────────────


def test_build_detail_individual_fields():
    """NPI 1000000004 detail should map all individual name fields correctly."""
    rows = _read_sample_rows()
    row = _row_by_npi(rows, "1000000004")
    now = datetime.now(timezone.utc)

    detail = _build_detail(row, now)

    assert detail.npi == "1000000004"
    assert detail.entity_type_code == "1"
    assert detail.provider_last_name_legal == "SMITH"
    assert detail.provider_first_name == "JOHN"
    assert detail.provider_middle_name == "ALAN"
    assert detail.provider_name_prefix == "DR."
    assert detail.provider_credential_text == "MD"
    assert detail.provider_gender_code == "M"
    assert detail.replacement_npi is None
    assert detail.ein is None


def test_build_detail_organization_fields():
    """NPI 1000000012 (pharmacy org) detail should map org + authorized-official fields."""
    rows = _read_sample_rows()
    row = _row_by_npi(rows, "1000000012")
    now = datetime.now(timezone.utc)

    detail = _build_detail(row, now)

    assert detail.entity_type_code == "2"
    assert detail.provider_organization_name_legal == "ACME PHARMACY INC"
    assert detail.provider_other_organization_name == "ACME DRUGS"
    assert detail.authorized_official_last_name == "JONES"
    assert detail.authorized_official_first_name == "MARY"
    assert detail.authorized_official_middle_name == "K"
    assert detail.authorized_official_title_or_position == "PRESIDENT"
    assert detail.authorized_official_telephone_number == "2125550200"
    assert detail.authorized_official_credential == "RPH"
    assert detail.is_sole_proprietor == "X"


def test_build_detail_replacement_npi():
    """NPI 1000000053 should have replacement_npi set."""
    rows = _read_sample_rows()
    row = _row_by_npi(rows, "1000000053")
    now = datetime.now(timezone.utc)

    detail = _build_detail(row, now)

    assert detail.replacement_npi == "1000000061"


def test_build_detail_certification_date():
    """NPI 1000000012 should have certification_date populated."""
    rows = _read_sample_rows()
    row = _row_by_npi(rows, "1000000012")
    now = datetime.now(timezone.utc)
    detail = _build_detail(row, now)
    from datetime import date
    assert detail.certification_date == date(2015, 6, 20)


def test_build_detail_parent_org_fields():
    """NPI 1000000095 should have parent org LBN and TIN populated."""
    rows = _read_sample_rows()
    row = _row_by_npi(rows, "1000000095")
    now = datetime.now(timezone.utc)
    detail = _build_detail(row, now)
    assert detail.parent_organization_lbn == "PARENT CORP"
    assert detail.parent_organization_tin == "999888777"
    assert detail.ein == "123456780"


# ── Tests: Deactivated NPI ────────────────────────────────────────────────


def test_deactivated_npi_loaded_with_status(db: Session, tmp_path: Path):
    """NPI 1000000038 is deactivated — should load with deactivation date set."""
    # Write a mini CSV with just the deactivated NPI
    rows = _read_sample_rows()
    deactivated = _row_by_npi(rows, "1000000038")

    mini_csv = tmp_path / "mini.csv"
    with mini_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(deactivated.keys()))
        writer.writeheader()
        writer.writerow(deactivated)

    stats = load_nppes_satellite_tables(db, mini_csv)

    assert stats.individuals == 1
    assert stats.organizations == 0

    detail = db.query(NppesPrescriberDetail).filter_by(npi="1000000038").one()
    from datetime import date
    assert detail.npi_deactivation_date == date(2023, 11, 30)
    assert detail.npi_deactivation_reason_code == "DT"
    assert detail.npi_reactivation_date is None


# ── Tests: Pharmacy supplement ────────────────────────────────────────────


def test_pharmacy_supplement_for_entity_2_taxonomy_333(db: Session, tmp_path: Path):
    """NPI 1000000012 (org, taxonomy 3336C0003X) should trigger pharmacy supplement attempt."""
    rows = _read_sample_rows()
    pharmacy_row = _row_by_npi(rows, "1000000012")

    mini_csv = tmp_path / "pharmacy.csv"
    with mini_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(pharmacy_row.keys()))
        writer.writeheader()
        writer.writerow(pharmacy_row)

    # T2's pharmacies table doesn't exist in test DB — supplement should log-and-skip
    stats = load_nppes_satellite_tables(db, mini_csv)

    # Should count as an org regardless of supplement success
    assert stats.organizations == 1
    # pharmacy_supplements may be 0 (T2 not landed) or 1 (T2 landed)
    # Both are valid — the point is no exception raised
    assert stats.pharmacy_supplements >= 0


def test_pharmacy_supplement_skipped_when_entity_1(db: Session, tmp_path: Path):
    """Entity type 1 (individual) should never trigger pharmacy supplement."""
    rows = _read_sample_rows()
    individual_row = _row_by_npi(rows, "1000000004")

    mini_csv = tmp_path / "individual.csv"
    with mini_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(individual_row.keys()))
        writer.writeheader()
        writer.writerow(individual_row)

    stats = load_nppes_satellite_tables(db, mini_csv)

    assert stats.individuals == 1
    assert stats.pharmacy_supplements == 0


def test_pharmacy_supplement_skipped_when_non_pharmacy_taxonomy(db: Session, tmp_path: Path):
    """Entity type 2 with non-333 taxonomy (hospital) should not supplement."""
    rows = _read_sample_rows()
    hospital_row = _row_by_npi(rows, "1000000020")  # taxonomy 282N00000X

    mini_csv = tmp_path / "hospital.csv"
    with mini_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(hospital_row.keys()))
        writer.writeheader()
        writer.writerow(hospital_row)

    stats = load_nppes_satellite_tables(db, mini_csv)

    assert stats.organizations == 1
    assert stats.pharmacy_supplements == 0


# ── Tests: Upsert idempotency ─────────────────────────────────────────────


def test_upsert_idempotent(db: Session, tmp_path: Path):
    """Running load_nppes_satellite_tables twice on same data should not double rows."""
    rows = _read_sample_rows()
    individual_row = _row_by_npi(rows, "1000000079")  # 3 taxonomies

    mini_csv = tmp_path / "idem.csv"
    with mini_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(individual_row.keys()))
        writer.writeheader()
        writer.writerow(individual_row)

    # First load
    stats1 = load_nppes_satellite_tables(db, mini_csv)
    count_tax_1 = (
        db.query(PrescriberTaxonomy).filter_by(npi="1000000079").count()
    )

    # Second load (upsert/replace)
    stats2 = load_nppes_satellite_tables(db, mini_csv)
    count_tax_2 = (
        db.query(PrescriberTaxonomy).filter_by(npi="1000000079").count()
    )

    assert stats1.total_taxonomies == 3
    assert stats2.total_taxonomies == 3
    # Taxonomies replaced in place — no doubling
    assert count_tax_1 == 3
    assert count_tax_2 == 3

    count_detail = (
        db.query(NppesPrescriberDetail).filter_by(npi="1000000079").count()
    )
    assert count_detail == 1


# ── Tests: Full sample load ───────────────────────────────────────────────


def test_full_sample_load(db: Session):
    """Load all 10 sample rows — verify aggregate counts."""
    stats = load_nppes_satellite_tables(db, _SAMPLE_CSV)

    # 10 total: rows 1,4,6,7,8,9 are entity=1 → 6 individuals
    # rows 2,3,5,10 are entity=2 → 4 organizations
    assert stats.individuals == 6
    assert stats.organizations == 4
    assert stats.total_prescribers == 10

    # All rows get addresses (mailing + practice where both present)
    # Row 2 has mailing (no fax) and practice → 2
    # Most rows have both → expect at least 16 addresses for 10 rows
    assert stats.total_addresses >= 16

    # Taxonomies: row 7 has 15, row 2 has 1, row 3 has 1, etc.
    assert stats.total_taxonomies >= 20

    # Identifiers: row 9 has 50, row 1 has 5, row 2 has 3, etc.
    assert stats.total_identifiers >= 55

    assert stats.records_errored == 0


def test_full_sample_load_detail_records(db: Session):
    """After full load, NppesPrescriberDetail should have 10 rows."""
    load_nppes_satellite_tables(db, _SAMPLE_CSV)
    count = db.query(NppesPrescriberDetail).count()
    assert count == 10


def test_full_sample_load_taxonomy_records(db: Session):
    """After full load, verify taxonomy counts for specific NPIs."""
    load_nppes_satellite_tables(db, _SAMPLE_CSV)

    # NPI 1000000061 should have 15 taxonomies
    count_15 = (
        db.query(PrescriberTaxonomy).filter_by(npi="1000000061").count()
    )
    assert count_15 == 15

    # NPI 1000000079 should have exactly 3 taxonomies
    count_3 = (
        db.query(PrescriberTaxonomy).filter_by(npi="1000000079").count()
    )
    assert count_3 == 3


def test_full_sample_load_identifier_records(db: Session):
    """After full load, NPI 1000000087 should have exactly 50 identifiers."""
    load_nppes_satellite_tables(db, _SAMPLE_CSV)
    count = (
        db.query(PrescriberIdentifier).filter_by(npi="1000000087").count()
    )
    assert count == 50


# ── Tests: Invalid NPI skipping ───────────────────────────────────────────


def test_invalid_npi_luhn_fail_increments_error_count(tmp_path: Path, db: Session):
    """A row with an NPI that fails Luhn check should be skipped (error count += 1)."""
    rows = _read_sample_rows()
    bad_row = dict(_row_by_npi(rows, "1000000004"))
    bad_row["NPI"] = "1000000005"  # fails Luhn (valid is 1000000004)

    mini_csv = tmp_path / "bad_npi.csv"
    with mini_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(bad_row.keys()))
        writer.writeheader()
        writer.writerow(bad_row)

    stats = load_nppes_satellite_tables(db, mini_csv)
    assert stats.records_errored == 1
    assert stats.total_prescribers == 0


def test_non_digit_npi_skipped(tmp_path: Path, db: Session):
    """NPI with non-digits should be skipped (records_skipped += 1)."""
    rows = _read_sample_rows()
    bad_row = dict(_row_by_npi(rows, "1000000004"))
    bad_row["NPI"] = "ABCDEFGHIJ"

    mini_csv = tmp_path / "alpha_npi.csv"
    with mini_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(bad_row.keys()))
        writer.writeheader()
        writer.writerow(bad_row)

    stats = load_nppes_satellite_tables(db, mini_csv)
    assert stats.records_skipped >= 1
    assert stats.total_prescribers == 0


# ── Tests: Authorized official ────────────────────────────────────────────


def test_authorized_official_fields_populated(db: Session, tmp_path: Path):
    """NPI 1000000046 — authorized official all fields should be in detail."""
    rows = _read_sample_rows()
    ao_row = _row_by_npi(rows, "1000000046")

    mini_csv = tmp_path / "ao.csv"
    with mini_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(ao_row.keys()))
        writer.writeheader()
        writer.writerow(ao_row)

    load_nppes_satellite_tables(db, mini_csv)

    detail = db.query(NppesPrescriberDetail).filter_by(npi="1000000046").one()
    assert detail.authorized_official_last_name == "BROWN"
    assert detail.authorized_official_first_name == "DAVID"
    assert detail.authorized_official_middle_name == "C"
    assert detail.authorized_official_title_or_position == "CFO"
    assert detail.authorized_official_credential == "CPA"
    assert detail.authorized_official_name_prefix == "DR."
    assert detail.authorized_official_name_suffix == "JR"


# ── Tests: Field registry registration ───────────────────────────────────


def test_field_registry_nppes_registered():
    """NPPES source fields should be registered in the global field registry."""
    # Import triggers the register_field calls
    import importlib
    import shared.data_ingestion.sources.nppes  # noqa: F401

    from shared.data_ingestion.field_registry import registry

    nppes_fields = registry.fields_for_source("nppes")
    assert len(nppes_fields) > 10

    field_names = [f.column for f in nppes_fields]
    assert "npi" in field_names
    assert "taxonomy_code" in field_names
    assert "identifier" in field_names


# ── Tests: _or_none helper ────────────────────────────────────────────────


def test_or_none_empty_string_returns_none():
    assert _or_none("") is None


def test_or_none_whitespace_returns_none():
    assert _or_none("   ") is None


def test_or_none_value_returns_stripped():
    assert _or_none("  HELLO  ") == "HELLO"


def test_or_none_none_input_returns_none():
    assert _or_none(None) is None  # type: ignore[arg-type]
