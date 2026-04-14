"""Tests for the CMS NADAC ingestion pipeline.

Covers:
  - Paginated Socrata API → merges multiple pages into one JSON file
  - Decimal precision: NADAC_Per_Unit stays Decimal, never float
  - History row created on price change
  - History row NOT created when price unchanged (idempotency)
  - NDC normalization via T3 normalize_ndc_11() helper
  - Invalid explanation_code rejection
  - Full idempotency: load twice → same row count
  - 10 synthetic records covering brand, generic, biosimilar, OTC, LTC (I),
    chain (C), generic-with-reference, discontinued, multiple price changes

SQLAlchemy isolation:
  SAVEPOINT-based per LESSON-001.
  _UUIDString TypeDecorator per LESSON-007.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from collections.abc import Iterator
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
import httpx
from sqlalchemy import BigInteger, Integer, JSON, String, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import TypeDecorator

# --- env defaults so shared.config does not raise --------------------------
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost/")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")
os.environ.setdefault(
    "ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM="
)

# --- path setup so src.* and shared.* resolve -------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DRUG_DB_ROOT = _REPO_ROOT / "modules" / "drug-database"

for _p in (str(_REPO_ROOT), str(_DRUG_DB_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# --- imports ----------------------------------------------------------------
from shared.data_ingestion.models import IngestionRun, IngestionSchedule
from shared.data_ingestion.sources.cms_nadac import (
    CMSNADACIngester,
    _parse_record,
    _parse_date,
    _parse_decimal,
)
from shared.data_ingestion.sources.fda_ndc import normalize_ndc_11
from shared.db.base import Base

from src.models.pricing_tables import (  # type: ignore[import]
    DrugNADACPricing,
    DrugNADACPricingHistory,
    PricingBase,
    SCHEMA as PRICING_SCHEMA,
)
from src.services.pricing_ingestion import NADACIngestionService  # type: ignore[import]

# ---------------------------------------------------------------------------
# Sample data path
# ---------------------------------------------------------------------------

_SAMPLE_DIR = Path(__file__).parent / "sample_data" / "cms_nadac"
_SAMPLE_JSON = _SAMPLE_DIR / "sample_nadac.json"

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


def _patch_pricing_tables_for_sqlite() -> None:
    """BigInteger PKs → Integer for SQLite autoincrement."""
    for table in [
        DrugNADACPricing.__table__,
        DrugNADACPricingHistory.__table__,
    ]:
        if getattr(table, "_sqlite_patched", False):
            continue
        for col in table.columns:
            if isinstance(col.type, BigInteger) and col.primary_key:
                col.type = Integer()
        table._sqlite_patched = True  # type: ignore[attr-defined]


_patch_ingestion_tables_for_sqlite()
_patch_pricing_tables_for_sqlite()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _engine():
    """Session-scoped SQLite engine with schema mapping for drug_database."""
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
        schema_translate_map={"shared": None, PRICING_SCHEMA: None}
    )

    Base.metadata.create_all(
        engine,
        tables=[IngestionRun.__table__, IngestionSchedule.__table__],
    )
    PricingBase.metadata.create_all(engine)

    yield engine

    PricingBase.metadata.drop_all(engine)
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
# Helper: minimal valid NADAC row dict
# ---------------------------------------------------------------------------


def _nadac_row(
    ndc_11: str = "00069420016",
    price: str = "0.841200",
    eff_date: date = date(2026, 1, 1),
    as_of: date = date(2026, 3, 26),
    **kwargs: Any,
) -> dict[str, Any]:
    return {
        "ndc_11": ndc_11,
        "ndc_description": "TEST DRUG",
        "nadac_per_unit": Decimal(price),
        "effective_date": eff_date,
        "pricing_unit": "EA",
        "pharmacy_type_indicator": "C",
        "otc": "N",
        "explanation_code": "1",
        "classification": "B",
        "generic_nadac_per_unit": None,
        "generic_effective_date": None,
        "as_of_date": as_of,
        **kwargs,
    }


# ===========================================================================
# 1. Date parsing
# ===========================================================================


class TestDateParsing:
    def test_iso_date(self) -> None:
        assert _parse_date("2026-03-26") == date(2026, 3, 26)

    def test_slash_date(self) -> None:
        assert _parse_date("2026/03/26") == date(2026, 3, 26)

    def test_none_returns_none(self) -> None:
        assert _parse_date(None) is None

    def test_empty_returns_none(self) -> None:
        assert _parse_date("") is None

    def test_invalid_returns_none(self) -> None:
        assert _parse_date("not-a-date") is None


# ===========================================================================
# 2. Decimal precision — LESSON for financial-precision.md
# ===========================================================================


class TestDecimalPrecisionNADACPerUnit:
    def test_decimal_precision_NADAC_per_unit(self) -> None:
        """'2.14567' string must become Decimal('2.145670'), never float."""
        result = _parse_decimal("2.14567")
        assert isinstance(result, Decimal), "Must be Decimal, not float"
        assert result == Decimal("2.145670")
        # Verify ROUND_HALF_UP: 2.1456789 → 2.145679
        result2 = _parse_decimal("2.1456789")
        assert result2 == Decimal("2.145679")

    def test_parse_decimal_from_int(self) -> None:
        result = _parse_decimal(5)
        assert result == Decimal("5.000000")

    def test_parse_decimal_none_returns_none(self) -> None:
        assert _parse_decimal(None) is None

    def test_parse_decimal_empty_string_returns_none(self) -> None:
        assert _parse_decimal("") is None

    def test_parse_decimal_non_numeric_returns_none(self) -> None:
        assert _parse_decimal("N/A") is None


# ===========================================================================
# 3. Record parsing from raw API dict
# ===========================================================================


class TestParseRecord:
    def test_parse_full_record(self) -> None:
        """All 12 fields from a typical API result dict are parsed."""
        raw = {
            "ndc": "00069420016",
            "ndc_description": "NORVASC 5MG TABLET",
            "nadac_per_unit": "0.841200",
            "effective_date": "2026-01-01",
            "pricing_unit": "EA",
            "pharmacy_type_indicator": "C",
            "otc": "N",
            "explanation_code": "1",
            "classification_for_rate_setting": "B",
            "corresponding_generic_drug_nadac_per_unit": "0.124300",
            "corresponding_generic_drug_effective_date": "2026-01-01",
            "as_of_date": "2026-03-26",
        }
        record = _parse_record(raw)
        assert record is not None
        assert record["ndc_11"] == "00069420016"
        assert record["ndc_description"] == "NORVASC 5MG TABLET"
        assert isinstance(record["nadac_per_unit"], Decimal)
        assert record["nadac_per_unit"] == Decimal("0.841200")
        assert record["effective_date"] == date(2026, 1, 1)
        assert record["pricing_unit"] == "EA"
        assert record["pharmacy_type_indicator"] == "C"
        assert record["otc"] == "N"
        assert record["explanation_code"] == "1"
        assert record["classification"] == "B"
        assert isinstance(record["generic_nadac_per_unit"], Decimal)
        assert record["generic_effective_date"] == date(2026, 1, 1)
        assert record["as_of_date"] == date(2026, 3, 26)

    def test_parse_record_missing_ndc_returns_none(self) -> None:
        raw = {"nadac_per_unit": "1.0", "effective_date": "2026-01-01", "as_of_date": "2026-03-26"}
        assert _parse_record(raw) is None

    def test_parse_record_missing_price_returns_none(self) -> None:
        raw = {"ndc": "00069420016", "effective_date": "2026-01-01", "as_of_date": "2026-03-26"}
        assert _parse_record(raw) is None

    def test_parse_record_invalid_ndc_returns_none(self) -> None:
        raw = {
            "ndc": "BADNDC",
            "nadac_per_unit": "1.0",
            "effective_date": "2026-01-01",
            "as_of_date": "2026-03-26",
        }
        assert _parse_record(raw) is None

    def test_parse_rejects_invalid_explanation_code_via_service(
        self, db_session: Session
    ) -> None:
        """Explanation code with special chars triggers validation error in service."""
        svc = NADACIngestionService(db_session)
        error_samples: list[dict[str, Any]] = []
        # Row with invalid explanation_code containing SQL injection attempt
        row_with_bad_code = {
            "ndc_11": "00069420016",
            "ndc_description": "TEST",
            "nadac_per_unit": "1.000000",
            "effective_date": date(2026, 1, 1),
            "pricing_unit": "EA",
            "pharmacy_type_indicator": "C",
            "otc": "N",
            "explanation_code": "'; DROP TABLE--",
            "classification": "B",
            "generic_nadac_per_unit": None,
            "generic_effective_date": None,
            "as_of_date": date(2026, 3, 26),
        }
        # Validation should raise ValueError for the explanation_code
        with pytest.raises(ValueError, match="explanation_code"):
            svc._validate_nadac_row(row_with_bad_code)


# ===========================================================================
# 4. NDC normalization via T3 helper
# ===========================================================================


class TestNDCNormalizedViaT3Helper:
    def test_ndc_normalized_via_T3_helper(self) -> None:
        """confirm cross-module dep works — normalize_ndc_11 from T3 is used."""
        # 4-4-2 format should be padded to 11 digits
        result = normalize_ndc_11("0069-4200-16")
        assert result == "00069420016"
        assert len(result) == 11

    def test_parse_record_calls_normalize(self) -> None:
        """_parse_record calls normalize_ndc_11; 4-4-2 NDC is normalized."""
        raw = {
            "ndc": "0069-4200-16",
            "nadac_per_unit": "1.0",
            "effective_date": "2026-01-01",
            "as_of_date": "2026-03-26",
        }
        record = _parse_record(raw)
        assert record is not None
        assert record["ndc_11"] == "00069420016"


# ===========================================================================
# 5. Paginated API — mock 3 pages with respx
# ===========================================================================


class TestPaginatedAPIMergesPages:
    @pytest.mark.asyncio
    async def test_paginated_api_merges_pages(self, tmp_path: Path) -> None:
        """CMSNADACIngester.download() merges multiple API pages into one JSON file."""
        page1 = [
            {
                "ndc": "00069420016",
                "ndc_description": "DRUG A",
                "nadac_per_unit": "1.00",
                "effective_date": "2026-01-01",
                "as_of_date": "2026-03-26",
            }
        ] * 8_000  # page size (CMS Socrata API cap)
        page2 = [
            {
                "ndc": "59762172001",
                "ndc_description": "DRUG B",
                "nadac_per_unit": "2.00",
                "effective_date": "2026-01-01",
                "as_of_date": "2026-03-26",
            }
        ] * 8_000
        page3 = [
            {
                "ndc": "57894003001",
                "ndc_description": "DRUG C",
                "nadac_per_unit": "3.00",
                "effective_date": "2026-01-01",
                "as_of_date": "2026-03-26",
            }
        ] * 5_000  # partial page — signals end

        # Patch _DEST_DIR to tmp_path inside the ingester
        mock_db = MagicMock()

        with respx.mock(assert_all_called=True) as mock_router:
            api_base = (
                "https://data.medicaid.gov/api/1/datastore/query"
                "/fbb83258-11c7-47f5-8b18-5f8e79f7e704/0"
            )
            mock_router.get(api_base, params={"limit": "8000", "offset": "0"}).mock(
                return_value=httpx.Response(200, json={"results": page1, "count": 21000})
            )
            mock_router.get(api_base, params={"limit": "8000", "offset": "8000"}).mock(
                return_value=httpx.Response(200, json={"results": page2, "count": 21000})
            )
            mock_router.get(api_base, params={"limit": "8000", "offset": "16000"}).mock(
                return_value=httpx.Response(200, json={"results": page3, "count": 21000})
            )

            ingester = CMSNADACIngester(db_session=mock_db)
            # Override destination directory
            import shared.data_ingestion.sources.cms_nadac as nadac_mod
            original_dest_dir = nadac_mod._DEST_DIR
            nadac_mod._DEST_DIR = tmp_path
            try:
                path = await ingester.download()
            finally:
                nadac_mod._DEST_DIR = original_dest_dir

        assert path.exists()
        data = json.loads(path.read_text())
        assert len(data) == 21_000  # 8K + 8K + 5K


# ===========================================================================
# 6. History row behavior
# ===========================================================================


class TestHistoryRowBehavior:
    def test_history_row_created_on_price_change(self, db_session: Session) -> None:
        """Upserting with changed price creates a new history row."""
        svc = NADACIngestionService(db_session)
        row_v1 = _nadac_row(price="1.000000")
        row_v2 = _nadac_row(
            price="1.500000",
            as_of=date(2026, 6, 25),
            eff_date=date(2026, 4, 1),
        )

        # First insert
        svc._upsert_batch([row_v1], [])
        db_session.flush()
        h1 = db_session.query(DrugNADACPricingHistory).count()
        assert h1 == 1

        # Second insert with changed price
        svc._upsert_batch([row_v2], [])
        db_session.flush()
        h2 = db_session.query(DrugNADACPricingHistory).count()
        assert h2 == 2

    def test_history_row_NOT_created_when_price_unchanged(
        self, db_session: Session
    ) -> None:
        """Re-upserting the exact same row does NOT create a duplicate history row."""
        svc = NADACIngestionService(db_session)
        row = _nadac_row(ndc_11="00093745798")

        svc._upsert_batch([row], [])
        db_session.flush()
        count_after_first = db_session.query(DrugNADACPricingHistory).filter_by(
            ndc_11="00093745798"
        ).count()
        assert count_after_first == 1

        # Re-ingest same row — ON CONFLICT DO NOTHING on history
        svc._upsert_batch([row], [])
        db_session.flush()
        count_after_second = db_session.query(DrugNADACPricingHistory).filter_by(
            ndc_11="00093745798"
        ).count()
        assert count_after_second == 1  # must NOT have duplicated


# ===========================================================================
# 7. Idempotency: load full sample twice → same row count
# ===========================================================================


class TestIdempotency:
    @pytest.mark.asyncio
    async def test_load_twice_same_row_count(self, db_session: Session) -> None:
        """Loading the sample JSON twice yields the same current-row count."""
        svc = NADACIngestionService(db_session)
        records_from_file = json.loads(_SAMPLE_JSON.read_text())

        def _iter_records() -> Iterator[dict[str, Any]]:
            from shared.data_ingestion.sources.cms_nadac import _parse_record
            for raw in records_from_file:
                parsed = _parse_record(raw)
                if parsed is not None:
                    yield parsed

        result1 = await svc.load_records(_iter_records(), source_name="cms_nadac")
        first_count = db_session.query(DrugNADACPricing).count()

        result2 = await svc.load_records(_iter_records(), source_name="cms_nadac")
        second_count = db_session.query(DrugNADACPricing).count()

        assert first_count == second_count, (
            f"Idempotency broken: {first_count} rows after first load, "
            f"{second_count} after second"
        )
        assert first_count > 0


# ===========================================================================
# 8. Sample data covers all required scenarios
# ===========================================================================


class TestSampleDataCoverage:
    def test_sample_has_10_records(self) -> None:
        data = json.loads(_SAMPLE_JSON.read_text())
        assert len(data) == 10

    def test_sample_has_brand_drug(self) -> None:
        data = json.loads(_SAMPLE_JSON.read_text())
        brands = [r for r in data if r.get("classification_for_rate_setting") == "B"]
        assert len(brands) >= 1

    def test_sample_has_generic_drug(self) -> None:
        data = json.loads(_SAMPLE_JSON.read_text())
        generics = [r for r in data if r.get("classification_for_rate_setting") == "G"]
        assert len(generics) >= 1

    def test_sample_has_biosimilar(self) -> None:
        data = json.loads(_SAMPLE_JSON.read_text())
        biosims = [r for r in data if "BIO" in (r.get("classification_for_rate_setting") or "")]
        assert len(biosims) >= 1

    def test_sample_has_otc_drug(self) -> None:
        data = json.loads(_SAMPLE_JSON.read_text())
        otc = [r for r in data if r.get("otc") == "Y"]
        assert len(otc) >= 1

    def test_sample_has_independent_pharmacy(self) -> None:
        data = json.loads(_SAMPLE_JSON.read_text())
        ind = [r for r in data if r.get("pharmacy_type_indicator") == "I"]
        assert len(ind) >= 1

    def test_sample_has_chain_pharmacy(self) -> None:
        data = json.loads(_SAMPLE_JSON.read_text())
        chain = [r for r in data if r.get("pharmacy_type_indicator") == "C"]
        assert len(chain) >= 1

    def test_sample_has_generic_with_reference_price(self) -> None:
        data = json.loads(_SAMPLE_JSON.read_text())
        with_ref = [r for r in data if r.get("corresponding_generic_drug_nadac_per_unit")]
        assert len(with_ref) >= 1

    def test_sample_has_discontinued_drug(self) -> None:
        """A drug with an effective_date in the past (Trulicity end-2023)."""
        data = json.loads(_SAMPLE_JSON.read_text())
        old_eff = [r for r in data if r.get("effective_date", "").startswith("2023")]
        assert len(old_eff) >= 1

    def test_sample_has_multiple_price_versions_same_ndc(self) -> None:
        """Two records for same NDC with different prices."""
        data = json.loads(_SAMPLE_JSON.read_text())
        ndcs = [r["ndc"] for r in data]
        duplicates = [n for n in set(ndcs) if ndcs.count(n) > 1]
        assert len(duplicates) >= 1
