"""B9.A C13 — Lock-in test for the drug-database declarative base.

Captures the Phase 09 baseline (9 tables on DrugBase.metadata). B9.B's
first commit that pushes this beyond the threshold is the trigger to
refactor into tier-scoped bases per
`waves/B9/module_base_profile.md`.

The test is intentionally an EQUALITY assertion, not a `>=` floor:
the WHOLE POINT is to detect when a new tier silently piles onto
DrugBase and to force a refactor decision in the same commit.
"""
from __future__ import annotations

# Phase 09 baseline. When B9.B-G land FDB models, this number changes:
#   * EXPECTED outcome: stays at 9; new tier models live on a separate
#     FDBBase declarative base. The shared MetaData is what alembic
#     sees (per waves/B9/module_base_profile.md "Recommended pattern").
#   * UNEXPECTED outcome: number > 9 means a new tier piled onto
#     DrugBase. The test fails; the operator must either (a) split into
#     a sub-base (the documented pattern) or (b) consciously bump this
#     baseline if the new tables genuinely belong on DrugBase.
PHASE_09_DRUGBASE_TABLE_COUNT = 9


def test_drugbase_table_count_matches_phase_09_baseline() -> None:
    """Detects accidental B9 model attachment to DrugBase."""
    from drug_database.models.tables import DrugBase

    actual = len(DrugBase.metadata.tables)
    assert actual == PHASE_09_DRUGBASE_TABLE_COUNT, (
        f"DrugBase.metadata.tables has {actual} entries; baseline is "
        f"{PHASE_09_DRUGBASE_TABLE_COUNT}. If a B9.B-G commit added "
        f"models, route them to a tier-scoped FDBBase (see "
        f"waves/B9/module_base_profile.md). If the increase is "
        f"intentional, bump PHASE_09_DRUGBASE_TABLE_COUNT in this file "
        f"in the same commit with a rationale in the message."
    )


def test_drugbase_imports_without_circular_errors() -> None:
    """Regression detector for sub-base pattern landing.

    Once the tier-scoped FDBBase lands, this test catches the
    classic circular-import bug where `fdb.__init__` tries to import
    `tables.DrugBase` and `tables` tries to import `fdb.fdb_metadata`.
    A clean import here proves the import graph is acyclic.
    """
    import importlib

    # Force a fresh import to surface any side-effect ordering bugs.
    import drug_database.models.tables as tables_mod
    importlib.reload(tables_mod)
    assert hasattr(tables_mod, "DrugBase"), (
        "drug_database.models.tables no longer exports DrugBase — "
        "this is an unannounced breaking change."
    )


def test_drugbase_metadata_schema_is_drug_database() -> None:
    """S8 schema-drift fix — DrugBase tables must use drug_database schema.

    After S8 (F-006 schema name drift fix), DrugBase.SCHEMA was corrected
    from 'drug_db' to 'drug_database' to match the alembic-managed schema.
    This test pins that all DrugBase tables resolve to drug_database.
    """
    from drug_database.models.tables import DrugBase

    schemas = {tbl.schema for tbl in DrugBase.metadata.tables.values()}
    # After S8, all DrugBase tables must be in drug_database (the canonical
    # alembic-managed schema). drug_db must no longer appear.
    assert schemas <= {"drug_database"}, (
        f"DrugBase tables span unexpected schemas: {sorted(schemas)}; "
        f"expected only {{'drug_database'}} after S8 schema-drift fix."
    )
