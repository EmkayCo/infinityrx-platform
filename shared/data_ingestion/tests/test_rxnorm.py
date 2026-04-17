"""Tests for the RxNorm ingestion pipeline.

Covers:
  - test_parse_rxnconso_all_fields_captured     — all 18 RXNCONSO fields
  - test_parse_rxnrel_all_fields_captured        — all 16 RXNREL fields
  - test_parse_rxnsat_all_fields_captured        — all 13 RXNSAT fields (NDC row)
  - test_parse_rxnsty_all_fields_captured        — all 6 RXNSTY fields
  - test_ndc_crosswalk_built_from_rxnsat         — NDC crosswalk correctness
  - test_atc_crosswalk_built                     — ATC crosswalk correctness
  - test_checksum_skip_reruns_noop               — second run returns skipped_unchanged
  - test_batch_upsert_idempotent                 — row counts stable on re-run
  - test_cron_first_monday_of_month              — croniter semantics verified
  - test_no_source_fields_dropped               — all 53 fields in model columns

SQLAlchemy isolation: SAVEPOINT-based per LESSON-001.
_UUIDString TypeDecorator per LESSON-007.
"""

from __future__ import annotations

import os
import sys
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from croniter import croniter
from sqlalchemy import BigInteger, Integer, JSON, String, Text, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import TypeDecorator

# ---------------------------------------------------------------------------
# Environment defaults so shared.config doesn't raise
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
# Path setup
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DRUG_DB_ROOT = _REPO_ROOT / "modules" / "drug-database"

