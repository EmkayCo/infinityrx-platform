"""Grant SELECT on reference tables to ifx_dev_app.

Shared-reference-read exception: reclaimrx may directly read reference tables
owned by other modules (pharmacy_dir, prescriber_dir, shared, drug_database)
because these are read-only, shared reference data. This is documented as the
module-isolation exception per the v2 spec locked decision #3.

DEVIATION from plan spec (2026-05-31): The plan referenced pharmacy_dir.dataq_fwa_markers
but that table was renamed to dataq_fwa_attestation in pharmacy-directory migration
0009_dataq_spec_correction (mas_fwa.txt -> fwa_attestation rename per NCPDP DataQ v3.1 spec).
Grant targets dataq_fwa_attestation instead of dataq_fwa_markers.
PHASE 4 BLOCKER: ALL-002 rule (locked decision #4) references dataq_fwa_markers.audit_npi --
that table and column do not exist; ALL-002 must be re-scoped before Phase 4 proceeds.

World-A chain: revises 0009_detection_run_sha_unique.
World-B 0008_sp3_extensions stays unmerged (do not chain).

Revision ID: 0010_reclaimrx_v2_ref_grants
"""
from alembic import op

revision = "0010_reclaimrx_v2_ref_grants"
down_revision = "0009_detection_run_sha_unique"
branch_labels = None
depends_on = None

_GRANTS = [
    "GRANT SELECT ON pharmacy_dir.dataq_master TO ifx_dev_app",
    # dataq_fwa_markers renamed to dataq_fwa_attestation per pharmacy-directory 0009
    "GRANT SELECT ON pharmacy_dir.dataq_fwa_attestation TO ifx_dev_app",
    "GRANT SELECT ON prescriber_dir.prescribers TO ifx_dev_app",
    "GRANT SELECT ON shared.oig_leie_exclusions TO ifx_dev_app",
    "GRANT SELECT ON shared.sam_exclusions TO ifx_dev_app",
    "GRANT SELECT ON drug_database.fdb_ndc_price_history TO ifx_dev_app",
    "GRANT SELECT ON drug_database.fdb_price_type_desc TO ifx_dev_app",
    "GRANT SELECT ON drug_database.drugs TO ifx_dev_app",
]


def upgrade() -> None:
    for stmt in _GRANTS:
        op.execute(stmt)


def downgrade() -> None:
    for stmt in _GRANTS:
        table = stmt.split(" ON ")[1].split(" TO ")[0]
        op.execute(f"REVOKE SELECT ON {table} FROM ifx_dev_app")
