"""Shared test fixtures for reclaimrx module."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import JSON, String, create_engine, event
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import TypeDecorator
from src._shim.auth import CurrentUser, set_current_user
from src._shim.db import Base
from src._shim.events import reset_events

TEST_TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
TEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


# ---------------------------------------------------------------------------
# LESSON-007: PG_UUID(as_uuid=True) returns floats under SQLite SAVEPOINT
# sessions.  Store UUIDs as VARCHAR(36) in SQLite-backed test fixtures.
# ---------------------------------------------------------------------------
class _UUIDString(TypeDecorator):
    """SQLite-compatible UUID stored as VARCHAR(36)."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):  # type: ignore[override]
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):  # type: ignore[override]
        return uuid.UUID(value) if value is not None else None


def _sqlite_compat_swap() -> None:
    """Register SQLite-compatible type variants on all registered ORM tables.

    Must be called AFTER all model modules are imported (so Base.metadata
    is fully populated) and BEFORE create_all.

    Uses TypeEngine.with_variant() so the base type (JSONB, PG_UUID, ARRAY)
    is preserved for Postgres while SQLite gets a compatible alternative.
    This is non-destructive: Postgres-gated tests running later in the same
    process continue to emit the correct Postgres-native types.

    Variants registered:
      JSONB        -> JSON        (sqlite dialect)
      PG_UUID      -> _UUIDString (sqlite dialect)
      ARRAY(...)   -> JSON        (sqlite dialect, lists serialised as JSON arrays)

    Does NOT touch table.schema.  SQLite schema resolution is handled by
    ATTACHing ':memory:' AS reclaimrx on every connection (see
    _attach_reclaimrx_schema_on_connect).  This keeps Base.metadata
    schema-qualified at all times.
    """
    for table in Base.metadata.tables.values():
        for col in table.columns:
            # Guard: skip if this dialect variant is already registered (idempotent
            # when multiple test modules import and call this function).
            if "sqlite" in getattr(col.type, "_variant_mapping", {}):
                continue
            if isinstance(col.type, JSONB):
                col.type = col.type.with_variant(JSON(), "sqlite")
            elif isinstance(col.type, PG_UUID):
                col.type = col.type.with_variant(_UUIDString(), "sqlite")
            elif isinstance(col.type, ARRAY):
                col.type = col.type.with_variant(JSON(), "sqlite")


def _attach_reclaimrx_schema_on_connect(dbapi_conn, _connection_record) -> None:
    """Pool-level 'connect' listener: ATTACH ':memory:' AS reclaimrx on every
    new DBAPI connection so schema-qualified DDL/DML resolves on SQLite.

    Registered via sqlalchemy event.listen(engine, 'connect', ...) before
    any connections are drawn, so it fires for the very first connection too.
    """
    dbapi_conn.execute("ATTACH DATABASE ':memory:' AS reclaimrx")


@pytest.fixture(autouse=True)
def reset_event_bus() -> None:
    reset_events()


@pytest.fixture(scope="session")
def engine():
    """Single in-memory SQLite engine, single persistent connection, tables created once.

    Imports all ORM model modules so Base.metadata is fully populated, then
    applies the LESSON-007 type-swap (JSONB->JSON, PG_UUID->VARCHAR36,
    ARRAY->JSON) before create_all so SQLite can render all column types.

    Schema handling: Base.metadata tables with schema='reclaimrx' are NOT
    stripped.  StaticPool ensures a single underlying DBAPI connection is
    reused for all engine.connect() calls, so the ATTACH executed on first
    connect (via the pool-level event) persists for the entire session and
    all reclaimrx-schema tables are visible to every Session.  This keeps
    Base.metadata schema-qualified so Postgres-gated tests running in the
    same process always emit fully-qualified 'reclaimrx.<table>' queries.
    """
    from sqlalchemy.pool import StaticPool

    # Register the ATTACH listener BEFORE the engine is created so it fires
    # on the very first DBAPI connection.
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    event.listen(eng, "connect", _attach_reclaimrx_schema_on_connect)

    # Import all ORM models so Base.metadata is fully populated before create_all.
    import src.models.tables  # noqa: F401, PLC0415
    import src.models.detection_run_models  # noqa: F401, PLC0415

    # Swap Postgres-only column types to SQLite-compatible equivalents (LESSON-007).
    # Does NOT touch table.schema — ATTACH handles schema resolution above.
    _sqlite_compat_swap()

    # Create tables; the ATTACH event fires on first connect so 'reclaimrx' schema
    # is available for schema-qualified CREATE TABLE statements.
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
    """Alias for `db` -- used by A2 tests (outbox, dispatcher, scheduler)."""
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