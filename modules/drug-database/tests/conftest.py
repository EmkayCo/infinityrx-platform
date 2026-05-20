"""Shared test fixtures for drug-database module.

LESSON-001: Uses SAVEPOINT-based isolation for tests that call db.commit().

Creates tables for all three ORM bases used by the module:
  DrugBase     (tables.py)      — clinical, pricing overrides, REMS, etc.
  NDCBase      (ndc_tables.py)  — seeded FDA NDC drugs/packages tables
  PricingBase  (pricing_tables.py) — seeded NADAC/ASP pricing tables
"""
from __future__ import annotations

import sys
import uuid
from collections.abc import Iterator
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from src.models.ndc_tables import NDCBase
from src.models.pricing_tables import PricingBase
from src.models.tables import DrugBase


@pytest.fixture(scope="session")
def _engine():
    # Named shared-memory SQLite so all connections share the same database.
    engine = create_engine(
        "sqlite:///file:drug_test_shared?mode=memory&cache=shared&uri=true",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # SQLite doesn't support schemas — strip schema prefix for tests
    for table in DrugBase.metadata.tables.values():
        table.schema = None
    for table in NDCBase.metadata.tables.values():
        table.schema = None
    for table in PricingBase.metadata.tables.values():
        table.schema = None

    DrugBase.metadata.create_all(engine)
    NDCBase.metadata.create_all(engine)
    PricingBase.metadata.create_all(engine)
    yield engine
    PricingBase.metadata.drop_all(engine)
    NDCBase.metadata.drop_all(engine)
    DrugBase.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(_engine) -> Iterator[Session]:
    """SAVEPOINT-isolated session (LESSON-001)."""
    connection = _engine.connect()
    outer = connection.begin()
    nested = connection.begin_nested()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, transaction):
        nonlocal nested
        if transaction.nested and not transaction._parent.nested:
            nested = connection.begin_nested()

    yield session
    session.close()
    outer.rollback()
    connection.close()


# Standard IDs
TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def tenant_id() -> uuid.UUID:
    return TENANT_A


@pytest.fixture
def other_tenant_id() -> uuid.UUID:
    return TENANT_B


def make_drug_row(
    product_id: str = "00093-3149",
    product_ndc: str = "00093-3149",
    ndc_11: str = "00093314900",
    non_proprietary_name: str = "metformin hydrochloride",
    proprietary_name: str | None = None,
    labeler_name: str = "Teva Pharmaceuticals",
    marketing_category_name: str = "ANDA",
) -> dict:
    """Factory for Drug (seeded FDA NDC schema) test rows."""
    now = datetime.now(timezone.utc)
    return {
        "product_id": product_id,
        "product_ndc": product_ndc,
        "ndc_11": ndc_11,
        "non_proprietary_name": non_proprietary_name,
        "proprietary_name": proprietary_name,
        "labeler_name": labeler_name,
        "marketing_category_name": marketing_category_name,
        "ndc_exclude_flag": None,
        "created_at": now,
        "updated_at": now,
    }


def make_nadac_pricing(
    ndc_11: str = "00093314900",
    nadac_per_unit: Decimal = Decimal("0.045000"),
    effective_date: date = date(2026, 1, 1),
    pricing_unit: str = "EA",
) -> dict:
    """Factory for DrugNADACPricing test rows."""
    now = datetime.now(timezone.utc)
    return {
        "ndc_11": ndc_11,
        "nadac_per_unit": nadac_per_unit,
        "effective_date": effective_date,
        "pricing_unit": pricing_unit,
        "as_of_date": effective_date,
        "created_at": now,
        "updated_at": now,
    }


# Legacy helpers kept for tests that still import them
def make_drug(
    ndc_11: str = "00093314905",
    drug_name_display: str = "Metformin 500mg",
    data_source: str = "fda_ndc",
    drug_type: str = "generic",
    marketing_status: str = "active",
    is_active: bool = True,
    is_specialty: bool = False,
    nonproprietary_name: str = "metformin hydrochloride",
) -> dict:
    """Legacy factory — kept for unit tests that still reference it."""
    return make_drug_row(
        non_proprietary_name=nonproprietary_name,
    )


def make_pricing(
    ndc_11: str = "00093314905",
    price_type: str = "NADAC",
    price_per_unit: Decimal = Decimal("0.045000"),
    effective_date: date = date(2026, 1, 1),
    data_source: str = "cms_nadac",
    termination_date: date | None = None,
) -> dict:
    """Legacy factory — kept for unit tests that still reference it."""
    return make_nadac_pricing(
        ndc_11=ndc_11,
        nadac_per_unit=price_per_unit,
        effective_date=effective_date,
    )
