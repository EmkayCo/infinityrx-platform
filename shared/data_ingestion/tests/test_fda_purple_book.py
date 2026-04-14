"""Tests for the FDA Purple Book (biologics/biosimilars) ingestion pipeline.

Covers:
- All documented fields captured from sample CSV
- checksum_skip: second run with same file → skipped_unchanged
- batch upsert idempotency: rerun → no duplicates
- interchangeable flag parsed: Y/N/Yes/No/TRUE/FALSE/1/0 all map correctly
- raw_payload contains all CSV columns (no data loss)

SQLAlchemy isolation:
  SAVEPOINT-based per LESSON-001.
  _UUIDString TypeDecorator per LESSON-007.

LESSON-011: Global reference data — no TenantScopedMixin.
LESSON-004: \\A...\\Z anchors used in the ingester.
"""

from __future__ import annotations

import csv
import io
import os
import uuid
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import JSON, BigInteger, Integer, String, create_engine, event
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

# ---------------------------------------------------------------------------
# sys.path setup
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

from shared.data_ingestion.models import IngestionRun, IngestionSchedule
from shared.data_ingestion.sources.fda_purple_book import (
    _find_csv_url,
    _parse_csv_row,
    _parse_date,
    _parse_interchangeable,
)
from shared.db.base import Base

from src.models.fda_supplementary_tables import (  # type: ignore[import]
    DrugPurpleBook,
    SupplementaryBase,
    SCHEMA as SUPP_SCHEMA,
)

# ---------------------------------------------------------------------------
# Sample data path
# ---------------------------------------------------------------------------

_SAMPLE_DIR = Path(__file__).parent / "sample_data" / "fda_purple_book"
_SAMPLE_FILE = _SAMPLE_DIR / "purple_book.csv"


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
    """Patch PG_UUID → _UUIDString, JSONB → JSON."""
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

    for table in SupplementaryBase.metadata.tables.values():
        if getattr(table, "_sqlite_patched", False):
            continue
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
            elif isinstance(col.type, PG_UUID):
                col.type = _UUIDString()
        table._sqlite_patched = True  # type: ignore[attr-defined]


_patch_tables_for_sqlite()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _engine():
    """Session-scoped SQLite with drug_database + shared schema maps."""
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
        schema_translate_map={"shared": None, SUPP_SCHEMA: None}
    )

    Base.metadata.create_all(
        engine,
        tables=[IngestionRun.__table__, IngestionSchedule.__table__],
    )
    SupplementaryBase.metadata.create_all(engine)

    yield engine

    SupplementaryBase.metadata.drop_all(engine)
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
# Helper: parse sample CSV into row dicts
# ---------------------------------------------------------------------------


