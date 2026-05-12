"""reclaimrx RLS tenant isolation.

Applies row-level security policies to all 8 reclaimrx baseline tables
per the Wave 20 B2 / platform RLS pattern. Every reclaimrx table is
tenant-scoped — no global-catalog tables here.

Pattern: FORCE ROW LEVEL SECURITY + NULLIF-wrapped tenant predicate
so an unset GUC (empty string) fails closed instead of casting to
'' which would otherwise blow up.

Revision ID: 0002_reclaimrx_rls
Revises: 0001_reclaimrx_baseline
Create Date: 2026-04-26
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002_reclaimrx_rls"
down_revision: Union[str, None] = "0001_reclaimrx_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "reclaimrx"
_TABLES = (
    "anomalies",
    "anomaly_audit_log",
    "case_anomaly_links",
    "case_assignments",
    "case_number_sequences",
    "csv_upload_rows",
    "detection_runs",
    "recoup_cases",
)
import os
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_ROLES = f"ifx_dev_app, {_APP_ROLE}"
_PREDICATE = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {_SCHEMA}.{table}
              FOR ALL
              TO {_ROLES}
              USING      ({_PREDICATE})
              WITH CHECK ({_PREDICATE});
            """
        )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {_SCHEMA}.{table};")
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} DISABLE ROW LEVEL SECURITY;")
