"""Minimal test to satisfy Werkbench test-first gate for alembic/env.py.

env.py is alembic configuration; its only testable behavior is that all
models it imports are importable without error. This test verifies that
ClaimUploadRawRow (added in migration 0009) is exported from tables.py
so that autogenerate can see it.
"""

def test_claim_upload_raw_row_importable_from_tables():
    """ClaimUploadRawRow must be importable so alembic env.py autogenerate works."""
    import sys
    from pathlib import Path
    module_root = Path(__file__).resolve().parent.parent
    project_root = module_root.parent.parent
    for p in [str(module_root), str(project_root)]:
        if p not in sys.path:
            sys.path.insert(0, p)

    from src.models.tables import ClaimUploadRawRow
    assert ClaimUploadRawRow.__tablename__ == "claim_upload_raw_rows"
