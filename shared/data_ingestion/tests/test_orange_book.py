"""Tests for the FDA Orange Book ingestion pipeline.

Covers:
- products.txt parsing (all 14 fields + dosage_form/route split from DF;Route)
- "Approved Prior to Jan 1, 1982" → date(1982, 1, 1) + flag=True
- application_number computed as "{appl_type_prefix}{appl_no:0>6}"
- patent delist_flag Y→True, N→False
- exclusivity_code captured correctly
- te_code nullable for original RX products
- cross-reference view joins to drugs table
- upsert idempotency (load twice → same row count)
- patent delete-then-insert (load with 2 patents, reload with 1 → 1 remains)
- parse_mmm_dd_yyyy: all months, single/double digit days, edge cases
- Y/N boolean parsing
- SAVEPOINT isolation (LESSON-001) + _UUIDString (LESSON-007)
- BigInteger → Integer patch per T3's pattern

SQLAlchemy isolation:
  SAVEPOINT-based per LESSON-001.
  _UUIDString TypeDecorator per LESSON-007 (shared IngestionRun uses PG_UUID).
  BigInteger PK → Integer patch for SQLite autoincrement compatibility.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import JSON, BigInteger, Integer, String, create_engine, event, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import TypeDecorator

# ---------------------------------------------------------------------------
# Environment defaults — shared.config must not raise during import
# ---------------------------------------------------------------------------

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost/")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")
os.environ.setdefault(
    "ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM="
)

# ---------------------------------------------------------------------------
# sys.path setup — must happen before any src.* imports
# ---------------------------------------------------------------------------

import sys

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DRUG_DB_ROOT = _REPO_ROOT / "modules" / "drug-database"
for _p in (str(_REPO_ROOT), str(_DRUG_DB_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

from shared.data_ingestion.date_parsers import parse_mmm_dd_yyyy
from shared.data_ingestion.models import IngestionRun, IngestionSchedule
from shared.data_ingestion.sources.fda_orange_book import (
    _compute_application_number,
    _parse_approval_date,
    _parse_exclusivity,
    _parse_patents,
    _parse_products,
    _split_df_route,
    _strip_or_none,
    _yn_to_bool,
)
from shared.db.base import Base

from src.models.ndc_tables import Drug, NDCBase, SCHEMA as NDC_SCHEMA  # type: ignore[import]
from src.models.orange_book_tables import (  # type: ignore[import]
    DrugExclusivity,
    DrugOrangeBook,
    DrugPatent,
    OrangeBookBase,
    SCHEMA as OB_SCHEMA,
)

# ---------------------------------------------------------------------------
# Sample data path
# ---------------------------------------------------------------------------

_SAMPLE_DIR = Path(__file__).parent / "sample_data" / "orange_book"

# ---------------------------------------------------------------------------
# SQLite compatibility patches (LESSON-007, T3 pattern)
# ---------------------------------------------------------------------------


class _UUIDString(TypeDecorator):
    """SQLite-compatible UUID stored as VARCHAR(36). LESSON-007."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        return str(value) if value is not None else None

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:
        return uuid.UUID(str(value)) if value is not None else None


def _patch_ingestion_tables_for_sqlite() -> None:
    """Patch shared IngestionRun/IngestionSchedule for SQLite SAVEPOINT compatibility."""
    for table in [IngestionRun.__table__, IngestionSchedule.__table__]:
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
                col.server_default = None  # type: ignore[attr-defined]
        table._sqlite_patched = True  # type: ignore[attr-defined]


def _patch_orange_book_tables_for_sqlite() -> None:
    """Patch Orange Book + NDC table BigInteger PKs to Integer for SQLite autoincrement.

    SQLite only supports INTEGER PRIMARY KEY autoincrement, not BIGINT.
    T3 established this pattern for NDC tables; we apply the same here.
    """
    tables_to_patch = [
        DrugOrangeBook.__table__,
        DrugPatent.__table__,
        DrugExclusivity.__table__,
    ]
    for table in tables_to_patch:
        if getattr(table, "_sqlite_patched", False):
            continue
        for col in table.columns:
            if isinstance(col.type, BigInteger) and col.primary_key:
                col.type = Integer()
        table._sqlite_patched = True  # type: ignore[attr-defined]


