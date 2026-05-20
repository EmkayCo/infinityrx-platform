"""SP-1 Plan D Task 1 -- add billing.file_artifacts table.

Adds:
  - billing.file_artifacts table with FK to payment_batches (x2) and uploads
  - Composite index on (tenant_id, generated_at) for time-range queries
  - RLS policy matching 0002/0003/0004 canonical shape

Migration is reversible: downgrade drops the table.

Revision ID: 0005_add_file_artifacts
Revises: 0004_propagate_upload_id
Create Date: 2026-05-17
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0005_add_file_artifacts"
down_revision: Union[str, None] = "0004_propagate_upload_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "billing"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_TENANT_ROLES = f"ifx_dev_app, ifx_mock_app, {_APP_ROLE}"


def upgrade() -> None:
    op.create_table(
        "file_artifacts",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column(
            "source_batch_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(
                f"{_SCHEMA}.payment_batches.id",
                name="fk_file_artifacts_source_batch",
                ondelete="RESTRICT",
            ),
            nullable=True,
        ),
        sa.Column(
            "source_payment_run_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(
                f"{_SCHEMA}.payment_batches.id",
                name="fk_file_artifacts_source_payment_run",
                ondelete="RESTRICT",
            ),
            nullable=True,
        ),
        sa.Column(
            "upload_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(
                f"{_SCHEMA}.uploads.id",
                name="fk_file_artifacts_upload",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column("generated_by", pg.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'ready'"),
        ),
        schema=_SCHEMA,
    )

    op.create_index(
        "idx_file_artifacts_tenant_generated_at",
        "file_artifacts",
        ["tenant_id", "generated_at"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_file_artifacts_source_batch",
        "file_artifacts",
        ["tenant_id", "source_batch_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_file_artifacts_source_payment_run",
        "file_artifacts",
        ["tenant_id", "source_payment_run_id"],
        schema=_SCHEMA,
    )

    # RLS -- matches 0002/0003/0004 canonical shape
    op.execute(f"ALTER TABLE {_SCHEMA}.file_artifacts ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.file_artifacts FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {_SCHEMA}.file_artifacts
          FOR ALL
          TO {_TENANT_ROLES}
          USING      (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {_SCHEMA}.file_artifacts")
    op.execute(f"ALTER TABLE {_SCHEMA}.file_artifacts NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.file_artifacts DISABLE ROW LEVEL SECURITY")
    op.drop_table("file_artifacts", schema=_SCHEMA)
