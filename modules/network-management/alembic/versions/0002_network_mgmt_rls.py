"""network_mgmt RLS tenant isolation.

FORCE ROW LEVEL SECURITY + NULLIF-wrapped tenant predicate on all
8 tables. banking_change_log is the audit log — also tenant-scoped
RLS but never UPDATE'd or DELETE'd by application code (append-only
via INSERT only; this enforces nothing structurally but keeps the
audit story clean).

Revision ID: 0002_network_mgmt_rls
Revises: 0001_network_mgmt_baseline
Create Date: 2026-04-25
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002_network_mgmt_rls"
down_revision: Union[str, None] = "0001_network_mgmt_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "network_mgmt"
_TABLES = (
    "banking",
    "banking_change_log",
    "chain_membership",
    "contracts",
    "eight_thirty_five_destinations",
    "pay_center_routing",
    "pay_to_entities",
    "statement_account_flags",
)
import os
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_ROLES = f"ifx_dev_app, {_APP_ROLE}"
_PREDICATE = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
)


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
