"""Tests for the CMS ASP drug pricing ingestion pipeline.

Covers:
  - Parse all 5 fields from XLSX
  - Effective quarter inferred from filename when column is absent
  - Payment limit stored as Decimal, never float
  - History table is idempotent — re-running same quarter does NOT duplicate
  - 8 synthetic ASP rows covering: vaccine Y, vaccine N, missing dosage,
    multiple HCPCS levels (J, Q, S, G codes)

SQLAlchemy isolation:
  SAVEPOINT-based per LESSON-001.
  _UUIDString TypeDecorator per LESSON-007.
"""

from __future__ import annotations

import os
import sys
import uuid
from collections.abc import Iterator
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import openpyxl
import pytest
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
from shared.data_ingestion.sources.cms_asp import (
    CMSASPIngester,
    _find_latest_xlsx_url,
    _infer_quarter_from_filename,
    _parse_decimal,
    _parse_xlsx,
)
from shared.db.base import Base

from src.models.pricing_tables import (  # type: ignore[import]
    DrugASPPricing,
    DrugASPPricingHistory,
    PricingBase,
    SCHEMA as PRICING_SCHEMA,
)
from src.services.pricing_ingestion import ASPIngestionService  # type: ignore[import]

# ---------------------------------------------------------------------------
# Sample data path
# ---------------------------------------------------------------------------

_SAMPLE_DIR = Path(__file__).parent / "sample_data" / "cms_asp"
_SAMPLE_XLSX = _SAMPLE_DIR / "sample_asp.xlsx"

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


def _patch_asp_tables_for_sqlite() -> None:
    """BigInteger PKs → Integer for SQLite autoincrement."""
    for table in [
        DrugASPPricing.__table__,
        DrugASPPricingHistory.__table__,
    ]:
        if getattr(table, "_sqlite_patched", False):
            continue
        for col in table.columns:
            if isinstance(col.type, BigInteger) and col.primary_key:
                col.type = Integer()
        table._sqlite_patched = True  # type: ignore[attr-defined]


_patch_ingestion_tables_for_sqlite()
_patch_asp_tables_for_sqlite()


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
# Helpers
# ---------------------------------------------------------------------------


def _asp_row(
    hcpcs: str = "J0135",
    description: str = "ADALIMUMAB INJECTION",
    dosage: str | None = "20 mg",
    payment: str = "2841.234500",
    vaccine: str | None = "N",
    quarter: str = "2026Q2",
) -> dict[str, Any]:
    return {
        "hcpcs_code": hcpcs,
        "short_description": description,
        "dosage": dosage,
        "payment_limit": Decimal(payment),
        "vaccine_awp": vaccine,
        "effective_quarter": quarter,
    }


def _make_xlsx(path: Path, rows: list[tuple], *, include_vaccine_col: bool = True,
               include_quarter_col: bool = True) -> None:
    """Write a synthetic ASP XLSX for testing."""
    wb = openpyxl.Workbook()
    ws = wb.active
    headers = ["HCPCS Code", "Short Description", "HCPCS Code Dosage", "Payment Limit"]
    if include_vaccine_col:
        headers.append("Vaccine AWP")
    if include_quarter_col:
        headers.append("Effective Quarter")
    ws.append(headers)
    for row in rows:
        ws.append(list(row))
    wb.save(str(path))


# ===========================================================================
# 1. Quarter inference from filename
# ===========================================================================


