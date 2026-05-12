"""paysync Wave 41 M3: echo_sftp_config + echo_status_file_ingestions.

Per-tenant SFTP credentials for Echo (production + test envs)
and ingestion-tracking table for incoming Payment Status Files.

Credentials encrypted at rest via shared.utils.secret_box (Wave 36
key rotation). RLS enforced.

Revision ID: 0014_echo_sftp
Revises: 0013_cycle_reconciliations
Create Date: 2026-04-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import os

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_echo_sftp"
down_revision: Union[str, None] = "0013_cycle_reconciliations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "paysync"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_TABLES = ("echo_sftp_config", "echo_status_file_ingestions")


def upgrade() -> None:
    # ── echo_sftp_config ──────────────────────────────────────────
    op.create_table(
        "echo_sftp_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "environment", sa.String(16),
            nullable=False, server_default=sa.text("'production'"),
        ),
        sa.Column("sftp_host", sa.String(255), nullable=False),
        sa.Column("sftp_port", sa.Integer(), nullable=False, server_default=sa.text("22")),
        sa.Column("sftp_username", sa.String(120), nullable=False),
        sa.Column("sftp_password_encrypted", postgresql.BYTEA(), nullable=True),
        sa.Column("sftp_private_key_encrypted", postgresql.BYTEA(), nullable=True),
        sa.Column("outbox_path", sa.String(500), nullable=False),
        sa.Column("inbox_path", sa.String(500), nullable=False),
        sa.Column("archive_path", sa.String(500), nullable=True),
        sa.Column(
            "active", sa.Boolean(),
            nullable=False, server_default=sa.true(),
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "environment IN ('production', 'test')",
            name="ck_paysync_echo_sftp_env",
        ),
        sa.CheckConstraint(
            "sftp_password_encrypted IS NOT NULL OR sftp_private_key_encrypted IS NOT NULL",
            name="ck_paysync_echo_sftp_credentials_supplied",
        ),
        sa.CheckConstraint(
            "(termination_date IS NULL) OR (termination_date >= effective_from)",
            name="ck_paysync_echo_sftp_term_after_eff",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "uq_paysync_echo_sftp_one_active_per_env_per_tenant",
        "echo_sftp_config",
        ["tenant_id", "environment"],
        unique=True,
        schema=_SCHEMA,
        postgresql_where=sa.text("active = true AND termination_date IS NULL"),
    )

    # ── echo_status_file_ingestions ───────────────────────────────
    op.create_table(
        "echo_status_file_ingestions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("remote_filename", sa.String(500), nullable=False),
        sa.Column("local_path", sa.String(500), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=True),
        sa.Column("records_matched", sa.Integer(), nullable=True),
        sa.Column("records_unmatched", sa.Integer(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status", sa.String(32),
            nullable=False, server_default=sa.text("'downloaded'"),
        ),
        sa.CheckConstraint(
            "status IN ('downloaded', 'parsed', 'failed', 'archived')",
            name="ck_paysync_echo_ingest_status",
        ),
        sa.CheckConstraint(
            "file_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_paysync_echo_ingest_sha256",
        ),
        # Idempotent re-ingest dedup: same file content (sha) per
        # tenant resolves to the same row.
        sa.UniqueConstraint(
            "tenant_id", "file_sha256",
            name="uq_paysync_echo_ingest_sha",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_echo_ingest_tenant_status",
        "echo_status_file_ingestions",
        ["tenant_id", "status"],
        schema=_SCHEMA,
    )

    # RLS
    for tbl in _TABLES:
        op.execute(f"ALTER TABLE {_SCHEMA}.{tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {_SCHEMA}.{tbl} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {_SCHEMA}.{tbl}
              FOR ALL
              TO ifx_dev_app, {_APP_ROLE}
              USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
              WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
            """
        )
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON "
        + ", ".join(f"{_SCHEMA}.{t}" for t in _TABLES)
        + f" TO ifx_dev_app, {_APP_ROLE}, ifx_dev_admin, ifx_prod_admin"
    )


def downgrade() -> None:
    for t in reversed(_TABLES):
        op.drop_table(t, schema=_SCHEMA)
