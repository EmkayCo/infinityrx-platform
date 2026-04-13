"""ReclaimRx SQLAlchemy ORM models (reclaimrx schema).

Rules:
- No float/Float for money fields — all use Numeric(precision, scale).
- Tenant isolation: every query must filter by tenant_id.
- All timestamps are timezone-aware.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import INTEGER as SQLITE_INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src._shim.db import Base

_BigIntAutoPK = BigInteger().with_variant(SQLITE_INTEGER(), "sqlite")


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


# ─────────────────────────────────────────────────────────────────────────────
# DETECTION RULES
# ─────────────────────────────────────────────────────────────────────────────


class DetectionRule(Base):
    __tablename__ = "reclaimrx_detection_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    rule_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)

    client_types: Mapped[dict] = mapped_column(JSON, nullable=False, default=lambda: ["all"])
    detection_mode: Mapped[str] = mapped_column(String(50), nullable=False)

    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)
    rule_logic: Mapped[dict] = mapped_column(JSON, nullable=False)
    default_parameters: Mapped[dict] = mapped_column(JSON, nullable=False)

    default_action: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence_scoring: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    tenant_configs: Mapped[list[TenantRuleConfig]] = relationship(back_populates="rule", cascade="all, delete-orphan")


class TenantRuleConfig(Base):
    __tablename__ = "reclaimrx_tenant_rule_configs"
    __table_args__ = (UniqueConstraint("tenant_id", "detection_rule_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    detection_rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("reclaimrx_detection_rules.id"), nullable=False)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    custom_parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    custom_action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    custom_confidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    applies_to_programs: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    rule: Mapped[DetectionRule] = relationship(back_populates="tenant_configs")


class DetectionProfile(Base):
    __tablename__ = "reclaimrx_detection_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_type: Mapped[str] = mapped_column(String(50), nullable=False)
    rule_ids: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


# ─────────────────────────────────────────────────────────────────────────────
# FLAGGED CLAIMS
# ─────────────────────────────────────────────────────────────────────────────


class FlaggedClaim(Base):
    __tablename__ = "reclaimrx_flagged_claims"
    __table_args__ = (
        Index("idx_fc_tenant_status", "tenant_id", "investigation_status"),
        Index("idx_fc_pharmacy", "tenant_id", "pharmacy_npi"),
        Index("idx_fc_prescriber", "tenant_id", "prescriber_npi"),
        Index("idx_fc_member", "tenant_id", "member_id"),
        Index("idx_fc_rule", "tenant_id", "rule_code"),
        Index("idx_fc_severity", "tenant_id", "severity"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    claim_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    auth_number: Mapped[str] = mapped_column(String(50), nullable=False)
    date_of_service: Mapped[date] = mapped_column(Date, nullable=False)

    pharmacy_npi: Mapped[str] = mapped_column(String(10), nullable=False)
    pharmacy_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prescriber_npi: Mapped[str | None] = mapped_column(String(10), nullable=True)
    member_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ndc: Mapped[str | None] = mapped_column(String(11), nullable=True)
    drug_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity: Mapped[object | None] = mapped_column(Numeric(10, 3), nullable=True)
    days_supply: Mapped[int | None] = mapped_column(Integer, nullable=True)

    billed_amount: Mapped[object | None] = mapped_column(Numeric(12, 2), nullable=True)
    paid_amount: Mapped[object | None] = mapped_column(Numeric(12, 2), nullable=True)
    expected_amount: Mapped[object | None] = mapped_column(Numeric(12, 2), nullable=True)
    variance_amount: Mapped[object | None] = mapped_column(Numeric(12, 2), nullable=True)

    detection_rule_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("reclaimrx_detection_rules.id"), nullable=True)
    rule_code: Mapped[str] = mapped_column(String(50), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    detection_mode: Mapped[str] = mapped_column(String(50), nullable=False)

    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)

    evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    comparison_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    action_taken: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    investigation_status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(36), nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)

    recovery_estimate_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    investigation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("reclaimrx_investigations.id"), nullable=True)

    client_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    program_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    program_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


# ─────────────────────────────────────────────────────────────────────────────
# ENTITY PROFILES
# ─────────────────────────────────────────────────────────────────────────────


class PharmacyProfile(Base):
    __tablename__ = "reclaimrx_pharmacy_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", "pharmacy_npi"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    pharmacy_npi: Mapped[str] = mapped_column(String(10), nullable=False)
    pharmacy_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    avg_daily_claims: Mapped[object | None] = mapped_column(Numeric(10, 2), nullable=True)
    avg_weekly_claims: Mapped[object | None] = mapped_column(Numeric(10, 2), nullable=True)
    avg_monthly_claims: Mapped[object | None] = mapped_column(Numeric(10, 2), nullable=True)
    total_claims_lifetime: Mapped[int | None] = mapped_column(Integer, nullable=True)

    avg_claim_amount: Mapped[object | None] = mapped_column(Numeric(12, 2), nullable=True)
    avg_ingredient_cost: Mapped[object | None] = mapped_column(Numeric(12, 2), nullable=True)
    avg_dispensing_fee: Mapped[object | None] = mapped_column(Numeric(12, 2), nullable=True)
    avg_nq_to_wac_ratio: Mapped[object | None] = mapped_column(Numeric(8, 4), nullable=True)
    avg_contracted_rate: Mapped[object | None] = mapped_column(Numeric(8, 4), nullable=True)

    reversal_rate: Mapped[object | None] = mapped_column(Numeric(8, 4), nullable=True)
    rejection_rate: Mapped[object | None] = mapped_column(Numeric(8, 4), nullable=True)
    weekend_holiday_rate: Mapped[object | None] = mapped_column(Numeric(8, 4), nullable=True)
    new_patient_rate: Mapped[object | None] = mapped_column(Numeric(8, 4), nullable=True)
    controlled_substance_rate: Mapped[object | None] = mapped_column(Numeric(8, 4), nullable=True)

    top_ndcs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ndc_diversity_score: Mapped[object | None] = mapped_column(Numeric(8, 4), nullable=True)

    network_peer_group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    percentile_rank_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    percentile_rank_claim_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    percentile_rank_reversal_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)

    composite_risk_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    risk_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)

    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    flag_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confirmed_fraud_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    last_calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class PrescriberProfile(Base):
    __tablename__ = "reclaimrx_prescriber_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", "prescriber_npi"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    prescriber_npi: Mapped[str] = mapped_column(String(10), nullable=False)
    prescriber_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    avg_daily_scripts: Mapped[object | None] = mapped_column(Numeric(10, 2), nullable=True)
    avg_quantity: Mapped[object | None] = mapped_column(Numeric(10, 2), nullable=True)
    avg_days_supply: Mapped[object | None] = mapped_column(Numeric(10, 2), nullable=True)

    top_therapeutic_classes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    controlled_substance_rate: Mapped[object | None] = mapped_column(Numeric(8, 4), nullable=True)
    schedule_ii_rate: Mapped[object | None] = mapped_column(Numeric(8, 4), nullable=True)
    brand_vs_generic_rate: Mapped[object | None] = mapped_column(Numeric(8, 4), nullable=True)

    unique_patient_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_scripts_per_patient: Mapped[object | None] = mapped_column(Numeric(8, 2), nullable=True)
    patient_geographic_spread: Mapped[object | None] = mapped_column(Numeric(8, 4), nullable=True)

    composite_risk_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    risk_trend: Mapped[str | None] = mapped_column(String(20), nullable=True)

    last_calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class MemberProfile(Base):
    __tablename__ = "reclaimrx_member_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", "member_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    member_id: Mapped[str] = mapped_column(String(100), nullable=False)

    fill_frequency_days: Mapped[object | None] = mapped_column(Numeric(8, 2), nullable=True)
    pharmacy_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prescriber_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_days_supply: Mapped[int | None] = mapped_column(Integer, nullable=True)

    controlled_substance_fills: Mapped[int | None] = mapped_column(Integer, nullable=True)
    early_refill_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pharmacy_shopping_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_accumulator_plan: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    accumulator_plan_detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accumulator_impact_amount: Mapped[object | None] = mapped_column(Numeric(12, 2), nullable=True)

    composite_risk_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    last_calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class ProfileSnapshot(Base):
    __tablename__ = "reclaimrx_profile_snapshots"
    __table_args__ = (UniqueConstraint("tenant_id", "entity_type", "entity_id", "snapshot_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)


# ─────────────────────────────────────────────────────────────────────────────
# ML MODEL MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────


class MlModel(Base):
    __tablename__ = "reclaimrx_ml_models"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_type: Mapped[str] = mapped_column(String(100), nullable=False)
    purpose: Mapped[str] = mapped_column(String(100), nullable=False)

    training_data_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    training_data_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    training_sample_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feature_set: Mapped[dict] = mapped_column(JSON, nullable=False)
    hyperparameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    accuracy: Mapped[object | None] = mapped_column(Numeric(8, 4), nullable=True)
    precision_score: Mapped[object | None] = mapped_column(Numeric(8, 4), nullable=True)
    recall: Mapped[object | None] = mapped_column(Numeric(8, 4), nullable=True)
    f1_score: Mapped[object | None] = mapped_column(Numeric(8, 4), nullable=True)
    auc_roc: Mapped[object | None] = mapped_column(Numeric(8, 4), nullable=True)
    confusion_matrix: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    status: Mapped[str] = mapped_column(String(50), default="training", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    model_artifact_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    predictions: Mapped[list[MlPrediction]] = relationship(back_populates="model", cascade="all, delete-orphan")


class MlPrediction(Base):
    __tablename__ = "reclaimrx_ml_predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    model_id: Mapped[str] = mapped_column(String(36), ForeignKey("reclaimrx_ml_models.id"), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    claim_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    feature_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    feature_importance: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    actual_outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)
    outcome_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    model: Mapped[MlModel] = relationship(back_populates="predictions")


# ─────────────────────────────────────────────────────────────────────────────
# INVESTIGATIONS & RECOVERY
# ─────────────────────────────────────────────────────────────────────────────


class Investigation(Base):
    __tablename__ = "reclaimrx_investigations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    investigation_number: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)

    subject_type: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    investigation_type: Mapped[str] = mapped_column(String(100), nullable=False)

    date_range_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_range_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    flagged_claim_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    total_flagged_amount: Mapped[object] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    recovery_estimate_conservative: Mapped[object] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    recovery_estimate_mid: Mapped[object] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    recovery_estimate_aggressive: Mapped[object] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    actual_recovered: Mapped[object] = mapped_column(Numeric(15, 2), default=0, nullable=False)

    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)

    assigned_to: Mapped[str | None] = mapped_column(String(36), nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    first_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    resolution_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    documents: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    client_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    program_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    litigation_hold: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    litigation_hold_placed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    litigation_hold_placed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    litigation_hold_released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    activities: Mapped[list[InvestigationActivity]] = relationship(back_populates="investigation", cascade="all, delete-orphan")
    recoveries: Mapped[list[Recovery]] = relationship(back_populates="investigation", cascade="all, delete-orphan")


class InvestigationActivity(Base):
    __tablename__ = "reclaimrx_investigation_activities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("reclaimrx_investigations.id"), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    activity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    performed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    file_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    investigation: Mapped[Investigation] = relationship(back_populates="activities")


class Recovery(Base):
    __tablename__ = "reclaimrx_recoveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("reclaimrx_investigations.id"), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    recovery_method: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[object] = mapped_column(Numeric(15, 2), nullable=False)
    confidence_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    methodology_tag: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[str] = mapped_column(String(50), default="estimated", nullable=False)

    demand_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    demand_letter_file_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    response_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    collection_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    investigation: Mapped[Investigation] = relationship(back_populates="recoveries")


class LetterTemplate(Base):
    __tablename__ = "reclaimrx_letter_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    letter_type: Mapped[str] = mapped_column(String(100), nullable=False)
    template_content: Mapped[str] = mapped_column(Text, nullable=False)
    merge_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    regulatory_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


# ─────────────────────────────────────────────────────────────────────────────
# ACCUMULATOR / MAXIMIZER
# ─────────────────────────────────────────────────────────────────────────────


class AccumulatorDetection(Base):
    __tablename__ = "reclaimrx_accumulator_detections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    member_id: Mapped[str] = mapped_column(String(100), nullable=False)
    plan_bin: Mapped[str | None] = mapped_column(String(10), nullable=True)
    plan_pcn: Mapped[str | None] = mapped_column(String(10), nullable=True)
    plan_group: Mapped[str | None] = mapped_column(String(15), nullable=True)

    detection_method: Mapped[str] = mapped_column(String(100), nullable=False)
    detection_fill_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detection_confidence: Mapped[object | None] = mapped_column(Numeric(8, 4), nullable=True)

    program_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    copay_assistance_amount: Mapped[object | None] = mapped_column(Numeric(12, 2), nullable=True)
    amount_applied_to_deductible: Mapped[object | None] = mapped_column(Numeric(12, 2), nullable=True)
    amount_not_applied: Mapped[object | None] = mapped_column(Numeric(12, 2), nullable=True)
    projected_annual_impact: Mapped[object | None] = mapped_column(Numeric(12, 2), nullable=True)

    recommended_action: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action_taken: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


# ─────────────────────────────────────────────────────────────────────────────
# EXTERNAL VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────


class VerificationConfig(Base):
    __tablename__ = "reclaimrx_verification_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    vendor_type: Mapped[str] = mapped_column(String(100), nullable=False)
    vendor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    api_endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_credentials_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)

    cost_per_inquiry: Mapped[object | None] = mapped_column(Numeric(8, 2), nullable=True)
    monthly_inquiry_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inquiries_used_this_month: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class VerificationResult(Base):
    __tablename__ = "reclaimrx_verification_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    verification_config_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("reclaimrx_verification_configs.id"), nullable=True)

    claim_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    member_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ndc: Mapped[str | None] = mapped_column(String(11), nullable=True)

    request_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    result_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cost: Mapped[object | None] = mapped_column(Numeric(8, 2), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


# ─────────────────────────────────────────────────────────────────────────────
# REPORTING
# ─────────────────────────────────────────────────────────────────────────────


class ReportConfig(Base):
    __tablename__ = "reclaimrx_report_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    schedule: Mapped[str | None] = mapped_column(String(50), nullable=True)
    delivery_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    delivery_recipients: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    filters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


# ─────────────────────────────────────────────────────────────────────────────
# PAYMENT HOLDS
# ─────────────────────────────────────────────────────────────────────────────


class PaymentHold(Base):
    __tablename__ = "reclaimrx_payment_holds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    investigation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("reclaimrx_investigations.id"), nullable=True)

    hold_scope: Mapped[str] = mapped_column(String(50), default="all", nullable=False)
    rule_filter: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    amount_threshold: Mapped[object | None] = mapped_column(Numeric(12, 2), nullable=True)

    placed_by: Mapped[str] = mapped_column(String(36), nullable=False)
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    released_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    release_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


# ─────────────────────────────────────────────────────────────────────────────
# TIP RECORDS
# ─────────────────────────────────────────────────────────────────────────────


class TipRecord(Base):
    __tablename__ = "reclaimrx_tip_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    tip_type: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_description: Mapped[str] = mapped_column(Text, nullable=False)
    detail_text: Mapped[str] = mapped_column(Text, nullable=False)

    reporter_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reporter_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    status: Mapped[str] = mapped_column(String(50), default="new", nullable=False)
    investigation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("reclaimrx_investigations.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


# ─────────────────────────────────────────────────────────────────────────────
# REGULATORY REPORTS
# ─────────────────────────────────────────────────────────────────────────────


class RegulatoryReport(Base):
    __tablename__ = "reclaimrx_regulatory_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("reclaimrx_investigations.id"), nullable=False, index=True)

    destination_type: Mapped[str] = mapped_column(String(100), nullable=False)
    destination_name: Mapped[str] = mapped_column(String(255), nullable=False)
    report_content: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    deadline_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


# ─────────────────────────────────────────────────────────────────────────────
# STATE AUDIT LAW COMPLIANCE
# ─────────────────────────────────────────────────────────────────────────────


class StateAuditRule(Base):
    __tablename__ = "reclaimrx_state_audit_rules"
    __table_args__ = (UniqueConstraint("state_code", "rule_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # advance_notice_days, lookback_period_months, audit_frequency_months,
    # appeal_deadline_days, extrapolation_allowed, on_site_notice_required

    int_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bool_value: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    text_value: Mapped[str | None] = mapped_column(String(500), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)


class StatuteOfLimitations(Base):
    __tablename__ = "reclaimrx_statute_of_limitations"
    __table_args__ = (UniqueConstraint("state_code", "claim_type", "violation_type", "program_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    claim_type: Mapped[str] = mapped_column(String(50), nullable=False)
    violation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    program_type: Mapped[str] = mapped_column(String(50), nullable=False)
    years: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


# ─────────────────────────────────────────────────────────────────────────────
# NETWORK RISK REGISTRY
# ─────────────────────────────────────────────────────────────────────────────


class NetworkRiskRegistry(Base):
    __tablename__ = "reclaimrx_network_risk_registry"
    __table_args__ = (UniqueConstraint("entity_type", "entity_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)

    network_risk_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    contributing_tenant_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_flag_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


# ─────────────────────────────────────────────────────────────────────────────
# WATCHLIST
# ─────────────────────────────────────────────────────────────────────────────


class WatchlistEntry(Base):
    __tablename__ = "reclaimrx_watchlist"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    fraud_probability_30d: Mapped[object | None] = mapped_column(Numeric(8, 4), nullable=True)
    fraud_probability_60d: Mapped[object | None] = mapped_column(Numeric(8, 4), nullable=True)
    fraud_probability_90d: Mapped[object | None] = mapped_column(Numeric(8, 4), nullable=True)

    added_by_rule: Mapped[str | None] = mapped_column(String(50), nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


# ─────────────────────────────────────────────────────────────────────────────
# CORRECTIVE ACTION PLANS
# ─────────────────────────────────────────────────────────────────────────────


class CorrectiveActionPlan(Base):
    __tablename__ = "reclaimrx_corrective_action_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("reclaimrx_investigations.id"), nullable=False, index=True)

    subject_type: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    issue_description: Mapped[str] = mapped_column(Text, nullable=False)
    compliance_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)

    status: Mapped[str] = mapped_column(String(50), default="issued", nullable=False)
    remonitoring_period_months: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    remonitoring_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    action_items: Mapped[list[CorrectiveActionItem]] = relationship(back_populates="plan", cascade="all, delete-orphan")


class CorrectiveActionItem(Base):
    __tablename__ = "reclaimrx_corrective_action_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("reclaimrx_corrective_action_plans.id"), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completion_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    plan: Mapped[CorrectiveActionPlan] = relationship(back_populates="action_items")