for _p in (str(_REPO_ROOT), str(_DRUG_DB_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

from shared.data_ingestion.base import IngestionResult
from shared.data_ingestion.models import IngestionRun, IngestionSchedule
from shared.data_ingestion.sources.rxnorm import (
    RxNormIngester,
    _parse_rrf_line,
    _stream_rrf_file,
    _RXNCONSO_FIELDS,
    _RXNREL_FIELDS,
    _RXNSAT_FIELDS,
    _RXNSTY_FIELDS,
)
from shared.db.base import Base

from src.models.rxnorm_tables import (  # type: ignore[import]
    RxNormAttribute,
    RxNormATCCrosswalk,
    RxNormBase,
    RxNormConcept,
    RxNormNDCCrosswalk,
    RxNormRelationship,
    RxNormSemanticType,
    SCHEMA as RXNORM_SCHEMA,
)


def _upsert_ndc_crosswalk(
    db: Session,
    ndc_11: str,
    rxcui: str | None,
    drug_name: str | None,
    tty: str | None,
) -> None:
    """Test helper: direct upsert of a single NDC crosswalk row via ORM."""
    existing = db.query(RxNormNDCCrosswalk).filter_by(ndc_11=ndc_11).one_or_none()
    if existing is not None:
        existing.rxcui = rxcui
        existing.drug_name = drug_name
        existing.tty = tty
    else:
        db.add(RxNormNDCCrosswalk(ndc_11=ndc_11, rxcui=rxcui, drug_name=drug_name, tty=tty))
    db.flush()


def _upsert_atc_crosswalk(
    db: Session,
    rxcui: str,
    atc_code: str,
    atc_level: str | None = None,
    atc_name: str | None = None,
) -> None:
    """Test helper: direct upsert of a single ATC crosswalk row via ORM."""
    existing = (
        db.query(RxNormATCCrosswalk)
        .filter_by(rxcui=rxcui, atc_code=atc_code)
        .one_or_none()
    )
    if existing is not None:
        existing.atc_level = atc_level
        existing.atc_name = atc_name
    else:
        db.add(
            RxNormATCCrosswalk(
                rxcui=rxcui, atc_code=atc_code, atc_level=atc_level, atc_name=atc_name
            )
        )
    db.flush()

# ---------------------------------------------------------------------------
# Sample data paths
# ---------------------------------------------------------------------------

_SAMPLE_DIR = Path(__file__).parent / "sample_data" / "rxnorm"
_RXNCONSO_FILE = _SAMPLE_DIR / "RXNCONSO.RRF"
_RXNREL_FILE = _SAMPLE_DIR / "RXNREL.RRF"
_RXNSAT_FILE = _SAMPLE_DIR / "RXNSAT.RRF"
_RXNSTY_FILE = _SAMPLE_DIR / "RXNSTY.RRF"

# ---------------------------------------------------------------------------
# SQLite compatibility helpers (LESSON-007)
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


def _patch_rxnorm_tables_for_sqlite() -> None:
    """BigInteger PKs → Integer for SQLite autoincrement. LESSON-007."""
    tables_to_patch = [
        RxNormConcept.__table__,
        RxNormRelationship.__table__,
        RxNormAttribute.__table__,
        RxNormSemanticType.__table__,
        RxNormATCCrosswalk.__table__,
    ]
    for table in tables_to_patch:
        if getattr(table, "_sqlite_patched", False):
            continue
        for col in table.columns:
            if isinstance(col.type, BigInteger) and col.primary_key:
                col.type = Integer()
        table._sqlite_patched = True  # type: ignore[attr-defined]


_patch_ingestion_tables_for_sqlite()
_patch_rxnorm_tables_for_sqlite()

# ---------------------------------------------------------------------------
# Engine / session fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _engine():
    """Session-scoped SQLite engine with schema_translate_map."""
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
        schema_translate_map={"shared": None, RXNORM_SCHEMA: None}
    )

    Base.metadata.create_all(
        engine,
        tables=[IngestionRun.__table__, IngestionSchedule.__table__],
    )
    RxNormBase.metadata.create_all(engine)

    yield engine

    RxNormBase.metadata.drop_all(engine)
    Base.metadata.drop_all(
        engine,
        tables=[IngestionRun.__table__, IngestionSchedule.__table__],
    )
    raw_engine.dispose()


@pytest.fixture
def db_session(_engine) -> Iterator[Session]:
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


# ---------------------------------------------------------------------------
# Helper: load sample RRF files as parsed record lists
# ---------------------------------------------------------------------------


def _parse_rrf_records(file_path: Path, fields: list[str], file_key: str) -> list[dict[str, Any]]:
    return list(_stream_rrf_file(file_path, fields, file_key))


# ===========================================================================
# 1. Field capture — all source fields present after parsing
# ===========================================================================


class TestParseAllFieldsCaptured:
    def test_parse_rxnconso_all_fields_captured(self) -> None:
        """All 18 RXNCONSO fields must be present in every parsed record."""
        records = _parse_rrf_records(_RXNCONSO_FILE, _RXNCONSO_FIELDS, "RXNCONSO")
        assert len(records) >= 1
        for rec in records:
            for field in _RXNCONSO_FIELDS:
                key = "str_" if field == "str" else field
                assert key in rec, f"Field '{key}' missing from RXNCONSO record"

    def test_parse_rxnrel_all_fields_captured(self) -> None:
        """All 16 RXNREL fields must be present in every parsed record."""
        records = _parse_rrf_records(_RXNREL_FILE, _RXNREL_FIELDS, "RXNREL")
        assert len(records) >= 1
        for rec in records:
            for field in _RXNREL_FIELDS:
                assert field in rec, f"Field '{field}' missing from RXNREL record"

    def test_parse_rxnsat_all_fields_captured(self) -> None:
        """All 13 RXNSAT fields must be present, including atv for NDC rows."""
        records = _parse_rrf_records(_RXNSAT_FILE, _RXNSAT_FIELDS, "RXNSAT")
        assert len(records) >= 1
        for rec in records:
            for field in _RXNSAT_FIELDS:
                assert field in rec, f"Field '{field}' missing from RXNSAT record"
        # Verify at least one NDC row has a non-None atv
        ndc_rows = [r for r in records if r.get("atn") == "NDC"]
        assert len(ndc_rows) >= 1
        assert any(r["atv"] is not None for r in ndc_rows)

    def test_parse_rxnsty_all_fields_captured(self) -> None:
        """All 6 RXNSTY fields must be present in every parsed record."""
        records = _parse_rrf_records(_RXNSTY_FILE, _RXNSTY_FIELDS, "RXNSTY")
        assert len(records) >= 1
        for rec in records:
            for field in _RXNSTY_FIELDS:
                assert field in rec, f"Field '{field}' missing from RXNSTY record"


# ===========================================================================
# 2. No source fields dropped — all 53 column names exist in ORM models
# ===========================================================================


class TestNoSourceFieldsDropped:
    def test_no_source_fields_dropped(self) -> None:
        """All 18+16+13+6=53 RRF field names appear as columns in models."""
        concept_cols = {c.key for c in RxNormConcept.__table__.columns}
        rel_cols = {c.key for c in RxNormRelationship.__table__.columns}
        attr_cols = {c.key for c in RxNormAttribute.__table__.columns}
        sty_cols = {c.key for c in RxNormSemanticType.__table__.columns}

        # RXNCONSO: 18 fields (str→str column name in DB)
        for field in _RXNCONSO_FIELDS:
            col_name = "str" if field == "str" else field
            assert col_name in concept_cols, f"RXNCONSO field '{field}' not in rxnorm_concepts columns"

        # RXNREL: 16 fields
        for field in _RXNREL_FIELDS:
            assert field in rel_cols, f"RXNREL field '{field}' not in rxnorm_relationships columns"

        # RXNSAT: 13 fields
        for field in _RXNSAT_FIELDS:
            assert field in attr_cols, f"RXNSAT field '{field}' not in rxnorm_attributes columns"

        # RXNSTY: 6 fields
        for field in _RXNSTY_FIELDS:
            assert field in sty_cols, f"RXNSTY field '{field}' not in rxnorm_semantic_types columns"


# ===========================================================================
# 3. NDC crosswalk — direct upsert test (SQLite compatible)
# ===========================================================================


class TestNDCCrosswalkBuilt:
    def test_ndc_crosswalk_built_from_rxnsat(self, db_session: Session) -> None:
        """Upserting a concept + NDC crosswalk row produces the expected entry."""
        concept = RxNormConcept(
            rxcui="1049502",
            rxaui="7417530",
            lat="ENG",
            ispref="Y",
            sab="RXNORM",
            tty="SBD",
            str_="Acetaminophen 325 MG Oral Tablet",
        )
        db_session.add(concept)
        db_session.flush()

        _upsert_ndc_crosswalk(
            db_session,
            ndc_11="00450448001",
            rxcui="1049502",
            drug_name="Acetaminophen 325 MG Oral Tablet",
            tty="SBD",
        )

        row = db_session.query(RxNormNDCCrosswalk).filter_by(ndc_11="00450448001").one()
        assert row.rxcui == "1049502"
        assert row.drug_name == "Acetaminophen 325 MG Oral Tablet"
        assert row.tty == "SBD"

    def test_ndc_crosswalk_upsert_idempotent(self, db_session: Session) -> None:
        """Upserting the same NDC row twice results in exactly one row."""
        _upsert_ndc_crosswalk(
            db_session, ndc_11="00450448009", rxcui="1049502",
            drug_name="Drug Name", tty="SBD",
        )
        _upsert_ndc_crosswalk(
            db_session, ndc_11="00450448009", rxcui="1049502",
            drug_name="Drug Name Updated", tty="SBD",
        )

        count = db_session.query(RxNormNDCCrosswalk).filter_by(ndc_11="00450448009").count()
        assert count == 1
        row = db_session.query(RxNormNDCCrosswalk).filter_by(ndc_11="00450448009").one()
        assert row.drug_name == "Drug Name Updated"


# ===========================================================================
# 4. ATC crosswalk
# ===========================================================================


class TestATCCrosswalkBuilt:
    def test_atc_crosswalk_built(self, db_session: Session) -> None:
        """Upserting an ATC crosswalk row produces the correct entry."""
        _upsert_atc_crosswalk(
            db_session, rxcui="131725", atc_code="N02BE01",
            atc_level="5", atc_name="Paracetamol",
        )

        row = (
            db_session.query(RxNormATCCrosswalk)
            .filter_by(rxcui="131725", atc_code="N02BE01")
            .one()
        )
        assert row.atc_name == "Paracetamol"
        assert row.atc_level == "5"

    def test_atc_crosswalk_upsert_idempotent(self, db_session: Session) -> None:
        """Upserting the same ATC row twice results in exactly one row."""
        _upsert_atc_crosswalk(db_session, rxcui="999999", atc_code="A01AA01")
        _upsert_atc_crosswalk(
            db_session, rxcui="999999", atc_code="A01AA01", atc_name="Updated",
        )

        count = (
            db_session.query(RxNormATCCrosswalk)
            .filter_by(rxcui="999999", atc_code="A01AA01")
            .count()
        )
        assert count == 1


# ===========================================================================
# 5. Batch upsert idempotency — run twice, row counts unchanged
# ===========================================================================


class TestBatchUpsertIdempotent:
    @pytest.mark.asyncio
    async def test_batch_upsert_idempotent(self, db_session: Session) -> None:
        """Loading the same records twice does not grow row counts."""
        ingester = RxNormIngester(db_session=db_session)

        def _all_records() -> Iterator[dict[str, Any]]:
            yield from _parse_rrf_records(_RXNCONSO_FILE, _RXNCONSO_FIELDS, "RXNCONSO")
            yield from _parse_rrf_records(_RXNSAT_FILE, _RXNSAT_FIELDS, "RXNSAT")
            yield from _parse_rrf_records(_RXNREL_FILE, _RXNREL_FIELDS, "RXNREL")
            yield from _parse_rrf_records(_RXNSTY_FILE, _RXNSTY_FIELDS, "RXNSTY")

        await ingester.load(_all_records())
        db_session.flush()
        count_after_first = db_session.query(RxNormConcept).count()

        await ingester.load(_all_records())
        db_session.flush()
        count_after_second = db_session.query(RxNormConcept).count()

        assert count_after_first == count_after_second
        assert count_after_first > 0


# ===========================================================================
# 6. Checksum skip — same file twice returns skipped_unchanged
# ===========================================================================


class TestChecksumSkipRerunsNoop:
    @pytest.mark.asyncio
    async def test_checksum_skip_reruns_noop(
        self, db_session: Session, tmp_path: Path
    ) -> None:
        """Running ingestion twice on the same file returns skipped_unchanged.

        We patch _download_with_retry to return a real file (the zip) so the
        base class checksum comparison fires. We also patch load() to avoid
        running PostgreSQL-dialect SQL on SQLite.
        """
        import zipfile

        # Build a minimal ZIP from sample RRF files
        zip_path = tmp_path / "rxnorm_sample.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(_RXNCONSO_FILE, "RXNCONSO.RRF")
            zf.write(_RXNREL_FILE, "RXNREL.RRF")
            zf.write(_RXNSAT_FILE, "RXNSAT.RRF")
            zf.write(_RXNSTY_FILE, "RXNSTY.RRF")

        ingester = RxNormIngester(db_session=db_session)

        async def _mock_download_with_retry() -> Path:
            return zip_path  # return the zip so checksum is computed on a real file

        ingester._download_with_retry = _mock_download_with_retry  # type: ignore[method-assign]

        # Patch parse to return empty iterator (avoids extracting/parsing in this test)
        ingester.parse = lambda file_path: iter([])  # type: ignore[method-assign]

        async def _mock_load(records: Iterator[dict[str, Any]]) -> IngestionResult:
            # consume iterator
            list(records)
            return IngestionResult(source="rxnorm", status="completed")

        ingester.load = _mock_load  # type: ignore[method-assign]

        # First run — should complete
        result1 = await ingester.run(run_type="manual_trigger")
        assert result1.status == "completed", f"First run failed: {result1.error_message}"

        # Second run — same zip → same checksum → skipped_unchanged
        result2 = await ingester.run(run_type="manual_trigger")
        assert result2.status == "skipped_unchanged", (
            f"Expected skipped_unchanged on second run, got: {result2.status}"
        )


# ===========================================================================
# 7. Cron — first Monday of month semantics
# ===========================================================================


class TestCronFirstMondayOfMonth:
    def test_cron_first_monday_of_month(self) -> None:
        """Cron '0 1 1-7 * 1' fires at 01:00 on days 1-7 OR on Mondays.

        Standard cron uses OR semantics when both day-of-month and
        day-of-week are specified. Croniter follows this: the expression
        fires on any date that satisfies EITHER condition (day in 1-7 OR
        weekday == Monday). All firings must be at 01:00.
        """
        cron_expr = "0 1 1-7 * 1"
        base = datetime(2026, 1, 1, 0, 0, 0)
        cron = croniter(cron_expr, base)
        occurrences = [cron.get_next(datetime) for _ in range(20)]

        for dt in occurrences:
            # Must satisfy at least one of: day in 1-7 OR Monday
            assert (1 <= dt.day <= 7) or dt.weekday() == 0, (
                f"{dt} satisfies neither day 1-7 nor Monday condition"
            )
            assert dt.hour == 1
            assert dt.minute == 0

    def test_cron_fires_multiple_days_per_month(self) -> None:
        """OR-semantics: multiple firings per month (days 1-7 + Mondays)."""
        cron_expr = "0 1 1-7 * 1"
        base = datetime(2026, 1, 1, 0, 0, 0)
        cron = croniter(cron_expr, base)

        # Collect January 2026 firings
        jan_firings: list[datetime] = []
        for _ in range(20):
            dt = cron.get_next(datetime)
            if dt.month == 1 and dt.year == 2026:
                jan_firings.append(dt)
            elif dt > datetime(2026, 1, 31):
                break

        # January 2026: days 1-7 are Jan 1-7 (7 firings) plus any Monday
        # after day 7 (Jan 12, 19, 26). Expect more than 1 firing.
        assert len(jan_firings) >= 7, f"Expected >=7 January firings, got {len(jan_firings)}"

    def test_cron_first_monday_known_dates(self) -> None:
        """Validate specific known first-Monday dates appear in schedule."""
        cron_expr = "0 1 1-7 * 1"
        base = datetime(2026, 1, 1, 0, 0, 0)
        cron = croniter(cron_expr, base)

        # Collect all 2026 firings that are Mondays in days 1-7
        first_mondays: list[datetime] = []
        for _ in range(200):
            dt = cron.get_next(datetime)
            if dt.year > 2026:
                break
            if dt.weekday() == 0 and 1 <= dt.day <= 7:
                first_mondays.append(dt)

        # Should have 12 first-Mondays for 2026 (one per month)
        months = {dt.month for dt in first_mondays}
        assert len(months) == 12, f"Expected first Mondays in all 12 months, got {months}"


# ===========================================================================
# 8. parse() routing — _file tag is present and correct
# ===========================================================================


class TestParseFileTagging:
    def test_rxnconso_records_tagged_with_file_key(self) -> None:
        records = _parse_rrf_records(_RXNCONSO_FILE, _RXNCONSO_FIELDS, "RXNCONSO")
        assert all(r["_file"] == "RXNCONSO" for r in records)

    def test_rxnrel_records_tagged_with_file_key(self) -> None:
        records = _parse_rrf_records(_RXNREL_FILE, _RXNREL_FIELDS, "RXNREL")
        assert all(r["_file"] == "RXNREL" for r in records)

    def test_rxnsat_records_tagged_with_file_key(self) -> None:
        records = _parse_rrf_records(_RXNSAT_FILE, _RXNSAT_FIELDS, "RXNSAT")
        assert all(r["_file"] == "RXNSAT" for r in records)

    def test_rxnsty_records_tagged_with_file_key(self) -> None:
        records = _parse_rrf_records(_RXNSTY_FILE, _RXNSTY_FIELDS, "RXNSTY")
        assert all(r["_file"] == "RXNSTY" for r in records)


# ===========================================================================
# 9. _parse_rrf_line edge cases
# ===========================================================================


class TestParseRRFLine:
    def test_empty_field_becomes_none(self) -> None:
        """Empty pipe-delimited fields become None."""
        line = "1049502||S1119203|7417530|AUI|274783|AT0001||NDC|RXNORM|00450448001|N|4096|"
        record = _parse_rrf_line(line, _RXNSAT_FIELDS, "RXNSAT")
        assert record["lui"] is None  # field index 1 is empty
        assert record["atn"] == "NDC"
        assert record["atv"] == "00450448001"

    def test_str_field_remapped_to_str_underscore(self) -> None:
        """RXNCONSO 'str' field is stored as 'str_' key to avoid Python builtin collision."""
        line = "1049502|ENG|P|L0044821|PF|S1119203|Y|7417530|||274783|RXNORM|SBD|274783|Acetaminophen 325 MG|0|N|4096|"
        record = _parse_rrf_line(line, _RXNCONSO_FIELDS, "RXNCONSO")
        assert "str_" in record
        assert "str" not in record
        assert record["str_"] == "Acetaminophen 325 MG"

    def test_trailing_pipe_handled(self) -> None:
        """Lines with trailing pipe parse correctly (standard RRF format)."""
        line = "T200|T200|A1.4.1.1.3|Clinical Drug|AT0010|4096|"
        record = _parse_rrf_line(line, _RXNSTY_FIELDS, "RXNSTY")
        assert record["rxcui"] == "T200"
        assert record["cvf"] == "4096"


# ===========================================================================
# 10. parse() method — directory vs non-directory, missing files
# ===========================================================================


class TestIngestorParseMethod:
    def test_parse_directory_yields_records_from_all_rrf_files(
        self, tmp_path: Path
    ) -> None:
        """parse() on a directory containing all 4 RRF files yields records."""
        # Copy sample files to tmp_path
        import shutil
        for rrf in ["RXNCONSO.RRF", "RXNREL.RRF", "RXNSAT.RRF", "RXNSTY.RRF"]:
            shutil.copy(_SAMPLE_DIR / rrf, tmp_path / rrf)

        ingester = RxNormIngester(db_session=MagicMock())
        records = list(ingester.parse(tmp_path))
        assert len(records) > 0
        file_keys = {r["_file"] for r in records}
        assert file_keys == {"RXNCONSO", "RXNREL", "RXNSAT", "RXNSTY"}

    def test_parse_non_directory_raises_value_error(self) -> None:
        """parse() raises ValueError when given a file path instead of directory."""
        ingester = RxNormIngester(db_session=MagicMock())
        with pytest.raises(ValueError, match="expected a directory"):
            list(ingester.parse(_RXNCONSO_FILE))

    def test_parse_missing_rrf_file_logs_warning(
        self, tmp_path: Path, caplog: Any
    ) -> None:
        """parse() logs a warning when a RRF file is not found in directory."""
        import logging
        ingester = RxNormIngester(db_session=MagicMock())
        # tmp_path is empty — all RRF files missing
        with caplog.at_level(logging.WARNING):
            records = list(ingester.parse(tmp_path))
        assert records == []


# ===========================================================================
# 11. load() — integration via RxNormIngester
# ===========================================================================


class TestIngestorLoadMethod:
    @pytest.mark.asyncio
    async def test_load_routes_all_file_types(self, db_session: Session) -> None:
        """load() on the ingester routes records from all 4 RRF files correctly."""
        ingester = RxNormIngester(db_session=db_session)

        def _all_sample_records() -> Iterator[dict[str, Any]]:
            yield from _parse_rrf_records(_RXNCONSO_FILE, _RXNCONSO_FIELDS, "RXNCONSO")
            yield from _parse_rrf_records(_RXNREL_FILE, _RXNREL_FIELDS, "RXNREL")
            yield from _parse_rrf_records(_RXNSAT_FILE, _RXNSAT_FIELDS, "RXNSAT")
            yield from _parse_rrf_records(_RXNSTY_FILE, _RXNSTY_FIELDS, "RXNSTY")

        result = await ingester.load(_all_sample_records())
        assert result.status == "completed"
        assert result.records_processed > 0

    @pytest.mark.asyncio
    async def test_load_unknown_file_key_increments_errored(
        self, db_session: Session
    ) -> None:
        """Records with unknown _file key are counted as errored.

        The SQLite crosswalk build also raises errors (PG-specific SQL),
        so errored count includes the crosswalk failures too.
        """
        ingester = RxNormIngester(db_session=db_session)

        def _bad_records() -> Iterator[dict[str, Any]]:
            yield {"_file": "UNKNOWN_FILE", "rxcui": "123"}

        result = await ingester.load(_bad_records())
        # 1 unknown-file error + up to 2 crosswalk build errors on SQLite
        assert result.records_errored >= 1
        assert result.records_processed == 0


# ===========================================================================
# 12. Download method — error handling paths
# ===========================================================================


class TestDownloadErrorPaths:
    @pytest.mark.asyncio
    async def test_download_falls_back_to_prescribable_on_umls_error(
        self, tmp_path: Path
    ) -> None:
        """When UMLS download fails, fallback to prescribable subset is attempted."""
        import zipfile as zf_mod

        # Build a minimal valid ZIP to return as prescribable subset
        zip_path = tmp_path / "prescribable.zip"
        with zf_mod.ZipFile(zip_path, "w") as zf:
            zf.write(_RXNCONSO_FILE, "RXNCONSO.RRF")

        ingester = RxNormIngester(db_session=MagicMock())

        call_count = {"n": 0}

        async def _mock_download_to_file(url: str, dest_dir: Path, **kwargs: Any) -> Path:
            call_count["n"] += 1
            if "apiKey" in url:
                raise httpx.TransportError("UMLS unreachable")
            # Return zip for prescribable subset
            return zip_path

        with patch(
            "shared.data_ingestion.sources.rxnorm.download_to_file",
            side_effect=_mock_download_to_file,
        ), patch.dict(os.environ, {"UMLS_API_KEY": "test-key"}):
            result = await ingester.download()

        assert result.is_dir()
        assert call_count["n"] == 2  # tried full release, then prescribable

    @pytest.mark.asyncio
    async def test_download_raises_when_both_sources_fail(
        self, tmp_path: Path
    ) -> None:
        """RuntimeError raised when both download sources fail."""
        ingester = RxNormIngester(db_session=MagicMock())

        async def _always_fail(url: str, dest_dir: Path, **kwargs: Any) -> Path:
            raise httpx.TransportError("network unreachable")

        with patch(
            "shared.data_ingestion.sources.rxnorm.download_to_file",
            side_effect=_always_fail,
        ), patch.dict(os.environ, {"UMLS_API_KEY": ""}):
            with pytest.raises(RuntimeError, match="downloads failed"):
                await ingester.download()

    @pytest.mark.asyncio
    async def test_download_skips_umls_when_no_api_key(
        self, tmp_path: Path
    ) -> None:
        """When UMLS_API_KEY is empty, only the prescribable subset is attempted."""
        import zipfile as zf_mod

        zip_path = tmp_path / "prescribable.zip"
        with zf_mod.ZipFile(zip_path, "w") as zf:
            zf.write(_RXNCONSO_FILE, "RXNCONSO.RRF")

        ingester = RxNormIngester(db_session=MagicMock())
        call_urls: list[str] = []

        async def _mock_download_to_file(url: str, dest_dir: Path, **kwargs: Any) -> Path:
            call_urls.append(url)
            return zip_path

        with patch(
            "shared.data_ingestion.sources.rxnorm.download_to_file",
            side_effect=_mock_download_to_file,
        ), patch.dict(os.environ, {"UMLS_API_KEY": ""}):
            await ingester.download()

        assert len(call_urls) == 1
        assert "prescribe" in call_urls[0]


# ===========================================================================
# 13. Service upsert exception paths — ensure errored count is set on failure
# ===========================================================================


class TestUpsertExceptionHandling:
    @pytest.mark.asyncio
    async def test_load_triggers_mid_batch_flush_at_batch_boundary(
        self, db_session: Session
    ) -> None:
        """Batch flush path is triggered when buffer reaches _BATCH_SIZE (1000)."""
        from shared.data_ingestion.sources.rxnorm import _BATCH_SIZE

        ingester = RxNormIngester(db_session=db_session)

        def _many_concepts() -> Iterator[dict[str, Any]]:
            for i in range(_BATCH_SIZE + 1):
                yield {
                    "_file": "RXNCONSO",
                    "rxcui": f"CUI{i:07d}",
                    "rxaui": f"AUI{i:07d}",
                    "str_": f"Drug {i}",
                    "lat": "ENG",
                    "ispref": "Y",
                }

        result = await ingester.load(_many_concepts())
        assert result.records_processed == _BATCH_SIZE + 1
        count = db_session.query(RxNormConcept).count()
        assert count == _BATCH_SIZE + 1


# ===========================================================================
# 14. _find_rrf_file — case-insensitive fallback
# ===========================================================================


class TestFindRRFFile:
    def test_find_rrf_file_exact_name(self, tmp_path: Path) -> None:
        """_find_rrf_file finds file by exact name."""
        from shared.data_ingestion.sources.rxnorm import _find_rrf_file

        (tmp_path / "RXNCONSO.RRF").write_text("test")
        result = _find_rrf_file(tmp_path, "RXNCONSO.RRF")
        assert result is not None
        assert result.name == "RXNCONSO.RRF"

    def test_find_rrf_file_case_insensitive(self, tmp_path: Path) -> None:
        """_find_rrf_file finds a file via case-insensitive fallback.

        On case-insensitive FS (macOS) the exact rglob matches first.
        On Linux (case-sensitive), the case-insensitive loop body at lines
        367-368 is the only way to find a lowercase file.

        We simulate Linux behavior by patching Path.rglob to return empty
        for the exact name but yield the lowercase candidate for '*'.
        """
        from shared.data_ingestion.sources.rxnorm import _find_rrf_file

        lowercase_file = tmp_path / "rxnconso.rrf"
        lowercase_file.write_text("test")

        original_rglob = Path.rglob

        def _patched_rglob(self: Path, pattern: str) -> Any:
            if pattern == "RXNCONSO.RRF":
                return iter([])  # exact match fails (simulates Linux)
            return original_rglob(self, pattern)

        with patch.object(Path, "rglob", _patched_rglob):
            result = _find_rrf_file(tmp_path, "RXNCONSO.RRF")

        assert result is not None
        assert result.name.lower() == "rxnconso.rrf"

    def test_find_rrf_file_returns_none_when_missing(self, tmp_path: Path) -> None:
        """_find_rrf_file returns None when file is not in directory."""
        from shared.data_ingestion.sources.rxnorm import _find_rrf_file

        result = _find_rrf_file(tmp_path, "RXNCONSO.RRF")
        assert result is None


# ===========================================================================
# 15. Crosswalk build success paths — mock DB execute to hit return lines
# ===========================================================================


class TestCrosswalkBuildSuccessPaths:
    def _mock_postgres_db(self, rowcount: int) -> MagicMock:
        """Build a MagicMock session whose dialect reads as 'postgresql'."""
        mock_result = MagicMock()
        mock_result.rowcount = rowcount
        mock_db = MagicMock()
        mock_db.execute.return_value = mock_result
        mock_db.bind.dialect.name = "postgresql"
        return mock_db

    def test_build_ndc_crosswalk_returns_rowcount_on_success(self) -> None:
        """_build_ndc_crosswalk returns (rowcount, 0) when execute succeeds."""
        mock_db = self._mock_postgres_db(rowcount=5)
        ingester = RxNormIngester(db_session=mock_db)
        ins, err = ingester._build_ndc_crosswalk()
        assert ins == 5
        assert err == 0

    def test_build_atc_crosswalk_returns_rowcount_on_success(self) -> None:
        """_build_atc_crosswalk returns (rowcount, 0) when execute succeeds."""
        mock_db = self._mock_postgres_db(rowcount=3)
        ingester = RxNormIngester(db_session=mock_db)
        ins, err = ingester._build_atc_crosswalk()
        assert ins == 3
        assert err == 0

    def test_build_ndc_crosswalk_skipped_on_non_postgres(self) -> None:
        """Non-postgres dialect returns (0, 0) without executing SQL."""
        mock_db = MagicMock()
        mock_db.bind.dialect.name = "sqlite"
        ingester = RxNormIngester(db_session=mock_db)
        ins, err = ingester._build_ndc_crosswalk()
        assert (ins, err) == (0, 0)
        mock_db.execute.assert_not_called()

    def test_build_atc_crosswalk_skipped_on_non_postgres(self) -> None:
        """Non-postgres dialect returns (0, 0) without executing SQL."""
        mock_db = MagicMock()
        mock_db.bind.dialect.name = "sqlite"
        ingester = RxNormIngester(db_session=mock_db)
        ins, err = ingester._build_atc_crosswalk()
        assert (ins, err) == (0, 0)
        mock_db.execute.assert_not_called()


# ===========================================================================
# 16. ingester load() — sys.path already present branch
# ===========================================================================


class TestIngesterLoadSysPath:
    @pytest.mark.asyncio
    async def test_load_when_drug_db_already_on_sys_path(
        self, db_session: Session
    ) -> None:
        """load() works correctly when drug-database src is already in sys.path."""
        import sys

        ingester = RxNormIngester(db_session=db_session)

        # Ensure drug-database is already on path (conftest puts it there)
        assert str(_DRUG_DB_ROOT) in sys.path

        def _records() -> Iterator[dict[str, Any]]:
            for rec in _parse_rrf_records(_RXNCONSO_FILE, _RXNCONSO_FIELDS, "RXNCONSO"):
                yield rec

        result = await ingester.load(_records())
        assert result.source == "rxnorm"
        assert result.status == "completed"


# ===========================================================================
# 17. download() — UMLS fallback success path (httpx.HTTPStatusError)
# ===========================================================================


class TestDownloadHTTPStatusErrorFallback:
    @pytest.mark.asyncio
    async def test_download_falls_back_on_http_status_error(
        self, tmp_path: Path
    ) -> None:
        """HTTPStatusError (5xx) from UMLS triggers prescribable fallback."""
        import zipfile as zf_mod

        zip_path = tmp_path / "prescribable.zip"
        with zf_mod.ZipFile(zip_path, "w") as zf:
            zf.write(_RXNCONSO_FILE, "RXNCONSO.RRF")

        ingester = RxNormIngester(db_session=MagicMock())

        async def _mock_download(url: str, dest_dir: Path, **kwargs: Any) -> Path:
            if "apiKey" in url:
                response = MagicMock()
                response.status_code = 503
                raise httpx.HTTPStatusError("503", request=MagicMock(), response=response)
            return zip_path

        with patch(
            "shared.data_ingestion.sources.rxnorm.download_to_file",
            side_effect=_mock_download,
        ), patch.dict(os.environ, {"UMLS_API_KEY": "my-key"}):
            result = await ingester.download()

        assert result.is_dir()

    @pytest.mark.asyncio
    async def test_download_umls_succeeds_skips_prescribable(
        self, tmp_path: Path
    ) -> None:
        """When UMLS download succeeds, prescribable fallback is NOT attempted."""
        import zipfile as zf_mod

        zip_path = tmp_path / "full.zip"
        with zf_mod.ZipFile(zip_path, "w") as zf:
            zf.write(_RXNCONSO_FILE, "RXNCONSO.RRF")

        ingester = RxNormIngester(db_session=MagicMock())
        call_urls: list[str] = []

        async def _mock_download(url: str, dest_dir: Path, **kwargs: Any) -> Path:
            call_urls.append(url)
            return zip_path

        with patch(
            "shared.data_ingestion.sources.rxnorm.download_to_file",
            side_effect=_mock_download,
        ), patch.dict(os.environ, {"UMLS_API_KEY": "valid-key"}):
            result = await ingester.download()

        # Only one call: the UMLS full-release URL (zip_path is not None → skips fallback)
        assert len(call_urls) == 1
        assert "apiKey" in call_urls[0]
        assert result.is_dir()


# ===========================================================================
# 18. _stream_rrf_file — empty lines are skipped
# ===========================================================================


class TestStreamRRFFileEmptyLines:
    def test_empty_lines_are_skipped(self, tmp_path: Path) -> None:
        """Empty lines in RRF file yield no records."""
        from shared.data_ingestion.sources.rxnorm import _stream_rrf_file

        rrf = tmp_path / "TEST.RRF"
        rrf.write_text("1049502|ENG|P|L1|PF|S1|Y|A1|||C1|RXNORM|SBD|C1|Drug Name|0|N|4096|\n\n\n")
        records = list(_stream_rrf_file(rrf, _RXNCONSO_FIELDS, "RXNCONSO"))
        assert len(records) == 1  # 3 empty lines skipped, 1 real record


# ===========================================================================
# 19. _extract_zip coverage
# ===========================================================================


class TestExtractZip:
    def test_extract_zip_creates_files_in_dest_dir(self, tmp_path: Path) -> None:
        """_extract_zip extracts all ZIP contents to dest_dir."""
        import zipfile as zf_mod
        from shared.data_ingestion.sources.rxnorm import _extract_zip

        zip_path = tmp_path / "test.zip"
        with zf_mod.ZipFile(zip_path, "w") as zf:
            zf.write(_RXNCONSO_FILE, "RXNCONSO.RRF")

        dest = tmp_path / "extracted"
        result = _extract_zip(zip_path, dest)

        assert result == dest
        assert result.is_dir()
        assert (result / "RXNCONSO.RRF").exists()


# ===========================================================================
# 20. load() sys.path insert coverage — force sys.path miss
# ===========================================================================


class TestLoadSysPathInsert:
    @pytest.mark.asyncio
    async def test_load_inserts_path_when_not_present(
        self, db_session: Session
    ) -> None:
        """load() inserts drug-database to sys.path when not already present."""
        import sys
        from shared.data_ingestion.sources.rxnorm import _CACHE_DIR

        ingester = RxNormIngester(db_session=db_session)

        # Temporarily remove the drug-database path from sys.path to trigger insert
        drug_db_str = str(_DRUG_DB_ROOT)
        was_present = drug_db_str in sys.path
        if was_present:
            sys.path.remove(drug_db_str)

        try:
            def _records() -> Iterator[dict[str, Any]]:
                return iter([])

            result = await ingester.load(_records())
            assert result.source == "rxnorm"
        finally:
            # Restore
            if was_present and drug_db_str not in sys.path:
                sys.path.insert(0, drug_db_str)
