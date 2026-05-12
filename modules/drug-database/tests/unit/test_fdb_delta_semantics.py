"""B9.A C8 — Tests for the SQLite-backed DELTA_SEMANTICS simulator.

Combines C3's abstract A/C/D/re-A driver with C8's concrete SQLite
INSERT/UPSERT/DELETE simulator. These tests prove the SAME contract
the per-tier integration tests will rely on:

  * UPSERT_BY_NATURAL_KEY with `DO UPDATE`     → PASS
  * UPSERT_BY_NATURAL_KEY with `DO NOTHING`    → FAIL loudly (A4)
  * APPEND_ONLY history table                  → PASS (row count grows)
  * UPSERT_WITH_EFFECTIVE_DATE                 → PASS
  * UNKNOWN / TRUNCATE_RELOAD                  → skipped per template
"""
from __future__ import annotations

import pytest
from sqlalchemy import Engine, create_engine

from drug_database.services.fdb_adapter import (
    DeltaSemantics,
    TableSpec,
    Tier,
)
# See test_fdb_contract.py — same `tests` package-name collision fix.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _fdb_contract import assert_delta_semantics_acd_cycle  # noqa: E402
from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402


@pytest.fixture
def sqlite_engine() -> Engine:
    """Fresh in-memory SQLite per test — no cross-test bleed."""
    engine = create_engine("sqlite:///:memory:", future=True)
    return engine


# ---------------------------------------------------------------------------
# UPSERT_BY_NATURAL_KEY — correct INSERT...ON CONFLICT DO UPDATE
# ---------------------------------------------------------------------------


def test_upsert_by_natural_key_passes_with_real_sqlite_upsert(
    sqlite_engine: Engine,
) -> None:
    spec = TableSpec(
        table_name="upsert_ok",
        columns=("id", "name"),
        coercers={"id": int, "name": str},
        tier=Tier.A,
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    )
    sim, teardown = make_sqlite_simulator(
        sqlite_engine,
        table_name="upsert_ok",
        natural_key_columns=("id",),
        all_columns=("id", "name"),
        conflict_action="upsert",
    )
    try:
        assert_delta_semantics_acd_cycle(
            spec,
            natural_key={"id": 1},
            initial_row={"name": "alpha"},
            changed_values={"name": "BETA"},
            simulator=sim,
        )
    finally:
        teardown()


def test_upsert_by_natural_key_FAILS_with_on_conflict_do_nothing(
    sqlite_engine: Engine,
) -> None:
    """A4 regression detector: ON CONFLICT DO NOTHING silently drops C.

    This is the WHOLE POINT of the C3+C8 contract. The test asserts
    that wiring a TableSpec marked UPSERT_BY_NATURAL_KEY through a
    DO NOTHING implementation fails the contract — proving the
    contract catches the bug it was designed to catch.
    """
    spec = TableSpec(
        table_name="upsert_broken",
        columns=("id", "name"),
        coercers={"id": int, "name": str},
        tier=Tier.A,
        delta_semantics=DeltaSemantics.UPSERT_BY_NATURAL_KEY,
    )
    sim, teardown = make_sqlite_simulator(
        sqlite_engine,
        table_name="upsert_broken",
        natural_key_columns=("id",),
        all_columns=("id", "name"),
        conflict_action="nothing",  # ← the regression
    )
    try:
        with pytest.raises(AssertionError, match="did not propagate changed_values"):
            assert_delta_semantics_acd_cycle(
                spec,
                natural_key={"id": 1},
                initial_row={"name": "alpha"},
                changed_values={"name": "BETA"},
                simulator=sim,
            )
    finally:
        teardown()


# ---------------------------------------------------------------------------
# APPEND_ONLY — every operation appends a row (no conflict resolution)
# ---------------------------------------------------------------------------