_patch_ingestion_tables_for_sqlite()
_patch_orange_book_tables_for_sqlite()


# ---------------------------------------------------------------------------
# Session-scoped engine + SAVEPOINT session fixtures (LESSON-001)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _engine():
    """Session-scoped in-memory SQLite with schema_translate_map.

    Both shared IngestionRun/IngestionSchedule tables AND NDC + Orange Book
    tables are created. SQLite does not support named schemas, so we strip them.
    """
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

    engine = raw_engine.execution_options(
        schema_translate_map={"shared": None, NDC_SCHEMA: None}
    )

    # Create shared tracking tables
    Base.metadata.create_all(
        engine,
        tables=[IngestionRun.__table__, IngestionSchedule.__table__],
    )
    # Create NDC tables (needed for the cross-ref view test)
    NDCBase.metadata.create_all(engine)
    # Create Orange Book tables
    OrangeBookBase.metadata.create_all(engine)

    yield engine

    OrangeBookBase.metadata.drop_all(engine)
    NDCBase.metadata.drop_all(engine)
    Base.metadata.drop_all(
        engine,
        tables=[IngestionRun.__table__, IngestionSchedule.__table__],
    )
    raw_engine.dispose()


@pytest.fixture
def db_session(_engine) -> Iterator[Session]:
    """SAVEPOINT-based isolated session per LESSON-001.

    Tests that call session.commit() inside service logic are fully isolated —
    all changes roll back at teardown via the outer connection.begin() rollback.
    """
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


# ===========================================================================
# 1. parse_mmm_dd_yyyy — date parser extension (T2's date_parsers.py)
# ===========================================================================


class TestParseMmmDdYyyy:
    """Tests for the new parse_mmm_dd_yyyy function added to date_parsers.py."""

    def test_standard_format(self) -> None:
        assert parse_mmm_dd_yyyy("Jan 22, 1988") == date(1988, 1, 22)

    def test_single_digit_day(self) -> None:
        assert parse_mmm_dd_yyyy("Jan 1, 1982") == date(1982, 1, 1)

    def test_all_months(self) -> None:
        months = [
            ("Jan", 1), ("Feb", 2), ("Mar", 3), ("Apr", 4),
            ("May", 5), ("Jun", 6), ("Jul", 7), ("Aug", 8),
            ("Sep", 9), ("Oct", 10), ("Nov", 11), ("Dec", 12),
        ]
        for abbr, num in months:
            result = parse_mmm_dd_yyyy(f"{abbr} 15, 2025")
            assert result == date(2025, num, 15), f"Failed for {abbr}"

    def test_case_insensitive_month(self) -> None:
        assert parse_mmm_dd_yyyy("JAN 1, 1982") == date(1982, 1, 1)
        assert parse_mmm_dd_yyyy("jan 1, 1982") == date(1982, 1, 1)

    def test_returns_none_for_empty(self) -> None:
        assert parse_mmm_dd_yyyy("") is None
        assert parse_mmm_dd_yyyy(None) is None

    def test_returns_none_for_invalid_month(self) -> None:
        assert parse_mmm_dd_yyyy("Xyz 1, 1982") is None

    def test_returns_none_for_invalid_date(self) -> None:
        assert parse_mmm_dd_yyyy("Feb 30, 2025") is None

    def test_returns_none_for_wrong_format(self) -> None:
        # Should not accept YYYYMMDD or MM/DD/YYYY
        assert parse_mmm_dd_yyyy("19820101") is None
        assert parse_mmm_dd_yyyy("01/01/1982") is None

    def test_trailing_newline_rejected(self) -> None:
        # LESSON-004: fullmatch prevents trailing newline from being accepted
        assert parse_mmm_dd_yyyy("Jan 1, 1982\n") is None


# ===========================================================================
# 2. Helper function unit tests
# ===========================================================================


class TestComputeApplicationNumber:
    """Tests for the application_number computation that creates cross-ref keys."""

    def test_nda_application(self) -> None:
        assert _compute_application_number("N", "019787") == "NDA019787"

    def test_anda_application(self) -> None:
        assert _compute_application_number("A", "020503") == "ANDA020503"

    def test_bla_application(self) -> None:
        assert _compute_application_number("BLA", "103772") == "BLA103772"

    def test_short_appl_no_zero_padded(self) -> None:
        # "5" → "000005"
        assert _compute_application_number("N", "5") == "NDA000005"

    def test_6_digit_no_padding_needed(self) -> None:
        assert _compute_application_number("N", "019777") == "NDA019777"

    def test_empty_appl_type_returns_none(self) -> None:
        assert _compute_application_number("", "019787") is None

    def test_empty_appl_no_returns_none(self) -> None:
        assert _compute_application_number("N", "") is None


