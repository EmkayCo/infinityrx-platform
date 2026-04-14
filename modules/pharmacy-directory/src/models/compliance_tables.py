"""Pharmacy compliance cross-reference columns.

Schema: pharmacy_dir

Table: pharmacy_exclusion_xref — cross-reference log recording which pharmacies
were flagged by OIG LEIE or SAM.gov exclusion checks.

Global reference data — no TenantScopedMixin (LESSON-011).
NPI plaintext — public registry identifier (LESSON-010).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import PharmacyBase

SCHEMA = "pharmacy_dir"


class PharmacyExclusionXref(PharmacyBase):
    """Cross-reference log recording which pharmacies were flagged by OIG/SAM.

    Populated by post-load UPDATE logic in OIG LEIE and SAM ingestion.
    One row per exclusion match event.

    Global reference — no TenantScopedMixin (LESSON-011).
    """

    __tablename__ = "pharmacy_exclusion_xref"
    __table_args__ = (
        UniqueConstraint(
            "pharmacy_npi", "exclusion_source", "exclusion_date",
            name="uq_pharmacy_excl_xref",
        ),
        Index("ix_pharmacy_excl_xref_npi", "pharmacy_npi"),
        Index("ix_pharmacy_excl_xref_source", "exclusion_source"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    pharmacy_npi: Mapped[str] = mapped_column(String(10), nullable=False)
    exclusion_source: Mapped[str] = mapped_column(String(50), nullable=False)
    exclusion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reinstatement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_currently_excluded: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    exclusion_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # SAM.gov UEI — for SAM-sourced exclusions matching via UEI
    uei_sam: Mapped[str | None] = mapped_column(String(20), nullable=True)

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = ["PharmacyExclusionXref"]
