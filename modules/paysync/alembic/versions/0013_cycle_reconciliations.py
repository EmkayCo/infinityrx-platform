"""paysync Wave 39 M6: cycle_reconciliations.

Captures three-way tie outcomes per cycle:
  Tie 1: Claims batch ↔ Invoice (AR side)
  Tie 2: Claims batch ↔ Total AP (manual + batch + carryover)
  Tie 3: Cycle batch AP ↔ NACHA ↔ 835 sums

$0.01 tolerance per tie. Multiple runs allowed; each insertion
is a new audit row. Operator finalizes via finalized=true with
optional accepted_deltas + notes.

Revision ID: 0013_cycle_reconciliations
Revises: 0012_bank_settlements
Create Date: 2026-04-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import os

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_cycle_reconciliations"
down_revision: Union[str, None] = "0012_bank_settlements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "paysync"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")


def upgrade() -> None:
    op.create_table(
        "cycle_reconciliations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "cycle_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.cycles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("run_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tie_1_status", sa.String(16), nullable=False),
        sa.Column("tie_2_status", sa.String(16), nullable=False),
        sa.Column("tie_3_status", sa.String(16), nullable=False),
        sa.Column("tie_1_expected", sa.Numeric(14, 2), nullable=False),
        sa.Column("tie_1_actual", sa.Numeric(14, 2), nullable=False),
        sa.Column("tie_1_delta", sa.Numeric(14, 2), nullable=False),
        sa.Column("tie_2_expected", sa.Numeric(14, 2), nullable=False),
        sa.Column("tie_2_actual", sa.Numeric(14, 2), nullable=False),
        sa.Column("tie_2_delta", sa.Numeric(14, 2), nullable=False),
        sa.Column("tie_3_batch_ap", sa.Numeric(14, 2), nullable=False),
        sa.Column("tie_3_nacha_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("tie_3_eight_thirty_five_total", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "findings", postgresql.JSONB(),
            nullable=False, server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "finalized", sa.Boolean(),
            nullable=False, server_default=sa.false(),
        ),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operator_notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "tie_1_status IN ('match', 'mismatch')",
            name="ck_paysync_recon_tie1",
        ),
        sa.CheckConstraint(
            "tie_2_status IN ('match', 'mismatch')",
            name="ck_paysync_recon_tie2",
        ),
        sa.CheckConstraint(
            "tie_3_status IN ('match', 'mismatch')",
            name="ck_paysync_recon_tie3",
        ),
        sa.CheckConstraint(
            "finalized = (finalized_at IS NOT NULL)",
            name="ck_paysync_recon_finalized_consistent",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(findings) = 'array'",
            name="ck_paysync_recon_findings_array",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_recon_cycle", "cycle_reconciliations",
        ["cycle_id", "run_at"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_recon_tenant", "cycle_reconciliations",
        ["tenant_id", "run_at"], schema=_SCHEMA,
    )

    op.execute(f"ALTER TABLE {_SCHEMA}.cycle_reconciliations ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {_SCHEMA}.cycle_reconciliations FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {_SCHEMA}.cycle_reconciliations
          FOR ALL
          TO ifx_dev_app, {_APP_ROLE}
          USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
        """
    )
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {_SCHEMA}.cycle_reconciliations "
        f"TO ifx_dev_app, {_APP_ROLE}, ifx_dev_admin, ifx_prod_admin"
    )


def downgrade() -> None:
    op.drop_table("cycle_reconciliations", schema=_SCHEMA)
