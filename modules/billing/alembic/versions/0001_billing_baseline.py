"""Baseline tables for the billing module.

Creates all 24 tables that the BillingBase ORM models define. Tables are
created in foreign-key dependency order so that referential constraints
resolve at DDL time.

Tables created (in dependency order):
  billing.claim_records          (ClaimRecord)
  billing.routing_rules          (RoutingRule)
  billing.payto_waterfall        (PaytoWaterfall)
  billing.file_format_mappings   (FileFormatMapping)
  billing.ap_records             (APRecord)          → claim_records
  billing.payment_batches        (PaymentBatch)
  billing.payments               (Payment)           → payment_batches
  billing.invoicing_configs      (InvoicingConfig)
  billing.invoices               (Invoice)           → invoicing_configs
  billing.invoice_line_items     (InvoiceLineItem)   → invoices
  billing.ar_records             (ARRecord)          → invoices
  billing.ar_payments            (ARPayment)         → ar_records
  billing.journal_entries        (JournalEntry)
  billing.program_budgets        (ProgramBudget)
  billing.program_budget_alerts  (ProgramBudgetAlert)    → program_budgets
  billing.program_budget_snapshots (ProgramBudgetSnapshot) → program_budgets
  billing.fee_configs            (FeeConfig)
  billing.funding_configs        (FundingConfig)
  billing.prefund_ledger         (PrefundLedger)     → funding_configs
  billing.remittance_configs     (RemittanceConfig)
  billing.sftp_configs           (SFTPConfig)
  billing.payment_vendor_configs (PaymentVendorConfig)
  billing.bank_accounts          (BankAccount)
  billing.accounting_configs     (AccountingConfig)
  billing.sequences              (BillingSequence)

Note: the billing schema is created by infrastructure/scripts/init-multi-db.sql
before migrations run — this migration does NOT issue CREATE SCHEMA.

Revision ID: 0001_billing_baseline
Revises: None
Create Date: 2026-04-15
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0001_billing_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "billing"


def upgrade() -> None:
    # ── claim_records ─────────────────────────────────────────────────────
    op.create_table(
        "claim_records",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_file_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("source_claim_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("auth_number", sa.String(50), nullable=False),
        sa.Column("reversal_of_auth", sa.String(50), nullable=True),
        sa.Column("claim_type", sa.String(50), nullable=False),
        sa.Column("member_id", sa.String(100), nullable=True),
        sa.Column("pharmacy_npi", sa.String(10), nullable=False),
        sa.Column("pharmacy_name", sa.String(255), nullable=True),
        sa.Column("prescriber_npi", sa.String(10), nullable=True),
        sa.Column("ndc", sa.String(11), nullable=True),
        sa.Column("drug_name", sa.String(255), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=True),
        sa.Column("days_supply", sa.Integer(), nullable=True),
        sa.Column("date_of_service", sa.Date(), nullable=False),
        sa.Column("date_received", sa.DateTime(timezone=True), nullable=False),
        sa.Column("program_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("program_name", sa.String(255), nullable=True),
        sa.Column("client_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("client_name", sa.String(255), nullable=True),
        sa.Column("network_reimbursement_id", sa.String(50), nullable=True),
        sa.Column("ingredient_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("dispensing_fee", sa.Numeric(12, 2), nullable=True),
        sa.Column("patient_pay", sa.Numeric(12, 2), nullable=True),
        sa.Column("plan_pay", sa.Numeric(12, 2), nullable=True),
        sa.Column("other_payer_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("net_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("under_reimbursement", sa.Numeric(12, 2), nullable=True),
        sa.Column("payment_route", sa.String(100), nullable=True),
        sa.Column("payment_vendor_config_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("payment_schedule", sa.String(100), nullable=True),
        sa.Column("pay_to_entity_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("pay_to_entity_name", sa.String(255), nullable=True),
        sa.Column("is_excluded", sa.Boolean(), nullable=True),
        sa.Column("exclusion_reason", sa.String(255), nullable=True),
        sa.Column("is_statement", sa.Boolean(), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "auth_number", name="uq_claim_tenant_auth"),
        schema=_SCHEMA,
    )
    op.create_index("idx_claims_tenant_status", "claim_records", ["tenant_id", "status"], schema=_SCHEMA)
    op.create_index("idx_claims_tenant_dos", "claim_records", ["tenant_id", "date_of_service"], schema=_SCHEMA)
    op.create_index("idx_claims_tenant_client", "claim_records", ["tenant_id", "client_id"], schema=_SCHEMA)
    op.create_index("idx_claims_nrid", "claim_records", ["tenant_id", "network_reimbursement_id"], schema=_SCHEMA)

    # ── routing_rules ─────────────────────────────────────────────────────
    op.create_table(
        "routing_rules",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("match_nrid", sa.String(50), nullable=True),
        sa.Column("match_program_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("match_pharmacy_npi", sa.String(10), nullable=True),
        sa.Column("match_claim_type", sa.String(50), nullable=True),
        sa.Column("match_client_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("match_conditions", sa.JSON(), nullable=True),
        sa.Column("payment_route", sa.String(100), nullable=False),
        sa.Column("payment_vendor_config_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("payment_schedule", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    # ── payto_waterfall ───────────────────────────────────────────────────
    op.create_table(
        "payto_waterfall",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("program_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        schema=_SCHEMA,
    )

    # ── file_format_mappings ──────────────────────────────────────────────
    op.create_table(
        "file_format_mappings",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=False),
        sa.Column("delimiter", sa.String(5), nullable=True),
        sa.Column("has_header", sa.Boolean(), nullable=True),
        sa.Column("column_mappings", sa.JSON(), nullable=False),
        sa.Column("validation_rules", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    # ── ap_records (→ claim_records) ──────────────────────────────────────
    op.create_table(
        "ap_records",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "claim_record_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("billing.claim_records.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("client_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("client_name", sa.String(255), nullable=True),
        sa.Column("program_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("program_name", sa.String(255), nullable=True),
        sa.Column("pay_to_entity_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("pay_to_entity_name", sa.String(255), nullable=False),
        sa.Column("pay_to_npi", sa.String(10), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_route", sa.String(100), nullable=False),
        sa.Column("payment_vendor_config_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("payment_schedule", sa.String(100), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("payment_batch_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("settlement_date", sa.Date(), nullable=True),
        sa.Column("return_code", sa.String(10), nullable=True),
        sa.Column("return_reason", sa.Text(), nullable=True),
        sa.Column("is_carryover", sa.Boolean(), nullable=True),
        sa.Column("carryover_from_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("carryover_reason", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )
    op.create_index("idx_ap_tenant_status", "ap_records", ["tenant_id", "status"], schema=_SCHEMA)
    op.create_index("idx_ap_payto", "ap_records", ["tenant_id", "pay_to_entity_id"], schema=_SCHEMA)
    op.create_index("idx_ap_client", "ap_records", ["tenant_id", "client_id"], schema=_SCHEMA)
    op.create_index("idx_ap_batch", "ap_records", ["payment_batch_id"], schema=_SCHEMA)

    # ── payment_batches ───────────────────────────────────────────────────
    op.create_table(
        "payment_batches",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_number", sa.String(50), nullable=False),
        sa.Column("payment_route", sa.String(100), nullable=False),
        sa.Column("payment_vendor_config_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("total_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("payment_count", sa.Integer(), nullable=False),
        sa.Column("ap_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validation_result", sa.JSON(), nullable=True),
        sa.Column("validation_warnings", sa.JSON(), nullable=True),
        sa.Column("payment_file_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("data_lock", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        schema=_SCHEMA,
    )

    # ── payments (→ payment_batches) ──────────────────────────────────────
    op.create_table(
        "payments",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "payment_batch_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("billing.payment_batches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("pay_to_entity_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("pay_to_entity_name", sa.String(255), nullable=False),
        sa.Column("pay_to_npi", sa.String(10), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("claim_count", sa.Integer(), nullable=False),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("bank_routing_number", sa.String(9), nullable=True),
        sa.Column("bank_account_number", sa.String(17), nullable=True),
        sa.Column("bank_account_type", sa.String(10), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("settlement_date", sa.Date(), nullable=True),
        sa.Column("settlement_reference", sa.String(255), nullable=True),
        sa.Column("check_number", sa.String(50), nullable=True),
        sa.Column("return_code", sa.String(10), nullable=True),
        sa.Column("return_reason", sa.Text(), nullable=True),
        sa.Column("remittance_file_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    # ── invoicing_configs ─────────────────────────────────────────────────
    op.create_table(
        "invoicing_configs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("frequency", sa.String(50), nullable=False),
        sa.Column("cycle_dates", sa.JSON(), nullable=True),
        sa.Column("day_of_week", sa.Integer(), nullable=True),
        sa.Column("custom_days", sa.Integer(), nullable=True),
        sa.Column("include_programs", sa.JSON(), nullable=True),
        sa.Column("include_fees", sa.Boolean(), nullable=True),
        sa.Column("automation_level", sa.String(50), nullable=True),
        sa.Column("auto_generate_time", sa.String(8), nullable=True),
        sa.Column("delivery_method", sa.String(50), nullable=True),
        sa.Column("delivery_recipients", sa.JSON(), nullable=True),
        sa.Column("invoice_template_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("detail_level", sa.String(50), nullable=True),
        sa.Column("payment_terms_days", sa.Integer(), nullable=True),
        sa.Column("late_fee_enabled", sa.Boolean(), nullable=True),
        sa.Column("late_fee_type", sa.String(50), nullable=True),
        sa.Column("late_fee_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("late_fee_percentage", sa.Numeric(8, 4), nullable=True),
        sa.Column("late_fee_grace_days", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    # ── invoices (→ invoicing_configs) ────────────────────────────────────
    op.create_table(
        "invoices",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "invoicing_config_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("billing.invoicing_configs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column("invoice_type", sa.String(50), nullable=False),
        sa.Column("client_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("client_name", sa.String(255), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("claims_subtotal", sa.Numeric(15, 2), nullable=True),
        sa.Column("fees_subtotal", sa.Numeric(15, 2), nullable=True),
        sa.Column("adjustments", sa.Numeric(15, 2), nullable=True),
        sa.Column("late_fees", sa.Numeric(15, 2), nullable=True),
        sa.Column("total", sa.Numeric(15, 2), nullable=False),
        sa.Column("claim_count", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("payment_terms_days", sa.Integer(), nullable=True),
        sa.Column("paid_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_method", sa.String(50), nullable=True),
        sa.Column("pdf_file_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("data_lock", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        schema=_SCHEMA,
    )

    # ── invoice_line_items (→ invoices) ───────────────────────────────────
    op.create_table(
        "invoice_line_items",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "invoice_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("billing.invoices.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("line_type", sa.String(50), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("program_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("program_name", sa.String(255), nullable=True),
        sa.Column("fee_config_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("unit_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    # ── ar_records (→ invoices) ───────────────────────────────────────────
    op.create_table(
        "ar_records",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "invoice_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("billing.invoices.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("client_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_due", sa.Numeric(15, 2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(15, 2), nullable=True),
        sa.Column("amount_outstanding", sa.Numeric(15, 2), nullable=False),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("days_outstanding", sa.Integer(), nullable=True),
        sa.Column("aging_bucket", sa.String(20), nullable=True),
        sa.Column("dispute_reason", sa.Text(), nullable=True),
        sa.Column("dispute_opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispute_resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispute_resolution", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    # ── ar_payments (→ ar_records) ────────────────────────────────────────
    op.create_table(
        "ar_payments",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "ar_record_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("billing.ar_records.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("payment_reference", sa.String(255), nullable=True),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("recorded_by", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    # ── journal_entries ───────────────────────────────────────────────────
    op.create_table(
        "journal_entries",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("entry_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_type", sa.String(100), nullable=False),
        sa.Column("client_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("client_name", sa.String(255), nullable=True),
        sa.Column("program_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("program_name", sa.String(255), nullable=True),
        sa.Column("pay_to_entity_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("pay_to_entity_name", sa.String(255), nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("gl_account_code", sa.String(50), nullable=True),
        sa.Column("gl_class", sa.String(100), nullable=True),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("reference_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("exported_to_accounting", sa.Boolean(), nullable=True),
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("export_reference", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )
    op.create_index("idx_journal_tenant_date", "journal_entries", ["tenant_id", "entry_date"], schema=_SCHEMA)
    op.create_index("idx_journal_client", "journal_entries", ["tenant_id", "client_id", "entry_date"], schema=_SCHEMA)
    op.create_index("idx_journal_program", "journal_entries", ["tenant_id", "program_id", "entry_date"], schema=_SCHEMA)
    op.create_index("idx_journal_type", "journal_entries", ["tenant_id", "entry_type"], schema=_SCHEMA)
    op.create_index("idx_journal_category", "journal_entries", ["tenant_id", "category"], schema=_SCHEMA)
    op.create_index("idx_journal_exported", "journal_entries", ["tenant_id", "exported_to_accounting"], schema=_SCHEMA)

    # ── program_budgets ───────────────────────────────────────────────────
    op.create_table(
        "program_budgets",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("program_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("budget_type", sa.String(50), nullable=False),
        sa.Column("budget_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("budget_period_start", sa.Date(), nullable=True),
        sa.Column("budget_period_end", sa.Date(), nullable=True),
        sa.Column("spent_to_date", sa.Numeric(15, 2), nullable=True),
        sa.Column("remaining", sa.Numeric(15, 2), nullable=True),
        sa.Column("utilization_percentage", sa.Numeric(8, 2), nullable=True),
        sa.Column("burn_rate_daily", sa.Numeric(12, 2), nullable=True),
        sa.Column("burn_rate_weekly", sa.Numeric(12, 2), nullable=True),
        sa.Column("burn_rate_monthly", sa.Numeric(12, 2), nullable=True),
        sa.Column("burn_rate_7day_avg", sa.Numeric(12, 2), nullable=True),
        sa.Column("burn_rate_30day_avg", sa.Numeric(12, 2), nullable=True),
        sa.Column("burn_rate_trend", sa.String(20), nullable=True),
        sa.Column("burn_rate_change_pct", sa.Numeric(8, 2), nullable=True),
        sa.Column("projected_depletion_date", sa.Date(), nullable=True),
        sa.Column("projected_period_spend", sa.Numeric(15, 2), nullable=True),
        sa.Column("projected_over_budget", sa.Boolean(), nullable=True),
        sa.Column("spend_increase_alert_pct", sa.Numeric(8, 2), nullable=True),
        sa.Column("budget_remaining_alert_pct", sa.Numeric(8, 2), nullable=True),
        sa.Column("depletion_alert_days", sa.Integer(), nullable=True),
        sa.Column("last_calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    # ── program_budget_alerts (→ program_budgets) ─────────────────────────
    op.create_table(
        "program_budget_alerts",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "program_budget_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("billing.program_budgets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("alert_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metric_value", sa.Numeric(15, 2), nullable=True),
        sa.Column("threshold_value", sa.Numeric(15, 2), nullable=True),
        sa.Column("comparison_value", sa.Numeric(15, 2), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    # ── program_budget_snapshots (→ program_budgets) ──────────────────────
    op.create_table(
        "program_budget_snapshots",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "program_budget_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("billing.program_budgets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("spent_to_date", sa.Numeric(15, 2), nullable=False),
        sa.Column("daily_spend", sa.Numeric(12, 2), nullable=False),
        sa.Column("claim_count", sa.Integer(), nullable=False),
        sa.Column("avg_claim_amount", sa.Numeric(12, 2), nullable=True),
        sa.UniqueConstraint("program_budget_id", "snapshot_date", name="uq_budget_snapshot_date"),
        schema=_SCHEMA,
    )

    # ── fee_configs ───────────────────────────────────────────────────────
    op.create_table(
        "fee_configs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("fee_code", sa.String(50), nullable=False),
        sa.Column("calculation_type", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(12, 4), nullable=True),
        sa.Column("percentage", sa.Numeric(8, 4), nullable=True),
        sa.Column("tiers", sa.JSON(), nullable=True),
        sa.Column("custom_formula", sa.Text(), nullable=True),
        sa.Column("applies_to_programs", sa.JSON(), nullable=True),
        sa.Column("applies_to_claim_types", sa.JSON(), nullable=True),
        sa.Column("applies_to_nrids", sa.JSON(), nullable=True),
        sa.Column("split_rules", sa.JSON(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    # ── funding_configs ───────────────────────────────────────────────────
    op.create_table(
        "funding_configs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("funding_model", sa.String(50), nullable=False),
        sa.Column("prefund_balance", sa.Numeric(15, 2), nullable=True),
        sa.Column("alert_threshold", sa.Numeric(15, 2), nullable=True),
        sa.Column("critical_threshold", sa.Numeric(15, 2), nullable=True),
        sa.Column("funding_bank_account_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    # ── prefund_ledger (→ funding_configs) ────────────────────────────────
    op.create_table(
        "prefund_ledger",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "funding_config_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("billing.funding_configs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_type", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("running_balance", sa.Numeric(15, 2), nullable=False),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("reference_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", pg.UUID(as_uuid=True), nullable=True),
        schema=_SCHEMA,
    )

    # ── remittance_configs ────────────────────────────────────────────────
    op.create_table(
        "remittance_configs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("delivery_method", sa.String(50), nullable=True),
        sa.Column("sftp_config_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("format_type", sa.String(50), nullable=True),
        sa.Column("include_pos_adjustment", sa.Boolean(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    # ── sftp_configs ──────────────────────────────────────────────────────
    op.create_table(
        "sftp_configs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("auth_type", sa.String(20), nullable=True),
        sa.Column("remote_path", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("last_delivery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_delivery_status", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    # ── payment_vendor_configs ────────────────────────────────────────────
    op.create_table(
        "payment_vendor_configs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("vendor_type", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("api_endpoint", sa.String(500), nullable=True),
        sa.Column("api_credentials_ref", sa.String(255), nullable=True),
        sa.Column("file_delivery_method", sa.String(50), nullable=True),
        sa.Column("file_format", sa.String(100), nullable=True),
        sa.Column("settlement_method", sa.String(50), nullable=True),
        sa.Column("expected_settlement_days", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    # ── bank_accounts ─────────────────────────────────────────────────────
    op.create_table(
        "bank_accounts",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("account_name", sa.String(255), nullable=False),
        sa.Column("bank_name", sa.String(255), nullable=False),
        sa.Column("routing_number", sa.String(9), nullable=False),
        sa.Column("account_number", sa.String(17), nullable=False),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("purpose", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    # ── accounting_configs ────────────────────────────────────────────────
    op.create_table(
        "accounting_configs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("system_type", sa.String(50), nullable=False),
        sa.Column("export_format", sa.String(50), nullable=True),
        sa.Column("connection_config", sa.JSON(), nullable=True),
        sa.Column("field_mapping", sa.JSON(), nullable=True),
        sa.Column("class_mapping", sa.JSON(), nullable=True),
        sa.Column("auto_export_ap", sa.Boolean(), nullable=True),
        sa.Column("auto_export_ar", sa.Boolean(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    # ── sequences ─────────────────────────────────────────────────────────
    op.create_table(
        "sequences",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_type", sa.String(50), nullable=False),
        sa.Column("prefix", sa.String(20), nullable=True),
        sa.Column("current_value", sa.Integer(), nullable=False),
        sa.UniqueConstraint("tenant_id", "sequence_type", name="uq_sequence_tenant_type"),
        schema=_SCHEMA,
    )


def downgrade() -> None:
    # Drop in reverse creation order — children before parents

    op.drop_table("sequences", schema=_SCHEMA)
    op.drop_table("accounting_configs", schema=_SCHEMA)
    op.drop_table("bank_accounts", schema=_SCHEMA)
    op.drop_table("payment_vendor_configs", schema=_SCHEMA)
    op.drop_table("sftp_configs", schema=_SCHEMA)
    op.drop_table("remittance_configs", schema=_SCHEMA)
    op.drop_table("prefund_ledger", schema=_SCHEMA)
    op.drop_table("funding_configs", schema=_SCHEMA)
    op.drop_table("fee_configs", schema=_SCHEMA)
    op.drop_table("program_budget_snapshots", schema=_SCHEMA)
    op.drop_table("program_budget_alerts", schema=_SCHEMA)
    op.drop_table("program_budgets", schema=_SCHEMA)

    op.drop_index("idx_journal_exported", table_name="journal_entries", schema=_SCHEMA)
    op.drop_index("idx_journal_category", table_name="journal_entries", schema=_SCHEMA)
    op.drop_index("idx_journal_type", table_name="journal_entries", schema=_SCHEMA)
    op.drop_index("idx_journal_program", table_name="journal_entries", schema=_SCHEMA)
    op.drop_index("idx_journal_client", table_name="journal_entries", schema=_SCHEMA)
    op.drop_index("idx_journal_tenant_date", table_name="journal_entries", schema=_SCHEMA)
    op.drop_table("journal_entries", schema=_SCHEMA)

    op.drop_table("ar_payments", schema=_SCHEMA)
    op.drop_table("ar_records", schema=_SCHEMA)
    op.drop_table("invoice_line_items", schema=_SCHEMA)
    op.drop_table("invoices", schema=_SCHEMA)
    op.drop_table("invoicing_configs", schema=_SCHEMA)
    op.drop_table("payments", schema=_SCHEMA)
    op.drop_table("payment_batches", schema=_SCHEMA)

    op.drop_index("idx_ap_batch", table_name="ap_records", schema=_SCHEMA)
    op.drop_index("idx_ap_client", table_name="ap_records", schema=_SCHEMA)
    op.drop_index("idx_ap_payto", table_name="ap_records", schema=_SCHEMA)
    op.drop_index("idx_ap_tenant_status", table_name="ap_records", schema=_SCHEMA)
    op.drop_table("ap_records", schema=_SCHEMA)

    op.drop_table("file_format_mappings", schema=_SCHEMA)
    op.drop_table("payto_waterfall", schema=_SCHEMA)
    op.drop_table("routing_rules", schema=_SCHEMA)

    op.drop_index("idx_claims_nrid", table_name="claim_records", schema=_SCHEMA)
    op.drop_index("idx_claims_tenant_client", table_name="claim_records", schema=_SCHEMA)
    op.drop_index("idx_claims_tenant_dos", table_name="claim_records", schema=_SCHEMA)
    op.drop_index("idx_claims_tenant_status", table_name="claim_records", schema=_SCHEMA)
    op.drop_table("claim_records", schema=_SCHEMA)
