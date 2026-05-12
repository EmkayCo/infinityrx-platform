"""paysync Wave 39 M5: bank_settlements + bank_settlement_entries + bank_file_adapters.

Bank settlement ingest with two paths:
  - Manual operator entry via API
  - SFTP/file ingest via per-tenant adapter config

Bounced entries (returned=True) auto-create paysync.carryovers
rows (we_owe_pharmacy direction) so they fold into the next
cycle.

Revision ID: 0012_bank_settlements
Revises: 0011_cycle_close_runs
Create Date: 2026-04-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import os

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_bank_settlements"
down_revision: Union[str, None] = "0011_cycle_close_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "paysync"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_TABLES = ("bank_settlements", "bank_settlement_entries", "bank_file_adapters")


def upgrade() -> None:
    # ── bank_settlements ─────────────────────────────────────────
    op.create_table(
        "bank_settlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "payment_batch_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.payment_batches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "nacha_file_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.payment_batch_files.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("settlement_date", sa.Date(), nullable=False),
        sa.Column("settled_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("bank_reference", sa.String(255), nullable=False),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("source_file_path", sa.Text(), nullable=True),
        sa.Column("source_file_sha256", sa.String(64), nullable=True),
        sa.Column(
            "status", sa.String(24),
            nullable=False, server_default=sa.text("'received'"),
        ),
        sa.Column("discrepancy_reason", sa.Text(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ingested_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "source IN ('manual_entry', 'sftp_ingest', 'api')",
            name="ck_paysync_bsettle_source",
        ),
        sa.CheckConstraint(
            "status IN ('received', 'reconciled', 'discrepancy')",
            name="ck_paysync_bsettle_status",
        ),
        sa.CheckConstraint(
            "source_file_sha256 IS NULL OR source_file_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_paysync_bsettle_sha256",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_bsettle_tenant_date", "bank_settlements",
        ["tenant_id", "settlement_date"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_bsettle_batch", "bank_settlements",
        ["payment_batch_id"], schema=_SCHEMA,
        postgresql_where=sa.text("payment_batch_id IS NOT NULL"),
    )

    # ── bank_settlement_entries ──────────────────────────────────
    op.create_table(
        "bank_settlement_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "bank_settlement_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.bank_settlements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "payment_batch_credit_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.payment_batch_credits.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("bank_trace_number", sa.String(50), nullable=False),
        sa.Column("settled_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("returned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("return_reason_code", sa.String(10), nullable=True),
        sa.Column("return_reason_description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "(NOT returned) OR return_reason_code IS NOT NULL",
            name="ck_paysync_bse_returned_has_code",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_bse_settle", "bank_settlement_entries",
        ["bank_settlement_id"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_bse_credit", "bank_settlement_entries",
        ["payment_batch_credit_id"], schema=_SCHEMA,
        postgresql_where=sa.text("payment_batch_credit_id IS NOT NULL"),
    )
    op.create_index(
        "ix_paysync_bse_trace", "bank_settlement_entries",
        ["tenant_id", "bank_trace_number"], schema=_SCHEMA,
    )

    # ── bank_file_adapters ───────────────────────────────────────
    op.create_table(
        "bank_file_adapters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("adapter_name", sa.String(100), nullable=False),
        sa.Column("file_format", sa.String(24), nullable=False),
        sa.Column(
            "column_mapping", postgresql.JSONB(),
            nullable=False, server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "sftp_config", postgresql.JSONB(),
            nullable=False, server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "active", sa.Boolean(),
            nullable=False, server_default=sa.true(),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "adapter_name", name="uq_paysync_adapter_name"),
        sa.CheckConstraint(
            "file_format IN ('nacha_return', 'csv_custom', 'fixed_width_custom')",
            name="ck_paysync_adapter_format",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_adapter_tenant", "bank_file_adapters",
        ["tenant_id"], schema=_SCHEMA,
    )

    # RLS
    for tbl in _TABLES:
        op.execute(f"ALTER TABLE {_SCHEMA}.{tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {_SCHEMA}.{tbl} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {_SCHEMA}.{tbl}
              FOR ALL
              TO ifx_dev_app, {_APP_ROLE}
              USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
              WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
            """
        )
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON "
        + ", ".join(f"{_SCHEMA}.{t}" for t in _TABLES)
        + f" TO ifx_dev_app, {_APP_ROLE}, ifx_dev_admin, ifx_prod_admin"
    )


def downgrade() -> None:
    for t in reversed(_TABLES):
        op.drop_table(t, schema=_SCHEMA)
