"""shared.ingestion_runs and shared.ingestion_schedules — run tracking tables

Revision ID: 0007_ingestion_tracking
Revises: 0006_sessions
Create Date: 2026-04-14 00:00:00.000000

Adds the global reference-data ingestion tracking tables to the ``shared``
schema. These are NOT tenant-scoped (LESSON-011: reference registries are
cross-tenant). Downgrade drops indexes then tables in dependency order.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_ingestion_tracking"
down_revision: Union[str, None] = "0006_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "shared"


def upgrade() -> None:
    # Ensure the shared schema exists (safe if already present)
    op.execute(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')

    op.create_table(
        "ingestion_runs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("run_type", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="running",
            nullable=False,
        ),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_file_name", sa.String(length=500), nullable=True),
        sa.Column("source_file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("source_file_checksum", sa.String(length=128), nullable=True),
        sa.Column("records_in_source", sa.Integer(), nullable=True),
        sa.Column(
            "records_processed", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "records_inserted", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "records_updated", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "records_skipped", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "records_errored", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("error_samples", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("download_seconds", sa.Integer(), nullable=True),
        sa.Column("parse_seconds", sa.Integer(), nullable=True),
        sa.Column("load_seconds", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_runs")),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_ingestion_runs_source_started",
        "ingestion_runs",
        ["source", sa.text("started_at DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_ingestion_runs_status",
        "ingestion_runs",
        ["status"],
        schema=SCHEMA,
    )

    op.create_table(
        "ingestion_schedules",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("cron_expression", sa.String(length=100), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column("last_run_id", sa.UUID(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["last_run_id"],
            [f"{SCHEMA}.ingestion_runs.id"],
            name=op.f("fk_ingestion_schedules_last_run_id_ingestion_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_schedules")),
        sa.UniqueConstraint(
            "source", name=op.f("uq_ingestion_schedules_source")
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    # Drop schedules first (FK dependency on runs)
    op.drop_table("ingestion_schedules", schema=SCHEMA)
    op.drop_index(
        "ix_ingestion_runs_status",
        table_name="ingestion_runs",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_ingestion_runs_source_started",
        table_name="ingestion_runs",
        schema=SCHEMA,
    )
    op.drop_table("ingestion_runs", schema=SCHEMA)
