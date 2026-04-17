"""Tests for the ICD-10-CM and HCPCS Level II ingesters (Wave 13).

Covers:
- Parser correctness on hand-built fixtures (ordinal, code, billable flag,
  short vs long descriptions; HCPCS modifiers, continuation rows, null
  sentinel dates).
- Filename → effective_date derivation (annual vs April update for ICD-10,
  quarterly for HCPCS including the plural-file filename variant).
- _choose_latest_filename picks the newest across multiple patterns.
- _aggregate_continuations folds multi-row long descriptions.
- End-to-end load into a SQLite-backed test DB — row counts match the
  fixture, idempotency verified (second run is a no-op).

LESSON-001: SAVEPOINT-based isolation.
LESSON-007: _UUIDString TypeDecorator for SQLite-compatibility on UUID PKs.
LESSON-011: Global reference — no TenantScopedMixin.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import JSON, String, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import TypeDecorator

# ---------------------------------------------------------------------------
# Environment defaults
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
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.data_ingestion.models import IngestionRun, IngestionSchedule  # noqa: E402
from shared.data_ingestion.sources.hcpcs import (  # noqa: E402
    HcpcsIngester,
    _aggregate_continuations,
    _choose_latest_filename as _hcpcs_choose_latest,
    _effective_date_from_filename as _hcpcs_effective_date,
    _parse_date_yyyymmdd,
    _parse_fixed_width_line as _hcpcs_parse_line,
    _publication_quarter_from_date,
)
from shared.data_ingestion.sources.icd10_cm import (  # noqa: E402
    Icd10CmIngester,
    _choose_latest_filename as _icd_choose_latest,
    _effective_date_from_filename as _icd_effective_date,
    _parse_fixed_width_line as _icd_parse_line,
)
from shared.db.base import Base  # noqa: E402
from shared.db.models.hcpcs_codes import HcpcsCode  # noqa: E402
from shared.db.models.icd10_cm_codes import Icd10CmCode  # noqa: E402

# ---------------------------------------------------------------------------
# Sample fixture paths
# ---------------------------------------------------------------------------

_SAMPLE_DIR = Path(__file__).parent / "sample_data"
_ICD_SAMPLE = _SAMPLE_DIR / "icd10_cm" / "icd10cm_order_2026.txt"
_HCPCS_SAMPLE = _SAMPLE_DIR / "hcpcs" / "HCPC_SAMPLE_ANWEB.txt"


# ---------------------------------------------------------------------------
# SQLite compatibility patches (LESSON-007)
# ---------------------------------------------------------------------------


class _UUIDString(TypeDecorator):
    """SQLite-compatible UUID stored as VARCHAR(36). LESSON-007."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        return str(value) if value is not None else None

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:
        return uuid.UUID(str(value)) if value is not None else None


def _patch_tables_for_sqlite() -> None:
    """Patch PG_UUID → _UUIDString, JSONB → JSON, remove gen_random_uuid()."""
    for table in [
        IngestionRun.__table__,
        IngestionSchedule.__table__,
        Icd10CmCode.__table__,
        HcpcsCode.__table__,
    ]:
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


_patch_tables_for_sqlite()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
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

    engine = raw_engine.execution_options(schema_translate_map={"shared": None})

    Base.metadata.create_all(
        engine,
        tables=[
            IngestionRun.__table__,
            IngestionSchedule.__table__,
            Icd10CmCode.__table__,
            HcpcsCode.__table__,
        ],
    )
    yield engine
    Base.metadata.drop_all(
        engine,
        tables=[
            HcpcsCode.__table__,
            Icd10CmCode.__table__,
            IngestionSchedule.__table__,
            IngestionRun.__table__,
        ],
    )
    raw_engine.dispose()


@pytest.fixture
def db_session(_engine) -> Iterator[Session]:
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
# ICD-10-CM unit tests
# ===========================================================================