def test_append_only_passes_when_every_tx_grows_history(
    sqlite_engine: Engine,
) -> None:
    spec = TableSpec(
        table_name="history_table",
        columns=("entity_id", "value"),
        coercers={"entity_id": int, "value": str},
        tier=Tier.A,
        delta_semantics=DeltaSemantics.APPEND_ONLY,
    )
    sim, teardown = make_sqlite_simulator(
        sqlite_engine,
        table_name="history_table",
        natural_key_columns=("entity_id",),
        all_columns=("entity_id", "value"),
        append_only=True,
    )
    try:
        assert_delta_semantics_acd_cycle(
            spec,
            natural_key={"entity_id": 99},
            initial_row={"value": "v1"},
            changed_values={"value": "v2"},
            simulator=sim,
        )
    finally:
        teardown()


# ---------------------------------------------------------------------------
# UPSERT_WITH_EFFECTIVE_DATE — 2+ rows after C (closed-then-new)
# ---------------------------------------------------------------------------


def test_upsert_with_effective_date_passes_when_c_opens_new_row(
    sqlite_engine: Engine,
) -> None:
    spec = TableSpec(
        table_name="eff_dated",
        columns=("id", "value", "eff_date"),
        coercers={"id": int, "value": str, "eff_date": str},
        tier=Tier.A,
        delta_semantics=DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE,
    )
    # Effective-dated tables use (id, eff_date) as the conflict target
    # — two rows with the same `id` but different `eff_date` coexist.
    sim, teardown = make_sqlite_simulator(
        sqlite_engine,
        table_name="eff_dated",
        natural_key_columns=("id", "eff_date"),
        all_columns=("id", "value", "eff_date"),
        conflict_action="upsert",
    )
    try:
        assert_delta_semantics_acd_cycle(
            spec,
            natural_key={"id": 1, "eff_date": "20260101"},  # bound to step A's row
            initial_row={"value": "old"},
            # C carries a NEW eff_date — natural key shifts, new row appears.
            changed_values={"value": "new", "eff_date": "20260501"},
            simulator=sim,
        )
    finally:
        teardown()


# ---------------------------------------------------------------------------
# UNKNOWN / TRUNCATE_RELOAD — both skipped per template contract
# ---------------------------------------------------------------------------


def test_unknown_semantics_skips_simulation(sqlite_engine: Engine) -> None:
    spec = TableSpec(
        table_name="phase09_compat",
        columns=("id",),
        coercers={"id": int},
        delta_semantics=DeltaSemantics.UNKNOWN,
    )

    def explosive_simulator(row, tx):  # pragma: no cover
        raise AssertionError(
            "UNKNOWN delta_semantics simulator must not be invoked"
        )

    # No teardown needed — the simulator factory isn't called.
    assert_delta_semantics_acd_cycle(
        spec,
        natural_key={"id": 1},
        initial_row={},
        changed_values={},
        simulator=explosive_simulator,
    )


def test_truncate_reload_semantics_skips_simulation(sqlite_engine: Engine) -> None:
    spec = TableSpec(
        table_name="bulk_reload",
        columns=("id",),
        coercers={"id": int},
        delta_semantics=DeltaSemantics.TRUNCATE_RELOAD,
    )

    def explosive_simulator(row, tx):  # pragma: no cover
        raise AssertionError(
            "TRUNCATE_RELOAD delta_semantics simulator must not be invoked "
            "(reload contract is tested by a dedicated integration test)"
        )

    assert_delta_semantics_acd_cycle(
        spec,
        natural_key={"id": 1},
        initial_row={},
        changed_values={},
        simulator=explosive_simulator,
    )


# ---------------------------------------------------------------------------
# make_sqlite_simulator — input validation
# ---------------------------------------------------------------------------


def test_simulator_rejects_append_only_with_explicit_conflict_action(
    sqlite_engine: Engine,
) -> None:
    """Operator can't claim append_only + a conflict_action — surface the contradiction."""
    with pytest.raises(ValueError, match="mutually exclusive"):
        make_sqlite_simulator(
            sqlite_engine,
            table_name="bad",
            natural_key_columns=("id",),
            all_columns=("id",),
            append_only=True,
            conflict_action="nothing",
        )


def test_simulator_rejects_unknown_conflict_action(sqlite_engine: Engine) -> None:
    with pytest.raises(ValueError, match="conflict_action must be"):
        make_sqlite_simulator(
            sqlite_engine,
            table_name="bad",
            natural_key_columns=("id",),
            all_columns=("id",),
            conflict_action="weird",
        )
