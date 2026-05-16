"""B9.C — Tier B batch 01 contract tests (schema-only scaffold).

Covers 9 tables: RAHFSGC1, RAPPLNA0, RAPPLSL0, RATCGC0, RCQNDC0,
RETCGC0, RETCGCH0, RETCHCL0, RETCHIC0.

Schema-only tests (no live FDB drop required):
  * spec.columns matches DDL manifest
  * spec.nullable set matches manifest
  * spec.tier == Tier.B
  * spec.loader_group == "fdb_tier_b"
  * spec.natural_key is non-empty
  * spec.record_counts_key is set

Row-population and FK-integrity tests deferred to Docker-up session
per the B9.B live-DB evidence pattern (status.md MEDIUM 3).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drug_database.services.fdb_adapter import DeltaSemantics, Tier
from drug_database.services.fdb_tier_b.batch_01 import SPECS

_MANIFEST = json.loads(
    (
        Path(__file__).resolve().parents[4]
        / "infrastructure" / "scripts" / "lib"
        / "fdb_table_ddl_manifest.json"
    ).read_text(encoding="utf-8")
)

BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_spec_columns_match_ddl_manifest(spec) -> None:
    entry = _MANIFEST.get(spec.table_name)
    assert entry is not None, (
        f"{spec.table_name}: not in DDL manifest — check table name spelling."
    )
    manifest_names = tuple(c["name"] for c in entry["columns"])
    assert tuple(spec.columns) == manifest_names, (
        f"{spec.table_name}: columns mismatch.\n"
        f"  spec:     {spec.columns}\n"
        f"  manifest: {manifest_names}"
    )


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_spec_nullable_set_matches_manifest(spec) -> None:
    entry = _MANIFEST[spec.table_name]
    manifest_nullable = {c["name"] for c in entry["columns"] if c.get("nullable")}
    over_permissive = spec.nullable - manifest_nullable
    assert not over_permissive, (
        f"{spec.table_name}: spec marks {sorted(over_permissive)} nullable "
        f"but manifest says NOT NULL."
    )


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_spec_is_tagged_tier_b(spec) -> None:
    assert spec.tier is Tier.B, (
        f"{spec.table_name}: tier={spec.tier!r}, expected Tier.B."
    )


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_spec_loader_group_is_fdb_tier_b(spec) -> None:
    assert spec.loader_group == "fdb_tier_b", (
        f"{spec.table_name}: loader_group={spec.loader_group!r}; must be 'fdb_tier_b'."
    )


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_spec_natural_key_is_set(spec) -> None:
    assert spec.natural_key, (
        f"{spec.table_name}: natural_key is empty — every Tier B spec needs "
        f"a natural key for ON CONFLICT handling."
    )


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_spec_record_counts_key_set(spec) -> None:
    assert spec.record_counts_key, (
        f"{spec.table_name}: record_counts_key is empty."
    )


def test_batch_01_has_expected_table_count() -> None:
    assert len(SPECS) == 9, (
        f"batch_01 has {len(SPECS)} specs; expected 9."
    )
