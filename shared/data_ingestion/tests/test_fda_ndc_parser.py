"""Tests for the FDA NDC Directory ingestion pipeline.

Covers:
- Product.txt parsing (all 20 fields)
- NDC-11 normalization for all segment-width patterns
- Active ingredient explosion and sequence preservation
- Pharmacological class type extraction
- Mismatched ingredient length error capture
- Date parsing (empty → None)
- Upsert idempotency

SQLAlchemy isolation:
  SAVEPOINT-based per LESSON-001.
  _UUIDString TypeDecorator per LESSON-007 (no UUID columns in ndc_tables, but
  the shared IngestionRun table uses PG_UUID — so we patch that here).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import JSON, BigInteger, Integer, String, create_engine, event, text
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

# --- imports ----------------------------------------------------------------
import sys

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DRUG_DB_ROOT = _REPO_ROOT / "modules" / "drug-database"

# Add both repo root and drug-database module root to path so src.* imports work
for _p in (str(_REPO_ROOT), str(_DRUG_DB_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from shared.data_ingestion.models import IngestionRun, IngestionSchedule
from shared.data_ingestion.sources.fda_ndc import (
    _extract_class_type,
    _parse_date,
    _parse_packages,
    _parse_products,
    normalize_ndc_11,
)
from shared.db.base import Base

# Import NDC models (drug-database is on sys.path so src.* resolves)
from src.models.ndc_tables import (  # type: ignore[import]
    Drug,
    DrugActiveIngredient,
    DrugPackage,
    DrugPharmClass,
    NDCBase,
    SCHEMA as NDC_SCHEMA,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_DIR = Path(__file__).parent / "sample_data" / "fda_ndc"


class _UUIDString(TypeDecorator):
    """SQLite-compatible UUID stored as VARCHAR(36). LESSON-007."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        return str(value) if value is not None else None

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:
        return uuid.UUID(str(value)) if value is not None else None


def _patch_ingestion_tables_for_sqlite() -> None:
    """Patch shared IngestionRun/IngestionSchedule for SQLite SAVEPOINT compatibility."""
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


_patch_ingestion_tables_for_sqlite()


def _patch_ndc_tables_for_sqlite() -> None:
    """Patch NDC table columns for SQLite compatibility.

    SQLite only supports INTEGER PRIMARY KEY for autoincrement.
    BigInteger PKs become 'BIGINT NOT NULL' in SQLite DDL and do not
    auto-generate values on INSERT — must be patched to Integer.
    """
    for table in [
        DrugPackage.__table__,
        DrugActiveIngredient.__table__,
        DrugPharmClass.__table__,
    ]:
        if getattr(table, "_sqlite_patched", False):
            continue
        for col in table.columns:
            if isinstance(col.type, BigInteger) and col.primary_key:
                col.type = Integer()
        table._sqlite_patched = True  # type: ignore[attr-defined]


_patch_ndc_tables_for_sqlite()


@pytest.fixture(scope="session")
def _engine():
    """Session-scoped in-memory SQLite with drug_database schema mapped to root.

    Both the shared IngestionRun/IngestionSchedule tables AND the NDC tables
    are created here. SQLite does not support named schemas, so we use
    schema_translate_map to strip them.
    """
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
        schema_translate_map={"shared": None, NDC_SCHEMA: None}
    )

    # Create shared tables
    Base.metadata.create_all(
        engine,
        tables=[IngestionRun.__table__, IngestionSchedule.__table__],
    )
    # Create NDC tables
    NDCBase.metadata.create_all(engine)

    yield engine

    NDCBase.metadata.drop_all(engine)
    Base.metadata.drop_all(
        engine,
        tables=[IngestionRun.__table__, IngestionSchedule.__table__],
    )
    raw_engine.dispose()


@pytest.fixture
def db_session(_engine) -> Iterator[Session]:
    """SAVEPOINT-based isolated session per LESSON-001.

    Tests that call ``session.commit()`` are fully isolated — all changes
    roll back at teardown via the outer ``connection.begin()`` rollback.
    """
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
# Helper: insert a Drug row directly via ORM
# ---------------------------------------------------------------------------

