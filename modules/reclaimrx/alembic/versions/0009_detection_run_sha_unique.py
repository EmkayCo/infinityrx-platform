"""Partial unique index on detection_runs (tenant_id, source_sha256) for active runs.

Prevents two in_progress or completed runs from being created for the same
file content within the same tenant. The partial predicate excludes failed
and NULL-sha rows so re-ingestion of a previously-failed file is allowed.

Revision ID: 0009_detection_run_sha_unique
Revises: 0008_ml_detector_seed
Create Date: 2026-05-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_detection_run_sha_unique"
down_revision = "0008_ml_detector_seed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_detection_runs_tenant_sha_active",
        "detection_runs",
        ["tenant_id", "source_sha256"],
        unique=True,
        schema="reclaimrx",
        postgresql_where=sa.text(
            "status IN ('in_progress','completed') AND source_sha256 IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_detection_runs_tenant_sha_active",
        table_name="detection_runs",
        schema="reclaimrx",
    )