class TestIcd10CmParser:
    def test_billable_leaf_row(self) -> None:
        line = "00002 A000    1 Cholera due to Vibrio cholerae                                Cholera due to Vibrio cholerae 01, biovar cholerae"
        row = _icd_parse_line(line)
        assert row is not None
        assert row["ordinal_num"] == 2
        assert row["code"] == "A000"
        assert row["is_billable"] is True
        assert row["short_description"].startswith("Cholera due to Vibrio")
        assert "biovar cholerae" in row["long_description"]

    def test_header_parent_row_is_not_billable(self) -> None:
        line = "00001 A00     0 Cholera                                                      Cholera"
        row = _icd_parse_line(line)
        assert row is not None
        assert row["code"] == "A00"
        assert row["is_billable"] is False

    def test_empty_line_returns_none(self) -> None:
        assert _icd_parse_line("") is None
        assert _icd_parse_line("   \n") is None

    def test_malformed_ordinal_returns_none_ordinal(self) -> None:
        line = "XXXXX A000    1 Cholera                                                      Cholera ..."
        row = _icd_parse_line(line)
        assert row is not None
        assert row["ordinal_num"] is None
        # Code is still parsed
        assert row["code"] == "A000"


class TestIcd10CmFilenames:
    def test_annual_filename_maps_to_prior_october(self) -> None:
        assert _icd_effective_date("2026-code-descriptions-tabular-order.zip") == date(2025, 10, 1)

    def test_april_filename_maps_to_april_1(self) -> None:
        assert _icd_effective_date("april-1-2026-code-descriptions-tabular-order.zip") == date(2026, 4, 1)

    def test_unrecognized_filename_raises(self) -> None:
        with pytest.raises(ValueError):
            _icd_effective_date("something-else.zip")

    def test_choose_latest_picks_april_over_annual_same_year(self) -> None:
        hrefs = [
            "/files/zip/2026-code-descriptions-tabular-order.zip",
            "/files/zip/april-1-2026-code-descriptions-tabular-order.zip",
            "/files/zip/2025-code-descriptions-tabular-order.zip",
        ]
        latest = _icd_choose_latest(hrefs)
        assert latest == "april-1-2026-code-descriptions-tabular-order.zip"

    def test_choose_latest_picks_newest_annual_when_no_april(self) -> None:
        hrefs = [
            "/files/zip/2024-code-descriptions-tabular-order.zip",
            "/files/zip/2026-code-descriptions-tabular-order.zip",
            "/files/zip/2025-code-descriptions-tabular-order.zip",
        ]
        latest = _icd_choose_latest(hrefs)
        assert latest == "2026-code-descriptions-tabular-order.zip"

    def test_choose_latest_returns_none_when_no_matches(self) -> None:
        assert _icd_choose_latest(["/files/zip/unrelated.zip"]) is None


class TestIcd10CmLoad:
    """End-to-end: parse sample file + upsert into SQLite."""

    def test_sample_load(self, db_session: Session) -> None:
        ingester = Icd10CmIngester(db_session=db_session, source_csv=_ICD_SAMPLE)
        records = ingester.parse(_ICD_SAMPLE)
        result = asyncio.run(ingester.load(records))
        db_session.commit()

        assert result.status == "completed"
        assert result.records_errored == 0
        assert result.records_processed == 8
        assert result.records_inserted == 8

        # Verify row counts
        rows = db_session.query(Icd10CmCode).all()
        assert len(rows) == 8
        by_code = {r.code: r for r in rows}
        assert "A00" in by_code and by_code["A00"].is_billable is False
        assert "A000" in by_code and by_code["A000"].is_billable is True
        # Effective date derived from filename
        assert all(r.effective_date == date(2025, 10, 1) for r in rows)

    def test_idempotent_reload(self, db_session: Session) -> None:
        """Running the load twice on the same data yields the same row count."""
        ingester = Icd10CmIngester(db_session=db_session, source_csv=_ICD_SAMPLE)
        records = ingester.parse(_ICD_SAMPLE)
        asyncio.run(ingester.load(records))
        first_count = db_session.query(Icd10CmCode).count()

        records_2 = ingester.parse(_ICD_SAMPLE)
        asyncio.run(ingester.load(records_2))
        db_session.commit()
        second_count = db_session.query(Icd10CmCode).count()

        assert first_count == second_count == 8


