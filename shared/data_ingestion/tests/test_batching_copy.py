"""Tests for the Wave 11.5 COPY-staging batching primitives.

Covers:

* ``_pg_copy_text_encode`` — correct escape of null / booleans / tab / newline
  / carriage-return / backslash.
* ``_encode_rows_as_copy_text`` — row/column projection with missing keys
  encoded as NULL.
* ``flush_upsert_batch_copy`` / ``flush_scoped_replace_batch_copy`` SQLite
  fallback — on a non-Postgres dialect the ``_copy`` variants must delegate
  to the existing VALUES-based primitive and produce an identical DB state.
* ``flush_upsert_batch_copy`` / ``flush_scoped_replace_batch_copy`` Postgres
  path — via a mocked DBAPI cursor we verify that the CREATE TEMP TABLE /
  COPY / INSERT SELECT / DELETE USING / TRUNCATE statements are emitted in
  the expected order and shape.

A real-Postgres integration test is intentionally out of scope here — the
mocked-cursor tests assert the SQL string shape, which is what breaks when
the COPY path regresses. A live-PG benchmark lives in Wave 11.5 commit 2.
"""

from __future__ import annotations

import io
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, Text
from sqlalchemy.orm import Session

from shared.data_ingestion.batching import (
    ErrorAggregator,
    _encode_rows_as_copy_text,
    _pg_copy_text_encode,
    _qualified_sql_name,
    _staging_table_name,
    flush_scoped_replace_batch_copy,
    flush_upsert_batch_copy,
)

# ---------------------------------------------------------------------------
# Text-format encoder unit tests
# ---------------------------------------------------------------------------


def test_pg_copy_text_encode_none_is_null_literal() -> None:
    assert _pg_copy_text_encode(None) == r"\N"


def test_pg_copy_text_encode_booleans() -> None:
    # Postgres text format for boolean: t / f.
    assert _pg_copy_text_encode(True) == "t"
    assert _pg_copy_text_encode(False) == "f"


def test_pg_copy_text_encode_integers_and_decimals() -> None:
    assert _pg_copy_text_encode(42) == "42"
    assert _pg_copy_text_encode(-7) == "-7"
    from decimal import Decimal
    assert _pg_copy_text_encode(Decimal("3.14")) == "3.14"


def test_pg_copy_text_encode_escapes_backslash() -> None:
    # Single backslash must become \\ so the reader doesn't treat it as
    # an escape sequence.
    assert _pg_copy_text_encode("a\\b") == "a\\\\b"


def test_pg_copy_text_encode_escapes_tab_newline_cr() -> None:
    # Each of the field/row separators has a standard 2-char escape.
    assert _pg_copy_text_encode("a\tb") == "a\\tb"
    assert _pg_copy_text_encode("a\nb") == "a\\nb"
    assert _pg_copy_text_encode("a\rb") == "a\\rb"


def test_pg_copy_text_encode_order_of_escapes_is_correct() -> None:
    # Backslash must be escaped BEFORE tab so a literal \t string
    # becomes \\t, not \\\t.
    assert _pg_copy_text_encode("\\t") == "\\\\t"


def test_pg_copy_text_encode_empty_string_stays_empty() -> None:
    # Empty string in COPY text format means zero-length field, distinct
    # from NULL (\N). We preserve that distinction.
    assert _pg_copy_text_encode("") == ""


def test_encode_rows_projects_onto_columns_in_order() -> None:
    rows = [
        {"a": 1, "b": "two"},
        {"b": "four", "a": 3},
    ]
    buf = _encode_rows_as_copy_text(rows, ["a", "b"])
    assert buf == "1\ttwo\n3\tfour\n"


def test_encode_rows_missing_key_becomes_null() -> None:
    rows = [{"a": 1}]  # "b" missing
    buf = _encode_rows_as_copy_text(rows, ["a", "b"])
    assert buf == "1\t\\N\n"


def test_encode_rows_empty_input_produces_empty_buffer() -> None:
    assert _encode_rows_as_copy_text([], ["a", "b"]) == ""


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def test_staging_table_name_strips_unsafe_chars_and_truncates() -> None:
    tbl = Table("prescribers", MetaData(), Column("id", Integer, primary_key=True))
    assert _staging_table_name(tbl) == "stg_prescribers"


