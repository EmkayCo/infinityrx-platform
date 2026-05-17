"""SP-1 Plan C Task 1 -- propagate upload_id FK onto derived billing entities.

Adds:
  - billing.payment_batches.upload_id   NULLABLE FK to billing.uploads.id
  - billing.invoice_line_items.upload_id NULLABLE FK to billing.uploads.id
  - billing.carryovers table (new -- AP carryforward with upload provenance)
  - Indexes on each new upload_id column
  - RLS policy on billing.carryovers (matches 0002/0003 canonical shape)

Migration is reversible: downgrade drops in reverse order.

Both FK columns are nullable so existing rows (ingested before this migration)
remain valid. The service layer must set upload_id for any new record created
from an upload-originated source.

Revision ID: 0004_propagate_upload_id
Revises: 0003_add_upload_resource
Create Date: 2026-05-17
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0004_propagate_upload_id"
down_revision: Union[str, None] = "0003_add_upload_resource"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "billing"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_TENANT_ROLES = f"ifx_dev_app, ifx_mock_app, {_APP_ROLE}"


def upgrade() -> None:
    # 1. Add upload_id FK to billing.payment_batches
    op.add_column(
        "payment_batches",
        sa.Column("upload_id", pg.UUID(as_uuid=True), nullable=True),
        schema=_SCHEMA,
    )
    op.create_foreign_key(
        "fk_payment_batches_upload",
        "payment_batches",
        "uploads",
        ["upload_id"],
        ["id"],
        source_schema=_SCHEMA,
        referent_schema=_SCHEMA,
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_payment_batches_upload",
        "payment_batches",
        ["upload_id"],
        schema=_SCHEMA,
    )

    # 2. Add upload_id FK to billing.invoice_line_items
    op.add_column(
        "invoice_line_items",
        sa.Column("upload_id", pg.UUID(as_uuid=True), nullable=True),
        schema=_SCHEMA,
    )
    op.create_foreign_key(
        "fk_invoice_line_items_upload",
        "invoice_line_items",
        "uploads",
        ["upload_id"],
        ["id"],
        source_schema=_SCHEMA,
        referent_schema=_SCHEMA,
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_invoice_line_items_upload",
        "invoice_line_items",
        ["upload_id"],
        schema=_SCHEMA,
    )

    # 3. Create billing.carryovers table
    op.create_table(
        "carryovers",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "ap_record_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(
                f"{_SCHEMA}.ap_records.id",
                name="fk_carryovers_ap_record",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column(
            "upload_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(
                f"{_SCHEMA}.uploads.id",
                name="fk_carryovers_upload",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_carryovers_tenant",
        "carryovers",
        ["tenant_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_carryovers_ap_record",
        "carryovers",
        ["tenant_id", "ap_record_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_carryovers_upload",
        "carryovers",
        ["upload_id"],
        schema=_SCHEMA,
    )

    # 4. RLS policy on billing.carryovers (matches 0002/0003 canonical shape)
    op.execute(f"ALTER TABLE {_SCHEMA}.carryovers ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.carryovers FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {_SCHEMA}.carryovers
          FOR ALL
          TO {_TENANT_ROLES}
          USING      (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    # 4. Drop RLS on carryovers
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {_SCHEMA}.carryovers")
    op.execute(f"ALTER TABLE {_SCHEMA}.carryovers NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.carryovers DISABLE ROW LEVEL SECURITY")

    # 3. Drop carryovers table (indexes dropped automatically with table)
    op.drop_table("carryovers", schema=_SCHEMA)

    # 2. Drop upload_id from invoice_line_items
    op.drop_index("idx_invoice_line_items_upload", table_name="invoice_line_items", schema=_SCHEMA)
    op.drop_constraint(
        "fk_invoice_line_items_upload", "invoice_line_items", schema=_SCHEMA, type_="foreignkey"
    )
    op.drop_column("invoice_line_items", "upload_id", schema=_SCHEMA)

    # 1. Drop upload_id from payment_batches
    op.drop_index("idx_payment_batches_upload", table_name="payment_batches", schema=_SCHEMA)
    op.drop_constraint(
        "fk_payment_batches_upload", "payment_batches", schema=_SCHEMA, type_="foreignkey"
    )
    op.drop_column("payment_batches", "upload_id", schema=_SCHEMA)
