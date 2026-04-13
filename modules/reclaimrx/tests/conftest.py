"""Shared test fixtures for reclaimrx module."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, event
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
