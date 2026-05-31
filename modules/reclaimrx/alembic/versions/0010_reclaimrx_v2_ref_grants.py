"""Verify FDW reference schema access for reclaimrx detection rules.

Reference data (dataq_master, prescribers, fdb_ndc_price_history, etc.) lives in a
separate database `infinityrx_reference`, exposed into infinityrx_dev via postgres_fdw
as a LOCAL schema called `reference`. The FDW server `infinityrx_reference_srv` and the
`reference` foreign-table schema are provisioned by infrastructure/scripts/setup_fdw.sh
(already run on dev). The user mapping ifx_dev_app -> ifx_ref_reader is established by
that script; NO module-owned grants are needed or created here.

This migration is a no-op / idempotent verification. It does NOT:
  - CREATE any tables or schemas.
  - GRANT SELECT on any native module tables (pharmacy_dir.*, prescriber_dir.*,
    drug_database.*, shared.*).
  - Modify any existing grants or user mappings.

It DOES confirm at run-time that reference.dataq_master is selectable by the current
migration role, raising a clear error if the FDW schema is missing.

World-A chain: revises 0009_detection_run_sha_unique.
World-B 0008_sp3_extensions stays unmerged (do not chain).

Revision ID: 0010_reclaimrx_v2_ref_grants
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_reclaimrx_v2_ref_grants"
down_revision = "0009_detection_run_sha_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Verify that the pre-existing FDW `reference` schema is accessible.

    Runs a LIMIT 0 guard against reference.dataq_master.
    If the FDW schema is missing or the user mapping is not in place, this
    raises a clear error before any Phase 4/5 rule code runs.

    Safe to re-run: pure read, no DDL, no DML.
    """
    bind = op.get_bind()
    try:
        bind.execute(sa.text("SELECT 1 FROM reference.dataq_master LIMIT 0"))
    except Exception as exc:
        raise RuntimeError(
            "Migration 0010 guard failed: reference.dataq_master is not selectable. "
            "Ensure infrastructure/scripts/setup_fdw.sh has been run on this database "
            "and the FDW user mapping (ifx_dev_app -> ifx_ref_reader) is in place. "
            f"Underlying error: {exc}"
        ) from exc


def downgrade() -> None:
    """No-op: nothing was granted, nothing to revoke."""
