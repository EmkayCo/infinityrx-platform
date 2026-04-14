"""Compliance cross-reference tables for prescriber-directory.

Schema: prescriber_dir

Tables:
- dea_registrations: DEA bulk file data (global ref — no TenantScopedMixin)
- prescriber_exclusion_xref: Cross-reference log for OIG/SAM exclusion matches

LESSON-011: Global reference → no TenantScopedMixin.
LESSON-010: NPI plaintext.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
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

from .tables import PrescriberBase

SCHEMA = "prescriber_dir"


class DeaRegistration(PrescriberBase):
    """DEA registrant data loaded from the DEA bulk file.

    When bulk file is unavailable (typical — requires NTIS agreement),
    the ingester operates in validator-only mode and this table remains empty.
    DEA number validation is still available via shared.utils.dea_validator.

    Global reference — no TenantScopedMixin (LESSON-011).
    """

    __tablename__ = "dea_registrations"
    __table_args__ = (
        Index("ix_dea_reg_npi", "npi"),
        Index("ix_dea_reg_activity_status", "business_activity", "registration_status"),
        Index("ix_dea_reg_expiration", "expiration_date"),
        {"schema": SCHEMA},
    )

    dea_number: Mapped[str] = mapped_column(String(9), primary_key=True)

    registrant_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Address
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    zip: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Classification
    business_activity: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Schedules authorized — stored as JSON list: ["2", "2N", "3", "3N", "4", "5"]
    drug_schedules_authorized: Mapped[Any] = mapped_column(JSON, nullable=True)

    expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    registration_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # NPI cross-reference (nullable — not all DEA registrants have NPI)
    npi: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Raw payload for forward-compatibility
    raw_payload: Mapped[Any] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PrescriberExclusionXref(PrescriberBase):
    """Cross-reference log recording which prescribers were flagged by OIG/SAM.

    Populated by post-load UPDATE logic in OIG LEIE and SAM ingestion.
    One row per exclusion match event — allows audit of when a flag was added
    or cleared.

    Global reference — no TenantScopedMixin (LESSON-011).
    """

    __tablename__ = "prescriber_exclusion_xref"
    __table_args__ = (
        UniqueConstraint(
            "prescriber_npi", "exclusion_source", "exclusion_date",
            name="uq_prescriber_excl_xref",
        ),
        Index("ix_prescriber_excl_xref_npi", "prescriber_npi"),
        Index("ix_prescriber_excl_xref_source", "exclusion_source"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    prescriber_npi: Mapped[str] = mapped_column(String(10), nullable=False)
    exclusion_source: Mapped[str] = mapped_column(String(50), nullable=False)
    exclusion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reinstatement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_currently_excluded: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    exclusion_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = ["DeaRegistration", "PrescriberExclusionXref"]