def test_staging_table_name_under_63_chars() -> None:
    meta = MetaData()
    long = Table(
        "a" * 100, meta, Column("id", Integer, primary_key=True),
    )
    name = _staging_table_name(long)
    assert len(name) <= 63


def test_qualified_sql_name_with_schema() -> None:
    meta = MetaData()
    tbl = Table("t", meta, Column("id", Integer, primary_key=True), schema="s")
    assert _qualified_sql_name(tbl) == '"s"."t"'


def test_qualified_sql_name_without_schema() -> None:
    meta = MetaData()
    tbl = Table("t", meta, Column("id", Integer, primary_key=True))
    assert _qualified_sql_name(tbl) == '"t"'


# ---------------------------------------------------------------------------
# SQLite fallback — verify the _copy variants delegate to VALUES primitives
# ---------------------------------------------------------------------------


def _make_test_table(name: str, db_session: Session) -> Table:
    """Create a small 3-column test table on the active SQLite connection."""
    meta = MetaData()
    tbl = Table(
        name,
        meta,
        Column("id", Integer, primary_key=True),
        Column("key", String(20), unique=True, nullable=False),
        Column("value", Text, nullable=True),
    )
    tbl.create(bind=db_session.connection())
    return tbl


def _make_scoped_table(name: str, db_session: Session) -> Table:
    """Create a scope/seq/value test table."""
    meta = MetaData()
    tbl = Table(
        name,
        meta,
        Column("id", Integer, primary_key=True),
        Column("scope", String(20), nullable=False),
        Column("seq", Integer, nullable=False),
        Column("value", Text, nullable=True),
    )
    tbl.create(bind=db_session.connection())
    return tbl


def test_flush_upsert_copy_falls_back_on_sqlite(db_session: Session) -> None:
    """On SQLite the _copy variant must produce the same state as VALUES."""
    tbl = _make_test_table("batch_upsert_sqlite", db_session)
    errors = ErrorAggregator()

    inserted, deduped = flush_upsert_batch_copy(
        db_session,
        source_name="test",
        table=tbl,
        unique_key=["key"],
        rows=[
            {"key": "a", "value": "one"},
            {"key": "b", "value": "two"},
        ],
        errors=errors,
    )
    assert inserted == 2
    assert deduped == 0
    assert errors.total_errors == 0

    rows = list(db_session.execute(tbl.select()).mappings())
    assert {r["key"]: r["value"] for r in rows} == {"a": "one", "b": "two"}


def test_flush_upsert_copy_sqlite_on_conflict_updates(db_session: Session) -> None:
    """Second flush with same key updates the value (VALUES fallback path)."""
    tbl = _make_test_table("batch_upsert_sqlite_conflict", db_session)
    errors = ErrorAggregator()

    flush_upsert_batch_copy(
        db_session, source_name="t", table=tbl, unique_key=["key"],
        rows=[{"key": "k", "value": "v1"}], errors=errors,
    )
    flush_upsert_batch_copy(
        db_session, source_name="t", table=tbl, unique_key=["key"],
        rows=[{"key": "k", "value": "v2"}], errors=errors,
    )

    row = db_session.execute(tbl.select().where(tbl.c.key == "k")).mappings().one()
    assert row["value"] == "v2"


def test_flush_upsert_copy_sqlite_dedups_in_batch(db_session: Session) -> None:
    """Same-key rows in one batch collapse to last-seen (VALUES fallback path)."""
    tbl = _make_test_table("batch_upsert_sqlite_dedup", db_session)
    errors = ErrorAggregator()

    inserted, deduped = flush_upsert_batch_copy(
        db_session, source_name="t", table=tbl, unique_key=["key"],
        rows=[
            {"key": "x", "value": "first"},
            {"key": "x", "value": "second"},
            {"key": "y", "value": "only"},
        ],
        errors=errors,
    )
    assert inserted == 2
    assert deduped == 1

    rows = list(db_session.execute(tbl.select()).mappings())
    by_key = {r["key"]: r["value"] for r in rows}
    assert by_key == {"x": "second", "y": "only"}


