"""Stage 1 positional capture -- add billing.claim_upload_raw_rows.

Stores one row per source line from pipe-delimited headerless claim export
files. The `fields` column is LargeBinary (AES-256-GCM via EncryptedJSON) --
all PHI is encrypted at rest. Column-name mapping comes in Stage 2.

Adds:
  - billing.claim_upload_raw_rows table
  - idx_raw_rows_tenant_upload index on (tenant_id, upload_id)
  - RLS policy mirroring billing.uploads pattern
  - 'captured' value is a valid string for the Upload.status column
    (stored as VARCHAR(32) -- no DB enum migration needed)

Revision ID: 0009_add_claim_upload_raw_rows
Revises: 0008_journal_chain_index_includes_id
Create Date: 2026-05-22
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0009_add_claim_upload_raw_rows"
down_revision: Union[str, None] = "0008_journal_chain_index_includes_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "billing"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_TENANT_ROLES = f"ifx_dev_app, ifx_mock_app, {_APP_ROLE}"


def upgrade() -> None:
    # 1. Create billing.claim_upload_raw_rows
    op.create_table(
        "claim_upload_raw_rows",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "upload_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(
                f"{_SCHEMA}.uploads.id",
                name="fk_raw_rows_upload",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        # 1-based line number in the source file (blank lines skipped)
        sa.Column("row_number", sa.Integer(), nullable=False),
        # Actual number of pipe-delimited fields in this source row
        sa.Column("field_count", sa.Integer(), nullable=False),
        # AES-256-GCM encrypted JSON: {"1": "val", ..., "N": "val"}
        # LargeBinary stores the ciphertext; ORM EncryptedJSON decrypts on read.
        sa.Column("fields", sa.LargeBinary(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("upload_id", "row_number", name="uq_raw_row_upload_rownum"),
        schema=_SCHEMA,
    )

    # 2. Composite index for tenant-scoped upload queries
    op.create_index(
        "idx_raw_rows_tenant_upload",
        "claim_upload_raw_rows",
        ["tenant_id", "upload_id"],
        schema=_SCHEMA,
    )

    # 3. RLS policy (mirrors billing.uploads from migration 0003)
    op.execute(
        f"ALTER TABLE {_SCHEMA}.claim_upload_raw_rows ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        f"ALTER TABLE {_SCHEMA}.claim_upload_raw_rows FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {_SCHEMA}.claim_upload_raw_rows
          FOR ALL
          TO {_TENANT_ROLES}
          USING      (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute(
        f"DROP POLICY IF EXISTS tenant_isolation ON {_SCHEMA}.claim_upload_raw_rows"
    )
    op.execute(
        f"ALTER TABLE {_SCHEMA}.claim_upload_raw_rows NO FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        f"ALTER TABLE {_SCHEMA}.claim_upload_raw_rows DISABLE ROW LEVEL SECURITY"
    )
    op.drop_index(
        "idx_raw_rows_tenant_upload",
        table_name="claim_upload_raw_rows",
        schema=_SCHEMA,
    )
    op.drop_table("claim_upload_raw_rows", schema=_SCHEMA)
