"""Test that ifx_dev_app role can SELECT from all 8 reference tables after migration 0010.

DEVIATION from plan spec (2026-05-31): The plan referenced pharmacy_dir.dataq_fwa_markers
but that table was renamed to dataq_fwa_attestation in pharmacy-directory migration
0009_dataq_spec_correction (mas_fwa.txt → fwa_attestation rename per NCPDP DataQ v3.1 spec).
The grant and this test target dataq_fwa_attestation instead.
PHASE 4 BLOCKER: ALL-002 rule (locked decision #4) references dataq_fwa_markers.audit_npi —
that table and column do not exist; ALL-002 must be re-scoped to dataq_fwa_attestation schema
before Phase 4 can proceed.
"""
import os
import pytest
import sqlalchemy as sa

REAL_DB = os.environ.get("RECLAIMRX_DB_URL", "")

@pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with ifx_dev_app role")
def test_reference_grants_all_tables():
    """Each reference table must be SELECTable by ifx_dev_app after 0010."""
    engine = sa.create_engine(REAL_DB)
    expected = [
        ("pharmacy_dir", "dataq_master"),
        # dataq_fwa_markers was renamed dataq_fwa_attestation in pharmacy-directory 0009;
        # plan spec updated here — PHASE 4 BLOCKER: ALL-002 NPI column must be re-mapped.
        ("pharmacy_dir", "dataq_fwa_attestation"),
        ("prescriber_dir", "prescribers"),
        ("shared", "oig_leie_exclusions"),
        ("shared", "sam_exclusions"),
        ("drug_database", "fdb_ndc_price_history"),
        ("drug_database", "fdb_price_type_desc"),
        ("drug_database", "drugs"),
    ]
    with engine.connect() as conn:
        for schema, table in expected:
            result = conn.execute(
                sa.text(f"SELECT 1 FROM {schema}.{table} LIMIT 1")
            )
            # Just fetching without PermissionError is the assertion
            result.close()
