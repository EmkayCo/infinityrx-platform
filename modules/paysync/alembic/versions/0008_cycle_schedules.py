"""paysync Wave 39 M1: cycle_schedules + decoupled payment/invoice cycles.

Adds:
  - paysync.cycle_schedules — operator-configurable cycle cadence
    (daily / weekly / bi_weekly / semi_monthly / monthly / custom)
    scoped at tenant / client / program / pharmacy_npi /
    pharmacy_state level. Resolution waterfall: state → npi →
    program → client → tenant default.
  - paysync.cycles extended: cycle_type (payment | invoice),
    schedule_id FK, applies_to_scope_type/id, pharmacy_state.
  - paysync.claims extended: payment_cycle_id + invoice_cycle_id
    (decoupled) plus *_resolved_at timestamps.
  - paysync.claims.pharmacy_state varchar(2) (drives schedule
    waterfall).

cadence_config JSONB shapes:
  daily        {"close_time_utc": "HH:MM"}
  weekly       {"close_day_of_week": "FRIDAY", "close_time_utc": "HH:MM"}
  bi_weekly    {"close_day_of_week": "FRIDAY", "anchor_date": "YYYY-MM-DD"}
  semi_monthly {"first_close_day": 15, "second_close_day": -1}
                 -1 = end of month
  monthly      {"close_day_of_month": -1}
  custom       {"period_definition": "..."}  (validation + DSL
                 deferred to a future wave; service-layer raises
                 NotImplementedError for now)

Revision ID: 0008_cycle_schedules
Revises: 0007_export_templates
Create Date: 2026-04-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import os

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_cycle_schedules"
down_revision: Union[str, None] = "0007_export_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "paysync"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")


def upgrade() -> None:
    # ── cycle_schedules ────────────────────────────────────────────
    op.create_table(
        "cycle_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_name", sa.String(100), nullable=False),
        sa.Column("cycle_type", sa.String(16), nullable=False),
        sa.Column("cadence", sa.String(16), nullable=False),
        sa.Column(
            "cadence_config", postgresql.JSONB(),
            nullable=False, server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("applies_to_scope", sa.String(16), nullable=False),
        sa.Column("applies_to_scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("applies_to_pharmacy_state", sa.String(2), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "cycle_type IN ('payment', 'invoice')",
            name="ck_paysync_csched_cycle_type",
        ),
        sa.CheckConstraint(
            "cadence IN ('daily', 'weekly', 'bi_weekly', "
            "'semi_monthly', 'monthly', 'custom')",
            name="ck_paysync_csched_cadence",
        ),
        sa.CheckConstraint(
            "applies_to_scope IN ('tenant', 'client', 'program', "
            "'pharmacy_npi', 'pharmacy_state')",
            name="ck_paysync_csched_scope",
        ),
        sa.CheckConstraint(
            # tenant scope ↔ scope_id IS NULL AND pharmacy_state IS NULL
            "(applies_to_scope = 'tenant') = "
            "(applies_to_scope_id IS NULL AND applies_to_pharmacy_state IS NULL)",
            name="ck_paysync_csched_tenant_no_id",
        ),
        sa.CheckConstraint(
            # pharmacy_state scope ↔ pharmacy_state set, scope_id NULL
            "(applies_to_scope = 'pharmacy_state') = "
            "(applies_to_pharmacy_state IS NOT NULL AND applies_to_scope_id IS NULL)",
            name="ck_paysync_csched_state_consistent",
        ),
        sa.CheckConstraint(
            "applies_to_pharmacy_state IS NULL OR "
            "applies_to_pharmacy_state ~ '^[A-Z]{2}$'",
            name="ck_paysync_csched_state_format",
        ),
        sa.CheckConstraint(
            "termination_date IS NULL OR termination_date >= effective_from",
            name="ck_paysync_csched_period_order",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(cadence_config) = 'object'",
            name="ck_paysync_csched_config_is_object",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_csched_tenant", "cycle_schedules",
        ["tenant_id"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_csched_lookup", "cycle_schedules",
        ["tenant_id", "cycle_type", "applies_to_scope"],
        schema=_SCHEMA,
    )

    # ── cycles extension ──────────────────────────────────────────
    op.add_column(
        "cycles",
        sa.Column(
            "cycle_type", sa.String(16),
            nullable=False, server_default=sa.text("'payment'"),
        ),
        schema=_SCHEMA,
    )
    op.add_column(
        "cycles",
        sa.Column(
            "schedule_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.cycle_schedules.id", ondelete="SET NULL"),
            nullable=True,
        ),
        schema=_SCHEMA,
    )
    op.add_column(
        "cycles",
        sa.Column("applies_to_scope_type", sa.String(16), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        "cycles",
        sa.Column("applies_to_scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        "cycles",
        sa.Column("applies_to_pharmacy_state", sa.String(2), nullable=True),
        schema=_SCHEMA,
    )
    op.create_check_constraint(
        "ck_paysync_cycles_cycle_type",
        "cycles",
        "cycle_type IN ('payment', 'invoice')",
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_cycles_type", "cycles",
        ["tenant_id", "cycle_type", "status"], schema=_SCHEMA,
    )

    # ── claims extension ─────────────────────────────────────────
    op.add_column(
        "claims",
        sa.Column(
            "payment_cycle_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.cycles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        schema=_SCHEMA,
    )
    op.add_column(
        "claims",
        sa.Column(
            "invoice_cycle_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.cycles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        schema=_SCHEMA,
    )
    op.add_column(
        "claims",
        sa.Column("payment_cycle_resolved_at", sa.DateTime(timezone=True), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        "claims",
        sa.Column("invoice_cycle_resolved_at", sa.DateTime(timezone=True), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        "claims",
        sa.Column("pharmacy_state", sa.String(2), nullable=True),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_claims_payment_cycle", "claims",
        ["tenant_id", "payment_cycle_id"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_claims_invoice_cycle", "claims",
        ["tenant_id", "invoice_cycle_id"], schema=_SCHEMA,
    )

    # Backfill: existing cycles get cycle_type='payment' (default
    # already covers it via server_default). Existing claims keep
    # cycle_id (legacy column from Wave 35) and ALSO have
    # payment_cycle_id populated to the same value so the new path
    # finds them. Idempotent UPDATE.
    op.execute(
        f"""
        UPDATE {_SCHEMA}.claims
           SET payment_cycle_id = cycle_id,
               payment_cycle_resolved_at = updated_at
         WHERE cycle_id IS NOT NULL AND payment_cycle_id IS NULL
        """
    )

    # RLS for cycle_schedules
    op.execute(f"ALTER TABLE {_SCHEMA}.cycle_schedules ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {_SCHEMA}.cycle_schedules FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {_SCHEMA}.cycle_schedules
          FOR ALL
          TO ifx_dev_app, {_APP_ROLE}
          USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
        """
    )
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {_SCHEMA}.cycle_schedules "
        f"TO ifx_dev_app, {_APP_ROLE}, ifx_dev_admin, ifx_prod_admin"
    )


def downgrade() -> None:
    op.drop_index("ix_paysync_claims_invoice_cycle", table_name="claims", schema=_SCHEMA)
    op.drop_index("ix_paysync_claims_payment_cycle", table_name="claims", schema=_SCHEMA)
    for col in (
        "pharmacy_state",
        "invoice_cycle_resolved_at",
        "payment_cycle_resolved_at",
        "invoice_cycle_id",
        "payment_cycle_id",
    ):
        op.drop_column("claims", col, schema=_SCHEMA)
    op.drop_index("ix_paysync_cycles_type", table_name="cycles", schema=_SCHEMA)
    op.drop_constraint(
        "ck_paysync_cycles_cycle_type", "cycles", schema=_SCHEMA, type_="check",
    )
    for col in (
        "applies_to_pharmacy_state",
        "applies_to_scope_id",
        "applies_to_scope_type",
        "schedule_id",
        "cycle_type",
    ):
        op.drop_column("cycles", col, schema=_SCHEMA)
    op.drop_table("cycle_schedules", schema=_SCHEMA)