def test_flush_upsert_copy_sqlite_empty_is_noop(db_session: Session) -> None:
    """Empty rows list returns (0, 0) and records no errors."""
    tbl = _make_test_table("batch_upsert_sqlite_empty", db_session)
    errors = ErrorAggregator()

    inserted, deduped = flush_upsert_batch_copy(
        db_session, source_name="t", table=tbl, unique_key=["key"],
        rows=[], errors=errors,
    )
    assert (inserted, deduped) == (0, 0)
    assert errors.total_errors == 0


def test_flush_scoped_replace_copy_falls_back_on_sqlite(db_session: Session) -> None:
    """On SQLite the scoped-replace _copy variant delegates and works."""
    tbl = _make_scoped_table("batch_scope_sqlite", db_session)
    errors = ErrorAggregator()

    # Seed scope=a
    flush_scoped_replace_batch_copy(
        db_session, source_name="t", table=tbl,
        scope_key=["scope"], unique_key=["scope", "seq"],
        rows=[
            {"scope": "a", "seq": 1, "value": "a1"},
            {"scope": "a", "seq": 2, "value": "a2"},
        ],
        errors=errors,
    )
    # Replace scope=a, add scope=b
    flush_scoped_replace_batch_copy(
        db_session, source_name="t", table=tbl,
        scope_key=["scope"], unique_key=["scope", "seq"],
        rows=[
            {"scope": "a", "seq": 1, "value": "a1_new"},
            {"scope": "b", "seq": 1, "value": "b1"},
        ],
        errors=errors,
    )

    rows = list(db_session.execute(tbl.select()).mappings())
    # scope=a should now have exactly 1 row (old seq=2 deleted)
    a_rows = [r for r in rows if r["scope"] == "a"]
    assert len(a_rows) == 1
    assert a_rows[0]["value"] == "a1_new"
    b_rows = [r for r in rows if r["scope"] == "b"]
    assert len(b_rows) == 1


def test_flush_scoped_replace_copy_sqlite_empty_is_noop(db_session: Session) -> None:
    tbl = _make_scoped_table("batch_scope_sqlite_empty", db_session)
    errors = ErrorAggregator()
    inserted, dd = flush_scoped_replace_batch_copy(
        db_session, source_name="t", table=tbl,
        scope_key=["scope"], unique_key=["scope", "seq"],
        rows=[], errors=errors,
    )
    assert (inserted, dd) == (0, 0)
    assert errors.total_errors == 0


# ---------------------------------------------------------------------------
# Postgres path — mocked cursor captures the SQL shape
# ---------------------------------------------------------------------------


class _FakePgSession:
    """Minimal duck-typed Session that reports dialect=postgresql and
    returns a MagicMock cursor so we can capture executed SQL."""

    def __init__(self) -> None:
        self.cursor_mock = MagicMock()
        self.cursor_mock.execute = MagicMock()
        self.cursor_mock.copy_expert = MagicMock()
        self.cursor_mock.close = MagicMock()

        # Connection → DBAPI conn → cursor chain
        self._dbapi_conn = MagicMock()
        self._dbapi_conn.cursor.return_value = self.cursor_mock
        self._conn = MagicMock()
        self._conn.connection = self._dbapi_conn

        # Bind → dialect.name = postgresql
        self._bind = MagicMock()
        self._bind.dialect.name = "postgresql"

        self.commit_count = 0
        self.rollback_count = 0

    def connection(self) -> Any:
        return self._conn

    def get_bind(self) -> Any:
        return self._bind

    # Fallback paths touch .bind (property on real Session); alias to get_bind.
    @property
    def bind(self) -> Any:
        return self._bind

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1


def _make_pg_session_and_table() -> tuple[_FakePgSession, Table]:
    sess = _FakePgSession()
    tbl = Table(
        "prescribers",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("npi", String(10), unique=True, nullable=False),
        Column("name", Text, nullable=True),
        schema="prescriber_dir",
    )
    return sess, tbl


