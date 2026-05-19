"""SP-3 backend extensions: new tables + column extensions + RLS + indexes.

New tables (public schema, `reclaimrx_*` prefix — ORM-aligned per R1 BLOCK 1):
  - reclaimrx_graph_runs            — durable per-tenant graph-analysis run tracking
  - reclaimrx_fraud_rings           — fraud rings detected per run
  - reclaimrx_accumulator_anomalies — accumulator manipulation anomalies (NOT extending
                                       accumulator_detections — this is a separate table)
  - reclaimrx_threshold_configs     — versioned per-tenant FWA threshold configuration
  - reclaimrx_threshold_config_audits — per-field hash-chained audit trail
  - reclaimrx_outbox_events         — transactional outbox for reliable event publishing

Altered tables:
  - reclaimrx_investigations — 12 new scalar columns (severity, source, source_ref_id,
                            member_id, opened_by, closed_at, closed_by,
                            outcome_label, recovered_amount, hold_amount,
                            threshold_config_version, threshold_snapshot)
  - reclaimrx_payment_holds — add status column (active|released|expired|cancelled)
                               NOTE: released_by, released_at, release_reason
                               ALREADY EXIST at tables.py:607-609 — DO NOT re-add.

RLS: FORCE ROW LEVEL SECURITY on all 6 new tables.
     GUC: app.current_tenant_id (matches 0002, 0003, 0006, 0007)
     Predicate: tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid

Indexes per .claude/rules/performance.md:
  - (tenant_id, status) on graph_runs, outbox_events, accumulator_anomalies
  - (tenant_id, FK) on fraud_rings, accumulator_anomalies, threshold_config_audits
  - (tenant_id, severity) on investigations
  - (tenant_id, member_id) on investigations
  - (status, created_at) on outbox_events (dispatcher poll)
  - UNIQUE partial (tenant_id WHERE superseded_at IS NULL) on threshold_configs
  - UNIQUE (idempotency_key) on outbox_events

Revision ID: 0008_sp3_extensions
Revises: 0007_flagged_npis
Create Date: 2026-05-18
"""
from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_sp3_extensions"
down_revision: Union[str, None] = "0007_flagged_npis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
# GUC matches every prior migration in this module (0002, 0003, 0006, 0007)
_RLS_PREDICATE = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
)

# R1 BLOCKS 1 + 2 fix — single physical-naming convention for SP-3.
#
# The reclaimrx codebase already has an internal split:
#   - migrations 0001-0007 create *unprefixed* tables inside the
#     `reclaimrx` named schema (e.g. reclaimrx.investigations);
#   - the ORM at `modules/reclaimrx/src/models/tables.py` declares
#     *prefixed* tables in the default public schema (e.g.
#     reclaimrx_investigations) with no `__table_args__["schema"]`.
#
# RESOLUTION: this migration follows the ORM's pattern verbatim —
# all new SP-3 tables are created in the default schema with the
# `reclaimrx_*` prefix. No `schema=` kwarg on `op.create_table`,
# no `schema=` on `op.create_index`, and the helper functions
# below operate on bare (already-prefixed) table names.
#
# Existing pre-SP-3 tables in the `reclaimrx` schema are NOT moved.
# They remain queryable through their own existing ORM models (if any)
# or raw SQL. SP-3 does not own that migration debt — Wave B11+ will
# audit and rationalize it.

_GRAPH_RUN_STATUSES = "('running', 'completed', 'completed_partial', 'failed')"
_GRAPH_RUN_TRIGGERS = "('cron', 'on_demand')"
_ACCUMULATOR_PATTERN_TYPES = (
    "('sudden_spike', 'multi_payer_convergence', 'reset_evasion', 'threshold_oscillation')"
)
_OUTBOX_STATUSES = "('pending', 'published', 'failed')"
_HOLD_STATUSES = "('active', 'released', 'expired', 'cancelled')"
_INVESTIGATION_SEVERITIES = "('low', 'medium', 'high', 'critical')"
_INVESTIGATION_SOURCES = (
    "('rule_firing', 'ml_score', 'graph_ring', 'accumulator_anomaly', 'manual')"
)
_INVESTIGATION_OUTCOMES = "('confirmed', 'false_positive', 'no_action')"