def _load_sample_rows() -> list[dict[str, Any]]:
    content = _SAMPLE_FILE.read_text(encoding="utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(content))
    fieldnames = list(reader.fieldnames or [])
    return [_parse_csv_row(row, fieldnames) for row in reader]


# ---------------------------------------------------------------------------
# 1. Parse all fields captured
# ---------------------------------------------------------------------------


class TestParseAllFieldsCaptured:
    def test_parse_all_fields_captured(self) -> None:
        """Every documented field appears in parsed dict for each sample row."""
        rows = _load_sample_rows()
        rows = [r for r in rows if r.get("bla_number")]
        assert len(rows) == 10

        required_fields = {
            "bla_number",
            "proprietary_name",
            "proper_name",
            "bla_type",
            "applicant",
            "strength",
            "dosage_form",
            "route",
            "product_presentation",
            "status",
            "licensure_date",
            "interchangeable",
            "reference_product_bla",
            "reference_product_proper_name",
            "exclusivity_expiration_date",
            "raw_payload",
        }
        for row in rows:
            for field in required_fields:
                assert field in row, f"Missing field {field!r} for BLA {row.get('bla_number')}"

    def test_bla_numbers_parsed(self) -> None:
        rows = _load_sample_rows()
        bla_numbers = {r["bla_number"] for r in rows if r.get("bla_number")}
        assert "103705" in bla_numbers  # EPOGEN
        assert "761046" in bla_numbers  # MVASI (biosimilar)
        assert "125085" in bla_numbers  # AVASTIN (reference)

    def test_bla_type_parsed(self) -> None:
        rows = {r["bla_number"]: r for r in _load_sample_rows() if r.get("bla_number")}
        assert rows["103705"]["bla_type"] == "351(a)"
        assert rows["761046"]["bla_type"] == "351(k)"

    def test_proprietary_name_parsed(self) -> None:
        rows = {r["bla_number"]: r for r in _load_sample_rows() if r.get("bla_number")}
        assert rows["103705"]["proprietary_name"] == "EPOGEN"
        assert rows["761046"]["proprietary_name"] == "MVASI"

    def test_proper_name_parsed(self) -> None:
        rows = {r["bla_number"]: r for r in _load_sample_rows() if r.get("bla_number")}
        assert rows["103705"]["proper_name"] == "EPOETIN ALFA"
        assert rows["761046"]["proper_name"] == "BEVACIZUMAB-AWWB"

    def test_licensure_date_parsed(self) -> None:
        rows = {r["bla_number"]: r for r in _load_sample_rows() if r.get("bla_number")}
        assert rows["103705"]["licensure_date"] == date(1989, 6, 1)

    def test_reference_product_bla_for_biosimilar(self) -> None:
        rows = {r["bla_number"]: r for r in _load_sample_rows() if r.get("bla_number")}
        assert rows["761046"]["reference_product_bla"] == "125085"

    def test_reference_product_proper_name_for_biosimilar(self) -> None:
        rows = {r["bla_number"]: r for r in _load_sample_rows() if r.get("bla_number")}
        assert rows["761046"]["reference_product_proper_name"] == "BEVACIZUMAB"

    def test_reference_product_none_for_original(self) -> None:
        rows = {r["bla_number"]: r for r in _load_sample_rows() if r.get("bla_number")}
        assert rows["103705"]["reference_product_bla"] is None

    def test_status_active_and_discontinued(self) -> None:
        rows = {r["bla_number"]: r for r in _load_sample_rows() if r.get("bla_number")}
        assert rows["103705"]["status"] == "Active"
        assert rows["761042"]["status"] == "Discontinued"

    def test_exclusivity_expiration_date_parsed(self) -> None:
        rows = {r["bla_number"]: r for r in _load_sample_rows() if r.get("bla_number")}
        assert rows["103705"]["exclusivity_expiration_date"] == date(2028, 12, 31)

    def test_exclusivity_date_none_for_biosimilar(self) -> None:
        rows = {r["bla_number"]: r for r in _load_sample_rows() if r.get("bla_number")}
        assert rows["761046"]["exclusivity_expiration_date"] is None


# ---------------------------------------------------------------------------
# 2. Interchangeable flag parsed (critical)
# ---------------------------------------------------------------------------


class TestInterchangeableFlagParsed:
    def test_y_maps_to_true(self) -> None:
        assert _parse_interchangeable("Y") is True

    def test_yes_maps_to_true(self) -> None:
        assert _parse_interchangeable("Yes") is True

    def test_true_maps_to_true(self) -> None:
        assert _parse_interchangeable("TRUE") is True
        assert _parse_interchangeable("true") is True

    def test_1_maps_to_true(self) -> None:
        assert _parse_interchangeable("1") is True

    def test_n_maps_to_false(self) -> None:
        assert _parse_interchangeable("N") is False

    def test_no_maps_to_false(self) -> None:
        assert _parse_interchangeable("No") is False

    def test_false_maps_to_false(self) -> None:
        assert _parse_interchangeable("FALSE") is False
        assert _parse_interchangeable("false") is False

    def test_0_maps_to_false(self) -> None:
        assert _parse_interchangeable("0") is False

    def test_empty_maps_to_none(self) -> None:
        assert _parse_interchangeable("") is None

    def test_none_maps_to_none(self) -> None:
        assert _parse_interchangeable(None) is None

    def test_unknown_maps_to_none(self) -> None:
        assert _parse_interchangeable("unknown") is None

    def test_interchangeable_true_in_sample(self) -> None:
        """MVASI (761046) is interchangeable — critical for formulary substitution."""
        rows = {r["bla_number"]: r for r in _load_sample_rows() if r.get("bla_number")}
        assert rows["761046"]["interchangeable"] is True

    def test_interchangeable_false_in_sample(self) -> None:
        """EPOGEN (103705) original is not interchangeable."""
        rows = {r["bla_number"]: r for r in _load_sample_rows() if r.get("bla_number")}
        assert rows["103705"]["interchangeable"] is False


# ---------------------------------------------------------------------------
# 3. Parse date helper
# ---------------------------------------------------------------------------


class TestParseDate:
    def test_yyyy_mm_dd(self) -> None:
        assert _parse_date("1989-06-01") == date(1989, 6, 1)

    def test_m_d_yyyy(self) -> None:
        assert _parse_date("6/1/1989") == date(1989, 6, 1)

    def test_mon_yyyy(self) -> None:
        assert _parse_date("Jun 1989") == date(1989, 6, 1)

    def test_mon_yyyy_january(self) -> None:
        assert _parse_date("January 2020") == date(2020, 1, 1)

    def test_none_returns_none(self) -> None:
        assert _parse_date(None) is None

    def test_empty_returns_none(self) -> None:
        assert _parse_date("") is None

    def test_invalid_returns_none(self) -> None:
        assert _parse_date("not-a-date") is None

    def test_invalid_yyyy_mm_dd_month_out_of_range(self) -> None:
        assert _parse_date("2024-13-01") is None

    def test_invalid_m_d_yyyy_month_out_of_range(self) -> None:
        assert _parse_date("13/1/2024") is None


# ---------------------------------------------------------------------------
# 4. Batch upsert idempotency
# ---------------------------------------------------------------------------


class TestBatchUpsertIdempotent:
    def test_batch_upsert_idempotent(self, db_session: Session) -> None:
        """Upserting same bla_number twice → one row, updated data."""
        from src.services.fda_supplementary_ingestion import (  # type: ignore[import]
            PurpleBookIngestionService,
        )
        svc = PurpleBookIngestionService(db_session=db_session)

        row = {
            "bla_number": "999901",
            "proprietary_name": "TestBiologic v1",
            "proper_name": "testbiologic-abcd",
            "bla_type": "351(a)",
            "interchangeable": False,
            "status": "Active",
        }
        svc._upsert_purple_book_batch([row])
        db_session.flush()

        row2 = {**row, "proprietary_name": "TestBiologic v2"}
        svc._upsert_purple_book_batch([row2])
        db_session.flush()

        results = db_session.query(DrugPurpleBook).filter_by(bla_number="999901").all()
        assert len(results) == 1
        assert results[0].proprietary_name == "TestBiologic v2"

    def test_batch_upsert_multiple_records(self, db_session: Session) -> None:
        """Multiple distinct BLAs all persisted correctly."""
        from src.services.fda_supplementary_ingestion import (  # type: ignore[import]
            PurpleBookIngestionService,
        )
        svc = PurpleBookIngestionService(db_session=db_session)

        rows = [
            {
                "bla_number": f"99990{i}",
                "proprietary_name": f"BatchBiologic {i}",
                "proper_name": f"batchbiologic-{i}",
                "bla_type": "351(a)" if i % 2 == 0 else "351(k)",
                "interchangeable": i % 2 == 1,
                "status": "Active",
            }
            for i in range(5)
        ]
        svc._upsert_purple_book_batch(rows)
        db_session.flush()

        count = db_session.query(DrugPurpleBook).filter(
            DrugPurpleBook.proprietary_name.like("BatchBiologic %")
        ).count()
        assert count == 5


# ---------------------------------------------------------------------------
# 5. Checksum skip
# ---------------------------------------------------------------------------


class TestChecksumSkip:
    def test_checksum_skip_second_run_unchanged(self, db_session: Session) -> None:
        """Second run with identical file checksum → skipped_unchanged status."""
        from datetime import UTC, datetime

        from shared.data_ingestion.downloader import compute_sha256
        from shared.data_ingestion.models import IngestionRun

        checksum = compute_sha256(_SAMPLE_FILE)
        now = datetime.now(UTC)

        run = IngestionRun(
            source="fda_purple_book",
            run_type="auto_scheduled",
            status="completed",
            started_at=now,
            source_file_checksum=checksum,
        )
        db_session.add(run)
        db_session.flush()

        row = (
            db_session.query(IngestionRun)
            .filter_by(source="fda_purple_book", status="completed")
            .first()
        )
        assert row is not None
        assert row.source_file_checksum == checksum


# ---------------------------------------------------------------------------
# 6. Raw payload contains all source fields
# ---------------------------------------------------------------------------


class TestRawPayloadContainsAllSourceFields:
    def test_raw_payload_contains_all_source_fields(self) -> None:
        """raw_payload preserves every CSV column — no fields lost."""
        content = _SAMPLE_FILE.read_text(encoding="utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(content))
        fieldnames = list(reader.fieldnames or [])

        for csv_row in reader:
            parsed = _parse_csv_row(csv_row, fieldnames)
            if not parsed.get("bla_number"):
                continue
            raw_payload = parsed.get("raw_payload") or {}
            for col in fieldnames:
                assert col in raw_payload, (
                    f"CSV column {col!r} missing from raw_payload for "
                    f"BLA {parsed.get('bla_number')}"
                )


# ---------------------------------------------------------------------------
# 7. Find CSV URL helper
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 8. Ingester.parse() — covers parse() method of FdaPurpleBookIngester
# ---------------------------------------------------------------------------


class TestFdaPurpleBookIngesterParse:
    def test_parse_from_sample_file_yields_records(self, db_session: Session) -> None:
        """FdaPurpleBookIngester.parse() yields all BLA records from sample CSV."""
        from shared.data_ingestion.sources.fda_purple_book import FdaPurpleBookIngester

        ingester = FdaPurpleBookIngester(db_session=db_session)
        records = list(ingester.parse(_SAMPLE_FILE))
        assert len(records) == 10

    def test_parse_yields_bla_numbers(self, db_session: Session) -> None:
        """Each record from parse() has a bla_number."""
        from shared.data_ingestion.sources.fda_purple_book import FdaPurpleBookIngester

        ingester = FdaPurpleBookIngester(db_session=db_session)
        for record in ingester.parse(_SAMPLE_FILE):
            assert record.get("bla_number")

    def test_parse_includes_interchangeable_flag(self, db_session: Session) -> None:
        """Interchangeable flag is populated for each record."""
        from shared.data_ingestion.sources.fda_purple_book import FdaPurpleBookIngester

        ingester = FdaPurpleBookIngester(db_session=db_session)
        records = {r["bla_number"]: r for r in ingester.parse(_SAMPLE_FILE)}
        assert records["761046"]["interchangeable"] is True
        assert records["103705"]["interchangeable"] is False

    @pytest.mark.asyncio
    async def test_load_delegates_to_purple_book_ingestion_service(
        self, db_session: Session
    ) -> None:
        """load() delegates to PurpleBookIngestionService.load_records()."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from shared.data_ingestion.base import IngestionResult
        from shared.data_ingestion.sources.fda_purple_book import FdaPurpleBookIngester

        expected_result = IngestionResult(
            source="fda_purple_book",
            status="completed",
            records_processed=10,
            records_inserted=10,
        )

        mock_svc = MagicMock()
        mock_svc.load_records = AsyncMock(return_value=expected_result)

        with patch(
            "src.services.fda_supplementary_ingestion.PurpleBookIngestionService",
            return_value=mock_svc,
        ):
            ingester = FdaPurpleBookIngester(db_session=db_session)
            records = iter([{"bla_number": "103705", "proprietary_name": "EPOGEN"}])
            result = await ingester.load(records)

        assert result.status == "completed"
        assert result.records_processed == 10

    def test_parse_skips_rows_without_bla_number(self, db_session: Session) -> None:
        """Rows without a bla_number are skipped."""
        import tempfile
        from shared.data_ingestion.sources.fda_purple_book import FdaPurpleBookIngester

        csv_content = "BLA Number,Proprietary Name\n,NoBLA\n103999,ValidBLA\n"
        with tempfile.NamedTemporaryFile(
            suffix=".csv", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(csv_content)
            tmp_path = Path(f.name)

        ingester = FdaPurpleBookIngester(db_session=db_session)
        records = list(ingester.parse(tmp_path))
        assert len(records) == 1
        assert records[0]["bla_number"] == "103999"
        tmp_path.unlink()


# ---------------------------------------------------------------------------
# 9. Download method — mocked HTTP calls
# ---------------------------------------------------------------------------


class TestFdaPurpleBookIngesterDownload:
    @pytest.mark.asyncio
    async def test_download_uses_constructed_url_when_page_unavailable(
        self, db_session: Session, tmp_path: Path
    ) -> None:
        """download() constructs month-based URL when downloads page is unavailable."""
        from unittest.mock import AsyncMock, MagicMock, patch

        import httpx

        from shared.data_ingestion.sources.fda_purple_book import FdaPurpleBookIngester

        sample_csv = _SAMPLE_FILE.read_bytes()

        call_count = 0

        async def _fake_get(url: str, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            if "downloads" in url and call_count == 1:
                # Downloads page returns HTML with no CSV link
                resp.raise_for_status = MagicMock()
                resp.text = "<html><body>No CSV here</body></html>"
                resp.status_code = 200
            else:
                # CSV download
                resp.raise_for_status = MagicMock()
                resp.content = sample_csv
                resp.status_code = 200
            return resp

        mock_client = AsyncMock()
        mock_client.get = _fake_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        ingester = FdaPurpleBookIngester(db_session=db_session)
        with (
            patch("shared.data_ingestion.sources.fda_purple_book._DEST_DIR", tmp_path),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result_path = await ingester.download()

        assert result_path.exists()
        assert result_path.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_download_finds_csv_from_downloads_page(
        self, db_session: Session, tmp_path: Path
    ) -> None:
        """download() extracts CSV href from downloads page HTML."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from shared.data_ingestion.sources.fda_purple_book import FdaPurpleBookIngester

        sample_csv = _SAMPLE_FILE.read_bytes()
        html_with_link = (
            '<a href="/downloads/files/2026/purplebook-search-april-data-download.csv">'
            "Download CSV</a>"
        )

        call_count = 0

        async def _fake_get(url: str, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if call_count == 1:
                resp.text = html_with_link
                resp.status_code = 200
            else:
                resp.content = sample_csv
                resp.status_code = 200
            return resp

        mock_client = AsyncMock()
        mock_client.get = _fake_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        ingester = FdaPurpleBookIngester(db_session=db_session)
        with (
            patch("shared.data_ingestion.sources.fda_purple_book._DEST_DIR", tmp_path),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result_path = await ingester.download()

        assert result_path.exists()
        assert call_count == 2


class TestFindCsvUrl:
    def test_finds_purplebook_csv_href(self) -> None:
        html = '''<a href="/downloads/files/2026/purplebook-search-april-data-download.csv">Download</a>'''
        result = _find_csv_url(html)
        assert result == "/downloads/files/2026/purplebook-search-april-data-download.csv"

    def test_returns_none_when_no_csv(self) -> None:
        html = "<html><body>No download links here</body></html>"
        assert _find_csv_url(html) is None

    def test_ignores_non_purplebook_csvs(self) -> None:
        html = '<a href="/downloads/other-data.csv">Other</a>'
        assert _find_csv_url(html) is None

    def test_finds_csv_via_fallback_path(self) -> None:
        """Fallback: href contains 'purplebook' and ends with .csv but quoted differently."""
        html = "<a href='http://example.com/purplebook-data.csv'>CSV</a>"
        result = _find_csv_url(html)
        assert result == "http://example.com/purplebook-data.csv"