def test_upsert_copy_postgres_emits_create_copy_insert_sequence() -> None:
    sess, tbl = _make_pg_session_and_table()
    errors = ErrorAggregator()

    inserted, deduped = flush_upsert_batch_copy(
        sess,  # type: ignore[arg-type]
        source_name="test",
        table=tbl,
        unique_key=["npi"],
        rows=[
            {"npi": "1000000001", "name": "Alpha"},
            {"npi": "1000000002", "name": "Beta"},
        ],
        errors=errors,
    )
    assert (inserted, deduped) == (2, 0)
    assert sess.commit_count == 1
    assert sess.rollback_count == 0

    # Capture the executed SQL in order.
    executed = [call.args[0] for call in sess.cursor_mock.execute.call_args_list]
    assert len(executed) == 3
    assert executed[0].startswith('CREATE TEMP TABLE IF NOT EXISTS "stg_prescribers"')
    assert 'LIKE "prescriber_dir"."prescribers"' in executed[0]
    assert "ON COMMIT DROP" in executed[0]
    assert executed[1] == 'TRUNCATE "stg_prescribers"'
    assert executed[2].startswith('INSERT INTO "prescriber_dir"."prescribers"')
    assert "ON CONFLICT" in executed[2]
    assert '"npi"' in executed[2]
    assert "EXCLUDED" in executed[2]

    # COPY call shape.
    assert sess.cursor_mock.copy_expert.call_count == 1
    copy_sql, buf = sess.cursor_mock.copy_expert.call_args.args
    assert copy_sql.startswith('COPY "stg_prescribers"')
    assert "FROM STDIN" in copy_sql
    # Buffer contents — one row per input NPI, tab-separated.
    body = buf.getvalue()
    assert "1000000001\tAlpha" in body
    assert "1000000002\tBeta" in body


def test_upsert_copy_postgres_nothing_to_update_uses_do_nothing() -> None:
    """When every non-unique column is immutable, use DO NOTHING not DO UPDATE."""
    sess = _FakePgSession()
    # A table whose only non-unique column is 'id' (immutable) and 'created_at' (immutable).
    from sqlalchemy import DateTime
    tbl = Table(
        "t",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("k", String(10), unique=True, nullable=False),
        Column("created_at", DateTime, nullable=True),
    )
    errors = ErrorAggregator()
    flush_upsert_batch_copy(
        sess,  # type: ignore[arg-type]
        source_name="t", table=tbl, unique_key=["k"],
        rows=[{"k": "a"}],
        errors=errors,
    )
    executed = [call.args[0] for call in sess.cursor_mock.execute.call_args_list]
    insert_sql = next(s for s in executed if s.startswith("INSERT"))
    assert "DO NOTHING" in insert_sql


def test_upsert_copy_postgres_rolls_back_on_cursor_exception() -> None:
    sess, tbl = _make_pg_session_and_table()
    sess.cursor_mock.execute.side_effect = RuntimeError("simulated DB fault")
    errors = ErrorAggregator()

    inserted, deduped = flush_upsert_batch_copy(
        sess,  # type: ignore[arg-type]
        source_name="t", table=tbl, unique_key=["npi"],
        rows=[{"npi": "1000000001", "name": "Alpha"}],
        errors=errors,
    )
    assert inserted == 0
    assert sess.rollback_count == 1
    assert sess.commit_count == 0
    assert errors.total_errors >= 1
    # Error kind should be bucketed by table name
    assert any("upsert_copy:prescribers" in k for k in errors.counts)


def test_upsert_copy_postgres_empty_rows_is_noop() -> None:
    sess, tbl = _make_pg_session_and_table()
    errors = ErrorAggregator()

    inserted, deduped = flush_upsert_batch_copy(
        sess,  # type: ignore[arg-type]
        source_name="t", table=tbl, unique_key=["npi"],
        rows=[], errors=errors,
    )
    assert (inserted, deduped) == (0, 0)
    assert sess.cursor_mock.execute.call_count == 0
    assert sess.commit_count == 0