def _enable_rls(table: str) -> None:
    """Enable + force RLS and create tenant_isolation policy.

    `table` MUST be the fully prefixed name (e.g. `reclaimrx_graph_runs`).
    R1 BLOCK 1 fix: no schema qualifier — these tables live in public.
    """
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {table}
          FOR ALL
          USING      ({_RLS_PREDICATE})
          WITH CHECK ({_RLS_PREDICATE})
        """
    )


def _grant_rw(table: str) -> None:
    for role in ("ifx_dev_app", _APP_ROLE):
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE ON {table} TO {role}"
        )
    for role in ("ifx_dev_admin", "ifx_prod_admin"):
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {role}"
        )


def upgrade() -> None:
    # R1 BLOCK 1 fix: all SP-3 tables live in public schema with `reclaimrx_*`
    # prefix to match the ORM at `src/models/tables.py`. No schema creation
    # needed (public always exists).

    # -------------------------------------------------------------------------
    # 1. graph_runs
    # -------------------------------------------------------------------------
    op.create_table(
        "reclaimrx_graph_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="running"),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("correlation_id", sa.String(36), nullable=False),
        sa.Column("stale_timeout_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rings_detected", sa.Integer, nullable=False, server_default="0"),
        sa.Column("investigations_opened", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_scanned", sa.Integer, nullable=False, server_default="0"),
        sa.Column("lookback_window_days", sa.Integer, nullable=False, server_default="90"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"status IN {_GRAPH_RUN_STATUSES}",
            name="ck_graph_runs_status",
        ),
        sa.CheckConstraint(
            f"trigger IN {_GRAPH_RUN_TRIGGERS}",
            name="ck_graph_runs_trigger",
        ),
    )
    op.create_index(
        "ix_graph_runs_tenant_status",
        "reclaimrx_graph_runs",
        ["tenant_id", "status"],
    )
    # Partial unique index: at most one 'running' row per tenant
    op.execute(
        """
        CREATE UNIQUE INDEX uq_graph_runs_one_running_per_tenant
          ON reclaimrx_graph_runs (tenant_id)
          WHERE status = 'running'
        """
    )
    _enable_rls("reclaimrx_graph_runs")
    _grant_rw("reclaimrx_graph_runs")

    # -------------------------------------------------------------------------
    # 2. fraud_rings
    # -------------------------------------------------------------------------
    op.create_table(
        "reclaimrx_fraud_rings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "graph_run_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("reclaimrx_graph_runs.id"),
            nullable=False,
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("density_score", sa.Numeric(8, 4), nullable=False),
        sa.Column("node_count", sa.Integer, nullable=False),
        sa.Column("edge_count", sa.Integer, nullable=False),
        sa.Column(
            "entity_refs",
            postgresql.JSONB,
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "spawned_investigation_id",
            postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "node_count >= 0 AND edge_count >= 0",
            name="ck_fraud_rings_counts_non_negative",
        ),
        sa.CheckConstraint(
            "density_score >= 0 AND density_score <= 1",
            name="ck_fraud_rings_density_range",
        ),
    )
    op.create_index(
        "ix_fraud_rings_tenant_run",
        "reclaimrx_fraud_rings",
        ["tenant_id", "graph_run_id"],
    )
    op.create_index(
        "ix_fraud_rings_tenant_detected",
        "reclaimrx_fraud_rings",
        ["tenant_id", "detected_at"],
    )
    _enable_rls("reclaimrx_fraud_rings")
    _grant_rw("reclaimrx_fraud_rings")

    # -------------------------------------------------------------------------
    # 3. accumulator_anomalies
    # NOTE: This is NOT an extension of reclaimrx_accumulator_detections.
    # AccumulatorDetection tracks copay-assistance plan-type detection.
    # AccumulatorAnomaly tracks SP-3 fraud pattern detection.
    # -------------------------------------------------------------------------
    op.create_table(
        "reclaimrx_accumulator_anomalies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("member_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("pattern_type", sa.String(50), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("evidence_window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "triggering_event_ids",
            postgresql.JSONB,
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "spawned_investigation_id",
            postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"pattern_type IN {_ACCUMULATOR_PATTERN_TYPES}",
            name="ck_accumulator_anomalies_pattern_type",
        ),
    )
    op.create_index(
        "ix_accumulator_anomalies_tenant_member",
        "reclaimrx_accumulator_anomalies",
        ["tenant_id", "member_id"],
    )
    op.create_index(
        "ix_accumulator_anomalies_tenant_detected",
        "reclaimrx_accumulator_anomalies",
        ["tenant_id", "detected_at"],
    )
    _enable_rls("reclaimrx_accumulator_anomalies")
    _grant_rw("reclaimrx_accumulator_anomalies")

    # -------------------------------------------------------------------------
    # 4. threshold_configs
    # -------------------------------------------------------------------------
    op.create_table(
        "reclaimrx_threshold_configs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "rule_thresholds",
            postgresql.JSONB,
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "ml_score_thresholds",
            postgresql.JSONB,
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("graph_density_threshold", sa.Numeric(8, 4), nullable=False),
        sa.Column("accumulator_anomaly_sensitivity", sa.Numeric(8, 4), nullable=False),
        sa.Column("updated_by", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("version > 0", name="ck_threshold_configs_version_positive"),
        sa.CheckConstraint(
            "graph_density_threshold > 0 AND graph_density_threshold <= 1",
            name="ck_threshold_configs_density_range",
        ),
        sa.CheckConstraint(
            "accumulator_anomaly_sensitivity > 0 AND accumulator_anomaly_sensitivity <= 1",
            name="ck_threshold_configs_sensitivity_range",
        ),
    )
    op.create_index(
        "ix_threshold_configs_tenant_version",
        "reclaimrx_threshold_configs",
        ["tenant_id", "version"],
    )
    # Partial unique index: only one current (unsuperseded) version per tenant
    op.execute(
        """
        CREATE UNIQUE INDEX uq_threshold_configs_current_per_tenant
          ON reclaimrx_threshold_configs (tenant_id)
          WHERE superseded_at IS NULL
        """
    )
    _enable_rls("reclaimrx_threshold_configs")
    _grant_rw("reclaimrx_threshold_configs")

    # -------------------------------------------------------------------------
    # 5. threshold_config_audits
    # -------------------------------------------------------------------------
    op.create_table(
        "reclaimrx_threshold_config_audits",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "threshold_config_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("reclaimrx_threshold_configs.id"),
            nullable=False,
        ),
        sa.Column("field", sa.String(255), nullable=False),
        sa.Column("old_value", sa.Text, nullable=True),
        sa.Column("new_value", sa.Text, nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("changed_by", sa.String(255), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        # hipaa-2026.md: MUST compute entry_hash on EVERY write — NOT NULL
        sa.Column("entry_hash", sa.String(64), nullable=False),
        sa.Column("prev_entry_hash", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "length(entry_hash) > 0",
            name="ck_threshold_config_audits_entry_hash_nonempty",
        ),
    )
    op.create_index(
        "ix_threshold_config_audits_tenant_config",
        "reclaimrx_threshold_config_audits",
        ["tenant_id", "threshold_config_id"],
    )
    op.create_index(
        "ix_threshold_config_audits_changed_at",
        "reclaimrx_threshold_config_audits",
        ["tenant_id", "changed_at"],
    )
    _enable_rls("reclaimrx_threshold_config_audits")
    _grant_rw("reclaimrx_threshold_config_audits")

    # -------------------------------------------------------------------------
    # 6. outbox_events
    # -------------------------------------------------------------------------
    op.create_table(
        "reclaimrx_outbox_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column(
            "envelope_json",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.CheckConstraint(
            f"status IN {_OUTBOX_STATUSES}",
            name="ck_outbox_events_status",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_outbox_events_idempotency_key"),
    )
    op.create_index(
        "ix_outbox_events_status_created",
        "reclaimrx_outbox_events",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_outbox_events_tenant_status",
        "reclaimrx_outbox_events",
        ["tenant_id", "status"],
    )
    _enable_rls("reclaimrx_outbox_events")
    _grant_rw("reclaimrx_outbox_events")

    # -------------------------------------------------------------------------
    # 7. ALTER reclaimrx_investigations — add 12 SP-3 scalar columns
    # -------------------------------------------------------------------------
    for col_def in [
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("source_ref_id", sa.String(36), nullable=True),
        sa.Column("member_id", sa.String(36), nullable=True),
        sa.Column("opened_by", sa.String(255), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", sa.String(255), nullable=True),
        sa.Column("outcome_label", sa.String(50), nullable=True),
        sa.Column("recovered_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("hold_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("threshold_config_version", sa.Integer, nullable=True),
        sa.Column(
            "threshold_snapshot",
            postgresql.JSONB,
            nullable=True,
            server_default=sa.text("NULL"),
        ),
    ]:
        op.add_column("reclaimrx_investigations", col_def)

    # Add CHECK constraints on new enum columns
    op.execute(
        "ALTER TABLE reclaimrx_investigations "
        f"ADD CONSTRAINT ck_investigations_severity "
        f"CHECK (severity IS NULL OR severity IN {_INVESTIGATION_SEVERITIES})"
    )
    op.execute(
        "ALTER TABLE reclaimrx_investigations "
        f"ADD CONSTRAINT ck_investigations_source "
        f"CHECK (source IS NULL OR source IN {_INVESTIGATION_SOURCES})"
    )
    op.execute(
        "ALTER TABLE reclaimrx_investigations "
        f"ADD CONSTRAINT ck_investigations_outcome_label "
        f"CHECK (outcome_label IS NULL OR outcome_label IN {_INVESTIGATION_OUTCOMES})"
    )

    # New indexes on investigations per performance.md
    op.create_index(
        "ix_reclaimrx_investigations_tenant_severity",
        "reclaimrx_investigations",
        ["tenant_id", "severity"],
    )
    op.create_index(
        "ix_reclaimrx_investigations_tenant_member_id",
        "reclaimrx_investigations",
        ["tenant_id", "member_id"],
    )
    op.create_index(
        "ix_reclaimrx_investigations_tenant_source_ref",
        "reclaimrx_investigations",
        ["tenant_id", "source_ref_id"],
    )

    # -------------------------------------------------------------------------
    # 8. ALTER reclaimrx_payment_holds — add status column
    # BLOCK 1 RESOLVED: released_by/released_at/release_reason ALREADY EXIST
    # at tables.py:607-609. DO NOT re-add. Only add status.
    # -------------------------------------------------------------------------
    op.add_column(
        "reclaimrx_payment_holds",
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
    )
    op.execute(
        "ALTER TABLE reclaimrx_payment_holds "
        f"ADD CONSTRAINT ck_payment_holds_status "
        f"CHECK (status IN {_HOLD_STATUSES})"
    )
    op.create_index(
        "ix_reclaimrx_payment_holds_tenant_status",
        "reclaimrx_payment_holds",
        ["tenant_id", "status"],
    )


def downgrade() -> None:
    # Reverse in dependency order

    # 1. payment_holds — drop index, drop CHECK, drop column.
    op.execute(
        "ALTER TABLE reclaimrx_payment_holds DROP CONSTRAINT IF EXISTS ck_payment_holds_status"
    )
    op.drop_index("ix_reclaimrx_payment_holds_tenant_status",
                  table_name="reclaimrx_payment_holds")
    op.drop_column("reclaimrx_payment_holds", "status")

    # 2. investigations — drop indexes, drop CHECKs, drop columns in REVERSE order.
    for idx in [
        "ix_reclaimrx_investigations_tenant_source_ref",
        "ix_reclaimrx_investigations_tenant_member_id",
        "ix_reclaimrx_investigations_tenant_severity",
    ]:
        op.drop_index(idx, table_name="reclaimrx_investigations")
    for constraint in [
        "ck_investigations_outcome_label",
        "ck_investigations_source",
        "ck_investigations_severity",
    ]:
        op.execute(
            f"ALTER TABLE reclaimrx_investigations DROP CONSTRAINT IF EXISTS {constraint}"
        )
    # Columns dropped in EXACT reverse of upgrade insertion order.
    for col_name in [
        "threshold_snapshot",
        "threshold_config_version",
        "hold_amount",
        "recovered_amount",
        "outcome_label",
        "closed_by",
        "closed_at",
        "opened_by",
        "member_id",
        "source_ref_id",
        "source",
        "severity",
    ]:
        op.drop_column("reclaimrx_investigations", col_name)

    # 3. New tables — drop partial unique indexes BEFORE the tables
    # (Alembic does not auto-drop partial indexes created via raw SQL).
    for idx in [
        "uq_threshold_configs_current_per_tenant",
        "uq_graph_runs_one_running_per_tenant",
    ]:
        op.execute(f"DROP INDEX IF EXISTS {idx}")

    # 4. Drop tables in reverse dependency order (children before parents).
    op.drop_table("reclaimrx_outbox_events")
    op.drop_table("reclaimrx_threshold_config_audits")  # FK -> threshold_configs
    op.drop_table("reclaimrx_threshold_configs")
    op.drop_table("reclaimrx_accumulator_anomalies")
    op.drop_table("reclaimrx_fraud_rings")               # FK -> graph_runs
    op.drop_table("reclaimrx_graph_runs")
