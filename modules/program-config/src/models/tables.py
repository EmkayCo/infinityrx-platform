"""SQLAlchemy ORM models for the program_config schema.

All money columns: Numeric — never Float.
Every tenant-owned table: TenantScopedMixin.
No PHI in this module — BRDs contain business config, not member data.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from shared.db.tenant_context import TenantScopedMixin

SCHEMA = "program_config"


class ProgramConfigBase(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


def _ts_now() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# BRD Template Engine
# ---------------------------------------------------------------------------


class BrdTemplate(ProgramConfigBase, TenantScopedMixin):
    """Schema-driven form builder template for capturing client requirements.

    form_builder_schema JSONB shape:
      {
        "sections": [
          {
            "id": "program_basics",
            "title": "Program Basics",
            "fields": [
              {
                "id": "program_name",
                "type": "text",
                "label": "Program Name",
                "required": true,
                "validation": {"max_length": 200},
                "conditional": null
              }
            ]
          }
        ],
        "version": "1.0"
      }
    """

    __tablename__ = "brd_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", "version", name="uq_brd_template_slug_ver"),
        Index("idx_brd_template_tenant_type", "tenant_id", "program_type"),
        Index("idx_brd_template_active", "tenant_id", "is_active"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    program_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # copay|voucher|bridge|debit_card|specialty|workers_comp|340b|commercial|medicare|medicaid
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    form_builder_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class BrdSubmission(ProgramConfigBase, TenantScopedMixin):
    """A client's filled-in BRD submission against a template.

    parsed_data: structured dict of section_id -> field_id -> value
    validation_results: dict of field_id -> {valid: bool, message: str}
    """

    __tablename__ = "brd_submissions"
    __table_args__ = (
        Index("idx_brd_sub_tenant_status", "tenant_id", "status"),
        Index("idx_brd_sub_program", "tenant_id", "program_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    template_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    template_version_at_upload: Mapped[int] = mapped_column(Integer, nullable=False)
    program_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="draft"
    )  # draft|submitted|under_review|change_requested|approved|signed|applied
    parsed_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    validation_results: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Programs (with state machine)
# ---------------------------------------------------------------------------


class Program(ProgramConfigBase, TenantScopedMixin):
    """A configured patient assistance or copay program.

    Status state machine:
      draft → pending_review → approved → onboarding → active → suspended → terminated
    """

    __tablename__ = "programs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uq_program_external_id"),
        Index("idx_program_status", "tenant_id", "status"),
        Index("idx_program_type", "tenant_id", "program_type"),
        Index("idx_program_client", "tenant_id", "client_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    program_type: Mapped[str] = mapped_column(String(50), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    brd_submission_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    # BIN/PCN routing
    bin_number: Mapped[str | None] = mapped_column(String(10), nullable=True)
    pcn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    group_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Dates
    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    termination_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Wizard save state — stores current step + partial data
    wizard_step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    wizard_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # Post-launch elevated monitoring flag (30 days per PRD §6)
    post_launch_monitoring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    post_launch_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class ProgramDrug(ProgramConfigBase, TenantScopedMixin):
    """NDC/GPI entries included in a program's formulary."""

    __tablename__ = "program_drugs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "program_id", "ndc", name="uq_program_drug_ndc"),
        Index("idx_pgdrug_program", "tenant_id", "program_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    program_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    ndc: Mapped[str] = mapped_column(String(11), nullable=False)
    gpi: Mapped[str | None] = mapped_column(String(14), nullable=True)
    drug_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Per-drug copay cap and annual max — money as Numeric
    copay_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    per_fill_cap: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    annual_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------


class Contract(ProgramConfigBase, TenantScopedMixin):
    """Program contract with SLAs, fee schedules, and BFSF documentation.

    sla JSONB shape: {"processing_time_hours": 4, "uptime_pct": 99.9, ...}
    fees JSONB shape: {"per_claim": "0.50", "monthly_admin": "500.00", ...}
    amendments JSONB shape: [{"effective_date": "...", "changes": {...}, "approved_by": "..."}]
    spend_cap_config JSONB: {"cap_amount": "100000.00", "refund_guarantee": true, ...}
    bfsf_documentation JSONB: {"services_catalog": [...], "fmv_assessment": {...}, ...}
    """

    __tablename__ = "contracts"
    __table_args__ = (
        Index("idx_contract_program", "tenant_id", "program_id"),
        Index("idx_contract_status", "tenant_id", "status"),
        Index("idx_contract_renewal", "tenant_id", "auto_renewal_date"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    program_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="draft"
    )  # draft|active|expired|terminated|pending_renewal
    effective_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    termination_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    auto_renewal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_renewal_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    renewal_notice_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    sla: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    fees: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    amendments: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    spend_cap_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    bfsf_documentation: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # Encrypted signed document URL — stores as text (URL to encrypted blob, not raw content)
    signed_document_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_signature_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Onboarding Workflow
# ---------------------------------------------------------------------------


class OnboardingWorkflow(ProgramConfigBase, TenantScopedMixin):
    """Configurable 12-step onboarding workflow for each program.

    steps JSONB shape:
      [
        {"step_number": 1, "name": "contract_signed", "required": true, "sla_hours": 24},
        ...
      ]
    """

    __tablename__ = "onboarding_workflows"
    __table_args__ = (
        UniqueConstraint("tenant_id", "program_id", name="uq_onboarding_program"),
        Index("idx_onboarding_status", "tenant_id", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    program_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="not_started"
    )  # not_started|in_progress|blocked|completed
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    steps: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    go_live_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class OnboardingStepLog(ProgramConfigBase, TenantScopedMixin):
    """Immutable log of each onboarding step completion/failure."""

    __tablename__ = "onboarding_step_log"
    __table_args__ = (
        Index("idx_steplog_workflow", "tenant_id", "workflow_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # completed|skipped|blocked|failed
    performed_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sla_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Manufacturer Self-Service
# ---------------------------------------------------------------------------


class ManufacturerProgramConfig(ProgramConfigBase, TenantScopedMixin):
    """Self-service program builder data for manufacturer-configured programs.

    wizard_data JSONB captures the full 10-step wizard state.
    ai_recommendations JSONB stores CopayRecommender output for audit trail.
    accumulator_strategy: how to handle accumulator/maximizer patients.
    """

    __tablename__ = "manufacturer_program_configs"
    __table_args__ = (
        Index("idx_mfr_config_program", "tenant_id", "program_id"),
        Index("idx_mfr_config_status", "tenant_id", "review_status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    program_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    manufacturer_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="draft"
    )  # draft|submitted|under_review|approved|rejected|live
    wizard_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    ai_recommendations: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    accumulator_strategy: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Money fields: copay amounts in recommendations — Numeric, never Float
    recommended_copay_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    recommended_per_fill_cap: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    recommended_annual_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Program Activity Log (audit trail)
# ---------------------------------------------------------------------------


class ProgramActivityLog(ProgramConfigBase, TenantScopedMixin):
    """Append-only log of all state changes and actions on programs."""

    __tablename__ = "program_activity_log"
    __table_args__ = (
        Index("idx_activity_program", "tenant_id", "program_id"),
        Index("idx_activity_entity", "tenant_id", "entity_type", "entity_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    program_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    performed_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    correlation_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    occurred_at: Mapped[datetime] = _ts_now()