def test_scoped_replace_copy_postgres_emits_delete_using_and_insert() -> None:
    sess = _FakePgSession()
    tbl = Table(
        "prescriber_taxonomies",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("npi", String(10), nullable=False),
        Column("seq", Integer, nullable=False),
        Column("code", String(20), nullable=True),
        schema="prescriber_dir",
    )
    errors = ErrorAggregator()

    inserted, dd = flush_scoped_replace_batch_copy(
        sess,  # type: ignore[arg-type]
        source_name="t",
        table=tbl,
        scope_key=["npi"],
        unique_key=["npi", "seq"],
        rows=[
            {"npi": "1000000001", "seq": 1, "code": "A"},
            {"npi": "1000000001", "seq": 2, "code": "B"},
            {"npi": "1000000002", "seq": 1, "code": "C"},
        ],
        errors=errors,
    )
    assert inserted == 3
    assert dd == 0
    assert sess.commit_count == 1

    executed = [call.args[0] for call in sess.cursor_mock.execute.call_args_list]
    assert any(s.startswith('CREATE TEMP TABLE') for s in executed)
    assert any(s.startswith('TRUNCATE') for s in executed)
    # DELETE USING (SELECT DISTINCT npi FROM stg) s WHERE target.npi = s.npi
    delete_sql = next((s for s in executed if s.startswith("DELETE FROM")), None)
    assert delete_sql is not None
    assert 'USING' in delete_sql
    assert 'SELECT DISTINCT "npi"' in delete_sql
    assert '"prescriber_dir"."prescriber_taxonomies"."npi" = s."npi"' in delete_sql
    # INSERT INTO target (...) SELECT (...) FROM stg
    insert_sql = next(s for s in executed if s.startswith("INSERT INTO"))
    assert 'FROM "stg_prescriber_taxonomies"' in insert_sql


def test_scoped_replace_copy_postgres_dedups_within_scope() -> None:
    sess = _FakePgSession()
    tbl = Table(
        "t",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("scope", String(10), nullable=False),
        Column("seq", Integer, nullable=False),
        Column("value", Text, nullable=True),
    )
    errors = ErrorAggregator()
    inserted, dd = flush_scoped_replace_batch_copy(
        sess,  # type: ignore[arg-type]
        source_name="t", table=tbl,
        scope_key=["scope"], unique_key=["scope", "seq"],
        rows=[
            {"scope": "a", "seq": 1, "value": "first"},
            {"scope": "a", "seq": 1, "value": "dup"},
            {"scope": "a", "seq": 2, "value": "ok"},
        ],
        errors=errors,
    )
    assert inserted == 2
    assert dd == 1


def test_scoped_replace_copy_postgres_missing_scope_col_records_error() -> None:
    sess = _FakePgSession()
    tbl = Table(
        "t",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("scope", String(10), nullable=False),
        Column("seq", Integer, nullable=False),
    )
    errors = ErrorAggregator()
    flush_scoped_replace_batch_copy(
        sess,  # type: ignore[arg-type]
        source_name="t", table=tbl,
        scope_key=["scope"], unique_key=["scope", "seq"],
        rows=[{"seq": 1}],  # missing 'scope'
        errors=errors,
    )
    assert errors.total_errors >= 1
    assert any("scoped_replace_copy" in k for k in errors.counts)


def test_scoped_replace_copy_postgres_rolls_back_on_exception() -> None:
    sess = _FakePgSession()
    tbl = Table(
        "t",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("scope", String(10), nullable=False),
        Column("seq", Integer, nullable=False),
    )
    sess.cursor_mock.execute.side_effect = RuntimeError("boom")
    errors = ErrorAggregator()
    inserted, _ = flush_scoped_replace_batch_copy(
        sess,  # type: ignore[arg-type]
        source_name="t", table=tbl,
        scope_key=["scope"], unique_key=["scope", "seq"],
        rows=[{"scope": "a", "seq": 1}], errors=errors,
    )
    assert inserted == 0
    assert sess.rollback_count == 1
    assert sess.commit_count == 0


def test_scoped_replace_copy_postgres_empty_rows_is_noop() -> None:
    sess = _FakePgSession()
    tbl = Table(
        "t",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("scope", String(10), nullable=False),
        Column("seq", Integer, nullable=False),
    )
    errors = ErrorAggregator()
    inserted, dd = flush_scoped_replace_batch_copy(
        sess,  # type: ignore[arg-type]
        source_name="t", table=tbl,
        scope_key=["scope"], unique_key=["scope", "seq"],
        rows=[], errors=errors,
    )
    assert (inserted, dd) == (0, 0)
    assert sess.cursor_mock.execute.call_count == 0
    assert sess.commit_count == 0


