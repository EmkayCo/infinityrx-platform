"""SQLAlchemy ORM models for the ebv_ebi schema.

All money columns: Numeric(14, 2) -- never Float.
Every table: TenantScopedMixin.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from shared.db.tenant_context import TenantScopedMixin

SCHEMA = "ebv_ebi"


class EbvEbiBase(DeclarativeBase):
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
# EBV Transaction (Eligibility & Benefit Verification)
# ---------------------------------------------------------------------------


class EBVTransaction(EbvEbiBase, TenantScopedMixin):
    """Records each eligibility verification request/response cycle.

    Supports NCPDP E1, X12 270/271, real-time API, and batch channels.
    """

    __tablename__ = "ebv_transactions"
    __table_args__ = (
        Index("idx_ebv_txn_tenant_member", "tenant_id", "member_id"),
        Index("idx_ebv_txn_tenant_created", "tenant_id", "created_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    member_id: Mapped[str] = mapped_column(String(100), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    request_data: Mapped[dict | None] = mapped_column(JSONB)
    response_data: Mapped[dict | None] = mapped_column(JSONB)
    member_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    group_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    coverage_start: Mapped[date | None] = mapped_column(Date)
    coverage_end: Mapped[date | None] = mapped_column(Date)
    copay_summary: Mapped[dict | None] = mapped_column(JSONB)
    benefit_phase: Mapped[str | None] = mapped_column(String(50))
    deductible_met: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    deductible_remaining: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    oop_met: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    oop_remaining: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# EBI Request (Electronic Benefit Investigation)
# ---------------------------------------------------------------------------


class EBIRequest(EbvEbiBase, TenantScopedMixin):
    """Deep benefit investigation for a specific drug/member combination.

    Captures formulary status, PA/ST/QL requirements, cost estimates,
    therapeutic alternatives, and accumulator program detection.
    """

    __tablename__ = "ebi_requests"
    __table_args__ = (
        Index("idx_ebi_req_tenant_member", "tenant_id", "member_id"),
        Index("idx_ebi_req_tenant_ndc", "tenant_id", "drug_ndc"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    member_id: Mapped[str] = mapped_column(String(100), nullable=False)
    drug_ndc: Mapped[str] = mapped_column(String(11), nullable=False)
    coverage_result: Mapped[dict | None] = mapped_column(JSONB)
    alternatives: Mapped[dict | None] = mapped_column(JSONB)
    accumulator_status: Mapped[str | None] = mapped_column(String(30))
    specialty_pharmacy_required: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False
    )
    site_of_care: Mapped[str | None] = mapped_column(String(100))
    member_cost_estimate: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# RTPB Transaction (Real-Time Prescription Benefit)
# ---------------------------------------------------------------------------


class RTPBTransaction(EbvEbiBase, TenantScopedMixin):
    """NCPDP RTPB (v13) transaction for real-time cost/formulary at prescribing.

    Captures patient cost, formulary status, tier, restrictions,
    alternatives, and pharmacy options per Surescripts spec.
    """

    __tablename__ = "rtpb_transactions"
    __table_args__ = (
        Index("idx_rtpb_txn_tenant_member", "tenant_id", "member_id"),
        Index("idx_rtpb_txn_tenant_ndc", "tenant_id", "drug_ndc"),
        Index("idx_rtpb_txn_tenant_created", "tenant_id", "created_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    member_id: Mapped[str] = mapped_column(String(100), nullable=False)
    drug_ndc: Mapped[str] = mapped_column(String(11), nullable=False)
    prescriber_npi: Mapped[str | None] = mapped_column(String(10))
    patient_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    formulary_status: Mapped[str | None] = mapped_column(String(30))
    tier: Mapped[str | None] = mapped_column(String(10))
    restrictions: Mapped[dict | None] = mapped_column(JSONB)
    alternatives: Mapped[dict | None] = mapped_column(JSONB)
    pharmacy_options: Mapped[dict | None] = mapped_column(JSONB)
    v13_compliant: Mapped[bool] = mapped_column(
        Boolean, server_default="true", default=True
    )
    surescripts_transaction_id: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Member Cost Lookup (cached cost estimates)
# ---------------------------------------------------------------------------


class MemberCostLookup(EbvEbiBase, TenantScopedMixin):
    """Cached per-member drug cost estimate at a specific pharmacy."""

    __tablename__ = "member_cost_lookups"
    __table_args__ = (
        Index("idx_cost_lookup_member_ndc", "tenant_id", "member_id", "drug_ndc"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    member_id: Mapped[str] = mapped_column(String(100), nullable=False)
    drug_ndc: Mapped[str] = mapped_column(String(11), nullable=False)
    pharmacy_npi: Mapped[str | None] = mapped_column(String(10))
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    alternative_savings: Mapped[dict | None] = mapped_column(JSONB)
    looked_up_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Pharmacy Cost Comparison
# ---------------------------------------------------------------------------


class PharmacyCostComparison(EbvEbiBase, TenantScopedMixin):
    """Comparison of drug cost across pharmacies for a member."""

    __tablename__ = "pharmacy_cost_comparisons"
    __table_args__ = (
        Index("idx_pharm_cost_member_ndc", "tenant_id", "member_id", "drug_ndc"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    member_id: Mapped[str] = mapped_column(String(100), nullable=False)
    drug_ndc: Mapped[str] = mapped_column(String(11), nullable=False)
    pharmacy_results: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Digital ID Card
# ---------------------------------------------------------------------------


class DigitalIDCard(EbvEbiBase, TenantScopedMixin):
    """Virtual ID card data for member self-service and pharmacy use."""

    __tablename__ = "digital_id_cards"
    __table_args__ = (
        Index("idx_digital_card_member", "tenant_id", "member_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    member_id: Mapped[str] = mapped_column(String(100), nullable=False)
    card_data: Mapped[dict | None] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer, server_default="1", default=1)
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Member Notification
# ---------------------------------------------------------------------------


class MemberNotification(EbvEbiBase, TenantScopedMixin):
    """Outbound notification to a member (alternative found, refill due, etc.)."""

    __tablename__ = "member_notifications"
    __table_args__ = (
        Index("idx_notif_tenant_member", "tenant_id", "member_id"),
        Index("idx_notif_tenant_status", "tenant_id", "delivery_status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    member_id: Mapped[str] = mapped_column(String(100), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(30), nullable=False)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    template_data: Mapped[dict | None] = mapped_column(JSONB)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_status: Mapped[str] = mapped_column(
        String(30), server_default="pending", default="pending"
    )
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Hub Integration Log
# ---------------------------------------------------------------------------


class HubIntegrationLog(EbvEbiBase, TenantScopedMixin):
    """Audit log for hub-partner BV/BI/status-update integrations."""

    __tablename__ = "hub_integration_logs"
    __table_args__ = (
        Index("idx_hub_log_tenant_partner", "tenant_id", "hub_partner_id"),
        Index("idx_hub_log_tenant_created", "tenant_id", "created_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    hub_partner_id: Mapped[str] = mapped_column(String(100), nullable=False)
    request_type: Mapped[str] = mapped_column(String(30), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    request_data: Mapped[dict | None] = mapped_column(JSONB)
    response_data: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = _ts_now()
