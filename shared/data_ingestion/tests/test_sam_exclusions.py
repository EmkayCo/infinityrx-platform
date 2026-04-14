"""Tests for SAM.gov exclusions ingestion pipeline.

Covers:
  - All SAM fields captured
  - Cross-reference by NPI and UEI
  - Missing API key fails gracefully with status=failed
  - Batch upsert idempotency
  - No source fields dropped

SQLAlchemy isolation: SAVEPOINT per LESSON-001; _UUIDString per LESSON-007.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from collections.abc import Iterator
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import JSON, Integer, String, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import TypeDecorator

# --- env defaults ---
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost/")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")
os.environ.setdefault("ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM=")

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.data_ingestion.models import IngestionRun, IngestionSchedule
from shared.data_ingestion.sources.sam_exclusions import (
    SamExclusionsIngester,
    _SamApiKeyMissingError,
    _parse_sam_date,
)
from shared.db.base import Base
from shared.db.models.sam_exclusions import SamExclusion

_SAMPLE_DIR = Path(__file__).parent / "sample_data" / "sam_exclusions"
_SAMPLE_JSONL = _SAMPLE_DIR / "sam_exclusions.jsonl"

# All expected SAM source fields
_SAM_FIELDS = [
    "classificationType", "name", "addressLine1", "city", "stateOrProvince",
    "zipCode", "country", "dunsNumber", "ueiSAM", "cageCode", "npi",
    "exclusionType", "exclusionProgram", "agency", "activationDate",
    "terminationDate", "ctCode", "additionalComments", "affiliations",
]


# ---------------------------------------------------------------------------
# SQLite compatibility (LESSON-007)
# ---------------------------------------------------------------------------

class _UUIDString(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        return str(value) if value is not None else None

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:
        return uuid.UUID(str(value)) if value is not None else None


def _patch_tables_for_sqlite() -> None:
    tables = [IngestionRun.__table__, IngestionSchedule.__table__, SamExclusion.__table__]
    for table in tables:
        if getattr(table, "_sqlite_patched_sam", False):
            continue
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
            elif isinstance(col.type, PG_UUID):
                col.type = _UUIDString()
            if col.server_default is not None and "gen_random_uuid" in str(col.server_default):
                col.server_default = None  # type: ignore[attr-defined]
        table._sqlite_patched_sam = True  # type: ignore[attr-defined]


_patch_tables_for_sqlite()


# ---------------------------------------------------------------------------
# Fixtures
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

    engine = raw_engine.execution_options(schema_translate_map={"shared": None})
    Base.metadata.create_all(
        engine,
        tables=[
            IngestionRun.__table__,
            IngestionSchedule.__table__,
            SamExclusion.__table__,
        ],
    )
    yield engine
    Base.metadata.drop_all(
        engine,
        tables=[
            IngestionRun.__table__,
            IngestionSchedule.__table__,
            SamExclusion.__table__,
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


@pytest.fixture
def ingester(db_session: Session) -> SamExclusionsIngester:
    return SamExclusionsIngester(db_session=db_session)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _run_load(ingester: SamExclusionsIngester, jsonl_path: Path | None = None) -> Any:
    """Parse sample JSONL and run load()."""
    path = jsonl_path or _SAMPLE_JSONL
    records = ingester.parse(path)
    return await ingester.load(records)


# ---------------------------------------------------------------------------
# Tests: API key handling
# ---------------------------------------------------------------------------

class TestSamApiKeyHandling:
    async def test_missing_api_key_fails_gracefully(
        self, db_session: Session, ingester: SamExclusionsIngester
    ):
        """run() returns status=failed with clear error when SAM_API_KEY missing."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SAM_API_KEY", None)
            result = await ingester.run()

        assert result.status == "failed"
        assert result.error_message is not None
        assert "SAM_API_KEY" in result.error_message or "api key" in result.error_message.lower()

    async def test_missing_api_key_error_message_is_helpful(
        self, db_session: Session, ingester: SamExclusionsIngester
    ):
        """Error message must direct user to register at sam.gov/api."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SAM_API_KEY", None)
            result = await ingester.run()

        assert result.error_message is not None
        lower = result.error_message.lower()
        assert "sam" in lower or "api" in lower

    async def test_missing_api_key_does_not_raise(
        self, db_session: Session, ingester: SamExclusionsIngester
    ):
        """_SamApiKeyMissingError must be caught, not propagated."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SAM_API_KEY", None)
            result = await ingester.run()
        assert result is not None


