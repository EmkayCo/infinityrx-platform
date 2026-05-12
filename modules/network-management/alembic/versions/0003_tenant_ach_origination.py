"""network_mgmt Wave 37: tenant_ach_origination — ODFI / originator settings.

Per-tenant NACHA origination configuration. Required to generate
ACH files from payment batches. UNIQUE on tenant_id + active row
because at any moment a tenant has one originator. Historical rows
remain via termination_date.

Revision ID: 0003_tenant_ach_origination
Revises: 0002_network_mgmt_rls
Create Date: 2026-04-25
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import os

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_tenant_ach_origination"
down_revision: Union[str, None] = "0002_network_mgmt_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "network_mgmt"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")


def upgrade() -> None:
    op.create_table(
        "tenant_ach_origination",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("immediate_destination", sa.String(10), nullable=False),
        sa.Column("immediate_destination_name", sa.String(23), nullable=False),
        sa.Column("immediate_origin", sa.String(10), nullable=False),
        sa.Column("immediate_origin_name", sa.String(23), nullable=False),
        sa.Column("originating_dfi_id", sa.String(8), nullable=False),
        sa.Column("company_name", sa.String(16), nullable=False),
        sa.Column("company_identification", sa.String(10), nullable=False),
        sa.Column("company_entry_description", sa.String(10), nullable=False),
        sa.Column("company_descriptive_date", sa.String(6), nullable=True),
        sa.Column(
            "effective_entry_date_offset_days", sa.Integer(),
            nullable=False, server_default=sa.text("1"),
        ),
        sa.Column(
            "service_class_code", sa.String(3),
            nullable=False, server_default=sa.text("'220'"),
        ),
        sa.Column(
            "file_id_modifier_seed", sa.String(1),
            nullable=False, server_default=sa.text("'A'"),
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        # Format constraints (NACHA spec)
        sa.CheckConstraint(
            # 10 chars: leading-space + 9 digits, OR 10 digits.
            "immediate_destination ~ '^[ ]?[0-9]{9}$' OR immediate_destination ~ '^[0-9]{10}$'",
            name="ck_nm_ach_imm_dest_format",
        ),
        sa.CheckConstraint(
            # immediate_origin: typically '1' + 9-digit TIN. Allow
            # leading space + 9 digits OR 10-char numeric.
            "immediate_origin ~ '^[ 1][0-9]{9}$' OR immediate_origin ~ '^[0-9]{10}$'",
            name="ck_nm_ach_imm_origin_format",
        ),
        sa.CheckConstraint(
            "originating_dfi_id ~ '^[0-9]{8}$'",
            name="ck_nm_ach_odfi_format",
        ),
        sa.CheckConstraint(
            "service_class_code IN ('200', '220', '225')",
            name="ck_nm_ach_service_class",
        ),
        sa.CheckConstraint(
            "file_id_modifier_seed ~ '^[A-Z0-9]$'",
            name="ck_nm_ach_file_id_seed",
        ),
        sa.CheckConstraint(
            "effective_entry_date_offset_days >= 0",
            name="ck_nm_ach_eed_offset_nonneg",
        ),
        sa.CheckConstraint(
            "termination_date IS NULL OR termination_date >= effective_from",
            name="ck_nm_ach_period_order",
        ),
        sa.CheckConstraint(
            "company_descriptive_date IS NULL OR company_descriptive_date ~ '^[0-9]{6}$'",
            name="ck_nm_ach_desc_date_format",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_nm_ach_orig_tenant",
        "tenant_ach_origination", ["tenant_id"],
        schema=_SCHEMA,
    )
    # Only one active origination row per tenant.
    op.execute(
        f"CREATE UNIQUE INDEX uq_nm_ach_orig_one_active_per_tenant "
        f"ON {_SCHEMA}.tenant_ach_origination (tenant_id) "
        f"WHERE termination_date IS NULL"
    )

    # RLS
    op.execute(
        f"ALTER TABLE {_SCHEMA}.tenant_ach_origination ENABLE ROW LEVEL SECURITY;"
    )
    op.execute(
        f"ALTER TABLE {_SCHEMA}.tenant_ach_origination FORCE ROW LEVEL SECURITY;"
    )
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {_SCHEMA}.tenant_ach_origination
          FOR ALL
          TO ifx_dev_app, {_APP_ROLE}
          USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
        """
    )

    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {_SCHEMA}.tenant_ach_origination "
        f"TO ifx_dev_app, {_APP_ROLE}, ifx_dev_admin, ifx_prod_admin"
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {_SCHEMA}.tenant_ach_origination;")
    op.drop_table("tenant_ach_origination", schema=_SCHEMA)