class TestParseApprovalDate:
    """Tests for the Approval_Date special-case parser."""

    def test_normal_date(self) -> None:
        d, flag = _parse_approval_date("Jan 22, 1988")
        assert d == date(1988, 1, 22)
        assert flag is False

    def test_approved_prior_to_1982(self) -> None:
        d, flag = _parse_approval_date("Approved Prior to Jan 1, 1982")
        assert d == date(1982, 1, 1)
        assert flag is True

    def test_empty_returns_none_no_flag(self) -> None:
        d, flag = _parse_approval_date("")
        assert d is None
        assert flag is False


class TestSplitDfRoute:
    """Tests for dosage_form;route splitting."""

    def test_splits_on_semicolon(self) -> None:
        df, route = _split_df_route("TABLET;ORAL")
        assert df == "TABLET"
        assert route == "ORAL"

    def test_no_semicolon_returns_all_as_dosage_form(self) -> None:
        df, route = _split_df_route("TABLET")
        assert df == "TABLET"
        assert route is None

    def test_empty_string_returns_none_none(self) -> None:
        df, route = _split_df_route("")
        assert df is None
        assert route is None

    def test_strips_whitespace(self) -> None:
        df, route = _split_df_route(" TABLET ; ORAL ")
        assert df == "TABLET"
        assert route == "ORAL"


class TestYnToBool:
    """Tests for Y/N boolean conversion."""

    def test_y_returns_true(self) -> None:
        assert _yn_to_bool("Y") is True

    def test_n_returns_false(self) -> None:
        assert _yn_to_bool("N") is False

    def test_empty_returns_none(self) -> None:
        assert _yn_to_bool("") is None

    def test_other_returns_none(self) -> None:
        assert _yn_to_bool("X") is None
        assert _yn_to_bool("Maybe") is None

    def test_case_insensitive(self) -> None:
        assert _yn_to_bool("y") is True
        assert _yn_to_bool("n") is False


# ===========================================================================
# 3. Parser integration tests — all 14 fields + split DF/Route
# ===========================================================================


