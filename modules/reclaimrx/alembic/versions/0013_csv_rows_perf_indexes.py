"""Add performance indexes to reclaimrx.csv_upload_rows.

Problem (profiled 2026-06-01):
  - All rule queries filter by (detection_run_id, tenant_id) but the table
    only has single-column indexes on each.  Every rule query does a parallel
    Seq Scan (cost ~674K) over 2.6M rows.
  - ALL-001 / MFR-002 / TH-002 / TH-005 / ALL-005 extract JSONB keys
    (patient_unique_hash, prescriber_npi) with no expression indexes.
  - MFR-004 / HP-005 / ALL-006 aggregate on (row_data->>'pharmacy_npi')
    and (row_data->>'prescriber_npi') with no index support.

Fixes (only indexes confirmed useful by EXPLAIN on the rule queries):
  1. Composite (detection_run_id, tenant_id) BTREE -- primary run+tenant filter.
  2. Expression BTREE on ((row_data->>'patient_unique_hash')) scoped to
     (detection_run_id, tenant_id) -- used by ALL-001, ALL-005 GROUP BY.
  3. Expression BTREE on ((row_data->>'prescriber_npi')) scoped to
     (detection_run_id, tenant_id) -- used by TH-002, TH-005, HP-005.
  4. Expression BTREE on ((row_data->>'pharmacy_npi')) scoped to
     (detection_run_id, tenant_id) -- used by MFR-004, ALL-006, TH-005.
  5. Expression BTREE on ((row_data->>'date_of_service')) scoped to
     (detection_run_id, tenant_id) -- used by ALL-001 (DOS dedup), ALL-005 LAG.
  6. Expression BTREE on ((row_data->>'rx_number_hash')) scoped to
     (detection_run_id, tenant_id) -- used by REJECT-75-70 group key.

All CONCURRENTLY to avoid locking the table.
Idempotent: IF NOT EXISTS on each.

revision: 0013_csv_rows_perf_indexes
down_revision: 0012_drop_evallog_anomaly_ck
"""
from alembic import op

revision = "0013_csv_rows_perf_indexes"
down_revision = "0012_drop_evallog_anomaly_ck"
branch_labels = None
depends_on = None

_SCHEMA = "reclaimrx"
_TABLE = "csv_upload_rows"


def upgrade() -> None:
    # 1. Composite run+tenant -- eliminates parallel seq-scan for all rule queries.
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS"
        " ix_reclaimrx_csv_rows_run_tenant"
        " ON reclaimrx.csv_upload_rows (detection_run_id, tenant_id)"
    )
    # 2. patient_unique_hash expression index (ALL-001 dedup, ALL-005 refill).
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS"
        " ix_reclaimrx_csv_rows_patient_hash"
        " ON reclaimrx.csv_upload_rows"
        " (detection_run_id, tenant_id, (row_data->>'patient_unique_hash'))"
        " WHERE row_data->>'patient_unique_hash' IS NOT NULL"
    )
    # 3. prescriber_npi expression index (TH-002, TH-005, HP-005).
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS"
        " ix_reclaimrx_csv_rows_presc_npi"
        " ON reclaimrx.csv_upload_rows"
        " (detection_run_id, tenant_id, (row_data->>'prescriber_npi'))"
        " WHERE row_data->>'prescriber_npi' IS NOT NULL"
    )
    # 4. pharmacy_npi expression index (MFR-004, ALL-006, TH-005 pair counts).
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS"
        " ix_reclaimrx_csv_rows_pharm_npi"
        " ON reclaimrx.csv_upload_rows"
        " (detection_run_id, tenant_id, (row_data->>'pharmacy_npi'))"
        " WHERE row_data->>'pharmacy_npi' IS NOT NULL"
    )
    # 5. date_of_service expression index (ALL-001 DOS grouping, ALL-005 LAG).
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS"
        " ix_reclaimrx_csv_rows_dos"
        " ON reclaimrx.csv_upload_rows"
        " (detection_run_id, tenant_id, (row_data->>'date_of_service'))"
        " WHERE row_data->>'date_of_service' IS NOT NULL"
    )
    # 6. rx_number_hash expression index (REJECT-75-70 group key).
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS"
        " ix_reclaimrx_csv_rows_rx_hash"
        " ON reclaimrx.csv_upload_rows"
        " (detection_run_id, tenant_id, (row_data->>'rx_number_hash'))"
        " WHERE row_data->>'rx_number_hash' IS NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX CONCURRENTLY IF EXISTS reclaimrx.ix_reclaimrx_csv_rows_rx_hash"
    )
    op.execute(
        "DROP INDEX CONCURRENTLY IF EXISTS reclaimrx.ix_reclaimrx_csv_rows_dos"
    )
    op.execute(
        "DROP INDEX CONCURRENTLY IF EXISTS reclaimrx.ix_reclaimrx_csv_rows_pharm_npi"
    )
    op.execute(
        "DROP INDEX CONCURRENTLY IF EXISTS reclaimrx.ix_reclaimrx_csv_rows_presc_npi"
    )
    op.execute(
        "DROP INDEX CONCURRENTLY IF EXISTS reclaimrx.ix_reclaimrx_csv_rows_patient_hash"
    )
    op.execute(
        "DROP INDEX CONCURRENTLY IF EXISTS reclaimrx.ix_reclaimrx_csv_rows_run_tenant"
    )