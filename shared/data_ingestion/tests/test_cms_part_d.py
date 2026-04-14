"""Tests for CMS Medicare Part D Prescriber Utilization ingestion.

Covers:
  - All 50+ fields captured from source row
  - Decimal money columns — NEVER float
  - Decimal precision round-trip: "12345.67" stays "12345.67"
  - Negative values allowed (adjustment rows)
  - Null handling: missing columns → None, not 0
  - NPI plaintext (LESSON-010)
  - Batch upsert idempotency
  - Checksum skip
  - Global ref — two tenants see same row (no TenantScopedMixin)
  - raw_payload contains full source row
  - No float in source module

SQLAlchemy isolation: SAVEPOINT-based per LESSON-001.
_UUIDString TypeDecorator per LESSON-007 (if any UUID columns).
"""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import os
import sys
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx
import respx
from sqlalchemy import JSON, Integer, String, create_engine, event, text
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

# --- imports ----------------------------------------------------------------
from shared.data_ingestion.models import IngestionRun, IngestionSchedule
from shared.data_ingestion.sources.cms_part_d_prescriber import (
    CmsPartDPrescriberIngester,
    parse_part_d_row,
    _parse_decimal_2,
    _parse_decimal_4,
    _parse_int,
)
from shared.db.base import Base

# ORM models from prescriber-directory
from src.models.medicare_tables import (  # type: ignore[import]
    MedicarePartDUtilization,
    PrescriberBase,
    SCHEMA as PRESCRIBER_SCHEMA,
)

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

_SAMPLE_FILE = Path(__file__).parent / "sample_data" / "cms_part_d" / "sample_part_d.json"

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

    # Patch medicare tables — JSONB → JSON for SQLite
    for table in [MedicarePartDUtilization.__table__]:
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
        tables=[MedicarePartDUtilization.__table__],
    )
    yield engine
    PrescriberBase.metadata.drop_all(engine, tables=[MedicarePartDUtilization.__table__])
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
# Helper: minimal valid Part D row dict
# ---------------------------------------------------------------------------

def _part_d_row(**kwargs: Any) -> dict[str, Any]:
    base = {
        "Prscrbr_NPI": "1234567893",
        "Prscrbr_Last_Org_Name": "SMITH",
        "Prscrbr_First_Name": "JOHN",
        "Prscrbr_City": "CHICAGO",
        "Prscrbr_State_Abrvtn": "IL",
        "Prscrbr_State_FIPS": "17",
        "Prscrbr_Zip5": "60601",
        "Prscrbr_RUCA": "1",
        "Prscrbr_Cntry": "US",
        "Prscrbr_Type": "Internal Medicine",
        "Prscrbr_Type_Src": "T",
        "Tot_Clms": "450",
        "Tot_30day_Fills": "380",
        "Tot_Day_Suply": "11400",
        "Tot_Drug_Cst": "12345.67",
        "Tot_Benes": "120",
        "Brnd_Clms": "180",
        "Brnd_Drug_Cst": "8500.00",
        "Gnrc_Clms": "250",
        "Gnrc_Drug_Cst": "3500.00",
        "Othr_Clms": "20",
        "Othr_Drug_Cst": "345.67",
        "MAPD_Clms": "200",
        "MAPD_Drug_Cst": "6000.00",
        "PDP_Clms": "250",
        "PDP_Drug_Cst": "6345.67",
        "LIS_Clms": "80",
        "LIS_Drug_Cst": "1200.00",
        "Opioid_Clms": "30",
        "Opioid_Drug_Cst": "450.00",
        "Opioid_Prscrbr_Rate": "0.0667",
        "Opioid_LA_Clms": "5",
        "Opioid_LA_Drug_Cst": "150.00",
        "Antbtc_Clms": "45",
        "Antbtc_Drug_Cst": "320.00",
        "Antpsycht_GE65_Clms": "10",
        "Antpsycht_GE65_Drug_Cst": "800.00",
        "Bene_Avg_Age": "72",
        "Bene_Avg_Risk_Scre": "1.2345",
        "Bene_Race_Wht_Cnt": "85",
        "Bene_Race_Black_Cnt": "20",
        "Bene_Race_Api_Cnt": "8",
        "Bene_Race_Hspnc_Cnt": "5",
        "Bene_Race_Natind_Cnt": "1",
        "Bene_Race_Othr_Cnt": "1",
        "Bene_Dual_Cnt": "30",
        "Bene_NDUAL_Cnt": "90",
        "GE65_Tot_Clms": "400",
        "GE65_Tot_Drug_Cst": "11000.00",
        "GE65_Brnd_Clms": "160",
        "GE65_Brnd_Drug_Cst": "7500.00",
        "GE65_Gnrc_Clms": "220",
        "GE65_Gnrc_Drug_Cst": "3200.00",
        "GE65_Othr_Clms": "20",
        "GE65_Othr_Drug_Cst": "300.00",
    }
    base.update(kwargs)
    return base