def _insert_drug(db: Session, product_id: str, **kwargs: Any) -> Drug:
    drug = Drug(
        product_id=product_id,
        product_ndc=kwargs.get("product_ndc", product_id.split("_")[0]),
        ndc_11=kwargs.get("ndc_11", "00069420016"),
        **{k: v for k, v in kwargs.items() if k not in ("product_ndc", "ndc_11")},
    )
    db.add(drug)
    db.flush()
    return drug


# ===========================================================================
# 1. NDC-11 normalization
# ===========================================================================


class TestNormalizeNDC11:
    """All segment-width patterns must pad correctly (LESSON-004 anchors used inside)."""

    def test_already_11_digits(self) -> None:
        assert normalize_ndc_11("00069420016") == "00069420016"

    def test_already_11_digits_with_dashes(self) -> None:
        # 11-digit string with dashes — strip and return
        # After stripping "00069-4200-16" → 11 chars
        assert normalize_ndc_11("00069-4200-16") == "00069420016"

    def test_4_4_2_pattern(self) -> None:
        """4-4-2: labeler is 4 digits, zero-pad labeler to 5.

        "0069-4200-16" -> labeler=0069 (4), product=4200 (4), package=16 (2)
        Padded: labeler=00069, product=4200, package=16 -> "00069420016"
        """
        result = normalize_ndc_11("0069-4200-16")
        assert result == "00069420016"
        assert len(result) == 11

    def test_5_3_2_pattern(self) -> None:
        """5-3-2: product segment is 3 digits, zero-pad product to 4.

        "00069-420-16" -> labeler=00069 (5), product=420 (3), package=16 (2)
        Padded: labeler=00069, product=0420, package=16 -> "00069042016"
        """
        result = normalize_ndc_11("00069-420-16")
        assert result == "00069042016"
        assert len(result) == 11

    def test_5_4_1_pattern(self) -> None:
        """5-4-1: package segment is 1 digit, zero-pad package to 2.

        "00069-4200-6" -> labeler=00069 (5), product=4200 (4), package=6 (1)
        Padded: labeler=00069, product=4200, package=06 -> "00069420006"
        """
        result = normalize_ndc_11("00069-4200-6")
        assert result == "00069420006"
        assert len(result) == 11

    def test_invalid_too_short_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid NDC"):
            normalize_ndc_11("123")

    def test_invalid_non_digit_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid NDC"):
            normalize_ndc_11("ABCDE-1234-56")

    def test_invalid_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid NDC"):
            normalize_ndc_11("")


# ===========================================================================
# 2. Date parsing
# ===========================================================================


class TestDateParsing:
    def test_valid_yyyymmdd(self) -> None:
        assert _parse_date("19920731") == date(1992, 7, 31)

    def test_empty_string_returns_none(self) -> None:
        assert _parse_date("") is None

    def test_none_returns_none(self) -> None:
        assert _parse_date(None) is None

    def test_whitespace_only_returns_none(self) -> None:
        assert _parse_date("   ") is None

    def test_invalid_date_returns_none(self) -> None:
        assert _parse_date("99999999") is None


# ===========================================================================
# 3. Product.txt parsing — all 20 fields
# ===========================================================================


