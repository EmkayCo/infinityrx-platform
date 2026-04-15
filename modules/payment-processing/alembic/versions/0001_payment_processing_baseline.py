"""Baseline tables for payment_proc schema.

Creates all eight tables that map 1:1 to models in
``src/models/tables.py``.  No prior migration exists for this module.

Tables created (in logical dependency order):
  * payment_proc.payment_proc_vendor_adapters    (VendorAdapter)
  * payment_proc.payment_proc_ach_return_codes   (AchReturnCode)
  * payment_proc.payment_proc_ofac_sdn           (OfacSdnEntry)
  * payment_proc.payment_proc_submissions        (Submission)
  * payment_proc.payment_proc_settlements        (Settlement)
  * payment_proc.payment_proc_vendor_health_log  (VendorHealthLog)
  * payment_proc.payment_proc_ofac_alerts        (OfacScreeningAlert)
  * payment_proc.payment_proc_payee_enrollments  (PayeeEnrollment)

Note: cross-table references (vendor_adapter_id, submission_id, etc.) are
stored as String(36) columns without DDL-level FOREIGN KEY constraints,
matching the ORM model definitions.

Revision ID: 0001_payment_processing_baseline
Revises: None
Create Date: 2026-04-15
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_payment_processing_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "payment_proc"


def upgrade() -> None:
    # ── payment_proc_vendor_adapters ──────────────────────────────────────
    op.create_table(
        "payment_proc_vendor_adapters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("vendor_type", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        # Connection
        sa.Column("connection_type", sa.String(50), nullable=False),
        sa.Column("api_endpoint", sa.String(500), nullable=True),
        sa.Column("api_version", sa.String(50), nullable=True),
        sa.Column("sftp_host", sa.String(255), nullable=True),
        sa.Column("sftp_port", sa.Integer(), nullable=False, server_default="22"),
        sa.Column("sftp_username", sa.String(255), nullable=True),
        sa.Column("sftp_remote_path", sa.String(500), nullable=True),
        sa.Column("credentials_vault_ref", sa.String(255), nullable=True),
        # File format
        sa.Column("file_format", sa.String(100), nullable=True),
        sa.Column("file_naming_pattern", sa.String(255), nullable=True),
        # Settlement
        sa.Column("settlement_method", sa.String(50), nullable=False),
        sa.Column("settlement_poll_interval_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("expected_settlement_days", sa.Integer(), nullable=False, server_default="2"),
        # Capabilities
        sa.Column("supports_ach", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("supports_eft", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("supports_virtual_card", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("supports_check", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("supports_same_day_ach", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        # Health
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("last_submission_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_submission_status", sa.String(50), nullable=True),
        sa.Column("last_settlement_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_count_24h", sa.Integer(), nullable=False, server_default="0"),
        # Failover chain
        sa.Column("failover_chain", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )
    op.create_index("idx_vendor_adapter_tenant", "payment_proc_vendor_adapters", ["tenant_id"], schema=_SCHEMA)

    # ── payment_proc_ach_return_codes ─────────────────────────────────────
    op.create_table(
        "payment_proc_ach_return_codes",
        sa.Column("code", sa.String(10), primary_key=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("is_retryable", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("default_action", sa.String(50), nullable=False),
        sa.Column("retry_delay_days", sa.Integer(), nullable=True),
        sa.Column("triggers_fwa_alert", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        schema=_SCHEMA,
    )

    # ── payment_proc_ofac_sdn ─────────────────────────────────────────────
    op.create_table(
        "payment_proc_ofac_sdn",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sdn_uid", sa.String(50), nullable=False),
        sa.Column("sdn_type", sa.String(20), nullable=False),
        sa.Column("program", sa.String(50), nullable=True),
        sa.Column("canonical_name", sa.String(500), nullable=False),
        sa.Column("aliases", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("country", sa.String(3), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="SDN"),
        sa.Column("source_list_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("sdn_uid", name="uq_ofac_sdn_uid"),
        schema=_SCHEMA,
    )
    op.create_index("idx_ofac_sdn_type", "payment_proc_ofac_sdn", ["sdn_type"], schema=_SCHEMA)
    op.create_index("idx_ofac_sdn_name", "payment_proc_ofac_sdn", ["canonical_name"], schema=_SCHEMA)

    # ── payment_proc_submissions ──────────────────────────────────────────
    op.create_table(
        "payment_proc_submissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("vendor_adapter_id", sa.String(36), nullable=False),
        sa.Column("billing_payment_batch_id", sa.String(36), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("submission_type", sa.String(50), nullable=False),
        sa.Column("file_id", sa.String(36), nullable=True),
        sa.Column("file_name", sa.String(500), nullable=True),
        sa.Column("file_format", sa.String(100), nullable=True),
        sa.Column("file_encrypted", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("encryption_key_ref", sa.String(255), nullable=True),
        sa.Column("payment_count", sa.Integer(), nullable=False),
        sa.Column("total_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("vendor_reference", sa.String(255), nullable=True),
        sa.Column("vendor_response", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ofac_screened", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("ofac_screened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fraud_monitoring_logged", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_submission_idempotency_key"),
        schema=_SCHEMA,
    )
    op.create_index("idx_submission_tenant", "payment_proc_submissions", ["tenant_id"], schema=_SCHEMA)
    op.create_index("idx_submission_vendor_adapter", "payment_proc_submissions", ["vendor_adapter_id"], schema=_SCHEMA)
    op.create_index("idx_submission_billing_batch", "payment_proc_submissions", ["billing_payment_batch_id"], schema=_SCHEMA)

    # ── payment_proc_settlements ──────────────────────────────────────────
    op.create_table(
        "payment_proc_settlements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("submission_id", sa.String(36), nullable=False),
        sa.Column("billing_payment_id", sa.String(36), nullable=False),
        sa.Column("pay_to_entity_id", sa.String(36), nullable=False),
        sa.Column("pay_to_npi", sa.String(10), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("settlement_date", sa.Date(), nullable=True),
        sa.Column("settlement_reference", sa.String(255), nullable=True),
        sa.Column("payment_method_used", sa.String(50), nullable=True),
        sa.Column("check_number", sa.String(50), nullable=True),
        sa.Column("trace_number", sa.String(50), nullable=True),
        sa.Column("return_code", sa.String(10), nullable=True),
        sa.Column("return_reason", sa.Text(), nullable=True),
        sa.Column("return_date", sa.Date(), nullable=True),
        sa.Column("vendor_payment_id", sa.String(255), nullable=True),
        sa.Column("vendor_status", sa.String(100), nullable=True),
        sa.Column("is_held", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("hold_reason", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )
    op.create_index("idx_settlement_tenant", "payment_proc_settlements", ["tenant_id"], schema=_SCHEMA)
    op.create_index("idx_settlement_submission", "payment_proc_settlements", ["submission_id"], schema=_SCHEMA)
    op.create_index("idx_settlement_billing_payment", "payment_proc_settlements", ["billing_payment_id"], schema=_SCHEMA)
    op.create_index("idx_settlement_tenant_status", "payment_proc_settlements", ["tenant_id", "status"], schema=_SCHEMA)

    # ── payment_proc_vendor_health_log ────────────────────────────────────
    op.create_table(
        "payment_proc_vendor_health_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("vendor_adapter_id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("check_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )
    op.create_index("idx_vendor_health_log_adapter", "payment_proc_vendor_health_log", ["vendor_adapter_id"], schema=_SCHEMA)
    op.create_index("idx_vendor_health_log_tenant", "payment_proc_vendor_health_log", ["tenant_id"], schema=_SCHEMA)

    # ── payment_proc_ofac_alerts ──────────────────────────────────────────
    op.create_table(
        "payment_proc_ofac_alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("entity_name", sa.String(500), nullable=True),
        sa.Column("sdn_uid", sa.String(50), nullable=False),
        sa.Column("sdn_canonical_name", sa.String(500), nullable=False),
        sa.Column("match_confidence", sa.String(20), nullable=False),
        sa.Column("match_score", sa.Integer(), nullable=False),
        sa.Column("match_reason", sa.Text(), nullable=True),
        sa.Column("blocked_payment_id", sa.String(36), nullable=True),
        sa.Column("resolution_status", sa.String(30), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )
    op.create_index("idx_ofac_alert_tenant_id", "payment_proc_ofac_alerts", ["tenant_id"], schema=_SCHEMA)
    op.create_index("idx_ofac_alert_tenant", "payment_proc_ofac_alerts", ["tenant_id", "created_at"], schema=_SCHEMA)
    op.create_index("idx_ofac_alert_entity", "payment_proc_ofac_alerts", ["tenant_id", "entity_id"], schema=_SCHEMA)

    # ── payment_proc_payee_enrollments ────────────────────────────────────
    op.create_table(
        "payment_proc_payee_enrollments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("vendor_adapter_id", sa.String(36), nullable=False),
        sa.Column("pay_to_entity_id", sa.String(36), nullable=False),
        sa.Column("pay_to_npi", sa.String(10), nullable=True),
        sa.Column("pay_to_name", sa.String(255), nullable=True),
        sa.Column("enrollment_status", sa.String(50), nullable=False, server_default="not_enrolled"),
        sa.Column("preferred_payment_method", sa.String(50), nullable=True),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_payment_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "vendor_adapter_id", "pay_to_entity_id",
            name="uq_payee_enrollment_tenant_vendor_entity",
        ),
        schema=_SCHEMA,
    )
    op.create_index("idx_payee_enrollment_tenant", "payment_proc_payee_enrollments", ["tenant_id"], schema=_SCHEMA)


def downgrade() -> None:
    op.drop_index("idx_payee_enrollment_tenant", table_name="payment_proc_payee_enrollments", schema=_SCHEMA)
    op.drop_table("payment_proc_payee_enrollments", schema=_SCHEMA)

    op.drop_index("idx_ofac_alert_entity", table_name="payment_proc_ofac_alerts", schema=_SCHEMA)
    op.drop_index("idx_ofac_alert_tenant", table_name="payment_proc_ofac_alerts", schema=_SCHEMA)
    op.drop_index("idx_ofac_alert_tenant_id", table_name="payment_proc_ofac_alerts", schema=_SCHEMA)
    op.drop_table("payment_proc_ofac_alerts", schema=_SCHEMA)

    op.drop_index("idx_vendor_health_log_tenant", table_name="payment_proc_vendor_health_log", schema=_SCHEMA)
    op.drop_index("idx_vendor_health_log_adapter", table_name="payment_proc_vendor_health_log", schema=_SCHEMA)
    op.drop_table("payment_proc_vendor_health_log", schema=_SCHEMA)

    op.drop_index("idx_settlement_tenant_status", table_name="payment_proc_settlements", schema=_SCHEMA)
    op.drop_index("idx_settlement_billing_payment", table_name="payment_proc_settlements", schema=_SCHEMA)
    op.drop_index("idx_settlement_submission", table_name="payment_proc_settlements", schema=_SCHEMA)
    op.drop_index("idx_settlement_tenant", table_name="payment_proc_settlements", schema=_SCHEMA)
    op.drop_table("payment_proc_settlements", schema=_SCHEMA)

    op.drop_index("idx_submission_billing_batch", table_name="payment_proc_submissions", schema=_SCHEMA)
    op.drop_index("idx_submission_vendor_adapter", table_name="payment_proc_submissions", schema=_SCHEMA)
    op.drop_index("idx_submission_tenant", table_name="payment_proc_submissions", schema=_SCHEMA)
    op.drop_table("payment_proc_submissions", schema=_SCHEMA)

    op.drop_index("idx_ofac_sdn_name", table_name="payment_proc_ofac_sdn", schema=_SCHEMA)
    op.drop_index("idx_ofac_sdn_type", table_name="payment_proc_ofac_sdn", schema=_SCHEMA)
    op.drop_table("payment_proc_ofac_sdn", schema=_SCHEMA)

    op.drop_table("payment_proc_ach_return_codes", schema=_SCHEMA)

    op.drop_index("idx_vendor_adapter_tenant", table_name="payment_proc_vendor_adapters", schema=_SCHEMA)
    op.drop_table("payment_proc_vendor_adapters", schema=_SCHEMA)
