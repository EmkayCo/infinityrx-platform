"""reclaimrx ML detector registry + training runs (Wave 44b M1).

Two tables:
  1. reclaimrx.ml_detector_registry  — global, no tenant_id, no RLS.
     Holds one row per named detector (e.g. 'pharmacy_behavioral_baseline').
     Placeholders ship with is_placeholder=True and no artifact path.
     Training the detector updates the row in-place.
  2. reclaimrx.ml_training_runs       — tenant-scoped, FORCE RLS.
     Provenance + metrics for every training job executed.

Revision ID: 0006_ml_detector_registry
Revises: 0005_eval_log_runwide_skips
Create Date: 2026-04-27
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_ml_detector_registry"
down_revision: Union[str, None] = "0005_eval_log_runwide_skips"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "reclaimrx"
_TRAINING_STATUSES = "('in_progress', 'completed', 'failed')"
import os
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_ROLES = f"ifx_dev_app, {_APP_ROLE}, ifx_dev_admin, ifx_prod_admin"
_APP_ROLES = f"ifx_dev_app, {_APP_ROLE}"
_ADMIN_ROLES = "ifx_dev_admin, ifx_prod_admin"
_PREDICATE = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"


def upgrade() -> None:
    # ── 1. ml_detector_registry — global reference, no RLS ──────────────
    op.create_table(
        "ml_detector_registry",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("detector_name", sa.String(100), nullable=False),
        sa.Column("detector_version", sa.String(20), nullable=False, server_default="0"),
        sa.Column("model_artifact_path", sa.Text(), nullable=True),
        sa.Column("feature_schema_class", sa.String(255), nullable=False),
        sa.Column("is_placeholder", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "training_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("detector_name", name="uq_ml_detector_registry_name"),
        sa.CheckConstraint(
            "jsonb_typeof(training_metadata) = 'object'",
            name="ck_ml_detector_registry_metadata_object",
        ),
        schema=_SCHEMA,
    )

    # ── 2. ml_training_runs — tenant-scoped with FORCE RLS ───────────────
    op.create_table(
        "ml_training_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("detector_name", sa.String(100), nullable=False),
        sa.Column("training_data_source", sa.String(255), nullable=False),
        sa.Column("training_data_sha256", sa.String(64), nullable=True),
        sa.Column("training_data_record_count", sa.Integer(), nullable=True),
        sa.Column(
            "features_used",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "training_started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("training_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="in_progress",
        ),
        sa.Column("resulting_artifact_path", sa.Text(), nullable=True),
        sa.Column(
            "validation_metrics",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("triggered_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            f"status IN {_TRAINING_STATUSES}",
            name="ck_ml_training_runs_status",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(features_used) = 'array'",
            name="ck_ml_training_runs_features_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(validation_metrics) = 'object'",
            name="ck_ml_training_runs_metrics_object",
        ),
        sa.CheckConstraint(
            # Completed runs must have a completed_at timestamp; failed runs
            # must have a failure reason; in_progress rows have neither.
            "(status = 'in_progress' AND training_completed_at IS NULL) OR "
            "(status = 'completed' AND training_completed_at IS NOT NULL) OR "
            "(status = 'failed' AND failure_reason IS NOT NULL)",
            name="ck_ml_training_runs_lifecycle",
        ),
        schema=_SCHEMA,
    )

    # Indexes
    op.create_index(
        "idx_ml_training_runs_tenant_detector",
        "ml_training_runs",
        ["tenant_id", "detector_name"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_ml_training_runs_status",
        "ml_training_runs",
        ["tenant_id", "status"],
        schema=_SCHEMA,
    )

    # RLS on ml_training_runs (FORCE — tenant-scoped)
    op.execute(f"ALTER TABLE {_SCHEMA}.ml_training_runs ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.ml_training_runs FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY ml_training_runs_tenant_isolation
        ON {_SCHEMA}.ml_training_runs
        USING ({_PREDICATE})
        """
    )

    # GRANTs
    for tbl in ("ml_detector_registry", "ml_training_runs"):
        op.execute(f"GRANT SELECT ON {_SCHEMA}.{tbl} TO {_APP_ROLES}")
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {_SCHEMA}.{tbl} TO {_ADMIN_ROLES}"
        )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS ml_training_runs_tenant_isolation ON {_SCHEMA}.ml_training_runs")
    op.drop_index("idx_ml_training_runs_status", table_name="ml_training_runs", schema=_SCHEMA)
    op.drop_index("idx_ml_training_runs_tenant_detector", table_name="ml_training_runs", schema=_SCHEMA)
    op.drop_table("ml_training_runs", schema=_SCHEMA)
    op.drop_table("ml_detector_registry", schema=_SCHEMA)
