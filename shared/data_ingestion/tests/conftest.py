"""Test fixtures for shared.data_ingestion tests.

Uses SAVEPOINT-based transaction isolation per LESSON-001 so tests that call
``session.commit()`` inside service/base logic do not leak data across tests.

Uses ``_UUIDString`` TypeDecorator per LESSON-007 to avoid the PG_UUID BLOB→float
bug under SQLite SAVEPOINT sessions.

Schema handling: SQLite does not support named schemas. We use
``engine.execution_options(schema_translate_map={"shared": None})`` so the ORM
generates schema-free DDL and DML. We also remove ``server_default`` entries that
reference Postgres functions (e.g. ``gen_random_uuid()``) before creating tables;
Python-level UUIDs are supplied in the ORM models via ``__init__`` overrides in
each base test.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import JSON, String, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import TypeDecorator

# Minimal env so shared.config does not raise (no real secrets needed in tests)
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost/")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")
os.environ.setdefault(
    "ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM="
)

# Import models so their metadata is populated before the engine fixture runs.
from shared.data_ingestion.models import IngestionRun, IngestionSchedule
from shared.db.base import Base


class _UUIDString(TypeDecorator):
    """SQLite-compatible UUID stored as VARCHAR(36).

    Prevents the PG_UUID BLOB→float bug under SQLite SAVEPOINT sessions
    (LESSON-007).
    """

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:
        if value is None:
            return None
        return uuid.UUID(str(value))


def _patch_tables_for_sqlite() -> None:
    """Patch ingestion ORM table columns for SQLite compatibility.

    Replaces PG_UUID with _UUIDString and JSONB with JSON, and removes
    server_default expressions that reference Postgres functions
    (``gen_random_uuid()``, ``now()`` is fine — SQLite has CURRENT_TIMESTAMP).

    Called once at module import time. Idempotent: repeated calls check
    ``_sqlite_patched`` flag on the table object.
    """
    for table in [IngestionRun.__table__, IngestionSchedule.__table__]:
        if getattr(table, "_sqlite_patched", False):
            continue
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
            elif isinstance(col.type, PG_UUID):
                col.type = _UUIDString()
            # Remove Postgres-specific server defaults; Python code provides IDs.
            if col.server_default is not None and "gen_random_uuid" in str(  # type: ignore[attr-defined]
                col.server_default  # type: ignore[attr-defined]
            ):
                col.server_default = None  # type: ignore[attr-defined]
        table._sqlite_patched = True  # type: ignore[attr-defined]


# Patch at import time so the engine fixture sees the corrected column types.
_patch_tables_for_sqlite()


@pytest.fixture(scope="session")
def _engine():
    """Session-scoped SQLite engine with schema_translate_map for the 'shared' schema.

    ``schema_translate_map={'shared': None}`` causes the ORM and DDL to emit
    schema-free table names, which SQLite understands (LESSON-007 / LESSON-001).
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

    # Use schema_translate_map so 'shared.table' → 'table' in all SQL
    engine = raw_engine.execution_options(schema_translate_map={"shared": None})

    Base.metadata.create_all(
        engine,
        tables=[IngestionRun.__table__, IngestionSchedule.__table__],
    )

    yield engine

    Base.metadata.drop_all(
        engine,
        tables=[IngestionRun.__table__, IngestionSchedule.__table__],
    )
    raw_engine.dispose()


@pytest.fixture
def db_session(_engine) -> Iterator[Session]:
    """SAVEPOINT-based isolated session per LESSON-001.

    Tests that call ``session.commit()`` inside service logic are fully
    isolated — each test sees a clean slate, with all changes rolled back
    via the outer ``connection.begin()`` teardown.
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
