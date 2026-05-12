"""RLS policies for payment-processing tenant-scoped tables (Wave 20 B3).

Enables Row-Level Security on 6 payment_proc base tables. All have
NOT NULL tenant_id → canonical single-policy shape applies uniformly.

NOTE — tenant_id is VARCHAR(36), not UUID. Unlike ai-nlp/billing/core,
payment-processing's models declare ``Mapped[str] = mapped_column(String(36))``
for tenant_id (a pre-existing design choice). The RLS policy compares
tenant_id as text — no ``::uuid`` cast. The NULLIF wrap is still
mandatory because an unset GUC returns the empty string and we need
fail-closed behaviour. scripts/apply_rls.py auto-detects the column
type and emits the right comparison.

CANONICAL (6 tables):
  payment_proc_ofac_alerts, payment_proc_payee_enrollments,
  payment_proc_settlements, payment_proc_submissions,
  payment_proc_vendor_adapters, payment_proc_vendor_health_log

OUT_OF_SCOPE (3 tables, shared reference data):
  alembic_version, payment_proc_ach_return_codes (NACHA return codes),
  payment_proc_ofac_sdn (OFAC SDN sanctions list).

Two hard-won rules from Wave 20 B2 are non-negotiable and encoded:
  1. FORCE ROW LEVEL SECURITY alongside ENABLE (tenant role is owner).
  2. NULLIF-wrapped current_setting to survive empty-string GUC.

Generated from ``scripts/apply_rls.py``. To regenerate:
    python scripts/apply_rls.py --schema payment_proc

Revision ID: 0002_rls_tenant_isolation
Revises: 0001_payment_processing_baseline
Create Date: 2026-04-18
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002_rls_tenant_isolation"
down_revision: Union[str, None] = "0001_payment_processing_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "payment_proc"
import os
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_TENANT_ROLES = f"ifx_dev_app, ifx_mock_app, {_APP_ROLE}"

_CANONICAL_TABLES: list[str] = [
    "payment_proc_ofac_alerts",
    "payment_proc_payee_enrollments",
    "payment_proc_settlements",
    "payment_proc_submissions",
    "payment_proc_vendor_adapters",
    "payment_proc_vendor_health_log",
]


def upgrade() -> None:
    for table in _CANONICAL_TABLES:
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {_SCHEMA}.{table}
              FOR ALL
              TO {_TENANT_ROLES}
              USING      (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), ''))
              WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), ''))
            """
        )


def downgrade() -> None:
    for table in reversed(_CANONICAL_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {_SCHEMA}.{table}")
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} DISABLE ROW LEVEL SECURITY")
