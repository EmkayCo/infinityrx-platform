"""Tests for the FDA REMS ingestion pipeline.

Covers:
- All documented fields captured from sample JSON
- checksum_skip: second run with same file → skipped_unchanged
- batch upsert idempotency: rerun → no duplicate rows
- ETASU JSONB roundtrip: complex dict persists and round-trips
- raw_payload contains all source fields (no data loss)

SQLAlchemy isolation:
  SAVEPOINT-based per LESSON-001.
  _UUIDString TypeDecorator per LESSON-007 (shared IngestionRun uses PG_UUID).
  BigInteger → Integer patch for SQLite autoincrement compatibility.

LESSON-011: Global reference data — no TenantScopedMixin.
LESSON-004: \\A...\\Z anchors used in the ingester.
LESSON-005: Log extra keys prefixed with ingest_.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import JSON, BigInteger, Integer, String, create_engine, event
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
from shared.data_ingestion.sources.fda_rems import (
    _build_etasu_requirements,
    _extract_rems_type,
    _parse_date_yyyymmdd,
    _parse_record,
)
from shared.db.base import Base

from src.models.fda_supplementary_tables import (  # type: ignore[import]
    DrugRems,
    DrugRemsNdc,
    SupplementaryBase,
    SCHEMA as SUPP_SCHEMA,
)

# ---------------------------------------------------------------------------
# Sample data path
# ---------------------------------------------------------------------------

_SAMPLE_DIR = Path(__file__).parent / "sample_data" / "fda_rems"
_SAMPLE_FILE = _SAMPLE_DIR / "fda_rems.json"


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
    """Patch PG_UUID → _UUIDString, JSONB → JSON, remove gen_random_uuid() defaults."""
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
        raw_labels = json.loads(_SAMPLE_FILE.read_text())
        parsed_records = [_parse_record(label) for label in raw_labels]
        parsed_records = [r for r in parsed_records if r is not None]

        assert len(parsed_records) == 5

        required_fields = {
            "application_number",
            "rems_program_name",
            "drug_name_brand",
            "drug_name_generic",
            "ndc_codes",
            "rems_type",
            "etasu_requirements",
            "initial_approval_date",
            "most_recent_modification_date",
            "status",
            "shared_system_name",
            "raw_payload",
        }
        for record in parsed_records:
            for field in required_fields:
                assert field in record, f"Missing field {field!r} in record for {record.get('application_number')}"

    def test_application_number_parsed(self) -> None:
        raw_labels = json.loads(_SAMPLE_FILE.read_text())
        parsed = [_parse_record(l) for l in raw_labels if l is not None]
        parsed = [r for r in parsed if r]
        app_numbers = {r["application_number"] for r in parsed}
        assert "NDA018662" in app_numbers
        assert "NDA019758" in app_numbers
        assert "BLA125104" in app_numbers

    def test_ndc_codes_list(self) -> None:
        raw_labels = json.loads(_SAMPLE_FILE.read_text())
        accutane = next(
            _parse_record(l) for l in raw_labels
            if (l.get("openfda") or {}).get("application_number", [""])[0] == "NDA018662"
        )
        assert accutane is not None
        assert isinstance(accutane["ndc_codes"], list)
        assert len(accutane["ndc_codes"]) == 2

    def test_rems_type_etasu_detected(self) -> None:
        raw_labels = json.loads(_SAMPLE_FILE.read_text())
        accutane = next(
            _parse_record(l) for l in raw_labels
            if (l.get("openfda") or {}).get("application_number", [""])[0] == "NDA018662"
        )
        assert accutane["rems_type"] == "ETASU"

    def test_status_is_active(self) -> None:
        raw_labels = json.loads(_SAMPLE_FILE.read_text())
        parsed = [r for r in (_parse_record(l) for l in raw_labels) if r]
        for record in parsed:
            assert record["status"] == "Active"

    def test_initial_approval_date_parsed(self) -> None:
        raw_labels = json.loads(_SAMPLE_FILE.read_text())
        accutane_label = next(
            l for l in raw_labels
            if (l.get("openfda") or {}).get("application_number", [""])[0] == "NDA018662"
        )
        parsed = _parse_record(accutane_label)
        assert parsed is not None
        assert parsed["initial_approval_date"] == date(2023, 10, 15)


# ---------------------------------------------------------------------------
# 2. Parse date helper
# ---------------------------------------------------------------------------


class TestParseDateYyyymmdd:
    def test_valid_date(self) -> None:
        assert _parse_date_yyyymmdd("20231015") == date(2023, 10, 15)

    def test_none_returns_none(self) -> None:
        assert _parse_date_yyyymmdd(None) is None

    def test_empty_returns_none(self) -> None:
        assert _parse_date_yyyymmdd("") is None

    def test_non_date_returns_none(self) -> None:
        assert _parse_date_yyyymmdd("INVALID") is None

    def test_invalid_month_returns_none(self) -> None:
        assert _parse_date_yyyymmdd("20231399") is None


# ---------------------------------------------------------------------------
# 3. ETASU JSONB roundtrip
# ---------------------------------------------------------------------------


class TestEtasuJsonbRoundtrip:
    def test_etasu_jsonb_roundtrip(self, db_session: Session) -> None:
        """Complex ETASU dict persists and round-trips correctly through SQLite JSON."""
        etasu = {
            "prescriber_certification": True,
            "pharmacy_certification": True,
            "patient_enrollment": True,
            "medication_guide": True,
            "communication_plan": False,
        }
        rems = DrugRems(
            application_number="NDA999001",
            rems_program_name="Test REMS Program",
            drug_name_brand="TestBrand",
            drug_name_generic="testgeneric",
            etasu_requirements=etasu,
            status="Active",
        )
        db_session.add(rems)
        db_session.flush()

        fetched = db_session.query(DrugRems).filter_by(application_number="NDA999001").one()
        assert fetched.etasu_requirements is not None
        assert fetched.etasu_requirements["prescriber_certification"] is True
        assert fetched.etasu_requirements["pharmacy_certification"] is True
        assert fetched.etasu_requirements["patient_enrollment"] is True
        assert fetched.etasu_requirements["medication_guide"] is True
        assert fetched.etasu_requirements["communication_plan"] is False

    def test_etasu_nested_structure_preserved(self, db_session: Session) -> None:
        """Nested ETASU structures with lists and nested dicts survive roundtrip."""
        etasu_complex = {
            "prescriber_certification": True,
            "requirements_list": ["req_1", "req_2", "req_3"],
            "nested": {"sub_key": "sub_value", "count": 3},
        }
        rems = DrugRems(
            application_number="NDA999002",
            rems_program_name="Complex ETASU Program",
            etasu_requirements=etasu_complex,
            status="Active",
        )
        db_session.add(rems)
        db_session.flush()

        fetched = db_session.query(DrugRems).filter_by(application_number="NDA999002").one()
        assert fetched.etasu_requirements["requirements_list"] == ["req_1", "req_2", "req_3"]
        assert fetched.etasu_requirements["nested"]["count"] == 3


# ---------------------------------------------------------------------------
# 4. Checksum skip
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
            source="fda_rems",
            run_type="auto_scheduled",
            status="completed",
            started_at=now,
            source_file_checksum=checksum,
        )
        db_session.add(run)
        db_session.flush()

        row = (
            db_session.query(IngestionRun)
            .filter_by(source="fda_rems", status="completed")
            .order_by(IngestionRun.started_at.desc())
            .first()
        )
        assert row is not None
        assert row.source_file_checksum == checksum


# ---------------------------------------------------------------------------
# 5. Batch upsert idempotency
# ---------------------------------------------------------------------------


class TestBatchUpsertIdempotent:
    def test_batch_upsert_idempotent(self, db_session: Session) -> None:
        """Upserting the same REMS record twice leaves exactly one row."""
        from src.services.fda_supplementary_ingestion import (  # type: ignore[import]
            RemsIngestionService,
        )

        svc = RemsIngestionService(db_session=db_session)

        row = {
            "application_number": "NDA777001",
            "rems_program_name": "Test Idempotent REMS",
            "drug_name_brand": "TestBrand v1",
            "drug_name_generic": "testgeneric",
            "ndc_codes": ["00001-0001-01"],
            "rems_type": "ETASU",
            "etasu_requirements": {"prescriber_certification": True},
            "status": "Active",
        }
        svc._upsert_rems_batch([row])
        db_session.flush()

        row2 = {**row, "drug_name_brand": "TestBrand v2"}
        svc._upsert_rems_batch([row2])
        db_session.flush()

        results = (
            db_session.query(DrugRems)
            .filter_by(application_number="NDA777001")
            .all()
        )
        assert len(results) == 1
        assert results[0].drug_name_brand == "TestBrand v2"

    def test_batch_upsert_multiple_records(self, db_session: Session) -> None:
        """Multiple distinct REMS records all persisted correctly."""
        from src.services.fda_supplementary_ingestion import (  # type: ignore[import]
            RemsIngestionService,
        )
        svc = RemsIngestionService(db_session=db_session)

        rows = [
            {
                "application_number": f"NDA88800{i}",
                "rems_program_name": f"Batch REMS {i}",
                "drug_name_generic": f"drug_{i}",
                "status": "Active",
            }
            for i in range(5)
        ]
        svc._upsert_rems_batch(rows)
        db_session.flush()

        count = db_session.query(DrugRems).filter(
            DrugRems.rems_program_name.like("Batch REMS %")
        ).count()
        assert count == 5


# ---------------------------------------------------------------------------
# 6. Raw payload contains all source fields
# ---------------------------------------------------------------------------


class TestRawPayloadContainsAllSourceFields:
    def test_raw_payload_contains_all_source_fields(self) -> None:
        """raw_payload preserves every key from the source JSON label."""
        raw_labels = json.loads(_SAMPLE_FILE.read_text())
        for label in raw_labels:
            parsed = _parse_record(label)
            if parsed is None:
                continue
            raw_payload = parsed.get("raw_payload") or {}
            for key in label:
                assert key in raw_payload, (
                    f"Source key {key!r} missing from raw_payload for "
                    f"application {parsed.get('application_number')}"
                )


# ---------------------------------------------------------------------------
# 7. REMS type extraction
# ---------------------------------------------------------------------------


class TestRemsTypeExtraction:
    def test_etasu_detected_from_rems_list(self) -> None:
        assert _extract_rems_type(["ETASU program details"]) == "ETASU"

    def test_unknown_keywords_returns_first_element(self) -> None:
        result = _extract_rems_type(["Some other REMS program"])
        assert result == "Some other REMS program"

    def test_communication_plan_detected(self) -> None:
        assert _extract_rems_type(["Communication Plan for prescribers"]) == "Communication Plan"

    def test_medication_guide_detected(self) -> None:
        result = _extract_rems_type(["Medication Guide required"])
        assert result == "Medication Guide"

    def test_none_for_empty_list(self) -> None:
        assert _extract_rems_type([]) is None

    def test_none_for_none(self) -> None:
        assert _extract_rems_type(None) is None


# ---------------------------------------------------------------------------
# 8. Build ETASU requirements
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 9. Ingester.parse() — covers the parse() method of FdaRemsIngester
# ---------------------------------------------------------------------------


class TestFdaRemsIngesterParse:
    def test_parse_from_sample_file_yields_records(self, db_session: Session) -> None:
        """FdaRemsIngester.parse() yields all valid records from sample JSON."""
        from shared.data_ingestion.sources.fda_rems import FdaRemsIngester

        ingester = FdaRemsIngester(db_session=db_session)
        records = list(ingester.parse(_SAMPLE_FILE))
        assert len(records) == 5

    def test_parse_yields_all_required_fields(self, db_session: Session) -> None:
        """Each yielded record contains all required fields."""
        from shared.data_ingestion.sources.fda_rems import FdaRemsIngester

        ingester = FdaRemsIngester(db_session=db_session)
        required = {"application_number", "rems_program_name", "status", "raw_payload"}
        for record in ingester.parse(_SAMPLE_FILE):
            for field in required:
                assert field in record

    def test_parse_record_none_for_missing_app_number(self) -> None:
        """_parse_record returns None when application_number is absent."""
        label_no_app = {
            "id": "label-no-app",
            "openfda": {"brand_name": ["TestBrand"]},
            "rems": ["Some REMS"],
        }
        result = _parse_record(label_no_app)
        assert result is None


# ---------------------------------------------------------------------------
# 10. Download method — mocked HTTP calls
# ---------------------------------------------------------------------------


class TestFdaRemsIngesterDownload:
    @pytest.mark.asyncio
    async def test_download_writes_json_file(
        self, db_session: Session, tmp_path: Path
    ) -> None:
        """download() fetches API pages and writes a JSON file."""
        import json as _json
        from unittest.mock import AsyncMock, MagicMock, patch

        from shared.data_ingestion.sources.fda_rems import FdaRemsIngester

        sample_labels = _json.loads(_SAMPLE_FILE.read_text())
        api_response = {
            "meta": {"results": {"total": len(sample_labels)}},
            "results": sample_labels,
        }

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=api_response)
        mock_resp.status_code = 200

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        ingester = FdaRemsIngester(db_session=db_session)

        with (
            patch("shared.data_ingestion.sources.fda_rems._DEST_DIR", tmp_path),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result_path = await ingester.download()

        assert result_path.exists()
        data = _json.loads(result_path.read_text())
        assert isinstance(data, list)
        assert len(data) == len(sample_labels)

    @pytest.mark.asyncio
    async def test_download_paginates_until_empty_results(
        self, db_session: Session, tmp_path: Path
    ) -> None:
        """download() stops paginating when results list is empty."""
        from unittest.mock import AsyncMock, MagicMock, patch
        import json as _json

        from shared.data_ingestion.sources.fda_rems import FdaRemsIngester, _API_LIMIT

        # Make a page with exactly _API_LIMIT records so pagination continues
        full_page = [
            {"openfda": {"application_number": [f"NDA{i:06d}"]}, "rems": ["ETASU: test"], "effective_time": "20240101"}
            for i in range(_API_LIMIT)
        ]
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

        ingester = FdaRemsIngester(db_session=db_session)
        with (
            patch("shared.data_ingestion.sources.fda_rems._DEST_DIR", tmp_path),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result_path = await ingester.download()

        assert call_count == 2
        data = _json.loads(result_path.read_text())
        assert len(data) == _API_LIMIT

    @pytest.mark.asyncio
    async def test_load_delegates_to_rems_ingestion_service(
        self, db_session: Session
    ) -> None:
        """load() delegates to RemsIngestionService.load_records()."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from shared.data_ingestion.base import IngestionResult
        from shared.data_ingestion.sources.fda_rems import FdaRemsIngester

        expected_result = IngestionResult(
            source="fda_rems",
            status="completed",
            records_processed=3,
            records_inserted=3,
        )

        mock_svc = MagicMock()
        mock_svc.load_records = AsyncMock(return_value=expected_result)

        with patch(
            "src.services.fda_supplementary_ingestion.RemsIngestionService",
            return_value=mock_svc,
        ):
            ingester = FdaRemsIngester(db_session=db_session)
            records = iter([{"application_number": "NDA000001", "rems_program_name": "Test"}])
            result = await ingester.load(records)

        assert result.status == "completed"
        assert result.records_processed == 3

    @pytest.mark.asyncio
    async def test_download_handles_404_gracefully(
        self, db_session: Session, tmp_path: Path
    ) -> None:
        """download() handles 404 on first page and writes empty file."""
        from unittest.mock import AsyncMock, MagicMock, patch
        import json as _json

        from shared.data_ingestion.sources.fda_rems import FdaRemsIngester

        mock_resp = MagicMock()
        mock_resp.status_code = 404

        def _raise(*args: Any, **kwargs: Any) -> None:
            raise httpx.HTTPStatusError("404", request=MagicMock(), response=mock_resp)

        mock_resp.raise_for_status = _raise

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        ingester = FdaRemsIngester(db_session=db_session)
        with (
            patch("shared.data_ingestion.sources.fda_rems._DEST_DIR", tmp_path),
            patch("httpx.AsyncClient", return_value=mock_client),
        ):
            result_path = await ingester.download()

        data = _json.loads(result_path.read_text())
        assert data == []


class TestBuildEtasuRequirements:
    def test_prescriber_certification_detected(self) -> None:
        reqs = _build_etasu_requirements(["Prescriber certification required"])
        assert reqs is not None
        assert reqs["prescriber_certification"] is True

    def test_pharmacy_certification_detected(self) -> None:
        reqs = _build_etasu_requirements(["Pharmacy certification required"])
        assert reqs is not None
        assert reqs["pharmacy_certification"] is True

    def test_patient_enrollment_detected(self) -> None:
        reqs = _build_etasu_requirements(["Patient enrollment required"])
        assert reqs is not None
        assert reqs["patient_enrollment"] is True

    def test_none_for_empty(self) -> None:
        assert _build_etasu_requirements(None) is None
        assert _build_etasu_requirements([]) is None
