"""Shared pytest fixtures for audit + notification tests.

Uses sync SQLAlchemy against an in-memory SQLite database via the
existing ``src._shim.db`` Base. Tables from the audit and notification
stand-in models are auto-created once per test session; each test gets a
clean transaction so rows don't leak between tests.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

# Make `src` importable as a top-level package for the tests
ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from src._shim import db as _shim_db  # noqa: E402
from src._shim.db import Base  # noqa: E402


def _configure_shared_sqlite() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _shim_db._engine = engine
    _shim_db._SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def get_engine():
    return _shim_db.get_engine()


def get_sessionmaker():
    return _shim_db.get_sessionmaker()
from src.audit import models as _audit_models  # noqa: F401,E402 -- register tables
from src.notifications import models as _notif_models  # noqa: F401,E402 -- register tables


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    _configure_shared_sqlite()
    Base.metadata.create_all(get_engine())
    yield
    Base.metadata.drop_all(get_engine())


@pytest.fixture
def db_session():
    SessionLocal = get_sessionmaker()
    session = SessionLocal()
    try:
        yield session
        session.rollback()
    finally:
        # Wipe rows so tests are isolated even though we share one DB
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()


@pytest.fixture
def tenant_id() -> uuid.UUID:
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def other_tenant_id() -> uuid.UUID:
    return uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def other_user_id() -> uuid.UUID:
    return uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
