"""B9.B C19 — Unit tests for the generic Tier-driven FDB loader.

Tests the `load_tier_group` dispatcher against an in-memory SQLite
engine. Real Postgres integration runs at B9.B mini-GATE-CLOSE
follow-on.

Specifically validates the codex B9.B GATE-CLOSE R1 HIGH 1 mitigation:
the generic loader dispatches on `delta_semantics` (UPSERT vs
APPEND_ONLY) and replays cleanly (0 net new rows on second run).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine, select
from sqlalchemy.orm import Session

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    FDBAdapter,
    FDBDrop,
    TableSpec,
    Tier,
)


# ---------------------------------------------------------------------------
# Fake adapter — returns canned rows per spec
# ---------------------------------------------------------------------------


class _FakeAdapter(FDBAdapter):
    """In-memory adapter; returns rows from a dict keyed by table_name."""

    def __init__(self, rows_by_table: dict[str, list[dict]]) -> None:
        self._rows = rows_by_table

    def discover_latest_drop(self) -> FDBDrop:
        return FDBDrop(
            drop_date=date(2026, 5, 6),
            license_code="TEL000000T",
            db_zip_path=Path("/dev/null"),
            ddl_zip_path=Path("/dev/null"),
            upd_zip_path=Path("/dev/null"),
            highlights_zip_path=Path("/dev/null"),
            record_counts_path=Path("/dev/null"),
        )

    def open_table(self, drop, table_name, *, source="DB"):  # pragma: no cover
        return iter([])

    def parse_table(self, drop, spec, *, source="DB"):
        for row in self._rows.get(spec.table_name, []):
            yield row


@pytest.fixture
def sqlite_engine():
    return create_engine("sqlite:///:memory:", future=True)


# ---------------------------------------------------------------------------
# Spec fixtures
# ---------------------------------------------------------------------------


_UPSERT_SPEC = TableSpec(
    table_name="RFOO_TEST",
    columns=("code", "desc_text"),
    coercers={"code": str, "desc_text": str},
    tier=Tier.A,
    loader_group="fdb_tier_a",
    record_counts_key="RFOO",
    delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    natural_key=("code",),
)

_APPEND_ONLY_SPEC = TableSpec(
    table_name="RBAR_HIST",
    columns=("repl_id", "prev_id"),
    coercers={"repl_id": int, "prev_id": int},
    tier=Tier.A,
    loader_group="fdb_tier_a",
    record_counts_key="RBAR",
    delta_semantics=DeltaSemantics.APPEND_ONLY,
)


def _setup_sqlite_tables(engine, specs: list[TableSpec], schema_name: str) -> None:
    """Create empty SQLite tables matching each spec (column names only)."""
    md = MetaData()
    for spec in specs:
        Table(
            spec.table_name.lower(),
            md,
            *(Column(c, String) for c in spec.columns),
            extend_existing=True,
        )
    md.create_all(engine)


# ---------------------------------------------------------------------------
# load_tier_group behaviors
# ---------------------------------------------------------------------------


def test_load_tier_group_filters_by_group(sqlite_engine) -> None:
    """Only specs whose loader_group matches `group` are loaded."""
    from drug_database.services.fdb_tier_loader import load_tier_group

    other_spec = TableSpec(
        table_name="RBAZ_OTHER",
        columns=("x",),
        coercers={"x": str},
        tier=Tier.A,
        loader_group="fdb_tier_b",  # not in fdb_tier_a
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=("x",),
    )
    adapter = _FakeAdapter({"RBAZ_OTHER": [{"x": "skipped"}]})
    drop = adapter.discover_latest_drop()
    with Session(sqlite_engine) as session:
        result = load_tier_group(
            session, adapter, drop,
            group="fdb_tier_a", specs=[other_spec], dry_run=True,
        )
    # No specs eligible → empty result.
    assert result.group == "fdb_tier_a"
    assert result.table_summaries == {}


def test_load_tier_group_dry_run_parses_but_does_not_write(sqlite_engine) -> None:
    """dry_run=True increments rows_parsed but inserted=0."""
    from drug_database.services.fdb_tier_loader import load_tier_group

    adapter = _FakeAdapter({
        "RFOO_TEST": [{"code": "a", "desc_text": "alpha"}],
    })
    drop = adapter.discover_latest_drop()
    with Session(sqlite_engine) as session:
        result = load_tier_group(
            session, adapter, drop,
            group="fdb_tier_a", specs=[_UPSERT_SPEC], dry_run=True,
        )
    summary = result.table_summaries["RFOO_TEST"]
    assert summary.rows_parsed == 1
    assert summary.inserted == 0


def test_load_tier_group_unsupported_semantics_skipped(sqlite_engine) -> None:
    """UNKNOWN / TRUNCATE_RELOAD specs are skipped with a warning."""
    from drug_database.services.fdb_tier_loader import load_tier_group

    unknown_spec = TableSpec(
        table_name="RBAZ_UNKNOWN",
        columns=("x",),
        coercers={"x": str},
        tier=Tier.A,
        loader_group="fdb_tier_a",
        delta_semantics=DeltaSemantics.UNKNOWN,
    )
    _setup_sqlite_tables(sqlite_engine, [unknown_spec], "drug_database")
    adapter = _FakeAdapter({"RBAZ_UNKNOWN": [{"x": "1"}]})
    drop = adapter.discover_latest_drop()
    with Session(sqlite_engine) as session:
        result = load_tier_group(
            session, adapter, drop,
            group="fdb_tier_a", specs=[unknown_spec], dry_run=False,
        )
    summary = result.table_summaries["RBAZ_UNKNOWN"]
    assert summary.rows_parsed == 1
    assert summary.skipped == 1


def test_load_tier_group_upsert_requires_natural_key() -> None:
    """UPSERT_BY_NATURAL_KEY spec without natural_key raises at runtime."""
    from drug_database.services.fdb_tier_loader import load_tier_group

    bad_spec = TableSpec(
        table_name="RBAD_TEST",
        columns=("x",),
        coercers={"x": str},
        tier=Tier.A,
        loader_group="fdb_tier_a",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        # natural_key=() — empty, the regression
    )
    adapter = _FakeAdapter({"RBAD_TEST": [{"x": "1"}]})
    drop = adapter.discover_latest_drop()
    engine = create_engine("sqlite:///:memory:", future=True)
    _setup_sqlite_tables(engine, [bad_spec], "drug_database")
    with Session(engine) as session:
        with pytest.raises(ValueError, match="natural_key"):
            load_tier_group(
                session, adapter, drop,
                group="fdb_tier_a", specs=[bad_spec], dry_run=False,
            )


def test_append_only_replay_with_natural_key_does_not_duplicate(sqlite_engine) -> None:
    """B9.B R2 HIGH: APPEND_ONLY with natural_key is replay-idempotent.

    Constructs a SQLite table with a UNIQUE index over the natural_key
    columns (mirroring what the migration emits for APPEND_ONLY specs).
    First load inserts the row; second load is `INSERT ... ON CONFLICT
    (natural_key) DO NOTHING` — row count must stay the same.
    """
    from sqlalchemy import Index
    from drug_database.services.fdb_tier_loader import load_tier_group

    hist_spec = TableSpec(
        table_name="RFOO_HIST",
        columns=("repl_id", "prev_id", "eff_dt"),
        coercers={"repl_id": int, "prev_id": int, "eff_dt": str},
        tier=Tier.A,
        loader_group="fdb_tier_a",
        delta_semantics=DeltaSemantics.APPEND_ONLY,
        natural_key=("repl_id", "prev_id", "eff_dt"),
    )
    # Create the table WITH a UNIQUE index over natural_key (mirrors
    # the UniqueConstraint the migration emits).
    md = MetaData()
    table = Table(
        "rfoo_hist", md,
        *(Column(c, String) for c in hist_spec.columns),
    )
    Index("uq_rfoo_hist", *(table.c[c] for c in hist_spec.natural_key), unique=True)
    md.create_all(sqlite_engine)

    adapter = _FakeAdapter({"RFOO_HIST": [{"repl_id": "42", "prev_id": "41", "eff_dt": "20260101"}]})
    drop = adapter.discover_latest_drop()

    # Run 1 — inserts the row.  schema="" matches the schemaless SQLite test table.
    with Session(sqlite_engine) as session:
        load_tier_group(session, adapter, drop, group="fdb_tier_a", specs=[hist_spec], schema="")
        n1 = session.execute(select(table)).all()
        assert len(n1) == 1

    # Run 2 (same drop, same data) — must NOT add a duplicate.
    with Session(sqlite_engine) as session:
        load_tier_group(session, adapter, drop, group="fdb_tier_a", specs=[hist_spec], schema="")
        n2 = session.execute(select(table)).all()
        assert len(n2) == 1, (
            f"APPEND_ONLY replay duplicated: row count went from {len(n1)} "
            f"to {len(n2)} after second load. The ON CONFLICT DO NOTHING "
            f"path is regressed."
        )


def test_load_tier_group_summary_aggregates_per_table(sqlite_engine) -> None:
    """TierLoadResult sums inserted/skipped across multiple specs."""
    from drug_database.services.fdb_tier_loader import load_tier_group

    spec_b = TableSpec(
        table_name="RFOO2_TEST",
        columns=("code", "desc_text"),
        coercers={"code": str, "desc_text": str},
        tier=Tier.A,
        loader_group="fdb_tier_a",
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        natural_key=("code",),
    )
    adapter = _FakeAdapter({
        "RFOO_TEST": [{"code": "a", "desc_text": "alpha"}],
        "RFOO2_TEST": [{"code": "b", "desc_text": "beta"}, {"code": "c", "desc_text": "gamma"}],
    })
    drop = adapter.discover_latest_drop()
    with Session(sqlite_engine) as session:
        result = load_tier_group(
            session, adapter, drop,
            group="fdb_tier_a", specs=[_UPSERT_SPEC, spec_b], dry_run=True,
        )
    assert len(result.table_summaries) == 2
    assert result.table_summaries["RFOO_TEST"].rows_parsed == 1
    assert result.table_summaries["RFOO2_TEST"].rows_parsed == 2
