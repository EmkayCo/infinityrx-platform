"""ORM model for government program BIN/PCN reference table.

Schema: shared
Table: government_program_bins

Global reference data — NOT tenant-scoped (LESSON-011).
Government program BINs are federal/state payer identifiers shared across
all tenants. Anti-Kickback Statute (AKS) compliance requires identifying
these payers to block copay card assistance.

Plan types:
  MEDICARE_PART_D, MEDICARE_ADVANTAGE, MEDICAID_FFS, MEDICAID_MCO,
  TRICARE, VA, FEP, IHS, CHAMPVA

Confidence levels:
  HIGH   — BIN+PCN or BIN+PCN+Group uniquely identifies a government plan
  MEDIUM — BIN alone (also used for commercial); PCN distinguishes
  LOW    — Inferred; requires additional verification
"""

from __future__ import annotations

import uuid as _uuid_module
from datetime import date, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base

SCHEMA = "shared"

VALID_PLAN_TYPES = frozenset({
    "MEDICARE_PART_D",
    "MEDICARE_ADVANTAGE",
    "MEDICAID_FFS",
    "MEDICAID_MCO",
    "TRICARE",
    "VA",
    "FEP",
    "IHS",
    "CHAMPVA",
})

VALID_CONFIDENCE_LEVELS = frozenset({"HIGH", "MEDIUM", "LOW"})


class GovernmentProgramBin(Base):
    """One row per BIN/PCN/Group combination that identifies a government payer.

    The natural key is (bin, pcn, group_number) — NULLs are meaningful
    (a row with pcn=NULL covers all PCNs for that BIN at MEDIUM confidence).

    This is GLOBAL reference data: do NOT add tenant_id or TenantScopedMixin.
    See LESSON-011: reference registries are shared cross-tenant.
    """

    __tablename__ = "government_program_bins"
    __table_args__ = (
        UniqueConstraint(
            "bin",
            "pcn",
            "group_number",
            name="uq_gov_bins_bin_pcn_group",
        ),
        Index("idx_gov_bins_bin", "bin"),
        Index("idx_gov_bins_bin_pcn", "bin", "pcn"),
        Index("idx_gov_bins_plan_type", "plan_type"),
        Index("idx_gov_bins_state", "state"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=_uuid_module.uuid4,
        server_default=func.gen_random_uuid(),
    )

    bin: Mapped[str] = mapped_column(String(6), nullable=False)
    pcn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    group_number: Mapped[str | None] = mapped_column(String(20), nullable=True)

    plan_type: Mapped[str] = mapped_column(String(50), nullable=False)
    plan_subtype: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pbm_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    plan_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mco_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)

    government_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa.true()
    )

    # Pipe-delimited OCC codes that indicate a government plan when BIN is ambiguous
    occ_codes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # HIGH = BIN+PCN uniquely identifies gov plan
    # MEDIUM = BIN alone (also commercial); PCN distinguishes
    # LOW = inferred
    confidence: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="HIGH"
    )

    source: Mapped[str] = mapped_column(String(500), nullable=False)
    source_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    @property
    def occ_codes_list(self) -> list[str]:
        if not self.occ_codes:
            return []
        return [c.strip() for c in self.occ_codes.split("|") if c.strip()]


__all__ = ["GovernmentProgramBin", "VALID_PLAN_TYPES", "VALID_CONFIDENCE_LEVELS"]
