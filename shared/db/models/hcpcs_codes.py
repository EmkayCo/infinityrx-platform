"""ORM model for the CMS HCPCS Level II code set.

Schema: shared
Table:  hcpcs_codes

Published by CMS quarterly (January / April / July / October). Level I
(CPT) codes are AMA-licensed and not included in this table — see the
HCPCS ingester for details.

Versioned on ``(code, is_modifier, publication_quarter)``. Each quarterly
load upserts by the full unique key; prior quarters stay intact so a
claim dated in a prior period resolves against the right publication.

Global reference — no TenantScopedMixin (LESSON-011).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base

SCHEMA = "shared"


class HcpcsCode(Base):
    """One row per HCPCS Level II code per quarterly publication.

    ``is_modifier`` distinguishes 2-char modifier codes (e.g. ``A1``) from
    full 5-char HCPCS codes (e.g. ``A0021``). Both live in the same table
    because the CMS source file does too — the only distinguishing marker
    in the raw record is a 3-char leading-space prefix in the code field.
    """

    __tablename__ = "hcpcs_codes"
    __table_args__ = (
        UniqueConstraint(
            "code",
            "is_modifier",
            "publication_quarter",
            name="uq_hcpcs_codes_code_modifier_quarter",
        ),
        Index("ix_hcpcs_codes_code_quarter", "code", "publication_quarter"),
        Index("ix_hcpcs_codes_publication_quarter", "publication_quarter"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(5), nullable=False)
    is_modifier: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_quarter: Mapped[str] = mapped_column(String(6), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)

    long_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_description: Mapped[str | None] = mapped_column(String(28), nullable=True)
    pricing_indicator: Mapped[str | None] = mapped_column(String(2), nullable=True)
    coverage_code: Mapped[str | None] = mapped_column(String(1), nullable=True)
    anesthesia_base_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action_code: Mapped[str | None] = mapped_column(String(1), nullable=True)
    added_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    action_effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    raw_payload: Mapped[Any] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["HcpcsCode"]