# ===========================================================================
# 1. Parse all 50+ fields
# ===========================================================================


class TestParseAllFieldsCaptured:
    def test_parse_all_50_plus_fields_captured(self) -> None:
        """Every documented field must be present in the parsed dict."""
        raw = _part_d_row()
        record = parse_part_d_row(raw, year=2023)
        assert record is not None

        expected_fields = [
            "npi", "year", "prscrbr_last_org_name", "prscrbr_first_name",
            "prscrbr_city", "prscrbr_state_abrvtn", "prscrbr_state_fips",
            "prscrbr_zip5", "prscrbr_ruca", "prscrbr_cntry",
            "prscrbr_type", "prscrbr_type_src",
            "tot_clms", "tot_30day_fills", "tot_day_suply", "tot_drug_cst", "tot_benes",
            "brnd_clms", "brnd_drug_cst", "gnrc_clms", "gnrc_drug_cst",
            "othr_clms", "othr_drug_cst",
            "mapd_clms", "mapd_drug_cst", "pdp_clms", "pdp_drug_cst",
            "lis_clms", "lis_drug_cst",
            "opioid_clms", "opioid_drug_cst", "opioid_prscrbr_rate",
            "opioid_la_clms", "opioid_la_drug_cst",
            "antbtc_clms", "antbtc_drug_cst",
            "antpsycht_ge65_clms", "antpsycht_ge65_drug_cst",
            "bene_avg_age", "bene_avg_risk_scre",
            "bene_race_wht_cnt", "bene_race_black_cnt", "bene_race_api_cnt",
            "bene_race_hspnc_cnt", "bene_race_natind_cnt", "bene_race_othr_cnt",
            "bene_dual_cnt", "bene_ndual_cnt",
            "ge65_tot_clms", "ge65_tot_drug_cst",
            "ge65_brnd_clms", "ge65_brnd_drug_cst",
            "ge65_gnrc_clms", "ge65_gnrc_drug_cst",
            "ge65_othr_clms", "ge65_othr_drug_cst",
            "raw_payload",
        ]
        for field in expected_fields:
            assert field in record, f"Missing field: {field}"

    def test_raw_payload_contains_full_source_row(self) -> None:
        raw = _part_d_row()
        record = parse_part_d_row(raw, year=2023)
        assert record is not None
        assert record["raw_payload"] == raw

    def test_year_stored_from_argument(self) -> None:
        raw = _part_d_row()
        record = parse_part_d_row(raw, year=2022)
        assert record is not None
        assert record["year"] == 2022


# ===========================================================================
# 2. Decimal money — never float
# ===========================================================================


class TestDecimalMoneyNeverFloat:
    def test_decimal_money_never_float(self) -> None:
        raw = _part_d_row()
        record = parse_part_d_row(raw, year=2023)
        assert record is not None
        money_fields = [
            "tot_drug_cst", "brnd_drug_cst", "gnrc_drug_cst", "othr_drug_cst",
            "mapd_drug_cst", "pdp_drug_cst", "lis_drug_cst",
            "opioid_drug_cst", "opioid_la_drug_cst", "antbtc_drug_cst",
            "antpsycht_ge65_drug_cst",
            "ge65_tot_drug_cst", "ge65_brnd_drug_cst", "ge65_gnrc_drug_cst",
            "ge65_othr_drug_cst",
        ]
        for field in money_fields:
            val = record.get(field)
            if val is not None:
                assert isinstance(val, Decimal), (
                    f"{field} must be Decimal, got {type(val).__name__}"
                )
                assert not isinstance(val, float), f"{field} must NOT be float"

    def test_risk_score_is_decimal_not_float(self) -> None:
        raw = _part_d_row()
        record = parse_part_d_row(raw, year=2023)
        assert record is not None
        assert isinstance(record["bene_avg_risk_scre"], Decimal)

    def test_opioid_rate_is_decimal_not_float(self) -> None:
        raw = _part_d_row()
        record = parse_part_d_row(raw, year=2023)
        assert record is not None
        assert isinstance(record["opioid_prscrbr_rate"], Decimal)


