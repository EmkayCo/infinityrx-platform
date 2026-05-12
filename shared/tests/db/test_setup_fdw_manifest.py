"""B9.A C11 — Tests for `setup_fdw.sh --verify` manifest invariants.

The bulk of `setup_fdw.sh` requires a live Postgres + FDW
configuration; those are integration tests. The pure manifest
invariants (file present, well-formed, count >= floor, lines parse
into schema|table tuples) are covered here without Postgres.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3]
_MANIFEST = _REPO_ROOT / "infrastructure" / "scripts" / "lib" / "expected_reference_tables.txt"
_SETUP_FDW = _REPO_ROOT / "infrastructure" / "scripts" / "setup_fdw.sh"


def _parse_manifest_lines() -> list[tuple[str, str]]:
    """Same logic as the awk pass in setup_fdw.sh --verify."""
    out: list[tuple[str, str]] = []
    text = _MANIFEST.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.rstrip("\r").strip()
        if not line or line.startswith("#"):
            continue
        if "|" not in line:
            continue
        # The manifest tolerates inline `# comment` after the table column
        # — strip it before splitting (some entries use `... # source`).
        # Match setup_fdw.sh treatment: take the FIRST `|`-split fields only.
        body = line.split("#", 1)[0].strip()
        if not body:
            continue
        parts = body.split("|", 1)
        if len(parts) != 2:
            continue
        schema, table = parts[0].strip(), parts[1].strip()
        if schema and table:
            out.append((schema, table))
    return out


# ---------------------------------------------------------------------------
# Manifest invariants (B9.A C11)
# ---------------------------------------------------------------------------


def test_manifest_file_exists() -> None:
    assert _MANIFEST.exists(), f"manifest missing at {_MANIFEST}"


def test_manifest_has_at_least_floor_entries() -> None:
    """B9.A C11 floor: 66 (B7 baseline). B9.B-G grows it; never shrinks."""
    entries = _parse_manifest_lines()
    assert len(entries) >= 66, (
        f"manifest has {len(entries)} entries; below B7 baseline floor of 66"
    )


def test_manifest_entries_have_schema_and_table() -> None:
    """Every line that survives the comment/blank filter is `schema|table`."""
    entries = _parse_manifest_lines()
    for schema, table in entries:
        assert schema and table, (
            f"empty schema or table in manifest: ({schema!r}, {table!r})"
        )


def test_manifest_schema_names_are_well_formed() -> None:
    """Schemas are lower-snake_case identifiers — no spaces, dots, hyphens."""
    pattern = re.compile(r"\A[a-z][a-z0-9_]*\Z")
    for schema, _table in _parse_manifest_lines():
        assert pattern.match(schema), (
            f"manifest schema {schema!r} is not a lower-snake_case identifier"
        )


def test_manifest_table_names_are_well_formed() -> None:
    """Tables follow the same naming rules."""
    pattern = re.compile(r"\A[a-z][a-z0-9_]*\Z")
    for _schema, table in _parse_manifest_lines():
        assert pattern.match(table), (
            f"manifest table {table!r} is not a lower-snake_case identifier"
        )


def test_manifest_has_no_duplicate_entries() -> None:
    """Duplicates would inflate the verify count and hide failures."""
    entries = _parse_manifest_lines()
    seen: set[tuple[str, str]] = set()
    dupes: list[tuple[str, str]] = []
    for entry in entries:
        if entry in seen:
            dupes.append(entry)
        seen.add(entry)
    assert not dupes, f"manifest contains duplicate entries: {dupes}"


# ---------------------------------------------------------------------------
# setup_fdw.sh invariants
# ---------------------------------------------------------------------------


def test_setup_fdw_no_hardcoded_expected_66_check() -> None:
    """C11 contract: the hard-coded `-ne 66` count assertion is gone."""
    body = _SETUP_FDW.read_text(encoding="utf-8")
    # Hard-coded equality check would look like: -ne 66
    # The C11 replacement uses -lt $MIN_MANIFEST_COUNT.
    assert "-ne 66" not in body, (
        "setup_fdw.sh still contains hard-coded `-ne 66` count assertion. "
        "Replace with MIN_MANIFEST_COUNT floor (C11)."
    )


def test_setup_fdw_uses_min_manifest_count_floor() -> None:
    """C11 contract: MIN_MANIFEST_COUNT variable is in use."""
    body = _SETUP_FDW.read_text(encoding="utf-8")
    assert "MIN_MANIFEST_COUNT=" in body
    assert "$MANIFEST_COUNT" in body and "MIN_MANIFEST_COUNT" in body


def test_setup_fdw_applies_deterministic_sort() -> None:
    """C11 contract: MANIFEST_SORTED is built and used as the iteration source."""
    body = _SETUP_FDW.read_text(encoding="utf-8")
    assert "MANIFEST_SORTED" in body
    # The sort pipeline appears once in the build step
    assert "| sort" in body
    # The iteration consumes the sorted view via heredoc, not the raw file
    assert '<<< "$MANIFEST_SORTED"' in body
