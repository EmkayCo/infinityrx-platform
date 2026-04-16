"""Shared fixtures for prior-authorization module tests.

Uses SAVEPOINT-based transaction isolation (LESSON-001) for any test that
calls db.commit() inside route/service logic.

Uses _UUIDString TypeDecorator (LESSON-007) to avoid PG_UUID/SQLite float issue.
"""
from __future__ import annotations

import os
import sys
import uuid
from collections.abc import Iterator
from datetime import date
from pathlib import Path

# Add module root to sys.path so imports use `src.*`
_MODULE_ROOT = Path(__file__).resolve().parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

# Add platform root to sys.path so `shared.*` resolves
_PLATFORM_ROOT = _MODULE_ROOT.parent.parent
if str(_PLATFORM_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLATFORM_ROOT))

# Minimal crypto env so EncryptedString works in SQLite tests
os.environ.setdefault("ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM=")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")

import pytest
from sqlalchemy import JSON, String, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

class _UUIDString(TypeDecorator):
    """SQLite-compatible UUID stored as VARCHAR(36). Fixes LESSON-007 float bug."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(value)


# ---------------------------------------------------------------------------
# Patch metadata at import time -- BEFORE any ORM objects are constructed.
# This prevents mapper compilation with PG_UUID types that fail on SQLite.
# ---------------------------------------------------------------------------

from src.models.tables import PriorAuthBase

for _table in PriorAuthBase.metadata.tables.values():
    _table.schema = None
    for _col in _table.columns:
        if isinstance(_col.type, JSONB):
            _col.type = JSON()
        elif isinstance(_col.type, PG_UUID):
            _col.type = _UUIDString()


# ---------------------------------------------------------------------------
# Standard test UUIDs
# ---------------------------------------------------------------------------

TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")
USER_A = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
MEMBER_1 = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PLAN_1 = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
PA_1 = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


@pytest.fixture(scope="session")
def _engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    PriorAuthBase.metadata.create_all(engine)
    yield engine
    PriorAuthBase.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(_engine) -> Iterator[Session]:
    """SAVEPOINT-based isolation (LESSON-001) for tests that commit inside routes."""
    connection = _engine.connect()
    outer = connection.begin()
    nested = connection.begin_nested()
    session_factory = sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    session = session_factory()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, transaction):
        nonlocal nested
        if transaction.nested and not transaction._parent.nested:
            nested = connection.begin_nested()

    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def tenant_id() -> uuid.UUID:
    return TENANT_A


@pytest.fixture
def other_tenant_id() -> uuid.UUID:
    return TENANT_B


@pytest.fixture
def user_id() -> uuid.UUID:
    return USER_A


@pytest.fixture
def member_id() -> uuid.UUID:
    return MEMBER_1


@pytest.fixture
def plan_id() -> uuid.UUID:
    return PLAN_1
