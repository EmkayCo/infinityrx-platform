"""paysync Wave 39 M2: manual_ap_records + echo_spec_400 schema.

Adds:
  - paysync.manual_ap_records — operator-entered or auto-job-
    created payment records for manual channels (Echo,
    CheckIssuing, Wire, Other). Status state machine:
    created → queued → submitted → processed (or failed/voided
    from any state).
  - paysync.echo_spec_400_runs — daily Echo Spec 400 batch run
    metadata (file, status_file, manual_ap_record_ids array).
  - paysync.echo_payment_status_records — per-record status
    from Echo Payment Status File ingest.

Echo Spec 400 file generation + Payment Status File parsing
deferred to Phase 4/5 daily-job wave; this migration lands the
schema so that wave can ship without further migrations.

Revision ID: 0009_manual_ap_records
Revises: 0008_cycle_schedules
Create Date: 2026-04-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import os

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_manual_ap_records"
down_revision: Union[str, None] = "0008_cycle_schedules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "paysync"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_TABLES = (
    "manual_ap_records",
    "echo_spec_400_runs",
    "echo_payment_status_records",
)


def upgrade() -> None:
    # ── manual_ap_records ─────────────────────────────────────────
    op.create_table(
        "manual_ap_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "claim_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.claims.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("external_reference", sa.String(255), nullable=True),
        sa.Column(
            "payee_entity_id", postgresql.UUID(as_uuid=True), nullable=True,
        ),
        sa.Column("payee_external_id", sa.String(64), nullable=True),
        sa.Column("payment_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "status", sa.String(32),
            nullable=False, server_default=sa.text("'created'"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "channel IN ('echo', 'check_issuing', 'wire', 'other')",
            name="ck_paysync_manual_ap_channel",
        ),
        sa.CheckConstraint(
            "status IN ('created', 'queued', 'submitted', 'processed', "
            "'failed', 'voided')",
            name="ck_paysync_manual_ap_status",
        ),
        sa.CheckConstraint(
            "source IN ('auto_daily_job', 'operator_manual', 'imported')",
            name="ck_paysync_manual_ap_source",
        ),
        sa.CheckConstraint(
            "payment_amount > 0",
            name="ck_paysync_manual_ap_amount_pos",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_manual_ap_tenant", "manual_ap_records",
        ["tenant_id"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_manual_ap_claim", "manual_ap_records",
        ["claim_id"], schema=_SCHEMA,
        postgresql_where=sa.text("claim_id IS NOT NULL"),
    )
    op.create_index(
        "ix_paysync_manual_ap_status", "manual_ap_records",
        ["tenant_id", "status"], schema=_SCHEMA,
    )

    # ── echo_spec_400_runs ────────────────────────────────────────
    op.create_table(
        "echo_spec_400_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("file_sha256", sa.String(64), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status_file_path", sa.Text(), nullable=True),
        sa.Column("status_file_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_file_processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "manual_ap_record_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'::uuid[]"),
        ),
        sa.Column(
            "status", sa.String(32),
            nullable=False, server_default=sa.text("'pending_submission'"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pending_submission', 'submitted', "
            "'status_received', 'reconciled', 'failed')",
            name="ck_paysync_echo_run_status",
        ),
        sa.CheckConstraint(
            "file_sha256 IS NULL OR file_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_paysync_echo_run_sha256",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_echo_run_tenant_date", "echo_spec_400_runs",
        ["tenant_id", "run_date"], schema=_SCHEMA,
    )

    # ── echo_payment_status_records ──────────────────────────────
    op.create_table(
        "echo_payment_status_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "echo_spec_400_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.echo_spec_400_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "manual_ap_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.manual_ap_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("echo_status_code", sa.String(10), nullable=False),
        sa.Column("echo_status_message", sa.Text(), nullable=True),
        sa.Column("actual_amount_paid", sa.Numeric(14, 2), nullable=True),
        sa.Column("paid_at_per_echo", sa.Date(), nullable=True),
        sa.Column("check_number", sa.String(50), nullable=True),
        sa.Column("card_token", sa.String(100), nullable=True),
        sa.Column(
            "reconciled", sa.Boolean(),
            nullable=False, server_default=sa.false(),
        ),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_echo_status_run", "echo_payment_status_records",
        ["echo_spec_400_run_id"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_echo_status_ap", "echo_payment_status_records",
        ["manual_ap_record_id"], schema=_SCHEMA,
        postgresql_where=sa.text("manual_ap_record_id IS NOT NULL"),
    )

    # RLS for all 3 tables
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
