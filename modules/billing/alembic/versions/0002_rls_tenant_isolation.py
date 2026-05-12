"""RLS policies for billing tenant-scoped tables (Wave 20 B3).

Enables Row-Level Security on all 25 billing base tables (every table
except alembic_version). Every table has a NOT NULL tenant_id column, so
they all receive the canonical single-policy shape:

    CREATE POLICY tenant_isolation ON billing.<table>
      FOR ALL TO <tenant roles>
      USING      (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
      WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)

The two hard-won rules from Wave 20 B2 are non-negotiable and encoded:

1. ``FORCE ROW LEVEL SECURITY`` alongside ``ENABLE`` — ``ifx_<tier>_app``
   owns these tables (per ``infrastructure/scripts/init-multi-db.sql``)
   and PG bypasses RLS for the owner by default. FORCE removes that
   exception.

2. ``NULLIF(current_setting('app.current_tenant_id', true), '')::uuid`` —
   unset GUCs return the empty string (not NULL); ``''::uuid`` raises
   ``InvalidTextRepresentation``. The NULLIF wrap makes the comparison
   safely return NULL → UNKNOWN → zero-row match (fail-closed).

Generated from ``scripts/apply_rls.py`` (Wave 20 B3). To regenerate:
    python scripts/apply_rls.py --schema billing
and confirm the emitted SQL matches this migration.

Revision ID: 0002_rls_tenant_isolation
Revises: 0001_billing_baseline
Create Date: 2026-04-18
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002_rls_tenant_isolation"
down_revision: Union[str, None] = "0001_billing_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "billing"
import os
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_TENANT_ROLES = f"ifx_dev_app, ifx_mock_app, {_APP_ROLE}"

# All 25 billing tenant-scoped base tables. Every one has NOT NULL
# tenant_id → canonical shape applies uniformly.
_CANONICAL_TABLES: list[str] = [
    "accounting_configs",
    "ap_records",
    "ar_payments",
    "ar_records",
    "bank_accounts",
    "claim_records",
    "fee_configs",
    "file_format_mappings",
    "funding_configs",
    "invoice_line_items",
    "invoices",
    "invoicing_configs",
    "journal_entries",
    "payment_batches",
    "payment_vendor_configs",
    "payments",
    "payto_waterfall",
    "prefund_ledger",
    "program_budget_alerts",
    "program_budget_snapshots",
    "program_budgets",
    "remittance_configs",
    "routing_rules",
    "sequences",
    "sftp_configs",
]


def upgrade() -> None:
    for table in _CANONICAL_TABLES:
        op.execute(
            f"ALTER TABLE {_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY"
        )
        op.execute(
            f"ALTER TABLE {_SCHEMA}.{table} FORCE ROW LEVEL SECURITY"
        )
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {_SCHEMA}.{table}
              FOR ALL
              TO {_TENANT_ROLES}
              USING      (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
              WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
            """
        )


def downgrade() -> None:
    for table in reversed(_CANONICAL_TABLES):
        op.execute(
            f"DROP POLICY IF EXISTS tenant_isolation ON {_SCHEMA}.{table}"
        )
        op.execute(
            f"ALTER TABLE {_SCHEMA}.{table} DISABLE ROW LEVEL SECURITY"
        )