def test_upsert_copy_excludes_autoincrement_id_absent_from_rows() -> None:
    """Wave 12 bench-regression: ``id SERIAL`` must be left out of the
    COPY column list when no row supplies it, so the staging table's
    ``DEFAULT nextval(...)`` applies on INSERT. The earlier (buggy)
    version named ``id`` in the COPY list, sent ``\\N``, and hit
    ``NotNullViolation: null value in column "id"``."""
    sess = _FakePgSession()
    tbl = Table(
        "nppes_prescriber_details",
        MetaData(),
        Column("id", Integer, primary_key=True),  # simulates SERIAL
        Column("npi", String(10), unique=True, nullable=False),
        Column("last_name", Text, nullable=True),
        schema="prescriber_dir",
    )
    errors = ErrorAggregator()
    flush_upsert_batch_copy(
        sess,  # type: ignore[arg-type]
        source_name="nppes_satellite", table=tbl, unique_key=["npi"],
        rows=[
            {"npi": "1679576722", "last_name": "WIEBE"},
            {"npi": "1871596098", "last_name": "DIAZ-LACAYO"},
        ],
        errors=errors,
    )
    # COPY list must name only npi and last_name.
    copy_sql, buf = sess.cursor_mock.copy_expert.call_args.args
    assert '("npi", "last_name")' in copy_sql
    assert '"id"' not in copy_sql
    # Every INSERT...SELECT executed against staging must also omit id.
    inserts = [
        call.args[0]
        for call in sess.cursor_mock.execute.call_args_list
        if call.args and str(call.args[0]).startswith("INSERT INTO")
    ]
    assert inserts, "no INSERT fired"
    for sql in inserts:
        assert '"id"' not in sql, f"INSERT still names id column: {sql}"
    # Rows/sec counts — both rows upserted, zero errors.
    assert errors.total_errors == 0


def test_scoped_replace_copy_excludes_autoincrement_id_absent_from_rows() -> None:
    """Same bug, scoped-replace path."""
    sess = _FakePgSession()
    tbl = Table(
        "prescriber_addresses",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("npi", String(10), nullable=False),
        Column("address_type", String(10), nullable=False),
        Column("line_1", Text, nullable=True),
        schema="prescriber_dir",
    )
    errors = ErrorAggregator()
    flush_scoped_replace_batch_copy(
        sess,  # type: ignore[arg-type]
        source_name="nppes_satellite", table=tbl,
        scope_key=["npi"], unique_key=["npi", "address_type"],
        rows=[
            {"npi": "1679576722", "address_type": "mailing", "line_1": "PO BOX 2168"},
            {"npi": "1679576722", "address_type": "practice", "line_1": "123 MAIN ST"},
        ],
        errors=errors,
    )
    copy_sql, buf = sess.cursor_mock.copy_expert.call_args.args
    assert '"id"' not in copy_sql
    # Expected column list (table order, minus id):
    assert '("npi", "address_type", "line_1")' in copy_sql
    inserts = [
        call.args[0]
        for call in sess.cursor_mock.execute.call_args_list
        if call.args and str(call.args[0]).startswith("INSERT INTO")
    ]
    for sql in inserts:
        assert '"id"' not in sql
    assert errors.total_errors == 0


def test_upsert_copy_column_order_pinned_to_table_columns() -> None:
    """COPY column list must follow Table.columns order and must include
    only columns that at least one row actually supplies.

    Regression guard for two bugs at once:

    1. Column list must be derived from Table.columns (not dict iteration)
       so the COPY payload stays positionally aligned with the staging
       table.

    2. An autoincrement PK that rows don't supply (``id`` here) must NOT
       appear in the COPY list — Postgres COPY treats ``\\N`` as literal
       NULL and never substitutes a default for columns named in the
       column list. Wave 12 bench caught this on ``id SERIAL NOT NULL
       DEFAULT nextval(...)``: sending ``\\N`` violated the NOT NULL
       constraint, failing every batch.
    """
    sess, tbl = _make_pg_session_and_table()
    errors = ErrorAggregator()
    flush_upsert_batch_copy(
        sess,  # type: ignore[arg-type]
        source_name="t", table=tbl, unique_key=["npi"],
        # Keys in reverse dict order — encoder must still produce
        # table-column order (npi, name) on the wire.
        rows=[{"name": "Omega", "npi": "9999999999"}],
        errors=errors,
    )
    copy_sql, buf = sess.cursor_mock.copy_expert.call_args.args
    # id is missing from the row → excluded from the COPY list.
    assert '("npi", "name")' in copy_sql
    assert '"id"' not in copy_sql
    # Buffer contents preserve table.columns order, not dict order.
    assert buf.getvalue() == "9999999999\tOmega\n"