class TestParseProducts:
    """Tests for _parse_products() against sample products.txt."""

    def _load_all(self) -> list[dict]:
        return [r["row"] for r in _parse_products(_SAMPLE_DIR / "products.txt")]

    def test_parse_products_all_14_fields_plus_split_df_route(self) -> None:
        """All 14+ mapped fields must be present and the DF;Route split must work."""
        rows = self._load_all()
        assert len(rows) == 8

        first = rows[0]  # LISINOPRIL PRINIVIL NDA
        assert first["ingredient"] == "LISINOPRIL"
        assert first["dosage_form"] == "TABLET"
        assert first["route"] == "ORAL"
        assert first["trade_name"] == "PRINIVIL"
        assert first["applicant"] == "MSD"
        assert first["strength"] == "5 MG"
        assert first["appl_type"] == "N"
        assert first["appl_no"] == "019777"
        assert first["application_number"] == "NDA019777"
        assert first["product_no"] == "001"
        assert first["te_code"] is None  # empty in sample
        assert first["approval_date"] == date(1988, 1, 22)
        assert first["approved_prior_to_1982"] is False
        assert first["rld"] is True
        assert first["rs"] is True
        assert first["product_type"] == "RX"
        assert first["applicant_full_name"] == "MERCK SHARP DOHME"

    def test_approval_date_prior_to_1982_sets_flag(self) -> None:
        """AMOXIL row has 'Approved Prior to Jan 1, 1982' — must set flag and use 1982-01-01."""
        rows = self._load_all()
        amoxil = next(r for r in rows if r["trade_name"] == "AMOXIL")
        assert amoxil["approval_date"] == date(1982, 1, 1)
        assert amoxil["approved_prior_to_1982"] is True

    def test_application_number_computed_matches_drugs_format(self) -> None:
        """N + 019777 must produce NDA019777, A + 020015 must produce ANDA020015."""
        rows = self._load_all()
        by_appl = {r["appl_no"]: r for r in rows}
        assert by_appl["019777"]["application_number"] == "NDA019777"
        assert by_appl["020015"]["application_number"] == "ANDA020015"
        assert by_appl["103772"]["application_number"] == "BLA103772"

    def test_te_code_nullable_for_original_products(self) -> None:
        """Original NDA products (Prinivil, Lipitor, Amoxil, Advil, Remicade) have no TE code."""
        rows = self._load_all()
        original_ndas = [
            r for r in rows
            if r["appl_type"] in ("N", "BLA") and r["trade_name"] in (
                "PRINIVIL", "LIPITOR", "AMOXIL", "ADVIL", "REMICADE"
            )
        ]
        for row in original_ndas:
            assert row["te_code"] is None, (
                f"Expected te_code=None for {row['trade_name']}, got {row['te_code']}"
            )

    def test_generic_has_te_code(self) -> None:
        """ANDA rows must have TE codes."""
        rows = self._load_all()
        generics = [r for r in rows if r["appl_type"] == "A"]
        for row in generics:
            assert row["te_code"] is not None

    def test_rld_false_for_generic(self) -> None:
        rows = self._load_all()
        mylan = next(r for r in rows if r["applicant"] == "MYLAN")
        assert mylan["rld"] is False

    def test_otc_product_type(self) -> None:
        rows = self._load_all()
        advil = next(r for r in rows if r["trade_name"] == "ADVIL")
        assert advil["product_type"] == "OTC"

    def test_bla_biologic(self) -> None:
        rows = self._load_all()
        remicade = next(r for r in rows if r["trade_name"] == "REMICADE")
        assert remicade["appl_type"] == "BLA"
        assert remicade["application_number"] == "BLA103772"


# ===========================================================================
# 4. Patent parser tests
# ===========================================================================


class TestParsePatents:
    """Tests for _parse_patents() against sample patent.txt."""

    def _load_all(self) -> list[dict]:
        return [r["row"] for r in _parse_patents(_SAMPLE_DIR / "patent.txt")]

    def test_patent_delist_flag_boolean(self) -> None:
        """Patent 5969156 for Lipitor (NDA020702) is delisted — must be True."""
        rows = self._load_all()
        delisted = [r for r in rows if r["delist_flag"] is True]
        assert len(delisted) == 1
        assert delisted[0]["patent_no"] == "5969156"

    def test_non_delisted_flag_is_false(self) -> None:
        rows = self._load_all()
        non_delisted = [r for r in rows if r["patent_no"] == "4374829"]
        assert len(non_delisted) == 1
        assert non_delisted[0]["delist_flag"] is False

    def test_drug_substance_and_product_flags(self) -> None:
        """One patent covers substance only, one covers product only, two cover both."""
        rows = self._load_all()
        # 4374829: substance=Y, product=Y
        p1 = next(r for r in rows if r["patent_no"] == "4374829")
        assert p1["drug_substance_flag"] is True
        assert p1["drug_product_flag"] is True
        # 5273995: substance=Y, product=N
        p2 = next(r for r in rows if r["patent_no"] == "5273995")
        assert p2["drug_substance_flag"] is True
        assert p2["drug_product_flag"] is False
        # 5686104: substance=N, product=Y
        p3 = next(r for r in rows if r["patent_no"] == "5686104")
        assert p3["drug_substance_flag"] is False
        assert p3["drug_product_flag"] is True

    def test_patent_use_code_captured(self) -> None:
        """Patent 5686104 has use code U-1234."""
        rows = self._load_all()
        p = next(r for r in rows if r["patent_no"] == "5686104")
        assert p["patent_use_code"] == "U-1234"

    def test_patent_use_code_null_when_absent(self) -> None:
        rows = self._load_all()
        p = next(r for r in rows if r["patent_no"] == "4374829")
        assert p["patent_use_code"] is None

    def test_patent_expire_date_parsed(self) -> None:
        rows = self._load_all()
        p = next(r for r in rows if r["patent_no"] == "4374829")
        assert p["patent_expire_date"] == date(2005, 1, 22)

    def test_application_number_for_patents(self) -> None:
        rows = self._load_all()
        p = next(r for r in rows if r["patent_no"] == "4374829")
        assert p["application_number"] == "NDA019777"