class TestParseProductAllFields:
    def test_parse_product_all_20_fields(self) -> None:
        """Every column from sample product.txt is parsed and mapped."""
        product_txt = _SAMPLE_DIR / "product.txt"
        rows = list(_parse_products(product_txt))

        # Should yield 10 rows from the 10-row sample
        assert len(rows) == 10
        assert all(r["table"] == "drugs" for r in rows)

        # Inspect the first row (Norvasc)
        norvasc = rows[0]["row"]
        assert norvasc["product_id"] == "0069-4200_0069-4200-16"
        assert norvasc["product_ndc"] == "0069-4200"
        assert norvasc["ndc_11"] is not None
        assert len(norvasc["ndc_11"]) == 11
        assert norvasc["product_type_name"] == "PRESCRIPTION"
        assert norvasc["proprietary_name"] == "Norvasc"
        assert norvasc["proprietary_name_suffix"] is None  # blank → None
        assert norvasc["non_proprietary_name"] == "Amlodipine Besylate"
        assert norvasc["dosage_form_name"] == "TABLET"
        assert norvasc["route_name"] == "ORAL"
        assert norvasc["start_marketing_date"] == date(1992, 7, 31)
        assert norvasc["end_marketing_date"] is None
        assert norvasc["marketing_category_name"] == "NDA"
        assert norvasc["application_number"] == "NDA019787"
        assert norvasc["labeler_name"] == "Pfizer Laboratories Div Pfizer Inc"
        assert norvasc["substance_name"] == "AMLODIPINE BESYLATE"
        assert norvasc["active_numerator_strength"] == "6.944"
        assert norvasc["active_ingred_unit"] == "MG"
        assert "Calcium Channel Blocker" in (norvasc["pharm_classes"] or "")
        assert norvasc["dea_schedule"] is None  # blank → None
        assert norvasc["ndc_exclude_flag"] == "N"
        assert norvasc["listing_record_certified_through"] == date(2026, 12, 31)

    def test_parse_oxycontin_dea_schedule(self) -> None:
        product_txt = _SAMPLE_DIR / "product.txt"
        rows = list(_parse_products(product_txt))
        oxy = next(r["row"] for r in rows if "1435" in r["row"]["product_id"])
        assert oxy["dea_schedule"] == "CII"

    def test_parse_discontinued_drug(self) -> None:
        product_txt = _SAMPLE_DIR / "product.txt"
        rows = list(_parse_products(product_txt))
        # Trulicity has end_marketing_date = 20231001
        trulicity = next(r["row"] for r in rows if "7140" in r["row"]["product_id"])
        assert trulicity["end_marketing_date"] == date(2023, 10, 1)

    def test_parse_otc_drug(self) -> None:
        product_txt = _SAMPLE_DIR / "product.txt"
        rows = list(_parse_products(product_txt))
        tylenol = next(r["row"] for r in rows if "50580" in r["row"]["product_id"])
        assert tylenol["product_type_name"] == "OTC"
        assert tylenol["proprietary_name"] == "Tylenol"
        assert tylenol["proprietary_name_suffix"] == "Extra Strength"

    def test_parse_biosimilar(self) -> None:
        product_txt = _SAMPLE_DIR / "product.txt"
        rows = list(_parse_products(product_txt))
        zarxio = next(r["row"] for r in rows if "57894" in r["row"]["product_id"])
        assert zarxio["marketing_category_name"] == "BLA"

    def test_generic_only_no_brand(self) -> None:
        product_txt = _SAMPLE_DIR / "product.txt"
        rows = list(_parse_products(product_txt))
        metformin = next(r["row"] for r in rows if "0781" in r["row"]["product_id"])
        assert metformin["proprietary_name"] is None
        assert metformin["non_proprietary_name"] == "Metformin Hydrochloride"


# ===========================================================================
# 4. Package.txt parsing
# ===========================================================================


class TestParsePackages:
    def test_parse_package_rows(self) -> None:
        package_txt = _SAMPLE_DIR / "package.txt"
        rows = list(_parse_packages(package_txt))
        assert len(rows) == 5
        assert all(r["table"] == "drug_packages" for r in rows)

    def test_package_ndc_11_normalized(self) -> None:
        package_txt = _SAMPLE_DIR / "package.txt"
        rows = list(_parse_packages(package_txt))
        for row in rows:
            assert len(row["row"]["ndc_package_code_11"]) == 11

    def test_package_maps_to_product(self) -> None:
        package_txt = _SAMPLE_DIR / "package.txt"
        rows = list(_parse_packages(package_txt))
        product_ids = {r["row"]["product_id"] for r in rows}
        # Two Norvasc packages map to same product_id
        assert "0069-4200_0069-4200-16" in product_ids

    def test_discontinued_package_end_date(self) -> None:
        package_txt = _SAMPLE_DIR / "package.txt"
        rows = list(_parse_packages(package_txt))
        trulicity_pkg = next(
            r["row"] for r in rows if "7140" in r["row"]["product_id"]
        )
        assert trulicity_pkg["end_marketing_date"] == date(2023, 10, 1)


# ===========================================================================
# 5. Active ingredient explosion
# ===========================================================================


