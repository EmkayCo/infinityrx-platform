"""paysync Wave 39 M4: cycle_close_runs.

Tracks the orchestrated cycle-close pipeline (preflight → holds →
manual AP recognition → carryover ingestion → batch generation →
NACHA → 835 → invoice generation → reconciliation → finalization).
Per-step status in JSONB so resume-from-failure can identify the
last successful step.

Revision ID: 0011_cycle_close_runs
Revises: 0010_carryovers
Create Date: 2026-04-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import os

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_cycle_close_runs"
down_revision: Union[str, None] = "0010_carryovers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "paysync"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")


def upgrade() -> None:
    op.create_table(
        "cycle_close_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "cycle_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.cycles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("triggered_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status", sa.String(24),
            nullable=False, server_default=sa.text("'in_progress'"),
        ),
        sa.Column(
            "step_status", postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("failure_step", sa.String(50), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("rollback_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invoice_cycle_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed', 'failed', 'rolled_back')",
            name="ck_paysync_close_run_status",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(step_status) = 'object'",
            name="ck_paysync_close_run_step_status_obj",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_close_run_cycle", "cycle_close_runs",
        ["cycle_id", "triggered_at"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_close_run_tenant_status", "cycle_close_runs",
        ["tenant_id", "status"], schema=_SCHEMA,
    )

    op.execute(f"ALTER TABLE {_SCHEMA}.cycle_close_runs ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {_SCHEMA}.cycle_close_runs FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {_SCHEMA}.cycle_close_runs
          FOR ALL
          TO ifx_dev_app, {_APP_ROLE}
          USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
        """
    )
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {_SCHEMA}.cycle_close_runs "
        f"TO ifx_dev_app, {_APP_ROLE}, ifx_dev_admin, ifx_prod_admin"
    )


def downgrade() -> None:
    op.drop_table("cycle_close_runs", schema=_SCHEMA)
