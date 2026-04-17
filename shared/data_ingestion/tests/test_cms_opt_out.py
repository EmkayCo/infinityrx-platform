"""Tests for CMS Medicare Opt-Out Affidavits ingestion.

Covers:
  - All fields captured from source row
  - cross_reference sets opt_out status on Prescriber
  - Ended opt-out (end_date in past) clears status
  - Batch upsert idempotency
  - raw_payload contains full source row

SQLAlchemy isolation: SAVEPOINT-based per LESSON-001.
_UUIDString TypeDecorator per LESSON-007.
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
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import JSON, String, create_engine, event
import httpx
import respx
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import TypeDecorator

# --- env defaults -----------------------------------------------------------
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost/")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")
os.environ.setdefault(
    "ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM="
)

# --- path setup -------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_PRESCRIBER_ROOT = _REPO_ROOT / "modules" / "prescriber-directory"

for _p in (str(_REPO_ROOT), str(_PRESCRIBER_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Preload prescriber-directory's src.models submodules into sys.modules
# under their canonical ``src.models.*`` names. Required because
# test_fda_ndc_parser.py (if it runs earlier in the pytest session)
# registers drug-database's src.* first, and Python will then refuse
# to re-search sys.path when we say ``from src.models.tables import
# Prescriber`` — it finds drug-database's tables.py which has neither
# ``Prescriber`` nor ``PrescriberBase``. Same root cause as debt item
# (d) in Wave 14. See test_dea.py for the sibling copy of this logic.
# ---------------------------------------------------------------------------

import importlib.util as _importlib_util
import types as _types


def _preload_prescriber_src_into_src_namespace() -> None:
    prescriber_models_dir = str(_PRESCRIBER_ROOT / "src" / "models")
    prescriber_src_dir = str(_PRESCRIBER_ROOT / "src")

    if "src" not in sys.modules:
        src_pkg = _types.ModuleType("src")
        src_pkg.__path__ = [prescriber_src_dir]  # type: ignore[attr-defined]
        sys.modules["src"] = src_pkg
    else:
        paths = getattr(sys.modules["src"], "__path__", None)
        if paths is not None and prescriber_src_dir not in paths:
            paths.append(prescriber_src_dir)

    if "src.models" not in sys.modules:
        models_pkg = _types.ModuleType("src.models")
        models_pkg.__path__ = [prescriber_models_dir]  # type: ignore[attr-defined]
        sys.modules["src.models"] = models_pkg
    else:
        paths = getattr(sys.modules["src.models"], "__path__", None)
        if paths is not None and prescriber_models_dir not in paths:
            paths.append(prescriber_models_dir)

    for mod_name in ("src.models.tables", "src.models.medicare_tables"):
        existing = sys.modules.get(mod_name)
        if existing is not None:
            src_file = getattr(existing, "__file__", "") or ""
            if "prescriber-directory" in src_file:
                continue
            del sys.modules[mod_name]
        filename = mod_name.rsplit(".", 1)[-1] + ".py"
        file_path = _PRESCRIBER_ROOT / "src" / "models" / filename
        spec = _importlib_util.spec_from_file_location(mod_name, file_path)
        if spec is None or spec.loader is None:
            continue
        module = _importlib_util.module_from_spec(spec)
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)


_preload_prescriber_src_into_src_namespace()

# --- imports ----------------------------------------------------------------
from shared.data_ingestion.models import IngestionRun, IngestionSchedule
from shared.data_ingestion.sources.cms_opt_out import (
    CmsOptOutIngester,
    parse_opt_out_row,
    _parse_date,
    _parse_bool,
)
from shared.db.base import Base

from src.models.medicare_tables import (  # type: ignore[import]
    MedicareOptOut,
    PrescriberBase,
    SCHEMA as PRESCRIBER_SCHEMA,
)
from src.models.tables import Prescriber  # type: ignore[import]

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

_SAMPLE_FILE = Path(__file__).parent / "sample_data" / "cms_opt_out" / "sample_opt_out.json"

# ---------------------------------------------------------------------------
# SQLite compatibility helpers (LESSON-007)
# ---------------------------------------------------------------------------


class _UUIDString(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        return str(value) if value is not None else None

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:
        return uuid.UUID(str(value)) if value is not None else None


def _patch_tables_for_sqlite() -> None:
    for table in [IngestionRun.__table__, IngestionSchedule.__table__]:
        if getattr(table, "_sqlite_patched", False):
            continue
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
            elif isinstance(col.type, PG_UUID):
                col.type = _UUIDString()
            if col.server_default is not None and "gen_random_uuid" in str(col.server_default):
                col.server_default = None  # type: ignore[attr-defined]
        table._sqlite_patched = True  # type: ignore[attr-defined]

    for table in [MedicareOptOut.__table__]:
        if getattr(table, "_sqlite_patched", False):
            continue
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
            elif isinstance(col.type, PG_UUID):
                col.type = _UUIDString()
        table._sqlite_patched = True  # type: ignore[attr-defined]

    # Prescriber table has UUID PK
    for table in [Prescriber.__table__]:
        if getattr(table, "_sqlite_patched_opt", False):
            continue
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
            elif isinstance(col.type, PG_UUID):
                col.type = _UUIDString()
            if col.server_default is not None and "gen_random_uuid" in str(col.server_default):
                col.server_default = None  # type: ignore[attr-defined]
        table._sqlite_patched_opt = True  # type: ignore[attr-defined]


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

    engine = raw_engine.execution_options(
        schema_translate_map={"shared": None, PRESCRIBER_SCHEMA: None}
    )
    Base.metadata.create_all(
        engine,
        tables=[IngestionRun.__table__, IngestionSchedule.__table__],
    )
    PrescriberBase.metadata.create_all(
        engine,
        tables=[MedicareOptOut.__table__, Prescriber.__table__],
    )
    yield engine
    PrescriberBase.metadata.drop_all(
        engine, tables=[MedicareOptOut.__table__, Prescriber.__table__]
    )
    Base.metadata.drop_all(engine, tables=[IngestionRun.__table__, IngestionSchedule.__table__])
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
# Helpers
# ---------------------------------------------------------------------------


def _opt_out_row(**kwargs: Any) -> dict[str, Any]:
    base = {
        "NPI": "1234567893",
        "First Name": "JOHN",
        "Last Name": "SMITH",
        "Middle Name": "A",
        "Specialty": "Internal Medicine",
        "Opt Out Effective Date": "2023-01-01",
        "Opt Out End Date": None,
        "Order/Referring": "N",
        "Address": "123 MAIN ST",
        "City": "CHICAGO",
        "State": "IL",
        "Zip": "60601",
        "Phone": "3125551234",
    }
    base.update(kwargs)
    return base


def _seed_prescriber(session: Session, npi: str) -> Prescriber:
    p = Prescriber(
        id=uuid.uuid4(),
        npi=npi,
        entity_type="1",
        display_name=f"Test Provider {npi}",
        medicare_opt_out=False,
        offers_telehealth=False,
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(p)
    session.flush()
    return p


# ===========================================================================
# 1. Parse all fields captured
# ===========================================================================


class TestParseAllFieldsCaptured:
    def test_parse_all_fields_captured(self) -> None:
        raw = _opt_out_row()
        record = parse_opt_out_row(raw)
        assert record is not None

        expected_fields = [
            "npi", "first_name", "last_name", "middle_name", "specialty",
            "opt_out_effective_date", "opt_out_end_date", "order_referring",
            "address", "city", "state", "zip", "phone", "raw_payload",
        ]
        for field in expected_fields:
            assert field in record, f"Missing field: {field}"

    def test_raw_payload_contains_full_source_row(self) -> None:
        raw = _opt_out_row()
        record = parse_opt_out_row(raw)
        assert record is not None
        assert record["raw_payload"] == raw

    def test_parse_valid_dates(self) -> None:
        raw = _opt_out_row(**{
            "Opt Out Effective Date": "2023-01-01",
            "Opt Out End Date": "2025-12-31",
        })
        record = parse_opt_out_row(raw)
        assert record is not None
        assert record["opt_out_effective_date"] == date(2023, 1, 1)
        assert record["opt_out_end_date"] == date(2025, 12, 31)

    def test_parse_null_end_date(self) -> None:
        raw = _opt_out_row(**{"Opt Out End Date": None})
        record = parse_opt_out_row(raw)
        assert record is not None
        assert record["opt_out_end_date"] is None

    def test_order_referring_bool_true(self) -> None:
        raw = _opt_out_row(**{"Order/Referring": "Y"})
        record = parse_opt_out_row(raw)
        assert record is not None
        assert record["order_referring"] is True

    def test_order_referring_bool_false(self) -> None:
        raw = _opt_out_row(**{"Order/Referring": "N"})
        record = parse_opt_out_row(raw)
        assert record is not None
        assert record["order_referring"] is False

    def test_invalid_npi_returns_none(self) -> None:
        raw = _opt_out_row(**{"NPI": "BADNPI"})
        assert parse_opt_out_row(raw) is None

    def test_missing_npi_returns_none(self) -> None:
        raw = {"First Name": "JOHN"}
        assert parse_opt_out_row(raw) is None


# ===========================================================================
# 2. Date parsing helpers
# ===========================================================================


class TestDateParsing:
    def test_iso_date(self) -> None:
        assert _parse_date("2023-06-15") == date(2023, 6, 15)

    def test_slash_date_mdy(self) -> None:
        assert _parse_date("6/15/2023") == date(2023, 6, 15)

    def test_none_returns_none(self) -> None:
        assert _parse_date(None) is None

    def test_empty_returns_none(self) -> None:
        assert _parse_date("") is None

    def test_invalid_returns_none(self) -> None:
        assert _parse_date("not-a-date") is None


# ===========================================================================
# 3. Bool parsing
# ===========================================================================


class TestBoolParsing:
    def test_y_is_true(self) -> None:
        assert _parse_bool("Y") is True

    def test_n_is_false(self) -> None:
        assert _parse_bool("N") is False

    def test_yes_is_true(self) -> None:
        assert _parse_bool("YES") is True

    def test_none_is_none(self) -> None:
        assert _parse_bool(None) is None

    def test_unknown_is_none(self) -> None:
        assert _parse_bool("MAYBE") is None


# ===========================================================================
# 4. Cross-reference sets opt_out_status
# ===========================================================================


class TestCrossReferenceOptOutStatus:
    def test_cross_reference_sets_opt_out_status(self, db_session: Session) -> None:
        """Seed prescriber with NPI, load active opt-out, assert medicare_opt_out=True."""
        npi = "1234567893"
        _seed_prescriber(db_session, npi)

        raw = _opt_out_row(**{
            "NPI": npi,
            "Opt Out Effective Date": "2023-01-01",
            "Opt Out End Date": None,  # active — no end date
        })
        record = parse_opt_out_row(raw)
        assert record is not None

        opt_out = MedicareOptOut(
            npi=record["npi"],
            first_name=record["first_name"],
            last_name=record["last_name"],
            opt_out_effective_date=record["opt_out_effective_date"],
            opt_out_end_date=None,
            raw_payload=record["raw_payload"],
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(opt_out)
        db_session.flush()

        import asyncio
        ingester = CmsOptOutIngester(db_session)

        def _iter_one() -> Iterator[dict[str, Any]]:
            yield record

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(ingester.load(_iter_one()))
        finally:
            loop.close()

        prescriber = db_session.query(Prescriber).filter_by(npi=npi).first()
        assert prescriber is not None
        assert prescriber.medicare_opt_out is True

    def test_ended_opt_out_clears_status(self, db_session: Session) -> None:
        """opt_out_end_date in the past → medicare_opt_out=False."""
        npi = "9876543219"
        prescriber = _seed_prescriber(db_session, npi)
        prescriber.medicare_opt_out = True
        db_session.flush()

        # Opt-out that ended in the past
        past_end = date(2020, 1, 1)
        opt_out = MedicareOptOut(
            npi=npi,
            opt_out_effective_date=date(2018, 1, 1),
            opt_out_end_date=past_end,
            raw_payload={},
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(opt_out)
        db_session.flush()

        raw = _opt_out_row(**{
            "NPI": npi,
            "Opt Out Effective Date": "2018-01-01",
            "Opt Out End Date": "2020-01-01",
        })
        record = parse_opt_out_row(raw)
        assert record is not None

        import asyncio
        ingester = CmsOptOutIngester(db_session)

        def _iter_one() -> Iterator[dict[str, Any]]:
            yield record

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(ingester.load(_iter_one()))
        finally:
            loop.close()

        db_session.refresh(prescriber)
        assert prescriber.medicare_opt_out is False


# ===========================================================================
# 5. Batch upsert idempotent
# ===========================================================================


class TestBatchUpsertIdempotent:
    def test_batch_upsert_idempotent(self, db_session: Session) -> None:
        """Loading the sample file twice yields the same opt-out row count."""
        sample_data = json.loads(_SAMPLE_FILE.read_text())

        def _iter() -> Iterator[dict[str, Any]]:
            for raw in sample_data:
                parsed = parse_opt_out_row(raw)
                if parsed is not None:
                    yield parsed

        import asyncio
        ingester = CmsOptOutIngester(db_session)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(ingester.load(_iter()))
            count1 = db_session.query(MedicareOptOut).count()
            loop.run_until_complete(ingester.load(_iter()))
            count2 = db_session.query(MedicareOptOut).count()
        finally:
            loop.close()

        assert count1 == count2, f"Idempotency broken: {count1} vs {count2}"
        assert count1 > 0


# ===========================================================================
# 6. Sample data smoke test
# ===========================================================================


class TestSampleDataSmokeTest:
    def test_sample_has_active_opt_out(self) -> None:
        data = json.loads(_SAMPLE_FILE.read_text())
        active = [r for r in data if r.get("Opt Out End Date") is None]
        assert len(active) >= 1

    def test_sample_has_ended_opt_out(self) -> None:
        data = json.loads(_SAMPLE_FILE.read_text())
        ended = [r for r in data if r.get("Opt Out End Date") is not None]
        assert len(ended) >= 1

    def test_all_sample_rows_have_valid_npi(self) -> None:
        data = json.loads(_SAMPLE_FILE.read_text())
        parsed = [parse_opt_out_row(r) for r in data]
        assert all(p is not None for p in parsed), "Some sample rows failed to parse"
        for p in parsed:
            assert p is not None
            assert len(p["npi"]) == 10
            assert p["npi"].isdigit()

    def test_global_ref_no_tenant_id(self) -> None:
        col_names = [c.name for c in MedicareOptOut.__table__.columns]
        assert "tenant_id" not in col_names, (
            "Global ref table must NOT have tenant_id (LESSON-011)"
        )


# ===========================================================================
# 7. Download method
# ===========================================================================


class TestOptOutDownload:
    """download() exercises the v1 data.cms.gov API — dataset + pagination.

    The test references the live constants from the production loader
    (``_API_BASE_URL`` derived from ``_DATASET_ID``, ``_PAGE_SIZE``) so
    a future dataset-ID migration or page-size tweak keeps the mocks
    in sync automatically.
    """

    @pytest.mark.asyncio
    async def test_download_paginates_and_merges(self, tmp_path: Path) -> None:
        """CmsOptOutIngester.download() paginates and writes JSON file."""
        import shared.data_ingestion.sources.cms_opt_out as mod

        page_size = mod._PAGE_SIZE
        page1 = [_opt_out_row()] * page_size
        # page2 is smaller than page_size so the pagination loop terminates
        page2 = [_opt_out_row(**{"NPI": "5555555557"})] * 1_234

        mock_db = MagicMock()

        with respx.mock(assert_all_called=False) as mock_router:
            mock_router.get(
                mod._API_BASE_URL,
                params={"size": str(page_size), "offset": "0"},
            ).mock(return_value=httpx.Response(200, json=page1))
            mock_router.get(
                mod._API_BASE_URL,
                params={"size": str(page_size), "offset": str(page_size)},
            ).mock(return_value=httpx.Response(200, json=page2))

            ingester = CmsOptOutIngester(db_session=mock_db)
            orig = mod._DEST_DIR
            mod._DEST_DIR = tmp_path
            try:
                path = await ingester.download()
            finally:
                mod._DEST_DIR = orig

        data = json.loads(path.read_text())
        assert len(data) == page_size + 1_234

    @pytest.mark.asyncio
    async def test_download_terminates_on_empty_page(self, tmp_path: Path) -> None:
        import shared.data_ingestion.sources.cms_opt_out as mod

        page_size = mod._PAGE_SIZE
        mock_db = MagicMock()

        with respx.mock(assert_all_called=False) as mock_router:
            mock_router.get(
                mod._API_BASE_URL,
                params={"size": str(page_size), "offset": "0"},
            ).mock(return_value=httpx.Response(200, json=[]))

            ingester = CmsOptOutIngester(db_session=mock_db)
            orig = mod._DEST_DIR
            mod._DEST_DIR = tmp_path
            try:
                path = await ingester.download()
            finally:
                mod._DEST_DIR = orig

        data = json.loads(path.read_text())
        assert len(data) == 0


# ===========================================================================
# 8. parse() method coverage
# ===========================================================================


class TestOptOutParse:
    def test_parse_json_file(self, tmp_path: Path) -> None:
        """parse() reads JSON file and yields valid records, skips invalid ones."""
        json_file = tmp_path / "opt_out.json"
        records = [
            _opt_out_row(),
            {"NPI": "BADNPI"},  # invalid — should be skipped
        ]
        json_file.write_text(json.dumps(records))

        mock_db = MagicMock()
        ingester = CmsOptOutIngester(db_session=mock_db)
        parsed = list(ingester.parse(json_file))
        assert len(parsed) == 1
        assert parsed[0]["npi"] == "1234567893"


# ===========================================================================
# 9. Additional date/bool edge cases
# ===========================================================================


class TestAdditionalEdgeCases:
    def test_parse_date_slash_with_wrong_parts_returns_none(self) -> None:
        """Slash date with only 2 parts → None."""
        assert _parse_date("01/2023") is None

    def test_parse_date_valid_iso_with_bad_value(self) -> None:
        """YYYY-99-99 matches regex but fails date() constructor → None."""
        assert _parse_date("2023-99-99") is None

    def test_parse_date_slash_invalid_values_returns_none(self) -> None:
        """M/D/YYYY with non-integer parts → ValueError → None."""
        assert _parse_date("XX/YY/2023") is None

    def test_parse_bool_false_variants(self) -> None:
        assert _parse_bool("FALSE") is False
        assert _parse_bool("0") is False
        assert _parse_bool("no") is False

    def test_parse_bool_true_variants(self) -> None:
        assert _parse_bool("true") is True
        assert _parse_bool("1") is True

    def test_parse_opt_out_row_alternate_key_names(self) -> None:
        """Lowercase 'npi' key should also work."""
        raw = {
            "npi": "1234567893",
            "first_name": "JOHN",
            "last_name": "SMITH",
        }
        record = parse_opt_out_row(raw)
        assert record is not None
        assert record["npi"] == "1234567893"

    def test_load_flushes_empty_batch_returns_zero(self, db_session: Session) -> None:
        """Loading empty iterator returns zero inserted without error."""
        import asyncio

        ingester = CmsOptOutIngester(db_session)
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(ingester.load(iter([])))
        finally:
            loop.close()

        assert result.records_inserted == 0

    def test_load_large_batch_triggers_flush(self, db_session: Session) -> None:
        """Batches >= _BATCH_SIZE flush mid-stream."""
        import asyncio

        def _big_iter() -> Iterator[dict[str, Any]]:
            for i in range(1100):
                npi = str(1000000000 + i).zfill(10)
                rec = parse_opt_out_row({
                    "NPI": npi,
                    "First Name": "TEST",
                    "Last Name": "PROVIDER",
                    "Opt Out Effective Date": "2023-01-01",
                })
                if rec is not None:
                    yield rec

        ingester = CmsOptOutIngester(db_session)
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(ingester.load(_big_iter()))
        finally:
            loop.close()
        assert result.records_inserted >= 1000

    def test_cross_ref_with_empty_npi_list_returns_zero(self, db_session: Session) -> None:
        """_update_prescriber_opt_out_status with empty list → 0."""
        ingester = CmsOptOutIngester(db_session)
        from datetime import datetime, timezone
        count = ingester._update_prescriber_opt_out_status([], datetime.now(timezone.utc))
        assert count == 0

    def test_load_postgresql_upsert_path(self) -> None:
        """When dialect reports postgresql, pg_insert ON CONFLICT path is used."""
        import asyncio
        from unittest.mock import MagicMock

        record = parse_opt_out_row({
            "NPI": "1234567893",
            "First Name": "JOHN",
            "Last Name": "SMITH",
            "Opt Out Effective Date": "2023-01-01",
        })
        assert record is not None

        mock_db = MagicMock()
        mock_db.connection.return_value.dialect.name = "postgresql"

        ingester = CmsOptOutIngester(db_session=mock_db)
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(ingester.load(iter([record])))
        finally:
            loop.close()
        assert result.records_inserted == 1
        mock_db.execute.assert_called()
