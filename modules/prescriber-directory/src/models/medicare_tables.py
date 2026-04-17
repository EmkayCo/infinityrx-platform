"""Medicare reference tables for the prescriber-directory module.

Schema: prescriber_dir

Tables:
  - MedicareOptOut — providers who have opted out of Medicare

LESSON-010: NPI is a public identifier — plaintext OK, do NOT encrypt.
LESSON-011: Global reference data — no TenantScopedMixin, no tenant_id.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .tables import PrescriberBase

SCHEMA = "prescriber_dir"


class MedicareOptOut(PrescriberBase):
    """Providers who have opted out of Medicare.

    Source: CMS Opt-Out Affidavits (Socrata API / CSV).
    PK: npi — one row per opted-out provider.

    LESSON-010: NPI plaintext.
    LESSON-011: Global reference — no TenantScopedMixin.
    """

    __tablename__ = "medicare_opt_out"
    __table_args__ = (
        sa.Index("idx_opt_out_end_date", "opt_out_end_date"),
        sa.Index("idx_opt_out_state", "state"),
        {"schema": SCHEMA},
    )

    npi: Mapped[str] = mapped_column(sa.String(10), primary_key=True)
    first_name: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    middle_name: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    specialty: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    opt_out_effective_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    opt_out_end_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    order_referring: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)
    address: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(sa.String(2), nullable=True)
    zip: Mapped[str | None] = mapped_column(sa.String(10), nullable=True)
    phone: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    raw_payload: Mapped[Any] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )


__all__ = ["MedicareOptOut", "SCHEMA"]
