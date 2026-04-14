"""Shared test fixtures for drug-database module.

LESSON-001: Uses SAVEPOINT-based isolation for tests that call db.commit().
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
from sqlalchemy.orm import Session, sessionmaker

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

    DrugBase.metadata.create_all(engine)
    yield engine
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
    return {
        "ndc_11": ndc_11,
        "ndc_formatted": f"{ndc_11[:5]}-{ndc_11[5:9]}-{ndc_11[9:]}",
        "labeler_code": ndc_11[:5],
        "product_code": ndc_11[5:9],
        "package_code": ndc_11[9:],
        "drug_name_display": drug_name_display,
        "nonproprietary_name": nonproprietary_name,
        "data_source": data_source,
        "drug_type": drug_type,
        "marketing_status": marketing_status,
        "is_active": is_active,
        "is_specialty": is_specialty,
        "is_biosimilar": False,
        "is_glp1": False,
        "unit_dose": False,
        "is_limited_distribution": False,
        "last_updated_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


def make_pricing(
    ndc_11: str = "00093314905",
    price_type: str = "NADAC",
    price_per_unit: Decimal = Decimal("0.045000"),
    effective_date: date = date(2026, 1, 1),
    data_source: str = "cms_nadac",
    termination_date: date | None = None,
) -> dict:
    return {
        "ndc_11": ndc_11,
        "price_type": price_type,
        "price_per_unit": price_per_unit,
        "unit_type": "EA",
        "effective_date": effective_date,
        "termination_date": termination_date,
        "data_source": data_source,
        "created_at": datetime.now(timezone.utc),
    }