# ===========================================================================
# HCPCS unit tests
# ===========================================================================


class TestHcpcsParser:
    def test_regular_code_parses(self) -> None:
        # Build a 320-char record for A0021
        line = (
            "A0021"                                                               # code
            "00100"                                                                # seq
            "3"                                                                    # rec id
            + "Ambulance service, outside state per mile".ljust(80)               # long
            + "Outside state ambulance serv".ljust(28)                             # short
            + "00"                                                                 # pricing
            + " " * 6 + " " + " " * 6 + " " * 12 + " " * 8 + " " * 16              # fillers up to 170
            + " " * 10                                                             # statute
            + " " * 3                                                              # lab cert
            + " " * 21                                                             # filler
            + " " * 5                                                              # xref
            + " " * 20                                                             # filler
            + " "                                                                  # coverage col 230
            + " " * 35                                                             # filler to 265
            + "   "                                                                # anesthesia 266-268
            + "20020701"                                                           # added
            + "20020701"                                                           # action eff
            + "00000000"                                                           # term
            + "N"                                                                  # action
            + " " * 27                                                             # filler to 320
        )
        assert len(line) == 320
        row = _hcpcs_parse_line(line)
        assert row is not None
        assert row["code"] == "A0021"
        assert row["is_modifier"] is False
        assert row["long_description_fragment"].startswith("Ambulance service")
        assert row["added_date"] == date(2002, 7, 1)
        assert row["termination_date"] is None  # 00000000 → None
        assert row["action_code"] == "N"

    def test_modifier_row_identified_by_leading_spaces(self) -> None:
        line = (
            "   A1"                                                                # 3 spaces + modifier
            "00100"
            "7"
            + "Dressing for one wound".ljust(80)
            + "Dressing one wound".ljust(28)
            + " " * (320 - 119)
        )
        assert len(line) == 320
        row = _hcpcs_parse_line(line)
        assert row is not None
        assert row["is_modifier"] is True
        assert row["code"] == "A1"

    def test_empty_line_returns_none(self) -> None:
        assert _hcpcs_parse_line("") is None
        assert _hcpcs_parse_line("  ") is None


class TestHcpcsDateHelpers:
    def test_date_parser_valid(self) -> None:
        assert _parse_date_yyyymmdd("20251015") == date(2025, 10, 15)

    def test_date_parser_zero_sentinel_is_none(self) -> None:
        assert _parse_date_yyyymmdd("00000000") is None

    def test_date_parser_empty_is_none(self) -> None:
        assert _parse_date_yyyymmdd("") is None
        assert _parse_date_yyyymmdd("        ") is None

    def test_date_parser_malformed_is_none(self) -> None:
        assert _parse_date_yyyymmdd("2025-01-01") is None
        assert _parse_date_yyyymmdd("20259999") is None


class TestHcpcsQuarterDerivation:
    @pytest.mark.parametrize(
        "effective,expected",
        [
            (date(2026, 1, 1), "2026Q1"),
            (date(2026, 4, 1), "2026Q2"),
            (date(2026, 7, 1), "2026Q3"),
            (date(2026, 10, 1), "2026Q4"),
            (date(2024, 4, 1), "2024Q2"),
        ],
    )
    def test_publication_quarter(self, effective: date, expected: str) -> None:
        assert _publication_quarter_from_date(effective) == expected


