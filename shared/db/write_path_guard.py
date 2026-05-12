"""B9.A C9 — Write-path guard for FDB reference data loaders.

Charter (and `waves/B9/write_path_enforcement.md`) require: every B9
FDB loader writes to `infinityrx_reference` and ONLY to
`infinityrx_reference`. Phase 09 tolerated the legacy fallback chain
`DATABASE_URL_SYNC_REFERENCE → DATABASE_URL_SYNC → DATABASE_URL`; B9
removes the fallback and adds a SQL-level assertion that fires
before any INSERT/COPY/CREATE TABLE.

Why both an env-var rule AND a SQL assertion:

  * Env-var only:  Operator runs `switch_env.sh dev` (sets
    `DATABASE_URL_SYNC` to the dev DB) and the legacy loader silently
    writes Tier A FDB tables into `infinityrx_dev`. They show up in
    the application schema instead of the FDW-fronted reference DB.
    The mistake is invisible until weekly delta produces duplicates.
  * SQL assertion only: Belt without suspenders. The env-var rule
    catches the typo BEFORE the engine even connects.

Public surface:

    resolve_reference_db_url() -> str
        Reads DATABASE_URL_SYNC_REFERENCE strictly; no fallback.
        Raises RuntimeError with a fix-it hint if unset.

    assert_reference_db_write_path(connection_or_session, *,
                                   expected='infinityrx_reference',
                                   resolver=None) -> None
        Runs `SELECT current_database()` and asserts the result
        equals `expected`. Mismatch → RuntimeError.

The `resolver` parameter is a test seam — pass a callable returning
the DB name to bypass the real SQL roundtrip in unit tests.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any


REFERENCE_DB_ENV_VAR = "DATABASE_URL_SYNC_REFERENCE"
REFERENCE_DB_EXPECTED_NAME = "infinityrx_reference"


def resolve_reference_db_url() -> str:
    """Return the reference-DB sync URL — strict, no fallback.

    Phase 09 allowed `DATABASE_URL_SYNC_REFERENCE → DATABASE_URL_SYNC
    → DATABASE_URL`. B9 removes the fallback to eliminate the silent-
    wrong-DB class of bugs. Operators must explicitly set the env var
    before running an FDB loader.

    Raises:
        RuntimeError: if the env var is unset or empty. Message
        includes the fix-it path so the operator does not have to dig.
    """
    url = os.environ.get(REFERENCE_DB_ENV_VAR, "").strip()
    if not url:
        raise RuntimeError(
            f"{REFERENCE_DB_ENV_VAR} is required for B9 FDB loaders. "
            f"Fix: `source infrastructure/scripts/switch_env.sh dev` "
            f"(or mock/prod) exports it to the reference DB URL. "
            f"Phase 09's URL fallback chain "
            f"(DATABASE_URL_SYNC → DATABASE_URL) is REMOVED in B9 to "
            f"prevent writing FDB tables to the operational DB."
        )
    # async driver doesn't work for sync engine — same coercion the
    # legacy loader does, kept consistent with scripts/load_fdb.py.
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _default_db_resolver(connection: Any) -> str:
    """Postgres path: SELECT current_database()."""
    from sqlalchemy import text
    return str(connection.execute(text("SELECT current_database()")).scalar())


def assert_reference_db_write_path(
    connection: Any,
    *,
    expected: str = REFERENCE_DB_EXPECTED_NAME,
    resolver: Callable[[Any], str] | None = None,
) -> None:
    """Assert the open connection points at the reference database.

    Args:
        connection: SQLAlchemy Connection or Session (anything with
            `.execute(text(...))`).
        expected: database name the loader requires. Defaults to
            ``infinityrx_reference``.
        resolver: test seam — callable taking the connection and
            returning the current DB name. Default uses
            `SELECT current_database()`.

    Raises:
        RuntimeError: if actual != expected. Message names both so
            the operator immediately sees what they were pointed at.
    """
    actual = (resolver or _default_db_resolver)(connection)
    if actual != expected:
        raise RuntimeError(
            f"Reference-DB write-path guard FAILED: connection is bound "
            f"to database {actual!r}, expected {expected!r}. B9 FDB "
            f"loaders only write to the reference DB. Re-run "
            f"`switch_env.sh` so DATABASE_URL_SYNC_REFERENCE points at "
            f"{expected!r} and try again."
        )


__all__ = [
    "REFERENCE_DB_ENV_VAR",
    "REFERENCE_DB_EXPECTED_NAME",
    "assert_reference_db_write_path",
    "resolve_reference_db_url",
]
