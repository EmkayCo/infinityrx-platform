"""SQLAlchemy ORM models for the rebate-management module.

All money columns are sa.Numeric(x,2) or sa.Numeric(x,4) — never Float.
Every tenant-owned table inherits TenantScopedMixin.
Hash chain columns (entry_hash, prev_hash) are used on immutable ledger entries.

Tables
------
rebate_contracts           — Contract master with lifecycle
rebate_contract_ndcs       — Per-NDC-11 rebate terms
rebate_tiers               — Volume / market-share tier definitions
rebate_transactions        — Immutable, hash-chained rebate transaction log
rebate_accruals            — Monthly accrual entries per NDC per contract
pass_through_entries       — Immutable, hash-chained manufacturer→sponsor ledger
pass_through_reconciliations — Monthly reconciliation summaries
bfsf_documents             — BFSF fee-only documentation
bfsf_service_catalog       — Catalog of services eligible for BFSF
transparency_reports       — Semiannual / quarterly CAA 2026 reports
audit_exports              — Audit export requests + signed zip metadata
industry_benchmarks        — Seeded benchmark values (configurable)
gtn_waterfall_snapshots    — Daily GTN waterfall snapshots per drug
copay_optimization_scenarios — What-if scenario records
spend_cap_guarantees       — Contract-level spend cap configuration
spend_cap_actuals          — Actual spend tracking vs cap
compliance_dashboard_snapshots — Fiduciary compliance snapshots
program_performance_metrics — Per-program, per-period benchmark metrics
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
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
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from shared.db.tenant_context import TenantScopedMixin

SCHEMA = "rebate_management"


class RebateBase(DeclarativeBase):
    """Declarative base for rebate-management module."""


# ---------------------------------------------------------------------------
# REBATE CONTRACT MANAGEMENT
# ---------------------------------------------------------------------------


class RebateContract(RebateBase, TenantScopedMixin):
    """Master rebate contract with manufacturer."""

    __tablename__ = "rebate_contracts"
    __table_args__ = (
        Index("idx_rebate_contracts_tenant_status", "tenant_id", "status"),
        Index("idx_rebate_contracts_tenant_mfr", "tenant_id", "manufacturer_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    manufacturer_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    manufacturer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contract_number: Mapped[str] = mapped_column(String(100), nullable=False)
    contract_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # formulary_access, market_share, volume, admin_fee, price_protection, combination
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="draft"
    )  # draft, negotiated, executed, active, amended, terminated
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_frequency: Mapped[str] = mapped_column(
        String(20), nullable=False, default="quarterly"
    )  # monthly, quarterly
    minimum_volume_threshold: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    bfsf_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_contract_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )  # tracks amendments
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    ndcs: Mapped[list[RebateContractNDC]] = relationship(
        "RebateContractNDC", back_populates="contract", cascade="all, delete-orphan"
    )
    tiers: Mapped[list[RebateTier]] = relationship(
        "RebateTier", back_populates="contract", cascade="all, delete-orphan"
    )
    transactions: Mapped[list[RebateTransaction]] = relationship(
        "RebateTransaction", back_populates="contract"
    )
    accruals: Mapped[list[RebateAccrual]] = relationship(
        "RebateAccrual", back_populates="contract"
    )
    spend_cap_guarantees: Mapped[list[SpendCapGuarantee]] = relationship(
        "SpendCapGuarantee", back_populates="contract"
    )


class RebateContractNDC(RebateBase, TenantScopedMixin):
    """Per-NDC-11 rebate terms within a contract."""

    __tablename__ = "rebate_contract_ndcs"
    __table_args__ = (
        Index("idx_contract_ndcs_tenant_ndc", "tenant_id", "ndc11"),
        Index("idx_contract_ndcs_contract", "tenant_id", "contract_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.rebate_contracts.id"),
        nullable=False,
    )
    ndc11: Mapped[str] = mapped_column(String(11), nullable=False)
    drug_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rebate_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # percent_wac, flat_per_unit
    rebate_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )  # e.g. 12.5000 = 12.5%
    rebate_per_unit: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4), nullable=True
    )  # flat $ per dispensed unit
    formulary_position: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # preferred, non_preferred, exclusive
    formulary_position_bonus_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    growth_bonus_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    contract: Mapped[RebateContract] = relationship(
        "RebateContract", back_populates="ndcs"
    )


class RebateTier(RebateBase, TenantScopedMixin):
    """Volume / market-share tier definitions for tiered rebate contracts."""

    __tablename__ = "rebate_tiers"
    __table_args__ = (
        Index("idx_rebate_tiers_contract", "tenant_id", "contract_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.rebate_contracts.id"),
        nullable=False,
    )
    tier_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tier_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # volume, market_share
    threshold_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False
    )  # units or % depending on tier_type
    rebate_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    contract: Mapped[RebateContract] = relationship(
        "RebateContract", back_populates="tiers"
    )


# ---------------------------------------------------------------------------
# REBATE TRANSACTIONS (IMMUTABLE HASH CHAIN)
# ---------------------------------------------------------------------------


class RebateTransaction(RebateBase, TenantScopedMixin):
    """Immutable rebate transaction record with sha256 hash chain.

    entry_hash = sha256(prev_hash || canonical_json(entry_fields))
    Append-only: no UPDATE or DELETE ever.
    """

    __tablename__ = "rebate_transactions"
    __table_args__ = (
        Index("idx_rebate_tx_tenant_contract", "tenant_id", "contract_id"),
        Index("idx_rebate_tx_tenant_period", "tenant_id", "period_start"),
        Index("idx_rebate_tx_tenant_ndc", "tenant_id", "ndc11"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.rebate_contracts.id"),
        nullable=False,
    )
    ndc11: Mapped[str] = mapped_column(String(11), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    transaction_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # calculated, invoice_generated, payment_received, adjustment
    rebate_category: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # commercial, market_share, formulary_access, admin_fee, price_protection, alternative_discount
    units_dispensed: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    wac_per_unit: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    gross_wac: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    rebate_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    sponsor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    manufacturer_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    # Hash chain fields — immutable audit integrity
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    contract: Mapped[RebateContract] = relationship(
        "RebateContract", back_populates="transactions"
    )


# ---------------------------------------------------------------------------
# ACCRUALS
# ---------------------------------------------------------------------------


class RebateAccrual(RebateBase, TenantScopedMixin):
    """Monthly earned-but-not-yet-received rebate accrual."""

    __tablename__ = "rebate_accruals"
    __table_args__ = (
        Index("idx_rebate_accruals_tenant_contract", "tenant_id", "contract_id"),
        Index("idx_rebate_accruals_tenant_period", "tenant_id", "accrual_month"),
        UniqueConstraint(
            "tenant_id",
            "contract_id",
            "ndc11",
            "accrual_month",
            name="uq_accrual_contract_ndc_month",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.rebate_contracts.id"),
        nullable=False,
    )
    ndc11: Mapped[str] = mapped_column(String(11), nullable=False)
    accrual_month: Mapped[date] = mapped_column(
        Date, nullable=False
    )  # first day of month
    accrued_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    recognized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recognized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    contract: Mapped[RebateContract] = relationship(
        "RebateContract", back_populates="accruals"
    )


# ---------------------------------------------------------------------------
# PASS-THROUGH LEDGER (IMMUTABLE HASH CHAIN)
# ---------------------------------------------------------------------------


class PassThroughEntry(RebateBase, TenantScopedMixin):
    """Dollar-for-dollar pass-through ledger entry.

    manufacturer → InfinityRx → plan sponsor, tracked at NDC-11 level.
    Immutable. Hash chained. Every rebate dollar must appear here.
    """

    __tablename__ = "pass_through_entries"
    __table_args__ = (
        Index("idx_pt_entries_tenant_sponsor", "tenant_id", "sponsor_id"),
        Index("idx_pt_entries_tenant_period", "tenant_id", "period_month"),
        Index("idx_pt_entries_tenant_ndc", "tenant_id", "ndc11"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.rebate_transactions.id"),
        nullable=False,
    )
    ndc11: Mapped[str] = mapped_column(String(11), nullable=False)
    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    sponsor_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    manufacturer_received: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )  # received from manufacturer
    sponsor_passed: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )  # passed to sponsor (must equal received)
    rebate_category: Mapped[str] = mapped_column(String(50), nullable=False)
    remittance_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Hash chain
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class PassThroughReconciliation(RebateBase, TenantScopedMixin):
    """Monthly reconciliation: total received == total passed through."""

    __tablename__ = "pass_through_reconciliations"
    __table_args__ = (
        Index("idx_pt_recon_tenant_period", "tenant_id", "period_month"),
        UniqueConstraint(
            "tenant_id",
            "sponsor_id",
            "period_month",
            name="uq_pt_recon_sponsor_month",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sponsor_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    total_received: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_passed: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    difference: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )  # must be zero for compliant pass-through
    is_balanced: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reconciled_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    reconciled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


# ---------------------------------------------------------------------------
# BFSF DOCUMENTATION
# ---------------------------------------------------------------------------


class BFSFServiceCatalog(RebateBase, TenantScopedMixin):
    """Catalog of services eligible for bona fide service fee compensation."""

    __tablename__ = "bfsf_service_catalog"
    __table_args__ = (
        Index("idx_bfsf_catalog_tenant", "tenant_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    market_rate_per_hour: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    market_comparables: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )  # JSON of comparable market rates
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class BFSFDocument(RebateBase, TenantScopedMixin):
    """BFSF fee-only documentation with approval workflow."""

    __tablename__ = "bfsf_documents"
    __table_args__ = (
        Index("idx_bfsf_docs_tenant_status", "tenant_id", "status"),
        Index("idx_bfsf_docs_tenant_contract", "tenant_id", "contract_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contract_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    sponsor_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    document_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # fair_market_value_assessment, fee_schedule, annual_attestation
    assessment_year: Mapped[int] = mapped_column(Integer, nullable=False)
    # Services breakdown: list of {service_id, service_name, hours, rate, total}
    services_detail: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False
    )
    total_fee: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    fair_market_value_justified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft"
    )  # draft, pending_approval, approved, rejected
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


# ---------------------------------------------------------------------------
# TRANSPARENCY REPORTS
# ---------------------------------------------------------------------------


class TransparencyReport(RebateBase, TenantScopedMixin):
    """Semiannual / quarterly CAA 2026 transparency report."""

    __tablename__ = "transparency_reports"
    __table_args__ = (
        Index("idx_transparency_tenant_status", "tenant_id", "status"),
        Index("idx_transparency_tenant_sponsor", "tenant_id", "sponsor_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sponsor_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    report_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # semiannual, quarterly
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, generating, ready, filed
    # Report data — structured summary
    net_drug_spending: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    gross_drug_costs: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    total_rebates_received: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    total_rebates_passed: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    spread_pricing_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )  # should be zero in pass-through model
    affiliated_pharmacy_utilization_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    report_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )  # full report JSON
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    filed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


# ---------------------------------------------------------------------------
# AUDIT EXPORTS
# ---------------------------------------------------------------------------


class AuditExport(RebateBase, TenantScopedMixin):
    """Audit export request + signed zip metadata."""

    __tablename__ = "audit_exports"
    __table_args__ = (
        Index("idx_audit_exports_tenant_status", "tenant_id", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sponsor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    export_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="full"
    )  # full, contracts_only, payments_only
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, generating, ready, failed
    manifest: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    zip_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


# ---------------------------------------------------------------------------
# INDUSTRY BENCHMARKS
# ---------------------------------------------------------------------------


class IndustryBenchmark(RebateBase, TenantScopedMixin):
    """Industry benchmark values per metric — configurable, seeded with placeholders."""

    __tablename__ = "industry_benchmarks"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "metric_name",
            "drug_class",
            "benchmark_year",
            name="uq_benchmark_metric_class_year",
        ),
        Index("idx_benchmarks_tenant_metric", "tenant_id", "metric_name"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    metric_name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # enrollment_rate, first_fill_rate, pdc, abandonment_rate, avg_copay, gtn_ratio, misuse_rate
    drug_class: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # None = overall
    benchmark_year: Mapped[int] = mapped_column(Integer, nullable=False)
    p25_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False
    )  # 25th percentile
    p50_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False
    )  # median / industry avg
    p75_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False
    )  # 75th percentile
    source: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # "PLACEHOLDER — update with actual data"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


# ---------------------------------------------------------------------------
# GTN WATERFALL SNAPSHOTS
# ---------------------------------------------------------------------------


class GTNWaterfallSnapshot(RebateBase, TenantScopedMixin):
    """Daily GTN waterfall snapshot per drug per period."""

    __tablename__ = "gtn_waterfall_snapshots"
    __table_args__ = (
        Index("idx_gtn_tenant_ndc_period", "tenant_id", "ndc11", "snapshot_date"),
        UniqueConstraint(
            "tenant_id",
            "ndc11",
            "snapshot_date",
            "program_id",
            name="uq_gtn_ndc_date_program",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ndc11: Mapped[str] = mapped_column(String(11), nullable=False)
    drug_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    program_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    wac: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    wholesaler_discount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    prompt_pay_discount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    rebates: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    chargebacks: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    copay_assistance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    copay_misuse_leakage: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    admin_fees: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    net_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    gtn_ratio: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False
    )  # e.g. 0.6400 = 64%
    fwa_data_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


# ---------------------------------------------------------------------------
# COPAY OPTIMIZATION SCENARIOS
# ---------------------------------------------------------------------------


class CopayOptimizationScenario(RebateBase, TenantScopedMixin):
    """What-if copay optimization scenario with forecasted outcomes."""

    __tablename__ = "copay_optimization_scenarios"
    __table_args__ = (
        Index(
            "idx_copay_scenarios_tenant_program", "tenant_id", "program_id"
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    scenario_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Copay parameters under evaluation
    proposed_annual_max: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    proposed_copay_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    proposed_eligibility_rules: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    # Forecasted outcomes (Decimal stored as Numeric)
    forecasted_script_lift_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    forecasted_adherence_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    forecasted_net_spend: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    forecasted_roi: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4), nullable=True
    )
    # Accumulator / maximizer impact
    accumulator_savings: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    maximizer_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    pillar: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # design, fraud_control, accumulator_impact, executive_cadence
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


# ---------------------------------------------------------------------------
# SPEND CAP GUARANTEES
# ---------------------------------------------------------------------------


class SpendCapGuarantee(RebateBase, TenantScopedMixin):
    """Contract-level spend cap / performance guarantee configuration."""

    __tablename__ = "spend_cap_guarantees"
    __table_args__ = (
        Index("idx_spend_cap_tenant_contract", "tenant_id", "contract_id"),
        Index("idx_spend_cap_tenant_sponsor", "tenant_id", "sponsor_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.rebate_contracts.id"),
        nullable=False,
    )
    sponsor_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    program_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    cap_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # spend_ceiling, performance_guarantee
    guarantee_ceiling: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )  # projected total spend ceiling
    guarantee_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    guarantee_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    alert_threshold_pct_80: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    alert_threshold_pct_90: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    refund_terms: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )  # contract refund calc method
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    contract: Mapped[RebateContract] = relationship(
        "RebateContract", back_populates="spend_cap_guarantees"
    )
    actuals: Mapped[list[SpendCapActual]] = relationship(
        "SpendCapActual", back_populates="guarantee"
    )


class SpendCapActual(RebateBase, TenantScopedMixin):
    """Actual spend tracking vs guaranteed cap."""

    __tablename__ = "spend_cap_actuals"
    __table_args__ = (
        Index("idx_spend_actuals_tenant_guarantee", "tenant_id", "guarantee_id"),
        UniqueConstraint(
            "tenant_id",
            "guarantee_id",
            "tracking_month",
            name="uq_spend_actual_guarantee_month",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    guarantee_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.spend_cap_guarantees.id"),
        nullable=False,
    )
    tracking_month: Mapped[date] = mapped_column(Date, nullable=False)
    actual_spend: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    cumulative_spend: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    ceiling_at_time: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    utilization_pct: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False
    )  # cumulative / ceiling
    refund_owed: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    alert_80_fired: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    alert_90_fired: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    alert_100_fired: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    guarantee: Mapped[SpendCapGuarantee] = relationship(
        "SpendCapGuarantee", back_populates="actuals"
    )


# ---------------------------------------------------------------------------
# COMPLIANCE DASHBOARD SNAPSHOTS
# ---------------------------------------------------------------------------


class ComplianceDashboardSnapshot(RebateBase, TenantScopedMixin):
    """Fiduciary compliance dashboard snapshot."""

    __tablename__ = "compliance_dashboard_snapshots"
    __table_args__ = (
        Index("idx_compliance_tenant_sponsor", "tenant_id", "sponsor_id"),
        UniqueConstraint(
            "tenant_id",
            "sponsor_id",
            "snapshot_date",
            name="uq_compliance_sponsor_date",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sponsor_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    pass_through_pct: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False
    )  # should be 1.0000 (100%)
    spread_pricing_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )  # should be 0.00
    bfsf_docs_complete: Mapped[bool] = mapped_column(Boolean, nullable=False)
    transparency_report_status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # filed, pending, overdue
    audit_export_ready: Mapped[bool] = mapped_column(Boolean, nullable=False)
    spend_cap_compliant: Mapped[bool] = mapped_column(Boolean, nullable=False)
    overall_compliant: Mapped[bool] = mapped_column(Boolean, nullable=False)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


# ---------------------------------------------------------------------------
# PROGRAM PERFORMANCE METRICS
# ---------------------------------------------------------------------------


class ProgramPerformanceMetric(RebateBase, TenantScopedMixin):
    """Per-program, per-period benchmark metric records."""

    __tablename__ = "program_performance_metrics"
    __table_args__ = (
        Index("idx_perf_metrics_tenant_program", "tenant_id", "program_id"),
        Index("idx_perf_metrics_tenant_period", "tenant_id", "period_start"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    drug_class: Mapped[str | None] = mapped_column(String(100), nullable=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    enrollment_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    first_fill_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    pdc_6month: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )  # proportion of days covered
    abandonment_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    avg_copay: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )  # average copay per patient per year (Decimal)
    gtn_ratio: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    misuse_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    accumulator_patients_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    maximizer_patients_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
