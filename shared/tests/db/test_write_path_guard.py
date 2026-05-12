"""B9.A C9 — Tests for the reference-DB write-path guard.

The guard is the load-bearing assertion that prevents a B9 FDB loader
from writing reference tables into an operational DB (the silent-
wrong-DB class of bugs).
"""
from __future__ import annotations

import pytest

from shared.db.write_path_guard import (
    REFERENCE_DB_ENV_VAR,
    REFERENCE_DB_EXPECTED_NAME,
    assert_reference_db_write_path,
    resolve_reference_db_url,
)


# ---------------------------------------------------------------------------
# resolve_reference_db_url — strict, no fallback
# ---------------------------------------------------------------------------


def test_resolve_returns_url_when_env_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        REFERENCE_DB_ENV_VAR,
        "postgresql://ifx_dev_app@localhost:5432/infinityrx_reference",
    )
    url = resolve_reference_db_url()
    assert url == "postgresql://ifx_dev_app@localhost:5432/infinityrx_reference"


def test_resolve_coerces_async_driver_to_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """async driver URL → sync driver (loaders use a sync engine)."""
    monkeypatch.setenv(
        REFERENCE_DB_ENV_VAR,
        "postgresql+asyncpg://ifx_dev_app@localhost:5432/infinityrx_reference",
    )
    url = resolve_reference_db_url()
    assert url.startswith("postgresql://")
    assert "asyncpg" not in url


def test_resolve_raises_with_fix_hint_when_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unset env var → RuntimeError naming the env var + switch_env.sh."""
    monkeypatch.delenv(REFERENCE_DB_ENV_VAR, raising=False)
    with pytest.raises(RuntimeError) as exc_info:
        resolve_reference_db_url()
    msg = str(exc_info.value)
    assert REFERENCE_DB_ENV_VAR in msg
    assert "switch_env.sh" in msg
    assert "FDB loaders" in msg


def test_resolve_raises_when_env_empty_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty string is treated as unset — explicit; not falsy-accidentally."""
    monkeypatch.setenv(REFERENCE_DB_ENV_VAR, "")
    with pytest.raises(RuntimeError, match=REFERENCE_DB_ENV_VAR):
        resolve_reference_db_url()


def test_resolve_raises_when_env_whitespace_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(REFERENCE_DB_ENV_VAR, "   ")
    with pytest.raises(RuntimeError, match=REFERENCE_DB_ENV_VAR):
        resolve_reference_db_url()


def test_resolve_no_fallback_when_only_legacy_vars_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 09's fallback chain is REMOVED. DATABASE_URL alone is not enough."""
    monkeypatch.delenv(REFERENCE_DB_ENV_VAR, raising=False)
    monkeypatch.setenv("DATABASE_URL_SYNC", "postgresql://x@y/operational")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x@y/operational")
    with pytest.raises(RuntimeError, match=REFERENCE_DB_ENV_VAR):
        resolve_reference_db_url()


# ---------------------------------------------------------------------------
# assert_reference_db_write_path — SQL assertion seam
# ---------------------------------------------------------------------------


class _FakeConnection:
    """Test seam — captures the SQL string for assertion."""

    def __init__(self, db_name: str) -> None:
        self._db_name = db_name
        self.executed: list[str] = []

    def execute(self, stmt):  # pragma: no cover - exercised via resolver=
        self.executed.append(str(stmt))
        return _FakeResult(self._db_name)


class _FakeResult:
    def __init__(self, value: str) -> None:
        self._value = value

    def scalar(self) -> str:
        return self._value


def test_assert_passes_when_current_database_matches() -> None:
    conn = _FakeConnection("infinityrx_reference")
    # Inject the resolver so we don't actually hit Postgres.
    assert_reference_db_write_path(
        conn, resolver=lambda c: "infinityrx_reference"
    )


def test_assert_raises_when_pointed_at_operational_db() -> None:
    conn = _FakeConnection("infinityrx_dev")
    with pytest.raises(RuntimeError) as exc_info:
        assert_reference_db_write_path(
            conn, resolver=lambda c: "infinityrx_dev"
        )
    msg = str(exc_info.value)
    # Both names must appear in the message — operator needs to see
    # WHAT they were pointed at AND what they should have been.
    assert "'infinityrx_dev'" in msg
    assert "'infinityrx_reference'" in msg
    assert "switch_env.sh" in msg


def test_assert_uses_default_expected_when_not_overridden() -> None:
    """Default expected = REFERENCE_DB_EXPECTED_NAME ('infinityrx_reference')."""
    conn = _FakeConnection("infinityrx_reference")
    assert REFERENCE_DB_EXPECTED_NAME == "infinityrx_reference"
    assert_reference_db_write_path(
        conn, resolver=lambda c: REFERENCE_DB_EXPECTED_NAME
    )


def test_assert_honors_custom_expected_value() -> None:
    """Future mock/prod DBs may use a different reference name."""
    conn = _FakeConnection("ifx_ref_alt")
    assert_reference_db_write_path(
        conn,
        expected="ifx_ref_alt",
        resolver=lambda c: "ifx_ref_alt",
    )


def test_default_resolver_runs_select_current_database() -> None:
    """The default resolver issues `SELECT current_database()`.

    Captured via a Connection stub that records the SQL it sees. This
    lets us assert on the actual SQL without spinning up Postgres.
    """
    class _RecordingConn:
        def __init__(self) -> None:
            self.last_sql: str | None = None

        def execute(self, stmt):
            self.last_sql = str(stmt)
            return _FakeResult("infinityrx_reference")

    conn = _RecordingConn()
    # Default resolver (no override) → SQL is issued.
    assert_reference_db_write_path(conn)
    assert conn.last_sql is not None
    assert "current_database" in conn.last_sql.lower()