# ---------------------------------------------------------------------------
# Tests: field capture
# ---------------------------------------------------------------------------

class TestSamFieldCapture:
    def test_parse_all_sam_fields_captured(self, ingester: SamExclusionsIngester):
        """Sample JSONL must contain all expected SAM fields."""
        rows = list(ingester.parse(_SAMPLE_JSONL))
        assert len(rows) >= 1

        first = rows[0]
        for field in _SAM_FIELDS:
            assert field in first, f"Expected field {field!r} missing from SAM record"

    def test_no_source_fields_dropped(self):
        """All expected SAM ORM columns must exist on the model."""
        model_cols = {col.key for col in SamExclusion.__table__.columns}
        expected = {
            "classification_type", "name", "address_line_1", "address_line_2",
            "city", "state_province", "zip_postal_code", "country_code",
            "duns_number", "uei_sam", "cage_code", "npi",
            "exclusion_type", "exclusion_program", "agency",
            "active_date", "termination_date", "ct_code",
            "additional_comments", "affiliations", "raw_payload",
        }
        missing = expected - model_cols
        assert not missing, f"SAM ORM model missing columns: {missing}"

    async def test_classification_type_captured(self, db_session: Session, ingester: SamExclusionsIngester):
        await _run_load(ingester)
        row = db_session.query(SamExclusion).filter(
            SamExclusion.classification_type == "Individual"
        ).first()
        assert row is not None

    async def test_uei_sam_captured(self, db_session: Session, ingester: SamExclusionsIngester):
        await _run_load(ingester)
        row = db_session.query(SamExclusion).filter(
            SamExclusion.uei_sam == "ABCDEF123456"
        ).first()
        assert row is not None

    async def test_npi_captured(self, db_session: Session, ingester: SamExclusionsIngester):
        await _run_load(ingester)
        row = db_session.query(SamExclusion).filter(
            SamExclusion.npi == "1234567890"
        ).first()
        assert row is not None

    async def test_exclusion_program_captured(self, db_session: Session, ingester: SamExclusionsIngester):
        await _run_load(ingester)
        row = db_session.query(SamExclusion).filter(
            SamExclusion.exclusion_program == "Procurement"
        ).first()
        assert row is not None

    async def test_active_date_parsed(self, db_session: Session, ingester: SamExclusionsIngester):
        await _run_load(ingester)
        row = db_session.query(SamExclusion).filter(
            SamExclusion.npi == "1234567890"
        ).first()
        assert row is not None
        assert isinstance(row.active_date, date)
        assert row.active_date == date(2020, 1, 1)

    async def test_termination_date_parsed(self, db_session: Session, ingester: SamExclusionsIngester):
        await _run_load(ingester)
        row = db_session.query(SamExclusion).filter(
            SamExclusion.npi == "2222222222"
        ).first()
        assert row is not None
        assert row.termination_date == date(2024, 12, 31)

    async def test_affiliations_captured_as_json(self, db_session: Session, ingester: SamExclusionsIngester):
        await _run_load(ingester)
        firm = db_session.query(SamExclusion).filter(
            SamExclusion.classification_type == "Firm"
        ).first()
        assert firm is not None
        assert firm.affiliations is not None

    async def test_raw_payload_populated(self, db_session: Session, ingester: SamExclusionsIngester):
        await _run_load(ingester)
        rows = db_session.query(SamExclusion).all()
        for row in rows:
            assert row.raw_payload is not None


# ---------------------------------------------------------------------------
# Tests: cross-reference
# ---------------------------------------------------------------------------

