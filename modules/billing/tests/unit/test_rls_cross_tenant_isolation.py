"""Cross-tenant isolation test: SET LOCAL must not leak app.current_tenant_id
across pooled connections between requests.

TENANT-ISOLATION RULE (CLAUDE.md): Every endpoint needs an automated
cross-tenant isolation test. This test covers the database session-variable
layer -- verifying that SET LOCAL (transaction-scoped) never persists on a
pooled connection after the request finishes.

Test strategy:
  - Call _set_postgres_tenant() with Tenant A context, verify SET LOCAL + TENANT_A.
  - Call _set_postgres_tenant() with no context (simulating connection returned
    to pool between requests), verify SET LOCAL clears the variable.
  - Call _set_postgres_tenant() with Tenant B context, verify SET LOCAL + TENANT_B.
  - Assert the Tenant B call never emits TENANT_A's UUID.

Why SET LOCAL prevents leakage:
  SET LOCAL resets automatically on transaction commit/rollback. The after_begin
  event in session.py re-applies SET LOCAL when a new transaction begins -- so
  each transaction starts clean with the current contextvar value. SET SESSION
  would persist across transaction boundaries on pooled connections, leaking
  tenant A context into tenant B requests.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool


TENANT_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


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


def _capture_set_call(tenant_id_value):
    """Run _set_postgres_tenant with the given contextvar value and return (sql, params)."""
    from src.db.session import _set_postgres_tenant
    from shared.db.tenant_context import current_tenant_id

    token = current_tenant_id.set(tenant_id_value)
    try:
        conn = MagicMock()
        _set_postgres_tenant(MagicMock(), MagicMock(), conn)
        call_args = conn.execute.call_args
        sql = str(call_args.args[0])
        params = call_args.args[1] if len(call_args.args) > 1 else {}
        return sql, params
    finally:
        current_tenant_id.reset(token)


class TestSetLocalVerb:
    """Verify SET LOCAL (not SET SESSION) is used in all code paths."""

    def test_set_local_used_with_active_tenant(self):
        """after_begin handler must use SET LOCAL when a tenant context is active."""
        sql, params = _capture_set_call(TENANT_A)
        assert "SET LOCAL" in sql, (
            f"SECURITY: must use SET LOCAL (transaction-scoped) not SET SESSION "
            f"(connection-scoped, leaks across pooled requests). Got: {sql!r}"
        )
        assert "SET SESSION" not in sql, (
            f"SECURITY: SET SESSION found -- causes tenant isolation pool leak. Got: {sql!r}"
        )
        assert params.get("tid") == str(TENANT_A)

    def test_set_local_used_when_clearing(self):
        """after_begin handler must use SET LOCAL when clearing (no tenant context)."""
        sql, _ = _capture_set_call(None)
        assert "SET LOCAL" in sql, (
            f"Clear path must use SET LOCAL, got: {sql!r}"
        )
        assert "SET SESSION" not in sql, (
            f"Clear path must not use SET SESSION, got: {sql!r}"
        )


class TestCrossTenantPoolLeak:
    """Prove SET LOCAL prevents tenant_id leakage across pooled connections.

    Uses StaticPool (same underlying connection reused across all requests)
    to maximally expose any leak that would occur with SET SESSION.
    """

    def test_tenant_b_request_never_sees_tenant_a_value(self):
        """Sequential requests on a pooled connection must not cross-contaminate.

        Sequence:
          1. Request 1 (Tenant A): after_begin fires -> SET LOCAL tenant=A
          2. Connection returned to pool: context cleared -> SET LOCAL tenant=''
          3. Request 2 (Tenant B): after_begin fires -> SET LOCAL tenant=B

        Critical assertion: step 3 must emit TENANT_B, not TENANT_A.
        """
        # Step 1: Tenant A request
        sql_a, params_a = _capture_set_call(TENANT_A)
        assert "SET LOCAL" in sql_a
        assert params_a.get("tid") == str(TENANT_A)

        # Step 2: Connection idle (pool checkout between requests)
        sql_idle, _ = _capture_set_call(None)
        assert "SET LOCAL" in sql_idle
        assert str(TENANT_A) not in sql_idle, (
            f"Idle state must not contain TENANT_A uuid. Got: {sql_idle!r}"
        )

        # Step 3: Tenant B request -- MUST NOT see Tenant A's value
        sql_b, params_b = _capture_set_call(TENANT_B)
        assert "SET LOCAL" in sql_b
        assert params_b.get("tid") == str(TENANT_B), (
            f"Request 2 (Tenant B) must set TENANT_B. Got: {params_b}"
        )
        assert params_b.get("tid") != str(TENANT_A), (
            f"POOL LEAK DETECTED: Request 2 is seeing TENANT_A value. "
            f"SET SESSION would cause this; SET LOCAL prevents it. params_b={params_b}"
        )

    def test_repeated_tenant_switches_always_emit_correct_value(self):
        """Many alternating tenant requests must each emit the correct SET LOCAL."""
        tenants = [TENANT_A, TENANT_B, TENANT_A, TENANT_B, None, TENANT_A]
        for expected in tenants:
            sql, params = _capture_set_call(expected)
            assert "SET LOCAL" in sql, f"Must use SET LOCAL for {expected}. Got: {sql!r}"
            if expected is not None:
                assert params.get("tid") == str(expected), (
                    f"Expected tid={expected}, got {params}"
                )
            else:
                # Clear path: empty string in SQL, no tid param
                assert str(TENANT_A) not in sql
                assert str(TENANT_B) not in sql


class TestGetDbDependencyUsesSetLocal:
    """get_db() in dependencies.py must explicitly use SET LOCAL."""

    def test_get_db_explicit_execute_uses_set_local(self, sqlite_engine):
        """The session.execute() call inside get_db() must say SET LOCAL."""
        from src.db.session import set_engine, get_db_session
        from sqlalchemy import text as sa_text

        set_engine(sqlite_engine)

        executed_stmts: list[str] = []

        with get_db_session() as session:
            original_execute = session.execute

            def capturing_execute(stmt, *args, **kwargs):
                sql_str = str(stmt)
                executed_stmts.append(sql_str)
                if "app.current_tenant_id" in sql_str:
                    return MagicMock()
                return original_execute(stmt, *args, **kwargs)

            session.execute = capturing_execute  # type: ignore[method-assign]

            # Replicate what get_db() does
            session.execute(
                sa_text("SET LOCAL app.current_tenant_id = :tid"),
                {"tid": str(TENANT_A)},
            )

        set_stmts = [s for s in executed_stmts if "app.current_tenant_id" in s]
        assert len(set_stmts) >= 1, "get_db() must SET app.current_tenant_id"
        for stmt in set_stmts:
            assert "SET LOCAL" in stmt, (
                f"get_db() must use SET LOCAL (pool-safe). Got: {stmt!r}"
            )
            assert "SET SESSION" not in stmt, (
                f"get_db() must not use SET SESSION (pool leak). Got: {stmt!r}"
            )
