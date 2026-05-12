"""paysync Wave 38 M1: invoice_sequences + invoice_sequence_change_log.

Per-tenant invoice numbering with two parallel sequence types
(reimbursement + client_fees) and three scope levels (tenant /
program / client). Allocation is atomic via SELECT ... FOR UPDATE
on the sequence row inside a tenant-scoped transaction.

Operator override permits manual jumps when QuickBooks has been
used between cycles (per project memory). Every change logged
append-only to invoice_sequence_change_log.

Revision ID: 0005_invoice_sequences
Revises: 0004_payment_batches
Create Date: 2026-04-25
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import os

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_invoice_sequences"
down_revision: Union[str, None] = "0004_payment_batches"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "paysync"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_TABLES = ("invoice_sequences", "invoice_sequence_change_log")


def upgrade() -> None:
    op.create_table(
        "invoice_sequences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_type", sa.String(32), nullable=False),
        sa.Column("scope_type", sa.String(16), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "next_invoice_number", sa.BigInteger(),
            nullable=False, server_default=sa.text("1"),
        ),
        sa.Column("prefix", sa.String(20), nullable=True),
        sa.Column("number_padding", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "sequence_type IN ('reimbursement', 'client_fees')",
            name="ck_paysync_inv_seq_type",
        ),
        sa.CheckConstraint(
            "scope_type IN ('tenant', 'program', 'client')",
            name="ck_paysync_inv_seq_scope_type",
        ),
        sa.CheckConstraint(
            "(scope_type = 'tenant') = (scope_id IS NULL)",
            name="ck_paysync_inv_seq_scope_id_consistent",
        ),
        sa.CheckConstraint(
            "next_invoice_number >= 1",
            name="ck_paysync_inv_seq_next_ge_1",
        ),
        sa.CheckConstraint(
            "number_padding >= 0 AND number_padding <= 20",
            name="ck_paysync_inv_seq_padding_bounded",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_inv_seq_tenant", "invoice_sequences",
        ["tenant_id"], schema=_SCHEMA,
    )
    # UNIQUE (tenant, type, scope_type, scope_id) — but scope_id can
    # be NULL (tenant-scoped), and Postgres treats NULLs as distinct
    # in standard UNIQUE. Use COALESCE-on-zero-uuid via expression
    # index to enforce.
    op.execute(
        f"CREATE UNIQUE INDEX uq_paysync_inv_seq_scope "
        f"ON {_SCHEMA}.invoice_sequences "
        f"(tenant_id, sequence_type, scope_type, COALESCE(scope_id, '00000000-0000-0000-0000-000000000000'::uuid))"
    )

    op.create_table(
        "invoice_sequence_change_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "sequence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.invoice_sequences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("old_next_value", sa.BigInteger(), nullable=False),
        sa.Column("new_next_value", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("new_next_value >= 1", name="ck_paysync_inv_seq_log_new_ge_1"),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_inv_seq_log_seq", "invoice_sequence_change_log",
        ["sequence_id"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_inv_seq_log_tenant", "invoice_sequence_change_log",
        ["tenant_id", "changed_at"], schema=_SCHEMA,
    )

    # RLS
    for table in _TABLES:
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {_SCHEMA}.{table}
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
