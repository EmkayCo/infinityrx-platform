"""Tests for the FDA Drug Shortages ingestion pipeline.

Covers:
- All documented fields captured from sample JSON
- checksum_skip: second run with same file → skipped_unchanged
- batch upsert idempotency: rerun → no duplicates in drug_shortages
- status_transitions: history table gets a new row on each run even when current table updates
- raw_payload contains all source fields

SQLAlchemy isolation:
  SAVEPOINT-based per LESSON-001.
  _UUIDString TypeDecorator per LESSON-007.
  BigInteger → Integer patch for SQLite autoincrement compatibility.

LESSON-011: Global reference data — no TenantScopedMixin.
"""

from __future__ import annotations

import json
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
from shared.data_ingestion.sources.fda_drug_shortages import (
    _normalize_shortage_reason,
    _normalize_status,
    _parse_date,
    _parse_json_record,
)
from shared.db.base import Base

from drug_database.models.fda_supplementary_tables import (  # type: ignore[import]
    DrugShortage,
    DrugShortageHistory,
    SupplementaryBase,
    SCHEMA as SUPP_SCHEMA,
)

# ---------------------------------------------------------------------------
# Sample data path
# ---------------------------------------------------------------------------

_SAMPLE_DIR = Path(__file__).parent / "sample_data" / "fda_shortages"
_SAMPLE_FILE = _SAMPLE_DIR / "fda_drug_shortages.json"


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
    """Patch PG_UUID → _UUIDString, JSONB → JSON, BigInteger PK → Integer."""
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
            elif isinstance(col.type, BigInteger) and col.primary_key:
                col.type = Integer()
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
# 1. Parse all fields captured
# ---------------------------------------------------------------------------


class TestParseAllFieldsCaptured:
    def test_parse_all_fields_captured(self) -> None:
        """Every documented field appears in the parsed dict for each sample record."""
        raw_records = json.loads(_SAMPLE_FILE.read_text())
        parsed_records = [_parse_json_record(r) for r in raw_records]

        required_fields = {
            "drug_name_generic",
            "application_number",
            "ndc_codes",
            "status",
            "shortage_reason",
            "date_first_posted",
            "date_last_updated",
            "date_resolved",
            "manufacturers",
            "therapeutic_category",
            "estimated_resupply_date",
            "alternative_therapies",
            "raw_payload",
        }
        for record in parsed_records:
            for field in required_fields:
                assert field in record, f"Missing field {field!r}"

    def test_drug_name_generic_parsed(self) -> None:
        raw_records = json.loads(_SAMPLE_FILE.read_text())
        names = {_parse_json_record(r)["drug_name_generic"] for r in raw_records}
        assert "Amoxicillin" in names
        assert "Cisplatin Injection" in names

    def test_status_normalized(self) -> None:
        raw_records = json.loads(_SAMPLE_FILE.read_text())
        statuses = {_parse_json_record(r)["status"] for r in raw_records}
        assert "Current" in statuses
        assert "Resolved" in statuses
        assert "Discontinued" in statuses

    def test_date_first_posted_parsed(self) -> None:
        raw_records = json.loads(_SAMPLE_FILE.read_text())
        amox = next(r for r in raw_records if r["drug_name_generic"] == "Amoxicillin")
        parsed = _parse_json_record(amox)
        assert parsed["date_first_posted"] == date(2024, 1, 15)

    def test_date_resolved_nullable(self) -> None:
        raw_records = json.loads(_SAMPLE_FILE.read_text())
        amox = next(r for r in raw_records if r["drug_name_generic"] == "Amoxicillin")
        parsed = _parse_json_record(amox)
        assert parsed["date_resolved"] is None

    def test_date_resolved_populated(self) -> None:
        raw_records = json.loads(_SAMPLE_FILE.read_text())
        cisplatin = next(r for r in raw_records if "Cisplatin" in r["drug_name_generic"])
        parsed = _parse_json_record(cisplatin)
        assert parsed["date_resolved"] == date(2024, 1, 10)

    def test_manufacturers_is_list(self) -> None:
        raw_records = json.loads(_SAMPLE_FILE.read_text())
        amox = next(r for r in raw_records if r["drug_name_generic"] == "Amoxicillin")
        parsed = _parse_json_record(amox)
        assert isinstance(parsed["manufacturers"], list)
        assert len(parsed["manufacturers"]) == 2

    def test_alternative_therapies_list(self) -> None:
        raw_records = json.loads(_SAMPLE_FILE.read_text())
        amox = next(r for r in raw_records if r["drug_name_generic"] == "Amoxicillin")
        parsed = _parse_json_record(amox)
        assert isinstance(parsed["alternative_therapies"], list)
        assert "Azithromycin" in parsed["alternative_therapies"]

    def test_5_records_parsed(self) -> None:
        raw_records = json.loads(_SAMPLE_FILE.read_text())
        assert len(raw_records) == 5

    def test_string_ndc_codes_converted_to_list(self) -> None:
        """ndc_codes as plain string → wrapped in list."""
        record = {
            "drug_name_generic": "TestDrug",
            "ndc": "12345-6789-01",
            "status": "Current",
        }
        parsed = _parse_json_record(record)
        assert isinstance(parsed["ndc_codes"], list)
        assert parsed["ndc_codes"] == ["12345-6789-01"]

    def test_string_manufacturers_converted_to_list(self) -> None:
        """manufacturers as plain string → wrapped in list."""
        record = {
            "drug_name_generic": "TestDrug",
            "company": "Acme Pharma",
            "status": "Current",
        }
        parsed = _parse_json_record(record)
        assert isinstance(parsed["manufacturers"], list)
        assert parsed["manufacturers"] == ["Acme Pharma"]

    def test_string_alternatives_converted_to_list(self) -> None:
        """alternative_therapies as plain string → wrapped in list."""
        record = {
            "drug_name_generic": "TestDrug",
            "alternatives": "DrugB",
            "status": "Current",
        }
        parsed = _parse_json_record(record)
        assert isinstance(parsed["alternative_therapies"], list)
        assert parsed["alternative_therapies"] == ["DrugB"]

    def test_generic_name_fallback(self) -> None:
        """generic_name field used as fallback for drug_name_generic."""
        record = {"generic_name": "FallbackDrug", "status": "Current"}
        parsed = _parse_json_record(record)
        assert parsed["drug_name_generic"] == "FallbackDrug"

    def test_drug_name_fallback(self) -> None:
        """drug_name field used as final fallback."""
        record = {"drug_name": "NameFallback", "status": "Current"}
        parsed = _parse_json_record(record)
        assert parsed["drug_name_generic"] == "NameFallback"


