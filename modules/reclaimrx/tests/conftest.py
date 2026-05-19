"""Shared test fixtures for reclaimrx module."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from src._shim.auth import CurrentUser, set_current_user
from src._shim.db import Base
from src._shim.events import reset_events

TEST_TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
TEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture(autouse=True)
def reset_event_bus() -> None:
    reset_events()


@pytest.fixture(scope="session")
def engine():
    """Single in-memory SQLite engine, single persistent connection, tables created once."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )

    # Keep a single connection alive so in-memory tables persist for the whole session.
    _conn = eng.connect()
    Base.metadata.create_all(_conn)
    _conn.commit()

    # Point the shim at this engine so service code uses the same DB.
    import src._shim.db as _shim_db
    _shim_db._engine = eng
    _shim_db._SessionLocal = sessionmaker(bind=eng, expire_on_commit=False, future=True)

    yield eng

    _conn.close()
    eng.dispose()


@pytest.fixture()
def db(engine) -> Session:
    """Function-scoped session; each test runs inside a SAVEPOINT rolled back on teardown."""
    connection = engine.connect()
    # Outer transaction: never committed, rolled back at teardown.
    outer = connection.begin()
    # Nested SAVEPOINT for SQLAlchemy-level rollback isolation.
    nested = connection.begin_nested()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")  # type: ignore[call-arg]

    # Re-open the savepoint on each commit so services can call session.commit() freely.
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, transaction):
        nonlocal nested
        if transaction.nested and not transaction._parent.nested:
            nested = connection.begin_nested()

    yield session

    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def default_user():
    user = CurrentUser(id=TEST_USER_ID, tenant_id=TEST_TENANT_ID)
    set_current_user(user)
    yield
    set_current_user(None)


@pytest.fixture()
def db_session(db) -> Session:
    """Alias for `db` — used by A2 tests (outbox, dispatcher, scheduler)."""
    return db


@pytest.fixture()
def tenant_a_id() -> str:
    """Return TEST_TENANT_ID as a string (used by atomicity integration tests)."""
    return str(TEST_TENANT_ID)


@pytest.fixture()
def mock_event_bus():
    """Mock EventBus with async publish for dispatcher unit tests."""
    bus = MagicMock()
    bus.publish = AsyncMock(return_value=None)
    return bus


@pytest.fixture()
async def async_db_engine():
    """Async SQLite in-memory engine for DLQ repository tests.

    EventDLQEntry uses schema='core' (Postgres-specific). SQLite supports schema
    aliases via ATTACH DATABASE. We attach a second in-memory database as 'core'
    so the ORM's 'core.event_dlq' table reference resolves correctly.
    The table is created via raw DDL to avoid JSONB/UUID column type issues.
    """
    from sqlalchemy import text
    from sqlalchemy.pool import StaticPool

    # Use a named file-based in-memory DB so ATTACH can reference the same
    # connection. StaticPool ensures the same underlying connection is reused.
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        # Attach a second in-memory DB as 'core' schema alias
        await conn.execute(text("ATTACH DATABASE ':memory:' AS core"))
        await conn.execute(text(
            "CREATE TABLE IF NOT EXISTS core.event_dlq ("
            "  id TEXT PRIMARY KEY,"
            "  event_id TEXT,"
            "  tenant_id TEXT,"
            "  event_type TEXT NOT NULL,"
            "  envelope TEXT,"
            "  failure_reason TEXT,"
            "  attempt_count INTEGER DEFAULT 0,"
            "  first_failed_at DATETIME,"
            "  last_failed_at DATETIME,"
            "  dlq_topic TEXT,"
            "  replayed_at DATETIME,"
            "  status TEXT DEFAULT 'queued'"
            ")"
        ))

    yield engine
    await engine.dispose()