# ===========================================================================
# 3. Decimal precision round-trip
# ===========================================================================


class TestDecimalPrecisionRoundtrip:
    def test_decimal_precision_preserved(self) -> None:
        """'12345.67' must remain exactly Decimal('12345.67') after parsing."""
        raw = _part_d_row(**{"Tot_Drug_Cst": "12345.67"})
        record = parse_part_d_row(raw, year=2023)
        assert record is not None
        assert record["tot_drug_cst"] == Decimal("12345.67")

    def test_parse_decimal_2_precision(self) -> None:
        result = _parse_decimal_2("12345.67")
        assert isinstance(result, Decimal)
        assert result == Decimal("12345.67")

    def test_parse_decimal_4_precision(self) -> None:
        result = _parse_decimal_4("1.2345")
        assert isinstance(result, Decimal)
        assert result == Decimal("1.2345")

    def test_parse_decimal_round_half_up(self) -> None:
        # 12345.675 should round up to 12345.68
        result = _parse_decimal_2("12345.675")
        assert result == Decimal("12345.68")

    def test_parse_decimal_none_returns_none(self) -> None:
        assert _parse_decimal_2(None) is None

    def test_parse_decimal_empty_returns_none(self) -> None:
        assert _parse_decimal_2("") is None


# ===========================================================================
# 4. Negative values allowed
# ===========================================================================


class TestNegativeValuesAllowed:
    def test_negative_values_allowed_and_preserved(self) -> None:
        raw = _part_d_row(**{"Tot_Drug_Cst": "-500.00", "Othr_Drug_Cst": "-8000.00"})
        record = parse_part_d_row(raw, year=2023)
        assert record is not None
        assert record["tot_drug_cst"] == Decimal("-500.00")
        assert record["othr_drug_cst"] == Decimal("-8000.00")


# ===========================================================================
# 5. Null handling
# ===========================================================================


class TestNullHandling:
    def test_null_handling_missing_columns_return_none(self) -> None:
        """Missing optional columns → None, not 0."""
        raw = {
            "Prscrbr_NPI": "1234567893",
            "Prscrbr_Type": "Internal Medicine",
        }
        record = parse_part_d_row(raw, year=2023)
        assert record is not None
        assert record["tot_drug_cst"] is None
        assert record["mapd_clms"] is None
        assert record["opioid_prscrbr_rate"] is None
        assert record["bene_avg_risk_scre"] is None

    def test_explicit_null_api_fields_return_none(self) -> None:
        raw = _part_d_row(**{"MAPD_Clms": None, "MAPD_Drug_Cst": None})
        record = parse_part_d_row(raw, year=2023)
        assert record is not None
        assert record["mapd_clms"] is None
        assert record["mapd_drug_cst"] is None


# ===========================================================================
# 6. NPI plaintext (LESSON-010)
# ===========================================================================


class TestNpiPlaintext:
    def test_npi_plaintext_not_encrypted(self) -> None:
        """NPI must be stored as a plain 10-digit string — LESSON-010."""
        raw = _part_d_row()
        record = parse_part_d_row(raw, year=2023)
        assert record is not None
        npi = record["npi"]
        assert isinstance(npi, str), "NPI must be str"
        assert len(npi) == 10, "NPI must be 10 digits"
        assert npi.isdigit(), "NPI must be all digits"
        # Must not be wrapped in an encryption envelope
        assert not npi.startswith("{"), "NPI must not be encrypted JSON"

    def test_invalid_npi_returns_none(self) -> None:
        raw = _part_d_row(**{"Prscrbr_NPI": "BADNPI"})
        assert parse_part_d_row(raw, year=2023) is None

    def test_short_npi_returns_none(self) -> None:
        raw = _part_d_row(**{"Prscrbr_NPI": "12345"})
        assert parse_part_d_row(raw, year=2023) is None


# ===========================================================================
# 7. Batch upsert idempotent
# ===========================================================================


