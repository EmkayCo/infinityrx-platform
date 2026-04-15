"""Tests for government exclusion BIN/PCN service and CSV loader.

Covers:
  - TRICARE exact match → BLOCKED, HIGH confidence
  - Medicare BIN-only → BLOCKED (MEDIUM → REVIEW)
  - Medicaid MCO match → BLOCKED, HIGH
  - Commercial BIN → ELIGIBLE
  - Ambiguous BIN without PCN → REVIEW, MEDIUM
  - OCC code fallback → BLOCKED
  - CSV import: valid rows
  - CSV import: invalid rows (bad BIN, missing source, bad plan_type)
  - Empty table → ELIGIBLE for all queries
  - State coverage query
  - Federal seed idempotency

Uses SAVEPOINT-based transaction isolation (LESSON-001) and _UUIDString
TypeDecorator (LESSON-007).
"""

from __future__ import annotations

import io
import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import JSON, String, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import TypeDecorator

# Minimal env setup
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost/")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")
os.environ.setdefault(
    "ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM="
)

from shared.db.base import Base
from shared.models.gov_exclusion_tables import GovernmentProgramBin
from shared.services.gov_exclusion_service import GovernmentExclusionService


# ---------------------------------------------------------------------------
# UUID string TypeDecorator for SQLite (LESSON-007)
# ---------------------------------------------------------------------------


