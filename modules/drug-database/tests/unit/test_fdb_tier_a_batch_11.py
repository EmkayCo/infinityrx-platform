"""B9.B C16 — Tier A batch 11 contract tests (hybrid NK widths + DATE columns).

This batch mixes single-column and multi-column natural keys:
  NK == 1:  RBLAPN0_PROPRIETARY_NAME, RXRNCQQ0_QQ_MSTR
  NK == 2:  RXRFAHX0_AGCSP_HICSEQN, RXRFDDX0_DACN_AGCSP,
            RXRGDFQ0_GCDF_SCRIPT_QQ, RXRMDFQ0_MEDDOSFM_SCRIPT_QQ,
            RXRPDFQ0_POEMDOSFM_SCRIPT_QQ
  NK == 3:  RMEDMGL0_MED_GENERIC_MED_LINK, RMEDMHL0_MED_HICLSEQNO_LINK
  NK == 4:  RBLAHIC0_INGREDIENTS, RPRDPC0_EXT_PRODUCT_CD

The ACD cycle test branches on NATURAL_KEY_COUNT[spec.table_name]:
  NK >= 2 → composite-NK pattern (batch_08 template): all NK cols as
            natural_key dict; last column as the changed value.
  NK == 1 → single-NK + extra_cols pattern (batch_04 template): first
            col as natural_key; second col as desc; remaining cols as
            extra_cols placeholders.

DATE column placeholder values: strings in "YYYYMMDD" form ("20260101").
The SQLite simulator stores all values as strings; _parse_fdb_date is
invoked by the real parser at parse time, NOT inside the contract
simulator. The ACD cycle tests verify delta-semantics correctness, not
coercion; using the raw string form avoids touching the coercer in test
context and matches how the simulator column layer works.

Special case — RPRDPC0_EXT_PRODUCT_CD: the NK includes EXT_PRODUCT_CD_START_DT
(a DATE column at position 3 of the NK). Its placeholder value is "20260101"
(raw YYYYMMDD string). The non-NK column EXT_PRODUCT_CD_END_DT (also DATE,
nullable) gets a placeholder of "20261231" in initial_row and changed_values.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from drug_database.services.fdb_adapter import DeltaSemantics
from drug_database.services.fdb_tier_a.batch_11 import SPECS, NATURAL_KEY_COUNT

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
# Hybrid ACD cycle — branches on NK width
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_engine():
    return create_engine("sqlite:///:memory:", future=True)


# Placeholder values for DATE columns when used as NK or extra-col values.
# Raw YYYYMMDD strings — the simulator stores everything as string; the real
# _parse_fdb_date coercer is NOT invoked inside the contract simulator.
_DATE_PLACEHOLDER_A = "20260101"
_DATE_PLACEHOLDER_B = "20261231"


def _nk_placeholder(col: str, idx: int) -> str:
    """Return a stable placeholder for a natural-key column.

    DATE columns (identified by the FDB naming convention *_DT or *DATEC
    or *DATE*) get a YYYYMMDD-form string; everything else gets a
    positional string.
    """
    col_upper = col.upper()
    if col_upper.endswith("_DT") or "DATEC" in col_upper or "DATE" in col_upper:
        return _DATE_PLACEHOLDER_A
    return f"nk_val_{idx}"


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_delta_semantics_acd_cycle(spec, sqlite_engine) -> None:
    """Hybrid A/C/D/re-A correctness per NATURAL_KEY_COUNT.

    NK >= 2 (composite-NK): natural_key spans the first NK columns;
    the LAST column is the mutable value toggled by C-step.

    NK == 1 (single-NK): first column is the natural key; second column
    is the description; columns[2:] are extra_cols with stable placeholders.
    """
    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
        f"{spec.table_name}: batch_11 invariant — UPSERT_BY_NATURAL_KEY only."
    )
    nk_count = NATURAL_KEY_COUNT[spec.table_name]

    if nk_count >= 2:
        # ----------------------------------------------------------------
        # Composite-NK branch (batch_08 pattern)
        # ----------------------------------------------------------------
        nk_cols = tuple(spec.columns[:nk_count])
        non_nk_cols = list(spec.columns[nk_count:])

        sim, teardown = make_sqlite_simulator(
            sqlite_engine,
            table_name=spec.table_name.lower(),
            natural_key_columns=nk_cols,
            all_columns=spec.columns,
            conflict_action="upsert",
        )
        try:
            natural_key = {
                col: _nk_placeholder(col, i) for i, col in enumerate(nk_cols)
            }

            if not non_nk_cols:
                # All-NK table: pure junction with no mutable columns.
                # A and C carry the same full-NK row; ON CONFLICT DO NOTHING
                # keeps count at 1. initial_row and changed_values are empty.
                assert_delta_semantics_acd_cycle(
                    spec,
                    natural_key=natural_key,
                    initial_row={},
                    changed_values={},
                    simulator=sim,
                )
            else:
                # Table has one or more non-NK mutable columns.
                # Build initial_row and changed_values covering ALL non-NK cols.
                # The last non-NK col is the "desc" that the C-step mutates;
                # earlier non-NK cols get stable placeholders in both rows.
                desc_col = non_nk_cols[-1]
                stable_extra = {}
                for i, col in enumerate(non_nk_cols[:-1]):
                    col_upper = col.upper()
                    if "DATE" in col_upper or col_upper.endswith("_DT") or "DATEC" in col_upper:
                        stable_extra[col] = _DATE_PLACEHOLDER_A
                    else:
                        stable_extra[col] = f"extra_{i}"

                col_upper = desc_col.upper()
                if "DATE" in col_upper or col_upper.endswith("_DT") or "DATEC" in col_upper:
                    initial_desc_val = _DATE_PLACEHOLDER_A
                    changed_desc_val = _DATE_PLACEHOLDER_B
                else:
                    initial_desc_val = "initial description"
                    changed_desc_val = "CHANGED DESCRIPTION"

                assert_delta_semantics_acd_cycle(
                    spec,
                    natural_key=natural_key,
                    initial_row={desc_col: initial_desc_val, **stable_extra},
                    changed_values={desc_col: changed_desc_val, **stable_extra},
                    simulator=sim,
                )
        finally:
            teardown()

    else:
        # ----------------------------------------------------------------
        # Single-NK branch (batch_04 pattern)
        # ----------------------------------------------------------------
        assert nk_count == 1
        natural_key_col = spec.columns[0]
        desc_col = spec.columns[1]

        # Extra cols: everything beyond col[1] gets a stable placeholder.
        extra_cols: dict[str, str] = {}
        for i, col in enumerate(spec.columns[2:], start=2):
            col_upper = col.upper()
            if "DATE" in col_upper or col_upper.endswith("_DT") or "DATEC" in col_upper:
                extra_cols[col] = _DATE_PLACEHOLDER_A
            else:
                extra_cols[col] = f"placeholder_{i}"

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
def test_spec_natural_key_count_registered(spec) -> None:
    """Every batch_11 spec has a NATURAL_KEY_COUNT entry."""
    nk_count = NATURAL_KEY_COUNT.get(spec.table_name)
    assert nk_count is not None, (
        f"{spec.table_name}: missing NATURAL_KEY_COUNT entry — "
        f"add it to batch_11.NATURAL_KEY_COUNT."
    )
    assert 1 <= nk_count <= len(spec.columns), (
        f"{spec.table_name}: NATURAL_KEY_COUNT={nk_count} out of range "
        f"[1, {len(spec.columns)}]."
    )


def test_batch_11_has_expected_table_count() -> None:
    assert len(SPECS) == 11, f"batch_11 has {len(SPECS)} specs; expected 11"


def test_natural_key_count_covers_all_specs() -> None:
    """NATURAL_KEY_COUNT has exactly one entry per spec."""
    spec_names = {s.table_name for s in SPECS}
    nk_names = set(NATURAL_KEY_COUNT.keys())
    assert nk_names == spec_names, (
        f"NATURAL_KEY_COUNT mismatch: "
        f"extra={sorted(nk_names - spec_names)}, "
        f"missing={sorted(spec_names - nk_names)}"
    )