class TestEffectiveQuarterInferredFromFilename:
    def test_infer_from_asp_pricing_file_2026_q2(self) -> None:
        result = _infer_quarter_from_filename("ASP_Pricing_File_2026_Q2.xlsx")
        assert result == "2026Q2"

    def test_infer_from_2026_q1_asp_drug(self) -> None:
        result = _infer_quarter_from_filename("2026_Q1_ASP_Drug_Pricing.xlsx")
        assert result == "2026Q1"

    def test_infer_from_2026q2_asp(self) -> None:
        result = _infer_quarter_from_filename("2026q2_asp.xlsx")
        assert result == "2026Q2"

    def test_infer_none_for_unknown(self) -> None:
        assert _infer_quarter_from_filename("random_file.xlsx") is None

    def test_infer_from_month_name_april_2026(self) -> None:
        """CMS ZIP filenames use month names: april-2026-... → 2026Q2."""
        result = _infer_quarter_from_filename("april-2026-medicare-part-b-payment-limit.zip")
        assert result == "2026Q2"

    def test_infer_from_month_name_october_2025(self) -> None:
        result = _infer_quarter_from_filename("october-2025-asp-pricing-final-file.zip")
        assert result == "2025Q4"

    def test_infer_from_month_name_january_2026(self) -> None:
        result = _infer_quarter_from_filename("january-2026-medicare-part-b-payment-limit-files.zip")
        assert result == "2026Q1"

    def test_effective_quarter_inferred_from_filename_when_missing(
        self, tmp_path: Path
    ) -> None:
        """When XLSX has no Effective Quarter column, quarter comes from filename."""
        xlsx_path = tmp_path / "ASP_Pricing_File_2026_Q2.xlsx"
        _make_xlsx(
            xlsx_path,
            rows=[("J0135", "ADALIMUMAB", "20 mg", 2841.23, "N")],
            include_quarter_col=False,
        )
        records = list(_parse_xlsx(xlsx_path))
        assert len(records) == 1
        assert records[0]["effective_quarter"] == "2026Q2"


# ===========================================================================
# 2. Parse all 5 fields from XLSX
# ===========================================================================


class TestParseAllFiveFields:
    def test_parse_all_5_fields(self) -> None:
        """HCPCS code, description, dosage, payment_limit, vaccine_awp all parsed."""
        records = list(_parse_xlsx(_SAMPLE_XLSX))
        # Sample has 8 rows
        assert len(records) == 8

        # J0135 row
        j0135 = next((r for r in records if r["hcpcs_code"] == "J0135"), None)
        assert j0135 is not None
        assert j0135["short_description"] == "ADALIMUMAB INJECTION"
        assert j0135["dosage"] == "20 mg"
        assert isinstance(j0135["payment_limit"], Decimal)
        assert j0135["vaccine_awp"] == "N"
        assert j0135["effective_quarter"] == "2026Q2"

    def test_vaccine_y_row_parsed(self) -> None:
        """Row with Vaccine AWP = Y is parsed correctly."""
        records = list(_parse_xlsx(_SAMPLE_XLSX))
        vaccine_rows = [r for r in records if r.get("vaccine_awp") == "Y"]
        assert len(vaccine_rows) >= 1
        # J7296 is the vaccine row
        j7296 = next((r for r in records if r["hcpcs_code"] == "J7296"), None)
        assert j7296 is not None
        assert j7296["vaccine_awp"] == "Y"

    def test_vaccine_n_row_parsed(self) -> None:
        records = list(_parse_xlsx(_SAMPLE_XLSX))
        non_vax = [r for r in records if r.get("vaccine_awp") == "N"]
        assert len(non_vax) >= 1

    def test_missing_dosage_treated_as_none(self) -> None:
        """Rows with empty dosage cell produce dosage=None."""
        records = list(_parse_xlsx(_SAMPLE_XLSX))
        no_dosage = [r for r in records if not r.get("dosage")]
        assert len(no_dosage) >= 1

    def test_j_q_s_g_code_prefixes_present(self) -> None:
        """Sample covers J, Q, S, G HCPCS code prefixes."""
        records = list(_parse_xlsx(_SAMPLE_XLSX))
        codes = {r["hcpcs_code"] for r in records}
        prefixes = {c[0] for c in codes}
        assert "J" in prefixes
        assert "Q" in prefixes
        assert "S" in prefixes
        assert "G" in prefixes

    def test_xlsx_without_vaccine_column(self, tmp_path: Path) -> None:
        """Parsing an XLSX with no Vaccine AWP column yields vaccine_awp=None."""
        xlsx_path = tmp_path / "no_vaccine_2026_Q1.xlsx"
        _make_xlsx(
            xlsx_path,
            rows=[("J0135", "ADALIMUMAB", "20 mg", 2841.23)],
            include_vaccine_col=False,
        )
        records = list(_parse_xlsx(xlsx_path))
        assert len(records) == 1
        assert records[0]["vaccine_awp"] is None


