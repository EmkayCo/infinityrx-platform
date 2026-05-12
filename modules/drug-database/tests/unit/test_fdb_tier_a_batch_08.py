"""B9.B C13 — Tier A batch 08 contract tests (composite-NK template).

The previous batches all used single-column natural keys. Batch 08
introduces 3- and 4-column composite NKs (TALL MAN family). This file
is the AUTHORITATIVE pattern for batches 09+ that share the
composite-NK shape.

Key differences vs. the batch_04 pattern:

  1. natural_key dict has multiple entries (all spec.columns except
     the last — the description).
  2. Simulator's `natural_key_columns` is a tuple of those column names.
  3. extra_cols is empty (there is no third "extra" non-key column —
     the desc is the only non-key column).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from drug_database.services.fdb_adapter import DeltaSemantics
from drug_database.services.fdb_tier_a.batch_08 import SPECS, NATURAL_KEY_COUNT

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
# Composite-NK ACD cycle (THE NEW PATTERN)
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_engine():
    return create_engine("sqlite:///:memory:", future=True)


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_delta_semantics_acd_cycle_composite_nk(spec, sqlite_engine) -> None:
    """Composite-NK A/C/D/re-A correctness.

    Natural key spans the first N columns where N = NATURAL_KEY_COUNT[name].
    The LAST column is the desc that the C step toggles.
    """
    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
        f"{spec.table_name}: batch_08 invariant — UPSERT_BY_NATURAL_KEY only."
    )
    nk_count = NATURAL_KEY_COUNT[spec.table_name]
    assert nk_count >= 2, f"{spec.table_name}: batch_08 is composite-NK only"
    nk_cols = tuple(spec.columns[:nk_count])
    desc_col = spec.columns[-1]

    sim, teardown = make_sqlite_simulator(
        sqlite_engine,
        table_name=spec.table_name.lower(),
        natural_key_columns=nk_cols,
        all_columns=spec.columns,
        conflict_action="upsert",
    )
    try:
        # Build natural_key dict — placeholder values for every NK column.
        natural_key = {
            col: f"nk_val_{i}" for i, col in enumerate(nk_cols)
        }
        assert_delta_semantics_acd_cycle(
            spec,
            natural_key=natural_key,
            initial_row={desc_col: "initial description"},
            changed_values={desc_col: "CHANGED DESCRIPTION"},
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
def test_spec_has_composite_nk(spec) -> None:
    """Every batch_08 spec has multi-column natural key per NATURAL_KEY_COUNT."""
    nk_count = NATURAL_KEY_COUNT.get(spec.table_name)
    assert nk_count is not None and nk_count >= 2, (
        f"{spec.table_name}: missing NATURAL_KEY_COUNT entry or NK <2 — "
        f"batch_08 is composite-NK only. Move single-NK specs to a "
        f"different batch."
    )


def test_batch_08_has_expected_table_count() -> None:
    assert len(SPECS) == 5, f"batch_08 has {len(SPECS)} specs; expected 5"
