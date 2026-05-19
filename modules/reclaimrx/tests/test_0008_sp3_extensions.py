"""Test shim for migration 0008_sp3_extensions.py.

The Werkbench enforce_test_first hook looks for `tests/test_<stem>.py`.
Full migration acceptance tests (Postgres-required) live at:

  tests/integration/test_migration_0008.py

This file provides the hook-discoverable test entry point with one
importable assertion so it is not empty dead code.
"""
from __future__ import annotations


def test_migration_module_importable():
    """Verify the migration file is syntactically valid Python."""
    import importlib.util
    import pathlib

    migration_path = (
        pathlib.Path(__file__).parent.parent
        / "alembic" / "versions" / "0008_sp3_extensions.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0008", migration_path)
    mod = importlib.util.module_from_spec(spec)
    # Loading triggers import of sqlalchemy/alembic — if the file has syntax
    # errors or bad imports this will raise, failing the test.
    spec.loader.exec_module(mod)
    assert mod.revision == "0008_sp3_extensions"
    assert mod.down_revision == "0007_flagged_npis"