class TestIngredientsExplodedPreserveSequence:
    def test_single_ingredient(self, db_session: Session) -> None:
        """Single-ingredient drug yields one row with sequence=0."""
        drug = _insert_drug(
            db_session,
            product_id="TEST-SINGLE",
            substance_name="AMLODIPINE BESYLATE",
            active_numerator_strength="6.944",
            active_ingred_unit="MG",
        )
        from src.services.ndc_ingestion import NDCIngestionService  # type: ignore[import]
        svc = NDCIngestionService(db_session=db_session)
        svc._reload_children_for_all_drugs([])

        ingredients = db_session.query(DrugActiveIngredient).filter_by(
            drug_id="TEST-SINGLE"
        ).all()
        assert len(ingredients) == 1
        assert ingredients[0].sequence == 0
        assert ingredients[0].substance_name == "AMLODIPINE BESYLATE"
        assert ingredients[0].numerator_strength == Decimal("6.944000")
        assert ingredients[0].unit == "MG"

    def test_multi_ingredient_three_substances(self, db_session: Session) -> None:
        """3-ingredient row yields 3 rows with sequence 0, 1, 2."""
        drug = _insert_drug(
            db_session,
            product_id="TEST-MULTI",
            substance_name="LISINOPRIL;HYDROCHLOROTHIAZIDE;MAGNESIUM STEARATE",
            active_numerator_strength="10;12.5;5",
            active_ingred_unit="MG;MG;MG",
            ndc_11="00268560031",
        )
        from src.services.ndc_ingestion import NDCIngestionService  # type: ignore[import]
        svc = NDCIngestionService(db_session=db_session)
        svc._reload_children_for_all_drugs([])

        ingredients = (
            db_session.query(DrugActiveIngredient)
            .filter_by(drug_id="TEST-MULTI")
            .order_by(DrugActiveIngredient.sequence)
            .all()
        )
        assert len(ingredients) == 3
        assert [i.sequence for i in ingredients] == [0, 1, 2]
        assert ingredients[0].substance_name == "LISINOPRIL"
        assert ingredients[1].substance_name == "HYDROCHLOROTHIAZIDE"
        assert ingredients[2].substance_name == "MAGNESIUM STEARATE"

    def test_non_numeric_strength_is_null(self, db_session: Session) -> None:
        """Non-numeric strength like 'q.s.' is stored as NULL, not 0."""
        drug = _insert_drug(
            db_session,
            product_id="TEST-QS",
            substance_name="WATER",
            active_numerator_strength="q.s.",
            active_ingred_unit="mL",
            ndc_11="00001234567",
        )
        from src.services.ndc_ingestion import NDCIngestionService  # type: ignore[import]
        svc = NDCIngestionService(db_session=db_session)
        svc._reload_children_for_all_drugs([])

        ingredient = db_session.query(DrugActiveIngredient).filter_by(
            drug_id="TEST-QS"
        ).one()
        assert ingredient.numerator_strength is None

    def test_meq_unit_preserved(self, db_session: Session) -> None:
        """MEQ unit (potassium chloride) is preserved exactly."""
        drug = _insert_drug(
            db_session,
            product_id="TEST-MEQ",
            substance_name="POTASSIUM CHLORIDE",
            active_numerator_strength="20",
            active_ingred_unit="MEQ/100ML",
            ndc_11="01439924025",
        )
        from src.services.ndc_ingestion import NDCIngestionService  # type: ignore[import]
        svc = NDCIngestionService(db_session=db_session)
        svc._reload_children_for_all_drugs([])

        ingredient = db_session.query(DrugActiveIngredient).filter_by(
            drug_id="TEST-MEQ"
        ).one()
        assert ingredient.unit == "MEQ/100ML"
        assert ingredient.numerator_strength == Decimal("20.000000")


# ===========================================================================
# 6. Pharmacological class type extraction
# ===========================================================================


