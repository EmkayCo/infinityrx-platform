"""reclaimrx baseline — Wave 42 foundation schema.

Tables created (in dependency order):
  1. detection_runs              (provenance per batch detection sweep)
  2. csv_upload_rows             (raw rows from operator CSV uploads)
  3. recoup_cases                (agent workflow envelope)
  4. anomalies                   (the core anomaly persistence row)
  5. case_assignments            (assignment history)
  6. case_anomaly_links          (many-to-many)
  7. anomaly_audit_log           (append-only state-change audit)
  8. case_number_sequences       (per-tenant operator-facing numbering)

All eight tables are tenant-scoped. Money columns are NUMERIC(12,2).
Quantity is NUMERIC(10,3). Confidence is NUMERIC(5,4).

CHECK constraints enforce value sets for status / kind / source enums.
RLS policies are applied in 0002_reclaimrx_rls.

Revision ID: 0001_reclaimrx_baseline
Revises:
Create Date: 2026-04-26
"""

from __future__ import annotations

from typing import Sequence, Union

import os

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_reclaimrx_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "reclaimrx"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")

# Value sets. Schema-level CHECKs enforce these; transition rules live in
# the service layer (anomalies/repository.py + cases/manager.py).
_DATA_SOURCES = "('live_db', 'paysync_data', 'csv_upload')"
_RUN_STATUSES = "('in_progress', 'completed', 'failed', 'cancelled')"
_RESOLUTION_METHODS_CSV = "('declared', 'group_id_lookup', 'ndc_lookup', 'manual', 'unmapped')"
_SOURCE_TABLES = "('claim_transactions', 'paysync_claims', 'csv_upload_rows')"
_DETECTION_KINDS = "('rule', 'ml_pattern', 'manual_flag')"
_SEVERITIES = "('critical', 'high', 'medium', 'low', 'informational')"
_ANOMALY_STATUSES = (
    "('open', 'under_review', 'confirmed', 'dismissed', "
    "'in_recoup', 'in_audit', 'resolved', 'written_off')"
)
_ANOMALY_RESOLUTION_METHODS = (
    "('pharmacy_corrected', 'recovered', 'audit_findings', "
    "'dismissed_false_positive', 'written_off')"
)
_CASE_SCOPE_TYPES = "('client_pharmacy', 'client_pharmacy_program', 'pharmacy_all_clients', 'custom')"
_CASE_STATUSES = (
    "('draft', 'assigned', 'in_progress', 'awaiting_pharmacy', "
    "'in_audit', 'resolved', 'written_off', 'cancelled')"
)


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    # ── 1. detection_runs ──
    op.create_table(
        "detection_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("data_source", sa.String(32), nullable=False),
        sa.Column("run_label", sa.String(255), nullable=False),
        sa.Column("source_path", sa.String(500), nullable=True),
        sa.Column("source_filename", sa.String(500), nullable=True),
        sa.Column("source_sha256", sa.String(64), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("filter_client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("filter_program_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("filter_pharmacy_npi", sa.String(10), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("anomaly_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "resolution_stats",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'in_progress'")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(f"data_source IN {_DATA_SOURCES}", name="ck_reclaimrx_runs_data_source"),
        sa.CheckConstraint(f"status IN {_RUN_STATUSES}", name="ck_reclaimrx_runs_status"),
        sa.CheckConstraint(
            "record_count >= 0 AND anomaly_count >= 0",
            name="ck_reclaimrx_runs_counts_nonneg",
        ),
        sa.CheckConstraint(
            "(period_start IS NULL AND period_end IS NULL) OR "
            "(period_start IS NOT NULL AND period_end IS NOT NULL AND period_end >= period_start)",
            name="ck_reclaimrx_runs_period_order",
        ),
        sa.CheckConstraint(
            "filter_pharmacy_npi IS NULL OR length(filter_pharmacy_npi) = 10",
            name="ck_reclaimrx_runs_npi_len",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(resolution_stats) = 'object'",
            name="ck_reclaimrx_runs_resolution_stats_object",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_runs_tenant_status",
        "detection_runs",
        ["tenant_id", "status"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_runs_started_at",
        "detection_runs",
        ["tenant_id", "started_at"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_runs_data_source",
        "detection_runs",
        ["tenant_id", "data_source"],
        schema=_SCHEMA,
    )

    # ── 2. csv_upload_rows ──
    op.create_table(
        "csv_upload_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "detection_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.detection_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column(
            "row_data",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("resolved_client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_program_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_pharmacy_npi", sa.String(10), nullable=True),
        sa.Column("resolved_ndc", sa.String(20), nullable=True),
        sa.Column("resolution_method", sa.String(32), nullable=False),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            f"resolution_method IN {_RESOLUTION_METHODS_CSV}",
            name="ck_reclaimrx_csv_rows_resolution_method",
        ),
        sa.CheckConstraint(
            "row_number >= 0",
            name="ck_reclaimrx_csv_rows_rownum_nonneg",
        ),
        sa.CheckConstraint(
            "resolved_pharmacy_npi IS NULL OR length(resolved_pharmacy_npi) = 10",
            name="ck_reclaimrx_csv_rows_npi_len",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(row_data) = 'object'",
            name="ck_reclaimrx_csv_rows_row_data_object",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_csv_rows_run",
        "csv_upload_rows",
        ["detection_run_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_csv_rows_tenant",
        "csv_upload_rows",
        ["tenant_id"],
        schema=_SCHEMA,
    )

    # ── 3. recoup_cases ──
    op.create_table(
        "recoup_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_number", sa.String(50), nullable=False),
        sa.Column("scope_type", sa.String(32), nullable=False),
        sa.Column("scope_client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scope_program_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scope_pharmacy_npi", sa.String(10), nullable=True),
        sa.Column("scope_filter", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("anomaly_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "total_amount_at_risk",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0.00"),
        ),
        sa.Column(
            "total_recovered",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0.00"),
        ),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opened_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "audit_log",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("tenant_id", "case_number", name="uq_reclaimrx_case_number"),
        sa.CheckConstraint(f"scope_type IN {_CASE_SCOPE_TYPES}", name="ck_reclaimrx_cases_scope_type"),
        sa.CheckConstraint(f"status IN {_CASE_STATUSES}", name="ck_reclaimrx_cases_status"),
        sa.CheckConstraint(
            "anomaly_count >= 0",
            name="ck_reclaimrx_cases_anomaly_count_nonneg",
        ),
        sa.CheckConstraint(
            "total_amount_at_risk >= 0",
            name="ck_reclaimrx_cases_amount_at_risk_nonneg",
        ),
        sa.CheckConstraint(
            "total_recovered >= 0",
            name="ck_reclaimrx_cases_recovered_nonneg",
        ),
        sa.CheckConstraint(
            "scope_pharmacy_npi IS NULL OR length(scope_pharmacy_npi) = 10",
            name="ck_reclaimrx_cases_scope_npi_len",
        ),
        sa.CheckConstraint(
            "scope_filter IS NULL OR jsonb_typeof(scope_filter) = 'object'",
            name="ck_reclaimrx_cases_scope_filter_object",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(audit_log) = 'array'",
            name="ck_reclaimrx_cases_audit_log_array",
        ),
        sa.CheckConstraint(
            "(closed_at IS NULL AND closed_by IS NULL) OR "
            "(closed_at IS NOT NULL AND closed_by IS NOT NULL)",
            name="ck_reclaimrx_cases_closed_pair",
        ),
        sa.CheckConstraint(
            "(assigned_to IS NULL AND assigned_at IS NULL AND assigned_by IS NULL) OR "
            "(assigned_to IS NOT NULL AND assigned_at IS NOT NULL AND assigned_by IS NOT NULL)",
            name="ck_reclaimrx_cases_assigned_triple",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_cases_status",
        "recoup_cases",
        ["tenant_id", "status"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_cases_assigned",
        "recoup_cases",
        ["tenant_id", "assigned_to"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_cases_client",
        "recoup_cases",
        ["tenant_id", "scope_client_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_cases_npi",
        "recoup_cases",
        ["tenant_id", "scope_pharmacy_npi"],
        schema=_SCHEMA,
    )

    # ── 4. anomalies ──
    op.create_table(
        "anomalies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("data_source", sa.String(32), nullable=False),
        sa.Column(
            "data_source_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.detection_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Hierarchy.
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("pharmacy_npi", sa.String(10), nullable=True),
        sa.Column("ndc", sa.String(20), nullable=True),
        # Polymorphic source.
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_table", sa.String(32), nullable=False),
        sa.Column("source_row_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Detection.
        sa.Column("detection_kind", sa.String(16), nullable=False),
        sa.Column("detection_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        # Domain context snapshot.
        sa.Column("date_of_service", sa.Date(), nullable=True),
        sa.Column("rx_number", sa.String(50), nullable=True),
        sa.Column("prescriber_npi", sa.String(10), nullable=True),
        sa.Column("days_supply", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=True),
        sa.Column("amount_paid", sa.Numeric(12, 2), nullable=True),
        sa.Column("amount_billed", sa.Numeric(12, 2), nullable=True),
        # Findings.
        sa.Column("finding_code", sa.String(50), nullable=False),
        sa.Column("finding_summary", sa.Text(), nullable=False),
        sa.Column(
            "finding_details",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # Workflow.
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'open'")),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.recoup_cases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolution_method", sa.String(32), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recovery_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(f"data_source IN {_DATA_SOURCES}", name="ck_reclaimrx_anomalies_data_source"),
        sa.CheckConstraint(f"source_table IN {_SOURCE_TABLES}", name="ck_reclaimrx_anomalies_source_table"),
        sa.CheckConstraint(f"detection_kind IN {_DETECTION_KINDS}", name="ck_reclaimrx_anomalies_detection_kind"),
        sa.CheckConstraint(f"severity IN {_SEVERITIES}", name="ck_reclaimrx_anomalies_severity"),
        sa.CheckConstraint(f"status IN {_ANOMALY_STATUSES}", name="ck_reclaimrx_anomalies_status"),
        sa.CheckConstraint(
            f"resolution_method IS NULL OR resolution_method IN {_ANOMALY_RESOLUTION_METHODS}",
            name="ck_reclaimrx_anomalies_resolution_method",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_reclaimrx_anomalies_confidence_range",
        ),
        sa.CheckConstraint(
            "days_supply IS NULL OR days_supply >= 0",
            name="ck_reclaimrx_anomalies_days_supply_nonneg",
        ),
        sa.CheckConstraint(
            "quantity IS NULL OR quantity >= 0",
            name="ck_reclaimrx_anomalies_qty_nonneg",
        ),
        sa.CheckConstraint(
            "pharmacy_npi IS NULL OR length(pharmacy_npi) = 10",
            name="ck_reclaimrx_anomalies_npi_len",
        ),
        sa.CheckConstraint(
            "prescriber_npi IS NULL OR length(prescriber_npi) = 10",
            name="ck_reclaimrx_anomalies_prescriber_npi_len",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(finding_details) = 'object'",
            name="ck_reclaimrx_anomalies_finding_details_object",
        ),
        # Manual flags carry no detection_id; rule + ml_pattern do.
        sa.CheckConstraint(
            "(detection_kind = 'manual_flag' AND detection_id IS NULL) OR "
            "(detection_kind <> 'manual_flag' AND detection_id IS NOT NULL)",
            name="ck_reclaimrx_anomalies_detection_id_kind",
        ),
        # Resolved anomalies must carry resolution_method + resolved_at + resolved_by.
        sa.CheckConstraint(
            "(resolved_at IS NULL AND resolved_by IS NULL AND resolution_method IS NULL) OR "
            "(resolved_at IS NOT NULL AND resolved_by IS NOT NULL AND resolution_method IS NOT NULL)",
            name="ck_reclaimrx_anomalies_resolved_triple",
        ),
        # Recovery amount only meaningful when resolved.
        sa.CheckConstraint(
            "recovery_amount IS NULL OR recovery_amount >= 0",
            name="ck_reclaimrx_anomalies_recovery_nonneg",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_anomalies_status",
        "anomalies",
        ["tenant_id", "status"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_anomalies_client_status",
        "anomalies",
        ["tenant_id", "client_id", "status"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_anomalies_npi_status",
        "anomalies",
        ["tenant_id", "pharmacy_npi", "status"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_anomalies_ndc_status",
        "anomalies",
        ["tenant_id", "ndc", "status"],
        schema=_SCHEMA,
    )
    op.create_index("ix_reclaimrx_anomalies_case", "anomalies", ["case_id"], schema=_SCHEMA)
    op.create_index(
        "ix_reclaimrx_anomalies_source_row",
        "anomalies",
        ["source_row_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_anomalies_run",
        "anomalies",
        ["data_source_run_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_anomalies_dos",
        "anomalies",
        ["tenant_id", "date_of_service"],
        schema=_SCHEMA,
    )

    # ── 5. case_assignments ──
    op.create_table(
        "case_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.recoup_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unassigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unassign_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(unassigned_at IS NULL) OR (unassigned_at >= assigned_at)",
            name="ck_reclaimrx_case_assignments_period_order",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_case_assignments_case",
        "case_assignments",
        ["case_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_case_assignments_assignee",
        "case_assignments",
        ["tenant_id", "assigned_to"],
        schema=_SCHEMA,
    )

    # ── 6. case_anomaly_links ──
    op.create_table(
        "case_anomaly_links",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.recoup_cases.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "anomaly_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.anomalies.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("linked_by", postgresql.UUID(as_uuid=True), nullable=False),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_case_anomaly_links_anomaly",
        "case_anomaly_links",
        ["anomaly_id"],
        schema=_SCHEMA,
    )

    # ── 7. anomaly_audit_log ──
    op.create_table(
        "anomaly_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "anomaly_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.anomalies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("old_value", postgresql.JSONB(), nullable=True),
        sa.Column("new_value", postgresql.JSONB(), nullable=True),
        sa.Column("performed_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_anomaly_audit_anomaly",
        "anomaly_audit_log",
        ["anomaly_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_anomaly_audit_tenant",
        "anomaly_audit_log",
        ["tenant_id", "performed_at"],
        schema=_SCHEMA,
    )

    # ── 8. case_number_sequences ──
    op.create_table(
        "case_number_sequences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prefix", sa.String(10), nullable=False, server_default=sa.text("'RX-'")),
        sa.Column("next_number", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("padding", sa.Integer(), nullable=False, server_default=sa.text("6")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("tenant_id", name="uq_reclaimrx_case_seq_one_per_tenant"),
        sa.CheckConstraint("next_number >= 1", name="ck_reclaimrx_case_seq_next_pos"),
        sa.CheckConstraint("padding >= 1 AND padding <= 12", name="ck_reclaimrx_case_seq_padding_sane"),
        schema=_SCHEMA,
    )

    # GRANTs to tier app + admin roles. Mock left out — dormant per CLAUDE.md.
    op.execute(
        f"GRANT USAGE ON SCHEMA {_SCHEMA} TO ifx_dev_app, {_APP_ROLE}, ifx_dev_admin, ifx_prod_admin"
    )
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {_SCHEMA} "
        f"TO ifx_dev_app, {_APP_ROLE}, ifx_dev_admin, ifx_prod_admin"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {_SCHEMA} "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES "
        f"TO ifx_dev_app, {_APP_ROLE}, ifx_dev_admin, ifx_prod_admin"
    )


def downgrade() -> None:
    op.drop_table("case_number_sequences", schema=_SCHEMA)
    op.drop_table("anomaly_audit_log", schema=_SCHEMA)
    op.drop_table("case_anomaly_links", schema=_SCHEMA)
    op.drop_table("case_assignments", schema=_SCHEMA)
    op.drop_table("anomalies", schema=_SCHEMA)
    op.drop_table("recoup_cases", schema=_SCHEMA)
    op.drop_table("csv_upload_rows", schema=_SCHEMA)
    op.drop_table("detection_runs", schema=_SCHEMA)