class _UUIDString(TypeDecorator):
    """SQLite-compatible UUID stored as VARCHAR(36)."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        return str(value) if value is not None else None

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:
        return uuid.UUID(str(value)) if value is not None else None


def _patch_gov_table_for_sqlite() -> None:
    table = GovernmentProgramBin.__table__
    if getattr(table, "_sqlite_patched", False):
        return
    for col in table.columns:
        if isinstance(col.type, PG_UUID):
            col.type = _UUIDString()
        if col.server_default is not None and "gen_random_uuid" in str(
            col.server_default
        ):
            col.server_default = None
    table._sqlite_patched = True  # type: ignore[attr-defined]


_patch_gov_table_for_sqlite()


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
    Base.metadata.create_all(engine, tables=[GovernmentProgramBin.__table__])
    yield engine
    Base.metadata.drop_all(engine, tables=[GovernmentProgramBin.__table__])
    raw_engine.dispose()


@pytest.fixture
def db(_engine) -> Iterator[Session]:
    """SAVEPOINT-isolated session per LESSON-001."""
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
def svc(db: Session) -> GovernmentExclusionService:
    return GovernmentExclusionService(db)


def _make_entry(db: Session, **kwargs: Any) -> GovernmentProgramBin:
    """Helper: insert a GovernmentProgramBin row."""
    now = datetime.now(UTC)
    defaults = {
        "id": uuid.uuid4(),
        "government_flag": True,
        "confidence": "HIGH",
        "source": "test",
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(kwargs)
    entry = GovernmentProgramBin(**defaults)
    db.add(entry)
    db.flush()
    return entry


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


class TestIsGovernmentPlan:
    def test_empty_table_returns_not_government(self, svc: GovernmentExclusionService) -> None:
        result = svc.is_government_plan(bin="003858")
        assert result.is_government is False
        assert result.match_type == "none"

    def test_tricare_exact_bin_pcn_group_match(
        self, db: Session, svc: GovernmentExclusionService
    ) -> None:
        _make_entry(
            db,
            bin="003858",
            pcn="A4",
            group_number="DODA",
            plan_type="TRICARE",
            confidence="HIGH",
        )
        result = svc.is_government_plan(bin="003858", pcn="A4", group="DODA")
        assert result.is_government is True
        assert result.confidence == "HIGH"
        assert result.match_type == "bin_pcn_group"
        assert result.plans[0].plan_type == "TRICARE"

    def test_tricare_bin_pcn_match(
        self, db: Session, svc: GovernmentExclusionService
    ) -> None:
        _make_entry(db, bin="003858", pcn="A4", plan_type="TRICARE", confidence="HIGH")
        result = svc.is_government_plan(bin="003858", pcn="A4")
        assert result.is_government is True
        assert result.match_type == "bin_pcn"

    def test_medicare_bin_only_medium_confidence(
        self, db: Session, svc: GovernmentExclusionService
    ) -> None:
        _make_entry(
            db,
            bin="004336",
            pcn=None,
            plan_type="MEDICARE_PART_D",
            confidence="MEDIUM",
        )
        result = svc.is_government_plan(bin="004336")
        assert result.is_government is True
        assert result.confidence == "MEDIUM"
        assert result.match_type == "bin_only"

    def test_medicaid_mco_match_high_confidence(
        self, db: Session, svc: GovernmentExclusionService
    ) -> None:
        _make_entry(
            db,
            bin="123456",
            pcn="MCO1",
            plan_type="MEDICAID_MCO",
            confidence="HIGH",
            mco_name="Molina Healthcare",
            state="CA",
        )
        result = svc.is_government_plan(bin="123456", pcn="MCO1")
        assert result.is_government is True
        assert result.confidence == "HIGH"
        assert result.plans[0].plan_type == "MEDICAID_MCO"
        assert result.plans[0].state == "CA"

    def test_commercial_bin_returns_not_government(
        self, svc: GovernmentExclusionService
    ) -> None:
        result = svc.is_government_plan(bin="999000")
        assert result.is_government is False

    def test_occ_code_fallback_government_code(
        self, svc: GovernmentExclusionService
    ) -> None:
        result = svc.is_government_plan(bin="999000", occ="13")
        assert result.is_government is True
        assert result.confidence == "MEDIUM"
        assert result.match_type == "occ"

    def test_occ_code_fallback_non_government_code(
        self, svc: GovernmentExclusionService
    ) -> None:
        result = svc.is_government_plan(bin="999000", occ="01")
        assert result.is_government is False

    def test_bin_left_padded_to_six_digits(
        self, db: Session, svc: GovernmentExclusionService
    ) -> None:
        _make_entry(db, bin="003858", plan_type="TRICARE", confidence="HIGH")
        # Submit without leading zeros — service normalizes
        result = svc.is_government_plan(bin="3858")
        assert result.is_government is True

    def test_ambiguous_bin_without_pcn_is_medium(
        self, db: Session, svc: GovernmentExclusionService
    ) -> None:
        _make_entry(
            db,
            bin="004336",
            pcn=None,
            plan_type="MEDICARE_PART_D",
            confidence="MEDIUM",
            notes="BIN also used for commercial",
        )
        result = svc.is_government_plan(bin="004336")
        assert result.is_government is True
        assert result.confidence == "MEDIUM"

    def test_multiple_rows_confidence_is_worst(
        self, db: Session, svc: GovernmentExclusionService
    ) -> None:
        _make_entry(db, bin="004336", pcn=None, plan_type="MEDICARE_PART_D", confidence="HIGH")
        _make_entry(
            db,
            bin="004336",
            pcn="ADV",
            plan_type="MEDICARE_ADVANTAGE",
            confidence="MEDIUM",
        )
        # Query with PCN=ADV → bin_pcn match, single MEDIUM row
        result = svc.is_government_plan(bin="004336", pcn="ADV")
        assert result.confidence == "MEDIUM"

    def test_state_coverage_query(
        self, db: Session, svc: GovernmentExclusionService
    ) -> None:
        _make_entry(db, bin="111111", state="CA", plan_type="MEDICAID_FFS", confidence="HIGH")
        _make_entry(db, bin="222222", state="CA", plan_type="MEDICAID_MCO", confidence="HIGH")
        _make_entry(db, bin="333333", state="NY", plan_type="MEDICAID_MCO", confidence="HIGH")

        ca_plans = svc.get_state_coverage("CA")
        assert len(ca_plans) == 2
        assert all(p.state == "CA" for p in ca_plans)

    def test_get_plan_details_returns_matching_rows(
        self, db: Session, svc: GovernmentExclusionService
    ) -> None:
        _make_entry(db, bin="610494", pcn=None, plan_type="MEDICARE_PART_D", confidence="HIGH")
        plans = svc.get_plan_details(bin="610494")
        assert len(plans) >= 1
        assert plans[0].bin == "610494"


class TestCopayCardEligibility:
    def test_empty_table_eligible(self, svc: GovernmentExclusionService) -> None:
        result = svc.check_copay_card_eligibility(bin="004336")
        assert result.eligible is True
        assert result.status == "ELIGIBLE"

    def test_tricare_high_confidence_blocked(
        self, db: Session, svc: GovernmentExclusionService
    ) -> None:
        _make_entry(
            db,
            bin="003858",
            pcn="A4",
            group_number="DODA",
            plan_type="TRICARE",
            confidence="HIGH",
        )
        result = svc.check_copay_card_eligibility(bin="003858", pcn="A4", group="DODA")
        assert result.eligible is False
        assert result.status == "BLOCKED"
        assert "Anti-Kickback" in result.reason

    def test_medium_confidence_review(
        self, db: Session, svc: GovernmentExclusionService
    ) -> None:
        _make_entry(
            db,
            bin="004336",
            pcn=None,
            plan_type="MEDICARE_PART_D",
            confidence="MEDIUM",
        )
        result = svc.check_copay_card_eligibility(bin="004336")
        assert result.eligible is False
        assert result.status == "REVIEW"
        assert "MEDIUM" in result.reason

    def test_occ_13_medicaid_blocked_medium(
        self, svc: GovernmentExclusionService
    ) -> None:
        result = svc.check_copay_card_eligibility(bin="999000", occ="13")
        assert result.eligible is False
        assert result.status == "REVIEW"

    def test_medicaid_mco_high_blocked(
        self, db: Session, svc: GovernmentExclusionService
    ) -> None:
        _make_entry(
            db,
            bin="555555",
            pcn="MCOM",
            plan_type="MEDICAID_MCO",
            confidence="HIGH",
        )
        result = svc.check_copay_card_eligibility(bin="555555", pcn="MCOM")
        assert result.eligible is False
        assert result.status == "BLOCKED"

    def test_commercial_bin_eligible(self, svc: GovernmentExclusionService) -> None:
        result = svc.check_copay_card_eligibility(bin="000000")
        assert result.eligible is True
        assert result.status == "ELIGIBLE"


# ---------------------------------------------------------------------------
# CSV loader tests
# ---------------------------------------------------------------------------


class TestCsvLoader:
    """Tests for load_state_medicaid_csv_from_bytes."""

    @pytest.mark.asyncio
    async def test_valid_csv_inserts_rows(self, db: Session) -> None:
        from shared.data_ingestion.sources.gov_exclusion import load_state_medicaid_csv_from_bytes

        csv_content = (
            "state,bin,pcn,group_number,plan_type,plan_subtype,pbm_name,"
            "plan_name,mco_name,confidence,source,source_date,notes\n"
            "CA,123456,MCO1,,MEDICAID_MCO,CA Medi-Cal MCO,Molina,"
            "CA Medi-Cal Managed Care,Molina Healthcare,HIGH,"
            "CA DHCS 2026-01,2026-01-01,Test row\n"
            "CA,234567,,,MEDICAID_FFS,,,"
            "CA Medi-Cal FFS,,,HIGH,"
            "CA DHCS 2026-01,2026-01-01,FFS row\n"
        )
        result = await load_state_medicaid_csv_from_bytes(
            csv_content.encode(), db
        )
        assert result.status == "completed"
        assert result.records_processed == 2
        assert result.records_inserted == 2
        assert result.records_errored == 0

        rows = db.query(GovernmentProgramBin).filter(
            GovernmentProgramBin.bin.in_(["123456", "234567"])
        ).all()
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_duplicate_row_updates_not_inserts(self, db: Session) -> None:
        from shared.data_ingestion.sources.gov_exclusion import load_state_medicaid_csv_from_bytes

        csv_content = (
            "state,bin,pcn,group_number,plan_type,plan_subtype,pbm_name,"
            "plan_name,mco_name,confidence,source,source_date,notes\n"
            "TX,666666,,,MEDICAID_FFS,,,TX Medicaid FFS,,,HIGH,TX HHSC,2026-01-01,\n"
        )
        # First load
        r1 = await load_state_medicaid_csv_from_bytes(csv_content.encode(), db)
        assert r1.records_inserted == 1

        # Second load (same row) — should update, not insert
        r2 = await load_state_medicaid_csv_from_bytes(csv_content.encode(), db)
        assert r2.records_updated == 1
        assert r2.records_inserted == 0

        count = db.query(GovernmentProgramBin).filter(
            GovernmentProgramBin.bin == "666666"
        ).count()
        assert count == 1

    @pytest.mark.asyncio
    async def test_comment_lines_skipped(self, db: Session) -> None:
        from shared.data_ingestion.sources.gov_exclusion import load_state_medicaid_csv_from_bytes

        csv_content = (
            "# This is a comment line\n"
            "state,bin,pcn,group_number,plan_type,plan_subtype,pbm_name,"
            "plan_name,mco_name,confidence,source,source_date,notes\n"
            "# Another comment\n"
            "NY,777777,,,MEDICAID_MCO,,,NY Medicaid MCO,,,HIGH,NY DOH,2026-01-01,\n"
        )
        result = await load_state_medicaid_csv_from_bytes(csv_content.encode(), db)
        assert result.records_processed == 1
        assert result.records_inserted == 1

    @pytest.mark.asyncio
    async def test_invalid_bin_rejected(self, db: Session) -> None:
        from shared.data_ingestion.sources.gov_exclusion import load_state_medicaid_csv_from_bytes

        csv_content = (
            "state,bin,pcn,group_number,plan_type,plan_subtype,pbm_name,"
            "plan_name,mco_name,confidence,source,source_date,notes\n"
            "CA,ABCDEF,,,MEDICAID_FFS,,,Test,,,HIGH,Test,2026-01-01,bad bin\n"
        )
        result = await load_state_medicaid_csv_from_bytes(csv_content.encode(), db)
        assert result.records_errored == 1
        assert result.records_inserted == 0
        assert "ABCDEF" in result.error_details[0]["error"]

    @pytest.mark.asyncio
    async def test_missing_source_rejected(self, db: Session) -> None:
        from shared.data_ingestion.sources.gov_exclusion import load_state_medicaid_csv_from_bytes

        csv_content = (
            "state,bin,pcn,group_number,plan_type,plan_subtype,pbm_name,"
            "plan_name,mco_name,confidence,source,source_date,notes\n"
            "CA,888888,,,MEDICAID_FFS,,,Test,,,,2026-01-01,no source\n"
        )
        result = await load_state_medicaid_csv_from_bytes(csv_content.encode(), db)
        assert result.records_errored == 1
        assert "source" in result.error_details[0]["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_plan_type_rejected(self, db: Session) -> None:
        from shared.data_ingestion.sources.gov_exclusion import load_state_medicaid_csv_from_bytes

        csv_content = (
            "state,bin,pcn,group_number,plan_type,plan_subtype,pbm_name,"
            "plan_name,mco_name,confidence,source,source_date,notes\n"
            "CA,999111,,,NOT_A_VALID_TYPE,,,Test,,,HIGH,Test,2026-01-01,\n"
        )
        result = await load_state_medicaid_csv_from_bytes(csv_content.encode(), db)
        assert result.records_errored == 1
        assert "plan_type" in result.error_details[0]["error"].lower()

    @pytest.mark.asyncio
    async def test_bin_left_padded_on_import(self, db: Session) -> None:
        from shared.data_ingestion.sources.gov_exclusion import load_state_medicaid_csv_from_bytes

        csv_content = (
            "state,bin,pcn,group_number,plan_type,plan_subtype,pbm_name,"
            "plan_name,mco_name,confidence,source,source_date,notes\n"
            "FL,3858,,,TRICARE,,,TRICARE,,,HIGH,TRICARE docs,2026-01-01,\n"
        )
        result = await load_state_medicaid_csv_from_bytes(csv_content.encode(), db)
        assert result.records_inserted == 1
        row = db.query(GovernmentProgramBin).filter(
            GovernmentProgramBin.bin == "003858",
            GovernmentProgramBin.plan_type == "TRICARE",
        ).first()
        assert row is not None
        assert row.bin == "003858"

    @pytest.mark.asyncio
    async def test_invalid_state_code_rejected(self, db: Session) -> None:
        from shared.data_ingestion.sources.gov_exclusion import load_state_medicaid_csv_from_bytes

        csv_content = (
            "state,bin,pcn,group_number,plan_type,plan_subtype,pbm_name,"
            "plan_name,mco_name,confidence,source,source_date,notes\n"
            "XX,112233,,,MEDICAID_FFS,,,Test,,,HIGH,Test,2026-01-01,bad state\n"
        )
        result = await load_state_medicaid_csv_from_bytes(csv_content.encode(), db)
        assert result.records_errored == 1

    @pytest.mark.asyncio
    async def test_mixed_valid_and_invalid_rows(self, db: Session) -> None:
        from shared.data_ingestion.sources.gov_exclusion import load_state_medicaid_csv_from_bytes

        csv_content = (
            "state,bin,pcn,group_number,plan_type,plan_subtype,pbm_name,"
            "plan_name,mco_name,confidence,source,source_date,notes\n"
            # valid
            "WA,445566,,,MEDICAID_MCO,,,WA Medicaid,,,HIGH,WA HCA,2026-01-01,\n"
            # invalid — missing source
            "WA,556677,,,MEDICAID_MCO,,,WA Medicaid,,,,2026-01-01,\n"
            # valid
            "WA,667788,,,MEDICAID_FFS,,,WA FFS,,,HIGH,WA HCA,2026-01-01,\n"
        )
        result = await load_state_medicaid_csv_from_bytes(csv_content.encode(), db)
        assert result.records_processed == 3
        assert result.records_inserted == 2
        assert result.records_errored == 1


# ---------------------------------------------------------------------------
# Federal seed idempotency test
# ---------------------------------------------------------------------------


class TestFederalSeed:
    def test_seed_is_idempotent(self, db: Session) -> None:
        from shared.data_ingestion.sources.gov_exclusion_federal_seed import seed_federal_programs

        result1 = seed_federal_programs(db)
        assert result1["inserted"] > 0

        count_after_first = db.query(GovernmentProgramBin).count()

        result2 = seed_federal_programs(db)
        # Second run: all rows already exist — should update only
        assert result2["inserted"] == 0
        assert result2["updated"] == result1["inserted"]

        count_after_second = db.query(GovernmentProgramBin).count()
        assert count_after_first == count_after_second

    def test_seed_tricare_present(self, db: Session) -> None:
        from shared.data_ingestion.sources.gov_exclusion_federal_seed import seed_federal_programs

        seed_federal_programs(db)
        tricare = db.query(GovernmentProgramBin).filter(
            GovernmentProgramBin.bin == "003858",
            GovernmentProgramBin.pcn == "A4",
            GovernmentProgramBin.plan_type == "TRICARE",
        ).first()
        assert tricare is not None
        assert tricare.confidence == "HIGH"
        assert tricare.government_flag is True

    def test_seed_medicare_part_d_optumrx_present(self, db: Session) -> None:
        from shared.data_ingestion.sources.gov_exclusion_federal_seed import seed_federal_programs

        seed_federal_programs(db)
        row = db.query(GovernmentProgramBin).filter(
            GovernmentProgramBin.bin == "610494",
            GovernmentProgramBin.plan_type == "MEDICARE_PART_D",
        ).first()
        assert row is not None

    def test_seed_fep_present(self, db: Session) -> None:
        from shared.data_ingestion.sources.gov_exclusion_federal_seed import seed_federal_programs

        seed_federal_programs(db)
        fep = db.query(GovernmentProgramBin).filter(
            GovernmentProgramBin.plan_type == "FEP",
        ).first()
        assert fep is not None

    def test_seed_va_present(self, db: Session) -> None:
        from shared.data_ingestion.sources.gov_exclusion_federal_seed import seed_federal_programs

        seed_federal_programs(db)
        va = db.query(GovernmentProgramBin).filter(
            GovernmentProgramBin.plan_type == "VA",
        ).first()
        assert va is not None

    def test_seed_champva_present(self, db: Session) -> None:
        from shared.data_ingestion.sources.gov_exclusion_federal_seed import seed_federal_programs

        seed_federal_programs(db)
        champva = db.query(GovernmentProgramBin).filter(
            GovernmentProgramBin.plan_type == "CHAMPVA",
        ).first()
        assert champva is not None

    def test_seed_ihs_present(self, db: Session) -> None:
        from shared.data_ingestion.sources.gov_exclusion_federal_seed import seed_federal_programs

        seed_federal_programs(db)
        ihs = db.query(GovernmentProgramBin).filter(
            GovernmentProgramBin.plan_type == "IHS",
        ).first()
        assert ihs is not None

    def test_tricare_bin_only_is_medium(self, db: Session) -> None:
        from shared.data_ingestion.sources.gov_exclusion_federal_seed import seed_federal_programs

        seed_federal_programs(db)
        medium_row = db.query(GovernmentProgramBin).filter(
            GovernmentProgramBin.bin == "003858",
            GovernmentProgramBin.pcn.is_(None),
            GovernmentProgramBin.plan_type == "TRICARE",
        ).first()
        assert medium_row is not None
        assert medium_row.confidence == "MEDIUM"
