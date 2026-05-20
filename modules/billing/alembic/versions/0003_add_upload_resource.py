"""SP-1 Plan B Task 1 — Upload resource + claim_records FK & amount_billed.

Adds:
  - billing.uploads table (paysync CSV/Excel upload provenance)
  - billing.claim_records.upload_id   NULLABLE FK to billing.uploads.id
  - billing.claim_records.amount_billed Numeric(14, 4) NULLABLE
  - idx_claims_upload index on billing.claim_records(upload_id)
  - RLS policy on billing.uploads (matches 0002 canonical shape)

Migration is reversible: downgrade drops in reverse order
(RLS policy then FK then indexes then claim_records cols then uploads table).

Both new claim_records columns are nullable so the existing rows
ingested before this migration remain valid; the upload service layer
requires them for any new upload-created claim.

Revision ID: 0003_add_upload_resource
Revises: 0002_rls_tenant_isolation
Create Date: 2026-05-16
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0003_add_upload_resource"
down_revision: Union[str, None] = "0002_rls_tenant_isolation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "billing"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_TENANT_ROLES = f"ifx_dev_app, ifx_mock_app, {_APP_ROLE}"


def upgrade() -> None:
    # 1. Create billing.uploads
    op.create_table(
        "uploads",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_by", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("source_platform", sa.String(256), nullable=True),
        sa.Column(
            "supersedes_upload_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.uploads.id", name="fk_upload_supersedes"),
            nullable=True,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'parsing'")),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=True),
        sa.Column("row_errors", pg.JSONB(), nullable=True),
        sa.UniqueConstraint("tenant_id", "sha256", name="uq_upload_tenant_sha256"),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_uploads_tenant_uploaded_at",
        "uploads",
        ["tenant_id", "uploaded_at"],
        schema=_SCHEMA,
    )

    # 2. Extend billing.claim_records with upload_id + amount_billed
    op.add_column(
        "claim_records",
        sa.Column("upload_id", pg.UUID(as_uuid=True), nullable=True),
        schema=_SCHEMA,
    )
    op.add_column(
        "claim_records",
        sa.Column("amount_billed", sa.Numeric(14, 4), nullable=True),
        schema=_SCHEMA,
    )
    op.create_foreign_key(
        "fk_claims_upload",
        "claim_records",
        "uploads",
        ["upload_id"],
        ["id"],
        source_schema=_SCHEMA,
        referent_schema=_SCHEMA,
    )
    op.create_index(
        "idx_claims_upload",
        "claim_records",
        ["upload_id"],
        schema=_SCHEMA,
    )

    # 3. RLS policy on billing.uploads (matches 0002 canonical shape)
    op.execute(f"ALTER TABLE {_SCHEMA}.uploads ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.uploads FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {_SCHEMA}.uploads
          FOR ALL
          TO {_TENANT_ROLES}
          USING      (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {_SCHEMA}.uploads")
    op.execute(f"ALTER TABLE {_SCHEMA}.uploads NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.uploads DISABLE ROW LEVEL SECURITY")

    op.drop_index("idx_claims_upload", table_name="claim_records", schema=_SCHEMA)
    op.drop_constraint("fk_claims_upload", "claim_records", schema=_SCHEMA, type_="foreignkey")
    op.drop_column("claim_records", "amount_billed", schema=_SCHEMA)
    op.drop_column("claim_records", "upload_id", schema=_SCHEMA)

    op.drop_index("idx_uploads_tenant_uploaded_at", table_name="uploads", schema=_SCHEMA)
    op.drop_table("uploads", schema=_SCHEMA)
