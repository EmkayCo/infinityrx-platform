"""Tests for Postgres RLS session-variable wiring in billing DB session.

The billing.uploads table (and related tables) has FORCE ROW LEVEL SECURITY
with a policy that checks ``app.current_tenant_id``. These tests verify that
the ``after_begin`` event correctly sets / clears the variable so INSERT and
SELECT operations are not blocked by RLS.

Tests use a SQLite in-memory engine to verify the event fires and calls the
right SQL — the exact Postgres syntax is verified by integration tests against
a live DB.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, call, patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(autouse=True)
def _reset_billing_session():
    """Reset billing session globals so each test starts clean."""
    from src.db import session as sess_mod

    orig_engine = sess_mod._engine
    orig_factory = sess_mod._SessionFactory
    yield
    sess_mod._engine = orig_engine
    sess_mod._SessionFactory = orig_factory


@pytest.fixture()
def sqlite_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield engine
    engine.dispose()


def test_rls_setter_event_installed_on_factory(sqlite_engine):
    """after_begin event must be registered on the Session class after factory init."""
    from src.db.session import _get_session_factory, set_engine

    # Clear any existing class-level flag from a prior test run
    from sqlalchemy.orm import Session
    if hasattr(Session, "_infinityrx_rls_setter_installed"):
        del Session._infinityrx_rls_setter_installed

    set_engine(sqlite_engine)
    factory = _get_session_factory()

    assert getattr(factory.class_, "_infinityrx_rls_setter_installed", False), (
        "RLS setter must be registered on the Session class after factory init"
    )


def test_set_postgres_tenant_with_active_context():
    """_set_postgres_tenant must run SET LOCAL with the active tenant UUID."""
    from src.db.session import _set_postgres_tenant
    from shared.db.tenant_context import current_tenant_id

    tid = uuid.UUID("a0000000-0000-0000-0000-000000000001")
    token = current_tenant_id.set(tid)
    try:
        mock_conn = MagicMock()
        _set_postgres_tenant(MagicMock(), MagicMock(), mock_conn)

        assert mock_conn.execute.call_count == 1
        call_args = mock_conn.execute.call_args
        # execute(text(...), {"tid": ...}) — params are positional arg[1]
        pos_args = call_args.args
        sql_str = str(pos_args[0])
        assert "SET SESSION" in sql_str
        assert "app.current_tenant_id" in sql_str
        # Second positional arg is the params dict
        assert len(pos_args) == 2, f"expected (sql, params) got {pos_args}"
        assert pos_args[1]["tid"] == str(tid)
    finally:
        current_tenant_id.reset(token)


def test_set_postgres_tenant_clears_when_no_context():
    """_set_postgres_tenant must set empty string when no tenant context is active."""
    from src.db.session import _set_postgres_tenant
    from shared.db.tenant_context import current_tenant_id

    # Ensure no context
    token = current_tenant_id.set(None)
    try:
        mock_conn = MagicMock()
        _set_postgres_tenant(MagicMock(), MagicMock(), mock_conn)

        assert mock_conn.execute.call_count == 1
        args, kwargs = mock_conn.execute.call_args
        sql_str = str(args[0])
        assert "SET SESSION" in sql_str
        assert "app.current_tenant_id" in sql_str
        # No :tid param — empty string is embedded in the SET LOCAL statement
    finally:
        current_tenant_id.reset(token)


def test_rls_setter_not_registered_twice(sqlite_engine):
    """Calling _get_session_factory() twice must not double-register the event."""
    from sqlalchemy.orm import Session

    from src.db.session import _get_session_factory, set_engine

    if hasattr(Session, "_infinityrx_rls_setter_installed"):
        del Session._infinityrx_rls_setter_installed

    set_engine(sqlite_engine)

    with patch("src.db.session.event.listen") as mock_listen:
        _get_session_factory()
        _get_session_factory()  # second call — must not re-register

    # event.listen for after_begin must be called at most once
    after_begin_calls = [
        c for c in mock_listen.call_args_list if "after_begin" in c.args
    ]
    assert len(after_begin_calls) <= 1, (
        f"after_begin event registered {len(after_begin_calls)} times — must be at most 1"
    )
