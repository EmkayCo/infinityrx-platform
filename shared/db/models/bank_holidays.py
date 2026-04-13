"""ORM model for the ``core.bank_holidays`` table.

Stores US federal (and future international) bank holidays for NACHA batch
scheduling and business-day calculations.  No tenant scope — holidays are
platform-wide reference data.

Design notes
------------
* ``holiday_date`` uses SQLAlchemy ``Date`` (Python ``date``, not ``datetime``)
  — no timezone ambiguity for a calendar date.
* ``country`` is a two-character ISO 3166-1 alpha-2 code (e.g. "US").
* Unique constraint on (holiday_date, country) prevents duplicates while still
  allowing the same calendar date to carry different names per country.
* UUID primary key with ``gen_random_uuid()`` server default — consistent with
  every other table in the platform.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base

SCHEMA = "core"


class BankHoliday(Base):
    """A single bank holiday date for a given country."""

    __tablename__ = "bank_holidays"
    __table_args__ = (
        UniqueConstraint(
            "holiday_date",
            "country",
            name="uq_bank_holiday_date_country",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="US")
    is_federal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_bank_holiday: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BankHoliday {self.country} {self.holiday_date} {self.name!r}>"


__all__ = ["BankHoliday"]
