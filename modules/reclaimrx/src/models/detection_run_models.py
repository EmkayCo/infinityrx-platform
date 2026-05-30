from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src._shim.db import Base

_SCHEMA = "reclaimrx"


def _now() -> datetime:
    return datetime.now(UTC)


def _uuid4() -> uuid.UUID:
    return uuid.uuid4()


class DetectionRun(Base):
    __tablename__ = "detection_runs"
    __table_args__ = {"schema": _SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    data_source: Mapped[str] = mapped_column(String(32), nullable=False)
    run_label: Mapped[str] = mapped_column(String(255), nullable=False)
    source_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    period_start: Mapped[object | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[object | None] = mapped_column(Date, nullable=True)
    filter_client_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    filter_program_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    filter_pharmacy_npi: Mapped[str | None] = mapped_column(String(10), nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    anomaly_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resolution_stats: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="in_progress")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)


class CsvUploadRow(Base):
    __tablename__ = "csv_upload_rows"
    __table_args__ = {"schema": _SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    detection_run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{_SCHEMA}.detection_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    row_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    resolved_client_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    resolved_program_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    resolved_pharmacy_npi: Mapped[str | None] = mapped_column(String(10), nullable=True)
    resolved_ndc: Mapped[str | None] = mapped_column(String(20), nullable=True)
    resolution_method: Mapped[str] = mapped_column(String(32), nullable=False)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class RecoupCase(Base):
    __tablename__ = "recoup_cases"
    __table_args__ = {"schema": _SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_number: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_client_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    scope_program_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    scope_pharmacy_npi: Mapped[str | None] = mapped_column(String(10), nullable=True)
    scope_filter: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    anomaly_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_amount_at_risk: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total_recovered: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    opened_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    close_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    audit_log: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class Anomaly(Base):
    __tablename__ = "anomalies"
    __table_args__ = {"schema": _SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    data_source: Mapped[str] = mapped_column(String(32), nullable=False)
    data_source_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{_SCHEMA}.detection_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    program_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    pharmacy_npi: Mapped[str | None] = mapped_column(String(10), nullable=True)
    ndc: Mapped[str | None] = mapped_column(String(20), nullable=True)
    claim_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    source_table: Mapped[str] = mapped_column(String(32), nullable=False)
    source_row_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    detection_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    detection_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[object] = mapped_column(Numeric(5, 4), nullable=False)
    date_of_service: Mapped[object | None] = mapped_column(Date, nullable=True)
    rx_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prescriber_npi: Mapped[str | None] = mapped_column(String(10), nullable=True)
    days_supply: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quantity: Mapped[object | None] = mapped_column(Numeric(10, 3), nullable=True)
    amount_paid: Mapped[object | None] = mapped_column(Numeric(12, 2), nullable=True)
    amount_billed: Mapped[object | None] = mapped_column(Numeric(12, 2), nullable=True)
    finding_code: Mapped[str] = mapped_column(String(50), nullable=False)
    finding_summary: Mapped[str] = mapped_column(Text, nullable=False)
    finding_details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{_SCHEMA}.recoup_cases.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolution_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    recovery_amount: Mapped[object | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class CaseAssignment(Base):
    __tablename__ = "case_assignments"
    __table_args__ = {"schema": _SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{_SCHEMA}.recoup_cases.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_to: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    assigned_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    unassigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unassign_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class CaseAnomalyLink(Base):
    __tablename__ = "case_anomaly_links"
    __table_args__ = {"schema": _SCHEMA}

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{_SCHEMA}.recoup_cases.id", ondelete="CASCADE"),
        primary_key=True,
    )
    anomaly_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{_SCHEMA}.anomalies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    linked_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)


class AnomalyAuditLog(Base):
    __tablename__ = "anomaly_audit_log"
    __table_args__ = {"schema": _SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    anomaly_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{_SCHEMA}.anomalies.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    performed_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class CaseNumberSequence(Base):
    __tablename__ = "case_number_sequences"
    __table_args__ = {"schema": _SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    prefix: Mapped[str] = mapped_column(String(10), nullable=False, default="RX-")
    next_number: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    padding: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class DetectionRuleType(Base):
    __tablename__ = "detection_rule_types"
    __table_args__ = {"schema": _SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid4)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    family: Mapped[str] = mapped_column(String(2), nullable=False)
    parameter_schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    default_severity: Mapped[str] = mapped_column(String(16), nullable=False)
    default_confidence: Mapped[object] = mapped_column(Numeric(5, 4), nullable=False)
    requires_baseline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_history: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deferred_data_feed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deferred_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    required_data_columns: Mapped[list] = mapped_column(ARRAY(String(64)), nullable=False, default=list)
    default_parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class DetectionRuleInstance(Base):
    __tablename__ = "detection_rule_instances"
    __table_args__ = {"schema": _SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    rule_type_code: Mapped[str] = mapped_column(
        String(50),
        ForeignKey(f"{_SCHEMA}.detection_rule_types.code", ondelete="RESTRICT"),
        nullable=False,
    )
    instance_name: Mapped[str] = mapped_column(String(120), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    severity_override: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence_override: Mapped[object | None] = mapped_column(Numeric(5, 4), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    applies_to_client_ids: Mapped[list | None] = mapped_column(ARRAY(PG_UUID(as_uuid=True)), nullable=True)
    applies_to_program_ids: Mapped[list | None] = mapped_column(ARRAY(PG_UUID(as_uuid=True)), nullable=True)
    applies_to_pharmacy_npis: Mapped[list | None] = mapped_column(ARRAY(String(10)), nullable=True)
    effective_from: Mapped[object] = mapped_column(Date, nullable=False)
    termination_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    created_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class DetectionRuleEvaluationLog(Base):
    __tablename__ = "detection_rule_evaluation_log"
    __table_args__ = {"schema": _SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    rule_instance_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{_SCHEMA}.detection_rule_instances.id", ondelete="CASCADE"),
        nullable=False,
    )
    detection_run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{_SCHEMA}.detection_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_table: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_row_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    evaluation_result: Mapped[str] = mapped_column(String(32), nullable=False)
    anomaly_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{_SCHEMA}.anomalies.id", ondelete="SET NULL"),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)


class BaselineCache(Base):
    __tablename__ = "baseline_cache"
    __table_args__ = {"schema": _SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    baseline_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    data_source: Mapped[str] = mapped_column(String(32), nullable=False)
    mean: Mapped[object | None] = mapped_column(Numeric(20, 8), nullable=True)
    stddev: Mapped[object | None] = mapped_column(Numeric(20, 8), nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    ttl_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=86400)


class MlDetectorRegistry(Base):
    __tablename__ = "ml_detector_registry"
    __table_args__ = {"schema": _SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid4)
    detector_name: Mapped[str] = mapped_column(String(100), nullable=False)
    detector_version: Mapped[str] = mapped_column(String(20), nullable=False, default="0")
    model_artifact_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    feature_schema_class: Mapped[str] = mapped_column(String(255), nullable=False)
    is_placeholder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    training_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class MlTrainingRun(Base):
    __tablename__ = "ml_training_runs"
    __table_args__ = {"schema": _SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    detector_name: Mapped[str] = mapped_column(String(100), nullable=False)
    training_data_source: Mapped[str] = mapped_column(String(255), nullable=False)
    training_data_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    training_data_record_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    features_used: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    training_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    training_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="in_progress")
    resulting_artifact_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)


class FlaggedNpi(Base):
    __tablename__ = "flagged_npis"
    __table_args__ = {"schema": _SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    npi_type: Mapped[str] = mapped_column(Text, nullable=False)
    npi_value: Mapped[str] = mapped_column(Text, nullable=False)
    flag_reason: Mapped[str] = mapped_column(Text, nullable=False)
    flagged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    flagged_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score_threshold_override: Mapped[object | None] = mapped_column(Numeric(5, 4), nullable=True)
    auto_create_investigation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    npi_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)