# ===========================================================================
# 5. Exclusivity parser tests
# ===========================================================================


class TestParseExclusivity:
    """Tests for _parse_exclusivity() against sample exclusivity.txt."""

    def _load_all(self) -> list[dict]:
        return [r["row"] for r in _parse_exclusivity(_SAMPLE_DIR / "exclusivity.txt")]

    def test_exclusivity_code_captured(self) -> None:
        """NCE, ODE, and PED codes all present."""
        rows = self._load_all()
        codes = {r["exclusivity_code"] for r in rows}
        assert "NCE" in codes
        assert "ODE" in codes
        assert "PED" in codes

    def test_exclusivity_date_parsed(self) -> None:
        rows = self._load_all()
        nce = next(r for r in rows if r["exclusivity_code"] == "NCE"
                   and r["appl_no"] == "019777")
        assert nce["exclusivity_date"] == date(1993, 1, 22)

    def test_application_number_for_exclusivity(self) -> None:
        rows = self._load_all()
        remicade_rows = [r for r in rows if r["appl_no"] == "103772"]
        for r in remicade_rows:
            assert r["application_number"] == "BLA103772"


# ===========================================================================
# 6. DB integration tests
# ===========================================================================


class TestOrangeBookDBIntegration:
    """Database round-trip tests using SAVEPOINT-isolated SQLite sessions."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_products(self, db: Session) -> int:
        """Parse sample products.txt and insert all rows; return row count."""
        import asyncio

        from shared.data_ingestion.sources.fda_orange_book import FDAOrangeBookIngester

        records = list(_parse_products(_SAMPLE_DIR / "products.txt"))
        ingester = FDAOrangeBookIngester(db_session=db)
        result = asyncio.run(ingester.load(iter(records)))
        return result.records_inserted

    def _load_patents(self, db: Session, patent_file: Path | None = None) -> int:
        import asyncio

        from shared.data_ingestion.sources.fda_orange_book import FDAOrangeBookIngester

        patent_file = patent_file or (_SAMPLE_DIR / "patent.txt")
        records = list(_parse_patents(patent_file))
        ingester = FDAOrangeBookIngester(db_session=db)
        result = asyncio.run(ingester.load(iter(records)))
        return result.records_inserted

    def _full_load(self, db: Session) -> None:
        """Load all three files through the ingester."""
        import asyncio

        from shared.data_ingestion.sources.fda_orange_book import FDAOrangeBookIngester

        all_records: list[dict] = []
        all_records.extend(_parse_products(_SAMPLE_DIR / "products.txt"))
        all_records.extend(_parse_patents(_SAMPLE_DIR / "patent.txt"))
        all_records.extend(_parse_exclusivity(_SAMPLE_DIR / "exclusivity.txt"))

        ingester = FDAOrangeBookIngester(db_session=db)
        asyncio.run(ingester.load(iter(all_records)))

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_upsert_idempotent(self, db_session: Session) -> None:
        """Loading the same products.txt twice must not double the row count."""
        self._load_products(db_session)
        first_count = db_session.query(DrugOrangeBook).count()
        self._load_products(db_session)
        second_count = db_session.query(DrugOrangeBook).count()
        assert first_count == second_count
        assert first_count == 8  # 8 rows in sample

    def test_patent_and_exclusivity_delete_then_insert(
        self, db_session: Session, tmp_path: Path
    ) -> None:
        """Load 5 patents, then reload with one Lipitor patent removed → 4 total.

        NDA020702 (Lipitor) starts with 3 patents (5273995, 5686104, 5969156).
        The reload removes 5969156 (the delisted one), leaving 2 for that key.
        Overall total: 1 (NDA019777) + 2 (NDA020702) + 1 (BLA103772) = 4.
        """
        # First load — all 5 patents
        self._load_patents(db_session)
        first_count = db_session.query(DrugPatent).count()
        assert first_count == 5

        # Write a reduced patent file — remove 5969156 (delisted Lipitor patent)
        reduced_patent = tmp_path / "patent_reduced.txt"
        original_lines = (_SAMPLE_DIR / "patent.txt").read_text(encoding="latin-1").splitlines()
        # Keep header + all lines except 5969156
        kept_lines = [original_lines[0]] + [
            line for line in original_lines[1:] if "5969156" not in line
        ]
        reduced_patent.write_text("\n".join(kept_lines), encoding="latin-1")

        # Second load with reduced file — must delete-then-reinsert for NDA020702
        self._load_patents(db_session, patent_file=reduced_patent)
        second_count = db_session.query(DrugPatent).count()
        assert second_count == 4

        # NDA020702 now has exactly 2 patents (5969156 removed)
        lipitor_patents = (
            db_session.query(DrugPatent)
            .filter(
                DrugPatent.appl_type == "N",
                DrugPatent.appl_no == "020702",
            )
            .all()
        )
        assert len(lipitor_patents) == 2
        patent_nos = {p.patent_no for p in lipitor_patents}
        assert "5969156" not in patent_nos

    def test_product_round_trip_all_fields(self, db_session: Session) -> None:
        """Products loaded from sample must have correct values in DB."""
        self._load_products(db_session)
        prinivil = (
            db_session.query(DrugOrangeBook)
            .filter(
                DrugOrangeBook.appl_type == "N",
                DrugOrangeBook.appl_no == "019777",
                DrugOrangeBook.product_no == "001",
            )
            .one()
        )
        assert prinivil.ingredient == "LISINOPRIL"
        assert prinivil.dosage_form == "TABLET"
        assert prinivil.route == "ORAL"
        assert prinivil.approval_date == date(1988, 1, 22)
        assert prinivil.approved_prior_to_1982 is False
        assert prinivil.rld is True
        assert prinivil.rs is True
        assert prinivil.application_number == "NDA019777"

    def test_approved_prior_to_1982_db_round_trip(self, db_session: Session) -> None:
        """Amoxil's approved_prior_to_1982 flag must be True in DB and date 1982-01-01."""
        self._load_products(db_session)
        amoxil = (
            db_session.query(DrugOrangeBook)
            .filter(DrugOrangeBook.trade_name == "AMOXIL")
            .one()
        )
        assert amoxil.approved_prior_to_1982 is True
        assert amoxil.approval_date == date(1982, 1, 1)

    def test_cross_ref_view_joins_to_drugs(self, db_session: Session) -> None:
        """Insert a Drug row with application_number='NDA019777' and an Orange Book
        row with the same; assert they can be joined via the application_number column.

        The DDL view v_drug_orange_book is not created in SQLite test DB (SQLite
        requires special handling for CREATE VIEW with schema-qualified names), so
        this test exercises the join logic directly using the ORM.
        """
        # Insert a drug with matching application_number
        drug = Drug(
            product_id="test-ob-drug-001",
            product_ndc="01977700",
            ndc_11="01977700000",
            application_number="NDA019777",
            proprietary_name="PRINIVIL TEST",
        )
        db_session.add(drug)
        db_session.flush()

        # Load orange book products
        self._load_products(db_session)

        # Join via application_number (what the view does)
        ob_row = (
            db_session.query(DrugOrangeBook)
            .filter(DrugOrangeBook.application_number == "NDA019777")
            .one()
        )
        matched_drug = (
            db_session.query(Drug)
            .filter(Drug.application_number == ob_row.application_number)
            .one()
        )
        assert matched_drug.product_id == "test-ob-drug-001"
        assert matched_drug.proprietary_name == "PRINIVIL TEST"
        assert ob_row.ingredient == "LISINOPRIL"

    def test_full_load_all_three_tables(self, db_session: Session) -> None:
        """Full load of all three files populates all three tables."""
        self._full_load(db_session)

        ob_count = db_session.query(DrugOrangeBook).count()
        pat_count = db_session.query(DrugPatent).count()
        exc_count = db_session.query(DrugExclusivity).count()

        assert ob_count == 8
        assert pat_count == 5
        assert exc_count == 4

    def test_exclusivity_codes_in_db(self, db_session: Session) -> None:
        """NCE, ODE, PED codes must appear in drug_exclusivity after load."""
        self._full_load(db_session)
        codes = {
            r.exclusivity_code
            for r in db_session.query(DrugExclusivity).all()
        }
        assert "NCE" in codes
        assert "ODE" in codes
        assert "PED" in codes
