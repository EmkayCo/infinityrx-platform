"""reclaimrx detection rule framework — Wave 43 M1.

Three tables:

  1. detection_rule_types        engineered code identity
                                 (no tenant_id, no RLS)
  2. detection_rule_instances    per-tenant operator-configurable
                                 rule instances (FORCE RLS)
  3. detection_rule_evaluation_log
                                 per-claim × per-instance evaluation
                                 trail (FORCE RLS, BRIN on
                                 evaluated_at + B-tree on
                                 rule_instance_id +
                                 detection_run_id)

Rule type catalog rows are upserted at app startup from the Python
:func:`register_rule_type` registry — this migration creates the
table empty.

Revision ID: 0003_detection_rule_framework
Revises: 0002_reclaimrx_rls
Create Date: 2026-04-27
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_detection_rule_framework"
down_revision: Union[str, None] = "0002_reclaimrx_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "reclaimrx"

_FAMILIES = "('A1', 'A2', 'A3', 'A4', 'A5', 'A6')"
_SEVERITIES = "('critical', 'high', 'medium', 'low', 'informational')"
_EVAL_RESULTS = "('no_finding', 'finding_raised', 'error', 'skipped_inapplicable')"
_DATA_SOURCES = "('live_db', 'paysync_data', 'csv_upload')"
import os
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_ROLES = f"ifx_dev_app, {_APP_ROLE}"
_PREDICATE = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"


def upgrade() -> None:
    # ── 1. detection_rule_types — global catalog, no RLS ──
    op.create_table(
        "detection_rule_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("family", sa.String(2), nullable=False),
        sa.Column("parameter_schema_version", sa.String(20), nullable=False),
        sa.Column("default_severity", sa.String(16), nullable=False),
        sa.Column("default_confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("requires_baseline", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requires_history", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deferred_data_feed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deferred_reason", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column(
            "required_data_columns",
            postgresql.ARRAY(sa.String(64)),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column(
            "default_parameters",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
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
        sa.UniqueConstraint("code", name="uq_reclaimrx_rule_type_code"),
        sa.CheckConstraint(f"family IN {_FAMILIES}", name="ck_reclaimrx_rule_type_family"),
        sa.CheckConstraint(
            f"default_severity IN {_SEVERITIES}",
            name="ck_reclaimrx_rule_type_severity",
        ),
        sa.CheckConstraint(
            "default_confidence >= 0 AND default_confidence <= 1",
            name="ck_reclaimrx_rule_type_confidence_range",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(default_parameters) = 'object'",
            name="ck_reclaimrx_rule_type_default_params_object",
        ),
        schema=_SCHEMA,
    )

    # ── 2. detection_rule_instances — per-tenant configuration ──
    op.create_table(
        "detection_rule_instances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_type_code", sa.String(50), nullable=False),
        sa.Column("instance_name", sa.String(120), nullable=False),
        sa.Column(
            "parameters",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("severity_override", sa.String(16), nullable=True),
        sa.Column("confidence_override", sa.Numeric(5, 4), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "applies_to_client_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=True,
        ),
        sa.Column(
            "applies_to_program_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=True,
        ),
        sa.Column(
            "applies_to_pharmacy_npis",
            postgresql.ARRAY(sa.String(10)),
            nullable=True,
        ),
        sa.Column("effective_from", sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["rule_type_code"],
            [f"{_SCHEMA}.detection_rule_types.code"],
            name="fk_reclaimrx_rule_instance_type",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id", "rule_type_code", "instance_name",
            name="uq_reclaimrx_rule_instance_name",
        ),
        sa.CheckConstraint(
            f"severity_override IS NULL OR severity_override IN {_SEVERITIES}",
            name="ck_reclaimrx_rule_instance_severity",
        ),
        sa.CheckConstraint(
            "confidence_override IS NULL OR "
            "(confidence_override >= 0 AND confidence_override <= 1)",
            name="ck_reclaimrx_rule_instance_confidence_range",
        ),
        sa.CheckConstraint(
            "termination_date IS NULL OR termination_date >= effective_from",
            name="ck_reclaimrx_rule_instance_period_order",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(parameters) = 'object'",
            name="ck_reclaimrx_rule_instance_params_object",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_rule_instances_tenant",
        "detection_rule_instances",
        ["tenant_id", "enabled"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_rule_instances_type",
        "detection_rule_instances",
        ["tenant_id", "rule_type_code"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_rule_instances_active",
        "detection_rule_instances",
        ["tenant_id", "rule_type_code", "effective_from"],
        postgresql_where=sa.text("termination_date IS NULL"),
        schema=_SCHEMA,
    )

    # ── 3. detection_rule_evaluation_log — per-evaluation audit ──
    op.create_table(
        "detection_rule_evaluation_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "rule_instance_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                f"{_SCHEMA}.detection_rule_instances.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "detection_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                f"{_SCHEMA}.detection_runs.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column("source_table", sa.String(50), nullable=False),
        sa.Column("source_row_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_result", sa.String(32), nullable=False),
        sa.Column(
            "anomaly_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                f"{_SCHEMA}.anomalies.id",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("elapsed_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            f"evaluation_result IN {_EVAL_RESULTS}",
            name="ck_reclaimrx_eval_log_result",
        ),
        sa.CheckConstraint(
            "elapsed_ms >= 0",
            name="ck_reclaimrx_eval_log_elapsed_nonneg",
        ),
        sa.CheckConstraint(
            "(evaluation_result = 'finding_raised' AND anomaly_id IS NOT NULL) OR "
            "(evaluation_result <> 'finding_raised' AND anomaly_id IS NULL)",
            name="ck_reclaimrx_eval_log_anomaly_id_iff_finding",
        ),
        sa.CheckConstraint(
            "(evaluation_result = 'error') = (error_message IS NOT NULL)",
            name="ck_reclaimrx_eval_log_error_iff_message",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_eval_log_instance",
        "detection_rule_evaluation_log",
        ["rule_instance_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_reclaimrx_eval_log_run",
        "detection_rule_evaluation_log",
        ["detection_run_id"],
        schema=_SCHEMA,
    )
    # BRIN on evaluated_at — table is high-volume + insert-only +
    # naturally clustered by time. BRIN gives bytes-of-storage cost
    # for the same range-scan path B-tree would; saves index size by
    # 100×+.
    op.execute(
        f"CREATE INDEX ix_reclaimrx_eval_log_brin_evaluated_at "
        f"ON {_SCHEMA}.detection_rule_evaluation_log "
        f"USING BRIN (evaluated_at)"
    )
    op.create_index(
        "ix_reclaimrx_eval_log_anomaly",
        "detection_rule_evaluation_log",
        ["anomaly_id"],
        postgresql_where=sa.text("anomaly_id IS NOT NULL"),
        schema=_SCHEMA,
    )

    # ── RLS — instances + evaluation_log only (rule_types is global) ──
    for table in ("detection_rule_instances", "detection_rule_evaluation_log"):
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {_SCHEMA}.{table}
              FOR ALL
              TO {_ROLES}
              USING      ({_PREDICATE})
              WITH CHECK ({_PREDICATE});
            """
        )

    # ── GRANTs ──
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON "
        f"{_SCHEMA}.detection_rule_types, "
        f"{_SCHEMA}.detection_rule_instances, "
        f"{_SCHEMA}.detection_rule_evaluation_log "
        f"TO ifx_dev_app, {_APP_ROLE}, ifx_dev_admin, ifx_prod_admin"
    )


def downgrade() -> None:
    op.drop_table("detection_rule_evaluation_log", schema=_SCHEMA)
    op.drop_table("detection_rule_instances", schema=_SCHEMA)
    op.drop_table("detection_rule_types", schema=_SCHEMA)
