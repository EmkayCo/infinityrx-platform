"""ORM model for SAM.gov federal exclusion list.

Schema: shared
Table: sam_exclusions

Global reference data — no TenantScopedMixin (LESSON-011).
Published by GSA/SAM.gov as public data.
NPI plaintext — public registry identifier (LESSON-010).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base

SCHEMA = "shared"


class SamExclusion(Base):
    """One row per excluded individual, firm, vessel, or entity in SAM.gov.

    Composite PK: (classification_type, name, exclusion_type, active_date).
    Indexed on npi, dunsNumber, ueiSAM for cross-reference lookups.
    """

    __tablename__ = "sam_exclusions"
    __table_args__ = (
        UniqueConstraint(
            "classification_type", "name", "exclusion_type", "active_date",
            name="uq_sam_exclusions_natural_key",
        ),
        Index("ix_sam_exclusions_npi", "npi"),
        Index("ix_sam_exclusions_duns", "duns_number"),
        Index("ix_sam_exclusions_uei", "uei_sam"),
        Index("ix_sam_exclusions_cage", "cage_code"),
        Index("ix_sam_exclusions_active_date", "active_date"),
        Index("ix_sam_exclusions_termination", "termination_date"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Classification
    classification_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Entity/individual name (full_name or company_name)
    name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Address
    address_line_1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state_province: Mapped[str | None] = mapped_column(String(50), nullable=True)
    zip_postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(3), nullable=True)

    # Identifiers
    duns_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    uei_sam: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cage_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    npi: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Exclusion details
    exclusion_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exclusion_program: Mapped[str | None] = mapped_column(String(100), nullable=True)
    agency: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Cross-reference to LEIE if overlap
    ct_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    additional_comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    # JSONB fallback for affiliations and any undocumented fields
    affiliations: Mapped[Any] = mapped_column(JSON, nullable=True)
    raw_payload: Mapped[Any] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["SamExclusion"]
