"""Stage 2 -- add billing.upload_field_config for per-tenant field dictionary.

One row per position per tenant. The operator names each captured position,
marks mandatory/PHI flags, and optionally records the data type. Stage 3 will
enforce mandatory fields and coerce types using this config.

Adds:
  - billing.upload_field_config table
  - idx_field_config_tenant_pos index on (tenant_id, position)
  - uq_field_config_tenant_pos unique constraint
  - RLS policy mirroring billing.claim_upload_raw_rows pattern
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0011_add_upload_field_config"
down_revision: Union[str, None] = "0010_rename_raw_rows_fields_to_blob"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "billing"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_TENANT_ROLES = f"ifx_dev_app, ifx_mock_app, {_APP_ROLE}"


def upgrade() -> None:
    op.create_table(
        "upload_field_config",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(128), nullable=False),
        sa.Column("data_type", sa.String(32), nullable=False, server_default="string"),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_phi", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sample_value", sa.String(512), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", pg.UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "position", name="uq_field_config_tenant_pos"),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_field_config_tenant_pos",
        "upload_field_config",
        ["tenant_id", "position"],
        schema=_SCHEMA,
    )
    op.execute(f"ALTER TABLE {_SCHEMA}.upload_field_config ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.upload_field_config FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_isolation ON {_SCHEMA}.upload_field_config
          FOR ALL TO {_TENANT_ROLES}
          USING      (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)"""
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {_SCHEMA}.upload_field_config")
    op.execute(f"ALTER TABLE {_SCHEMA}.upload_field_config NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.upload_field_config DISABLE ROW LEVEL SECURITY")
    op.drop_index("idx_field_config_tenant_pos", table_name="upload_field_config", schema=_SCHEMA)
    op.drop_table("upload_field_config", schema=_SCHEMA)
