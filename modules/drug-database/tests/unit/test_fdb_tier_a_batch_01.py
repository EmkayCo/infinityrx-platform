"""B9.B C6 — Tier A batch 01 contract tests (canonical template).

This file is the AUTHORITATIVE pattern parallel B9.B agents replicate
for batches 02-10. Each batch test module:

  1. Imports its sibling batch_NN.SPECS list (no re-declaration).
  2. Declares `BATCH_TESTED_NAMES: frozenset[str]` — the
     test_fdb_contract_coverage loader picks this up automatically.
     CONTRACT_TESTED_SPECS becomes the union of all batch declarations.
  3. Has one parametrized test per contract assertion shape, driven by
     SPECS. Adding a new spec to batch_01.py automatically expands
     the parametrize matrix here — no test edits needed for new specs
     in the SAME batch.

Coverage shape (per spec, per test function):

  test_schema_parity_against_ddl_manifest      — column-set matches DDL
  test_delta_semantics_acd_cycle               — A→C→D→re-A correct
  test_record_counts_key_resolves_in_real_file — record_counts_key exists

The latin-1 decode smoke / UPD A/C/D probe / row-count reconciliation
contracts that require the real FDB drop run as INTEGRATION tests
elsewhere — they skip without Docker + a live drop on disk.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from drug_database.services.fdb_adapter import DeltaSemantics
from drug_database.services.fdb_tier_a.batch_01 import SPECS

# Reach the helpers without going through the `tests` package (see
# the same pattern in tests/unit/test_fdb_contract.py).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _fdb_contract import (  # noqa: E402
    assert_delta_semantics_acd_cycle,
    assert_schema_parity,
)
from _fdb_delta_semantics import make_sqlite_simulator  # noqa: E402

from sqlalchemy import create_engine  # noqa: E402


# ---------------------------------------------------------------------------
# Coverage declaration — picked up by test_fdb_contract_coverage._load
# ---------------------------------------------------------------------------


BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)


# ---------------------------------------------------------------------------
# Schema parity vs. the per-table DDL manifest
# ---------------------------------------------------------------------------


_MANIFEST = json.loads(
    (
        Path(__file__).resolve().parents[4]
        / "infrastructure" / "scripts" / "lib"
        / "fdb_table_ddl_manifest.json"
    ).read_text(encoding="utf-8")
)


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_spec_columns_match_ddl_manifest(spec) -> None:
    """Spec's `columns` tuple matches the manifest's column-name list."""
    entry = _MANIFEST.get(spec.table_name)
    assert entry is not None, (
        f"{spec.table_name}: missing from DDL manifest — either the "
        f"spec name is wrong or the manifest needs regenerating "
        f"(`python infrastructure/scripts/build_fdb_ddl_manifest.py`)."
    )
    manifest_names = tuple(c["name"] for c in entry["columns"])
    assert tuple(spec.columns) == manifest_names, (
        f"{spec.table_name}: spec.columns={spec.columns} but manifest "
        f"says {manifest_names}. One is wrong; reconcile with the DDL."
    )


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_spec_nullable_set_matches_manifest(spec) -> None:
    """`nullable` frozenset matches manifest's nullable=true columns."""
    entry = _MANIFEST[spec.table_name]
    manifest_nullable = {
        c["name"] for c in entry["columns"] if c["nullable"]
    }
    # The spec is allowed to be MORE restrictive (mark a nullable
    # column as not-null), but never less. Reject the unsafe direction.
    spec_marks_required_as_nullable = spec.nullable - manifest_nullable
    assert not spec_marks_required_as_nullable, (
        f"{spec.table_name}: spec marks {sorted(spec_marks_required_as_nullable)} "
        f"as nullable but DDL says NOT NULL. Spec must not be MORE "
        f"permissive than the DDL — that would let the loader insert "
        f"NULL into a column the DDL rejects."
    )


# ---------------------------------------------------------------------------
# Delta semantics A/C/D/re-A simulation
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_engine():
    """Fresh in-memory SQLite per test."""
    return create_engine("sqlite:///:memory:", future=True)


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_delta_semantics_acd_cycle_for_each_spec(spec, sqlite_engine) -> None:
    """Every batch_01 spec passes the A/C/D/re-A correctness contract.

    Each Tier A table is UPSERT_BY_NATURAL_KEY: id+desc semantics. The
    natural key is the FIRST column; the second column is the
    description. C-step changes the description; D-step deletes; re-A
    restores. Correct UPSERT (ON CONFLICT DO UPDATE) passes all four
    sub-assertions in _fdb_contract.
    """
    assert spec.delta_semantics is DeltaSemantics.UPSERT_BY_NATURAL_KEY, (
        f"{spec.table_name}: batch_01 invariant — all specs are "
        f"UPSERT_BY_NATURAL_KEY (id+desc lookups). Got "
        f"{spec.delta_semantics}."
    )
    natural_key_col = spec.columns[0]
    desc_col = spec.columns[1]
    table_name_safe = spec.table_name.lower()

    sim, teardown = make_sqlite_simulator(
        sqlite_engine,
        table_name=table_name_safe,
        natural_key_columns=(natural_key_col,),
        all_columns=spec.columns,
        conflict_action="upsert",
    )
    try:
        assert_delta_semantics_acd_cycle(
            spec,
            natural_key={natural_key_col: "key_val_42"},
            initial_row={desc_col: "initial description"},
            changed_values={desc_col: "CHANGED DESCRIPTION"},
            simulator=sim,
        )
    finally:
        teardown()


# ---------------------------------------------------------------------------
# Spec sanity (Tier + loader_group + record_counts_key invariants)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_spec_is_tagged_tier_a(spec) -> None:
    from drug_database.services.fdb_adapter import Tier
    assert spec.tier is Tier.A, (
        f"{spec.table_name}: tier={spec.tier!r}, expected Tier.A — "
        f"batch_01 is Tier A only."
    )


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_spec_loader_group_is_fdb_tier_a(spec) -> None:
    assert spec.loader_group == "fdb_tier_a", (
        f"{spec.table_name}: loader_group={spec.loader_group!r}; "
        f"every Tier A spec MUST set loader_group='fdb_tier_a' so the "
        f"registry's tier-aware filter includes it on `--mode fdb_tier_a`."
    )


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_spec_record_counts_key_set(spec) -> None:
    """Every spec sets record_counts_key — required for row-count reconciliation."""
    assert spec.record_counts_key, (
        f"{spec.table_name}: record_counts_key is empty — "
        f"assert_row_count_reconciles cannot lookup the FDB manifest "
        f"value without it. Set it to the FDB short key from "
        f"RECORD_COUNTS.TXT (typically the first underscore-segment "
        f"of the table_name)."
    )


def test_batch_01_has_expected_table_count() -> None:
    """Batch 01 ships 12 specs — canonical template size."""
    assert len(SPECS) == 12, (
        f"batch_01 SPECS has {len(SPECS)} entries; canonical template "
        f"is 12. If extending this batch beyond 12 tables, also extend "
        f"this assertion (or move overflow to batch_02)."
    )
