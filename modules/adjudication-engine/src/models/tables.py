"""SQLAlchemy ORM models for the adjudication_engine schema.

All money columns: Numeric — never Float.
Every tenant-owned table: TenantScopedMixin.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from shared.db.tenant_context import TenantScopedMixin

SCHEMA = "adjudication_engine"


class AdjudicationBase(DeclarativeBase):
    """Declarative base for the adjudication-engine module."""


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
# CLAIM TRANSACTION
# ---------------------------------------------------------------------------


class ClaimTransaction(AdjudicationBase, TenantScopedMixin):
    """Core claim adjudication record.

    Tracks every pharmacy claim processed through the adjudication pipeline,
    including pricing breakdown, DUR alerts, fraud scoring, and full audit
    trail of every adjudication step taken.

    Transaction types follow NCPDP D.0:
    - B1 = new billing
    - B2 = reversal
    - B3 = rebill
    - E1 = eligibility verification
    """

    __tablename__ = "claim_transactions"
    __table_args__ = (
        Index("idx_claim_tenant_member", "tenant_id", "member_id"),
        Index("idx_claim_tenant_pharmacy", "tenant_id", "pharmacy_npi"),
        Index("idx_claim_tenant_prescriber", "tenant_id", "prescriber_npi"),
        Index("idx_claim_tenant_ndc", "tenant_id", "drug_ndc"),
        Index("idx_claim_tenant_status", "tenant_id", "status"),
        Index("idx_claim_tenant_date", "tenant_id", "date_of_service"),
        Index("idx_claim_tenant_type", "tenant_id", "transaction_type"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    member_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    pharmacy_npi: Mapped[str] = mapped_column(String(10), nullable=False)
    prescriber_npi: Mapped[str] = mapped_column(String(10), nullable=False)
    drug_ndc: Mapped[str] = mapped_column(String(11), nullable=False)
    drug_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    day_supply: Mapped[int] = mapped_column(Integer, nullable=False)
    date_of_service: Mapped[datetime] = mapped_column(Date, nullable=False)

    # NCPDP transaction type
    transaction_type: Mapped[str] = mapped_column(
        String(2), nullable=False
    )  # B1/B2/B3/E1

    # Pricing breakdown — ALL Numeric, never Float
    ingredient_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    dispensing_fee: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    patient_pay: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    plan_pay: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    pricing_model_used: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Adjudication outcome
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # paid/rejected/reversed/pending
    reject_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Plain English adjudication reasoning and full step trace
    adjudication_reasons: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    claim_trace: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Accumulator / fraud detection
    accumulator_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    copay_fraud_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)

    # DUR and COB
    dur_alerts: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    cob_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Override tracking
    override_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# CLAIM OVERRIDE
# ---------------------------------------------------------------------------


class ClaimOverride(AdjudicationBase, TenantScopedMixin):
    """Rule-level override for a member, optionally scoped to drug or pharmacy.

    Overrides let authorized users bypass specific rules for a member
    when clinical or business circumstances warrant an exception. Each
    override has a defined scope and duration, with an approval workflow
    for high-risk overrides.

    Scope values:
    - member_rule_drug: override applies only when the member fills a specific NDC
    - member_rule_any: override applies to the member for any drug under the rule
    - member_rule_pharmacy: override applies only at a specific pharmacy
    """

    __tablename__ = "claim_overrides"
    __table_args__ = (
        Index("idx_override_tenant_member", "tenant_id", "member_id"),
        Index("idx_override_tenant_rule", "tenant_id", "rule_id"),
        Index("idx_override_tenant_status", "tenant_id", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    member_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    rule_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(100), nullable=False)
    ndc: Mapped[str | None] = mapped_column(String(11), nullable=True)

    scope: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # member_rule_drug/member_rule_any/member_rule_pharmacy

    reason_code: Mapped[str] = mapped_column(String(50), nullable=False)
    reason_text: Mapped[str] = mapped_column(Text, nullable=False)

    duration_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # one_time/fixed_period/benefit_year/permanent

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending_approval"
    )  # pending_approval/active/expired/revoked

    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_claim_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )

    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# OVERRIDE APPROVAL CONFIG
# ---------------------------------------------------------------------------


class OverrideApprovalConfig(AdjudicationBase, TenantScopedMixin):
    """Per-tenant configuration for which override types require supervisor approval."""

    __tablename__ = "override_approval_configs"
    __table_args__ = (
        Index("idx_approval_cfg_tenant_rule", "tenant_id", "rule_type"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    rule_type: Mapped[str] = mapped_column(String(100), nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    approver_role: Mapped[str] = mapped_column(String(100), nullable=False, default="supervisor")


# ---------------------------------------------------------------------------
# DUR SCREENING LOG
# ---------------------------------------------------------------------------


class DURScreeningLog(AdjudicationBase, TenantScopedMixin):
    """Log of Drug Utilization Review checks performed during adjudication.

    Each row represents a single DUR check (drug-drug interaction,
    therapeutic duplication, early refill, quantity validation) and the
    action taken (reject, flag for review, informational only).
    """

    __tablename__ = "dur_screening_logs"
    __table_args__ = (
        Index("idx_dur_tenant_claim", "tenant_id", "claim_id"),
        Index("idx_dur_tenant_check", "tenant_id", "check_type"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    claim_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    check_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # drug_drug/therapeutic_dup/early_refill/quantity

    severity: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # critical/major/minor/info

    description: Mapped[str] = mapped_column(Text, nullable=False)

    action_taken: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # reject/flag/info

    drug_a_ndc: Mapped[str | None] = mapped_column(String(11), nullable=True)
    drug_b_ndc: Mapped[str | None] = mapped_column(String(11), nullable=True)

    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# COPAY FRAUD FLAG
# ---------------------------------------------------------------------------


class CopayFraudFlag(AdjudicationBase, TenantScopedMixin):
    """Fraud signal detected during claim adjudication.

    Flag types:
    - bill_reverse_rebill: pattern of billing, reversing, and rebilling
    - volume_spike: abnormal dispensing volume at a pharmacy
    - collusion: pharmacy/prescriber relationship anomaly
    - geographic: member/pharmacy distance anomaly
    - identity: cardholder identity inconsistency
    """

    __tablename__ = "copay_fraud_flags"
    __table_args__ = (
        Index("idx_fraud_tenant_claim", "tenant_id", "claim_id"),
        Index("idx_fraud_tenant_type", "tenant_id", "flag_type"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    claim_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    flag_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # bill_reverse_rebill/volume_spike/collusion/geographic/identity

    score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    action: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # block/flag/pass

    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# DRUG WASTE ALERT
# ---------------------------------------------------------------------------


class DrugWasteAlert(AdjudicationBase, TenantScopedMixin):
    """Identified drug waste opportunity during or after adjudication.

    Alert types:
    - abandoned: prescription filled but never picked up
    - early_discontinuation: therapy stopped prematurely
    - dose_optimization: lower dose could achieve same clinical outcome
    - days_supply_waste: excessive days supply leading to expiration waste
    """

    __tablename__ = "drug_waste_alerts"
    __table_args__ = (
        Index("idx_waste_tenant_claim", "tenant_id", "claim_id"),
        Index("idx_waste_tenant_type", "tenant_id", "alert_type"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    claim_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    alert_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # abandoned/early_discontinuation/dose_optimization/days_supply_waste

    drug_ndc: Mapped[str] = mapped_column(String(11), nullable=False)
    estimated_waste: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    created_at: Mapped[datetime] = _ts_now()
