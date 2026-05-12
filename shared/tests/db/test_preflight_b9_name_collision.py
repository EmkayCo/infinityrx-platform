"""B9.A C10 — Tests for the FDW name-collision preflight.

Covers the pure functions (no Postgres dependency) by injecting a
fake `table_lister`. The Postgres-backed lister is exercised in
B9.B integration when a live reference DB is available.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make `preflight_b9_name_collision.py` importable without packaging
# `infrastructure/scripts/` as a Python package.
_SCRIPTS_DIR = (
    Path(__file__).resolve().parents[3] / "infrastructure" / "scripts"
)
sys.path.insert(0, str(_SCRIPTS_DIR))

from preflight_b9_name_collision import (  # noqa: E402
    fdb_name_to_table_name,
    format_evidence,
    load_expected_names,
    scan_for_collisions,
)


# ---------------------------------------------------------------------------
# fdb_name_to_table_name
# ---------------------------------------------------------------------------


def test_fdb_name_is_lowercased() -> None:
    assert fdb_name_to_table_name("RNP3_NDC_PRICE") == "rnp3_ndc_price"


def test_fdb_name_underscores_preserved() -> None:
    assert fdb_name_to_table_name("RPRDPTD0_PRICE_TYPE_DESC") == "rprdptd0_price_type_desc"


def test_fdb_name_whitespace_stripped() -> None:
    assert fdb_name_to_table_name("  RNDC14_NDC_MSTR  \r\n") == "rndc14_ndc_mstr"


# ---------------------------------------------------------------------------
# load_expected_names
# ---------------------------------------------------------------------------


def test_load_expected_names_parses_record_counts(tmp_path: Path) -> None:
    rc = tmp_path / "RECORD_COUNTS.TXT"
    rc.write_text(
        "# header\n"
        "RFOO=10\n"
        "RBAR=20\n"
        "\n"
        "RNP3_NDC_PRICE=15000000\n",
        encoding="latin-1",
    )
    names = load_expected_names(rc)
    assert names == ["rfoo", "rbar", "rnp3_ndc_price"]


def test_load_expected_names_dedupes_repeats(tmp_path: Path) -> None:
    """Same key on two lines → one entry in the output."""
    rc = tmp_path / "RECORD_COUNTS.TXT"
    rc.write_text("RFOO=10\nRFOO=999\n", encoding="latin-1")
    assert load_expected_names(rc) == ["rfoo"]


def test_load_expected_names_skips_malformed_lines(tmp_path: Path) -> None:
    rc = tmp_path / "RECORD_COUNTS.TXT"
    rc.write_text(
        "RFOO=10\n"
        "this-line-has-no-equals-sign\n"
        "# comment\n"
        "RBAR=20\n",
        encoding="latin-1",
    )
    assert load_expected_names(rc) == ["rfoo", "rbar"]


# ---------------------------------------------------------------------------
# scan_for_collisions
# ---------------------------------------------------------------------------


def test_scan_returns_empty_when_no_collisions() -> None:
    expected = ["rfoo", "rbar"]
    lister = lambda: {("public", "users"), ("core", "tenants")}
    hard, soft = scan_for_collisions(expected, table_lister=lister)
    assert hard == [] and soft == []


def test_scan_flags_hard_collision_in_reference_schema() -> None:
    expected = ["rfoo", "rbar"]
    lister = lambda: {
        ("reference", "rfoo"),     # ← hard
        ("public", "users"),       # unrelated
    }
    hard, soft = scan_for_collisions(expected, table_lister=lister)
    assert hard == [("reference", "rfoo")]
    assert soft == []


def test_scan_flags_hard_collision_in_public_shared_drug_db() -> None:
    expected = ["rmiid1_med", "rndc14_ndc_mstr"]
    lister = lambda: {
        ("public", "rmiid1_med"),
        ("shared", "rndc14_ndc_mstr"),
        ("drug_db", "rmiid1_med"),
    }
    hard, soft = scan_for_collisions(expected, table_lister=lister)
    assert hard == [
        ("drug_db", "rmiid1_med"),
        ("public", "rmiid1_med"),
        ("shared", "rndc14_ndc_mstr"),
    ]


def test_scan_flags_soft_collision_in_drug_database_schema() -> None:
    """drug_database is the OWNED schema — collisions there are soft."""
    expected = ["rnp3_ndc_price"]
    lister = lambda: {("drug_database", "rnp3_ndc_price")}
    hard, soft = scan_for_collisions(expected, table_lister=lister)
    assert hard == []
    assert soft == [("drug_database", "rnp3_ndc_price")]


def test_scan_unknown_schema_treated_as_hard() -> None:
    """Anything we forgot to classify is treated as hard — fail safe."""
    expected = ["rfoo"]
    lister = lambda: {("some_unclassified_schema", "rfoo")}
    hard, soft = scan_for_collisions(expected, table_lister=lister)
    assert hard == [("some_unclassified_schema", "rfoo")]
    assert soft == []


def test_scan_ignores_tables_with_unmatched_names() -> None:
    """A table whose name isn't in expected_names is never a collision."""
    expected = ["rfoo"]
    lister = lambda: {
        ("reference", "rbar"),   # name not in expected
        ("public", "users"),
    }
    hard, soft = scan_for_collisions(expected, table_lister=lister)
    assert hard == [] and soft == []


def test_scan_order_is_stable() -> None:
    """Evidence reproducibility — output sorted lexicographically."""
    expected = ["rfoo", "rbar", "rbaz"]
    lister = lambda: {
        ("public", "rfoo"),
        ("public", "rbaz"),
        ("reference", "rbar"),
    }
    hard, _soft = scan_for_collisions(expected, table_lister=lister)
    assert hard == [
        ("public", "rbaz"),
        ("public", "rfoo"),
        ("reference", "rbar"),
    ]


# ---------------------------------------------------------------------------
# format_evidence
# ---------------------------------------------------------------------------


def test_evidence_clean_state_documents_proceed() -> None:
    body = format_evidence(["rfoo", "rbar"], hard=[], soft=[])
    assert "Expected B9 table names: **2**" in body
    assert "Hard collisions:         **0**" in body
    assert "No collisions found" in body
    assert "B9.B clear to proceed" in body


def test_evidence_hard_section_appears_only_with_hard_collisions() -> None:
    body = format_evidence(
        ["rfoo"], hard=[("reference", "rfoo")], soft=[]
    )
    assert "## Hard collisions" in body
    assert "## Soft collisions" not in body
    assert "`reference`" in body
    assert "`rfoo`" in body


def test_evidence_soft_section_appears_only_with_soft_collisions() -> None:
    body = format_evidence(
        ["rnp3_ndc_price"], hard=[], soft=[("drug_database", "rnp3_ndc_price")]
    )
    assert "## Soft collisions" in body
    assert "## Hard collisions" not in body
    assert "alembic_version" in body
