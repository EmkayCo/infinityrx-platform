"""SQLAlchemy ORM models for the dataiq schema.

Follows PRD data model exactly. All tenant-owned tables inherit TenantScopedMixin.
Money columns use sa.Numeric — never sa.Float.
PostGIS geometry columns defined as Text for portability; production migrations
add the actual geometry type via raw DDL.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base
from shared.db.tenant_context import TenantScopedMixin

SCHEMA = "dataiq"


def _uuid_pk() -> Mapped[UUID]:
    return mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.func.gen_random_uuid(),
    )


def _ts_now() -> Mapped[datetime]:
    return mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


class MetricDefinition(Base):
    """Global metric definitions — not tenant-scoped (shared reference data)."""

    __tablename__ = "metric_definitions"
    __table_args__ = (
        sa.UniqueConstraint("metric_key", name="uq_metric_definitions_metric_key"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    metric_key: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text)
    category: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    calculation_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    source_event: Mapped[str | None] = mapped_column(sa.String(100))
    aggregation: Mapped[str | None] = mapped_column(sa.String(50))
    dimensions: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    spc_enabled: Mapped[bool] = mapped_column(sa.Boolean, server_default="false")
    spc_window_days: Mapped[int] = mapped_column(sa.Integer, server_default="30")
    spc_sigma_threshold: Mapped[Any] = mapped_column(
        sa.Numeric(4, 2), server_default="2.00", nullable=False
    )
    created_at: Mapped[datetime] = _ts_now()


class MetricSnapshot(Base, TenantScopedMixin):
    """Hourly/daily snapshots of tenant KPI values for trend analysis."""

    __tablename__ = "metric_snapshots"
    __table_args__ = (
        sa.Index(
            "idx_metrics_tenant_date",
            "tenant_id",
            "metric_definition_id",
            sa.text("snapshot_date DESC"),
        ),
        sa.Index("ix_metric_snapshots_tenant_id", "tenant_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey(f"{SCHEMA}.metric_definitions.id", use_alter=True),
        nullable=False,
        index=True,
    )
    metric_definition_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey(f"{SCHEMA}.metric_definitions.id"),
        nullable=False,
    )
    snapshot_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    snapshot_hour: Mapped[int | None] = mapped_column(sa.Integer)
    dimensions: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    value: Mapped[Any] = mapped_column(sa.Numeric(18, 4), nullable=False)
    sample_count: Mapped[int | None] = mapped_column(sa.Integer)
    moving_average: Mapped[Any | None] = mapped_column(sa.Numeric(18, 4))
    standard_deviation: Mapped[Any | None] = mapped_column(sa.Numeric(18, 4))
    upper_control_limit: Mapped[Any | None] = mapped_column(sa.Numeric(18, 4))
    lower_control_limit: Mapped[Any | None] = mapped_column(sa.Numeric(18, 4))
    is_anomalous: Mapped[bool] = mapped_column(sa.Boolean, server_default="false")
    created_at: Mapped[datetime] = _ts_now()


class DataQualityScore(Base, TenantScopedMixin):
    """Daily data quality scores per tenant."""

    __tablename__ = "data_quality_scores"
    __table_args__ = (
        sa.UniqueConstraint("tenant_id", "score_date", name="uq_data_quality_scores_tenant_date"),
        sa.Index("ix_data_quality_scores_tenant_id", "tenant_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    score_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    overall_score: Mapped[Any] = mapped_column(sa.Numeric(5, 2), nullable=False)
    volume_score: Mapped[Any | None] = mapped_column(sa.Numeric(5, 2))
    completeness_score: Mapped[Any | None] = mapped_column(sa.Numeric(5, 2))
    format_score: Mapped[Any | None] = mapped_column(sa.Numeric(5, 2))
    timeliness_score: Mapped[Any | None] = mapped_column(sa.Numeric(5, 2))
    consistency_score: Mapped[Any | None] = mapped_column(sa.Numeric(5, 2))
    referential_score: Mapped[Any | None] = mapped_column(sa.Numeric(5, 2))
    issues: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class Benchmark(Base, TenantScopedMixin):
    """Configurable benchmarks for metric comparison."""

    __tablename__ = "benchmarks"
    __table_args__ = (
        sa.Index("ix_benchmarks_tenant_id", "tenant_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    metric_key: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    benchmark_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    target_value: Mapped[Any | None] = mapped_column(sa.Numeric(18, 4))
    warning_threshold: Mapped[Any | None] = mapped_column(sa.Numeric(18, 4))
    critical_threshold: Mapped[Any | None] = mapped_column(sa.Numeric(18, 4))
    comparison_operator: Mapped[str] = mapped_column(sa.String(10), server_default="gte")
    comparison_entity_type: Mapped[str | None] = mapped_column(sa.String(100))
    comparison_entity_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default="true")
    created_at: Mapped[datetime] = _ts_now()


class SavedExploration(Base, TenantScopedMixin):
    """User-saved self-service exploration configurations."""

    __tablename__ = "saved_explorations"
    __table_args__ = (
        sa.Index("ix_saved_explorations_tenant_id", "tenant_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    exploration_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_shared: Mapped[bool] = mapped_column(sa.Boolean, server_default="false")
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


class InsightAlert(Base, TenantScopedMixin):
    """Auto-generated insight alerts from analytics detection."""

    __tablename__ = "insight_alerts"
    __table_args__ = (
        sa.CheckConstraint(
            "severity IN ('info', 'warning', 'critical')",
            name="insight_alerts_severity_valid",
        ),
        sa.Index("ix_insight_alerts_tenant_id", "tenant_id"),
        sa.Index("ix_insight_alerts_tenant_created", "tenant_id", "created_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    insight_type: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    severity: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    metric_key: Mapped[str | None] = mapped_column(sa.String(255))
    metric_value: Mapped[Any | None] = mapped_column(sa.Numeric(18, 4))
    threshold_value: Mapped[Any | None] = mapped_column(sa.Numeric(18, 4))
    affected_entity_type: Mapped[str | None] = mapped_column(sa.String(100))
    affected_entity_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    affected_entity_name: Mapped[str | None] = mapped_column(sa.String(255))
    recommended_action: Mapped[str | None] = mapped_column(sa.Text)
    acknowledged_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    acknowledged_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    created_at: Mapped[datetime] = _ts_now()


class ForecastModel(Base, TenantScopedMixin):
    """Trained forecast models with results."""

    __tablename__ = "forecast_models"
    __table_args__ = (
        sa.Index("ix_forecast_models_tenant_id", "tenant_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    forecast_type: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    metric_key: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    input_period_months: Mapped[int] = mapped_column(sa.Integer, server_default="24")
    model_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    model_parameters: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    forecast_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    confidence_interval: Mapped[Any] = mapped_column(
        sa.Numeric(5, 2), server_default="0.95", nullable=False
    )
    mape: Mapped[Any | None] = mapped_column(sa.Numeric(8, 4))
    created_at: Mapped[datetime] = _ts_now()


class TrendDecomposition(Base, TenantScopedMixin):
    """Stored drug trend decomposition results by period pair and drug class."""

    __tablename__ = "trend_decomposition"
    __table_args__ = (
        sa.UniqueConstraint(
            "tenant_id", "period_pair", "drug_class",
            name="uq_trend_decomposition_tenant_period_class",
        ),
        sa.Index("ix_trend_decomposition_tenant_id", "tenant_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    period_pair: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    drug_class: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    utilization_effect: Mapped[Any] = mapped_column(sa.Numeric(18, 4), nullable=False)
    price_effect: Mapped[Any] = mapped_column(sa.Numeric(18, 4), nullable=False)
    mix_effect: Mapped[Any] = mapped_column(sa.Numeric(18, 4), nullable=False)
    total_delta: Mapped[Any] = mapped_column(sa.Numeric(18, 4), nullable=False)
    old_spend: Mapped[Any] = mapped_column(sa.Numeric(18, 4), nullable=False)
    new_spend: Mapped[Any] = mapped_column(sa.Numeric(18, 4), nullable=False)
    created_at: Mapped[datetime] = _ts_now()


class RepricingRun(Base, TenantScopedMixin):
    """Claims repricing run results (idempotent by plan_design_hash)."""

    __tablename__ = "repricing_runs"
    __table_args__ = (
        sa.UniqueConstraint(
            "tenant_id", "plan_design_hash",
            name="uq_repricing_runs_tenant_hash",
        ),
        sa.Index("ix_repricing_runs_tenant_id", "tenant_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    plan_design_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    plan_design: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    claim_set_id: Mapped[str | None] = mapped_column(sa.String(255))
    total_claims: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    total_original_plan_paid: Mapped[Any] = mapped_column(
        sa.Numeric(18, 2), nullable=False, server_default="0"
    )
    total_repriced_plan_paid: Mapped[Any] = mapped_column(
        sa.Numeric(18, 2), nullable=False, server_default="0"
    )
    total_delta: Mapped[Any] = mapped_column(
        sa.Numeric(18, 2), nullable=False, server_default="0"
    )
    status: Mapped[str] = mapped_column(sa.String(20), server_default="pending")
    created_at: Mapped[datetime] = _ts_now()


class KpiRollup(Base, TenantScopedMixin):
    """Hourly KPI rollups from Redis → Postgres warm storage."""

    __tablename__ = "kpi_rollups"
    __table_args__ = (
        sa.UniqueConstraint(
            "tenant_id", "metric_key", "granularity", "bucket_ts",
            name="uq_kpi_rollups_tenant_metric_bucket",
        ),
        sa.Index("ix_kpi_rollups_tenant_id", "tenant_id"),
        sa.Index(
            "ix_kpi_rollups_tenant_metric_ts",
            "tenant_id",
            "metric_key",
            "bucket_ts",
        ),
        sa.UniqueConstraint("tenant_id", name="uq_kpi_rollups_tenant_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    metric_key: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    granularity: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    bucket_ts: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    value: Mapped[Any] = mapped_column(sa.Numeric(18, 4), nullable=False)
    created_at: Mapped[datetime] = _ts_now()


class SPCAlert(Base, TenantScopedMixin):
    """SPC anomaly alerts with Western Electric rule violations."""

    __tablename__ = "spc_alerts"
    __table_args__ = (
        sa.Index("ix_spc_alerts_tenant_id", "tenant_id"),
        sa.Index("ix_spc_alerts_tenant_metric", "tenant_id", "metric_key"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    metric_key: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    rule_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    severity: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    value: Mapped[Any] = mapped_column(sa.Numeric(18, 4), nullable=False)
    ucl: Mapped[Any] = mapped_column(sa.Numeric(18, 4), nullable=False)
    lcl: Mapped[Any] = mapped_column(sa.Numeric(18, 4), nullable=False)
    mean: Mapped[Any] = mapped_column(sa.Numeric(18, 4), nullable=False)
    std_dev: Mapped[Any] = mapped_column(sa.Numeric(18, 4), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = _ts_now()


__all__ = [
    "Benchmark",
    "DataQualityScore",
    "ForecastModel",
    "InsightAlert",
    "KpiRollup",
    "MetricDefinition",
    "MetricSnapshot",
    "RepricingRun",
    "SPCAlert",
    "SavedExploration",
    "TrendDecomposition",
]
