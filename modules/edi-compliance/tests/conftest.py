"""Test configuration and fixtures for edi-compliance module.

Uses SAVEPOINT-based isolation (LESSON-001) for any test that calls db.commit().
Uses _UUIDString TypeDecorator for SQLite SAVEPOINT UUID compatibility (LESSON-007).
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

# Add module root to sys.path so imports use `src.*`
_MODULE_ROOT = Path(__file__).resolve().parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

# Add project root so `shared.*` is importable
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

os.environ.setdefault("ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM=")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")

import pytest
from sqlalchemy import JSON, String, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session
from sqlalchemy.types import TypeDecorator

from shared.db.base import Base

# Import models to register on Base.metadata
import src.models.edi_models  # noqa: F401


class _UUIDString(TypeDecorator):
    """Store UUIDs as VARCHAR(36) in SQLite tests (LESSON-007)."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return uuid.UUID(value) if value is not None else None


@pytest.fixture(scope="session")
def engine():
    e = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, PG_UUID):
                col.type = _UUIDString()
            elif isinstance(col.type, JSONB):
                col.type = JSON()
        table.schema = None

    Base.metadata.create_all(e)
    yield e
    e.dispose()


@pytest.fixture()
def db(engine) -> Session:
    """SAVEPOINT-isolated synchronous session (LESSON-001)."""
    connection = engine.connect()
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