class TestHcpcsFilenames:
    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("january-2026-alpha-numeric-hcpcs-file.zip", date(2026, 1, 1)),
            ("april-2026-alpha-numeric-hcpcs-file.zip", date(2026, 4, 1)),
            ("july-2025-alpha-numeric-hcpcs-file.zip", date(2025, 7, 1)),
            ("october-2025-alpha-numeric-hcpcs-file.zip", date(2025, 10, 1)),
            # Plural-file variant (some years CMS used this)
            ("april-2024-alpha-numeric-hcpcs-files.zip", date(2024, 4, 1)),
            ("october-2024-alpha-numeric-hcpcs-files.zip", date(2024, 10, 1)),
        ],
    )
    def test_effective_date_from_filename(self, filename: str, expected: date) -> None:
        assert _hcpcs_effective_date(filename) == expected

    def test_unrecognized_filename_raises(self) -> None:
        with pytest.raises(ValueError):
            _hcpcs_effective_date("not-hcpcs.zip")

    def test_choose_latest_picks_newest_quarter(self) -> None:
        hrefs = [
            "/files/zip/january-2025-alpha-numeric-hcpcs-file.zip",
            "/files/zip/april-2026-alpha-numeric-hcpcs-file.zip",
            "/files/zip/january-2026-alpha-numeric-hcpcs-file.zip",
        ]
        latest = _hcpcs_choose_latest(hrefs)
        assert latest == "april-2026-alpha-numeric-hcpcs-file.zip"

    def test_choose_latest_handles_mixed_plural_singular(self) -> None:
        hrefs = [
            "/files/zip/july-2024-alpha-numeric-hcpcs-files.zip",
            "/files/zip/october-2024-alpha-numeric-hcpcs-file.zip",
        ]
        latest = _hcpcs_choose_latest(hrefs)
        assert latest == "october-2024-alpha-numeric-hcpcs-file.zip"


class TestHcpcsContinuationAggregation:
    def test_aggregates_two_row_long_description(self) -> None:
        rows = [
            {
                "code": "A0080",
                "is_modifier": False,
                "_sequence": 100,
                "long_description_fragment": "Non-emergency transportation, per mile - vehicle provided by volunteer",
                "short_description": "Noninterest escort",
                "pricing_indicator": "00",
                "coverage_code": None,
                "anesthesia_base_units": None,
                "added_date": date(2002, 7, 1),
                "action_effective_date": date(2002, 7, 1),
                "termination_date": None,
                "action_code": "N",
            },
            {
                "code": "A0080",
                "is_modifier": False,
                "_sequence": 200,
                "long_description_fragment": "(individual or organization), with no vested interest",
                "short_description": None,
                "pricing_indicator": None,
                "coverage_code": None,
                "anesthesia_base_units": None,
                "added_date": None,
                "action_effective_date": None,
                "termination_date": None,
                "action_code": None,
            },
        ]
        agg = list(_aggregate_continuations(iter(rows)))
        assert len(agg) == 1
        r = agg[0]
        assert r["code"] == "A0080"
        assert "volunteer (individual or organization), with no vested interest" in r["long_description"]
        # Primary row metadata preserved
        assert r["added_date"] == date(2002, 7, 1)
        assert r["action_code"] == "N"
        # Sentinel fields stripped
        assert "long_description_fragment" not in r
        assert "_sequence" not in r

    def test_distinct_codes_yield_separate_aggregate_rows(self) -> None:
        rows = [
            {"code": "A0021", "is_modifier": False, "_sequence": 100,
             "long_description_fragment": "A", "short_description": None,
             "pricing_indicator": None, "coverage_code": None,
             "anesthesia_base_units": None, "added_date": None,
             "action_effective_date": None, "termination_date": None, "action_code": None},
            {"code": "A0022", "is_modifier": False, "_sequence": 100,
             "long_description_fragment": "B", "short_description": None,
             "pricing_indicator": None, "coverage_code": None,
             "anesthesia_base_units": None, "added_date": None,
             "action_effective_date": None, "termination_date": None, "action_code": None},
        ]
        agg = list(_aggregate_continuations(iter(rows)))
        assert [r["code"] for r in agg] == ["A0021", "A0022"]

    def test_modifier_and_regular_same_code_stay_separate(self) -> None:
        # A1 modifier and A1... regular code would never collide in practice
        # (modifiers are 2-char, regulars are 5-char). But the aggregator
        # uses (code, is_modifier) as the key, so it correctly keeps them apart.
        rows = [
            {"code": "A1", "is_modifier": True, "_sequence": 100,
             "long_description_fragment": "Modifier A1 desc",
             "short_description": None, "pricing_indicator": None,
             "coverage_code": None, "anesthesia_base_units": None,
             "added_date": None, "action_effective_date": None,
             "termination_date": None, "action_code": None},
            {"code": "A1", "is_modifier": False, "_sequence": 100,
             "long_description_fragment": "Regular A1 code desc",
             "short_description": None, "pricing_indicator": None,
             "coverage_code": None, "anesthesia_base_units": None,
             "added_date": None, "action_effective_date": None,
             "termination_date": None, "action_code": None},
        ]
        agg = list(_aggregate_continuations(iter(rows)))
        assert len(agg) == 2
        assert {(r["code"], r["is_modifier"]) for r in agg} == {("A1", True), ("A1", False)}


