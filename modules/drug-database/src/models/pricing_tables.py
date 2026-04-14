"""CMS NADAC and ASP pricing ORM models for the drug-database module.

Schema: ``drug_database`` (same schema as NDC tables, migration 0002_pricing).

Tables:
  drug_database.drug_nadac_pricing          — current NADAC price per NDC-11 (upsert)
  drug_database.drug_nadac_pricing_history  — append-only history of NADAC price changes
  drug_database.drug_asp_pricing            — current ASP + 6% per HCPCS code (upsert)
  drug_database.drug_asp_pricing_history    — append-only history of ASP price changes

Data rules (non-negotiable):
  - Every money/price column: sa.Numeric(18, 6) with Python Decimal + ROUND_HALF_UP.
  - No float, no int-cents, no sa.Float anywhere in this file.
  - Global reference data — no TenantScopedMixin (LESSON-011).

LESSON-004: All regex uses \\A...\\Z anchors (enforcement in service layer).
LESSON-005: All log extra keys prefixed with ingest_.

Alembic revision chain:
  0001_ndc    (T3) — drugs, packages, ingredients, pharm classes
  0002_pricing (this migration) — NADAC + ASP pricing tables
  0003        reserved for Orange Book therapeutic equivalence overlay (T5)
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEMA = "drug_database"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PricingBase(DeclarativeBase):
    """Declarative base for drug_database pricing tables."""


# ---------------------------------------------------------------------------
# NADAC tables
# ---------------------------------------------------------------------------


class DrugNADACPricing(PricingBase):
    """Current NADAC (National Average Drug Acquisition Cost) price per NDC-11.

    Upserted by ndc_11 — one row per NDC representing the most recent price.
    A history row is written to DrugNADACPricingHistory whenever the price
    or effective_date changes.

    All money columns: Numeric(18, 6), Python Decimal, ROUND_HALF_UP.
    No float, no sa.Float (financial-precision.md).
    Global reference data — no TenantScopedMixin (LESSON-011).
    """

    __tablename__ = "drug_nadac_pricing"
    __table_args__ = (
        Index("ix_nadac_pricing_ndc_11", "ndc_11"),
        Index("ix_nadac_pricing_effective_date", "effective_date"),
        Index("ix_nadac_pricing_as_of_date", "as_of_date"),
        {"schema": SCHEMA},
    )

    ndc_11: Mapped[str] = mapped_column(
        String(11), primary_key=True,
        comment="11-digit normalized NDC (5-4-2); upsert key",
    )
    ndc_description: Mapped[str | None] = mapped_column(
        Text, comment="NDC Description from CMS NADAC file",
    )
    nadac_per_unit: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False,
        comment="NADAC price per unit — Decimal(18,6) ROUND_HALF_UP; never float",
    )
    effective_date: Mapped[date] = mapped_column(
        Date, nullable=False,
        comment="Date the NADAC price became effective",
    )
    pricing_unit: Mapped[str | None] = mapped_column(
        String(10), comment="ML, GM, EA, etc.",
    )
    pharmacy_type_indicator: Mapped[str | None] = mapped_column(
        String(1), comment="C=Chain, I=Independent, blank=combined",
    )
    otc: Mapped[str | None] = mapped_column(
        String(1), comment="Y=OTC, N=Rx",
    )
    explanation_code: Mapped[str | None] = mapped_column(
        String(10), comment="Explanation code from CMS",
    )
    classification: Mapped[str | None] = mapped_column(
        String(10), comment="B, G, B-BIO, B-ANDA — classification for rate setting",
    )
    generic_nadac_per_unit: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6),
        comment="Corresponding generic drug NADAC per unit — nullable; Decimal(18,6)",
    )
    generic_effective_date: Mapped[date | None] = mapped_column(
        Date, comment="Corresponding generic drug effective date — nullable",
    )
    as_of_date: Mapped[date] = mapped_column(
        Date, nullable=False,
        comment="As of date for this NADAC snapshot",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )


class DrugNADACPricingHistory(PricingBase):
    """Append-only NADAC price change history.

    A new row is written every time ndc_11 price or effective_date changes.
    Unique on (ndc_11, effective_date, as_of_date) — prevents duplicate history rows
    when the same snapshot is re-ingested without actual changes.

    All money columns: Numeric(18, 6), Python Decimal, ROUND_HALF_UP.
    No float, no sa.Float.
    Global reference data — no TenantScopedMixin (LESSON-011).
    """

    __tablename__ = "drug_nadac_pricing_history"
    __table_args__ = (
        UniqueConstraint(
            "ndc_11", "effective_date", "as_of_date",
            name="uq_nadac_history_ndc_eff_asof",
        ),
        Index("ix_nadac_history_ndc_11", "ndc_11"),
        Index("ix_nadac_history_effective_date", "effective_date"),
        Index("ix_nadac_history_as_of_date", "as_of_date"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True,
    )
    ndc_11: Mapped[str] = mapped_column(
        String(11), nullable=False,
        comment="11-digit normalized NDC (5-4-2)",
    )
    ndc_description: Mapped[str | None] = mapped_column(Text)
    nadac_per_unit: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False,
        comment="NADAC price per unit — Decimal(18,6) ROUND_HALF_UP; never float",
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    pricing_unit: Mapped[str | None] = mapped_column(String(10))
    pharmacy_type_indicator: Mapped[str | None] = mapped_column(String(1))
    otc: Mapped[str | None] = mapped_column(String(1))
    explanation_code: Mapped[str | None] = mapped_column(String(10))
    classification: Mapped[str | None] = mapped_column(String(10))
    generic_nadac_per_unit: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6),
        comment="Corresponding generic drug NADAC per unit — nullable; Decimal(18,6)",
    )
    generic_effective_date: Mapped[date | None] = mapped_column(Date)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )


# ---------------------------------------------------------------------------
# ASP tables
# ---------------------------------------------------------------------------


class DrugASPPricing(PricingBase):
    """Current CMS ASP (Average Sales Price) + 6% payment limit per HCPCS code.

    Upserted by hcpcs_code — one row per code representing the most recent quarter.
    A history row is written to DrugASPPricingHistory when the quarter changes.

    All money columns: Numeric(18, 6), Python Decimal, ROUND_HALF_UP.
    No float, no sa.Float (financial-precision.md).
    Global reference data — no TenantScopedMixin (LESSON-011).
    """

    __tablename__ = "drug_asp_pricing"
    __table_args__ = (
        Index("ix_asp_pricing_hcpcs_code", "hcpcs_code"),
        Index("ix_asp_pricing_effective_quarter", "effective_quarter"),
        {"schema": SCHEMA},
    )

    hcpcs_code: Mapped[str] = mapped_column(
        String(10), primary_key=True,
        comment="HCPCS code; upsert key",
    )
    short_description: Mapped[str | None] = mapped_column(
        Text, comment="Short description from ASP pricing file",
    )
    dosage: Mapped[str | None] = mapped_column(
        String(100), comment="HCPCS Code Dosage, e.g. '10 mg'",
    )
    payment_limit: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False,
        comment="Payment limit (ASP + 6%) — Decimal(18,6) ROUND_HALF_UP; never float",
    )
    vaccine_awp: Mapped[str | None] = mapped_column(
        String(1), comment="Y/N — Vaccine AWP column; may be absent in some quarters",
    )
    effective_quarter: Mapped[str] = mapped_column(
        String(7), nullable=False,
        comment="YYYYQN format, e.g. '2026Q2'; inferred from filename if not in file",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )


class DrugASPPricingHistory(PricingBase):
    """Append-only ASP price change history.

    Unique on (hcpcs_code, effective_quarter) — re-running the same quarter
    does NOT create duplicate history rows.

    All money columns: Numeric(18, 6), Python Decimal, ROUND_HALF_UP.
    No float, no sa.Float.
    Global reference data — no TenantScopedMixin (LESSON-011).
    """

    __tablename__ = "drug_asp_pricing_history"
    __table_args__ = (
        UniqueConstraint(
            "hcpcs_code", "effective_quarter",
            name="uq_asp_history_hcpcs_quarter",
        ),
        Index("ix_asp_history_hcpcs_code", "hcpcs_code"),
        Index("ix_asp_history_effective_quarter", "effective_quarter"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True,
    )
    hcpcs_code: Mapped[str] = mapped_column(String(10), nullable=False)
    short_description: Mapped[str | None] = mapped_column(Text)
    dosage: Mapped[str | None] = mapped_column(String(100))
    payment_limit: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False,
        comment="Payment limit (ASP + 6%) — Decimal(18,6) ROUND_HALF_UP; never float",
    )
    vaccine_awp: Mapped[str | None] = mapped_column(String(1))
    effective_quarter: Mapped[str] = mapped_column(String(7), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )


__all__ = [
    "DrugNADACPricing",
    "DrugNADACPricingHistory",
    "DrugASPPricing",
    "DrugASPPricingHistory",
    "PricingBase",
    "SCHEMA",
]
