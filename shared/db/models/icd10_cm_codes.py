"""ORM model for the CMS ICD-10-CM diagnosis code set.

Schema: shared
Table:  icd10_cm_codes

Published by CMS annually (October release) with a mid-year update (April).
Versioned on ``(code, effective_date)`` so retrospective claim adjudication
can resolve the description that was valid at the date of service.

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


class Icd10CmCode(Base):
    """One row per ICD-10-CM code per publication cycle.

    Example rows for code ``A000`` across publications:

        code='A000', effective_date=2025-10-01, long_description='Cholera ...'
        code='A000', effective_date=2026-04-01, long_description='Cholera ...'

    A claim with date of service 2026-02-15 resolves to the 2025-10-01 row.
    """

    __tablename__ = "icd10_cm_codes"
    __table_args__ = (
        UniqueConstraint(
            "code", "effective_date", name="uq_icd10_cm_codes_code_effective"
        ),
        Index("ix_icd10_cm_codes_effective_date", "effective_date"),
        Index("ix_icd10_cm_codes_code", "code"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(7), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_billable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    short_description: Mapped[str | None] = mapped_column(String(80), nullable=True)
    long_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ordinal_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_payload: Mapped[Any] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["Icd10CmCode"]
