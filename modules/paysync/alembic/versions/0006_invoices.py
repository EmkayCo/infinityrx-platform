"""paysync Wave 38 M2: invoices + invoice_lines + invoice_attachments + invoice_audit_log + fee_schedules + gl_account_mappings.

Money discipline: every dollar amount NUMERIC(14,2). Reversals
permitted as negative line_amounts on adjustment lines so an
invoice can carry rebate offsets / corrections. Invoice totals
recomputed on every line change in the service layer.

Status state machine on invoices:

  draft → finalized → sent → paid|partial → (reconciled)
                              ↓
                            voided  (void allowed from any non-paid
                                     status; from paid requires
                                     explicit confirmation)

Composite UNIQUE (tenant_id, invoice_number) — no two invoices in
a tenant share a rendered number, even across sequence_types.
Operators must keep prefixes distinct between sequences (REIM- /
FEE-) to guarantee non-collision; we don't enforce structurally
because operators may rationally choose to share namespace.

Revision ID: 0006_invoices
Revises: 0005_invoice_sequences
Create Date: 2026-04-25
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import os

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_invoices"
down_revision: Union[str, None] = "0005_invoice_sequences"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "paysync"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_TABLES = (
    "fee_schedules",
    "gl_account_mappings",
    "invoices",
    "invoice_lines",
    "invoice_attachments",
    "invoice_audit_log",
)


def upgrade() -> None:
    # ── fee_schedules ─────────────────────────────────────────────
    op.create_table(
        "fee_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_name", sa.String(100), nullable=False),
        sa.Column("bill_to_scope_type", sa.String(16), nullable=False),
        sa.Column("bill_to_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fee_lines", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "bill_to_scope_type IN ('client', 'program', 'tenant')",
            name="ck_paysync_fee_sched_scope_type",
        ),
        sa.CheckConstraint(
            "(bill_to_scope_type = 'tenant') = (bill_to_id IS NULL)",
            name="ck_paysync_fee_sched_scope_id_consistent",
        ),
        sa.CheckConstraint(
            "termination_date IS NULL OR termination_date >= effective_from",
            name="ck_paysync_fee_sched_period_order",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(fee_lines) = 'array'",
            name="ck_paysync_fee_sched_lines_is_array",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_fee_sched_tenant", "fee_schedules",
        ["tenant_id"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_fee_sched_billto", "fee_schedules",
        ["tenant_id", "bill_to_scope_type", "bill_to_id"], schema=_SCHEMA,
    )

    # ── gl_account_mappings ───────────────────────────────────────
    op.create_table(
        "gl_account_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mapping_key", sa.String(64), nullable=False),
        sa.Column("gl_account_code", sa.String(50), nullable=False),
        sa.Column("gl_account_name", sa.String(255), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "mapping_key IN ('claim_reimbursement', 'transaction_fee', "
            "'admin_fee', 'rebate_offset', 'manual_adjustment')",
            name="ck_paysync_gl_mapping_key",
        ),
        sa.CheckConstraint(
            "termination_date IS NULL OR termination_date >= effective_from",
            name="ck_paysync_gl_mapping_period_order",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_gl_mapping_tenant", "gl_account_mappings",
        ["tenant_id"], schema=_SCHEMA,
    )
    op.execute(
        f"CREATE UNIQUE INDEX uq_paysync_gl_mapping_active "
        f"ON {_SCHEMA}.gl_account_mappings (tenant_id, mapping_key) "
        f"WHERE termination_date IS NULL"
    )

    # ── invoices ──────────────────────────────────────────────────
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column("invoice_number_raw", sa.BigInteger(), nullable=False),
        sa.Column(
            "sequence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.invoice_sequences.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sequence_type", sa.String(32), nullable=False),
        sa.Column(
            "cycle_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.cycles.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("bill_to_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bill_to_scope_type", sa.String(16), nullable=False),
        sa.Column("bill_to_name", sa.String(255), nullable=True),
        sa.Column("invoice_group", sa.String(50), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("payment_reference", sa.String(255), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id", "invoice_number",
            name="uq_paysync_invoice_number",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'finalized', 'sent', 'paid', "
            "'partial', 'voided', 'overdue')",
            name="ck_paysync_invoice_status",
        ),
        sa.CheckConstraint(
            "sequence_type IN ('reimbursement', 'client_fees')",
            name="ck_paysync_invoice_sequence_type",
        ),
        sa.CheckConstraint(
            "bill_to_scope_type IN ('client', 'program')",
            name="ck_paysync_invoice_bill_to_scope_type",
        ),
        sa.CheckConstraint(
            "due_date IS NULL OR due_date >= invoice_date",
            name="ck_paysync_invoice_due_after_invoice_date",
        ),
        sa.CheckConstraint(
            "tax_amount >= 0",
            name="ck_paysync_invoice_tax_nonneg",
        ),
        sa.CheckConstraint(
            "paid_amount IS NULL OR paid_amount >= 0",
            name="ck_paysync_invoice_paid_amount_nonneg",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_invoice_tenant_status", "invoices",
        ["tenant_id", "status"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_invoice_cycle", "invoices",
        ["cycle_id"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_invoice_billto", "invoices",
        ["tenant_id", "bill_to_scope_type", "bill_to_id"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_invoice_group", "invoices",
        ["tenant_id", "invoice_group"], schema=_SCHEMA,
    )

    # ── invoice_lines ─────────────────────────────────────────────
    op.create_table(
        "invoice_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("line_type", sa.String(32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "quantity", sa.Numeric(10, 2),
            nullable=False, server_default=sa.text("1.00"),
        ),
        sa.Column("unit_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("line_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "source_claim_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.claims.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_program_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("gl_account_code", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "invoice_id", "line_number",
            name="uq_paysync_invoice_line_number",
        ),
        sa.CheckConstraint(
            "line_type IN ('claim_reimbursement', 'transaction_fee', "
            "'admin_fee', 'rebate_offset', 'manual_adjustment')",
            name="ck_paysync_invoice_line_type",
        ),
        sa.CheckConstraint(
            "line_number >= 1",
            name="ck_paysync_invoice_line_number_ge_1",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_invoice_line_invoice", "invoice_lines",
        ["invoice_id"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_invoice_line_claim", "invoice_lines",
        ["source_claim_id"], schema=_SCHEMA,
        postgresql_where=sa.text("source_claim_id IS NOT NULL"),
    )

    # ── invoice_attachments ───────────────────────────────────────
    op.create_table(
        "invoice_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attachment_type", sa.String(32), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("generated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "attachment_type IN ('backup_excel', 'serialized_report', "
            "'pdf_invoice', 'custom_export', 'saasant_excel', "
            "'pharmacy_statement', 'csv_summary')",
            name="ck_paysync_inv_attach_type",
        ),
        sa.CheckConstraint(
            "file_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_paysync_inv_attach_sha256_format",
        ),
        sa.CheckConstraint(
            "file_size_bytes >= 0",
            name="ck_paysync_inv_attach_size_nonneg",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_inv_attach_invoice", "invoice_attachments",
        ["invoice_id"], schema=_SCHEMA,
    )

    # ── invoice_audit_log ─────────────────────────────────────────
    op.create_table(
        "invoice_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("event_data", postgresql.JSONB(), nullable=True),
        sa.Column("performed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_inv_audit_invoice", "invoice_audit_log",
        ["invoice_id"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_inv_audit_tenant", "invoice_audit_log",
        ["tenant_id", "performed_at"], schema=_SCHEMA,
    )

    # RLS for all 6
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