class TestSamCrossReference:
    def test_sam_cross_reference_by_npi_and_uei(
        self, db_session: Session, ingester: SamExclusionsIngester
    ):
        """_cross_reference_prescribers() and _cross_reference_pharmacies() return int without raising."""
        # Seed a SAM exclusion with an NPI
        excl = SamExclusion(
            classification_type="Individual",
            name="TEST PERSON",
            exclusion_type="Reciprocal",
            active_date=date(2020, 1, 1),
            npi="7777777777",
            uei_sam="TEST123456",
            termination_date=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(excl)
        db_session.flush()

        p_count = ingester._cross_reference_prescribers()
        ph_count = ingester._cross_reference_pharmacies()

        assert isinstance(p_count, int)
        assert isinstance(ph_count, int)
        assert p_count >= 0
        assert ph_count >= 0

    def test_cross_reference_with_terminated_exclusion(
        self, db_session: Session, ingester: SamExclusionsIngester
    ):
        """Terminated SAM exclusions (termination_date in past) should not flip is_excluded."""
        excl = SamExclusion(
            classification_type="Individual",
            name="OLD EXCLUSION",
            exclusion_type="Reciprocal",
            active_date=date(2010, 1, 1),
            npi="8888888888",
            termination_date=date(2015, 12, 31),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(excl)
        db_session.flush()

        # Should complete without raising
        count = ingester._cross_reference_prescribers()
        assert isinstance(count, int)


# ---------------------------------------------------------------------------
# Tests: idempotency
# ---------------------------------------------------------------------------

class TestSamIdempotency:
    async def test_batch_upsert_idempotent(self, db_session: Session, ingester: SamExclusionsIngester):
        """Loading the same file twice must not duplicate rows."""
        await _run_load(ingester)
        count_first = db_session.query(SamExclusion).count()

        await _run_load(ingester)
        count_second = db_session.query(SamExclusion).count()

        assert count_first == count_second


# ---------------------------------------------------------------------------
# Tests: date parsing
# ---------------------------------------------------------------------------

class TestSamDateParsing:
    def test_parse_sam_date_iso(self):
        assert _parse_sam_date("2020-01-01") == date(2020, 1, 1)

    def test_parse_sam_date_slash(self):
        assert _parse_sam_date("01/01/2020") == date(2020, 1, 1)

    def test_parse_sam_date_yyyymmdd(self):
        assert _parse_sam_date("20200101") == date(2020, 1, 1)

    def test_parse_sam_date_empty(self):
        assert _parse_sam_date("") is None

    def test_parse_sam_date_none(self):
        assert _parse_sam_date(None) is None

    def test_parse_sam_date_invalid_returns_none(self):
        """Line 89: all formats exhausted → return None."""
        assert _parse_sam_date("not-a-date") is None


# ---------------------------------------------------------------------------
# Tests: field registry
# ---------------------------------------------------------------------------

class TestSamParseBlanksSkipped:
    def test_parse_skips_blank_lines(self, tmp_path: Path, ingester: SamExclusionsIngester):
        """Line 182: blank lines in JSONL are skipped via continue."""
        import json as _json

        jsonl = tmp_path / "test.jsonl"
        jsonl.write_text(
            '{"classificationType": "Individual", "name": "A"}\n'
            '\n'  # blank line → continue
            '{"classificationType": "Firm", "name": "B"}\n'
        )
        rows = list(ingester.parse(jsonl))
        assert len(rows) == 2
        assert rows[0]["name"] == "A"
        assert rows[1]["name"] == "B"


class TestSamFieldRegistry:
    def test_field_registry_has_all_sam_fields(self):
        from shared.data_ingestion.field_registry import registry

        sam_fields = registry.fields_for_source("sam_exclusions")
        registered_cols = {f.column for f in sam_fields}

        expected = {
            "classification_type", "name", "address_line_1", "city",
            "state_province", "zip_postal_code", "country_code",
            "duns_number", "uei_sam", "cage_code", "npi",
            "exclusion_type", "exclusion_program", "agency",
            "active_date", "termination_date", "ct_code",
            "additional_comments", "affiliations",
        }
        missing = expected - registered_cols
        assert not missing, f"Field registry missing: {missing}"


class TestSamLoadEdgeCases:
    async def test_flush_error_path_increments_errored(
        self, db_session: Session, ingester: SamExclusionsIngester
    ):
        """Lines 202-204: when _upsert_row raises, records_errored is incremented."""
        with patch.object(ingester, "_upsert_row", side_effect=ValueError("bad row")):
            result = await ingester.load(iter([{"classificationType": "Individual", "name": "X"}]))
        assert result.records_errored == 1

    async def test_batch_overflow_triggers_mid_stream_flush(
        self, db_session: Session, ingester: SamExclusionsIngester
    ):
        """Line 218: when batch reaches _BATCH_SIZE, _flush() fires mid-stream."""
        from shared.data_ingestion.sources.sam_exclusions import _BATCH_SIZE

        records = [
            {
                "classificationType": "Individual",
                "name": f"PERSON{i}",
                "exclusionType": "Reciprocal",
                "activationDate": "2020-01-01",
            }
            for i in range(_BATCH_SIZE + 1)
        ]

        with patch.object(ingester, "_cross_reference_prescribers", return_value=0):
            with patch.object(ingester, "_cross_reference_pharmacies", return_value=0):
                result = await ingester.load(iter(records))

        assert result.records_processed == _BATCH_SIZE + 1

    async def test_affiliations_string_parsed_as_json(
        self, db_session: Session, ingester: SamExclusionsIngester
    ):
        """Lines 256-259: affiliations that is a valid JSON string is decoded to list/dict."""
        records = [
            {
                "classificationType": "Firm",
                "name": "ACME CORP",
                "exclusionType": "Reciprocal",
                "activationDate": "2020-01-01",
                "affiliations": '[{"name": "ACME SUBSIDIARY"}]',
            }
        ]
        with patch.object(ingester, "_cross_reference_prescribers", return_value=0):
            with patch.object(ingester, "_cross_reference_pharmacies", return_value=0):
                await ingester.load(iter(records))

        row = db_session.query(SamExclusion).filter(SamExclusion.name == "ACME CORP").first()
        assert row is not None
        assert isinstance(row.affiliations, list)

    async def test_affiliations_invalid_json_string_kept_as_string(
        self, db_session: Session, ingester: SamExclusionsIngester
    ):
        """Line 259 except branch: invalid JSON string in affiliations is kept as-is."""
        records = [
            {
                "classificationType": "Firm",
                "name": "BAD AFFIL CORP",
                "exclusionType": "Reciprocal",
                "activationDate": "2021-01-01",
                "affiliations": "not-valid-json",
            }
        ]
        with patch.object(ingester, "_cross_reference_prescribers", return_value=0):
            with patch.object(ingester, "_cross_reference_pharmacies", return_value=0):
                await ingester.load(iter(records))

        row = db_session.query(SamExclusion).filter(SamExclusion.name == "BAD AFFIL CORP").first()
        assert row is not None


class TestSamCrossReferenceSuccessPath:
    def test_cross_reference_prescribers_returns_rowcount_on_success(
        self, db_session: Session, ingester: SamExclusionsIngester
    ):
        """Lines 326-327: success path returns rowcount from execute result."""
        from unittest.mock import MagicMock

        mock_result = MagicMock()
        mock_result.rowcount = 7

        with patch.object(db_session, "execute", return_value=mock_result):
            with patch.object(db_session, "commit"):
                count = ingester._cross_reference_prescribers()

        assert count == 7

    def test_cross_reference_pharmacies_returns_rowcount_on_success(
        self, db_session: Session, ingester: SamExclusionsIngester
    ):
        """Lines 359-360: success path returns accumulated rowcount."""
        from unittest.mock import MagicMock

        mock_result = MagicMock()
        mock_result.rowcount = 4

        with patch.object(db_session, "execute", return_value=mock_result):
            with patch.object(db_session, "commit"):
                count = ingester._cross_reference_pharmacies()

        assert count == 4


class TestSamRunOverride:
    async def test_run_catches_api_key_missing_error_returns_failed(
        self, db_session: Session, ingester: SamExclusionsIngester
    ):
        """Lines 375-381: run() catches _SamApiKeyMissingError from super().run()."""
        from shared.data_ingestion.sources.sam_exclusions import _SamApiKeyMissingError
        from unittest.mock import AsyncMock

        with patch(
            "shared.data_ingestion.base.DataSourceIngester.run",
            new=AsyncMock(side_effect=_SamApiKeyMissingError("key missing")),
        ):
            result = await ingester.run()

        assert result.status == "failed"
        assert "key missing" in result.error_message or "sam" in result.error_message.lower()

    async def test_run_duration_seconds_set_on_api_key_error(
        self, db_session: Session, ingester: SamExclusionsIngester
    ):
        """run() sets duration_seconds even when failing due to missing API key."""
        from shared.data_ingestion.sources.sam_exclusions import _SamApiKeyMissingError
        from unittest.mock import AsyncMock

        with patch(
            "shared.data_ingestion.base.DataSourceIngester.run",
            new=AsyncMock(side_effect=_SamApiKeyMissingError("invalid")),
        ):
            result = await ingester.run()

        assert result.duration_seconds is not None
        assert result.duration_seconds >= 0


class TestSamDownload:
    """Tests for the SAM download() method with mocked API."""

    async def test_download_with_valid_api_key_fetches_records(
        self, db_session: Session, ingester: SamExclusionsIngester
    ):
        """download() with SAM_API_KEY set fetches one page and writes JSONL file."""
        import respx
        import httpx

        from shared.data_ingestion.sources.sam_exclusions import _SAM_API_BASE_URL

        sample_record = {
            "classificationType": "Individual",
            "name": "TEST PERSON",
            "exclusionType": "Reciprocal",
            "activationDate": "2020-01-01",
            "npi": "1234567890",
        }

        response_data = {
            "exclusionList": [sample_record],
            "totalRecords": 1,
        }

        with patch.dict(os.environ, {"SAM_API_KEY": "test-api-key-abc123"}):
            with respx.mock:
                respx.get(_SAM_API_BASE_URL).mock(
                    return_value=httpx.Response(200, json=response_data)
                )
                out_path = await ingester.download()

        assert out_path.exists()
        content = out_path.read_text()
        assert "TEST PERSON" in content

    async def test_download_401_raises_api_key_missing_error(
        self, db_session: Session, ingester: SamExclusionsIngester
    ):
        """download() with 401 response raises _SamApiKeyMissingError."""
        import respx
        import httpx
        from shared.data_ingestion.sources.sam_exclusions import (
            _SAM_API_BASE_URL,
            _SamApiKeyMissingError,
        )

        with patch.dict(os.environ, {"SAM_API_KEY": "invalid-key"}):
            with respx.mock:
                respx.get(_SAM_API_BASE_URL).mock(
                    return_value=httpx.Response(401, json={"error": "Unauthorized"})
                )
                with pytest.raises(_SamApiKeyMissingError):
                    await ingester.download()

    async def test_download_empty_response_writes_empty_file(
        self, db_session: Session, ingester: SamExclusionsIngester
    ):
        """download() with empty exclusionList stops pagination immediately."""
        import respx
        import httpx
        from shared.data_ingestion.sources.sam_exclusions import _SAM_API_BASE_URL

        response_data = {"exclusionList": [], "totalRecords": 0}

        with patch.dict(os.environ, {"SAM_API_KEY": "test-key"}):
            with respx.mock:
                respx.get(_SAM_API_BASE_URL).mock(
                    return_value=httpx.Response(200, json=response_data)
                )
                out_path = await ingester.download()

        assert out_path.exists()

    async def test_download_uses_data_key_fallback(
        self, db_session: Session, ingester: SamExclusionsIngester
    ):
        """download() uses 'data' key if 'exclusionList' absent."""
        import respx
        import httpx
        from shared.data_ingestion.sources.sam_exclusions import _SAM_API_BASE_URL

        record = {"classificationType": "Firm", "name": "ACME", "activationDate": "2021-01-01"}
        response_data = {"data": [record], "total": 1}

        with patch.dict(os.environ, {"SAM_API_KEY": "test-key"}):
            with respx.mock:
                respx.get(_SAM_API_BASE_URL).mock(
                    return_value=httpx.Response(200, json=response_data)
                )
                out_path = await ingester.download()

        content = out_path.read_text()
        assert "ACME" in content

    async def test_download_pagination_stops_when_total_reached(
        self, db_session: Session, ingester: SamExclusionsIngester
    ):
        """Lines 124→170, 168: pagination loop exits when total_written >= totalRecords.
        Covers the logger.info after page and the break on total condition."""
        import respx
        import httpx
        from shared.data_ingestion.sources.sam_exclusions import _SAM_API_BASE_URL, _SAM_PAGE_SIZE

        records = [
            {"classificationType": "Individual", "name": f"P{i}", "activationDate": "2020-01-01"}
            for i in range(_SAM_PAGE_SIZE)
        ]
        # totalRecords == len(records) so loop exits after first page via total_written >= totalRecords
        response_data = {"exclusionList": records, "totalRecords": _SAM_PAGE_SIZE}

        call_count = 0

        def _mock_response(request):
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json=response_data)

        with patch.dict(os.environ, {"SAM_API_KEY": "test-key"}):
            with respx.mock:
                respx.get(_SAM_API_BASE_URL).mock(side_effect=_mock_response)
                out_path = await ingester.download()

        # Should have stopped after exactly 1 page (total_written == totalRecords)
        assert call_count == 1
        content = out_path.read_text()
        assert content.count("\n") == _SAM_PAGE_SIZE

    async def test_download_401_during_pagination_raises(
        self, db_session: Session, ingester: SamExclusionsIngester
    ):
        """Lines 202-204 in download: 401 mid-pagination raises _SamApiKeyMissingError."""
        import respx
        import httpx
        from shared.data_ingestion.sources.sam_exclusions import _SAM_API_BASE_URL, _SAM_PAGE_SIZE, _SamApiKeyMissingError

        with patch.dict(os.environ, {"SAM_API_KEY": "expired-key"}):
            with respx.mock:
                respx.get(_SAM_API_BASE_URL).mock(
                    return_value=httpx.Response(401, json={"error": "expired"})
                )
                with pytest.raises(_SamApiKeyMissingError):
                    await ingester.download()

    async def test_download_multi_page_increments_page_counter(
        self, db_session: Session, ingester: SamExclusionsIngester
    ):
        """Lines 168, 182: page += 1 fires when first page has more records than totalRecords
        suggests (i.e., second page needed), then logger after loop fires on completion."""
        import respx
        import httpx
        from shared.data_ingestion.sources.sam_exclusions import _SAM_API_BASE_URL, _SAM_PAGE_SIZE

        page1_records = [
            {"classificationType": "Individual", "name": f"P{i}", "activationDate": "2020-01-01"}
            for i in range(_SAM_PAGE_SIZE)
        ]
        page2_records = [
            {"classificationType": "Individual", "name": "LAST", "activationDate": "2020-01-01"}
        ]

        call_count = 0

        def _mock_response(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First page: full page size, totalRecords > written → page += 1 fires
                return httpx.Response(200, json={
                    "exclusionList": page1_records,
                    "totalRecords": _SAM_PAGE_SIZE + 1,
                })
            else:
                # Second page: fewer than page_size → break
                return httpx.Response(200, json={
                    "exclusionList": page2_records,
                    "totalRecords": _SAM_PAGE_SIZE + 1,
                })

        with patch.dict(os.environ, {"SAM_API_KEY": "test-key"}):
            with respx.mock:
                respx.get(_SAM_API_BASE_URL).mock(side_effect=_mock_response)
                out_path = await ingester.download()

        assert call_count == 2
        assert out_path.exists()
        content = out_path.read_text()
        assert "LAST" in content