# ===========================================================================
# 3. Payment limit — Decimal precision
# ===========================================================================


class TestPaymentLimitDecimal:
    def test_payment_limit_decimal(self) -> None:
        """Payment limit from XLSX cell is stored as Decimal, never float."""
        records = list(_parse_xlsx(_SAMPLE_XLSX))
        for record in records:
            assert isinstance(record["payment_limit"], Decimal), (
                f"payment_limit for {record['hcpcs_code']} must be Decimal, "
                f"got {type(record['payment_limit'])}"
            )

    def test_payment_limit_rounding(self) -> None:
        """Decimal(str(value)) with ROUND_HALF_UP: 2841.23450 → 2841.234500."""
        result = _parse_decimal(2841.2345)
        assert result == Decimal("2841.234500")
        assert isinstance(result, Decimal)

    def test_payment_limit_zero_is_decimal(self) -> None:
        result = _parse_decimal(0.0)
        assert result == Decimal("0.000000")
        assert isinstance(result, Decimal)


# ===========================================================================
# 4. History table idempotency
# ===========================================================================


class TestHistoryTableIdempotentInsert:
    @pytest.mark.asyncio
    async def test_history_table_idempotent_insert(self, db_session: Session) -> None:
        """Re-running same quarter does NOT duplicate history rows."""
        svc = ASPIngestionService(db_session)

        rows = [
            _asp_row("J0135", quarter="2026Q2"),
            _asp_row("J3490", dosage=None, quarter="2026Q2"),
        ]

        # First load
        result1 = await svc.load_records(iter(rows), source_name="cms_asp")
        db_session.flush()
        hist_count_1 = db_session.query(DrugASPPricingHistory).count()

        # Second load — same quarter
        result2 = await svc.load_records(iter(rows), source_name="cms_asp")
        db_session.flush()
        hist_count_2 = db_session.query(DrugASPPricingHistory).count()

        assert hist_count_1 == hist_count_2, (
            f"History duplicated: {hist_count_1} after first, {hist_count_2} after second"
        )
        assert hist_count_1 > 0

    @pytest.mark.asyncio
    async def test_new_quarter_creates_history_row(self, db_session: Session) -> None:
        """Updating to a new quarter creates an additional history row."""
        svc = ASPIngestionService(db_session)

        row_q1 = _asp_row("J0695", quarter="2026Q1")
        row_q2 = _asp_row("J0695", payment="4.000000", quarter="2026Q2")

        await svc.load_records(iter([row_q1]), source_name="cms_asp")
        hist_after_q1 = db_session.query(DrugASPPricingHistory).filter_by(
            hcpcs_code="J0695"
        ).count()
        assert hist_after_q1 == 1

        await svc.load_records(iter([row_q2]), source_name="cms_asp")
        hist_after_q2 = db_session.query(DrugASPPricingHistory).filter_by(
            hcpcs_code="J0695"
        ).count()
        assert hist_after_q2 == 2


# ===========================================================================
# 5. URL discovery from HTML
# ===========================================================================