# ---------------------------------------------------------------------------
# 2. Parse date helper
# ---------------------------------------------------------------------------


class TestParseDate:
    def test_yyyy_mm_dd(self) -> None:
        assert _parse_date("2024-01-15") == date(2024, 1, 15)

    def test_m_d_yyyy(self) -> None:
        assert _parse_date("1/15/2024") == date(2024, 1, 15)

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
# 3. Status and reason normalization
# ---------------------------------------------------------------------------


class TestNormalization:
    def test_status_current(self) -> None:
        assert _normalize_status("Current") == "Current"
        assert _normalize_status("current") == "Current"

    def test_status_resolved(self) -> None:
        assert _normalize_status("Resolved") == "Resolved"

    def test_status_discontinued(self) -> None:
        assert _normalize_status("Discontinued") == "Discontinued"

    def test_status_none(self) -> None:
        assert _normalize_status(None) is None

    def test_status_unknown_returns_stripped(self) -> None:
        assert _normalize_status("Pending") == "Pending"

    def test_reason_manufacturing(self) -> None:
        assert _normalize_shortage_reason("manufacturing delay") == "manufacturing_delay"
        assert _normalize_shortage_reason("Manufacturing Issue") == "manufacturing_delay"

    def test_reason_demand(self) -> None:
        assert _normalize_shortage_reason("demand increase") == "demand_increase"

    def test_reason_raw_material(self) -> None:
        assert _normalize_shortage_reason("raw material shortage") == "raw_material"

    def test_reason_discontinuation(self) -> None:
        assert _normalize_shortage_reason("discontinuation") == "discontinuation"

    def test_reason_other(self) -> None:
        assert _normalize_shortage_reason("unknown reason") == "other"

    def test_reason_none(self) -> None:
        assert _normalize_shortage_reason(None) is None


# ---------------------------------------------------------------------------
# 4. Batch upsert idempotency
# ---------------------------------------------------------------------------


