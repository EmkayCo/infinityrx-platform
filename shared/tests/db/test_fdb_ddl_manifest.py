"""B9.B C4 — Lock-in tests for the per-table DDL manifest.

The manifest at `infrastructure/scripts/lib/fdb_table_ddl_manifest.json`
is the AUTHORITATIVE column-list source for B9.B-G builder agents.
Each agent reads its assigned tables from this file and authors
SQLAlchemy models + TableSpec coercers without re-parsing the DDL zip.

These tests prevent silent regression of the manifest builder:
schema-shape changes here would cascade across 200+ per-table specs.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3]
    / "infrastructure" / "scripts" / "lib" / "fdb_table_ddl_manifest.json"
)


@pytest.fixture(scope="module")
def manifest() -> dict:
    """Load the in-repo manifest once per test module."""
    if not _MANIFEST_PATH.exists():
        pytest.skip(
            f"DDL manifest missing at {_MANIFEST_PATH}. Run "
            f"`python infrastructure/scripts/build_fdb_ddl_manifest.py`."
        )
    return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_has_expected_table_count(manifest: dict) -> None:
    """220 DB.zip tables + 1 NDDF_PRODUCT_INFO metadata = 221 entries.

    Tolerance ±3 for vendor drift between drops; if it slips outside
    that, regenerate the manifest in the same commit that bumps the
    DB.zip namelist's 220 count.
    """
    assert 218 <= len(manifest) <= 224, (
        f"DDL manifest has {len(manifest)} entries; expected 221 "
        f"(220 DB.zip + 1 metadata). Either vendor drift or builder regression."
    )


def test_manifest_includes_all_db_zip_namelist_tables(manifest: dict) -> None:
    """Every DB.zip table MUST have a manifest entry — no orphans."""
    namelist_path = (
        Path(__file__).resolve().parents[3]
        / "infrastructure" / "scripts" / "lib" / "fdb_db_zip_namelist.txt"
    )
    namelist = {
        line.strip() for line in namelist_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    manifest_keys = set(manifest.keys())
    missing = namelist - manifest_keys
    assert not missing, (
        f"{len(missing)} DB.zip tables missing from DDL manifest: "
        f"{sorted(missing)[:10]}... Regenerate the manifest after a "
        f"vendor drop ships new tables."
    )


def test_manifest_entry_has_required_fields(manifest: dict) -> None:
    """Every entry has dataset + columns; every column has name/type/nullable."""
    for table_name, entry in manifest.items():
        assert "dataset" in entry, f"{table_name}: missing 'dataset'"
        assert "columns" in entry, f"{table_name}: missing 'columns'"
        assert entry["columns"], f"{table_name}: empty columns"
        for col in entry["columns"]:
            assert "name" in col, f"{table_name}: column missing name"
            assert "sql_type" in col, f"{table_name}.{col.get('name','?')}: missing sql_type"
            assert "nullable" in col, f"{table_name}.{col.get('name','?')}: missing nullable"
            assert isinstance(col["nullable"], bool), (
                f"{table_name}.{col['name']}: nullable must be bool"
            )


def test_rnp3_matches_phase09_known_schema(manifest: dict) -> None:
    """Lock-in: RNP3_NDC_PRICE columns exactly match the Phase 09 TableSpec.

    Phase 09 declared RNP3 with: NDC, PRICE_TYPE, PRICE_EFFECTIVE_DT, PRICE.
    The manifest must agree, or per-table spec generation in B9.B+
    silently drops or duplicates columns.
    """
    rnp3 = manifest.get("RNP3_NDC_PRICE")
    assert rnp3 is not None, "RNP3_NDC_PRICE missing from manifest"
    column_names = [c["name"] for c in rnp3["columns"]]
    assert column_names == ["NDC", "PRICE_TYPE", "PRICE_EFFECTIVE_DT", "PRICE"]
    # Spot-check PRICE is decimal-typed (NUMERIC) — Phase 09's
    # Decimal coercer depends on this.
    price = next(c for c in rnp3["columns"] if c["name"] == "PRICE")
    assert "NUMERIC" in price["sql_type"].upper()


def test_rndc14_has_68_columns(manifest: dict) -> None:
    """Recon documents RNDC14_NDC_MSTR as the 68-column NDC master.

    This is the load-bearing table referenced by adjudication +
    formulary + reclaimrx. A regression in column count here means
    the manifest builder is dropping columns, which would silently
    underspec the most important B9 table.
    """
    rndc14 = manifest.get("RNDC14_NDC_MSTR")
    assert rndc14 is not None, "RNDC14_NDC_MSTR missing from manifest"
    assert len(rndc14["columns"]) == 68, (
        f"RNDC14_NDC_MSTR has {len(rndc14['columns'])} columns; "
        f"recon documents 68. Manifest builder regression."
    )


def test_sql_types_have_no_internal_whitespace(manifest: dict) -> None:
    """`VARCHAR(11)` not `VARCHAR (11)` — consistent normalization."""
    import re
    for table_name, entry in manifest.items():
        for col in entry["columns"]:
            assert " " not in col["sql_type"], (
                f"{table_name}.{col['name']}: sql_type {col['sql_type']!r} "
                f"has whitespace — normalize in build_fdb_ddl_manifest.py."
            )


def test_column_count_distribution_matches_recon(manifest: dict) -> None:
    """Sanity: distribution matches what recon §3 documented.

    Recon: ~113 Tier A (≤5 cols), ~66 Tier B (NDC/GCN joins, 2-7 cols),
    ~19 Tier C (>8 cols or large), 19 Tier D (MTL, varied).

    This test asserts the COARSE distribution. Exact tier
    classification is the operator's call (B9.B+ design work) — this
    only catches manifest-builder regressions that systematically
    drop/duplicate columns.
    """
    col_counts = [len(v["columns"]) for v in manifest.values()]
    # ≤5 col tables: recon says ~113 Tier A → expect 100-200
    small = sum(1 for c in col_counts if c <= 5)
    assert 100 <= small <= 200, (
        f"≤5-col table count: {small}; expected 100-200 per recon. "
        f"Builder may be dropping columns systematically."
    )
    # ≥8 col tables: recon says ~21 (19 Tier C + RNDC14 + a few outliers)
    large = sum(1 for c in col_counts if c >= 8)
    assert 15 <= large <= 40, (
        f"≥8-col table count: {large}; expected 15-40 per recon."
    )