class TestFindLatestXlsxUrl:
    def test_finds_asp_xlsx_link(self) -> None:
        html = """
        <html><body>
        <a href="/files/2025_Q4_ASP_Drug_Pricing.xlsx">Q4 2025</a>
        <a href="/files/2026_Q1_ASP_Drug_Pricing.xlsx">Q1 2026</a>
        <a href="/files/2026_Q2_ASP_Drug_Pricing.xlsx">Q2 2026</a>
        </body></html>
        """
        url = _find_latest_xlsx_url(html, "https://www.cms.gov")
        assert url is not None
        assert "2026_Q2" in url

    def test_returns_none_for_no_matches(self) -> None:
        html = "<html><body><a href='/page'>no xlsx here</a></body></html>"
        url = _find_latest_xlsx_url(html, "https://www.cms.gov")
        assert url is None

    def test_absolute_url_constructed(self) -> None:
        html = '<a href="/files/asp.xlsx">download</a>'
        url = _find_latest_xlsx_url(html, "https://www.cms.gov")
        assert url is not None
        assert url.startswith("https://www.cms.gov")

    def test_finds_asp_zip_link_when_no_xlsx(self) -> None:
        """CMS uses ZIP files; should find the latest asp-pricing zip."""
        html = """
        <html><body>
        <a href="/files/zip/january-2026-medicare-part-b-payment-limit-files.zip">Q1 2026</a>
        <a href="/files/zip/april-2026-medicare-part-b-payment-limit-files-03-30-2026-final-file.zip">Q2 2026</a>
        </body></html>
        """
        url = _find_latest_xlsx_url(html, "https://www.cms.gov")
        assert url is not None
        assert "april-2026" in url

    def test_prefers_xlsx_over_zip(self) -> None:
        """When both XLSX and ZIP are present, prefer XLSX."""
        html = """
        <html><body>
        <a href="/files/zip/april-2026-asp-pricing.zip">Q2 ZIP</a>
        <a href="/files/ASP_Pricing_File_2026_Q2.xlsx">Q2 XLSX</a>
        </body></html>
        """
        url = _find_latest_xlsx_url(html, "https://www.cms.gov")
        assert url is not None
        assert url.endswith(".xlsx")


# ===========================================================================
# 6. ASP service validation
# ===========================================================================


class TestASPServiceValidation:
    def test_invalid_hcpcs_code_rejected(self, db_session: Session) -> None:
        svc = ASPIngestionService(db_session)
        with pytest.raises(ValueError, match="hcpcs_code"):
            svc._validate_asp_row({
                "hcpcs_code": "TOOLONG_CODE",
                "payment_limit": "1.00",
                "effective_quarter": "2026Q1",
            })

    def test_invalid_quarter_rejected(self, db_session: Session) -> None:
        svc = ASPIngestionService(db_session)
        with pytest.raises(ValueError, match="effective_quarter"):
            svc._validate_asp_row({
                "hcpcs_code": "J0135",
                "payment_limit": "1.00",
                "effective_quarter": "2026-Q1",  # wrong format
            })

    def test_missing_payment_limit_rejected(self, db_session: Session) -> None:
        svc = ASPIngestionService(db_session)
        with pytest.raises(ValueError, match="payment_limit"):
            svc._validate_asp_row({
                "hcpcs_code": "J0135",
                "payment_limit": None,
                "effective_quarter": "2026Q1",
            })

    def test_unexpected_vaccine_awp_value_tolerated(self, db_session: Session) -> None:
        """Vaccine AWP column with unexpected value is set to None (graceful)."""
        svc = ASPIngestionService(db_session)
        row = svc._validate_asp_row({
            "hcpcs_code": "J0135",
            "payment_limit": "1.00",
            "effective_quarter": "2026Q1",
            "vaccine_awp": "UNKNOWN_VALUE",
        })
        assert row["vaccine_awp"] is None


# ===========================================================================
# 7. Full load from sample XLSX
# ===========================================================================


class TestFullLoadFromSampleXlsx:
    @pytest.mark.asyncio
    async def test_load_sample_xlsx_all_8_rows(self, db_session: Session) -> None:
        """Loading the pre-committed sample XLSX inserts 8 current rows."""
        svc = ASPIngestionService(db_session)

        def _iter_xlsx() -> Iterator[dict[str, Any]]:
            yield from _parse_xlsx(_SAMPLE_XLSX)

        result = await svc.load_records(_iter_xlsx(), source_name="cms_asp")
        count = db_session.query(DrugASPPricing).count()
        assert count == 8
        assert result.records_processed == 8
        assert result.records_errored == 0