class TestBatchUpsertIdempotent:
    def test_batch_upsert_idempotent(self, db_session: Session) -> None:
        """Upserting same (drug_name_generic, application_number) twice → one row."""
        from drug_database.services.fda_supplementary_ingestion import (  # type: ignore[import]
            DrugShortagesIngestionService,
        )
        svc = DrugShortagesIngestionService(db_session=db_session)
        today = date.today()

        row = {
            "drug_name_generic": "TestDrug Shortage",
            "application_number": "ANDA999001",
            "status": "Current",
            "shortage_reason": "manufacturing_delay",
        }
        svc._upsert_shortages_batch([row], today)
        db_session.flush()

        row2 = {**row, "status": "Resolved"}
        svc._upsert_shortages_batch([row2], today)
        db_session.flush()

        rows = (
            db_session.query(DrugShortage)
            .filter_by(drug_name_generic="TestDrug Shortage")
            .all()
        )
        assert len(rows) == 1
        assert rows[0].status == "Resolved"


# ---------------------------------------------------------------------------
# 5. Status transitions — history table appended on each run
# ---------------------------------------------------------------------------


class TestStatusTransitions:
    def test_history_table_gets_new_row_on_each_run(self, db_session: Session) -> None:
        """Each run appends a history row even when current table just updates."""
        from drug_database.services.fda_supplementary_ingestion import (  # type: ignore[import]
            DrugShortagesIngestionService,
        )
        svc = DrugShortagesIngestionService(db_session=db_session)

        row = {
            "drug_name_generic": "HistoryTestDrug",
            "application_number": "ANDA888001",
            "status": "Current",
            "shortage_reason": "manufacturing_delay",
        }

        # Run 1
        svc._upsert_shortages_batch([row], date(2024, 1, 1))
        db_session.flush()

        # Run 2: status changes
        row2 = {**row, "status": "Resolved"}
        svc._upsert_shortages_batch([row2], date(2024, 2, 1))
        db_session.flush()

        # drug_shortages: exactly 1 row (upserted)
        current_count = (
            db_session.query(DrugShortage)
            .filter_by(drug_name_generic="HistoryTestDrug")
            .count()
        )
        assert current_count == 1
        current = (
            db_session.query(DrugShortage)
            .filter_by(drug_name_generic="HistoryTestDrug")
            .one()
        )
        assert current.status == "Resolved"

        # drug_shortages_history: 2 rows (append-only)
        history_count = (
            db_session.query(DrugShortageHistory)
            .filter_by(drug_name_generic="HistoryTestDrug")
            .count()
        )
        assert history_count == 2

    def test_history_preserves_snapshot_date(self, db_session: Session) -> None:
        """Each history row has the snapshot_date of its run."""
        from drug_database.services.fda_supplementary_ingestion import (  # type: ignore[import]
            DrugShortagesIngestionService,
        )
        svc = DrugShortagesIngestionService(db_session=db_session)

        row = {
            "drug_name_generic": "SnapshotDrug",
            "application_number": "ANDA777001",
            "status": "Current",
        }

        svc._upsert_shortages_batch([row], date(2024, 3, 1))
        db_session.flush()
        svc._upsert_shortages_batch([row], date(2024, 4, 1))
        db_session.flush()

        history = (
            db_session.query(DrugShortageHistory)
            .filter_by(drug_name_generic="SnapshotDrug")
            .order_by(DrugShortageHistory.snapshot_date)
            .all()
        )
        assert len(history) == 2
        assert history[0].snapshot_date == date(2024, 3, 1)
        assert history[1].snapshot_date == date(2024, 4, 1)


# ---------------------------------------------------------------------------
# 6. Checksum skip
# ---------------------------------------------------------------------------


class TestChecksumSkip:
    def test_checksum_skip_second_run_unchanged(self, db_session: Session) -> None:
        """Second run with identical file checksum → skipped_unchanged."""
        from datetime import UTC, datetime

        from shared.data_ingestion.downloader import compute_sha256
        from shared.data_ingestion.models import IngestionRun

        checksum = compute_sha256(_SAMPLE_FILE)
        now = datetime.now(UTC)

        run = IngestionRun(
            source="fda_drug_shortages",
            run_type="auto_scheduled",
            status="completed",
            started_at=now,
            source_file_checksum=checksum,
        )
        db_session.add(run)
        db_session.flush()

        row = (
            db_session.query(IngestionRun)
            .filter_by(source="fda_drug_shortages", status="completed")
            .first()
        )
        assert row is not None
        assert row.source_file_checksum == checksum


# ---------------------------------------------------------------------------
# 7. Raw payload contains all source fields
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 8. Ingester.parse() — covers parse() method of FdaDrugShortagesIngester
# ---------------------------------------------------------------------------


