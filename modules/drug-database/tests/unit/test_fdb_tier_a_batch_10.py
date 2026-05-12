"""B9.B C15 — Tier A batch 10 contract tests (composite+single NK hybrid).

batch_10 contains three structural families. The ACD cycle test branches
on `NATURAL_KEY_COUNT[spec.table_name]`:

  NK == 1 (single-NK):
    batch_04 pattern — natural key is columns[0]; extra_cols fills
    columns[2:] with stable placeholders; columns[1] is the desc toggled
    in the C step.

  NK == 2 AND len(spec.columns) == 2 (pure-link, all cols are NK):
    Composite-NK sub-pattern where there is NO non-key column. The
    simulator falls through to `on_conflict_do_nothing` because
    `update_cols` is empty — correct behaviour for a pure link table.
    `initial_row` and `changed_values` are both empty dicts; the C step
    assertion is vacuously satisfied (no non-key state to check).

  NK == 2 AND len(spec.columns) > 2 (composite-NK with extra col):
    batch_08 pattern — first NK cols are the natural key; last column(s)
    are the value toggled in the C step.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from drug_database.services.fdb_adapter import DeltaSemantics
from drug_database.services.fdb_tier_a.batch_10 import SPECS, NATURAL_KEY_COUNT

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _fdb_contract import (  # noqa: E402
    assert_delta_semantics_acd_cycle,
)
from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402

from sqlalchemy import create_engine  # noqa: E402


# ---------------------------------------------------------------------------
# Coverage declaration — picked up by test_fdb_contract_coverage._load
# ---------------------------------------------------------------------------

BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)


_MANIFEST = json.loads(
    (
        Path(__file__).resolve().parents[4]
        / "infrastructure" / "scripts" / "lib"
        / "fdb_table_ddl_manifest.json"
    ).read_text(encoding="utf-8")
)


# ---------------------------------------------------------------------------
# Schema parity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_spec_columns_match_ddl_manifest(spec) -> None:
    entry = _MANIFEST.get(spec.table_name)
    assert entry is not None, f"{spec.table_name}: missing from DDL manifest"
    manifest_names = tuple(c["name"] for c in entry["columns"])
    assert tuple(spec.columns) == manifest_names


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_spec_nullable_set_matches_manifest(spec) -> None:
    entry = _MANIFEST[spec.table_name]
    manifest_nullable = {c["name"] for c in entry["columns"] if c["nullable"]}
    spec_marks_required_as_nullable = spec.nullable - manifest_nullable
    assert not spec_marks_required_as_nullable, (
        f"{spec.table_name}: spec marks {sorted(spec_marks_required_as_nullable)} "
        f"nullable but DDL says NOT NULL."
    )


# ---------------------------------------------------------------------------
# Hybrid ACD cycle — branches on NATURAL_KEY_COUNT
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_engine():
    return create_engine("sqlite:///:memory:", future=True)


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_delta_semantics_acd_cycle(spec, sqlite_engine) -> None:
    """A/C/D/re-A correctness — branches on NATURAL_KEY_COUNT.

    Three sub-patterns (see module docstring):
      nk_count == 1    → single-NK with extra_cols (batch_04 pattern)
      nk_count == 2, len(columns) == 2  → pure-link all-NK (vacuous C step)
      nk_count == 2, len(columns) > 2   → composite-NK with trailing extra col
    """
    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
        f"{spec.table_name}: batch_10 invariant — UPSERT_BY_NATURAL_KEY only."
    )
    nk_count = NATURAL_KEY_COUNT[spec.table_name]
    nk_cols = tuple(spec.columns[:nk_count])
    natural_key = {col: f"nk_val_{i}" for i, col in enumerate(nk_cols)}

    if nk_count == 1:
        # ----------------------------------------------------------------
        # Single-NK path (batch_04 pattern): col[0]=key, col[1]=desc,
        # col[2:]=extra placeholders.
        # ----------------------------------------------------------------
        natural_key_col = spec.columns[0]
        desc_col = spec.columns[1]
        extra_cols = {
            col: f"placeholder_{i}"
            for i, col in enumerate(spec.columns[2:], start=2)
        }
        sim, teardown = make_sqlite_simulator(
            sqlite_engine,
            table_name=spec.table_name.lower(),
            natural_key_columns=(natural_key_col,),
            all_columns=spec.columns,
            conflict_action="upsert",
        )
        try:
            assert_delta_semantics_acd_cycle(
                spec,
                natural_key={natural_key_col: "key_val_42"},
                initial_row={desc_col: "initial description", **extra_cols},
                changed_values={desc_col: "CHANGED DESCRIPTION", **extra_cols},
                simulator=sim,
            )
        finally:
            teardown()

    elif len(spec.columns) == nk_count:
        # ----------------------------------------------------------------
        # Pure-link path: ALL columns form the natural key; no non-key
        # column exists. The simulator falls back to on_conflict_do_nothing.
        # initial_row and changed_values are empty — C step assertion is
        # vacuously True (nothing to toggle).
        # ----------------------------------------------------------------
        sim, teardown = make_sqlite_simulator(
            sqlite_engine,
            table_name=spec.table_name.lower(),
            natural_key_columns=nk_cols,
            all_columns=spec.columns,
            conflict_action="upsert",
        )
        try:
            assert_delta_semantics_acd_cycle(
                spec,
                natural_key=natural_key,
                initial_row={},
                changed_values={},
                simulator=sim,
            )
        finally:
            teardown()

    else:
        # ----------------------------------------------------------------
        # Composite-NK with trailing extra col(s) (batch_08 pattern):
        # first nk_count cols are the natural key; last column is the
        # value toggled in the C step.
        # ----------------------------------------------------------------
        desc_col = spec.columns[-1]
        sim, teardown = make_sqlite_simulator(
            sqlite_engine,
            table_name=spec.table_name.lower(),
            natural_key_columns=nk_cols,
            all_columns=spec.columns,
            conflict_action="upsert",
        )
        try:
            assert_delta_semantics_acd_cycle(
                spec,
                natural_key=natural_key,
                initial_row={desc_col: "1"},
                changed_values={desc_col: "0"},
                simulator=sim,
            )
        finally:
            teardown()


# ---------------------------------------------------------------------------
# Spec sanity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_spec_is_tagged_tier_a(spec) -> None:
    from drug_database.services.fdb_adapter import Tier
    assert spec.tier is Tier.A


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_spec_loader_group_is_fdb_tier_a(spec) -> None:
    assert spec.loader_group == "fdb_tier_a"


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_spec_record_counts_key_set(spec) -> None:
    assert spec.record_counts_key


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_natural_key_count_entry_exists(spec) -> None:
    """Every batch_10 spec has a NATURAL_KEY_COUNT entry."""
    nk_count = NATURAL_KEY_COUNT.get(spec.table_name)
    assert nk_count is not None, (
        f"{spec.table_name}: missing NATURAL_KEY_COUNT entry"
    )
    assert 1 <= nk_count <= len(spec.columns), (
        f"{spec.table_name}: NATURAL_KEY_COUNT={nk_count} out of range "
        f"for {len(spec.columns)}-column spec"
    )


def test_batch_10_has_expected_table_count() -> None:
    assert len(SPECS) == 11, f"batch_10 has {len(SPECS)} specs; expected 11"
