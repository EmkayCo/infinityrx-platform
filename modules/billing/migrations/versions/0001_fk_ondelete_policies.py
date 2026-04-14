"""Add explicit ondelete= constraints to billing FK columns

Revision ID: 0001_fk_ondelete_policies
Revises: None
Create Date: 2026-04-14 00:00:00.000000

M-07: No ondelete= specified on any ForeignKey in billing — RESTRICT intent
was undocumented. This migration makes the intent explicit at the DB level.

Constraint policies:
  - Child financial records → parent batch/record: RESTRICT (never cascade delete money)
  - Invoice → invoicing_config: SET NULL (config is soft-deleted, not cascaded)
  - Invoice line items → invoice: RESTRICT
  - AR payment events → AR record: RESTRICT
  - Budget alerts/snapshots → program_budget: RESTRICT
  - Funding ledger entries → funding_config: RESTRICT
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_fk_ondelete_policies"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "billing"


def _drop_and_recreate(
    table: str,
    col: str,
    constraint_name: str,
    ref: str,
    ondelete: str,
) -> None:
    """Helper: drop old FK constraint, add new one with explicit ondelete."""
    op.drop_constraint(constraint_name, table, schema=SCHEMA, type_="foreignkey")
    op.create_foreign_key(
        constraint_name,
        table,
        ref.split(".")[0],  # ref table (within same schema)
        [col],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete=ondelete,
    )


def upgrade() -> None:
    # ap_records.claim_record_id → claim_records.id (RESTRICT)
    _drop_and_recreate(
        "ap_records", "claim_record_id",
        "ap_records_claim_record_id_fkey",
        "claim_records.id", "RESTRICT",
    )

    # payments.payment_batch_id → payment_batches.id (RESTRICT)
    _drop_and_recreate(
        "payments", "payment_batch_id",
        "payments_payment_batch_id_fkey",
        "payment_batches.id", "RESTRICT",
    )

    # invoices.invoicing_config_id → invoicing_configs.id (SET NULL)
    _drop_and_recreate(
        "invoices", "invoicing_config_id",
        "invoices_invoicing_config_id_fkey",
        "invoicing_configs.id", "SET NULL",
    )

    # invoice_line_items.invoice_id → invoices.id (RESTRICT)
    _drop_and_recreate(
        "invoice_line_items", "invoice_id",
        "invoice_line_items_invoice_id_fkey",
        "invoices.id", "RESTRICT",
    )

    # ar_payment_events.ar_record_id → ar_records.id (RESTRICT)
    _drop_and_recreate(
        "ar_payment_events", "ar_record_id",
        "ar_payment_events_ar_record_id_fkey",
        "ar_records.id", "RESTRICT",
    )

    # budget_alerts.program_budget_id → program_budgets.id (RESTRICT)
    _drop_and_recreate(
        "budget_alerts", "program_budget_id",
        "budget_alerts_program_budget_id_fkey",
        "program_budgets.id", "RESTRICT",
    )

    # budget_snapshots.program_budget_id → program_budgets.id (RESTRICT)
    _drop_and_recreate(
        "budget_snapshots", "program_budget_id",
        "budget_snapshots_program_budget_id_fkey",
        "program_budgets.id", "RESTRICT",
    )

    # funding_ledger_entries.funding_config_id → funding_configs.id (RESTRICT)
    _drop_and_recreate(
        "funding_ledger_entries", "funding_config_id",
        "funding_ledger_entries_funding_config_id_fkey",
        "funding_configs.id", "RESTRICT",
    )


def downgrade() -> None:
    # Remove explicit ondelete= (revert to DB default RESTRICT behavior — functionally equivalent)
    # Drop and re-add constraints without ondelete= to match original state
    for table, col, constraint, ref in [
        ("ap_records", "claim_record_id", "ap_records_claim_record_id_fkey", "claim_records"),
        ("payments", "payment_batch_id", "payments_payment_batch_id_fkey", "payment_batches"),
        ("invoices", "invoicing_config_id", "invoices_invoicing_config_id_fkey", "invoicing_configs"),
        ("invoice_line_items", "invoice_id", "invoice_line_items_invoice_id_fkey", "invoices"),
        ("ar_payment_events", "ar_record_id", "ar_payment_events_ar_record_id_fkey", "ar_records"),
        ("budget_alerts", "program_budget_id", "budget_alerts_program_budget_id_fkey", "program_budgets"),
        ("budget_snapshots", "program_budget_id", "budget_snapshots_program_budget_id_fkey", "program_budgets"),
        ("funding_ledger_entries", "funding_config_id", "funding_ledger_entries_funding_config_id_fkey", "funding_configs"),
    ]:
        op.drop_constraint(constraint, table, schema=SCHEMA, type_="foreignkey")
        op.create_foreign_key(
            constraint, table, ref, [col], ["id"],
            source_schema=SCHEMA, referent_schema=SCHEMA,
        )
