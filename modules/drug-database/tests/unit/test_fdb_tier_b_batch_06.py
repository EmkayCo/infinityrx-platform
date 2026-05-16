"""B9.C Tier B batch 06 contract tests (schema-only scaffold).

Covers: ROBCNDC0, RPEIGA0, RPEIGD0, RPEIGR0, RPEIGRR0, RPEIHR0, RPEIMA0, RPEIMD0, RPEIMNR0.
Row-population and FK-integrity tests deferred to Docker-up.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from drug_database.services.fdb_adapter import Tier
from drug_database.services.fdb_tier_b.batch_06 import SPECS

_MANIFEST = json.loads(
    (Path(__file__).resolve().parents[4]
     / "infrastructure" / "scripts" / "lib" / "fdb_table_ddl_manifest.json")
    .read_text(encoding="utf-8")
)

BATCH_TESTED_NAMES: frozenset[str] = frozenset(s.table_name for s in SPECS)


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_spec_columns_match_ddl_manifest(spec) -> None:
    entry = _MANIFEST.get(spec.table_name)
    assert entry is not None, f"{spec.table_name}: not in DDL manifest"
    assert tuple(spec.columns) == tuple(c["name"] for c in entry["columns"])


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_spec_nullable_matches_manifest(spec) -> None:
    entry = _MANIFEST[spec.table_name]
    mnb = {c["name"] for c in entry["columns"] if c.get("nullable")}
    assert not (spec.nullable - mnb)


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_tier_b(spec) -> None: assert spec.tier is Tier.B


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_loader_group(spec) -> None: assert spec.loader_group == "fdb_tier_b"


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_natural_key(spec) -> None: assert spec.natural_key


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.table_name)
def test_record_counts_key(spec) -> None: assert spec.record_counts_key


def test_batch_count() -> None: assert len(SPECS) == 9
