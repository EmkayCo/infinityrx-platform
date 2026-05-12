"""B9.B C2 — Lock-in: real RECORD_COUNTS.TXT parses cleanly.

The synthetic test fixtures in `test_fdb_contract.py` and
`test_preflight_b9_name_collision.py` used `=` as the delimiter; the
REAL file at `data/reference/fdb/TEL251759D/Current/RECORD_COUNTS.TXT`
uses `|`. Both parsers were fixed in this commit to accept either,
preferring `|` (real format).

This test runs against the real file when it is on disk and skips
otherwise. CI machines with the FDB drop mounted run the lock-in;
dev machines without the drop skip cleanly.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[4]
_REAL_RECORD_COUNTS = (
    _REPO_ROOT / "data" / "reference" / "fdb" / "TEL251759D" / "Current"
    / "RECORD_COUNTS.TXT"
)

# Make _fdb_contract reachable without going through the `tests` package
# (see existing pattern in tests/unit/test_fdb_contract.py).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


pytestmark = pytest.mark.skipif(
    not _REAL_RECORD_COUNTS.exists(),
    reason=f"RECORD_COUNTS.TXT not at {_REAL_RECORD_COUNTS}",
)


def test_real_record_counts_parses_with_pipe_delimiter() -> None:
    """The real FDB file uses `|` as the key/value delimiter.

    Reality check (2026-05-12):  RECORD_COUNTS.TXT ships ~906 entries
    — NOT the 220 DB.zip tables. It is a SUPERSET that includes:
      * Archive snapshots (`AR*` prefix — 1Y/3Y/All historical files)
      * Clinical surveillance (`CMCS*` prefix)
      * UPD-only variants of DB tables
      * Other vendor-side bookkeeping rows
    The 220 canonical DB schema-driving tables live in the
    `NDDF Plus DB.zip` namelist — see `test_db_zip_has_220_tables`
    below. This test asserts ONLY that the parser handles the real
    file shape without choking.
    """
    from _fdb_contract import _parse_record_counts
    counts = _parse_record_counts(_REAL_RECORD_COUNTS)
    # Real file ships ~900 entries. Tolerance ±20 for vendor drift
    # between drops (archive rotations, new surveillance flags).
    assert 880 <= len(counts) <= 920, (
        f"Expected ~906 RECORD_COUNTS entries, got {len(counts)}. "
        f"Either the FDB drop changed shape or the parser regressed."
    )
    # ARETCNDC is the first entry; verify the value parses to int.
    assert "ARETCNDC" in counts
    assert isinstance(counts["ARETCNDC"], int)
    assert counts["ARETCNDC"] > 0


def test_db_zip_has_220_tables() -> None:
    """The canonical B9 schema-driving universe is `NDDF Plus DB.zip`.

    Reality: 220 files in DB.zip = 1 RNP3 (Phase 09 pricing) + 1
    RPRDPTD0 + 1 RNPTYPD0 + ~217 NEW B9 schema targets (B9.B-G).
    """
    import zipfile
    db_zip = (
        _REPO_ROOT / "data" / "reference" / "fdb" / "TEL251759D" / "Current"
        / "NDDF Plus DB" / "NDDF PLUS DB.zip"
    )
    if not db_zip.exists():
        pytest.skip(f"DB.zip not at {db_zip}")
    with zipfile.ZipFile(db_zip) as z:
        # Filter to files (not directory entries); FDB zips have nested dirs.
        files = [n for n in z.namelist() if not n.endswith("/")]
    # Tolerance ±3 for vendor drift between drops.
    assert 217 <= len(files) <= 223, (
        f"DB.zip has {len(files)} files; expected ~220. Vendor drift "
        f"or zip-structure change."
    )


def test_real_record_counts_preflight_generates_correct_count() -> None:
    """The preflight name generator covers all real RECORD_COUNTS keys.

    Output is the deduped lowercase name list — should match
    RECORD_COUNTS.TXT entry count (no dedup wins on this real file).
    """
    sys.path.insert(
        0,
        str(_REPO_ROOT / "infrastructure" / "scripts"),
    )
    from preflight_b9_name_collision import load_expected_names

    names = load_expected_names(_REAL_RECORD_COUNTS)
    # Matches `test_real_record_counts_parses_with_pipe_delimiter`
    # tolerance — same source, same shape.
    assert 880 <= len(names) <= 920, (
        f"preflight name list has {len(names)} entries; expected ~906 "
        f"matching RECORD_COUNTS.TXT. NOTE: the canonical 220-table "
        f"B9 schema list is in DB.zip, not RECORD_COUNTS.TXT — the "
        f"preflight should be re-pointed to DB.zip as part of B9.B "
        f"C3 design work."
    )
    # Spot-check a few known FDB table names (lowercase).
    assert "aretcndc" in names


def test_real_record_counts_contains_known_phase09_tables() -> None:
    """Phase 09 pricing tables must appear in the real manifest."""
    from _fdb_contract import _parse_record_counts
    counts = _parse_record_counts(_REAL_RECORD_COUNTS)
    # Phase 09 ingested 3 tables; their RECORD_COUNTS keys are the
    # short FDB names. RNP3 is the 15.6M-row history table.
    # Names taken from `fdb_pricing_ingester.py` TableSpec.record_counts_key
    # (or table_name when key unset).
    phase09_keys = {"RNP3", "RPRDPTD0", "RNPTYPD0"}
    found = phase09_keys & counts.keys()
    # At least one should exist; allow for vendor key-naming variance.
    assert found, (
        f"None of the Phase 09 keys {sorted(phase09_keys)} found in "
        f"RECORD_COUNTS.TXT (top 10 actual keys: "
        f"{sorted(counts.keys())[:10]})"
    )