class TestBatchUpsertIdempotent:
    def test_batch_upsert_idempotent(self, db_session: Session) -> None:
        """Loading the sample file twice yields the same row count."""
        sample_data = json.loads(_SAMPLE_FILE.read_text())

        def _iter(year: int) -> Iterator[dict[str, Any]]:
            for raw in sample_data:
                parsed = parse_part_d_row(raw, year=year)
                if parsed is not None:
                    yield parsed

        ingester = CmsPartDPrescriberIngester(db_session, year=2023)

        import asyncio
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(ingester.load(_iter(2023)))
            count1 = db_session.query(MedicarePartDUtilization).count()
            loop.run_until_complete(ingester.load(_iter(2023)))
            count2 = db_session.query(MedicarePartDUtilization).count()
        finally:
            loop.close()

        assert count1 == count2, f"Idempotency broken: {count1} vs {count2}"
        assert count1 > 0


# ===========================================================================
# 8. Checksum skip
# ===========================================================================


class TestChecksumSkip:
    @pytest.mark.asyncio
    async def test_checksum_skip_on_unchanged_file(self, db_session: Session) -> None:
        """If source file checksum matches last successful run, skip ingestion."""
        import shared.data_ingestion.sources.cms_part_d_prescriber as mod

        ingester = CmsPartDPrescriberIngester(db_session, year=2023)

        with patch.object(ingester, "_last_successful_checksum", return_value="abc123"):
            with patch(
                "shared.data_ingestion.downloader.compute_sha256", return_value="abc123"
            ):
                with patch.object(ingester, "download", new_callable=AsyncMock) as mock_dl:
                    mock_dl.return_value = _SAMPLE_FILE
                    result = await ingester.run()

        assert result.status == "skipped_unchanged"


# ===========================================================================
# 9. Global ref — not tenant-scoped
# ===========================================================================


class TestCrossTenantNotScoped:
    def test_cross_tenant_not_scoped(self, db_session: Session) -> None:
        """Global ref table: a single row is visible regardless of tenant context."""
        sample_data = json.loads(_SAMPLE_FILE.read_text())
        raw = sample_data[0]
        record = parse_part_d_row(raw, year=2023)
        assert record is not None

        row = MedicarePartDUtilization(**{k: v for k, v in record.items() if k != "raw_payload"})
        row.raw_payload = record.get("raw_payload")
        db_session.add(row)
        db_session.flush()

        # Both "tenants" see the same row — no tenant_id column exists
        count = db_session.query(MedicarePartDUtilization).filter_by(
            npi=record["npi"], year=2023
        ).count()
        assert count == 1

        # Verify no tenant_id column on the table
        col_names = [c.name for c in MedicarePartDUtilization.__table__.columns]
        assert "tenant_id" not in col_names, (
            "Global ref table must NOT have tenant_id (LESSON-011)"
        )


# ===========================================================================
# 10. No float in source module
# ===========================================================================


class TestNoFloatInModule:
    def test_no_float_in_module(self) -> None:
        """Grep the source file for 'float' or 'Float' in model/service code."""
        import shared.data_ingestion.sources.cms_part_d_prescriber as mod

        source_path = Path(inspect.getfile(mod))
        source_text = source_path.read_text()

        # Parse as AST and check for float annotations or Float() calls
        tree = ast.parse(source_text)
        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "float":
                violations.append(f"'float' at line {node.lineno}")
            if isinstance(node, ast.Attribute) and node.attr == "Float":
                violations.append(f"'.Float' at line {node.lineno}")

        assert not violations, (
            "Float found in cms_part_d_prescriber.py (financial-precision.md violation):\n"
            + "\n".join(violations)
        )

    def test_no_float_in_model(self) -> None:
        """medicare_tables.py must not use Float anywhere."""
        model_path = _PRESCRIBER_ROOT / "src" / "models" / "medicare_tables.py"
        source_text = model_path.read_text()
        tree = ast.parse(source_text)
        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in ("Float", "FLOAT"):
                violations.append(f"'.{node.attr}' at line {node.lineno}")
        assert not violations, (
            "Float column type found in medicare_tables.py: " + str(violations)
        )


# ===========================================================================
# 11. Paginated API download
# ===========================================================================