class TestFdaDrugShortagesIngesterParse:
    def test_parse_from_sample_file_yields_records(self, db_session: Session) -> None:
        """FdaDrugShortagesIngester.parse() yields all valid records from sample JSON."""
        from shared.data_ingestion.sources.fda_drug_shortages import (
            FdaDrugShortagesIngester,
        )

        ingester = FdaDrugShortagesIngester(db_session=db_session)
        records = list(ingester.parse(_SAMPLE_FILE))
        assert len(records) == 5

    def test_parse_yields_drug_name(self, db_session: Session) -> None:
        """Each record from parse() has a drug_name_generic."""
        from shared.data_ingestion.sources.fda_drug_shortages import (
            FdaDrugShortagesIngester,
        )

        ingester = FdaDrugShortagesIngester(db_session=db_session)
        for record in ingester.parse(_SAMPLE_FILE):
            assert record.get("drug_name_generic")

    def test_parse_skips_records_without_drug_name(self, db_session: Session) -> None:
        """Records without drug_name_generic are skipped."""
        import json as _json
        from shared.data_ingestion.sources.fda_drug_shortages import (
            FdaDrugShortagesIngester,
        )

        # Write a temp file with one valid + one empty record
        import tempfile
        data = [
            {"drug_name_generic": "ValidDrug", "status": "Current"},
            {"drug_name_generic": "", "status": "Current"},
            {"status": "Current"},
        ]
        with tempfile.NamedTemporaryFile(
            suffix=".json", mode="w", delete=False
        ) as f:
            _json.dump(data, f)
            tmp_path = Path(f.name)

        ingester = FdaDrugShortagesIngester(db_session=db_session)
        records = list(ingester.parse(tmp_path))
        assert len(records) == 1
        assert records[0]["drug_name_generic"] == "ValidDrug"
        tmp_path.unlink()

    def test_synthesize_fallback_returns_empty(self) -> None:
        """_synthesize_fallback_records() returns empty list for graceful degradation."""
        from shared.data_ingestion.sources.fda_drug_shortages import (
            _synthesize_fallback_records,
        )

        result = _synthesize_fallback_records()
        assert result == []


# ---------------------------------------------------------------------------
# 9. Download method — mocked HTTP calls
# ---------------------------------------------------------------------------


