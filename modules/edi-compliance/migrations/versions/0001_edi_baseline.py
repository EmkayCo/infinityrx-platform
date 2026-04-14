"""EDI compliance module baseline schema

Revision ID: 0001_edi_baseline
Revises:
Create Date: 2026-04-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_edi_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS edi")

    op.create_table(
        "trading_partners",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("partner_type", sa.String(50), nullable=False),
        sa.Column("isa_qualifier", sa.String(2), nullable=False),
        sa.Column("isa_id", sa.String(15), nullable=False),
        sa.Column("gs_id", sa.String(15), nullable=True),
        sa.Column("supported_transactions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("transport_type", sa.String(50), nullable=False),
        sa.Column("transport_config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("test_mode", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("companion_guide_ref", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="edi",
    )
    op.create_index("ix_edi_trading_partners_tenant", "trading_partners", ["tenant_id"], schema="edi")
    op.create_index("ix_edi_trading_partners_active", "trading_partners", ["tenant_id", "is_active"], schema="edi")

    op.create_table(
        "control_number_sequences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trading_partner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_type", sa.String(10), nullable=False),
        sa.Column("current_value", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("max_value", sa.BigInteger(), nullable=False, server_default="999999999"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "trading_partner_id", "sequence_type",
                            name="uq_control_number_sequences_scope"),
        schema="edi",
    )

    op.create_table(
        "transaction_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trading_partner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("transaction_type", sa.String(10), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("file_name", sa.String(500), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("isa_control_number", sa.String(9), nullable=True),
        sa.Column("gs_control_number", sa.String(9), nullable=True),
        sa.Column("transmission_status", sa.String(50), nullable=False, server_default="'pending'"),
        sa.Column("ack_status", sa.String(50), nullable=True),
        sa.Column("ack_control_number", sa.String(9), nullable=True),
        sa.Column("transmission_date", sa.String(10), nullable=True),
        sa.Column("ack_date", sa.String(10), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("raw_content_ref", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["trading_partner_id"], ["edi.trading_partners.id"]),
        schema="edi",
    )
    op.create_index("ix_edi_transaction_files_tenant_status",
                    "transaction_files", ["tenant_id", "transmission_status"], schema="edi")
    op.create_index("ix_edi_transaction_files_tenant_type",
                    "transaction_files", ["tenant_id", "transaction_type"], schema="edi")

    op.create_table(
        "transaction_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("transaction_type", sa.String(10), nullable=False),
        sa.Column("st_control_number", sa.String(9), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="'pending'"),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["file_id"], ["edi.transaction_files.id"]),
        schema="edi",
    )
    op.create_index("ix_edi_transaction_records_tenant_status",
                    "transaction_records", ["tenant_id", "status"], schema="edi")

    op.create_table(
        "compliance_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("check_type", sa.String(50), nullable=False),
        sa.Column("check_level", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column("segment_id", sa.String(10), nullable=True),
        sa.Column("element_position", sa.Integer(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["file_id"], ["edi.transaction_files.id"]),
        schema="edi",
    )
    op.create_index("ix_edi_compliance_log_tenant_check",
                    "compliance_log", ["tenant_id", "check_type"], schema="edi")

    op.create_table(
        "payer_companion_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trading_partner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("transaction_type", sa.String(10), nullable=False),
        sa.Column("rule_name", sa.String(255), nullable=False),
        sa.Column("rule_type", sa.String(50), nullable=False),
        sa.Column("segment_id", sa.String(10), nullable=True),
        sa.Column("element_position", sa.Integer(), nullable=True),
        sa.Column("required_value", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["trading_partner_id"], ["edi.trading_partners.id"]),
        schema="edi",
    )
    op.create_index("ix_edi_payer_companion_rules_partner",
                    "payer_companion_rules", ["tenant_id", "trading_partner_id"], schema="edi")

    op.create_table(
        "trading_partner_agreements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trading_partner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_type", sa.String(10), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("implementation_guide", sa.String(50), nullable=True),
        sa.Column("test_mode", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("effective_date", sa.String(10), nullable=True),
        sa.Column("termination_date", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["trading_partner_id"], ["edi.trading_partners.id"]),
        schema="edi",
    )

    op.create_table(
        "as2_certificates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trading_partner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("certificate_type", sa.String(50), nullable=False),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("thumbprint", sa.String(128), nullable=True),
        sa.Column("expiry_date", sa.String(10), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["trading_partner_id"], ["edi.trading_partners.id"]),
        schema="edi",
    )
    op.create_index("ix_edi_as2_certificates_partner",
                    "as2_certificates", ["tenant_id", "trading_partner_id"], schema="edi")


def downgrade() -> None:
    op.drop_table("as2_certificates", schema="edi")
    op.drop_table("trading_partner_agreements", schema="edi")
    op.drop_table("payer_companion_rules", schema="edi")
    op.drop_table("compliance_log", schema="edi")
    op.drop_table("transaction_records", schema="edi")
    op.drop_table("transaction_files", schema="edi")
    op.drop_table("control_number_sequences", schema="edi")
    op.drop_table("trading_partners", schema="edi")
    op.execute("DROP SCHEMA IF EXISTS edi")
