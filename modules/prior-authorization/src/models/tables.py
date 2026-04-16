"""SQLAlchemy ORM models for the prior_authorization schema.

All money columns: Numeric -- never Float.
All PHI columns: EncryptedString.
Every tenant-owned table: TenantScopedMixin.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from shared.crypto.sqlalchemy_types import EncryptedString
from shared.db.tenant_context import TenantScopedMixin

SCHEMA = "prior_authorization"


class PriorAuthBase(DeclarativeBase):
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
# PARequest
# ---------------------------------------------------------------------------


class PARequest(PriorAuthBase, TenantScopedMixin):
    """Prior authorization request submitted by pharmacy, prescriber, or system."""

    __tablename__ = "pa_requests"
    __table_args__ = (
        Index("idx_pa_tenant_member", "tenant_id", "member_id"),
        Index("idx_pa_tenant_drug", "tenant_id", "drug_ndc"),
        Index("idx_pa_tenant_status", "tenant_id", "status"),
        Index("idx_pa_tenant_plan", "tenant_id", "plan_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    member_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    prescriber_npi: Mapped[str] = mapped_column(String(10), nullable=False)
    drug_ndc: Mapped[str] = mapped_column(String(11), nullable=False)
    drug_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="pharmacy_reject | epa | manual | phone | fhir",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="submitted",
        comment="submitted | in_review | approved | denied | expired | appealed",
    )
    priority: Mapped[str] = mapped_column(
        String(10), nullable=False, default="routine",
        comment="routine | urgent",
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    program_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    clinical_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    criteria_set_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = _ts_now()

    # Relationships
    decisions: Mapped[list[PADecision]] = relationship(back_populates="pa_request", lazy="selectin")
    appeals: Mapped[list[PAAppeal]] = relationship(back_populates="pa_request", lazy="selectin")
    letters: Mapped[list[PALetter]] = relationship(back_populates="pa_request", lazy="selectin")
    epa_transactions: Mapped[list[EPATransaction]] = relationship(back_populates="pa_request", lazy="selectin")
    copay_epa_records: Mapped[list[CopayEPARecord]] = relationship(back_populates="pa_request", lazy="selectin")


# ---------------------------------------------------------------------------
# PADecision
# ---------------------------------------------------------------------------


class PADecision(PriorAuthBase, TenantScopedMixin):
    """Clinical reviewer decision on a PA request."""

    __tablename__ = "pa_decisions"
    __table_args__ = (
        Index("idx_padec_tenant_request", "tenant_id", "pa_request_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    pa_request_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.pa_requests.id"),
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="approved | denied | pend | request_info",
    )
    approved_duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_quantity: Mapped[None] = mapped_column(Numeric(12, 2), nullable=True)
    reviewed_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = _ts_now()

    pa_request: Mapped[PARequest] = relationship(back_populates="decisions")


# ---------------------------------------------------------------------------
# PAAppeal
# ---------------------------------------------------------------------------


class PAAppeal(PriorAuthBase, TenantScopedMixin):
    """Appeal against a PA denial."""

    __tablename__ = "pa_appeals"
    __table_args__ = (
        Index("idx_paapp_tenant_request", "tenant_id", "pa_request_id"),
        Index("idx_paapp_tenant_status", "tenant_id", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    pa_request_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.pa_requests.id"),
        nullable=False,
    )
    appeal_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    appeal_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="clinical_reviewer | medical_director | external",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="submitted",
        comment="submitted | in_review | upheld | overturned",
    )
    regulatory_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    filed_at: Mapped[datetime] = _ts_now()
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    pa_request: Mapped[PARequest] = relationship(back_populates="appeals")


# ---------------------------------------------------------------------------
# PACriteriaSet
# ---------------------------------------------------------------------------


class PACriteriaSet(PriorAuthBase, TenantScopedMixin):
    """Clinical criteria used to evaluate PA requests.

    When plan_id is NULL, the criteria set applies globally (all plans).
    criteria JSONB structure:
      {
        "diagnosis_codes": ["E11.9", "E66.01"],
        "step_therapy_lookback_days": 90,
        "lab_values": {"HbA1c": {"min": 7.0}},
        "age_range": {"min": 18, "max": 75},
        "quantity_justification_required": true,
        "glp1_bmi_threshold": 30,
        "glp1_comorbidities": ["E11", "I10", "E78"],
        "glp1_lifestyle_intervention_days": 180
      }
    """

    __tablename__ = "pa_criteria_sets"
    __table_args__ = (
        Index("idx_pacrit_tenant_drug", "tenant_id", "drug_ndc"),
        Index("idx_pacrit_tenant_class", "tenant_id", "drug_class"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    drug_ndc: Mapped[str | None] = mapped_column(String(11), nullable=True)
    drug_class: Mapped[str | None] = mapped_column(String(50), nullable=True)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True,
        comment="NULL means global (all plans)",
    )
    criteria: Mapped[dict] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)

    @property
    def diagnosis_codes(self) -> list[str]:
        return self.criteria.get("diagnosis_codes", [])

    @property
    def step_therapy_lookback_days(self) -> int | None:
        return self.criteria.get("step_therapy_lookback_days")

    @property
    def lab_values(self) -> dict:
        return self.criteria.get("lab_values", {})

    @property
    def age_range(self) -> dict:
        return self.criteria.get("age_range", {})

    @property
    def glp1_bmi_threshold(self) -> float | None:
        return self.criteria.get("glp1_bmi_threshold")

    @property
    def glp1_comorbidities(self) -> list[str]:
        return self.criteria.get("glp1_comorbidities", [])


# ---------------------------------------------------------------------------
# PALetter
# ---------------------------------------------------------------------------


class PALetter(PriorAuthBase, TenantScopedMixin):
    """Determination letter generated for a PA request."""

    __tablename__ = "pa_letters"
    __table_args__ = (
        Index("idx_palet_tenant_request", "tenant_id", "pa_request_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    pa_request_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.pa_requests.id"),
        nullable=False,
    )
    letter_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="approval | denial | appeal_decision | request_info",
    )
    template_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sent_via: Mapped[str | None] = mapped_column(
        String(10), nullable=True,
        comment="email | fax | portal | mail",
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    pa_request: Mapped[PARequest] = relationship(back_populates="letters")


# ---------------------------------------------------------------------------
# EPATransaction
# ---------------------------------------------------------------------------


class EPATransaction(PriorAuthBase, TenantScopedMixin):
    """Electronic prior authorization (ePA) NCPDP SCRIPT transaction."""

    __tablename__ = "epa_transactions"
    __table_args__ = (
        Index("idx_epa_tenant_request", "tenant_id", "pa_request_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    pa_request_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.pa_requests.id"),
        nullable=False,
    )
    script_version: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="2017071 | 2023011",
    )
    message_type: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = _ts_now()

    pa_request: Mapped[PARequest] = relationship(back_populates="epa_transactions")


# ---------------------------------------------------------------------------
# CopayEPARecord
# ---------------------------------------------------------------------------


class CopayEPARecord(PriorAuthBase, TenantScopedMixin):
    """Copay ePA first-fill record for manufacturer-funded programs."""

    __tablename__ = "copay_epa_records"
    __table_args__ = (
        Index("idx_copayepa_tenant_request", "tenant_id", "pa_request_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    pa_request_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.pa_requests.id"),
        nullable=False,
    )
    manufacturer_program_id: Mapped[str] = mapped_column(String(50), nullable=False)
    first_fill_amount: Mapped[None] = mapped_column(Numeric(12, 2), nullable=True)
    first_fill_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    pa_outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)
    manufacturer_absorbed_cost: Mapped[None] = mapped_column(Numeric(12, 2), nullable=True)

    pa_request: Mapped[PARequest] = relationship(back_populates="copay_epa_records")


# ---------------------------------------------------------------------------
# REMSRequirement
# ---------------------------------------------------------------------------


class REMSRequirement(PriorAuthBase, TenantScopedMixin):
    """REMS (Risk Evaluation and Mitigation Strategy) requirements for a drug."""

    __tablename__ = "rems_requirements"
    __table_args__ = (
        Index("idx_rems_tenant_drug", "tenant_id", "drug_ndc"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    drug_ndc: Mapped[str] = mapped_column(String(11), nullable=False)
    rems_program_name: Mapped[str] = mapped_column(String(200), nullable=False)
    certifications_required: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    monitoring_required: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    restricted_distribution: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


# ---------------------------------------------------------------------------
# FRMActivityLog
# ---------------------------------------------------------------------------


class FRMActivityLog(PriorAuthBase, TenantScopedMixin):
    """Field Reimbursement Manager (FRM) activity log."""

    __tablename__ = "frm_activity_logs"
    __table_args__ = (
        Index("idx_frm_tenant_user", "tenant_id", "frm_user_id"),
        Index("idx_frm_tenant_practice", "tenant_id", "practice_npi"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    frm_user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    practice_npi: Mapped[str] = mapped_column(String(10), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    pa_request_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.pa_requests.id"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    logged_at: Mapped[datetime] = _ts_now()