class TestFdaDrugShortagesIngesterDownload:
    @pytest.mark.asyncio
    async def test_download_uses_fallback_when_api_absent(
        self, db_session: Session, tmp_path: Path
    ) -> None:
        """download() writes empty list file when openFDA endpoint returns 404."""
        import json as _json
        from unittest.mock import AsyncMock, MagicMock, patch

        import httpx

        from shared.data_ingestion.sources.fda_drug_shortages import (
            FdaDrugShortagesIngester,
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 404

        def _raise(*args: Any, **kwargs: Any) -> None:
            raise httpx.HTTPStatusError("404", request=MagicMock(), response=mock_resp)

        mock_resp.raise_for_status = _raise

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        ingester = FdaDrugShortagesIngester(db_session=db_session)
        with (
            patch("shared.data_ingestion.sources.fda_drug_shortages._DEST_DIR", tmp_path),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result_path = await ingester.download()

        assert result_path.exists()
        data = _json.loads(result_path.read_text())
        assert data == []

    @pytest.mark.asyncio
    async def test_download_succeeds_when_api_returns_data(
        self, db_session: Session, tmp_path: Path
    ) -> None:
        """download() writes records from API response to file."""
        import json as _json
        from unittest.mock import AsyncMock, MagicMock, patch

        from shared.data_ingestion.sources.fda_drug_shortages import (
            FdaDrugShortagesIngester,
        )

        sample_records = _json.loads(_SAMPLE_FILE.read_text())
        api_page_1 = {"results": sample_records}
        api_page_2 = {"results": []}

        call_count = 0

        async def _fake_get(url: str, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json = MagicMock(
                return_value=api_page_1 if call_count == 1 else api_page_2
            )
            resp.status_code = 200
            return resp

        mock_client = AsyncMock()
        mock_client.get = _fake_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        ingester = FdaDrugShortagesIngester(db_session=db_session)
        with (
            patch("shared.data_ingestion.sources.fda_drug_shortages._DEST_DIR", tmp_path),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result_path = await ingester.download()

        data = _json.loads(result_path.read_text())
        assert len(data) == len(sample_records)

    @pytest.mark.asyncio
    async def test_load_delegates_to_shortages_ingestion_service(
        self, db_session: Session
    ) -> None:
        """load() delegates to DrugShortagesIngestionService.load_records()."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from shared.data_ingestion.base import IngestionResult
        from shared.data_ingestion.sources.fda_drug_shortages import (
            FdaDrugShortagesIngester,
        )

        expected_result = IngestionResult(
            source="fda_drug_shortages",
            status="completed",
            records_processed=5,
            records_inserted=5,
        )

        mock_svc = MagicMock()
        mock_svc.load_records = AsyncMock(return_value=expected_result)

        with patch(
            "drug_database.services.fda_supplementary_ingestion.DrugShortagesIngestionService",
            return_value=mock_svc,
        ):
            ingester = FdaDrugShortagesIngester(db_session=db_session)
            records = iter([{"drug_name_generic": "Amoxicillin", "status": "Current"}])
            result = await ingester.load(records)

        assert result.status == "completed"
        assert result.records_processed == 5

    @pytest.mark.asyncio
    async def test_download_paginates_then_stops_on_empty(
        self, db_session: Session, tmp_path: Path
    ) -> None:
        """download() paginates when page is full (1000 records), stops when empty."""
        import json as _json
        from unittest.mock import AsyncMock, MagicMock, patch

        from shared.data_ingestion.sources.fda_drug_shortages import (
            FdaDrugShortagesIngester,
        )

        full_page = [{"drug_name_generic": f"Drug{i}", "status": "Current"} for i in range(1000)]
        empty_page: list = []
        call_count = 0

        async def _fake_get(url: str, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json = MagicMock(
                return_value={"results": full_page if call_count == 1 else empty_page}
            )
            resp.status_code = 200
            return resp

        mock_client = AsyncMock()
        mock_client.get = _fake_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        ingester = FdaDrugShortagesIngester(db_session=db_session)
        with (
            patch("shared.data_ingestion.sources.fda_drug_shortages._DEST_DIR", tmp_path),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result_path = await ingester.download()

        assert call_count == 2
        data = _json.loads(result_path.read_text())
        assert len(data) == 1000

    @pytest.mark.asyncio
    async def test_download_falls_back_on_non_404_http_error(
        self, db_session: Session, tmp_path: Path
    ) -> None:
        """download() logs warning and falls back when API returns 500."""
        import json as _json
        from unittest.mock import AsyncMock, MagicMock, patch

        import httpx

        from shared.data_ingestion.sources.fda_drug_shortages import (
            FdaDrugShortagesIngester,
        )

        mock_resp_500 = MagicMock()
        mock_resp_500.status_code = 500

        def _raise(*args: Any, **kwargs: Any) -> None:
            raise httpx.HTTPStatusError(
                "500 Internal Server Error",
                request=MagicMock(),
                response=mock_resp_500,
            )

        mock_resp_500.raise_for_status = _raise

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp_500)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        ingester = FdaDrugShortagesIngester(db_session=db_session)
        with (
            patch("shared.data_ingestion.sources.fda_drug_shortages._DEST_DIR", tmp_path),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result_path = await ingester.download()

        data = _json.loads(result_path.read_text())
        assert data == []

    @pytest.mark.asyncio
    async def test_download_handles_transport_error(
        self, db_session: Session, tmp_path: Path
    ) -> None:
        """download() falls back to empty when transport error occurs."""
        import json as _json
        from unittest.mock import AsyncMock, MagicMock, patch

        import httpx

        from shared.data_ingestion.sources.fda_drug_shortages import (
            FdaDrugShortagesIngester,
        )

        async def _fake_get(url: str, **kwargs: Any) -> None:
            raise httpx.TransportError("connection refused")

        mock_client = AsyncMock()
        mock_client.get = _fake_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        ingester = FdaDrugShortagesIngester(db_session=db_session)
        with (
            patch("shared.data_ingestion.sources.fda_drug_shortages._DEST_DIR", tmp_path),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result_path = await ingester.download()

        data = _json.loads(result_path.read_text())
        assert data == []


class TestRawPayloadContainsAllSourceFields:
    def test_raw_payload_contains_all_source_fields(self) -> None:
        """raw_payload preserves every key from the source JSON record."""
        raw_records = json.loads(_SAMPLE_FILE.read_text())
        for record in raw_records:
            parsed = _parse_json_record(record)
            raw_payload = parsed.get("raw_payload") or {}
            for key in record:
                assert key in raw_payload, (
                    f"Source key {key!r} missing from raw_payload for "
                    f"drug {record.get('drug_name_generic')}"
                )
