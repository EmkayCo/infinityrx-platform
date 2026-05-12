"""network_mgmt baseline — 8 tables for the contract + money-routing layer.

Tables:
  1. pay_to_entities                 — pharmacy NPI / chain code / pay center entities
  2. banking                         — encrypted account number per pay-to entity
  3. contracts                       — direct / PSAO contract types
  4. pay_center_routing              — NPI → pay center coverage
  5. chain_membership                — NPI → chain code association
  6. eight_thirty_five_destinations  — SFTP / email / portal / paper delivery
  7. statement_account_flags         — manufacturer-handled credits, bypass payment
  8. banking_change_log              — append-only audit log

Constraints:
  - One active banking row per pay_to_entity_id (partial unique
    where termination_date IS NULL)
  - One active pay_center_routing per (tenant, covered_npi)
    (partial unique)
  - One active chain_membership per (tenant, npi)
    (partial unique)
  - One active statement_account_flag per (tenant, group, npi)
    (partial unique)
  - status, entity_type, account_type, source, change_type,
    delivery_method, contract_type CHECKed against canonical sets

Money: NONE. This module routes; paysync owns amounts.

RLS deferred to 0002.

Revision ID: 0001_network_mgmt_baseline
Revises:
Create Date: 2026-04-25
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import os

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_network_mgmt_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "network_mgmt"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    # ── 1. pay_to_entities ─────────────────────────────────────────
    op.create_table(
        "pay_to_entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("legal_business_name", sa.String(255), nullable=False),
        sa.Column("dba_name", sa.String(255), nullable=True),
        sa.Column("federal_tax_id", sa.String(9), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'active'")),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id", "entity_type", "external_id",
            name="uq_nm_entity_tenant_type_extid",
        ),
        sa.CheckConstraint(
            "entity_type IN ('pharmacy_npi', 'chain_code', 'pay_center', 'manufacturer')",
            name="ck_nm_entity_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'pending_credentialing')",
            name="ck_nm_entity_status",
        ),
        sa.CheckConstraint(
            "termination_date IS NULL OR termination_date >= effective_from",
            name="ck_nm_entity_period_order",
        ),
        schema=_SCHEMA,
    )
    op.create_index("ix_nm_entity_tenant", "pay_to_entities", ["tenant_id"], schema=_SCHEMA)
    op.create_index("ix_nm_entity_status", "pay_to_entities", ["tenant_id", "status"], schema=_SCHEMA)

    # ── 2. banking ─────────────────────────────────────────────────
    op.create_table(
        "banking",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "pay_to_entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.pay_to_entities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("routing_number", sa.String(9), nullable=False),
        sa.Column("account_number_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("account_number_last_four", sa.String(4), nullable=False),
        sa.Column("account_type", sa.String(32), nullable=False),
        sa.Column("bank_name", sa.String(120), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "account_type IN ('checking', 'savings', 'business_checking', 'business_savings')",
            name="ck_nm_banking_acct_type",
        ),
        sa.CheckConstraint(
            "source IN ('operator_entered', 'imported', 'pharmacy_portal')",
            name="ck_nm_banking_source",
        ),
        sa.CheckConstraint(
            "length(routing_number) = 9 AND routing_number ~ '^[0-9]{9}$'",
            name="ck_nm_banking_rtn_format",
        ),
        sa.CheckConstraint(
            "length(account_number_last_four) = 4 AND account_number_last_four ~ '^[0-9]{4}$'",
            name="ck_nm_banking_last4_format",
        ),
        sa.CheckConstraint(
            "termination_date IS NULL OR termination_date >= effective_from",
            name="ck_nm_banking_period_order",
        ),
        schema=_SCHEMA,
    )
    op.create_index("ix_nm_banking_entity", "banking", ["pay_to_entity_id"], schema=_SCHEMA)
    op.create_index("ix_nm_banking_tenant", "banking", ["tenant_id"], schema=_SCHEMA)
    op.execute(
        f"CREATE UNIQUE INDEX uq_nm_banking_one_active_per_entity "
        f"ON {_SCHEMA}.banking (pay_to_entity_id) "
        f"WHERE termination_date IS NULL"
    )

    # ── 3. contracts ───────────────────────────────────────────────
    op.create_table(
        "contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "pay_to_entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.pay_to_entities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("contract_type", sa.String(64), nullable=False),
        sa.Column("rate_negotiation_terms", postgresql.JSONB(), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "contract_type IN ("
            "'direct', "
            "'psao_full_payment_and_reconciliation', "
            "'psao_reconciliation_only', "
            "'standalone_reconciliation_vendor')",
            name="ck_nm_contract_type",
        ),
        sa.CheckConstraint(
            "termination_date IS NULL OR termination_date >= effective_from",
            name="ck_nm_contract_period_order",
        ),
        schema=_SCHEMA,
    )
    op.create_index("ix_nm_contracts_entity", "contracts", ["pay_to_entity_id"], schema=_SCHEMA)
    op.create_index("ix_nm_contracts_tenant", "contracts", ["tenant_id"], schema=_SCHEMA)

    # ── 4. pay_center_routing ─────────────────────────────────────
    op.create_table(
        "pay_center_routing",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "pay_center_entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.pay_to_entities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("covered_npi", sa.String(10), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "length(covered_npi) = 10 AND covered_npi ~ '^[0-9]{10}$'",
            name="ck_nm_paycenter_npi_format",
        ),
        sa.CheckConstraint(
            "termination_date IS NULL OR termination_date >= effective_from",
            name="ck_nm_paycenter_period_order",
        ),
        schema=_SCHEMA,
    )
    op.create_index("ix_nm_pay_center_pcid", "pay_center_routing", ["pay_center_entity_id"], schema=_SCHEMA)
    op.create_index(
        "ix_nm_pay_center_npi", "pay_center_routing",
        ["tenant_id", "covered_npi"], schema=_SCHEMA,
    )
    op.execute(
        f"CREATE UNIQUE INDEX uq_nm_pay_center_one_active_per_npi "
        f"ON {_SCHEMA}.pay_center_routing (tenant_id, covered_npi, effective_from) "
        f"WHERE termination_date IS NULL"
    )

    # ── 5. chain_membership ───────────────────────────────────────
    op.create_table(
        "chain_membership",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("npi", sa.String(10), nullable=False),
        sa.Column("chain_code", sa.String(20), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "length(npi) = 10 AND npi ~ '^[0-9]{10}$'",
            name="ck_nm_chain_npi_format",
        ),
        sa.CheckConstraint(
            "termination_date IS NULL OR termination_date >= effective_from",
            name="ck_nm_chain_period_order",
        ),
        schema=_SCHEMA,
    )
    op.create_index("ix_nm_chain_npi", "chain_membership", ["tenant_id", "npi"], schema=_SCHEMA)
    op.create_index("ix_nm_chain_code", "chain_membership", ["tenant_id", "chain_code"], schema=_SCHEMA)
    op.execute(
        f"CREATE UNIQUE INDEX uq_nm_chain_one_active_per_npi "
        f"ON {_SCHEMA}.chain_membership (tenant_id, npi, effective_from) "
        f"WHERE termination_date IS NULL"
    )

    # ── 6. eight_thirty_five_destinations ─────────────────────────
    op.create_table(
        "eight_thirty_five_destinations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "pay_to_entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.pay_to_entities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("delivery_method", sa.String(32), nullable=False),
        sa.Column("sftp_host", sa.String(255), nullable=True),
        sa.Column("sftp_port", sa.Integer(), nullable=True),
        sa.Column("sftp_username", sa.String(120), nullable=True),
        sa.Column("sftp_password_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("sftp_path", sa.String(512), nullable=True),
        sa.Column("email_address", sa.String(255), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "delivery_method IN ('sftp', 'email', 'portal_pickup', 'paper_check')",
            name="ck_nm_835_delivery_method",
        ),
        sa.CheckConstraint(
            "termination_date IS NULL OR termination_date >= effective_from",
            name="ck_nm_835_period_order",
        ),
        sa.CheckConstraint(
            # SFTP requires host + username; email requires email_address.
            "(delivery_method <> 'sftp' OR (sftp_host IS NOT NULL AND sftp_username IS NOT NULL)) "
            "AND (delivery_method <> 'email' OR email_address IS NOT NULL)",
            name="ck_nm_835_method_fields_present",
        ),
        schema=_SCHEMA,
    )
    op.create_index("ix_nm_835_entity", "eight_thirty_five_destinations", ["pay_to_entity_id"], schema=_SCHEMA)
    op.create_index("ix_nm_835_tenant", "eight_thirty_five_destinations", ["tenant_id"], schema=_SCHEMA)

    # ── 7. statement_account_flags ────────────────────────────────
    op.create_table(
        "statement_account_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("manufacturer_group_id", sa.String(64), nullable=False),
        sa.Column("pharmacy_npi", sa.String(10), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "length(pharmacy_npi) = 10 AND pharmacy_npi ~ '^[0-9]{10}$'",
            name="ck_nm_stmt_npi_format",
        ),
        sa.CheckConstraint(
            "termination_date IS NULL OR termination_date >= effective_from",
            name="ck_nm_stmt_period_order",
        ),
        schema=_SCHEMA,
    )
    op.create_index("ix_nm_stmt_group", "statement_account_flags", ["tenant_id", "manufacturer_group_id"], schema=_SCHEMA)
    op.create_index("ix_nm_stmt_npi", "statement_account_flags", ["tenant_id", "pharmacy_npi"], schema=_SCHEMA)
    op.execute(
        f"CREATE UNIQUE INDEX uq_nm_stmt_acct_active "
        f"ON {_SCHEMA}.statement_account_flags "
        f"(tenant_id, manufacturer_group_id, pharmacy_npi, effective_from) "
        f"WHERE termination_date IS NULL"
    )

    # ── 8. banking_change_log ─────────────────────────────────────
    op.create_table(
        "banking_change_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "pay_to_entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.pay_to_entities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("banking_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("change_type", sa.String(32), nullable=False),
        sa.Column("old_routing_last_four", sa.String(4), nullable=True),
        sa.Column("new_routing_last_four", sa.String(4), nullable=True),
        sa.Column("old_account_last_four", sa.String(4), nullable=True),
        sa.Column("new_account_last_four", sa.String(4), nullable=True),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "change_type IN ('created', 'updated', 'verified', 'terminated')",
            name="ck_nm_blog_change_type",
        ),
        sa.CheckConstraint(
            "source IN ('operator_entered', 'imported', 'pharmacy_portal')",
            name="ck_nm_blog_source",
        ),
        schema=_SCHEMA,
    )
    op.create_index("ix_nm_blog_entity", "banking_change_log", ["pay_to_entity_id"], schema=_SCHEMA)
    op.create_index("ix_nm_blog_tenant", "banking_change_log", ["tenant_id"], schema=_SCHEMA)
    op.create_index(
        "ix_nm_blog_changed", "banking_change_log",
        ["tenant_id", "created_at"], schema=_SCHEMA,
    )

    # GRANTs
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
    op.drop_table("banking_change_log", schema=_SCHEMA)
    op.drop_table("statement_account_flags", schema=_SCHEMA)
    op.drop_table("eight_thirty_five_destinations", schema=_SCHEMA)
    op.drop_table("chain_membership", schema=_SCHEMA)
    op.drop_table("pay_center_routing", schema=_SCHEMA)
    op.drop_table("contracts", schema=_SCHEMA)
    op.drop_table("banking", schema=_SCHEMA)
    op.drop_table("pay_to_entities", schema=_SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA}")
