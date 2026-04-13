"""SQLAlchemy ORM models for the reporting schema.

All monetary fields use NUMERIC(precision, scale) — never FLOAT.
All models are tenant-scoped; queries must always filter by tenant_id.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from shared.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class ReportDefinition(Base):
    __tablename__ = "report_definitions"
    __table_args__ = {"schema": "reporting"}  # noqa: RUF012

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    data_source: Mapped[str] = mapped_column(String(100), nullable=False)
    base_query: Mapped[str | None] = mapped_column(Text, nullable=True)

    columns: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    default_filters: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    default_groupings: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    default_sort: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    calculated_fields: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    summary_row: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    chart_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    chart_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    required_permission: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    contains_phi: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class ReportSchedule(Base):
    __tablename__ = "report_schedules"
    __table_args__ = {"schema": "reporting"}  # noqa: RUF012

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    report_definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reporting.report_definitions.id"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    frequency: Mapped[str] = mapped_column(String(50), nullable=False)
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_of_day: Mapped[time] = mapped_column(Time, nullable=False, default=time(6, 0))
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="America/New_York")

    filters: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    output_format: Mapped[str] = mapped_column(String(50), nullable=False)
    delivery_method: Mapped[str] = mapped_column(String(50), nullable=False)
    delivery_recipients: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    sftp_config_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    include_cover_page: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    include_charts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class ReportRun(Base):
    __tablename__ = "report_runs"
    __table_args__ = {"schema": "reporting"}  # noqa: RUF012

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    report_definition_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    schedule_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    filters_applied: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    requested_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_format: Mapped[str | None] = mapped_column(String(50), nullable=True)
    output_file_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    delivery_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    phi_accessed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    phi_access_logged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class Dashboard(Base):
    __tablename__ = "dashboards"
    __table_args__ = {"schema": "reporting"}  # noqa: RUF012

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    role_target: Mapped[str | None] = mapped_column(String(100), nullable=True)
    layout: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)

    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class UserDashboard(Base):
    __tablename__ = "user_dashboards"
    __table_args__ = (
        UniqueConstraint("user_id", "dashboard_id", name="uq_user_dashboards_user_id_dashboard_id"),
        {"schema": "reporting"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    dashboard_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("reporting.dashboards.id"), nullable=True
    )

    custom_layout: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    pinned_filters: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class FilterPreset(Base):
    __tablename__ = "filter_presets"
    __table_args__ = {"schema": "reporting"}  # noqa: RUF012

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    applies_to: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class RegulatorySubmission(Base):
    __tablename__ = "regulatory_submissions"
    __table_args__ = {"schema": "reporting"}  # noqa: RUF012

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    report_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    file_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    submission_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)

    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class ActuarialModel(Base):
    __tablename__ = "actuarial_models"
    __table_args__ = {"schema": "reporting"}  # noqa: RUF012

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    input_data_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_parameters: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    results: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # NUMERIC for confidence interval — never float
    confidence_interval: Mapped[Any] = mapped_column(Numeric(8, 2), nullable=True)
    methodology: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")

    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class PhiAccessLog(Base):
    """Tracks every access to PHI-containing reports for compliance auditing."""

    __tablename__ = "phi_access_log"
    __table_args__ = {"schema": "reporting"}  # noqa: RUF012

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    report_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    report_definition_id: Mapped[str] = mapped_column(String(36), nullable=False)
    access_type: Mapped[str] = mapped_column(String(50), nullable=False)
    masking_level: Mapped[str] = mapped_column(String(50), nullable=False, default="full_detail")
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class AlertReportMapping(Base):
    """Maps event alerts to reports that auto-generate on trigger."""

    __tablename__ = "alert_report_mappings"
    __table_args__ = {"schema": "reporting"}  # noqa: RUF012

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    report_definition_id: Mapped[str] = mapped_column(String(36), nullable=False)
    filter_template: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    delivery_method: Mapped[str] = mapped_column(String(50), nullable=False, default="email")
    delivery_recipients: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    dedup_window_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
