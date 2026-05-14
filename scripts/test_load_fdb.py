"""CLI-contract tests for scripts/load_fdb.py.

Regression guard for B12 codex P1: commit b561900 removed 'fdb_tier_a'
from the --mode choices, which made `--mode fdb_tier_a` (a documented
B9.B-G runbook invocation, exercised by 7 test_fdb_tier_a_batch_*.py
suites) fail at argparse before any loader code could run. The script
had zero test coverage, so the regression was invisible until codex
review. This suite locks the --mode contract.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# load_fdb.py lives in scripts/ and is run as a standalone script; add it
# to sys.path so `import load_fdb` resolves the same way the script's own
# bootstrap does.
sys.path.insert(0, str(Path(__file__).parent))

import load_fdb  # noqa: E402

EXPECTED_MODES = {"fdb_initial", "fdb_weekly", "fdb_rebase", "fdb_tier_a"}


def test_build_parser_accepts_all_documented_modes() -> None:
    """All four ingestion modes must be valid --mode choices.

    fdb_tier_a is the one b561900 dropped; the other three are Phase 09
    pricing modes. If this set drifts, a runbook invocation breaks.
    """
    parser = load_fdb._build_parser()
    mode_action = next(a for a in parser._actions if a.dest == "mode")
    assert set(mode_action.choices) == EXPECTED_MODES


@pytest.mark.parametrize("mode", sorted(EXPECTED_MODES))
def test_build_parser_parses_each_mode(mode: str) -> None:
    """Each documented mode parses without argparse rejecting it."""
    parser = load_fdb._build_parser()
    ns = parser.parse_args(["--mode", mode])
    assert ns.mode == mode


def test_build_parser_rejects_unknown_mode() -> None:
    """An undocumented mode is rejected by argparse (SystemExit 2)."""
    parser = load_fdb._build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--mode", "fdb_bogus"])


def test_build_parser_keeps_require_reference_db_flag() -> None:
    """The B9.A C9 strict-mode flag survives alongside the restored mode.

    This is the half of b561900 that was legitimate — the fix-forward
    keeps it while restoring fdb_tier_a.
    """
    parser = load_fdb._build_parser()
    ns = parser.parse_args(["--mode", "fdb_tier_a", "--require-reference-db"])
    assert ns.require_reference_db is True


def test_mode_help_documents_fdb_tier_a() -> None:
    """The --mode help text must document fdb_tier_a.

    b561900 stripped the descriptive help down to 'ingestion mode
    (SPEC 4.7)', which hid the mode's existence and its loader_group
    semantics from any operator reading --help. The fix-forward
    restores the full help string.
    """
    parser = load_fdb._build_parser()
    mode_action = next(a for a in parser._actions if a.dest == "mode")
    help_text = mode_action.help or ""
    assert "fdb_tier_a" in help_text
    assert "loader_group" in help_text


def test_load_fdb_exposes_main_and_build_parser() -> None:
    """Both the CLI entry point and the extracted parser builder remain
    importable — guards against an accidental rename breaking the
    `if __name__ == '__main__'` dispatch or the test seam."""
    assert callable(load_fdb.main)
    assert callable(load_fdb._build_parser)
