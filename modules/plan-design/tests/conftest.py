"""Shared fixtures for plan-design module tests.

Uses SAVEPOINT-based transaction isolation (LESSON-001) for any test that
calls db.commit() inside route/service logic.

Uses _UUIDString TypeDecorator (LESSON-007) to avoid PG_UUID/SQLite float issue.
"""

from __future__ import annotations

import os
import sys
import uuid
from collections.abc import Iterator
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

from src.models.tables import PlanDesignBase


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
# Standard test UUIDs
# ---------------------------------------------------------------------------

TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")
USER_A = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _configure_test_auth():
    """Configure in-memory auth once per test session."""
    from shared.auth.dependencies import CurrentUser, configure_auth
    from shared.auth.tokens_repo import InMemoryRevokedTokenRepo

    global _FAKE_USER_FOR_TESTS
    _FAKE_USER_FOR_TESTS = CurrentUser(
        id=USER_A,
        tenant_id=TENANT_A,
        email="test@example.com",
        status="active",
        roles=("tenant_admin",),
    )
    configure_auth(
        user_loader=lambda uid: _FAKE_USER_FOR_TESTS if uid == USER_A else None,
        revoked_repo=InMemoryRevokedTokenRepo(),
    )


_FAKE_USER_FOR_TESTS = None  # type: ignore[assignment]
_configure_test_auth()


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

    # SQLite doesn't support schemas — remove schema prefix
    for table in PlanDesignBase.metadata.tables.values():
        table.schema = None
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
            elif isinstance(col.type, PG_UUID):
                col.type = _UUIDString()

    PlanDesignBase.metadata.create_all(engine)
    yield engine
    PlanDesignBase.metadata.drop_all(engine)
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
