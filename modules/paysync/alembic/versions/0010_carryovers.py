"""paysync Wave 39 M3: carryovers.

Tracks money that didn't settle in its origin cycle and needs to
fold into a future cycle:
  - bounced_ach / bounced_check: original payment never reached
    pharmacy; we_owe_pharmacy direction
  - overpayment: pharmacy was paid too much; pharmacy_owes_us
  - underpayment: pharmacy was paid too little; we_owe_pharmacy
  - reversal_post_payment: claim reversal hit after payment;
    pharmacy_owes_us
  - echo_failed_payment: Echo Spec 400 record failed; we_owe_pharmacy
  - manual_adjustment: operator-entered correction (either direction)

Status state machine:
  open → pending_resolution → resolved
  open → written_off

Resolution methods:
  - next_cycle_offset: fold into next cycle's payment batch
  - separate_invoice: bill the pharmacy directly
  - check_reissue: reissue the original payment via check
  - write_off: tenant absorbs the cost (operator decision)

Money: NUMERIC(14,2) > 0 (direction is on a separate column).

Revision ID: 0010_carryovers
Revises: 0009_manual_ap_records
Create Date: 2026-04-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import os

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_carryovers"
down_revision: Union[str, None] = "0009_manual_ap_records"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "paysync"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")


def upgrade() -> None:
    op.create_table(
        "carryovers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("carryover_type", sa.String(40), nullable=False),
        sa.Column("direction", sa.String(24), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "related_claim_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.claims.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "related_payment_batch_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.payment_batches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "related_manual_ap_record_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.manual_ap_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "related_pay_to_entity_id", postgresql.UUID(as_uuid=True),
            nullable=False,  # carryover always belongs to a payee
        ),
        sa.Column(
            "origin_cycle_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.cycles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "resolution_cycle_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.cycles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status", sa.String(24),
            nullable=False, server_default=sa.text("'open'"),
        ),
        sa.Column("resolution_method", sa.String(40), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "carryover_type IN ('bounced_ach', 'bounced_check', "
            "'overpayment', 'underpayment', 'reversal_post_payment', "
            "'echo_failed_payment', 'manual_adjustment')",
            name="ck_paysync_carryover_type",
        ),
        sa.CheckConstraint(
            "direction IN ('we_owe_pharmacy', 'pharmacy_owes_us')",
            name="ck_paysync_carryover_direction",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'pending_resolution', 'resolved', 'written_off')",
            name="ck_paysync_carryover_status",
        ),
        sa.CheckConstraint(
            "resolution_method IS NULL OR resolution_method IN ("
            "'next_cycle_offset', 'separate_invoice', 'check_reissue', "
            "'write_off')",
            name="ck_paysync_carryover_resolution_method",
        ),
        sa.CheckConstraint("amount > 0", name="ck_paysync_carryover_amount_pos"),
        # Status/resolution consistency
        sa.CheckConstraint(
            "(status IN ('resolved', 'written_off')) = (resolved_at IS NOT NULL)",
            name="ck_paysync_carryover_resolved_at_consistent",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_carryover_tenant", "carryovers",
        ["tenant_id", "status"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_carryover_payee", "carryovers",
        ["tenant_id", "related_pay_to_entity_id"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_carryover_origin", "carryovers",
        ["origin_cycle_id"], schema=_SCHEMA,
        postgresql_where=sa.text("origin_cycle_id IS NOT NULL"),
    )
    op.create_index(
        "ix_paysync_carryover_resolution", "carryovers",
        ["resolution_cycle_id"], schema=_SCHEMA,
        postgresql_where=sa.text("resolution_cycle_id IS NOT NULL"),
    )

    # RLS
    op.execute(f"ALTER TABLE {_SCHEMA}.carryovers ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {_SCHEMA}.carryovers FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {_SCHEMA}.carryovers
          FOR ALL
          TO ifx_dev_app, {_APP_ROLE}
          USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
        """
    )
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {_SCHEMA}.carryovers "
        f"TO ifx_dev_app, {_APP_ROLE}, ifx_dev_admin, ifx_prod_admin"
    )


def downgrade() -> None:
    op.drop_table("carryovers", schema=_SCHEMA)
