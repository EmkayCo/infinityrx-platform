"""paysync baseline — schema + foundation tables for Wave 35.

Tables created:
  1. import_runs                       (one row per file ingest)
  2. import_run_errors                 (per-row failures from ingest)
  3. import_field_mapping_profiles     (operator-configurable column maps)
  4. cycles                            (payment/billing periods)
  5. claims                            (post-adjudication tabular records)
  6. nrid_channel_mappings             (NRID → channel routing)
  7. client_special_rules              (per-client routing overrides)

All seven tables are tenant-scoped. Check constraints + RLS are
applied in 0002_paysync_rls.

Money columns are NUMERIC(12,2) (claims) or NUMERIC(14,2) (cycles
aggregates). Quantity is NUMERIC(10,3).

Revision ID: 0001_paysync_baseline
Revises:
Create Date: 2026-04-25
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import os

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_paysync_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "paysync"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    # ── 1. import_runs ──
    op.create_table(
        "import_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_filename", sa.String(512), nullable=False),
        sa.Column("source_format", sa.String(32), nullable=False),
        sa.Column("source_column_count", sa.Integer(), nullable=True),
        sa.Column(
            "source_field_mapping",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("profile_name", sa.String(120), nullable=True),
        sa.Column("rows_imported", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rows_skipped", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rows_errored", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'in_progress'")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed', 'failed')",
            name="ck_paysync_import_runs_status",
        ),
        sa.CheckConstraint(
            "rows_imported >= 0 AND rows_skipped >= 0 AND rows_errored >= 0",
            name="ck_paysync_import_runs_counts_nonneg",
        ),
        schema=_SCHEMA,
    )
    op.create_index("ix_paysync_import_runs_tenant", "import_runs", ["tenant_id"], schema=_SCHEMA)
    op.create_index(
        "ix_paysync_import_runs_started_at",
        "import_runs",
        ["tenant_id", "started_at"],
        schema=_SCHEMA,
    )

    # ── 2. import_run_errors ──
    op.create_table(
        "import_run_errors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "import_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.import_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("error_type", sa.String(64), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("source_row", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("row_number >= 0", name="ck_paysync_import_errors_rownum_nonneg"),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_import_errors_run",
        "import_run_errors",
        ["import_run_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_import_errors_tenant",
        "import_run_errors",
        ["tenant_id"],
        schema=_SCHEMA,
    )

    # ── 3. import_field_mapping_profiles ──
    op.create_table(
        "import_field_mapping_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_name", sa.String(120), nullable=False),
        sa.Column("delimiter", sa.String(4), nullable=False),
        sa.Column("line_ending", sa.String(8), nullable=False, server_default=sa.text("E'\\n'")),
        sa.Column("has_header", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "column_mappings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "profile_name", name="uq_paysync_profile_name"),
        sa.CheckConstraint(
            "jsonb_typeof(column_mappings) = 'array'",
            name="ck_paysync_profile_mappings_is_array",
        ),
        schema=_SCHEMA,
    )
    op.create_index("ix_paysync_profiles_tenant", "import_field_mapping_profiles", ["tenant_id"], schema=_SCHEMA)

    # ── 4. cycles ──
    op.create_table(
        "cycles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cycle_label", sa.String(64), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'open'")),
        sa.Column("claim_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_pay_sum", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("client_billed_sum", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invoiced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("tenant_id", "cycle_label", name="uq_paysync_cycle_label"),
        sa.CheckConstraint(
            "status IN ('open', 'closed', 'invoiced', 'paid', 'reconciled')",
            name="ck_paysync_cycles_status",
        ),
        sa.CheckConstraint("period_end >= period_start", name="ck_paysync_cycles_period_order"),
        sa.CheckConstraint("claim_count >= 0", name="ck_paysync_cycles_count_nonneg"),
        schema=_SCHEMA,
    )
    op.create_index("ix_paysync_cycles_status", "cycles", ["tenant_id", "status"], schema=_SCHEMA)
    op.create_index(
        "ix_paysync_cycles_period",
        "cycles",
        ["tenant_id", "period_start", "period_end"],
        schema=_SCHEMA,
    )

    # ── 5. claims ──
    op.create_table(
        "claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "import_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.import_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("auth_num", sa.String(64), nullable=False),
        sa.Column("transaction_id", sa.String(64), nullable=True),
        sa.Column("claim_status", sa.String(32), nullable=True),
        sa.Column("date_of_service", sa.Date(), nullable=True),
        sa.Column("adjudication_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cycle_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.cycles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Payment routing
        sa.Column("pay_to_id", sa.String(64), nullable=True),
        sa.Column("pay_to_name", sa.String(255), nullable=True),
        sa.Column("pay_to_account_number", sa.String(64), nullable=True),
        sa.Column("pay_to_routing_number", sa.String(16), nullable=True),
        sa.Column("pay_to_fed_tin", sa.String(16), nullable=True),
        sa.Column("pay_to_file_media", sa.String(8), nullable=True),
        sa.Column("chain_code", sa.String(32), nullable=True),
        sa.Column("chain_name", sa.String(255), nullable=True),
        # Pharmacy
        sa.Column("pharmacy_ncpdp", sa.String(16), nullable=True),
        sa.Column("pharmacy_npi", sa.String(10), nullable=True),
        sa.Column("pharmacy_name", sa.String(255), nullable=True),
        # Client / drug
        sa.Column("group_number", sa.String(64), nullable=True),
        sa.Column("group_id", sa.String(64), nullable=True),
        sa.Column("group_name", sa.String(255), nullable=True),
        sa.Column("ndc", sa.String(11), nullable=True),
        sa.Column("rx_number", sa.String(32), nullable=True),
        # Member
        sa.Column("member_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("member_chid", sa.String(64), nullable=True),
        # Money
        sa.Column("total_pay", sa.Numeric(12, 2), nullable=True),
        sa.Column("client_billed", sa.Numeric(12, 2), nullable=True),
        sa.Column("quantity_dispensed", sa.Numeric(10, 3), nullable=True),
        # Routing keys
        sa.Column("network_reimbursement_id", sa.String(64), nullable=True),
        sa.Column(
            "exempt_from_payables",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "exempt_from_receivables",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        # Adjustments
        sa.Column("transaction_pay_to_adjustment_id", sa.String(64), nullable=True),
        sa.Column("transaction_amount_adjustment_id", sa.String(64), nullable=True),
        # Fees
        sa.Column("pharmacy_fee", sa.Numeric(12, 2), nullable=True),
        sa.Column("pharmacy_admin_fee", sa.Numeric(12, 2), nullable=True),
        sa.Column("other_fees", postgresql.JSONB(), nullable=True),
        # Reversal linkage
        sa.Column("reversed_auth_num", sa.String(64), nullable=True),
        # Channel resolution
        sa.Column("payment_channel", sa.String(64), nullable=True),
        sa.Column("channel_resolved_at", sa.DateTime(timezone=True), nullable=True),
        # Raw retained
        sa.Column("source_row", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "auth_num", name="uq_paysync_claim_tenant_auth"),
        sa.CheckConstraint(
            "quantity_dispensed IS NULL OR quantity_dispensed >= 0",
            name="ck_paysync_claims_qty_nonneg",
        ),
        sa.CheckConstraint(
            "pharmacy_npi IS NULL OR length(pharmacy_npi) = 10",
            name="ck_paysync_claims_npi_len",
        ),
        sa.CheckConstraint(
            "ndc IS NULL OR length(ndc) BETWEEN 9 AND 11",
            name="ck_paysync_claims_ndc_len",
        ),
        schema=_SCHEMA,
    )
    op.create_index("ix_paysync_claims_auth", "claims", ["tenant_id", "auth_num"], schema=_SCHEMA)
    op.create_index("ix_paysync_claims_pay_to", "claims", ["tenant_id", "pay_to_id"], schema=_SCHEMA)
    op.create_index(
        "ix_paysync_claims_nrid",
        "claims",
        ["tenant_id", "network_reimbursement_id"],
        schema=_SCHEMA,
    )
    op.create_index("ix_paysync_claims_ndc", "claims", ["tenant_id", "ndc"], schema=_SCHEMA)
    op.create_index("ix_paysync_claims_group", "claims", ["tenant_id", "group_id"], schema=_SCHEMA)
    op.create_index("ix_paysync_claims_npi", "claims", ["tenant_id", "pharmacy_npi"], schema=_SCHEMA)
    op.create_index("ix_paysync_claims_member", "claims", ["tenant_id", "member_id"], schema=_SCHEMA)
    op.create_index("ix_paysync_claims_cycle", "claims", ["tenant_id", "cycle_id"], schema=_SCHEMA)
    op.create_index("ix_paysync_claims_dos", "claims", ["tenant_id", "date_of_service"], schema=_SCHEMA)
    op.create_index("ix_paysync_claims_reversed", "claims", ["tenant_id", "reversed_auth_num"], schema=_SCHEMA)
    op.create_index("ix_paysync_claims_import_run", "claims", ["import_run_id"], schema=_SCHEMA)

    # ── 6. nrid_channel_mappings ──
    op.create_table(
        "nrid_channel_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("nrid", sa.String(64), nullable=True),
        sa.Column("nrid_pattern", sa.String(64), nullable=True),
        sa.Column("channel", sa.String(64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "(nrid IS NOT NULL) <> (nrid_pattern IS NOT NULL)",
            name="ck_paysync_nrid_exact_xor_pattern",
        ),
        sa.CheckConstraint(
            "termination_date IS NULL OR termination_date >= effective_from",
            name="ck_paysync_nrid_period_order",
        ),
        schema=_SCHEMA,
    )
    op.create_index("ix_paysync_nrid_tenant", "nrid_channel_mappings", ["tenant_id"], schema=_SCHEMA)
    op.create_index(
        "ix_paysync_nrid_active",
        "nrid_channel_mappings",
        ["tenant_id", "nrid", "termination_date"],
        schema=_SCHEMA,
    )

    # ── 7. client_special_rules ──
    op.create_table(
        "client_special_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_match", sa.String(120), nullable=False),
        sa.Column("client_match_field", sa.String(32), nullable=False, server_default=sa.text("'group_id'")),
        sa.Column("rule_type", sa.String(64), nullable=False),
        sa.Column(
            "parameters",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "termination_date IS NULL OR termination_date >= effective_from",
            name="ck_paysync_csr_period_order",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(parameters) = 'object'",
            name="ck_paysync_csr_parameters_is_object",
        ),
        schema=_SCHEMA,
    )
    op.create_index("ix_paysync_csr_tenant", "client_special_rules", ["tenant_id"], schema=_SCHEMA)
    op.create_index(
        "ix_paysync_csr_client",
        "client_special_rules",
        ["tenant_id", "client_match"],
        schema=_SCHEMA,
    )

    # GRANTs to tier app + admin roles. Mock left out — dormant per CLAUDE.md.
    op.execute(f"GRANT USAGE ON SCHEMA {_SCHEMA} TO ifx_dev_app, {_APP_ROLE}, ifx_dev_admin, ifx_prod_admin")
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
    op.drop_table("client_special_rules", schema=_SCHEMA)
    op.drop_table("nrid_channel_mappings", schema=_SCHEMA)
    op.drop_table("claims", schema=_SCHEMA)
    op.drop_table("cycles", schema=_SCHEMA)
    op.drop_table("import_field_mapping_profiles", schema=_SCHEMA)
    op.drop_table("import_run_errors", schema=_SCHEMA)
    op.drop_table("import_runs", schema=_SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA}")