class TestPaginatedAPIDownload:
    @pytest.mark.asyncio
    async def test_paginated_api_merges_pages(self, tmp_path: Path) -> None:
        """CmsPartDPrescriberIngester.download() merges multiple API pages."""
        page1 = [_part_d_row()] * 50_000
        page2 = [_part_d_row(**{"Prscrbr_NPI": "9876543210"})] * 25_000

        mock_db = MagicMock()

        with respx.mock(assert_all_called=False) as mock_router:
            mock_router.get(
                "https://data.cms.gov/data-api/v1/dataset/3ntk-nwcc/data",
                params={"$limit": "50000", "$offset": "0"},
            ).mock(return_value=httpx.Response(200, json=page1))
            mock_router.get(
                "https://data.cms.gov/data-api/v1/dataset/3ntk-nwcc/data",
                params={"$limit": "50000", "$offset": "50000"},
            ).mock(return_value=httpx.Response(200, json=page2))

            ingester = CmsPartDPrescriberIngester(db_session=mock_db, year=2023)
            import shared.data_ingestion.sources.cms_part_d_prescriber as mod
            orig = mod._DEST_DIR
            mod._DEST_DIR = tmp_path
            try:
                path = await ingester.download()
            finally:
                mod._DEST_DIR = orig

        data = json.loads(path.read_text())
        assert len(data) == 75_000

    @pytest.mark.asyncio
    async def test_download_terminates_on_empty_page(self, tmp_path: Path) -> None:
        """Download stops when API returns empty array."""
        mock_db = MagicMock()

        with respx.mock(assert_all_called=False) as mock_router:
            mock_router.get(
                "https://data.cms.gov/data-api/v1/dataset/3ntk-nwcc/data",
                params={"$limit": "50000", "$offset": "0"},
            ).mock(return_value=httpx.Response(200, json=[]))

            ingester = CmsPartDPrescriberIngester(db_session=mock_db, year=2023)
            import shared.data_ingestion.sources.cms_part_d_prescriber as mod
            orig = mod._DEST_DIR
            mod._DEST_DIR = tmp_path
            try:
                path = await ingester.download()
            finally:
                mod._DEST_DIR = orig

        data = json.loads(path.read_text())
        assert len(data) == 0


# ===========================================================================
# 12. CSV parse path
# ===========================================================================


class TestCsvParsePath:
    def test_parse_csv_file(self, tmp_path: Path) -> None:
        """parse() delegates to _parse_csv for .csv suffix files."""
        import csv as csv_mod

        csv_file = tmp_path / "part_d.csv"
        fieldnames = [
            "Prscrbr_NPI", "Prscrbr_Last_Org_Name", "Prscrbr_First_Name",
            "Prscrbr_City", "Prscrbr_State_Abrvtn", "Prscrbr_State_FIPS",
            "Prscrbr_Zip5", "Prscrbr_RUCA", "Prscrbr_Cntry", "Prscrbr_Type",
            "Prscrbr_Type_Src", "Tot_Drug_Cst",
        ]
        rows = [
            {
                "Prscrbr_NPI": "1234567893",
                "Prscrbr_Last_Org_Name": "SMITH",
                "Prscrbr_First_Name": "JOHN",
                "Prscrbr_City": "CHICAGO",
                "Prscrbr_State_Abrvtn": "IL",
                "Prscrbr_State_FIPS": "17",
                "Prscrbr_Zip5": "60601",
                "Prscrbr_RUCA": "1",
                "Prscrbr_Cntry": "US",
                "Prscrbr_Type": "Internal Medicine",
                "Prscrbr_Type_Src": "T",
                "Tot_Drug_Cst": "12345.67",
            }
        ]
        with csv_file.open("w", newline="") as fh:
            writer = csv_mod.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        mock_db = MagicMock()
        ingester = CmsPartDPrescriberIngester(db_session=mock_db, year=2023)
        parsed = list(ingester.parse(csv_file))
        assert len(parsed) == 1
        assert parsed[0]["npi"] == "1234567893"
        assert parsed[0]["tot_drug_cst"] == Decimal("12345.67")


# ===========================================================================
# 13. Additional helper coverage
# ===========================================================================