class TestPharmClassTypeExtraction:
    def test_epc_type_extracted(self) -> None:
        text, ctype = _extract_class_type("Beta Blocker [EPC]")
        assert text == "Beta Blocker"
        assert ctype == "EPC"

    def test_moa_type_extracted(self) -> None:
        text, ctype = _extract_class_type("Calcium Channel Antagonists [MoA]")
        assert text == "Calcium Channel Antagonists"
        assert ctype == "MoA"

    def test_pe_type_extracted(self) -> None:
        text, ctype = _extract_class_type("Increased Diuresis [PE]")
        assert text == "Increased Diuresis"
        assert ctype == "PE"

    def test_cs_type_extracted(self) -> None:
        text, ctype = _extract_class_type("GABA Receptor Agonist [CS]")
        assert text == "GABA Receptor Agonist"
        assert ctype == "CS"

    def test_no_type_marker_returns_none(self) -> None:
        text, ctype = _extract_class_type("Angiotensin 2 Receptor Blocker")
        assert text == "Angiotensin 2 Receptor Blocker"
        assert ctype is None

    def test_pharm_classes_exploded_in_db(self, db_session: Session) -> None:
        drug = _insert_drug(
            db_session,
            product_id="TEST-PC",
            pharm_classes="Calcium Channel Blocker [EPC],Calcium Channel Antagonists [MoA]",
            ndc_11="00695770030",
        )
        from src.services.ndc_ingestion import NDCIngestionService  # type: ignore[import]
        svc = NDCIngestionService(db_session=db_session)
        svc._reload_children_for_all_drugs([])

        classes = (
            db_session.query(DrugPharmClass)
            .filter_by(drug_id="TEST-PC")
            .order_by(DrugPharmClass.sequence)
            .all()
        )
        assert len(classes) == 2
        assert classes[0].pharm_class == "Calcium Channel Blocker"
        assert classes[0].class_type == "EPC"
        assert classes[1].pharm_class == "Calcium Channel Antagonists"
        assert classes[1].class_type == "MoA"


# ===========================================================================
# 7. Mismatched ingredient lengths → error sample captured
# ===========================================================================


class TestMismatchedIngredientLengthsCapturedInErrorSamples:
    def test_mismatch_skips_drug_and_records_error(self, db_session: Session) -> None:
        """SUBSTANCENAME has 3 items but STRENGTH has 2 → drug skipped, error captured."""
        drug = _insert_drug(
            db_session,
            product_id="TEST-MISMATCH",
            substance_name="DRUG_A;DRUG_B;DRUG_C",
            active_numerator_strength="100;200",  # only 2, not 3
            active_ingred_unit="MG;MG;MG",
            ndc_11="00001111111",
        )
        error_samples: list[dict[str, Any]] = []

        from src.services.ndc_ingestion import NDCIngestionService  # type: ignore[import]
        svc = NDCIngestionService(db_session=db_session)
        svc._reload_children_for_all_drugs(error_samples)

        # No ingredient rows should be created for this drug
        count = db_session.query(DrugActiveIngredient).filter_by(
            drug_id="TEST-MISMATCH"
        ).count()
        assert count == 0

        # Error should be captured
        assert len(error_samples) >= 1
        assert any("mismatch" in str(e).lower() for e in error_samples)


# ===========================================================================
# 8. Upsert idempotency
# ===========================================================================


class TestUpsertIdempotency:
    def test_drug_upsert_is_idempotent(self, db_session: Session) -> None:
        """Upserting the same product_id twice leaves exactly one row."""
        from src.services.ndc_ingestion import NDCIngestionService  # type: ignore[import]
        from datetime import datetime, timezone

        svc = NDCIngestionService(db_session=db_session)

        row = {
            "product_id": "TEST-IDEM",
            "product_ndc": "0001-1111",
            "ndc_11": "00011111100",
            "proprietary_name": "TestDrug v1",
            "updated_at": datetime.now(timezone.utc),
        }

        svc._upsert_drug_batch([row])
        db_session.flush()

        # Update the proprietary_name
        row2 = {**row, "proprietary_name": "TestDrug v2",
                 "updated_at": datetime.now(timezone.utc)}
        svc._upsert_drug_batch([row2])
        db_session.flush()

        drugs = db_session.query(Drug).filter_by(product_id="TEST-IDEM").all()
        assert len(drugs) == 1
        # The second upsert should have updated the name
        assert drugs[0].proprietary_name == "TestDrug v2"
