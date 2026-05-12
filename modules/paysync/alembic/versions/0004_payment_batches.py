"""paysync Wave 37: payment_batches + credits + held_claims + files.

Adds the payment-side domain model on top of cycles + claims +
pay_to_resolutions:

  - paysync.payment_batches            — one row per batch
  - paysync.payment_batch_credits      — one row per pay-to within
                                         a batch
  - paysync.payment_batch_held_claims  — claims excluded from
                                         batch generation
  - paysync.payment_batch_files        — generated NACHA / 835 /
                                         remittance / CSV files
  - paysync.batch_audit_log            — append-only state-
                                         transition + file-gen log

Status state machine on payment_batches:

  draft → pending_approval → approved → submitted → settled → reconciled
                                              ↓
                                            voided

Voided batches cannot regenerate files; void requires
human-approved reason text.

Composite UNIQUE (tenant_id, cycle_id, batch_number).

RLS forced + NULLIF tenant predicate on every new table.

Revision ID: 0004_payment_batches
Revises: 0003_pay_to_resolutions
Create Date: 2026-04-25
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import os

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_payment_batches"
down_revision: Union[str, None] = "0003_pay_to_resolutions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "paysync"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_TABLES = (
    "payment_batches",
    "payment_batch_credits",
    "payment_batch_held_claims",
    "payment_batch_files",
    "batch_audit_log",
)


def upgrade() -> None:
    # ── payment_batches ───────────────────────────────────────────
    op.create_table(
        "payment_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "cycle_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.cycles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("batch_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'draft'")),
        sa.Column(
            "total_credit_amount", sa.Numeric(14, 2),
            nullable=False, server_default=sa.text("0.00"),
        ),
        sa.Column("credit_entry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("claim_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("file_id_modifier", sa.String(1), nullable=False, server_default=sa.text("'A'")),
        sa.Column("effective_entry_date", sa.Date(), nullable=False),
        sa.Column("entry_class_code", sa.String(3), nullable=False, server_default=sa.text("'PPD'")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id", "cycle_id", "batch_number",
            name="uq_paysync_pbatch_cycle_num",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'pending_approval', 'approved', "
            "'submitted', 'settled', 'reconciled', 'voided', 'failed')",
            name="ck_paysync_pbatch_status",
        ),
        sa.CheckConstraint(
            "entry_class_code IN ('PPD', 'CCD', 'CTX')",
            name="ck_paysync_pbatch_entry_class",
        ),
        sa.CheckConstraint(
            "file_id_modifier ~ '^[A-Z0-9]$'",
            name="ck_paysync_pbatch_file_id_modifier",
        ),
        sa.CheckConstraint(
            "batch_number >= 1",
            name="ck_paysync_pbatch_number_ge_1",
        ),
        sa.CheckConstraint(
            "total_credit_amount >= 0 AND credit_entry_count >= 0 AND claim_count >= 0",
            name="ck_paysync_pbatch_counts_nonneg",
        ),
        schema=_SCHEMA,
    )
    op.create_index("ix_paysync_pbatch_cycle", "payment_batches", ["cycle_id"], schema=_SCHEMA)
    op.create_index(
        "ix_paysync_pbatch_status", "payment_batches",
        ["tenant_id", "status"], schema=_SCHEMA,
    )

    # ── payment_batch_credits ─────────────────────────────────────
    op.create_table(
        "payment_batch_credits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "payment_batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.payment_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pay_to_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("banking_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credit_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("claim_count", sa.Integer(), nullable=False),
        sa.Column(
            "claim_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'::uuid[]"),
        ),
        sa.Column("addenda_record_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("trace_number", sa.String(15), nullable=True),
        sa.Column("entry_class_code", sa.String(3), nullable=False, server_default=sa.text("'PPD'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "payment_batch_id", "pay_to_entity_id",
            name="uq_paysync_pbcr_batch_payto",
        ),
        sa.CheckConstraint(
            "credit_amount > 0",
            name="ck_paysync_pbcr_amount_positive",
        ),
        sa.CheckConstraint(
            "claim_count >= 1",
            name="ck_paysync_pbcr_claim_count_ge_1",
        ),
        sa.CheckConstraint(
            "entry_class_code IN ('PPD', 'CCD', 'CTX')",
            name="ck_paysync_pbcr_entry_class",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_pbcr_batch", "payment_batch_credits",
        ["payment_batch_id"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_pbcr_payto", "payment_batch_credits",
        ["tenant_id", "pay_to_entity_id"], schema=_SCHEMA,
    )

    # ── payment_batch_held_claims ─────────────────────────────────
    op.create_table(
        "payment_batch_held_claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "cycle_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.cycles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "claim_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.claims.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("hold_reason", sa.Text(), nullable=False),
        sa.Column("held_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("held_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("release_notes", sa.Text(), nullable=True),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_held_claim", "payment_batch_held_claims",
        ["claim_id"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_held_cycle", "payment_batch_held_claims",
        ["tenant_id", "cycle_id"], schema=_SCHEMA,
    )
    # One active hold per claim (released_at IS NULL means active)
    op.execute(
        f"CREATE UNIQUE INDEX uq_paysync_held_one_active_per_claim "
        f"ON {_SCHEMA}.payment_batch_held_claims (tenant_id, claim_id) "
        f"WHERE released_at IS NULL"
    )

    # ── payment_batch_files ───────────────────────────────────────
    op.create_table(
        "payment_batch_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "payment_batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.payment_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pay_to_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("file_type", sa.String(32), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("generated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "file_type IN ('nacha', '835', 'remittance_pdf', 'csv_summary')",
            name="ck_paysync_pbfile_type",
        ),
        sa.CheckConstraint(
            "file_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_paysync_pbfile_sha256_format",
        ),
        sa.CheckConstraint(
            "file_size_bytes >= 0",
            name="ck_paysync_pbfile_size_nonneg",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_pbfile_batch", "payment_batch_files",
        ["payment_batch_id"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_pbfile_type", "payment_batch_files",
        ["tenant_id", "file_type"], schema=_SCHEMA,
    )

    # ── batch_audit_log ───────────────────────────────────────────
    # Append-only state-transition + file-generation log. No
    # UPDATE/DELETE in application code.
    op.create_table(
        "batch_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "payment_batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.payment_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_baudit_batch", "batch_audit_log",
        ["payment_batch_id"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_baudit_tenant", "batch_audit_log",
        ["tenant_id", "created_at"], schema=_SCHEMA,
    )

    # RLS for all 5 tables
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
    for table in reversed(_TABLES):
        op.drop_table(table, schema=_SCHEMA)
