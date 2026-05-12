"""B9.B C14 — Tier A batch 09 contract tests (APPEND_ONLY history template).

batch_09 specs are all `delta_semantics=APPEND_ONLY` — history rows
that grow with each weekly delta and are never updated in place. The
simulator uses `append_only=True` (not `conflict_action="upsert"`),
and the contract template's APPEND_ONLY branch asserts row-count
growth across A/C/D/re-A.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from drug_database.services.fdb_adapter import DeltaSemantics
from drug_database.services.fdb_tier_a.batch_09 import SPECS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _fdb_contract import (  # noqa: E402
    assert_delta_semantics_acd_cycle,
)
from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402

from sqlalchemy import create_engine  # noqa: E402


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
    assert entry is not None
    manifest_names = tuple(c["name"] for c in entry["columns"])
    assert tuple(spec.columns) == manifest_names


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_spec_nullable_set_matches_manifest(spec) -> None:
    entry = _MANIFEST[spec.table_name]
    manifest_nullable = {c["name"] for c in entry["columns"] if c["nullable"]}
    spec_extras = spec.nullable - manifest_nullable
    assert not spec_extras, (
        f"{spec.table_name}: spec marks {sorted(spec_extras)} nullable "
        f"but DDL says NOT NULL."
    )


# ---------------------------------------------------------------------------
# APPEND_ONLY ACD cycle
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_engine():
    return create_engine("sqlite:///:memory:", future=True)


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_delta_semantics_append_only_for_each_spec(spec, sqlite_engine) -> None:
    """Every batch_09 spec passes the APPEND_ONLY A/C/D/re-A contract.

    APPEND_ONLY semantics: every transaction grows the row count.
    `make_sqlite_simulator` with `append_only=True` makes every
    INSERT a plain INSERT (no ON CONFLICT), and D becomes a tombstone
    append (preserves the count-grows invariant — see _fdb_delta_semantics).
    """
    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY, (
        f"{spec.table_name}: batch_09 invariant — APPEND_ONLY only."
    )

    # Natural key: all non-date columns at the start (first 2-3 typically).
    # The template's APPEND_ONLY branch doesn't check state-after-A specifically
    # (just count growth); the natural_key is used only for the "find row"
    # lookup, which is allowed to return None for append_only tables.
    natural_key_col = spec.columns[0]
    # Use a sentinel value distinct from the desc/date column to avoid coercer issues.
    natural_key = {natural_key_col: "nk_42"}
    # Fill out remaining columns with placeholders so INSERT covers all.
    other_cols = {c: "p" for c in spec.columns[1:]}

    sim, teardown = make_sqlite_simulator(
        sqlite_engine,
        table_name=spec.table_name.lower(),
        natural_key_columns=(natural_key_col,),
        all_columns=spec.columns,
        append_only=True,
    )
    try:
        assert_delta_semantics_acd_cycle(
            spec,
            natural_key=natural_key,
            initial_row=other_cols,
            changed_values=other_cols,
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
def test_spec_uses_append_only_semantics(spec) -> None:
    """batch_09 is APPEND_ONLY only — no UPSERTs in history tables."""
    assert spec.delta_semantics is DeltaSemantics.APPEND_ONLY


def test_batch_09_has_expected_table_count() -> None:
    assert len(SPECS) == 8, f"batch_09 has {len(SPECS)} specs; expected 8"