class TestHcpcsLoad:
    def test_sample_load(self, db_session: Session) -> None:
        # Fixture is named HCPC_SAMPLE_ANWEB.txt; filename-based effective_date
        # won't resolve (it's not a real dated zip), so we pass an override.
        ingester = HcpcsIngester(db_session=db_session, source_csv=_HCPCS_SAMPLE)
        ingester._override_effective_date = date(2026, 4, 1)

        records = ingester.parse(_HCPCS_SAMPLE)
        result = asyncio.run(ingester.load(records))
        db_session.commit()

        assert result.status == "completed"
        assert result.records_errored == 0
        # 6 input rows → 5 distinct (code, is_modifier) after continuation merge
        assert result.records_processed == 5
        assert result.records_inserted == 5

        rows = db_session.query(HcpcsCode).all()
        assert len(rows) == 5
        by_code = {(r.code, r.is_modifier): r for r in rows}
        assert ("A0021", False) in by_code
        assert ("A0080", False) in by_code
        assert ("J7315", False) in by_code
        assert ("A1", True) in by_code
        assert ("Q9949", False) in by_code
        # Continuation aggregated
        assert "vested interest" in by_code[("A0080", False)].long_description
        # Termination date on Q9949 is real (not sentinel)
        assert by_code[("Q9949", False)].termination_date == date(2024, 12, 31)
        # Publication quarter derived from effective_date override
        assert all(r.publication_quarter == "2026Q2" for r in rows)

    def test_idempotent_reload(self, db_session: Session) -> None:
        ingester = HcpcsIngester(db_session=db_session, source_csv=_HCPCS_SAMPLE)
        ingester._override_effective_date = date(2026, 4, 1)

        asyncio.run(ingester.load(ingester.parse(_HCPCS_SAMPLE)))
        first_count = db_session.query(HcpcsCode).count()

        asyncio.run(ingester.load(ingester.parse(_HCPCS_SAMPLE)))
        db_session.commit()
        second_count = db_session.query(HcpcsCode).count()

        assert first_count == second_count == 5

    def test_different_quarter_keeps_prior_rows(self, db_session: Session) -> None:
        """Loading the same codes under a different publication_quarter
        must NOT replace prior rows — the unique key includes quarter."""
        ingester = HcpcsIngester(db_session=db_session, source_csv=_HCPCS_SAMPLE)
        ingester._override_effective_date = date(2026, 1, 1)  # Q1
        asyncio.run(ingester.load(ingester.parse(_HCPCS_SAMPLE)))

        ingester._override_effective_date = date(2026, 4, 1)  # Q2
        asyncio.run(ingester.load(ingester.parse(_HCPCS_SAMPLE)))
        db_session.commit()

        total = db_session.query(HcpcsCode).count()
        assert total == 10  # 5 codes × 2 quarters

        quarters = {r.publication_quarter for r in db_session.query(HcpcsCode).all()}
        assert quarters == {"2026Q1", "2026Q2"}