class TestHelperEdgeCases:
    def test_parse_decimal_2_invalid_returns_none(self) -> None:
        assert _parse_decimal_2("not-a-number") is None

    def test_parse_decimal_4_empty_returns_none(self) -> None:
        assert _parse_decimal_4("") is None

    def test_parse_decimal_4_none_returns_none(self) -> None:
        assert _parse_decimal_4(None) is None

    def test_parse_decimal_4_invalid_returns_none(self) -> None:
        assert _parse_decimal_4("not-a-number") is None

    def test_parse_int_invalid_returns_none(self) -> None:
        assert _parse_int("not-an-int") is None

    def test_parse_int_empty_returns_none(self) -> None:
        assert _parse_int("") is None

    def test_parse_int_valid(self) -> None:
        assert _parse_int("42") == 42

    def test_parse_int_decimal_string(self) -> None:
        assert _parse_int("42.7") == 43  # rounds up

    def test_default_year_is_prior_year(self) -> None:
        from datetime import datetime, timezone
        ingester = CmsPartDPrescriberIngester(db_session=MagicMock())
        assert ingester._year == datetime.now(timezone.utc).year - 1

    def test_parse_json_file_skips_invalid_npi_rows(self, tmp_path: Path) -> None:
        """parse() with .json file skips rows with invalid NPI."""
        data = [
            {
                "Prscrbr_NPI": "BADNPI",
                "Prscrbr_Last_Org_Name": "BAD",
                "Tot_Drug_Cst": "100.00",
            },
            {
                "Prscrbr_NPI": "1234567893",
                "Prscrbr_Last_Org_Name": "GOOD",
                "Tot_Drug_Cst": "200.00",
            },
        ]
        json_file = tmp_path / "data.json"
        json_file.write_text(json.dumps(data))

        ingester = CmsPartDPrescriberIngester(db_session=MagicMock(), year=2023)
        parsed = list(ingester.parse(json_file))
        assert len(parsed) == 1
        assert parsed[0]["npi"] == "1234567893"

    def test_parse_csv_skips_invalid_npi_rows(self, tmp_path: Path) -> None:
        """_parse_csv skips rows where NPI fails validation."""
        import csv as csv_mod

        csv_file = tmp_path / "bad.csv"
        fieldnames = ["Prscrbr_NPI", "Prscrbr_Last_Org_Name", "Tot_Drug_Cst"]
        rows = [
            {"Prscrbr_NPI": "BADNPI", "Prscrbr_Last_Org_Name": "BAD", "Tot_Drug_Cst": "0.00"},
            {"Prscrbr_NPI": "1234567893", "Prscrbr_Last_Org_Name": "GOOD", "Tot_Drug_Cst": "0.00"},
        ]
        with csv_file.open("w", newline="") as fh:
            writer = csv_mod.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        ingester = CmsPartDPrescriberIngester(db_session=MagicMock(), year=2023)
        parsed = list(ingester.parse(csv_file))
        assert len(parsed) == 1
        assert parsed[0]["npi"] == "1234567893"

    def test_load_postgresql_upsert_path(self, db_session: Session) -> None:
        """When dialect reports postgresql, pg_insert ON CONFLICT path is taken."""
        import asyncio
        from unittest.mock import MagicMock, patch

        records = [
            {
                "npi": "1234567893",
                "year": 2023,
                "prscrbr_type": "Internal Medicine",
                "tot_drug_cst": Decimal("100.00"),
                "raw_payload": {},
                "updated_at": None,
            }
        ]

        mock_execute_result = MagicMock()
        mock_db = MagicMock()
        mock_db.connection.return_value.dialect.name = "postgresql"
        mock_db.execute.return_value = mock_execute_result

        ingester = CmsPartDPrescriberIngester(db_session=mock_db, year=2023)
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(ingester.load(iter(records)))
        finally:
            loop.close()
        assert result.records_inserted == 1
        mock_db.execute.assert_called()

    def test_load_large_batch_triggers_flush(self, db_session: Session) -> None:
        """Verify that batches >= _BATCH_SIZE flush mid-stream (>1000 rows)."""
        import asyncio

        def _big_iter() -> Iterator[dict[str, Any]]:
            for i in range(1100):
                npi = str(1000000000 + i).zfill(10)
                yield {
                    "npi": npi,
                    "year": 2023,
                    "prscrbr_type": "Family Practice",
                    "tot_drug_cst": Decimal("100.00"),
                    "raw_payload": {},
                    "updated_at": None,
                }

        ingester = CmsPartDPrescriberIngester(db_session, year=2023)
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(ingester.load(_big_iter()))
        finally:
            loop.close()
        assert result.records_inserted >= 1000

    def test_load_empty_iterator_returns_zero(self, db_session: Session) -> None:
        """Loading empty iterator completes with 0 inserted."""
        import asyncio

        ingester = CmsPartDPrescriberIngester(db_session, year=2023)
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(ingester.load(iter([])))
        finally:
            loop.close()

        assert result.records_inserted == 0

